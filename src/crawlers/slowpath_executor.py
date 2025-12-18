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
        from src.crawlers.playwright import ensure_shared_browser, new_page

        logger.debug(f"[SlowPath] Executing: query='{query}', timeout={timeout:.2f}s")

        # 쿼리 정규화
        normalized_query = normalize_for_search_query(query)

        # Playwright 실행
        browser = await ensure_shared_browser()
        page = await new_page()

        try:
            # 1단계: 상품 검색 (pcode 추출)
            search_url_base = "https://search.danawa.com/dsearch.php"
            pcode = await search_product(
                create_page=lambda: new_page(),
                search_url_base=search_url_base,
                search_query=normalized_query,
                overall_timeout_s=timeout / 2,
            )

            if not pcode:
                from src.core.exceptions import ProductNotFoundException
                raise ProductNotFoundException(f"No product found for query: {query}")

            # 2단계: 가격 정보 가져오기
            product_url_base = f"https://prod.danawa.com/info/?pcode={pcode}"
            price_data = await get_product_lowest_price(
                page=page,
                product_url_base=product_url_base,
                product_code=pcode,
                search_query=normalized_query,
            )

            if not price_data:
                from src.core.exceptions import ProductNotFoundException
                raise ProductNotFoundException(f"No price found for pcode: {pcode}")

            logger.debug(
                f"[SlowPath] Success: pcode={pcode}, price={price_data.get('lowest_price')}"
            )

            return CrawlResult(
                product_url=product_url_base,
                price=price_data["lowest_price"],
                product_name=price_data.get("product_name"),
                metadata={"method": "slowpath", "timeout": timeout, "pcode": pcode},
            )
        finally:
            await page.close()

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
