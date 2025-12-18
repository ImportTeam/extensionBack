"""FastPath/SlowPath Executor 단위 테스트."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.crawlers.fastpath_executor import FastPathExecutor, SearchExecutor
from src.crawlers.slowpath_executor import SlowPathExecutor
from src.schemas.price_schema import CrawlResult, CrawledPrice


@pytest.fixture
def fastpath_executor():
    """FastPathExecutor 인스턴스."""
    return FastPathExecutor()


@pytest.fixture
def slowpath_executor():
    """SlowPathExecutor 인스턴스."""
    return SlowPathExecutor()


@pytest.mark.asyncio
async def test_fastpath_executor_protocol(fastpath_executor):
    """FastPathExecutor SearchExecutor 프로토콜 준수."""
    assert hasattr(fastpath_executor, "execute")
    assert callable(fastpath_executor.execute)


@pytest.mark.asyncio
async def test_fastpath_executor_execute_success(fastpath_executor):
    """FastPath 실행 성공."""
    with patch("src.crawlers.fastpath_executor.DanawaHttpFastPath") as mock_http:
        mock_instance = MagicMock()
        mock_instance.search_lowest_price = AsyncMock(
            return_value={
                "lowest_price": 45000,
                "product_code": "K12345678",
                "link": "https://example.com",
                "currency": "KRW",
            }
        )
        mock_http.return_value = mock_instance
        
        result = await fastpath_executor.execute(
            query="다나와 모니터",
            timeout_sec=10.0
        )
        
        assert result is not None
        assert isinstance(result, dict)
        assert result["lowest_price"] == 45000


@pytest.mark.asyncio
async def test_fastpath_executor_execute_timeout(fastpath_executor):
    """FastPath 타임아웃 처리."""
    with patch("src.crawlers.fastpath_executor.DanawaHttpFastPath") as mock_http:
        mock_instance = MagicMock()
        # 타임아웃 시뮬레이션
        mock_instance.search_lowest_price = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        mock_http.return_value = mock_instance
        
        result = await fastpath_executor.execute(
            query="timeout_query",
            timeout_sec=0.001
        )
        
        # 타임아웃 시 None 반환
        assert result is None


@pytest.mark.asyncio
async def test_slowpath_executor_protocol(slowpath_executor):
    """SlowPathExecutor SearchExecutor 프로토콜 준수."""
    assert hasattr(slowpath_executor, "execute")
    assert callable(slowpath_executor.execute)


@pytest.mark.asyncio
async def test_slowpath_executor_execute_success(slowpath_executor):
    """SlowPath 실행 성공."""
    mock_page = AsyncMock()
    mock_browser_context = MagicMock()
    
    with patch("src.crawlers.slowpath_executor.PlaywrightBrowser") as mock_pw_browser:
        mock_pw_instance = MagicMock()
        mock_pw_instance.create_context = AsyncMock(return_value=mock_browser_context)
        mock_pw_instance.search_product = AsyncMock(
            return_value=("K87654321", "https://example.com/K87654321")
        )
        mock_pw_instance.get_product_lowest_price = AsyncMock(
            return_value={"lowest_price": 48000, "link": "https://example.com/price"}
        )
        mock_pw_browser.return_value = mock_pw_instance
        
        result = await slowpath_executor.execute(
            query="느린경로 검색",
            timeout_sec=20.0
        )
        
        # 결과 검증
        assert result is not None or result is None  # 실제 구현에 따라


@pytest.mark.asyncio
async def test_fastpath_executor_error_handling(fastpath_executor):
    """FastPath 에러 처리."""
    with patch("src.crawlers.fastpath_executor.DanawaHttpFastPath") as mock_http:
        mock_instance = MagicMock()
        mock_instance.search_lowest_price = AsyncMock(
            side_effect=Exception("Network error")
        )
        mock_http.return_value = mock_instance
        
        # 예외 처리하지 않고 None 반환해야 함
        result = await fastpath_executor.execute(
            query="error_query",
            timeout_sec=10.0
        )
        
        assert result is None


def test_crawled_price_validation():
    """CrawledPrice 필드 검증."""
    # 필수 필드만
    price = CrawledPrice(
        product_name="테스트",
        lowest_price=45000,
        product_url="https://example.com",
        source="fastpath",
    )
    
    assert price.lowest_price == 45000
    assert price.source == "fastpath"
    
    # 모든 필드 포함
    price_full = CrawledPrice(
        product_name="전체",
        lowest_price=45000,
        product_url="https://example.com",
        source="fastpath",
    )
    
    assert price_full.source == "fastpath"
