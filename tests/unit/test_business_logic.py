"""
실제 비즈니스 로직 테스트 (상품명과 현재가격만으로 검색)

시나리오:
- FE: 상품명 ("Apple 2025 아이패드 프로 11(M5 모델) 스탠다드 글래스"), 현재가격 (1,517,000원)
- BE: 다나와에서 같은 상품의 최저가 검색
- 결과: 더 저렴한 가격이 있으면 추천, 없으면 현재가격이 최저
"""

import pytest
from typing import Dict, Any
from src.schemas.price_schema import PriceSearchRequest, PriceSearchResponse, PriceData
from src.engine.result import SearchResult, SearchStatus
from src.utils.edge_cases import EdgeCaseHandler


class TestBusinessLogic:
    """비즈니스 로직 테스트"""
    
    # ========== 정상 시나리오 ==========
    
    def test_request_with_product_name_only(self):
        """상품명만으로 요청 (URL 없음)"""
        request = PriceSearchRequest(
            product_name="Apple 2025 아이패드 프로 11(M5 모델) 스탠다드 글래스",
            current_price=None,  # 가격 없음
            current_url=None,     # URL 없음
        )
        
        assert request.product_name == "Apple 2025 아이패드 프로 11(M5 모델) 스탠다드 글래스"
        assert request.current_price is None
        assert request.current_url is None
    
    def test_request_with_name_and_price(self):
        """상품명 + 현재가격으로 요청"""
        request = PriceSearchRequest(
            product_name="Apple 2025 아이패드 프로 11(M5 모델) 스탠다드 글래스",
            current_price=1517000,
        )
        
        assert request.product_name == "Apple 2025 아이패드 프로 11(M5 모델) 스탠다드 글래스"
        assert request.current_price == 1517000
    
    # ========== 검색 결과 시나리오 ==========
    
    def test_search_result_found_cheaper(self):
        """다나와에서 더 저렴한 가격 발견"""
        # 시뮬레이션: 다나와 최저가 1,299,000원 (현재가 1,517,000원보다 저쌈)
        result = SearchResult(
            product_url="https://prod.danawa.com/info/?pcode=9876543",
            price=1299000,  # 더 저씀
            product_name="Apple 2025 아이패드 프로 11(M5) 스탠다드",
            source="fastpath",
            elapsed_ms=234.5,
        )
        
        current_price = 1517000
        is_cheaper = result.price < current_price
        price_diff = current_price - result.price
        
        assert result.is_success is True
        assert is_cheaper is True
        assert price_diff == 218000  # 218,000원 절약 가능
    
    def test_search_result_same_price(self):
        """다나와 가격이 현재 가격과 동일"""
        result = SearchResult(
            product_url="https://prod.danawa.com/info/?pcode=9876543",
            price=1517000,
            product_name="Apple 2025 아이패드 프로 11(M5) 스탠다드",
            source="fastpath",
            elapsed_ms=200.0,
        )
        
        current_price = 1517000
        is_cheaper = result.price < current_price
        
        assert is_cheaper is False
    
    def test_search_result_more_expensive(self):
        """다나와 가격이 현재 가격보다 비쌈"""
        result = SearchResult(
            product_url="https://prod.danawa.com/info/?pcode=9876543",
            price=1599000,  # 더 비쌈
            product_name="Apple 2025 아이패드 프로 11(M5) 스탠다드",
            source="fastpath",
            elapsed_ms=200.0,
        )
        
        current_price = 1517000
        is_cheaper = result.price < current_price
        
        assert is_cheaper is False
    
    # ========== 에러 시나리오 ==========
    
    def test_search_product_not_found(self):
        """상품을 찾을 수 없음"""
        result = SearchResult(
            product_url=None,
            price=None,
            product_name=None,
            source="none",
            elapsed_ms=3000.0,
        )
        
        assert result.is_success is False
        assert result.status == SearchStatus.NOT_FOUND
    
    def test_search_timeout(self):
        """검색 타임아웃 (12초 초과)"""
        result = SearchResult(
            product_url=None,
            price=None,
            product_name=None,
            source="none",
            elapsed_ms=12000.0,
            status=SearchStatus.TIMEOUT,
        )
        
        assert result.is_success is False
        assert result.status == SearchStatus.TIMEOUT
    
    def test_search_blocked_by_danawa(self):
        """다나와 봇 차단"""
        result = SearchResult(
            product_url=None,
            price=None,
            product_name=None,
            source="none",
            elapsed_ms=500.0,
            status=SearchStatus.BLOCKED,
        )
        
        assert result.is_success is False
        assert result.status == SearchStatus.BLOCKED
    
    # ========== 응답 포맷팅 ==========
    
    def test_response_success_with_cheaper_price(self):
        """성공 응답: 더 저렴한 가격 발견"""
        request = PriceSearchRequest(
            product_name="Apple 2025 아이패드 프로 11(M5 모델)",
            current_price=1517000,
        )
        
        # 검색 결과
        search_result = SearchResult(
            product_url="https://prod.danawa.com/info/?pcode=9876543",
            price=1299000,
            product_name="Apple 2025 아이패드 프로 11(M5)",
            source="fastpath",
            elapsed_ms=234.5,
        )
        
        # 응답 생성
        lowest_price = search_result.price if search_result.price is not None else 0
        is_cheaper = lowest_price < request.current_price if request.current_price else False
        price_diff = request.current_price - lowest_price if request.current_price and is_cheaper else 0
        
        response = PriceSearchResponse(
            status="success",
            message=f"다나와에서 {price_diff:,}원 저렴한 가격 발견!",
            error_code=None,
            data=PriceData(
                product_name=request.product_name,
                is_cheaper=is_cheaper,
                price_diff=price_diff,
                lowest_price=lowest_price,
                link=search_result.product_url or "",
                mall="다나와",
                free_shipping=None,
                source=search_result.source or "unknown",
                elapsed_ms=search_result.elapsed_ms or 0.0,
            ),
        )
        
        assert response.status == "success"
        assert response.data is not None
        assert response.data.is_cheaper is True
        assert response.data.price_diff == 218000
    
    def test_response_not_found(self):
        """실패 응답: 상품을 찾을 수 없음"""
        request = PriceSearchRequest(
            product_name="존재하지 않는 상품명 xyzabc123",
            current_price=100000,
        )
        
        response = PriceSearchResponse(
            status="error",
            message="입력하신 상품을 다나와에서 찾을 수 없습니다.",
            error_code="PRODUCT_NOT_FOUND",
            data=None,
        )
        
        assert response.status == "error"
        assert response.data is None
        assert response.error_code == "PRODUCT_NOT_FOUND"
    
    def test_response_timeout(self):
        """실패 응답: 검색 타임아웃"""
        response = PriceSearchResponse(
            status="error",
            message="검색 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
            error_code="TIMEOUT",
            data=None,
        )
        
        assert response.status == "error"
        assert response.error_code == "TIMEOUT"
    
    # ========== 엣지 케이스 ==========
    
    def test_response_with_none_values(self):
        """None 값 처리 (safe_* 메서드 검증)"""
        search_result = SearchResult(
            product_url=None,  # None 값
            price=None,
            product_name=None,
            source=None,
            elapsed_ms=None,
        )
        
        # safe_* 메서드로 안전하게 처리
        lowest_price = EdgeCaseHandler.safe_int(
            search_result.price, default=0, min_val=0, max_val=10**9
        )
        link = EdgeCaseHandler.safe_str(search_result.product_url, default="")
        source = EdgeCaseHandler.safe_str(search_result.source, default="unknown")
        elapsed_ms = EdgeCaseHandler.safe_get(
            {"elapsed_ms": search_result.elapsed_ms},
            "elapsed_ms",
            default=0.0,
        )
        
        assert lowest_price == 0
        assert link == ""
        assert source == "unknown"
        assert elapsed_ms == 0.0
    
    def test_price_validation_range(self):
        """가격 범위 검증"""
        # 정상 범위
        valid_prices = [1, 100, 1000000, 10**9]
        for price in valid_prices:
            validated = EdgeCaseHandler.safe_int(
                price, min_val=0, max_val=10**9
            )
            assert validated == price
        
        # 범위 초과
        invalid_prices = [-1, 0, 10**10]
        for price in invalid_prices:
            # 음수와 0은 범위 밖, 10**10은 최대값 초과
            if price < 0 or price > 10**9:
                result = EdgeCaseHandler.safe_int(
                    price, default=0, min_val=0, max_val=10**9
                )
                assert result == 0
    
    def test_product_name_normalization(self):
        """상품명 정규화"""
        # 입력: 사용자가 입력한 상품명
        product_name = "Apple 2025 아이패드 프로 11(M5 모델) 스탠다드 글래스"
        
        # 검증: Pydantic이 자동으로 처리
        request = PriceSearchRequest(product_name=product_name)
        
        # 정규화된 상품명
        assert request.product_name == product_name
        assert len(request.product_name) <= 500
        assert any(c in request.product_name for c in ['<', '>', '"', "'"])is False
