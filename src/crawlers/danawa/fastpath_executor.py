"""FastPath Executor - HTTP-based fast search execution

Wraps the existing boundary/ (HTTP FastPath) logic into the SearchExecutor interface.
"""

from typing import Optional

from src.core.logging import logger
from src.utils.text_utils import build_cache_key, normalize_for_search_query

from .executor import SearchExecutor
from .result import CrawlResult


class FastPathExecutor(SearchExecutor):
    """HTTP 기반 빠른 경로 실행자

    기존 boundary/ 로직을 SearchExecutor 인터페이스로 래핑합니다.

    특징:
    - HTTP 기반 (빠름, 비용 낮음)
    - 단순한 HTML 파싱
    - 타임아웃 3초 권장

    Usage:
        executor = FastPathExecutor()
        result = await executor.execute("삼성 갤럭시 S24", timeout=3.0)
    """

    def __init__(self, crawler=None):
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
            TimeoutError: 타임아웃
            FastPathNoResults: 검색 결과 없음
            FastPathProductFetchFailed: 상품 가져오기 실패
        """
        from src.crawlers.danawa.boundary import http_fastpath_search

        logger.debug(f"[FastPath] Executing: query='{query}', timeout={timeout:.2f}s")

        # 쿼리 정규화
        normalized_query = normalize_for_search_query(query)
        cache_key = build_cache_key(normalized_query)

        # HTTP FastPath 실행
        result = await http_fastpath_search(
            search_query=cache_key,
            timeout_ms=int(timeout * 1000),
        )

        logger.debug(
            f"[FastPath] Success: url={result['product_url']}, price={result['price']}"
        )

        return CrawlResult(
            product_url=result["product_url"],
            price=result["price"],
            product_name=result.get("product_name"),
            metadata={"method": "fastpath", "timeout": timeout},
        )

    @classmethod
    def from_crawler(cls, crawler) -> "FastPathExecutor":
        """DanawaCrawler 인스턴스에서 생성

        Args:
            crawler: DanawaCrawler 인스턴스

        Returns:
            FastPathExecutor: FastPath 실행자
        """
        return cls(crawler=crawler)
