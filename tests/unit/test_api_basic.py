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
    product_name: str = "matched"
    metadata: dict[str, Any] | None = None


class FakeFastPath:
    def __init__(
        self,
        result: Optional[FakeResult] = None,
        error: Optional[Exception] = None,
        error_by_product_code: Optional[dict[Optional[str], Exception]] = None,
    ):
        self.result = result
        self.error = error
        self.error_by_product_code = error_by_product_code or {}
        self.calls = 0
        self.received_product_codes: list[Optional[str]] = []

    async def execute(self, query: str, timeout: float, product_code: Optional[str] = None):
        self.calls += 1
        self.received_product_codes.append(product_code)
        if product_code in self.error_by_product_code:
            raise self.error_by_product_code[product_code]
        if self.error:
            raise self.error
        return self.result


class FakeSlowPath:
    def __init__(self, result: Optional[FakeResult] = None, error: Optional[Exception] = None):
        self.result = result
        self.error = error
        self.calls = 0
        self.received_product_codes: list[Optional[str]] = []

    async def execute(self, query: str, timeout: float, product_code: Optional[str] = None):
        self.calls += 1
        self.received_product_codes.append(product_code)
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
        fast = FakeFastPath(
            result=FakeResult(
                "f",
                2000,
                product_name="real product",
                metadata={
                    "product_name": "real product",
                    "mall": "Danawa",
                    "free_shipping": True,
                    "top_prices": [{"price": 2000}],
                    "price_trend": [{"label": "today", "price": 2000}],
                },
            )
        )
        slow = FakeSlowPath(result=FakeResult("s", 3000))

        orch = make_orchestrator(cache, fast, slow)
        result = await orch.search("query")

        assert result.status == SearchStatus.FASTPATH_SUCCESS
        assert fast.calls == 1
        assert slow.calls == 0
        assert cache.saved["query"]["price"] == 2000
        assert result.product_name == "real product"
        assert result.mall == "Danawa"
        assert result.free_shipping is True
        assert result.price_trend == [{"label": "today", "price": 2000}]

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

        # SlowPath returning None is treated as a parse error
        assert result.status == SearchStatus.PARSE_ERROR

    @pytest.mark.asyncio
    async def test_product_code_is_forwarded_to_fastpath(self):
        cache = FakeCache(hit=None)
        fast = FakeFastPath(result=FakeResult("f", 2000))
        slow = FakeSlowPath(result=FakeResult("s", 3000))

        orch = make_orchestrator(cache, fast, slow)
        result = await orch.search("query", product_code="12345")

        assert result.status == SearchStatus.FASTPATH_SUCCESS
        assert fast.received_product_codes == ["12345"]
        assert slow.calls == 0

    @pytest.mark.asyncio
    async def test_product_code_falls_back_to_query_search(self):
        cache = FakeCache(hit=None)
        fast = FakeFastPath(
            result=FakeResult("f", 2000),
            error_by_product_code={"12345": Exception("direct pcode failed")},
        )
        slow = FakeSlowPath(result=FakeResult("s", 3000))

        orch = make_orchestrator(cache, fast, slow)
        result = await orch.search("query", product_code="12345")

        assert result.status == SearchStatus.FASTPATH_SUCCESS
        assert fast.received_product_codes == ["12345", None]
        assert slow.received_product_codes == []


class TestBudgetAndValidation:
    @pytest.mark.asyncio
    async def test_budget_exhausted_skips_slowpath(self):
        cache = FakeCache(hit=None)
        fast = FakeFastPath(result=None)
        slow = FakeSlowPath(result=FakeResult("s", 3000))

        tight_budget = BudgetConfig(total_budget=2.0, cache_timeout=0.1, fastpath_timeout=0.5, slowpath_timeout=1.0)
        orch = make_orchestrator(cache, fast, slow, budget=tight_budget)

        # Force budget exhaustion branch deterministically
        orch.budget_manager.can_execute_slowpath = lambda: False  # type: ignore[assignment]

        result = await orch.search("query")

        assert result.status == SearchStatus.BUDGET_EXHAUSTED

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
        from src.engine.exceptions import TimeoutError as EngineTimeout
        from src.core.exceptions import BlockedException

        assert ExecutionStrategy.should_fallback_to_slowpath(EngineTimeout()) is True
        assert ExecutionStrategy.should_fallback_to_slowpath(BlockedException("blocked")) is True
        assert ExecutionStrategy.should_fallback_to_slowpath(ValueError("noop")) is False
