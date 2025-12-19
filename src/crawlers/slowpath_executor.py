"""SlowPath Executor - Enhanced Type Safety & Exception Handling"""

from typing import Optional, Dict, Any
from asyncio import TimeoutError as AsyncTimeoutError

from src.core.logging import logger
from src.core.exceptions import ProductNotFoundException
from src.utils.text_utils import build_cache_key, normalize_for_search_query
from src.utils.edge_cases import EdgeCaseHandler

from .executor import SearchExecutor
from .result import CrawlResult


class SlowPathExecutor(SearchExecutor):
    """Playwright 기반 느린 경로 실행자 (타입 안전 버전)

    기존 playwright/ 로직을 SearchExecutor 인터페이스로 래핑합니다.

    특징:
    - Playwright 브라우저 렌더링 (느림, 비용 높음)
    - JavaScript 실행 지원
    - 복잡한 페이지 처리 가능
    - 타임아웃 9초 권장
    - 완전한 타입 힌트 및 예외 처리

    Usage:
        executor = SlowPathExecutor()
        result = await executor.execute("삼성 갤럭시 S24", timeout=9.0)
    """

    def __init__(self, crawler: Optional[Any] = None):
        """
        Args:
            crawler: DanawaCrawler 인스턴스 (선택, 없으면 내부 생성)
        """
        self.crawler = crawler
        self._browser_manager: Optional[Any] = None

    async def execute(self, query: str, timeout: float) -> CrawlResult:
        """Playwright SlowPath 실행

        Args:
            query: 검색어
            timeout: 타임아웃 (초)

        Returns:
            CrawlResult: 크롤링 결과

        Raises:
            AsyncTimeoutError: 타임아웃
            ProductNotFoundException: 상품을 찾을 수 없음
            ValueError: 쿼리 또는 타임아웃이 유효하지 않음
            Exception: 기타 크롤링 오류
        """
        from src.crawlers.playwright.search import search_product
        from src.crawlers.playwright.detail import get_product_lowest_price
        from src.crawlers.playwright import ensure_shared_browser, new_page

        # Input validation
        try:
            if not query or not isinstance(query, str):
                raise ValueError(f"Invalid query: {query}")
            
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise ValueError(f"Invalid timeout: {timeout}")
        except ValueError:
            raise

        logger.debug(f"[SlowPath] Executing: query='{query}', timeout={timeout:.2f}s")

        # 쿼리 정규화
        try:
            normalized_query = normalize_for_search_query(query)
            if not normalized_query:
                logger.warning(f"[SlowPath] Normalized query is empty for: {query}")
                raise ValueError(f"Normalized query is empty for: {query}")
        except Exception as e:
            logger.error(f"[SlowPath] Query normalization failed: {type(e).__name__}: {e}")
            raise

        page = None
        try:
            # Playwright 초기화
            try:
                browser = await ensure_shared_browser()
                page = await new_page()
            except Exception as e:
                logger.error(f"[SlowPath] Failed to initialize browser: {type(e).__name__}: {e}")
                raise

            # 1단계: 상품 검색 (pcode 추출)
            try:
                search_url_base = "https://search.danawa.com/dsearch.php"
                
                # 타임아웃 계산: 전체 타임아웃의 40%를 검색에 할당
                search_timeout = timeout * 0.4
                
                pcode = await search_product(
                    create_page=lambda: new_page(),
                    search_url_base=search_url_base,
                    search_query=normalized_query,
                    overall_timeout_s=search_timeout,
                )

                if not pcode or not isinstance(pcode, str):
                    logger.warning(f"[SlowPath] search_product returned invalid pcode: {pcode}")
                    raise ProductNotFoundException(f"No product found for query: {query}")
                
                logger.debug(f"[SlowPath] Found product: pcode={pcode}")

            except AsyncTimeoutError as e:
                logger.error(f"[SlowPath] Search step timeout")
                raise
            except ProductNotFoundException:
                raise
            except Exception as e:
                logger.error(f"[SlowPath] Search step failed: {type(e).__name__}: {e}")
                raise ProductNotFoundException(f"Search failed for query: {query}") from e

            # 2단계: 가격 정보 가져오기
            try:
                product_url_base = f"https://prod.danawa.com/info/?pcode={pcode}"
                
                # 타임아웃 계산: 전체 타임아웃의 60%를 상세 페이지에 할당
                detail_timeout = timeout * 0.6
                
                price_data: Optional[Dict[str, Any]] = await get_product_lowest_price(
                    page=page,
                    product_url_base=product_url_base,
                    product_code=pcode,
                    search_query=normalized_query,
                    timeout_s=detail_timeout,
                )

                if not price_data or not isinstance(price_data, dict):
                    logger.warning(f"[SlowPath] get_product_lowest_price returned invalid data: {price_data}")
                    raise ProductNotFoundException(f"No price found for pcode: {pcode}")

                # Safe 딕셔너리 접근 및 검증
                price = EdgeCaseHandler.safe_get(price_data, "lowest_price")
                if price is None:
                    logger.warning(f"[SlowPath] Missing 'lowest_price' in price_data")
                    raise ProductNotFoundException(f"No price data for pcode: {pcode}")
                
                # Price validation with safe conversion
                try:
                    price_int = EdgeCaseHandler.safe_int(
                        price,
                        min_val=1,
                        max_val=10**9
                    )
                    if price_int <= 0:
                        logger.warning(f"[SlowPath] Invalid price value: {price}")
                        raise ValueError(f"Invalid price value: {price}")
                except (TypeError, ValueError) as e:
                    logger.error(f"[SlowPath] Price is not a valid integer: {price}, error={e}")
                    raise ValueError(f"Invalid price format: {price}") from e

                logger.debug(
                    f"[SlowPath] Success: pcode={pcode}, price={price_int}"
                )

                return CrawlResult(
                    product_url=product_url_base,
                    price=price_int,
                    product_name=price_data.get("product_name"),
                    metadata={
                        "method": "slowpath",
                        "timeout": timeout,
                        "pcode": pcode,
                    },
                )

            except AsyncTimeoutError as e:
                logger.error(f"[SlowPath] Detail step timeout")
                raise
            except ProductNotFoundException:
                raise
            except Exception as e:
                logger.error(f"[SlowPath] Detail step failed: {type(e).__name__}: {e}")
                raise ProductNotFoundException(f"Failed to get price for pcode: {pcode}") from e

        except AsyncTimeoutError:
            raise
        except ProductNotFoundException:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"[SlowPath] Unexpected error: {type(e).__name__}: {e}", exc_info=True)
            raise
        finally:
            # 페이지 정리
            if page is not None:
                try:
                    await page.close()
                except Exception as e:
                    logger.warning(f"[SlowPath] Failed to close page: {type(e).__name__}: {e}")

    @classmethod
    def from_crawler(cls, crawler: Any) -> "SlowPathExecutor":
        """DanawaCrawler 인스턴스에서 생성

        Args:
            crawler: DanawaCrawler 인스턴스

        Returns:
            SlowPathExecutor: SlowPath 실행자
            
        Raises:
            ValueError: crawler가 None인 경우
        """
        if crawler is None:
            raise ValueError("crawler must not be None")
        
        return cls(crawler=crawler)

    async def close(self) -> None:
        """브라우저 리소스 정리"""
        try:
            if self._browser_manager:
                await self._browser_manager.close()
        except Exception as e:
            logger.warning(f"[SlowPath] Failed to close browser manager: {type(e).__name__}: {e}")
