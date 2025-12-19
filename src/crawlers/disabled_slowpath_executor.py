"""Disabled SlowPath Executor

저메모리/저비용 환경(Render Free 등)에서 브라우저 기반 SlowPath를 비활성화하기 위한 실행자입니다.

의도:
- 오케스트레이터는 동일한 인터페이스(SearchExecutor)를 기대하므로, 구현체를 주입해
  SlowPath 단계에서 '결과 없음'으로 자연스럽게 종료되도록 만듭니다.
"""

from __future__ import annotations

from src.core.logging import logger
from src.core.exceptions import ProductNotFoundException

from .executor import SearchExecutor
from .result import CrawlResult


class DisabledSlowPathExecutor(SearchExecutor):
    async def execute(self, query: str, timeout: float) -> CrawlResult:
        logger.info(
            f"[SlowPath:disabled] Skipping browser fallback: query='{query}', timeout={timeout:.2f}s"
        )
        raise ProductNotFoundException(
            query=query,
            details={"reason": "slowpath_disabled"},
        )
