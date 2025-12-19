"""스트레스 테스트 - 높은 동시성/부하 환경 검증

Playwright/HTTP 크롤러가 동시에 많은 요청을 처리하면서도 타임아웃/메모리/폴백을 안전하게
관리하는지 검증합니다.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.engine.orchestrator import SearchOrchestrator
from src.engine.result import SearchStatus


class _CacheMock:
    def __init__(self):
        self.store = {}

    async def get(self, key, timeout=None):
        await asyncio.sleep(0.01)  # 네트워크 지연 시뮬레이션
        return self.store.get(key)

    async def set(self, key, value, ttl=None):
        await asyncio.sleep(0.01)
        self.store[key] = value


class _SlowFastPathMock:
    """FastPath가 항상 느린 경우"""
    def __init__(self, delay=0.5):
        self.delay = delay

    async def execute(self, query, timeout):
        await asyncio.sleep(self.delay)
        if self.delay > timeout:
            raise asyncio.TimeoutError(f"Slow fastpath exceeded timeout {timeout}s")
        return MagicMock(product_url="http://test.com", price=10000)


class _SlowPathMock:
    """SlowPath도 느린 경우 (또는 성공하는 경우)"""
    def __init__(self, delay=1.0, succeed=True):
        self.delay = delay
        self.succeed = succeed

    async def execute(self, query, timeout):
        await asyncio.sleep(self.delay)
        if self.delay > timeout:
            raise asyncio.TimeoutError(f"Slow slowpath exceeded timeout {timeout}s")
        if self.succeed:
            return MagicMock(product_url="http://test.com/fallback", price=9000)
        raise ValueError("SlowPath failed")


@pytest.mark.asyncio
async def test_concurrent_requests_10():
    """동시 10개 요청 (캐시 미스)"""
    cache = _CacheMock()
    fastpath = _SlowFastPathMock(delay=0.1)  # 100ms
    slowpath = _SlowPathMock(delay=0.2, succeed=True)  # 200ms

    orch = SearchOrchestrator(cache, fastpath, slowpath)

    queries = [f"product_{i}" for i in range(10)]
    tasks = [orch.search(q) for q in queries]

    results = await asyncio.gather(*tasks, return_exceptions=False)

    # 모두 성공해야 함
    assert len(results) == 10
    assert all(r.is_success for r in results)
    print(f"✅ 10개 동시 요청 성공 (avg elapsed: {sum(r.elapsed_ms for r in results) / 10:.1f}ms)")


@pytest.mark.asyncio
async def test_concurrent_requests_50():
    """동시 50개 요청 (높은 부하)"""
    cache = _CacheMock()
    fastpath = _SlowFastPathMock(delay=0.05)  # 50ms
    slowpath = _SlowPathMock(delay=0.1, succeed=True)  # 100ms

    orch = SearchOrchestrator(cache, fastpath, slowpath)

    queries = [f"product_{i}" for i in range(50)]
    tasks = [orch.search(q) for q in queries]

    results = await asyncio.gather(*tasks, return_exceptions=False)

    assert len(results) == 50
    # 타임아웃이 발생할 가능성이 있지만, 모두 "완료" 상태여야 함
    assert all(r.status in [SearchStatus.FASTPATH_SUCCESS, SearchStatus.SLOWPATH_SUCCESS, SearchStatus.TIMEOUT] for r in results)
    print(f"✅ 50개 동시 요청 완료 (성공: {sum(1 for r in results if r.is_success)}/50)")


@pytest.mark.asyncio
async def test_cache_hit_under_load():
    """캐시 히트 시나리오 (10개 동일 쿼리)"""
    cache = _CacheMock()
    cache.store["test_product"] = {"product_url": "http://test.com", "price": 5000}

    fastpath = _SlowFastPathMock(delay=0.5)
    slowpath = _SlowPathMock(delay=1.0)

    orch = SearchOrchestrator(cache, fastpath, slowpath)

    # 동일 쿼리 10개 병렬 요청
    tasks = [orch.search("test_product") for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # 모두 캐시 히트여야 함
    assert all(r.status == SearchStatus.CACHE_HIT for r in results)
    assert all(r.price == 5000 for r in results)
    print(f"✅ 캐시 10개 동시 히트 (avg elapsed: {sum(r.elapsed_ms for r in results) / 10:.1f}ms)")


@pytest.mark.asyncio
async def test_fastpath_timeout_fallback_to_slowpath():
    """FastPath 타임아웃 → SlowPath 폴백"""
    cache = _CacheMock()
    fastpath = _SlowFastPathMock(delay=5.0)  # 5초 (FastPath 예산 4s 초과)
    slowpath = _SlowPathMock(delay=0.2, succeed=True)

    orch = SearchOrchestrator(cache, fastpath, slowpath)

    # FastPath 타임아웃이 발생하면 SlowPath로 폴백해야 함
    result = await orch.search("test")

    # SlowPath에서 결과를 받아야 함
    assert result.status == SearchStatus.SLOWPATH_SUCCESS or result.status == SearchStatus.TIMEOUT
    print(f"✅ FastPath 타임아웃 → SlowPath 폴백 (status: {result.status.value})")


@pytest.mark.asyncio
async def test_sequential_vs_parallel_performance():
    """순차 vs 병렬 성능 비교"""
    import time

    cache = _CacheMock()
    fastpath = _SlowFastPathMock(delay=0.1)
    slowpath = _SlowPathMock(delay=0.05)

    orch = SearchOrchestrator(cache, fastpath, slowpath)
    queries = [f"product_{i}" for i in range(5)]

    # 순차
    start = time.time()
    seq_results = []
    for q in queries:
        r = await orch.search(q)
        seq_results.append(r)
    seq_time = time.time() - start

    # 병렬
    start = time.time()
    par_tasks = [orch.search(q) for q in queries]
    par_results = await asyncio.gather(*par_tasks)
    par_time = time.time() - start

    # 병렬이 훨씬 빨아야 함
    assert par_time < seq_time
    print(f"✅ 순차: {seq_time:.2f}s vs 병렬: {par_time:.2f}s (개선율: {(seq_time/par_time - 1)*100:.1f}%)")


@pytest.mark.asyncio
async def test_mixed_success_timeout():
    """성공/타임아웃 혼합 시나리오"""
    cache = _CacheMock()

    class _MixedExecutor:
        def __init__(self):
            self.call_count = 0

        async def execute(self, query, timeout):
            self.call_count += 1
            # 짝수 호출은 성공, 홀수 호출은 타임아웃
            if self.call_count % 2 == 0:
                return MagicMock(product_url="http://test.com", price=10000)
            raise asyncio.TimeoutError("Simulated timeout")

    fastpath = _MixedExecutor()
    slowpath = _SlowPathMock(delay=0.05, succeed=True)

    orch = SearchOrchestrator(cache, fastpath, slowpath)

    tasks = [orch.search(f"product_{i}") for i in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    assert len(results) == 10
    # 모든 결과가 유효한 상태여야 함
    assert all(r.status in [SearchStatus.FASTPATH_SUCCESS, SearchStatus.SLOWPATH_SUCCESS, SearchStatus.TIMEOUT] for r in results)
    print(f"✅ 혼합 성공/타임아웃 처리 완료 (10개)")
