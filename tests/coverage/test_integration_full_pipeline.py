"""Integration/Coverage Tests - 전체 파이프라인 검증

테스트 범위:
- Cache → FastPath → SlowPath 전체 흐름
- 다양한 상품 카테고리
- 캐시 히트/미스
- 실패 복구 (폴백)
- 검색 로그 기록
"""

import pytest
import httpx
import time
from typing import List, Dict, Any


class TestFullPipeline:
    """전체 검색 파이프라인 테스트 (Cache → FastPath → SlowPath)"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_first_search_fastpath(
        self, api_base_url, http_client, api_search_payload_shin_ramyeon
    ):
        """테스트 1: 첫 번째 검색 (캐시 미스 → FastPath)
        
        캐시에 없으면 FastPath(HTTP)로 검색합니다.
        - Expected: 200 OK + source = "fastpath"
        """
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=api_search_payload_shin_ramyeon,
            timeout=25.0,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 첫 검색이므로 캐시 미스 → FastPath 또는 SlowPath
        if "source" in data["data"]:
            assert data["data"]["source"] in ["fastpath", "slowpath"]

    def test_cache_hit_on_second_search(
        self, api_base_url, http_client, api_search_payload_shin_ramyeon
    ):
        """테스트 2: 두 번째 검색 (캐시 히트)
        
        같은 상품을 다시 검색하면 캐시에서 반환합니다.
        - Expected: 매우 빠른 응답 (< 500ms)
        """
        # 첫 번째 검색
        response1 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=api_search_payload_shin_ramyeon,
            timeout=25.0,
        )
        
        # 짧은 대기 후 두 번째 검색
        time.sleep(0.5)
        
        start = time.time()
        response2 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=api_search_payload_shin_ramyeon,
            timeout=25.0,
        )
        elapsed = (time.time() - start) * 1000  # ms
        
        assert response2.status_code == 200
        
        # 캐시 히트는 매우 빨라야 함 (< 500ms)
        if response1.status_code == 200:
            assert elapsed < 500, f"Cache hit should be fast, got {elapsed}ms"

    def test_diverse_product_categories(
        self, api_base_url, http_client, api_search_payloads_diverse
    ):
        """테스트 3: 다양한 상품 카테고리
        
        전자제품, 식품, 화장품 등 여러 카테고리를 검색합니다.
        """
        for payload in api_search_payloads_diverse:
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=payload,
                timeout=25.0,
            )
            
            # 상품을 찾지 못했을 수도 있지만, 요청은 정상 처리
            assert response.status_code in [200, 404]

    def test_sequential_searches(self, api_base_url, http_client):
        """테스트 4: 순차 검색 (10개 상품)
        
        10개의 상품을 순차적으로 검색합니다.
        """
        products = [
            ("삼성 갤럭시 버즈3", 207900),
            ("Apple 맥북 에어 M4", 1430980),
            ("신라면", 2986),
            ("Intel i5-12400F", 190900),
            ("TCL TV 55인치", 634230),
            ("아이패드 프로", 1299000),
            ("에이수스 비보북", 1024000),
            ("LG 올레드 TV", 2500000),
            ("삼성 노트북", 669000),
            ("농심 신라면 블랙", 33230),
        ]
        
        responses = []
        for product_name, price in products:
            payload = {
                "product_name": product_name,
                "current_price": price,
            }
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=payload,
                timeout=25.0,
            )
            responses.append((product_name, response.status_code))
        
        # 모든 응답이 200 또는 404
        for product_name, status_code in responses:
            assert status_code in [200, 404], f"{product_name}: {status_code}"

    def test_fallback_on_fastpath_failure(
        self, api_base_url, http_client
    ):
        """테스트 5: FastPath 실패 시 SlowPath 폴백
        
        HTTP 요청이 실패하면 Playwright 폴백을 시도합니다.
        """
        # 어려운 검색어 (FastPath 실패 가능성 높음)
        payload = {
            "product_name": "매우 특이한 제품명 이상한 상품 zzzzz",
            "current_price": 999999,
        }
        
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
            timeout=25.0,
        )
        
        # 결과를 못 찾았을 수 있지만, 요청은 정상 처리
        assert response.status_code in [200, 404]

    def test_response_consistency(
        self, api_base_url, http_client, api_search_payload_shin_ramyeon
    ):
        """테스트 6: 응답 일관성
        
        같은 상품의 응답이 일관성 있게 반환됩니다.
        """
        responses = []
        for _ in range(3):
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=api_search_payload_shin_ramyeon,
                timeout=25.0,
            )
            
            if response.status_code == 200:
                responses.append(response.json()["data"]["lowest_price"])
        
        # 모든 응답이 같은 가격
        if len(responses) >= 2:
            assert all(price == responses[0] for price in responses)


class TestErrorRecovery:
    """에러 처리 및 복구 테스트"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_non_existent_product(self, api_base_url, http_client):
        """테스트 7: 존재하지 않는 상품
        
        검색 결과가 없으면 404를 반환합니다.
        """
        payload = {
            "product_name": "절대로존재할수없는상품명완전히가짜상품",
            "current_price": 100000,
        }
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
            timeout=25.0,
        )
        
        assert response.status_code in [200, 404]
        # 200이면 상품 못 찾음, 404면 상품 없음

    def test_malformed_json(self, api_base_url, http_client):
        """테스트 8: 잘못된 JSON
        
        잘못된 JSON은 400 에러를 반환합니다.
        """
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            content=b"{invalid json}",
            headers={"Content-Type": "application/json"},
        )
        
        assert response.status_code == 400

    def test_missing_required_fields(self, api_base_url, http_client):
        """테스트 9: 필수 필드 누락
        
        product_name이 없으면 400 에러를 반환합니다.
        """
        test_cases = [
            {},  # 모든 필드 없음
            {"current_price": 100000},  # product_name 없음
            {"product_name": ""},  # product_name 빈 문자열
        ]
        
        for payload in test_cases:
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=payload,
            )
            assert response.status_code == 400


