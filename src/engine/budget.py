"""Budget Manager - Time and Resource Budget Management

Manages the 12-second budget allocation across different execution stages:
- Cache lookup: 200ms
- FastPath (HTTP): 3s
- SlowPath (Playwright): 9s
"""

from dataclasses import dataclass
from time import time
from typing import Optional


@dataclass
class BudgetConfig:
    """예산 설정"""

    total_budget: float = 12.0  # 전체 예산 (초)
    cache_timeout: float = 0.2  # Cache 조회 최대 시간 (초)
    fastpath_timeout: float = 3.0  # FastPath 최대 시간 (초)
    slowpath_timeout: float = 9.0  # SlowPath 최대 시간 (초)
    min_remaining: float = 1.0  # 실행 최소 여유 시간 (초)


class BudgetManager:
    """시간/리소스 예산 관리자

    12초 예산을 관리하고 각 단계별 타임아웃을 제공합니다.
    실시간으로 경과 시간을 추적하고 남은 예산을 계산합니다.

    Usage:
        manager = BudgetManager()
        manager.start()

        # 단계별 타임아웃 가져오기
        cache_timeout = manager.get_timeout_for("cache")

        # 체크포인트 기록
        manager.checkpoint("cache_miss")

        # 예산 체크
        if manager.can_execute_fastpath():
            # FastPath 실행
            pass

        # 리포트 생성
        report = manager.get_report()
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()
        self.start_time: Optional[float] = None
        self._checkpoints: dict[str, float] = {}

    def start(self) -> None:
        """예산 측정 시작"""
        self.start_time = time()
        self._checkpoints.clear()

    def checkpoint(self, name: str) -> None:
        """체크포인트 기록

        Args:
            name: 체크포인트 이름 (예: "cache_hit", "fastpath_success")

        Raises:
            RuntimeError: start()가 호출되지 않은 경우
        """
        if self.start_time is None:
            raise RuntimeError("Budget not started. Call start() first.")
        self._checkpoints[name] = time() - self.start_time

    def elapsed(self) -> float:
        """경과 시간 반환 (초)

        Returns:
            float: 시작부터 현재까지 경과 시간. start() 전에는 0.0 반환.
        """
        if self.start_time is None:
            return 0.0
        return time() - self.start_time

    def remaining(self) -> float:
        """남은 예산 반환 (초)

        Returns:
            float: 남은 예산. 음수가 되지 않도록 보장.
        """
        return max(0.0, self.config.total_budget - self.elapsed())

    def can_execute_fastpath(self) -> bool:
        """FastPath 실행 가능 여부

        Returns:
            bool: FastPath를 실행할 충분한 예산이 남아있는지 여부
        """
        return self.remaining() >= self.config.fastpath_timeout

    def can_execute_slowpath(self) -> bool:
        """SlowPath 실행 가능 여부

        Returns:
            bool: SlowPath를 실행할 충분한 예산이 남아있는지 여부
        """
        return self.remaining() >= self.config.slowpath_timeout

    def is_exhausted(self) -> bool:
        """예산 소진 여부

        Returns:
            bool: 최소 여유 시간보다 적게 남았는지 여부
        """
        return self.remaining() < self.config.min_remaining

    def get_timeout_for(self, stage: str) -> float:
        """단계별 타임아웃 계산

        남은 예산과 단계별 설정값 중 작은 값을 반환합니다.

        Args:
            stage: 실행 단계 ("cache", "fastpath", "slowpath")

        Returns:
            float: 해당 단계에 적용할 타임아웃 (초)
        """
        remaining = self.remaining()

        if stage == "cache":
            return min(self.config.cache_timeout, remaining)
        elif stage == "fastpath":
            return min(self.config.fastpath_timeout, remaining)
        elif stage == "slowpath":
            return min(self.config.slowpath_timeout, remaining)
        else:
            return remaining

    def get_report(self) -> dict:
        """예산 사용 리포트 생성

        Returns:
            dict: 예산 사용 현황 정보
                - total_budget: 전체 예산
                - elapsed: 경과 시간
                - remaining: 남은 예산
                - checkpoints: 체크포인트별 경과 시간
                - is_exhausted: 예산 소진 여부
        """
        return {
            "total_budget": self.config.total_budget,
            "elapsed": self.elapsed(),
            "remaining": self.remaining(),
            "checkpoints": self._checkpoints.copy(),
            "is_exhausted": self.is_exhausted(),
        }
