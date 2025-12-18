"""CacheAdapter 단위 테스트."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.engine.cache_adapter import CacheAdapter
from src.schemas.price_schema import CachedPrice


@pytest.fixture
def cache_adapter():
    """CacheAdapter 인스턴스."""
    return CacheAdapter()


@pytest.mark.asyncio
async def test_cache_adapter_get_hit():
    """캐시 히트 케이스."""
    mock_cache_service = MagicMock()
    cached = CachedPrice(
        product_name="캐시된 상품",
        lowest_price=45000,
        product_url="https://example.com/product",
        source="cache",
        updated_at=datetime.now().isoformat(),
    )
    mock_cache_service.get = MagicMock(return_value=cached)
    
    adapter = CacheAdapter(cache_service=mock_cache_service)
    result = await adapter.get("캐시된 상품")
    
    assert result is not None
    assert isinstance(result, dict)
    assert result["product_url"] == "https://example.com/product"
    assert result["price"] == 45000


@pytest.mark.asyncio
async def test_cache_adapter_get_miss():
    """캐시 미스 케이스."""
    mock_cache_service = MagicMock()
    mock_cache_service.get = MagicMock(return_value=None)
    
    adapter = CacheAdapter(cache_service=mock_cache_service)
    result = await adapter.get("없는 상품")
    
    assert result is None


@pytest.mark.asyncio
async def test_cache_adapter_set():
    """캐시 저장."""
    mock_cache_service = MagicMock()
    mock_cache_service.set = MagicMock(return_value=True)
    
    adapter = CacheAdapter(cache_service=mock_cache_service)
    
    data = {
        "product_url": "https://example.com/product",
        "price": 50000,
        "product_name": "테스트 상품",
    }
    
    result = await adapter.set("테스트 상품", data, ttl=3600)
    
    # set은 None 반환
    assert result is None
    mock_cache_service.set.assert_called_once()


def test_cached_price_schema():
    """CachedPrice Pydantic 모델 검증."""
    cached = CachedPrice(
        product_name="캐시 테스트",
        lowest_price=42000,
        product_url="https://example.com/product",
        source="cache",
        updated_at=datetime.now().isoformat(),
    )
    
    # JSON 직렬화 가능성
    json_str = cached.model_dump_json()
    assert isinstance(json_str, str)
    assert "42000" in json_str
    assert "product_url" in json_str
    
    # dict 변환
    dict_data = cached.model_dump()
    assert dict_data["lowest_price"] == 42000
    assert dict_data["source"] == "cache"


def test_cached_price_attribute_names():
    """CachedPrice 속성명 일관성."""
    cached = CachedPrice(
        product_name="테스트",
        lowest_price=45000,
        product_url="https://example.com",
        source="cache",
        updated_at=datetime.now().isoformat(),
    )
    
    # 속성 접근 가능성
    assert hasattr(cached, "lowest_price")
    assert hasattr(cached, "product_url")
    assert hasattr(cached, "product_name")
    
    # 구식 속성명이 없어야 함
    assert not hasattr(cached, "url")
    assert not hasattr(cached, "price")

