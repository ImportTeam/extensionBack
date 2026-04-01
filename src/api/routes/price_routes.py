"""Price Routes (Engine Layer) - Refactored to use SearchOrchestrator

HTTP Layer가 Engine Layer로 요청을 위임하는 단순한 Translator 역할만 수행합니다.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.core.logging import logger
from src.crawlers import FastPathExecutor, SlowPathExecutor, DisabledSlowPathExecutor
from src.engine import BudgetConfig, CacheAdapter, SearchOrchestrator, SearchResult, SearchStatus
from src.repositories.impl.search_log_repository import SearchLogRepository
from src.schemas.price_schema import (
    MallPrice,
    PriceData,
    PriceSearchRequest,
    PriceSearchResponse,
    PriceTrendPoint,
)
from src.services.impl.cache_service import CacheService
from src.utils.text_utils import (
    build_option_query_tokens,
    normalize_for_search_query,
    parse_fe_options_text,
)
from src.utils.url import extract_pcode_from_url

router = APIRouter(prefix="/api/v1", tags=["price"])

# 싱글톤 서비스
_cache_service: Optional[CacheService] = None
_orchestrator: Optional[SearchOrchestrator] = None


@dataclass(frozen=True)
class SearchRequestContext:
    request_product_name: str
    normalized_query: str
    search_query: str
    product_code: str | None
    selected_options: list | None


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

        if settings.crawler_slowpath_backend == "disabled":
            slowpath = DisabledSlowPathExecutor()
        elif settings.crawler_slowpath_backend == "playwright":
            slowpath = SlowPathExecutor()
        else:
            # drissionpage 등은 아직 구현체가 없을 수 있으므로 명시적으로 막습니다.
            raise ValueError(
                f"Unsupported crawler_slowpath_backend: {settings.crawler_slowpath_backend}"
            )

        budget_config = BudgetConfig.from_settings(settings)

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
    """최저가 검색 API (Engine Layer + Security Enhanced)

    HTTP → Engine → Cache/FastPath/SlowPath 파이프라인으로 실행

    Flow:
        1. HTTP Request 수신 (보안 검증)
        2. 쿼리 정규화
        3. Engine에 위임 (Cache → FastPath → SlowPath)
        4. 결과를 HTTP Response로 변환
        5. 백그라운드로 로그 저장
    """
    from src.core.security import SecurityValidator
    
    try:
        # Security validation
        SecurityValidator.validate_query(request.product_name)
        if request.current_url:
            SecurityValidator.validate_url(request.current_url)
        if request.current_price is not None:
            SecurityValidator.validate_price(request.current_price)
    except ValueError as e:
        logger.warning(f"[API] Input validation failed: {e}")
        return PriceSearchResponse(
            status="error",
            data=None,
            message=f"입력 검증 실패: {str(e)}",
            error_code="VALIDATION_ERROR",
        )

    logger.info(f"[API] Search request: product_name (length: {len(request.product_name)})")
    try:
        context = _build_search_context(request)
    except Exception as e:
        logger.error(f"[API] Query normalization failed: {e}")
        return PriceSearchResponse(
            status="error",
            data=None,
            message="검색어 정규화 실패",
            error_code="NORMALIZATION_ERROR",
        )

    try:
        timeout_s = settings.api_price_search_timeout_s
        result = await asyncio.wait_for(
            orchestrator.search(context.search_query, product_code=context.product_code),
            timeout=timeout_s,
        )

        background_tasks.add_task(
            _log_search,
            db=db,
            query_name=_build_log_query_name(request),
            origin_price=request.current_price,
            found_price=result.price if result.is_success else None,
            product_id=result.product_id if result.is_success else None,
            status="SUCCESS" if result.is_success else "FAIL",
            source=result.source,
            elapsed_ms=result.elapsed_ms,
            top_prices=_dump_optional_json(result.top_prices),
            price_trend=_dump_optional_json(result.price_trend),
        )

        if result.is_success:
            return _build_success_response(request, result)

        # 실패 응답
        error_message = _get_error_message(result.status)
        return PriceSearchResponse(
            status="error",
            data=None,
            message=error_message,
            error_code=result.status.value,
            selected_options=request.selected_options,
        )

    except asyncio.TimeoutError:
        logger.error(f"[API] Timeout: query='{context.normalized_query}'")
        return PriceSearchResponse(
            status="error",
            data=None,
            message="검색 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
            error_code="TIMEOUT",
            selected_options=request.selected_options,
        )
    except Exception as e:
        logger.error(f"[API] Search failed: query='{context.normalized_query}'", exc_info=True)
        return PriceSearchResponse(
            status="error",
            data=None,
            message=f"검색 중 오류가 발생했습니다: {str(e)}",
            error_code="INTERNAL_ERROR",
            selected_options=request.selected_options,
        )


def _build_search_context(request: PriceSearchRequest) -> SearchRequestContext:
    product_code = request.product_code
    if not product_code and request.current_url:
        try:
            product_code = extract_pcode_from_url(request.current_url)
            logger.debug("[API] Extracted pcode from URL")
        except Exception as e:
            logger.warning(f"[API] Failed to extract pcode from URL: {e}")

    normalized_query = normalize_for_search_query(request.product_name)
    if not normalized_query:
        raise ValueError("Normalized query is empty")

    try:
        option_tokens = _build_option_tokens(request)
    except Exception as e:
        logger.warning(f"[API] Failed to apply option filters: {e}")
        option_tokens = []
    search_query = normalized_query
    if option_tokens:
        search_query = f"{normalized_query} {' '.join(option_tokens)}"
        logger.info(f"[API] Options applied: tokens={option_tokens[:8]} (total={len(option_tokens)})")
    elif request.options_text or request.selected_options:
        logger.warning("[API] Options provided but all tokens were filtered out")

    return SearchRequestContext(
        request_product_name=request.product_name,
        normalized_query=normalized_query,
        search_query=search_query,
        product_code=product_code,
        selected_options=request.selected_options,
    )


def _build_option_pairs(request: PriceSearchRequest) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if request.selected_options:
        pairs.extend(
            [(opt.name, opt.value) for opt in request.selected_options if opt.name and opt.value]
        )
    if request.options_text:
        pairs.extend(parse_fe_options_text(request.options_text))
    return pairs


def _build_option_tokens(request: PriceSearchRequest, max_tokens: int | None = None) -> list[str]:
    pairs = _build_option_pairs(request)
    if not pairs:
        return []
    kwargs = {"max_tokens": max_tokens} if max_tokens is not None else {}
    return build_option_query_tokens(pairs, **kwargs)


def _build_log_query_name(request: PriceSearchRequest) -> str:
    try:
        log_tokens = _build_option_tokens(request, max_tokens=10)
    except Exception:
        return request.product_name
    if not log_tokens:
        return request.product_name
    return f"{request.product_name} [{', '.join(log_tokens)}]"


def _dump_optional_json(value) -> str | None:
    if not value:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return None


def _to_mall_prices(top_prices_data) -> tuple[list[MallPrice] | None, str | None, bool | None, str | None]:
    if not isinstance(top_prices_data, list) or not top_prices_data:
        return None, None, None, None

    prices_as_dicts = []
    for item in top_prices_data:
        if isinstance(item, MallPrice):
            prices_as_dicts.append(item.model_dump())
        elif isinstance(item, dict):
            prices_as_dicts.append(item)

    sorted_prices = sorted(prices_as_dicts, key=lambda x: x.get("price", float("inf")))[:3]
    if not sorted_prices:
        return None, None, None, None

    mall_prices = [
        MallPrice(
            rank=index + 1,
            mall=item.get("mall", "알 수 없음"),
            price=item.get("price", 0),
            free_shipping=item.get("free_shipping", False),
            delivery=item.get("delivery", ""),
            link=item.get("link", ""),
        )
        for index, item in enumerate(sorted_prices)
    ]
    top_item = sorted_prices[0]
    return (
        mall_prices,
        top_item.get("mall", "알 수 없음"),
        top_item.get("free_shipping", False),
        top_item.get("link"),
    )


def _to_price_trend_points(price_trend_data) -> list[PriceTrendPoint] | None:
    if not isinstance(price_trend_data, list):
        return None
    points: list[PriceTrendPoint] = []
    for item in price_trend_data:
        if isinstance(item, PriceTrendPoint):
            points.append(item)
        elif isinstance(item, dict):
            try:
                points.append(PriceTrendPoint(**item))
            except Exception:
                continue
    return points or None


def _build_success_response(request: PriceSearchRequest, result: SearchResult) -> PriceSearchResponse:
    lowest_price = result.price if result.price is not None else 0
    is_cheaper = False
    price_diff = 0
    if request.current_price is not None and request.current_price > 0 and lowest_price > 0:
        is_cheaper = lowest_price < request.current_price
        price_diff = request.current_price - lowest_price

    link = result.product_url or ""
    top_prices_list, top_mall, top_free_shipping, top_link = _to_mall_prices(result.top_prices)
    resolved_product_name = result.product_name or request.product_name

    return PriceSearchResponse(
        status="success",
        data=PriceData(
            product_name=resolved_product_name,
            product_id=result.product_id,
            is_cheaper=is_cheaper,
            price_diff=price_diff,
            lowest_price=lowest_price,
            link=top_link or link,
            mall=top_mall if top_mall is not None else result.mall,
            free_shipping=top_free_shipping if top_free_shipping is not None else result.free_shipping,
            top_prices=top_prices_list,
            price_trend=_to_price_trend_points(result.price_trend),
            selected_options=request.selected_options,
            source=result.source or "unknown",
            elapsed_ms=result.elapsed_ms or 0.0,
        ),
        message="검색 완료",
        error_code=None,
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
    product_id: Optional[str] = None,
    top_prices: Optional[str] = None,
    price_trend: Optional[str] = None,
):
    """검색 로그 저장 (백그라운드)"""
    try:
        repo = SearchLogRepository(db)
        repo.create(
            query_name=query_name,
            origin_price=origin_price,
            found_price=found_price,
            product_id=product_id,
            status=status,
            source=source,
            elapsed_ms=elapsed_ms,
            top_prices=top_prices,
            price_trend=price_trend,
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
