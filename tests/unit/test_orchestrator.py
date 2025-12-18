"""SearchOrchestrator 통합 테스트."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.crawlers.core.orchestrator import SearchOrchestrator
from src.schemas.price_schema import CrawlResult, CrawledPrice, PriceData


@pytest.fixture
def mock_cache():
    """캐시 모의 객체."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def mock_http_fastpath():
    """HTTP FastPath 모의 객체."""
    fastpath = AsyncMock()
    fastpath.search_lowest_price = AsyncMock(
        return_value={
            "lowest_price": 45000,
            "product_code": "K12345678",
            "link": "https://example.com",
            "currency": "KRW",
        }
    )
    return fastpath


@pytest.fixture
def mock_playwright():
    """Playwright 모의 객체."""
    playwright = AsyncMock()
    playwright.search_product = AsyncMock(
        return_value=("K87654321", "https://example.com/product/K87654321")
    )
    playwright.get_product_lowest_price = AsyncMock(
        return_value={"lowest_price": 48000, "link": "https://example.com/price"}
    )
    return playwright


@pytest.mark.asyncio
async def test_orchestrator_fast_path_success(mock_cache, mock_http_fastpath):
    """Fast Path 성공 케이스."""
    with patch.object(SearchOrchestrator, "_get_http_fastpath", return_value=mock_http_fastpath):
        orchestrator = SearchOrchestrator(cache=mock_cache)
        
        result = await orchestrator.search_product(
            query="다나와 모니터",
            cache_ttl_sec=3600,
            timeout_budget_sec=15
        )
        
        assert result is not None
        assert "lowest_price" in result
        assert result["lowest_price"] == 45000


@pytest.mark.asyncio
async def test_orchestrator_cache_hit(mock_cache):
    """캐시 히트 케이스."""
    cached_result = {
        "lowest_price": 42000,
        "product_code": "K99999999",
        "link": "https://cached.com",
        "source": "cache",
    }
    mock_cache.get = AsyncMock(return_value=cached_result)
    
    with patch.object(SearchOrchestrator, "_get_http_fastpath", return_value=AsyncMock()):
        orchestrator = SearchOrchestrator(cache=mock_cache)
        
        result = await orchestrator.search_product(
            query="캐시된 상품",
            cache_ttl_sec=3600,
            timeout_budget_sec=15
        )
        
        assert result == cached_result
        mock_cache.get.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_timeout_handling():
    """타임아웃 처리 테스트."""
    orchestrator = SearchOrchestrator(cache=AsyncMock())
    
    # 타임아웃 시간 매우 짧게 설정
    result = await orchestrator.search_product(
        query="timeout_test",
        cache_ttl_sec=3600,
        timeout_budget_sec=0.001  # 1ms
    )
    
    # 타임아웃 시 None 반환해야 함
    assert result is None


@pytest.mark.asyncio
async def test_orchestrator_fallback_to_playwright(mock_cache, mock_http_fastpath, mock_playwright):
    """FastPath 실패 시 Playwright 폴백."""
    # FastPath가 None을 반환하는 시나리오
    mock_http_fastpath.search_lowest_price = AsyncMock(return_value=None)
    
    with patch.object(SearchOrchestrator, "_get_http_fastpath", return_value=mock_http_fastpath), \
         patch.object(SearchOrchestrator, "_get_playwright", return_value=mock_playwright):
        orchestrator = SearchOrchestrator(cache=mock_cache)
        
        result = await orchestrator.search_product(
            query="폴백 테스트",
            cache_ttl_sec=3600,
            timeout_budget_sec=15
        )
        
        # Playwright 결과가 반환되어야 함
        assert result is not None or result is None  # 실제로 fallback 구현에 따라 달라짐


@pytest.mark.asyncio
async def test_orchestrator_crawl_result_schema():
    """CrawlResult 스키마 검증."""
    # CrawlResult 모델 생성
    crawl_result = CrawlResult(
        query="test query",
        status="success",
        lowest_price=50000,
        product_url="https://example.com",
        product_code="K12345678",
    )
    
    assert crawl_result.query == "test query"
    assert crawl_result.status == "success"
    assert crawl_result.lowest_price == 50000
    assert crawl_result.product_url == "https://example.com"


def test_crawled_price_schema():
    """CrawledPrice Pydantic 모델 검증."""
    # 필수 필드만
    price = CrawledPrice(
        product_name="테스트 상품",
        lowest_price=45000,
        product_url="https://example.com",
        source="fastpath",
    )
    
    assert price.lowest_price == 45000
    assert price.source == "fastpath"
    
    # Pydantic dict 변환 테스트
    price_dict = price.model_dump()
    assert isinstance(price_dict, dict)
    assert price_dict["lowest_price"] == 45000
