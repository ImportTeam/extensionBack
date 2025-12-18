"""Pydantic 스키마 테스트."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.schemas.price_schema import CachedPrice, PriceData, PriceSearchResponse


def test_price_data_creation():
    """PriceData 생성."""
    price = PriceData(
        product_name="테스트 상품",
        is_cheaper=True,
        price_diff=-5000,
        lowest_price=45000,
        link="https://example.com",
        source="fastpath",
        elapsed_ms=234.5,
    )
    
    assert price.lowest_price == 45000
    assert price.source == "fastpath"
    assert price.is_cheaper is True


def test_price_search_response():
    """PriceSearchResponse 생성."""
    price_data = PriceData(
        product_name="상품",
        is_cheaper=False,
        price_diff=0,
        lowest_price=50000,
        link="https://example.com",
        source="cache",
        elapsed_ms=100.0,
    )
    
    response = PriceSearchResponse(
        status="success",
        data=price_data,
        message="완료",
        error_code=None,
    )
    
    assert response.status == "success"
    assert response.data.lowest_price == 50000


def test_price_search_response_error():
    """오류 응답."""
    response = PriceSearchResponse(
        status="error",
        data=None,
        message="타임아웃",
        error_code="TIMEOUT",
    )
    
    assert response.status == "error"
    assert response.error_code == "TIMEOUT"


def test_cached_price_creation():
    """CachedPrice 생성."""
    cached = CachedPrice(
        product_name="캐시된 상품",
        lowest_price=42000,
        product_url="https://example.com/product",
        source="cache",
        updated_at=datetime.now().isoformat(),
    )
    
    assert cached.product_name == "캐시된 상품"
    assert cached.lowest_price == 42000
    assert cached.source == "cache"


def test_cached_price_json():
    """CachedPrice JSON 직렬화."""
    cached = CachedPrice(
        product_name="JSON 테스트",
        lowest_price=55000,
        product_url="https://example.com",
        source="fastpath",
        updated_at=datetime.now().isoformat(),
    )
    
    json_str = cached.model_dump_json()
    assert "55000" in json_str
    assert "product_url" in json_str
    
    dict_data = cached.model_dump()
    assert dict_data["lowest_price"] == 55000


def test_price_data_with_optional_fields():
    """선택 필드 포함."""
    price = PriceData(
        product_name="전체 필드",
        is_cheaper=True,
        price_diff=-10000,
        lowest_price=40000,
        link="https://example.com",
        source="slowpath",
        elapsed_ms=1000.0,
        mall="쇼핑몰",
        free_shipping=True,
    )
    
    assert price.mall == "쇼핑몰"
    assert price.free_shipping is True
