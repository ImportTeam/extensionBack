"""Unit Tests (엔진 교체 내성)

PRD 원칙:
- 외부 호출 없음 (HTTP/DB/Redis 금지)
- FastPath/SlowPath/Fallback 의미 보존 검증
- Budget/Timeout/예외 → Status 매핑 검증
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest

from src.engine import BudgetConfig, SearchOrchestrator
from src.engine.result import SearchStatus
from src.engine.strategy import ExecutionStrategy


@dataclass
class FakeResult:
    product_url: str
    price: int


class FakeFastPath:
    def __init__(self, result: Optional[FakeResult] = None, error: Optional[Exception] = None):
        self.result = result
        self.error = error
        self.calls = 0

    async def execute(self, query: str, timeout: float):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class FakeSlowPath:
    def __init__(self, result: Optional[FakeResult] = None, error: Optional[Exception] = None):
        self.result = result
        self.error = error
        self.calls = 0

    async def execute(self, query: str, timeout: float):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class FakeCache:
    def __init__(self, hit: Optional[dict[str, Any]] = None):
        self.hit = hit
        self.saved: dict[str, dict[str, Any]] = {}

    async def get(self, key: str, timeout: float) -> Optional[dict[str, Any]]:
        return self.hit

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        self.saved[key] = value


def make_orchestrator(
    cache: FakeCache,
    fast: FakeFastPath,
    slow: FakeSlowPath,
    budget: Optional[BudgetConfig] = None,
) -> SearchOrchestrator:
    return SearchOrchestrator(
        cache_service=cache,
        fastpath_executor=fast,
        slowpath_executor=slow,
        budget_config=budget,
    )


class TestOrchestratorFlow:
    @pytest.mark.asyncio
    async def test_cache_hit_short_circuits(self):
        cache = FakeCache(hit={"product_url": "u", "price": 1000})
        fast = FakeFastPath(result=FakeResult("f", 2000))
        slow = FakeSlowPath(result=FakeResult("s", 3000))

        orch = make_orchestrator(cache, fast, slow)
        result = await orch.search("query")

        assert result.status == SearchStatus.CACHE_HIT
        assert fast.calls == 0
        assert slow.calls == 0

    @pytest.mark.asyncio
    async def test_fastpath_success_and_cached(self):
        cache = FakeCache(hit=None)
        fast = FakeFastPath(result=FakeResult("f", 2000))
        slow = FakeSlowPath(result=FakeResult("s", 3000))

        orch = make_orchestrator(cache, fast, slow)
        result = await orch.search("query")

        assert result.status == SearchStatus.FASTPATH_SUCCESS
        assert fast.calls == 1
        assert slow.calls == 0
        assert cache.saved["query"]["price"] == 2000

    @pytest.mark.asyncio
    async def test_fallback_to_slowpath_on_fastpath_none(self):
        cache = FakeCache(hit=None)
        fast = FakeFastPath(result=None)
        slow = FakeSlowPath(result=FakeResult("s", 3000))

        orch = make_orchestrator(cache, fast, slow)
        result = await orch.search("query")

        assert result.status == SearchStatus.SLOWPATH_SUCCESS
        assert fast.calls == 1
        assert slow.calls == 1

    @pytest.mark.asyncio
    async def test_no_results_when_all_fail(self):
        cache = FakeCache(hit=None)
        fast = FakeFastPath(result=None)
        slow = FakeSlowPath(result=None)

        orch = make_orchestrator(cache, fast, slow)
        result = await orch.search("query")

        assert result.status == SearchStatus.NO_RESULTS


class TestBudgetAndValidation:
    @pytest.mark.asyncio
    async def test_budget_exhausted_skips_slowpath(self):
        cache = FakeCache(hit=None)
        fast = FakeFastPath(result=None)
        slow = FakeSlowPath(result=FakeResult("s", 3000))

        tight_budget = BudgetConfig(total_budget=2.0, cache_timeout=0.1, fastpath_timeout=0.5, slowpath_timeout=1.8)
        orch = make_orchestrator(cache, fast, slow, budget=tight_budget)

        result = await orch.search("query")

        # fastpath timed out → slowpath budget exhausted path
        assert result.status in {SearchStatus.NO_RESULTS, SearchStatus.BUDGET_EXHAUSTED}

    @pytest.mark.asyncio
    async def test_invalid_query_raises(self):
        cache = FakeCache(hit=None)
        fast = FakeFastPath(result=None)
        slow = FakeSlowPath(result=None)
        orch = make_orchestrator(cache, fast, slow)

        with pytest.raises(ValueError):
            await orch.search(None)  # type: ignore[arg-type]


class TestExecutionStrategy:
    def test_fallback_errors(self):
        class DummyTimeout(Exception):
            pass

        class DummyBlocked(Exception):
            pass

        assert ExecutionStrategy.should_fallback_to_slowpath(DummyTimeout()) is True
        assert ExecutionStrategy.should_fallback_to_slowpath(DummyBlocked()) is False  # not registered

