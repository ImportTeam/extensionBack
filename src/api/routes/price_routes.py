"""Price Routes (Engine Layer) - Refactored to use SearchOrchestrator

HTTP Layer가 Engine Layer로 요청을 위임하는 단순한 Translator 역할만 수행합니다.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.core.logging import logger
from src.crawlers import FastPathExecutor, SlowPathExecutor
from src.engine import BudgetConfig, CacheAdapter, SearchOrchestrator, SearchStatus
from src.repositories.impl.search_log_repository import SearchLogRepository
from src.schemas.price_schema import (
    PriceData,
    PriceSearchRequest,
    PriceSearchResponse,
)
from src.services.impl.cache_service import CacheService
from src.utils.text_utils import normalize_for_search_query
from src.utils.url import extract_pcode_from_url

router = APIRouter(prefix="/api/v1", tags=["price"])

# 싱글톤 서비스
_cache_service: Optional[CacheService] = None
_orchestrator: Optional[SearchOrchestrator] = None


def get_cache_service() -> CacheService:
    """CacheService 싱글톤"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def get_orchestrator(
    cache_service: CacheService = Depends(get_cache_service),
) -> SearchOrchestrator:
    """SearchOrchestrator 싱글톤

    Engine Layer의 진입점을 제공합니다.
    """
    global _orchestrator
    if _orchestrator is None:
        cache_adapter = CacheAdapter(cache_service)
        fastpath = FastPathExecutor()
        slowpath = SlowPathExecutor()

        # 12초 예산 설정
        budget_config = BudgetConfig(
            total_budget=12.0,
            cache_timeout=0.2,
            fastpath_timeout=3.0,
            slowpath_timeout=9.0,
        )

        _orchestrator = SearchOrchestrator(
            cache_service=cache_adapter,
            fastpath_executor=fastpath,
            slowpath_executor=slowpath,
            budget_config=budget_config,
        )

    return _orchestrator


@router.post("/price/search", response_model=PriceSearchResponse)
async def search_price(
    request: PriceSearchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    orchestrator: SearchOrchestrator = Depends(get_orchestrator),
):
    """최저가 검색 API (Engine Layer)

    HTTP → Engine → Cache/FastPath/SlowPath 파이프라인으로 실행

    Flow:
        1. HTTP Request 수신
        2. 쿼리 정규화
        3. Engine에 위임 (Cache → FastPath → SlowPath)
        4. 결과를 HTTP Response로 변환
        5. 백그라운드로 로그 저장
    """
    logger.info(f"[API] Search request: product_name='{request.product_name}'")

    # URL에서 pcode 추출
    product_code = request.product_code
    if not product_code and request.current_url:
        product_code = extract_pcode_from_url(request.current_url)
        logger.debug(f"[API] Extracted pcode from URL: {product_code}")

    # 쿼리 정규화
    normalized_query = normalize_for_search_query(request.product_name)

    try:
        # Engine Layer로 위임 (14초 타임아웃)
        result = await asyncio.wait_for(
            orchestrator.search(normalized_query),
            timeout=float(getattr(settings, "api_price_search_timeout_s", 14.0)),
        )

        # 백그라운드 로그 저장
        background_tasks.add_task(
            _log_search,
            db=db,
            query_name=request.product_name,
            origin_price=request.current_price,
            found_price=result.price if result.is_success else None,
            status="SUCCESS" if result.is_success else "FAIL",
            source=result.source,
            elapsed_ms=result.elapsed_ms,
        )

        # 성공 응답
        if result.is_success:
            is_cheaper = (
                result.price < request.current_price
                if request.current_price
                else False
            )
            price_diff = (
                request.current_price - result.price if request.current_price else 0
            )

            return PriceSearchResponse(
                status="success",
                data=PriceData(
                    product_name=request.product_name,
                    is_cheaper=is_cheaper,
                    price_diff=price_diff,
                    lowest_price=result.price,
                    link=result.product_url,
                    mall="다나와",
                    free_shipping=None,  # TODO: 배송비 정보
                    top_prices=None,  # TODO: TOP 가격 정보
                    price_trend=None,  # TODO: 가격 추이
                    source=result.source,
                    elapsed_ms=result.elapsed_ms,
                ),
                message="최저가를 찾았습니다.",
                error_code=None,
            )

        # 실패 응답
        error_message = _get_error_message(result.status)
        return PriceSearchResponse(
            status="error",
            data=None,
            message=error_message,
            error_code=result.status.value,
        )

    except asyncio.TimeoutError:
        logger.error(f"[API] Timeout: query='{normalized_query}'")
        return PriceSearchResponse(
            status="error",
            data=None,
            message="검색 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
            error_code="TIMEOUT",
        )
    except Exception as e:
        logger.error(f"[API] Search failed: query='{normalized_query}'", exc_info=True)
        return PriceSearchResponse(
            status="error",
            data=None,
            message=f"검색 중 오류가 발생했습니다: {str(e)}",
            error_code="INTERNAL_ERROR",
        )


