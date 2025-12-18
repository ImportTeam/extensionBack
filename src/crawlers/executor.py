"""Executor Protocol - Interface for FastPath/SlowPath executors

Defines the common interface that all executors must implement.
"""

from typing import Protocol

from .result import CrawlResult


class SearchExecutor(Protocol):
    """검색 실행자 프로토콜

    FastPath/SlowPath Executor가 구현해야 할 인터페이스입니다.

    구현 예시:
        class FastPathExecutor(SearchExecutor):
            async def execute(self, query: str, timeout: float) -> CrawlResult:
                # HTTP 기반 검색 로직
                ...
    """

    async def execute(self, query: str, timeout: float) -> CrawlResult:
        """검색 실행

        Args:
            query: 검색어 (정규화된 쿼리)
            timeout: 타임아웃 (초)

        Returns:
            CrawlResult: 크롤링 결과

        Raises:
            TimeoutError: 타임아웃 발생
            ParsingError: 파싱 오류
            BlockedError: 차단 감지
            ProductNotFoundException: 상품을 찾을 수 없음
        """
        ...
