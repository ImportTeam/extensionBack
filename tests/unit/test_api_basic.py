"""Unit Tests - API 기본 기능 검증

테스트 범위:
- API 엔드포인트 가용성
- 요청/응답 형식 검증
- 입력값 검증 (보안)
- 단순 성공/실패 시나리오
"""

import pytest
import httpx
from typing import Dict, Any


class TestAPIBasicFunctionality:
    """API 기본 기능 테스트 (localhost:8000)"""

    @pytest.fixture
    def http_client(self):
        """HTTP 클라이언트"""
        return httpx.Client(timeout=25.0)

    def test_api_health_check(self, api_base_url, http_client):
        """테스트 1: API 헬스체크
        
        서버가 정상 작동하는지 확인합니다.
        - Expected: 200 OK
        - Check: Redis + PostgreSQL 상태
        """
        response = http_client.get(f"{api_base_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ["healthy", "ok"]

    def test_price_search_success_basic(
        self, api_base_url, http_client, api_search_payload_shin_ramyeon
    ):
        """테스트 2: 기본 최저가 검색 성공 (신라면)
        
        간단한 상품의 기본 검색이 성공합니다.
        - Request: product_name, current_price
        - Expected: 200 OK + SearchResult
        """
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=api_search_payload_shin_ramyeon,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 응답 구조 검증
        assert "status" in data
        assert "data" in data
        assert "message" in data
        
        # data 구조 검증
        result = data["data"]
        assert "is_cheaper" in result
        assert "lowest_price" in result
        assert isinstance(result["is_cheaper"], bool)
        assert isinstance(result["lowest_price"], int)

    def test_price_search_request_format(self, api_base_url, http_client):
        """테스트 3: 요청 형식 검증
        
        FE에서 보내는 정확한 형식을 사용합니다.
        - product_name만 포함 (다나와 URL 제외)
        - current_price는 선택사항
        """
        # 정상 요청: product_name + current_price
        payload = {
            "product_name": "농심 신라면 120g",
            "current_price": 2986,
        }
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
        )
        assert response.status_code == 200

    def test_price_search_missing_product_name(self, api_base_url, http_client):
        """테스트 4: 필수 필드 누락 검증
        
        product_name이 없으면 400 에러를 반환합니다.
        - Expected: 400 Bad Request
        """
        payload = {
            "current_price": 100000,
            # product_name 누락
        }
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
        )
        assert response.status_code == 400

    def test_price_search_empty_product_name(self, api_base_url, http_client):
        """테스트 5: 빈 product_name 검증
        
        product_name이 비어있으면 400 에러를 반환합니다.
        """
        payload = {
            "product_name": "",
            "current_price": 100000,
        }
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
        )
        assert response.status_code == 400

    def test_price_search_negative_price(self, api_base_url, http_client):
        """테스트 6: 음수 가격 검증
        
        current_price가 음수이면 400 에러를 반환합니다.
        """
        payload = {
            "product_name": "아이폰",
            "current_price": -1000,
        }
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
        )
        assert response.status_code == 400

    def test_price_search_xss_injection(self, api_base_url, http_client):
        """테스트 7: XSS 인젝션 방지
        
        XSS 페이로드가 있어도 서버는 안전하게 처리합니다.
        - product_name 정규화 진행
        - 또는 400 에러 반환
        """
        payload = {
            "product_name": "<script>alert('xss')</script>",
            "current_price": 100000,
        }
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload,
        )
        # 정규화되거나 에러 반환
        assert response.status_code in [200, 400]

    def test_price_search_response_contains_required_fields(
        self, api_base_url, http_client, api_search_payload_shin_ramyeon
    ):
        """테스트 8: 응답 필수 필드 검증
        
        성공 응답에는 다음 필드가 모두 포함되어야 합니다.
        """
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=api_search_payload_shin_ramyeon,
        )
        
        if response.status_code == 200:
            data = response.json()
            result = data["data"]
            
            required_fields = [
                "is_cheaper",
                "lowest_price",
                "link",
                "mall",
                "free_shipping",
            ]
            for field in required_fields:
                assert field in result, f"Missing field: {field}"

    def test_price_search_timeout_handling(
        self, api_base_url, http_client, api_search_payload_macbook_m4
    ):
        """테스트 9: 타임아웃 처리
        
        20초 이내에 응답을 받거나 504 에러를 반환합니다.
        (서버 설정: 20초 하드캡)
        """
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=api_search_payload_macbook_m4,
            timeout=25.0,
        )
        
        # 200 OK 또는 504 Gateway Timeout
        assert response.status_code in [200, 504]

    def test_price_search_electronics_vs_food(
        self, api_base_url, http_client
    ):
        """테스트 10: 전자제품 vs 식품 검색 차이
        
        카테고리별로 다른 가격대를 반환합니다.
        """
        # 전자제품 (고가)
        electronics_payload = {
            "product_name": "Apple 맥북 에어 M4",
            "current_price": 1430980,
        }
        
        # 식품 (저가)
        food_payload = {
            "product_name": "농심 신라면 120g",
            "current_price": 2986,
        }
        
        resp_electronics = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=electronics_payload,
        )
        
        resp_food = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=food_payload,
        )
        
        if resp_electronics.status_code == 200 and resp_food.status_code == 200:
            price_electronics = resp_electronics.json()["data"]["lowest_price"]
            price_food = resp_food.json()["data"]["lowest_price"]
            
            # 맥북이 라면보다 훨씬 비싸야 함
            assert price_electronics > price_food * 100