def _get_error_message(status: SearchStatus) -> str:
    """상태별 에러 메시지 반환"""
    messages = {
        SearchStatus.TIMEOUT: "검색 시간이 초과되었습니다.",
        SearchStatus.PARSE_ERROR: "검색 결과를 처리하는 중 오류가 발생했습니다.",
        SearchStatus.BLOCKED: "일시적으로 검색이 제한되었습니다. 잠시 후 다시 시도해주세요.",
        SearchStatus.NO_RESULTS: "검색 결과를 찾을 수 없습니다.",
        SearchStatus.BUDGET_EXHAUSTED: "검색 시간이 초과되었습니다.",
    }
    return messages.get(status, "검색 중 오류가 발생했습니다.")


def _log_search(
    db: Session,
    query_name: str,
    origin_price: Optional[int],
    found_price: Optional[int],
    status: str,
    source: Optional[str] = None,
    elapsed_ms: Optional[float] = None,
):
    """검색 로그 저장 (백그라운드)"""
    try:
        repo = SearchLogRepository(db)
        repo.create(
            query_name=query_name,
            origin_price=origin_price,
            found_price=found_price,
            status=status,
        )
        db.commit()
        logger.debug(f"[API] Search log saved: query='{query_name}', status={status}")
    except Exception as e:
        logger.error(f"[API] Failed to save search log: {e}")
        db.rollback()


# 통계 API는 추후 Engine Layer로 마이그레이션 예정
# 현재는 legacy 로직 사용
@router.get("/price/statistics")
async def get_search_statistics(db: Session = Depends(get_db)):
    """검색 통계 API
    
    Returns:
        - total_searches: 총 검색 횟수
        - cache_hits: 캠시 히트 횟수
        - hit_rate: 캠시 히트율 (%)
        - popular_queries: 인기 검색어 Top 5
    """
    from src.repositories.impl.search_log_repository import SearchLogRepository
    from src.schemas.price_schema import StatisticsResponse, PopularQuery
    
    repo = SearchLogRepository(db)
    
    total_searches = repo.get_total_count()
    cache_hits = repo.get_cache_hit_count()
    hit_rate = (cache_hits / total_searches * 100) if total_searches > 0 else 0
    
    popular_queries_data = repo.get_popular_queries(limit=5)
    popular_queries = [
        PopularQuery(name=name, count=count)
        for name, count in popular_queries_data
    ]
    
    logger.info(f"Statistics: {total_searches} searches, {hit_rate:.2f}% hit rate")
    
    return StatisticsResponse(
        total_searches=total_searches,
        cache_hits=cache_hits,
        hit_rate=round(hit_rate, 2),
        popular_queries=popular_queries
    )


@router.get("/price/popular")
async def get_popular_queries_api(db: Session = Depends(get_db), limit: int = 10):
    """인기 검색어 API
    
    Args:
        limit: 반환할 검색어 수 (기본 10개)
    
    Returns:
        인기 검색어 목록
    """
    from src.repositories.impl.search_log_repository import SearchLogRepository
    from src.schemas.price_schema import PopularQuery
    
    repo = SearchLogRepository(db)
    popular_queries_data = repo.get_popular_queries(limit=limit)
    
    popular_queries = [
        PopularQuery(name=name, count=count)
        for name, count in popular_queries_data
    ]
    
    logger.info(f"Popular queries requested: top {limit}")
    
    return {"popular_queries": popular_queries}
