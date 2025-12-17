"""Circuit Breaker + Metrics tracking for HTTP Fast Path."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from src.core.logging import logger


@dataclass
class CircuitBreakerMetrics:
    """HTTP Fast Path 메트릭 추적."""

    fastpath_hits: int = 0
    fastpath_misses: int = 0
    playwright_hits: int = 0
    playwright_failures: int = 0

    def record_fastpath_hit(self) -> None:
        self.fastpath_hits += 1

    def record_fastpath_miss(self) -> None:
        self.fastpath_misses += 1

    def record_playwright_hit(self) -> None:
        self.playwright_hits += 1

    def record_playwright_failure(self) -> None:
        self.playwright_failures += 1

    @property
    def fastpath_success_rate(self) -> float:
        """HTTP Fast Path 성공률 (0.0~1.0)."""
        total = self.fastpath_hits + self.fastpath_misses
        return self.fastpath_hits / total if total > 0 else 0.0

    @property
    def playwright_success_rate(self) -> float:
        """Playwright 성공률 (0.0~1.0)."""
        total = self.playwright_hits + self.playwright_failures
        return self.playwright_hits / total if total > 0 else 0.0

    def __repr__(self) -> str:
        return (
            f"Metrics(fastpath: {self.fastpath_hits}H/{self.fastpath_misses}M={self.fastpath_success_rate:.1%}, "
            f"playwright: {self.playwright_hits}H/{self.playwright_failures}F={self.playwright_success_rate:.1%})"
        )


class CircuitBreaker:
    """HTTP Fast Path Circuit Breaker (fail-open/fail-close).

    - 연속 실패 시 회로 개방 (일시적 차단)
    - 개방 후 일정 시간 후 자동 복구
    - 성공 시 즉시 회로 닫기 (복구)
    """

    def __init__(
        self,
        fail_threshold: int = 5,
        open_duration_sec: float = 60.0,
    ) -> None:
        """초기화.

        Args:
            fail_threshold: 회로 개방 임계값 (연속 실패 횟수)
            open_duration_sec: 개방 상태 유지 시간 (초)
        """
        self.fail_threshold = fail_threshold
        self.open_duration_sec = open_duration_sec

        self._fail_count = 0
        self._open_until: float = 0.0
        self.metrics = CircuitBreakerMetrics()

    def record_success(self) -> None:
        """성공 기록 → 회로 닫기."""
        self._fail_count = 0
        self._open_until = 0.0
        self.metrics.record_fastpath_hit()

    def record_failure(self) -> None:
        """실패 기록 → 임계값 도달 시 회로 개방."""
        self._fail_count += 1
        self.metrics.record_fastpath_miss()

        if self._fail_count >= self.fail_threshold:
            loop = asyncio.get_running_loop()
            self._open_until = loop.time() + self.open_duration_sec
            logger.warning(
                f"[CIRCUIT_BREAKER] OPEN (fail_count={self._fail_count} >= {self.fail_threshold}). "
                f"HTTP Fast Path blocked for {self.open_duration_sec}s"
            )

    def is_open(self) -> bool:
        """회로가 개방되었는가?"""
        if self._open_until <= 0.0:
            return False

        loop = asyncio.get_running_loop()
        if loop.time() >= self._open_until:
            # 자동 복구
            self._fail_count = 0
            self._open_until = 0.0
            logger.info("[CIRCUIT_BREAKER] CLOSED (auto-recovery)")
            return False

        return True

    def get_remaining_open_time(self) -> float:
        """회로 개방 남은 시간 (초)."""
        if self._open_until <= 0.0:
            return 0.0

        loop = asyncio.get_running_loop()
        remaining = self._open_until - loop.time()
        return max(0.0, remaining)

    def __repr__(self) -> str:
        status = "OPEN" if self.is_open() else "CLOSED"
        open_time = self.get_remaining_open_time()
        return f"CircuitBreaker({status}, fail_count={self._fail_count}/{self.fail_threshold}, open_time={open_time:.1f}s)"
