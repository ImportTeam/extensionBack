"""SlowPath Executor - Playwright-based slow search execution

Wraps the existing playwright/ logic into the SearchExecutor interface.
"""

from typing import Optional

from src.core.logging import logger
from src.utils.text_utils import build_cache_key, normalize_for_search_query

from .executor import SearchExecutor
from .result import CrawlResult


class SlowPathExecutor(SearchExecutor):
    """Playwright 기반 느린 경로 실행자

    기존 playwright/ 로직을 SearchExecutor 인터페이스로 래핑합니다.

    특징:
    - Playwright 브라우저 렌더링 (느림, 비용 높음)
    - JavaScript 실행 지원
    - 복잡한 페이지 처리 가능
    - 타임아웃 9초 권장

    Usage:
        executor = SlowPathExecutor()
        result = await executor.execute("삼성 갤럭시 S24", timeout=9.0)
    """

    def __init__(self, crawler=None):
        """
        Args:
            crawler: DanawaCrawler 인스턴스 (선택, 없으면 내부 생성)
        """
        self.crawler = crawler
        self._browser_manager = None

    async def execute(self, query: str, timeout: float) -> CrawlResult:
        """Playwright SlowPath 실행

        Args:
            query: 검색어
            timeout: 타임아웃 (초)

        Returns:
            CrawlResult: 크롤링 결과

        Raises:
            TimeoutError: 타임아웃
            ProductNotFoundException: 상품을 찾을 수 없음
            CrawlerException: 크롤링 실패
        """
        from src.crawlers.playwright.search import search_product
        from src.crawlers.playwright.detail import get_product_lowest_price

        logger.debug(f"[SlowPath] Executing: query='{query}', timeout={timeout:.2f}s")

        # 쿼리 정규화
        normalized_query = normalize_for_search_query(query)
        cache_key = build_cache_key(normalized_query)

        # Playwright 검색 실행
        # 타임아웃을 밀리초로 변환
        timeout_ms = int(timeout * 1000)

        # 1단계: 상품 검색
        search_result = await search_product(
            query=cache_key,
            timeout_ms=timeout_ms // 2,  # 검색에 절반 할당
        )

        if not search_result or not search_result.get("product_url"):
            from src.core.exceptions import ProductNotFoundException

            raise ProductNotFoundException(f"No product found for query: {query}")

        product_url = search_result["product_url"]

        # 2단계: 가격 정보 가져오기
        price_result = await get_product_lowest_price(
            product_url=product_url,
            timeout_ms=timeout_ms // 2,  # 가격 조회에 절반 할당
        )

        logger.debug(
            f"[SlowPath] Success: url={product_url}, price={price_result['price']}"
        )

        return CrawlResult(
            product_url=product_url,
            price=price_result["price"],
            product_name=search_result.get("product_name"),
            metadata={"method": "slowpath", "timeout": timeout},
        )

    @classmethod
    def from_crawler(cls, crawler) -> "SlowPathExecutor":
        """DanawaCrawler 인스턴스에서 생성

        Args:
            crawler: DanawaCrawler 인스턴스

        Returns:
            SlowPathExecutor: SlowPath 실행자
        """
        return cls(crawler=crawler)

    async def close(self):
        """브라우저 리소스 정리"""
        if self._browser_manager:
            await self._browser_manager.close()