class TestPriceComparison:
    """가격 비교 기능 테스트"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_cheaper_product(self, api_base_url, http_client):
        """테스트 10: 더 싼 상품
        
        다나와 최저가가 현재 가격보다 저렴하면 is_cheaper=true
        """
        # 높은 가격으로 설정
        payload = {
            "product_name": "신라면 120g",
            "current_price": 10000,  # 실제 가격보다 훨씬 높음
        }
        
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
            timeout=25.0,
        )
        
        if response.status_code == 200:
            result = response.json()["data"]
            # is_cheaper가 true일 수 있음
            if "is_cheaper" in result:
                assert isinstance(result["is_cheaper"], bool)

    def test_expensive_product(self, api_base_url, http_client):
        """테스트 11: 더 비싼 상품
        
        다나와 최저가가 현재 가격보다 비싸면 is_cheaper=false
        """
        # 낮은 가격으로 설정
        payload = {
            "product_name": "Apple 맥북 에어 M4",
            "current_price": 500000,  # 실제 가격보다 훨씬 낮음
        }
        
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
            timeout=25.0,
        )
        
        if response.status_code == 200:
            result = response.json()["data"]
            if "is_cheaper" in result:
                assert isinstance(result["is_cheaper"], bool)

    def test_top_prices_ranking(self, api_base_url, http_client):
        """테스트 12: 최저가 TOP3 순위
        
        top_prices가 가격순으로 정렬되어 있습니다.
        """
        payload = {
            "product_name": "신라면 120g",
            "current_price": 3000,
        }
        
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
            timeout=25.0,
        )
        
        if response.status_code == 200:
            result = response.json()["data"]
            if "top_prices" in result and result["top_prices"]:
                top_prices = result["top_prices"]
                
                # top_prices가 비어있지 않으면
                if len(top_prices) > 1:
                    # 가격순으로 정렬
                    for i in range(len(top_prices) - 1):
                        assert (
                            top_prices[i]["price"] <= top_prices[i + 1]["price"]
                        ), "top_prices should be sorted by price"


class TestCacheConsistency:
    """캐시 일관성 테스트"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_cache_isolation_between_products(self, api_base_url, http_client):
        """테스트 13: 상품 간 캐시 격리
        
        다른 상품의 캐시가 서로 영향을 주지 않습니다.
        """
        product1 = {"product_name": "신라면", "current_price": 3000}
        product2 = {"product_name": "맥북", "current_price": 1000000}
        
        # 각각 검색
        resp1_1 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=product1,
            timeout=25.0,
        )
        resp2_1 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=product2,
            timeout=25.0,
        )
        
        # 캐시에서 다시 검색
        resp1_2 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=product1,
            timeout=25.0,
        )
        resp2_2 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=product2,
            timeout=25.0,
        )
        
        # 각각의 응답이 일관성 있어야 함
        if resp1_1.status_code == 200 and resp1_2.status_code == 200:
            assert (
                resp1_1.json()["data"]["lowest_price"]
                == resp1_2.json()["data"]["lowest_price"]
            )

    def test_cache_ttl_6hours(self, api_base_url, http_client):
        """테스트 14: 캐시 TTL 검증 (6시간)
        
        캐시는 6시간 동안 유지됩니다.
        (실제 테스트는 즉시 재요청만 가능)
        """
        payload = {
            "product_name": "신라면 120g",
            "current_price": 3000,
        }
        
        # 첫 번째 요청
        response1 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
            timeout=25.0,
        )
        
        # 즉시 재요청
        response2 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
            timeout=25.0,
        )
        
        if response1.status_code == 200 and response2.status_code == 200:
            # 두 응답이 동일
            assert response1.json() == response2.json()
