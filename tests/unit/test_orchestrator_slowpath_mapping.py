import pytest

from src.core.exceptions import ProductNotFoundException
from src.engine.orchestrator import SearchOrchestrator
from src.engine.result import SearchStatus


class _DummyCache:
    async def get(self, key: str, timeout: float):
        return None

    async def set(self, key: str, value, ttl: int):
        return None


class _DummyFastPath:
    async def execute(self, query: str, timeout: float):
        raise ProductNotFoundException(query=query)


class _SlowPathNotFound:
    async def execute(self, query: str, timeout: float):
        raise ProductNotFoundException(query=query)


class _SlowPathTimeout:
    async def execute(self, query: str, timeout: float):
        raise TimeoutError("timeout")


@pytest.mark.asyncio
async def test_slowpath_product_not_found_maps_to_no_results():
    orch = SearchOrchestrator(
        cache_service=_DummyCache(),
        fastpath_executor=_DummyFastPath(),
        slowpath_executor=_SlowPathNotFound(),
    )
    result = await orch.search("some query")
    assert result.status == SearchStatus.NO_RESULTS


@pytest.mark.asyncio
async def test_slowpath_timeout_maps_to_timeout():
    orch = SearchOrchestrator(
        cache_service=_DummyCache(),
        fastpath_executor=_DummyFastPath(),
        slowpath_executor=_SlowPathTimeout(),
    )
    result = await orch.search("some query")
    assert result.status == SearchStatus.TIMEOUT
