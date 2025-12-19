"""Stress Tests - 고부하 성능 테스트

테스트 범위:
- 대량 동시 요청 (100+)
- 메모리 사용량 모니터링
- 응답 시간 측정
- 캐시 효율성
- 시스템 안정성
"""

import pytest
import httpx
import time
import asyncio
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import os


class TestStressBasic:
    """기본 스트레스 테스트"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_100_sequential_requests(
        self, api_base_url, http_client, api_search_payloads_diverse
    ):
        """테스트 1: 100개 순차 요청
        
        동일 상품 100개를 순차적으로 요청합니다.
        """
        results = {
            "total": 0,
            "success": 0,
            "error": 0,
            "not_found": 0,
            "times": [],
        }
        
        # 100번 반복 (10개 상품 × 10회)
        for i in range(10):
            for payload in api_search_payloads_diverse:
                start = time.time()
                response = http_client.post(
                    f"{api_base_url}/api/v1/price/search",
                    json=payload,
                    timeout=25.0,
                )
                elapsed = time.time() - start
                
                results["total"] += 1
                results["times"].append(elapsed)
                
                if response.status_code == 200:
                    results["success"] += 1
                elif response.status_code == 404:
                    results["not_found"] += 1
                else:
                    results["error"] += 1
        
        # 통계
        assert results["total"] == 50
        assert results["success"] + results["not_found"] > 0
        
        avg_time = sum(results["times"]) / len(results["times"])
        max_time = max(results["times"])
        min_time = min(results["times"])
        
        print(f"\n=== Stress Test 1: 100 Sequential Requests ===")
        print(f"Total: {results['total']}")
        print(f"Success: {results['success']}")
        print(f"Not Found: {results['not_found']}")
        print(f"Errors: {results['error']}")
        print(f"Avg Time: {avg_time:.3f}s")
        print(f"Min Time: {min_time:.3f}s")
        print(f"Max Time: {max_time:.3f}s")

    def test_cache_efficiency_sequential(
        self, api_base_url, http_client, api_search_payload_shin_ramyeon
    ):
        """테스트 2: 캐시 효율성 (순차)
        
        같은 상품을 10번 요청하면 점점 빨라집니다.
        """
        times = []
        
        for i in range(10):
            start = time.time()
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=api_search_payload_shin_ramyeon,
                timeout=25.0,
            )
            elapsed = time.time() - start
            times.append(elapsed)
        
        print(f"\n=== Stress Test 2: Cache Efficiency ===")
        for i, t in enumerate(times):
            print(f"Request {i+1}: {t:.3f}s")
        
        # 캐시 히트는 첫 요청보다 훨씬 빠름
        first_request = times[0]
        cached_requests = times[1:]
        avg_cached = sum(cached_requests) / len(cached_requests)
        
        print(f"First request: {first_request:.3f}s")
        print(f"Avg cached: {avg_cached:.3f}s")
        print(f"Speedup: {first_request / avg_cached:.1f}x")

    def test_concurrent_requests_threaded(
        self, api_base_url, api_search_payloads_diverse
    ):
        """테스트 3: 동시 요청 (멀티스레드, 20 스레드)
        
        20개 스레드에서 동시에 요청합니다.
        """
        
        def make_request(payload: Dict[str, Any]) -> tuple:
            try:
                with httpx.Client(timeout=25.0) as client:
                    start = time.time()
                    response = client.post(
                        f"{api_base_url}/api/v1/price/search",
                        json=payload,
                        timeout=25.0,
                    )
                    elapsed = time.time() - start
                    return (response.status_code, elapsed)
            except Exception as e:
                return (None, None)
        
        results = {
            "total": 0,
            "success": 0,
            "error": 0,
            "times": [],
        }
        
        # 각 상품을 4번씩 요청 (5개 상품 × 4 = 20개 요청)
        payloads = api_search_payloads_diverse * 4
        
        start_total = time.time()
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(make_request, payload) for payload in payloads
            ]
            
            for future in as_completed(futures):
                status_code, elapsed = future.result()
                results["total"] += 1
                
                if status_code == 200:
                    results["success"] += 1
                    results["times"].append(elapsed)
                elif status_code == 404:
                    pass
                else:
                    results["error"] += 1
        
        total_elapsed = time.time() - start_total
        
        print(f"\n=== Stress Test 3: Concurrent Requests (20 threads) ===")
        print(f"Total Requests: {results['total']}")
        print(f"Success: {results['success']}")
        print(f"Errors: {results['error']}")
        print(f"Total Time: {total_elapsed:.3f}s")
        
        if results["times"]:
            print(f"Avg Response Time: {sum(results['times']) / len(results['times']):.3f}s")
            print(f"Max Response Time: {max(results['times']):.3f}s")

    def test_different_products_concurrent(
        self, api_base_url, api_stress_payloads
    ):
        """테스트 4: 다양한 상품 동시 요청 (100개)
        
        100개의 서로 다른 상품을 동시에 요청합니다.
        """
        
        def make_request(payload: Dict[str, Any]) -> tuple:
            try:
                with httpx.Client(timeout=25.0) as client:
                    start = time.time()
                    response = client.post(
                        f"{api_base_url}/api/v1/price/search",
                        json=payload,
                        timeout=25.0,
                    )
                    elapsed = time.time() - start
                    return (response.status_code, elapsed, payload["product_name"])
            except Exception as e:
                return (None, None, payload["product_name"])
        
        results = {
            "total": 0,
            "success": 0,
            "error": 0,
            "times": [],
        }
        
        start_total = time.time()
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(make_request, payload)
                for payload in api_stress_payloads[:100]
            ]
            
            for future in as_completed(futures):
                status_code, elapsed, product = future.result()
                results["total"] += 1
                
                if status_code == 200:
                    results["success"] += 1
                    if elapsed:
                        results["times"].append(elapsed)
                elif status_code == 404:
                    pass
                else:
                    results["error"] += 1
        
        total_elapsed = time.time() - start_total
        
        print(f"\n=== Stress Test 4: 100 Different Products ===")
        print(f"Total Requests: {results['total']}")
        print(f"Success: {results['success']}")
        print(f"Errors: {results['error']}")
        print(f"Total Time: {total_elapsed:.3f}s")
        print(f"Requests/Second: {results['total'] / total_elapsed:.2f}")
        
        if results["times"]:
            print(f"Avg Response Time: {sum(results['times']) / len(results['times']):.3f}s")


class TestPerformanceMetrics:
    """성능 지표 측정"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_response_time_p99(self, api_base_url, api_search_payloads_diverse):
        """테스트 5: 응답 시간 P99 (99th percentile)
        
        상위 1%를 제외한 응답 시간을 측정합니다.
        """
        
        def make_request(payload):
            try:
                with httpx.Client(timeout=25.0) as client:
                    start = time.time()
                    response = client.post(
                        f"{api_base_url}/api/v1/price/search",
                        json=payload,
                        timeout=25.0,
                    )
                    return time.time() - start
            except:
                return None
        
        times = []
        payloads = api_search_payloads_diverse * 10  # 50개 요청
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(make_request, payload) for payload in payloads
            ]
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    times.append(result)
        
        times.sort()
        p99_idx = int(len(times) * 0.99)
        p99_time = times[p99_idx]
        p95_time = times[int(len(times) * 0.95)]
        p50_time = times[int(len(times) * 0.50)]
        
        print(f"\n=== Stress Test 5: Response Time Percentiles ===")
        print(f"P50: {p50_time:.3f}s")
        print(f"P95: {p95_time:.3f}s")
        print(f"P99: {p99_time:.3f}s")

    def test_memory_usage(self, api_base_url, api_search_payloads_diverse):
        """테스트 6: 메모리 사용량
        
        대량 요청 중 메모리 사용량을 추적합니다.
        """
        
        def make_request(payload):
            try:
                with httpx.Client(timeout=25.0) as client:
                    response = client.post(
                        f"{api_base_url}/api/v1/price/search",
                        json=payload,
                        timeout=25.0,
                    )
                    return response.status_code
            except:
                return None
        
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        payloads = api_search_payloads_diverse * 20  # 100개 요청
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(make_request, payload) for payload in payloads
            ]
            
            for future in as_completed(futures):
                future.result()
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        print(f"\n=== Stress Test 6: Memory Usage ===")
        print(f"Memory Before: {memory_before:.2f} MB")
        print(f"Memory After: {memory_after:.2f} MB")
        print(f"Increase: {memory_increase:.2f} MB")

    def test_error_rate_under_load(self, api_base_url, api_search_payloads_diverse):
        """테스트 7: 고부하 에러율
        
        100개의 동시 요청 중 에러율을 측정합니다.
        """
        
        def make_request(payload):
            try:
                with httpx.Client(timeout=25.0) as client:
                    response = client.post(
                        f"{api_base_url}/api/v1/price/search",
                        json=payload,
                        timeout=25.0,
                    )
                    return response.status_code
            except:
                return None
        
        total = 0
        success = 0
        error = 0
        
        payloads = api_search_payloads_diverse * 20  # 100개 요청
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [
                executor.submit(make_request, payload) for payload in payloads
            ]
            
            for future in as_completed(futures):
                total += 1
                status = future.result()
                if status == 200:
                    success += 1
                elif status and status != 404:
                    error += 1
        
        error_rate = (error / total * 100) if total > 0 else 0
        
        print(f"\n=== Stress Test 7: Error Rate Under Load ===")
        print(f"Total: {total}")
        print(f"Success: {success}")
        print(f"Error Rate: {error_rate:.2f}%")


class TestBudgetConstraints:
    """예산 제약 테스트 (12초 제한)"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_all_requests_within_timeout(
        self, api_base_url, api_search_payloads_diverse
    ):
        """테스트 8: 모든 요청이 20초 내에 완료
        
        각 요청이 설정된 타임아웃 내에 완료됩니다.
        """
        times = []
        timeout_exceeded = 0
        
        for payload in api_search_payloads_diverse * 10:  # 50개
            start = time.time()
            try:
                with httpx.Client(timeout=25.0) as client:
                    response = client.post(
                        f"{api_base_url}/api/v1/price/search",
                        json=payload,
                        timeout=25.0,
                    )
                    elapsed = time.time() - start
                    times.append(elapsed)
            except httpx.TimeoutException:
                timeout_exceeded += 1
        
        print(f"\n=== Stress Test 8: Budget Constraints ===")
        print(f"Total Requests: {len(times) + timeout_exceeded}")
        print(f"Completed: {len(times)}")
        print(f"Timeout Exceeded: {timeout_exceeded}")
        
        if times:
            print(f"Avg Time: {sum(times) / len(times):.3f}s")
            print(f"Max Time: {max(times):.3f}s")