class TestResponseStructure:
    """응답 구조 검증"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_response_json_format(
        self, api_base_url, http_client, api_search_payload_shin_ramyeon
    ):
        """테스트 11: 응답 JSON 형식
        
        모든 필드가 예상 타입입니다.
        """
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=api_search_payload_shin_ramyeon,
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # 타입 검증
            assert isinstance(data, dict)
            assert isinstance(data["status"], str)
            assert isinstance(data["message"], str)
            assert isinstance(data["data"], dict)

    def test_price_diff_calculation(
        self, api_base_url, http_client, api_search_payload_shin_ramyeon
    ):
        """테스트 12: 가격 차이 계산
        
        price_diff = current_price - lowest_price
        """
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=api_search_payload_shin_ramyeon,
        )
        
        if response.status_code == 200:
            result = response.json()["data"]
            current_price = api_search_payload_shin_ramyeon["current_price"]
            lowest_price = result["lowest_price"]
            price_diff = result.get("price_diff", 0)
            
            # price_diff가 있으면 검증
            if "price_diff" in result:
                expected_diff = current_price - lowest_price
                assert price_diff == expected_diff


class TestInputVariations:
    """다양한 입력값 테스트"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_product_name_variations(self, api_base_url, http_client):
        """테스트 13: 상품명 형식 다양성
        
        다양한 형식의 상품명을 처리합니다.
        """
        variations = [
            "삼성 갤럭시 버즈3",  # 단순 이름
            "삼성전자 갤럭시 버즈3 프로",  # 회사명 포함
            "Apple 맥북프로 14인치 M4",  # 영문 포함
            "농심 신라면 120g 40개",  # 사양 포함
        ]
        
        for product_name in variations:
            payload = {
                "product_name": product_name,
                "current_price": 100000,
            }
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=payload,
                timeout=25.0,
            )
            
            # 성공하거나 404 (상품 없음)
            assert response.status_code in [200, 404]

    def test_with_and_without_current_price(self, api_base_url, http_client):
        """테스트 14: current_price 유무
        
        current_price가 있을 때와 없을 때 모두 동작합니다.
        """
        # current_price 있음
        payload_with_price = {
            "product_name": "신라면",
            "current_price": 3000,
        }
        response1 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload_with_price,
            timeout=25.0,
        )
        
        # current_price 없음
        payload_without_price = {
            "product_name": "신라면",
        }
        response2 = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=payload_without_price,
            timeout=25.0,
        )
        
        # 둘 다 valid
        assert response1.status_code in [200, 404]
        assert response2.status_code in [200, 404]
