"""가격 검색 서비스 - 비즈니스 로직 오케스트레이션"""
import asyncio
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from src.services.impl.cache_service import CacheService
from src.crawlers.danawa import DanawaCrawler
from src.repositories.impl.search_log_repository import SearchLogRepository
from src.repositories.impl.search_failure_repository import SearchFailureRepository
from src.repositories.impl.price_cache_repository import PriceCacheRepository
from src.utils.search import DanawaSearchHelper
from src.core.logging import logger
from src.core.exceptions import ProductNotFoundException, CrawlerException
from src.core.config import settings


class PriceSearchService:
    """
    가격 검색 서비스 - SRP: 비즈니스 로직 조율만 담당
    
    - 캐시 조회는 CacheService
    - 크롤링은 DanawaCrawler
    - DB 저장은 SearchLogRepository
    """
    
    def __init__(self, cache_service: CacheService, db_session: Optional[Session] = None):
        self.cache_service = cache_service
        self.db_session = db_session
        self.search_helper = DanawaSearchHelper()
    
    async def search_price(
        self,
        product_name: str,
        current_price: Optional[int] = None,
        product_code: Optional[str] = None
    ) -> Dict:
        """
        최저가 검색 (Cache-First 전략)
        
        1. Redis 캐시 확인 (정규화된 상품명 기준)
        2. 캐시 미스 시 크롤링
        3. 결과 캐싱 및 반환
        
        Args:
            product_name: 검색할 상품명
            current_price: 사용자가 보고 있는 현재 가격
            
        Returns:
            {
                "lowest_price": int,
                "link": str,
                "is_cheaper": bool,
                "price_diff": int,
                "status": str,  # HIT, MISS, FAIL
                "message": str
            }
        """
        # 검색어를 먼저 정규화하여 캐시 키와 검색 일관성 유지
        from src.utils.text import clean_product_name, normalize_search_query
        
        # 정규화된 상품명으로 캐시 키 생성
        normalized_name = normalize_search_query(product_name) or clean_product_name(product_name)
        search_key = clean_product_name(normalized_name)
        
        logger.info(f"Search request: {product_name}")
        logger.info(f"Normalized query for search: {normalized_name}")
        logger.debug(f"Cache key: {search_key}")

        # 1. 캐시 확인
        cached = self.cache_service.get(search_key)
        
        if cached:
            logger.info(f"Cache hit for key: {search_key}")
            return self._build_response(
                result=cached.model_dump(),
                current_price=current_price,
                status="HIT",
                message="캐시에서 발견했습니다."
            )

        # 1-1. 부정 캐시 확인 (최근 미발견이면 크롤링 재시도 억제)
        negative_message = self.cache_service.get_negative(search_key)
        if negative_message:
            logger.info(f"Negative cache hit for: {search_key}")
            return self._build_error_response(negative_message)

        # 1-2. DB 영속 캐시 확인 (Redis 미스/부정 캐시 없음)
        # DB에 저장된 깨끗한 product_name을 재사용하여 매번 정규화 작업을 피함
        if self.db_session is not None:
            db_cached = PriceCacheRepository(self.db_session).get_fresh(
                cache_key=search_key,
                max_age_seconds=int(settings.cache_ttl),
            )
            if db_cached:
                # Redis에도 재적재하여 이후 요청은 더 빠르게
                try:
                    self.cache_service.set(search_key, db_cached)
                except Exception:
                    pass
                logger.info(f"DB cache hit for key: {search_key}, product_name={db_cached.get('product_name', 'N/A')}")
                return self._build_response(
                    result=db_cached,
                    current_price=current_price,
                    status="HIT",
                    message="DB 캐시에서 발견했습니다.",
                )
        
        # 1-3. 🔴 Hard Skip 확인 (3회 이상 연속 실패 → 즉시 거절)
        if self.cache_service.should_hard_skip(search_key, max_failures=3):
            msg = "이 상품은 반복적으로 검색 실패했습니다. (최근 3회 실패)"
            logger.warning(f"Hard skip activated for: {search_key}")
            return self._build_error_response(msg)
        logger.info(f"Cache miss, crawling for: {search_key}")
        
        try:
            async with DanawaCrawler() as crawler:
                # ✅ 캐시와 크롤링 모두 정규화된 쿼리 사용
                # 이전: 원본 product_name을 크롤러에 전달 → 중복 정규화 + 신호 손실
                # 개선: 정규화된 normalized_name을 직접 전달
                result = await crawler.search_lowest_price(normalized_name, product_code=product_code)
            
            if not result:
                msg = "검색 결과를 찾을 수 없습니다."
                self.cache_service.set_negative(search_key, msg)
                return self._build_error_response(msg)
            
            # 3. 캐싱
            self.cache_service.set(search_key, result)
            # 🟢 성공 → 실패 카운트 초기화
            self.cache_service.reset_failure_count(search_key)

            # 3-1. DB에도 영속 캐시 저장 (선택)
            # DB에 저장된 깨끗한 product_name을 다음 요청에서 재사용할 수 있음
            if self.db_session is not None:
                try:
                    logger.debug(f"Saving to DB cache: {search_key}, product_name={result.get('product_name', 'N/A')}")
                    PriceCacheRepository(self.db_session).upsert(search_key, result)
                except Exception as e:
                    # DB 캐시 실패는 기능적 실패가 아니므로 무시
                    logger.warning(f"DB cache write failed: {e}")
                    pass
            
            return self._build_response(
                result=result,
                current_price=current_price,
                status="MISS",
                message="다나와에서 새로 검색했습니다."
            )
        
        except asyncio.TimeoutError:
            msg = "요청 시간 초과"
            logger.warning(f"Search timeout for: {product_name}")
            self.cache_service.set_negative(search_key, msg)
            # 🔴 실패 카운트 증가
            fail_count = self.cache_service.increment_failure_count(search_key)
            self._record_search_failure(
                product_name=product_name,
                normalized_name=normalized_name,
                error_message=f"{msg} (fail_count={fail_count})",
            )
            return self._build_error_response(msg)

        except ProductNotFoundException as e:
            logger.warning(f"Product not found: {e}")
            msg = str(e)
            self.cache_service.set_negative(search_key, msg)
            # 🔴 실패 카운트 증가
            fail_count = self.cache_service.increment_failure_count(search_key)
            
            # 실패 기록 저장 (학습용)
            self._record_search_failure(
                product_name=product_name,
                normalized_name=normalized_name,
                error_message=f"{msg} (fail_count={fail_count})"
            )
            
            return self._build_error_response(msg)
        
        except CrawlerException as e:
            logger.error(f"Crawler error: {e}")
            # 🔴 실패 카운트 증가
            fail_count = self.cache_service.increment_failure_count(search_key)
            
            # 실패 기록 저장
            self._record_search_failure(
                product_name=product_name,
                normalized_name=normalized_name,
                error_message=f"Crawler error: {str(e)} (fail_count={fail_count})"
            )
            
            return self._build_error_response("크롤링 중 오류가 발생했습니다.")
        
        except Exception as e:
            logger.error(f"Unexpected error in search_price: {e}")
            # 🔴 실패 카운트 증가
            fail_count = self.cache_service.increment_failure_count(search_key)
            
            # 실패 기록 저장
            self._record_search_failure(
                product_name=product_name,
                normalized_name=normalized_name,
                error_message=f"Unexpected error: {str(e)} (fail_count={fail_count})"
            )
            
            return self._build_error_response("검색 중 오류가 발생했습니다.")
    
    def _build_response(
        self,
        result: Dict[str, Any],
        current_price: Optional[int],
        status: str,
        message: str
    ) -> Dict:
        """성공 응답 생성"""
        product_name = result.get("product_name", "")
        lowest_price = result.get("lowest_price", 0)
        link = result.get("link", "")
        mall = result.get("mall")
        free_shipping = result.get("free_shipping")
        top_prices = result.get("top_prices")
        price_trend = result.get("price_trend")

        is_cheaper = False
        price_diff = 0
        
        if current_price is not None:
            is_cheaper = lowest_price < current_price
            price_diff = lowest_price - current_price
        
        return {
            "product_name": product_name,
            "lowest_price": lowest_price,
            "link": link,
            "mall": mall,
            "free_shipping": free_shipping,
            "top_prices": top_prices,
            "price_trend": price_trend,
            "is_cheaper": is_cheaper,
            "price_diff": price_diff,
            "status": status,
            "message": message
        }
    
    def _build_error_response(self, message: str) -> Dict:
        """실패 응답 생성"""
        return {
            "product_name": "",
            "lowest_price": 0,
            "link": "",
            "mall": None,
            "free_shipping": None,
            "top_prices": None,
            "price_trend": None,
            "is_cheaper": False,
            "price_diff": 0,
            "status": "FAIL",
            "message": message
        }
    
    async def log_search(
        self,
        db: Session,
        query_name: str,
        origin_price: Optional[int],
        found_price: Optional[int],
        status: str
    ) -> None:
        """
        검색 로그 저장 (백그라운드 작업)
        
        Args:
            db: DB 세션
            query_name: 검색한 상품명
            origin_price: 사용자가 보던 원래 가격
            found_price: 찾아낸 최저가
            status: HIT, MISS, FAIL
        """
        try:
            repo = SearchLogRepository(db)
            repo.create(
                query_name=query_name,
                origin_price=origin_price,
                found_price=found_price,
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to log search: {e}")
    
    def _record_search_failure(
        self,
        product_name: str,
        normalized_name: str,
        error_message: str,
        attempted_count: int = 1
    ) -> None:
        """
        검색 실패 기록 (학습 데이터 수집)
        
        Args:
            product_name: 원본 상품명
            normalized_name: 정규화된 상품명
            error_message: 에러 메시지
            attempted_count: 시도 횟수
        """
        if not self.db_session:
            logger.debug("DB session not available for failure logging")
            return
        
        try:
            # 카테고리 및 브랜드/모델 추출
            category = self.search_helper.detect_category(product_name)
            brand, model = self.search_helper.extract_brand_and_model(product_name)
            
            # 시도한 후보 생성
            candidates = self.search_helper.generate_search_candidates(product_name)
            
            # 실패 기록 저장
            SearchFailureRepository.record_failure(
                db=self.db_session,
                original_query=product_name,
                normalized_query=normalized_name,
                candidates=candidates,
                attempted_count=attempted_count,
                error_message=error_message,
                category_detected=category,
                brand=brand,
                model=model
            )
            
            logger.info(f"Recorded search failure for: {product_name}")
        
        except Exception as e:
            logger.error(f"Failed to record search failure: {e}")

