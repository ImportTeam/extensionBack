"""CacheAdapter 단위 테스트."""

from __future__ import annotations

import pytest

from src.engine.cache_adapter import CacheAdapter
from src.schemas.price_schema import CachedPrice


@pytest.fixture
def cache_adapter():
    """CacheAdapter 인스턴스."""
    return CacheAdapter()


def test_cache_adapter_to_dict():
    """CachedPrice → dict 변환."""
    from datetime import datetime
    
    cached = CachedPrice(
        product_name="다나와 모니터",
        lowest_price=45000,
        product_url="https://example.com/product",
        source="cache",
        updated_at=datetime.now().isoformat(),
    )
    
    adapter = CacheAdapter()
    result = adapter.to_dict(cached)
    
    assert isinstance(result, dict)
    assert result["lowest_price"] == 45000
    assert result["product_url"] == "https://example.com/product"
    assert result["source"] == "cache"


def test_cache_adapter_from_dict():
    """dict → CachedPrice 변환."""
    from datetime import datetime
    
    data = {
        "product_name": "검색 상품",
        "lowest_price": 48000,
        "product_url": "https://example.com/item",
        "source": "fastpath",
        "updated_at": datetime.now().isoformat(),
    }
    
    adapter = CacheAdapter()
    cached = adapter.from_dict(data)
    
    assert isinstance(cached, CachedPrice)
    assert cached.lowest_price == 48000
    assert cached.product_url == "https://example.com/item"
    assert cached.source == "fastpath"


def test_cache_adapter_round_trip():
    from datetime import datetime
    
    original = CachedPrice(
        product_name="왕복 테스트",
        lowest_price=50000,
        product_url="https://example.com/roundtrip",
        source="slowpath",
        updated_at=datetime.now().isoformat(),
    )
    
    adapter = CacheAdapter()
    
    # CachedPrice → dict
    dict_data = adapter.to_dict(original)
    
    # dict → CachedPrice
    restored = adapter.from_dict(dict_data)
    
    assert restored.lowest_price == original.lowest_price
    assert restored.product_url == original.product_url
    assert restored.product_name == original.product_nam
    assert restored.product_code == original.product_code
    assert restored.source == original.source


def test_cache_adapter_attribute_names():
    from datetime import datetime
    
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
    # 구식 속성명이 없어야 함 (url 대신 product_url)
    assert not hasattr(cached, "url")
    assert not hasattr(cached, "price")

from datetime import datetime
    
    cached = CachedPrice(
        product_name="캐시 테스트",
        lowest_price=42000,
        product_url="https://example.com/product",
        source="cache",
        updated_at=datetime.now().isoformat()ttps://example.com/product",
        product_code="K11111111",
        currency="KRW",
        source="cache",
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
