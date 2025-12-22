"""Search Result - Standardized Result Format

Provides a standardized format for search results across all execution paths.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SearchStatus(str, Enum):
    """검색 상태

    검색 결과의 상태를 나타냅니다.
    """

    SUCCESS = "success"  # 일반 성공 (deprecated, 구체적인 상태 사용 권장)
    CACHE_HIT = "cache_hit"  # 캐시 히트
    FASTPATH_SUCCESS = "fastpath_success"  # FastPath 성공
    SLOWPATH_SUCCESS = "slowpath_success"  # SlowPath 성공
    TIMEOUT = "timeout"  # 타임아웃
    PARSE_ERROR = "parse_error"  # 파싱 오류
    BLOCKED = "blocked"  # 차단 (봇 감지 등)
    NO_RESULTS = "no_results"  # 결과 없음
    BUDGET_EXHAUSTED = "budget_exhausted"  # 예산 소진


@dataclass
class SearchResult:
    """검색 결과 표준 포맷

    모든 검색 경로(Cache/FastPath/SlowPath)에서 사용하는 통일된 결과 형식입니다.

    Attributes:
        status: 검색 상태
        product_url: 상품 URL
        price: 가격
        query: 검색어
        source: 결과 출처 ("cache" | "fastpath" | "slowpath")
        elapsed_ms: 소요 시간 (밀리초)
        error_message: 오류 메시지
        budget_report: 예산 사용 리포트
    """

    status: SearchStatus
    product_url: Optional[str] = None
    price: Optional[int] = None

    # 메타데이터
    query: Optional[str] = None
    source: Optional[str] = None  # "cache" | "fastpath" | "slowpath"
    elapsed_ms: Optional[float] = None
    
    # 상품 식별자 (pcode 등)
    product_id: Optional[str] = None  # 다나와 pcode or unique ID
    
    # TOP 3 가격 리스트
    top_prices: Optional[list[dict]] = None  # [{"rank": 1, "mall": "...", "price": 123, "link": "..."}]
    
    # 가격 추세 데이터
    price_trend: Optional[dict] = None  # {"product_id": "pcode", "min": 123, "max": 456, "trend": [...]}

    # 디버깅 정보
    error_message: Optional[str] = None
    budget_report: Optional[dict] = None

    @property
    def is_success(self) -> bool:
        """성공 여부 반환"""
        return self.status in [
            SearchStatus.CACHE_HIT,
            SearchStatus.FASTPATH_SUCCESS,
            SearchStatus.SLOWPATH_SUCCESS,
        ]

    @property
    def is_error(self) -> bool:
        """오류 여부 반환"""
        return self.status in [
            SearchStatus.TIMEOUT,
            SearchStatus.PARSE_ERROR,
            SearchStatus.BLOCKED,
            SearchStatus.NO_RESULTS,
            SearchStatus.BUDGET_EXHAUSTED,
        ]

    @classmethod
    def from_cache(
        cls, product_url: str, price: int, query: str, elapsed_ms: float,
        product_id: Optional[str] = None, top_prices: Optional[list[dict]] = None,
        price_trend: Optional[dict] = None
    ) -> "SearchResult":
        """캐시에서 반환된 결과 생성

        Args:
            product_url: 상품 URL
            price: 가격
            query: 검색어
            elapsed_ms: 소요 시간 (밀리초)
            product_id: 상품 ID (pcode)
            top_prices: TOP 3 가격 리스트
            price_trend: 가격 추세 데이터

        Returns:
            SearchResult: 캐시 히트 결과
        """
        return cls(
            status=SearchStatus.CACHE_HIT,
            product_url=product_url,
            price=price,
            query=query,
            source="cache",
            elapsed_ms=elapsed_ms,
            product_id=product_id,
            top_prices=top_prices,
            price_trend=price_trend,
        )

    @classmethod
    def from_fastpath(
        cls, product_url: str, price: int, query: str, elapsed_ms: float,
        product_id: Optional[str] = None, top_prices: Optional[list[dict]] = None,
        price_trend: Optional[dict] = None
    ) -> "SearchResult":
        """FastPath에서 반환된 결과 생성

        Args:
            product_url: 상품 URL
            price: 가격
            query: 검색어
            elapsed_ms: 소요 시간 (밀리초)
            product_id: 상품 ID (pcode)
            top_prices: TOP 3 가격 리스트
            price_trend: 가격 추세 데이터

        Returns:
            SearchResult: FastPath 성공 결과
        """
        return cls(
            status=SearchStatus.FASTPATH_SUCCESS,
            product_url=product_url,
            price=price,
            query=query,
            source="fastpath",
            elapsed_ms=elapsed_ms,
            product_id=product_id,
            top_prices=top_prices,
            price_trend=price_trend,
        )

    @classmethod
    def from_slowpath(
        cls, product_url: str, price: int, query: str, elapsed_ms: float,
        product_id: Optional[str] = None, top_prices: Optional[list[dict]] = None,
        price_trend: Optional[dict] = None
    ) -> "SearchResult":
        """SlowPath에서 반환된 결과 생성

        Args:
            product_url: 상품 URL
            price: 가격
            query: 검색어
            elapsed_ms: 소요 시간 (밀리초)
            product_id: 상품 ID (pcode)
            top_prices: TOP 3 가격 리스트
            price_trend: 가격 추세 데이터

        Returns:
            SearchResult: SlowPath 성공 결과
        """
        return cls(
            status=SearchStatus.SLOWPATH_SUCCESS,
            product_url=product_url,
            price=price,
            query=query,
            source="slowpath",
            elapsed_ms=elapsed_ms,
            product_id=product_id,
            top_prices=top_prices,
            price_trend=price_trend,
        )

    @classmethod
    def timeout(
        cls, query: str, elapsed_ms: float, budget_report: dict
    ) -> "SearchResult":
        """타임아웃 결과 생성

        Args:
            query: 검색어
            elapsed_ms: 소요 시간 (밀리초)
            budget_report: 예산 사용 리포트

        Returns:
            SearchResult: 타임아웃 결과
        """
        return cls(
            status=SearchStatus.TIMEOUT,
            query=query,
            elapsed_ms=elapsed_ms,
            budget_report=budget_report,
            error_message="Search timeout exceeded",
        )

    @classmethod
    def parse_error(
        cls, query: str, elapsed_ms: float, error: str
    ) -> "SearchResult":
        """파싱 오류 결과 생성

        Args:
            query: 검색어
            elapsed_ms: 소요 시간 (밀리초)
            error: 오류 메시지

        Returns:
            SearchResult: 파싱 오류 결과
        """
        return cls(
            status=SearchStatus.PARSE_ERROR,
            query=query,
            elapsed_ms=elapsed_ms,
            error_message=error,
        )

    @classmethod
    def blocked(cls, query: str, elapsed_ms: float) -> "SearchResult":
        """차단 결과 생성

        Args:
            query: 검색어
            elapsed_ms: 소요 시간 (밀리초)

        Returns:
            SearchResult: 차단 결과
        """
        return cls(
            status=SearchStatus.BLOCKED,
            query=query,
            elapsed_ms=elapsed_ms,
            error_message="Request blocked (bot detection)",
        )

    @classmethod
    def no_results(cls, query: str, elapsed_ms: float) -> "SearchResult":
        """결과 없음 생성

        Args:
            query: 검색어
            elapsed_ms: 소요 시간 (밀리초)

        Returns:
            SearchResult: 결과 없음
        """
        return cls(
            status=SearchStatus.NO_RESULTS,
            query=query,
            elapsed_ms=elapsed_ms,
            error_message="No products found",
        )

    @classmethod
    def budget_exhausted(
        cls, query: str, elapsed_ms: float, budget_report: dict
    ) -> "SearchResult":
        """예산 소진 결과 생성

        Args:
            query: 검색어
            elapsed_ms: 소요 시간 (밀리초)
            budget_report: 예산 사용 리포트

        Returns:
            SearchResult: 예산 소진 결과
        """
        return cls(
            status=SearchStatus.BUDGET_EXHAUSTED,
            query=query,
            elapsed_ms=elapsed_ms,
            budget_report=budget_report,
            error_message="Budget exhausted before completion",
        )
