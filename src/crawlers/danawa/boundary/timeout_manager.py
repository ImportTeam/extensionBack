"""Timeout and budget management for Danawa crawler.

크롤링 전체 예산(total_timeout_ms)을 HTTP Fast Path와 Playwright 폴백에
효율적으로 배분하고 관리합니다.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class TimeoutBudget:
    """크롤링 타임아웃 예산 계산기.

    - 전체 예산: total_ms
    - HTTP 예산: 전체의 65% (default)
    - Playwright: 나머지
    """

    total_ms: int  # 전체 예산 (ms)
    http_budget_percent: float = 0.65  # HTTP Fast Path가 사용할 비율

    @property
    def http_budget_ms(self) -> int:
        """HTTP Fast Path에 할당된 예산 (ms)."""
        return max(500, int(self.total_ms * self.http_budget_percent))

    @property
    def playwright_budget_ms(self) -> int:
        """Playwright에 할당된 예산 (ms)."""
        return max(500, self.total_ms - self.http_budget_ms)

    @property
    def http_budget_s(self) -> float:
        """HTTP Fast Path에 할당된 예산 (초)."""
        return max(0.2, self.http_budget_ms / 1000.0)

    @property
    def playwright_budget_s(self) -> float:
        """Playwright에 할당된 예산 (초)."""
        return max(0.2, self.playwright_budget_ms / 1000.0)


class TimeoutManager:
    """크롤링 진행 중 타임아웃 추적 및 관리.

    - 시작 시간 기록
    - 경과 시간 계산
    - 남은 예산 계산
    """

    def __init__(self, total_timeout_ms: int) -> None:
        """초기화.

        Args:
            total_timeout_ms: 전체 크롤링 타임아웃 (ms)
        """
        self.total_timeout_ms = total_timeout_ms
        self.budget = TimeoutBudget(total_timeout_ms)

        loop = asyncio.get_running_loop()
        self._start_time = loop.time()

    @property
    def elapsed_ms(self) -> int:
        """경과 시간 (ms)."""
        loop = asyncio.get_running_loop()
        return int((loop.time() - self._start_time) * 1000)

    @property
    def elapsed_s(self) -> float:
        """경과 시간 (초)."""
        return self.elapsed_ms / 1000.0

    @property
    def remaining_ms(self) -> int:
        """남은 예산 (ms)."""
        return max(0, self.total_timeout_ms - self.elapsed_ms)

    @property
    def remaining_s(self) -> float:
        """남은 예산 (초)."""
        return max(0.0, self.remaining_ms / 1000.0)

    def is_exhausted(self) -> bool:
        """예산이 소진되었는가?"""
        return self.remaining_ms <= 0

    def has_minimum_for_playwright(self, min_required_ms: int = 1000) -> bool:
        """Playwright 실행에 최소 필요한 시간이 남아있는가?"""
        return self.remaining_ms >= min_required_ms

    def has_minimum_for_playwright_search(self, min_required_ms: int = 1200) -> bool:
        """Playwright 검색 단계에 최소 필요한 시간이 남아있는가?"""
        return self.remaining_ms >= min_required_ms

    def has_minimum_for_playwright_detail(self, min_required_ms: int = 1000) -> bool:
        """Playwright 상세 조회에 최소 필요한 시간이 남아있는가?"""
        return self.remaining_ms >= min_required_ms

    def get_playwright_search_timeout(self, max_timeout_s: float = 5.0) -> float:
        """Playwright 검색에 사용할 타임아웃 (초).

        - 최대 max_timeout_s
        - 남은 예산 * 65% (검색 단계가 느릴 때가 많아 조금 더 배정)
        """
        allocated = max(1.5, self.remaining_s * 0.65)
        return min(max_timeout_s, allocated)

    def get_playwright_detail_timeout(self, max_timeout_s: float = 6.0) -> float:
        """Playwright 상세 조회에 사용할 타임아웃 (초).

        - 최대 max_timeout_s
        - 남은 예산 - 여유 (최소 1.0초)
        """
        return min(max_timeout_s, max(1.0, self.remaining_s - 0.2))

    def __repr__(self) -> str:
        return (
            f"TimeoutManager(total={self.total_timeout_ms}ms, "
            f"elapsed={self.elapsed_ms}ms, "
            f"remaining={self.remaining_ms}ms, "
            f"budget={self.budget})"
        )
