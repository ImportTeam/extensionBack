"""API 엔드포인트 - 가격 검색 및 통계"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.schemas.price_schema import (
    PriceSearchRequest,
    PriceSearchResponse,
    PriceData,
    StatisticsResponse,
    PopularQuery
)
from src.services.impl.price_search_service import PriceSearchService
from src.services.impl.cache_service import CacheService
from src.repositories.impl.search_log_repository import SearchLogRepository
from src.core.logging import logger
from src.utils.url import extract_pcode_from_url
from src.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["price"])

# 싱글톤 서비스 (FastAPI 앱 생명주기에서 관리)
_cache_service = None


def get_cache_service() -> CacheService:
    """CacheService 인스턴스 제공"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def get_price_service(
    cache_service: CacheService = Depends(get_cache_service),
    db: Session = Depends(get_db),
) -> PriceSearchService:
    """PriceSearchService 인스턴스 제공"""
    return PriceSearchService(cache_service, db_session=db)


@router.post("/price/search", response_model=PriceSearchResponse)
async def search_price(
    request: PriceSearchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    price_service: PriceSearchService = Depends(get_price_service)
):
    """
    최저가 검색 API
    
    1. Redis 캐시 확인 (HIT: 즉시 반환)
    2. 캐시 미스 시 다나와 크롤링
    3. 결과를 Redis에 캐싱
    4. 로그를 DB에 백그라운드로 저장
    """
    logger.info(f"Search request: {request.product_name}")
    
    # URL에서 pcode 추출 (product_code가 없으면)
    product_code = request.product_code
    if not product_code and request.current_url:
        product_code = extract_pcode_from_url(request.current_url)
        logger.info(f"Extracted pcode from URL: {product_code}")
    
    try:
        # 최저가 검색
        # FE(브라우저) 타임아웃(15s)보다 짧게 하드 캡을 걸어 응답이 끊기는 문제를 방지
        result = await asyncio.wait_for(
            price_service.search_price(
                product_name=request.product_name,
                current_price=request.current_price,
                product_code=product_code,
            ),
            timeout=float(getattr(settings, "api_price_search_timeout_s", 14.0)),
        )
        
        # 백그라운드로 로그 저장
        background_tasks.add_task(
            price_service.log_search,
            db=db,
            query_name=request.product_name,
            origin_price=request.current_price,
            found_price=result["lowest_price"] if result["status"] != "FAIL" else None,
            status=result["status"]
        )
        
        # 응답 생성
        if result["status"] != "FAIL":
            return PriceSearchResponse(
                status="success",
                data=PriceData(
                    product_name=result.get("product_name", request.product_name),
                    is_cheaper=result["is_cheaper"],
                    price_diff=result["price_diff"],
                    lowest_price=result["lowest_price"],
                    link=result["link"],
                    mall=result.get("mall"),
                    free_shipping=result.get("free_shipping"),
                    top_prices=result.get("top_prices"),
                    price_trend=result.get("price_trend")
                ),
                message=result["message"]
            )
        else:
            return PriceSearchResponse(
                status="fail",
                data=None,
                message=result["message"]
            )
    
    except Exception as e:
        logger.error(f"API Error: {e}")
        
        # 에러 로그 저장
        background_tasks.add_task(
            price_service.log_search,
            db=db,
            query_name=request.product_name,
            origin_price=request.current_price,
            found_price=None,
            status="FAIL"
        )
        
        return PriceSearchResponse(
            status="fail",
            data=None,
            message="서버 오류가 발생했습니다."
        )


@router.get("/stats", response_model=StatisticsResponse)
async def get_statistics(db: Session = Depends(get_db)):
    """
    통계 API
    
    - 총 검색 횟수
    - 캐시 히트율
    - 인기 검색어 Top 5
    """
    repo = SearchLogRepository(db)
    
    total_searches = repo.get_total_count()
    cache_hits = repo.get_cache_hit_count()
    hit_rate = (cache_hits / total_searches * 100) if total_searches > 0 else 0
    
    popular_queries_data = repo.get_popular_queries(limit=5)
    popular_queries = [
        PopularQuery(name=name, count=count)
        for name, count in popular_queries_data
    ]
    
    logger.info(f"Statistics requested: {total_searches} searches, {hit_rate:.2f}% hit rate")
    
    return StatisticsResponse(
        total_searches=total_searches,
        cache_hits=cache_hits,
        hit_rate=round(hit_rate, 2),
        popular_queries=popular_queries
    )
