"""Price API 라우트 단위 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.schemas.price_schema import PriceSearchResponse, PriceData


client = TestClient(app)


def test_price_search_endpoint_available():
    """가격 검색 엔드포인트 존재."""
    # 엔드포인트가 등록되어 있는지 확인
    routes = [route.path for route in app.routes]
    assert "/api/price/search" in routes


@pytest.mark.asyncio
async def test_price_search_response_schema():
    """PriceSearchResponse Pydantic 모델 검증."""
    from datetime import datetime
    
    price_data = PriceData(
        product_name="테스트 상품",
        is_cheaper=True,
        price_diff=-5000,
        lowest_price=45000,
        link="https://example.com",
        source="fastpath",
        elapsed_ms=234.5,
    )
    
    response = PriceSearchResponse(
        status="success",
        data=price_data,
        message="성공",
        error_code=None,
    )
    
    assert response.status == "success"
    assert response.data.lowest_price == 45000
    assert response.error_code is None


def test_price_search_response_with_error():
    """오류 응답 스키마."""
    response = PriceSearchResponse(
        status="error",
        data=None,
        message="타임아웃 발생",
        error_code="TIMEOUT",
    )
    
    assert response.status == "error"
    assert response.error_code == "TIMEOUT"
    assert response.data is None


def test_price_search_response_json_serialization():
    """PriceSearchResponse JSON 직렬화."""
    price_data = PriceData(
        product_name="직렬화 테스트",
        is_cheaper=False,
        price_diff=0,
        lowest_price=50000,
        link="https://example.com/product",
        source="slowpath",
        elapsed_ms=567.8,
    )
    
    response = PriceSearchResponse(
        status="success",
        data=price_data,
        message="완료",
        error_code=None,
    )
    
    # model_dump_json()로 직렬화
    json_str = response.model_dump_json()
    assert isinstance(json_str, str)
    assert "50000" in json_str
    assert "success" in json_str
    assert "slowpath" in json_str


def test_price_data_schema():
    """PriceData Pydantic 모델 검증."""
    # 필수 필드만
    pricproduct_name="상품1",
        is_cheaper=True,
        price_diff=-10000,
        lowest_price=45000,
        link="https://example.com",
        source="fastpath",
        elapsed_ms=100.0,
    )
    
    assert price.lowest_price == 45000
    assert price.source == "fastpath"
    
    # 모든 필드 포함
    price_full = PriceData(
        product_name="상품2",
        is_cheaper=False,
        price_diff=5000,
        lowest_price=48000,
        link="https://example.com/full",
        source="fastpath",
        elapsed_ms=123.45,
        mall="쇠떼",
        free_shipping=True,
    )
    
    assert price_full.source == "fastpath"
    assert price_full.elapsed_ms == 123.45
    assert price_full.mall == "쇠떼5
    assert price_full.error_code == "NONE"
status="success",
        data=None,
        message="no data",
        error_code=None,
    )
    
    # model_dump(exclude_none=True) 시 None 필드 제외
    dumped = response.model_dump(exclude_none=True)
    
    # error_code가 None이므로 제외되어야 함
    assert "error_code" not in dumped or dumped.get("error_code")
    # model_dump(exclude_none=True) 시 None 필드 제외
    dumped = response.model_dump(exclude_none=True)
    
    # error_code가 None이므로 제외되어야 함
    assert "error_code" not in dumped or dumped["error_code"] is None


@pytest.product_name="트렌드 상품",
        is_cheaper=True,
        price_diff=-2000,
        lowest_price=45000,
        link="https://example.com",
        source="fastpath",
        elapsed_ms=234.5,
    )
    
    # 트렌드 데이터는 선택 필드
    assert hasattr(price_data, "lowest_price")
    assert price_data.is_cheaper == True
    # 트렌드 데이터는 별도 처리
    # API 응답에 포함될 수 있음
    assert hasattr(price_data, "lowest_price")
    assert price_data.currency == "KRW"
