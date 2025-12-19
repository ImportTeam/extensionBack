"""FastPath Executor - Enhanced Type Safety & Exception Handling"""

from typing import Optional, List, Dict, Any
from asyncio import TimeoutError as AsyncTimeoutError

from src.core.logging import logger
from src.core.exceptions import ProductNotFoundException
from src.utils.text_utils import build_cache_key, normalize_for_search_query
from src.utils.edge_cases import EdgeCaseHandler

from .executor import SearchExecutor
from .result import CrawlResult


class FastPathExecutor(SearchExecutor):
    """HTTP 기반 빠른 경로 실행자 (타입 안전 버전)

    기존 boundary/ 로직을 SearchExecutor 인터페이스로 래핑합니다.

    특징:
    - HTTP 기반 (빠름, 비용 낮음)
    - 단순한 HTML 파싱
    - 타임아웃 3초 권장
    - 완전한 타입 힌트 및 예외 처리
    """

    def __init__(self, crawler: Optional[Any] = None):
        """
        Args:
            crawler: DanawaCrawler 인스턴스 (선택, 없으면 내부 생성)
        """
        self.crawler = crawler

    async def execute(self, query: str, timeout: float) -> CrawlResult:
        """HTTP FastPath 실행

        Args:
            query: 검색어
            timeout: 타임아웃 (초)

        Returns:
            CrawlResult: 크롤링 결과

        Raises:
            AsyncTimeoutError: 타임아웃
            ProductNotFoundException: 검색 결과 없음
            ValueError: 쿼리 또는 타임아웃이 유효하지 않음
            Exception: 기타 크롤링 오류
        """
        try:
            # Input validation
            if not query or not isinstance(query, str):
                raise ValueError(f"Invalid query: {query}")
            
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise ValueError(f"Invalid timeout: {timeout}")
            
            logger.debug(f"[FastPath] Executing: query='{query}', timeout={timeout:.2f}s")

            # 쿼리 정규화
            normalized_query = normalize_for_search_query(query)
            
            if not normalized_query:
                logger.warning(f"[FastPath] Normalized query is empty for: {query}")
                raise ValueError(f"Normalized query is empty for: {query}")

            # 검색 후보 생성
            try:
                from src.utils.search.search_optimizer import DanawaSearchHelper
                helper = DanawaSearchHelper()
                candidates: List[str] = helper.generate_search_candidates(normalized_query)
                
                if not candidates:
                    logger.warning(f"[FastPath] No search candidates generated for: {normalized_query}")
                    raise ProductNotFoundException(f"No search candidates for: {query}")
            except Exception as e:
                logger.error(f"[FastPath] Failed to generate search candidates: {type(e).__name__}: {e}")
                raise

            # HTTP FastPath 실행
            try:
                from src.crawlers.boundary import DanawaHttpFastPath
                fastpath = DanawaHttpFastPath()
                
                result = await fastpath.search_lowest_price(
                    query=normalized_query,
                    candidates=candidates,
                    total_timeout_ms=int(timeout * 1000),
                )

                if not result:
                    logger.warning(f"[FastPath] search_lowest_price returned None for: {query}")
                    raise ProductNotFoundException(f"No results from FastPath for: {query}")
                
                # Result validation
                if not isinstance(result, dict):
                    logger.error(f"[FastPath] search_lowest_price returned invalid type: {type(result)}")
                    raise ValueError(f"Invalid result type from FastPath: {type(result)}")
                
                # Safe 딕셔너리 접근
                product_url = EdgeCaseHandler.safe_get(result, "product_url")
                price = EdgeCaseHandler.safe_get(result, "price")
                product_name = EdgeCaseHandler.safe_get(result, "product_name")
                
                if not product_url:
                    logger.error(f"[FastPath] Missing product_url in result")
                    raise ValueError("Missing or invalid product_url in result")
                
                if price is None:
                    logger.error(f"[FastPath] Missing price in result")
                    raise ValueError("Missing price in result")
                
                # Price validation with safe conversion
                try:
                    price_int = EdgeCaseHandler.safe_int(
                        price, 
                        min_val=1,  # 가격은 1 이상
                        max_val=10**9  # 합리적인 최대값
                    )
                    if price_int <= 0:
                        logger.warning(f"[FastPath] Invalid price value: {price}")
                        raise ValueError(f"Invalid price value: {price}")
                except (TypeError, ValueError) as e:
                    logger.error(f"[FastPath] Price conversion failed: {price}, error={e}")
                    raise ValueError(f"Invalid price format: {price}") from e

                logger.debug(
                    f"[FastPath] Success: url={product_url}, price={price_int}"
                )

                return CrawlResult(
                    product_url=product_url,
                    price=price_int,
                    product_name=EdgeCaseHandler.safe_str(product_name),
                    metadata={"method": "fastpath", "timeout": timeout},
                )
            
            except AsyncTimeoutError as e:
                logger.warning(f"[FastPath] Timeout during search: {e}")
                raise
            except ProductNotFoundException:
                raise
            except Exception as e:
                logger.error(f"[FastPath] Search execution failed: {type(e).__name__}: {e}")
                raise

        except AsyncTimeoutError:
            raise
        except ProductNotFoundException:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"[FastPath] Unexpected error: {type(e).__name__}: {e}", exc_info=True)
            raise

    @classmethod
    def from_crawler(cls, crawler: Any) -> "FastPathExecutor":
        """DanawaCrawler 인스턴스에서 생성

        Args:
            crawler: DanawaCrawler 인스턴스

        Returns:
            FastPathExecutor: FastPath 실행자
            
        Raises:
            ValueError: crawler가 None인 경우
        """
        if crawler is None:
            raise ValueError("crawler must not be None")
        
        return cls(crawler=crawler)
