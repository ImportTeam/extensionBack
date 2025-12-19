"""Execution Strategy - Fast/Slow Path Decision Logic

Determines execution paths and retry strategies based on error types.
"""

from enum import Enum
from typing import Protocol


class ExecutionPath(str, Enum):
    """실행 경로

    검색 실행 시 사용 가능한 경로들을 정의합니다.
    """

    CACHE = "cache"
    FASTPATH = "fastpath"
    SLOWPATH = "slowpath"


class SearchExecutor(Protocol):
    """검색 실행자 인터페이스

    FastPath/SlowPath Executor가 구현해야 할 프로토콜입니다.
    """

    async def execute(self, query: str, timeout: float):
        """검색 실행

        Args:
            query: 검색어
            timeout: 타임아웃 (초)

        Returns:
            실행 결과 (구현체에 따라 다름)

        Raises:
            TimeoutError: 타임아웃 발생
            ParsingError: 파싱 오류
            BlockedError: 차단 감지
        """
        ...


class ExecutionStrategy:
    """실행 전략 결정

    에러 유형에 따라 Fallback 및 재시도 전략을 결정합니다.

    Usage:
        strategy = ExecutionStrategy()

        try:
            result = await fastpath.execute(query, timeout=3.0)
        except Exception as e:
            if strategy.should_fallback_to_slowpath(e):
                result = await slowpath.execute(query, timeout=9.0)
    """

    @staticmethod
    def should_fallback_to_slowpath(error: Exception) -> bool:
        """SlowPath로 Fallback 여부 결정

        다음 오류 유형에서 SlowPath로 전환:
        - TimeoutError: FastPath 타임아웃
        - ParsingError: HTML 구조 변경
        - BlockedError: 봇 차단 감지

        Args:
            error: 발생한 예외

        Returns:
            bool: SlowPath로 전환해야 하는지 여부
        """
        # NOTE:
        # 현재 코드베이스는 예외 계층이 두 군데에 존재합니다.
        # - src.engine.exceptions: 엔진 전용 예외
        # - src.core.exceptions: 실행자(FastPath/SlowPath)에서 실제로 많이 사용하는 예외
        # 폴백/재시도 로직이 둘 중 어느 쪽 예외를 받더라도 정상 동작해야 합니다.

        from src.engine.exceptions import (
            BlockedError,
            ParsingError,
            TimeoutError,
            ProductNotFoundException as EngineProductNotFound,
        )
        from src.core.exceptions import (
            BlockedException,
            ParsingException,
            TimeoutException,
            NetworkTimeoutException,
            ProductNotFoundException as CoreProductNotFound,
        )

        return isinstance(
            error,
            (
                TimeoutError,
                ParsingError,
                BlockedError,
                EngineProductNotFound,
                TimeoutException,
                NetworkTimeoutException,
                ParsingException,
                BlockedException,
                CoreProductNotFound,
            ),
        )

    @staticmethod
    def get_retry_count(error: Exception) -> int:
        """재시도 횟수 결정

        오류 유형에 따라 재시도 횟수를 결정:
        - TimeoutError: 1회 (타임아웃은 빠르게 포기)
        - ParsingError: 0회 (파싱 오류는 재시도 무의미)
        - BlockedError: 2회 (차단은 여러 번 시도)
        - 기타: 0회

        Args:
            error: 발생한 예외

        Returns:
            int: 재시도 횟수
        """
        from src.engine.exceptions import (
            BlockedError,
            ParsingError,
            TimeoutError,
            ProductNotFoundException as EngineProductNotFound,
        )
        from src.core.exceptions import (
            BlockedException,
            ParsingException,
            TimeoutException,
            NetworkTimeoutException,
            ProductNotFoundException as CoreProductNotFound,
        )

        if isinstance(error, (TimeoutError, TimeoutException, NetworkTimeoutException)):
            return 1
        if isinstance(error, (EngineProductNotFound, CoreProductNotFound)):
            return 0
        if isinstance(error, (ParsingError, ParsingException)):
            return 0
        if isinstance(error, (BlockedError, BlockedException)):
            return 2
        return 0

    @staticmethod
    def should_skip_fastpath(error_history: list[Exception]) -> bool:
        """FastPath 스킵 여부 결정

        최근 오류 히스토리를 기반으로 FastPath를 건너뛸지 결정합니다.
        예: 최근 3번 연속 차단된 경우 FastPath 스킵

        Args:
            error_history: 최근 오류 히스토리 (최대 10개)

        Returns:
            bool: FastPath를 건너뛸지 여부
        """
        if not error_history:
            return False

        from src.engine.exceptions import BlockedError
        from src.core.exceptions import BlockedException

        # 최근 3번 연속 차단인 경우 FastPath 스킵
        recent_errors = error_history[-3:]
        if len(recent_errors) == 3 and all(
            isinstance(e, (BlockedError, BlockedException)) for e in recent_errors
        ):
            return True

        return False
