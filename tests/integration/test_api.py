"""API 통합 테스트"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock

# App factory 사용
from src.app import create_app
from src.api.price_routes import get_price_service

app = create_app()


@pytest.mark.asyncio
class TestHealthAPI:
    """헬스 체크 API 테스트"""
    
    async def test_health_check(self) -> None:
        """헬스 체크 엔드포인트"""
        with patch('src.api.health_routes.get_cache_service') as mock_cache, \
             patch('src.api.health_routes.engine') as mock_engine:
            
            # Mock 설정
            mock_cache_service = MagicMock()
            mock_cache_service.health_check.return_value = True
            mock_cache.return_value = mock_cache_service
            
            mock_engine.connect.return_value.__enter__.return_value = True
            
            async with AsyncClient(app=app, base_url="http://testserver") as client:
                response = await client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "timestamp" in data
            assert "version" in data
    
    async def test_root_endpoint(self) -> None:
        """루트 엔드포인트"""
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data


@pytest.mark.asyncio
class TestPriceSearchAPI:
    """가격 검색 API 테스트"""
    
    async def test_search_price_cache_hit(self) -> None:
        """캐시 히트 시나리오"""
        mock_price_service = AsyncMock()
        mock_price_service.search_price.return_value = {
            "lowest_price": 100000,
            "link": "https://prod.danawa.com/info/?pcode=12345",
            "is_cheaper": True,
            "price_diff": -50000,
            "status": "HIT",
            "message": "캐시에서 발견했습니다."
        }
        mock_price_service.log_search = AsyncMock()
        
        app.dependency_overrides[get_price_service] = lambda: mock_price_service
        
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/price/search",
                json={
                    "product_name": "아이폰 15 프로",
                    "current_price": 150000
                }
            )
        
        app.dependency_overrides.clear()
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["lowest_price"] == 100000
        assert data["data"]["is_cheaper"] is True
    
    async def test_search_price_cache_miss(self) -> None:
        """캐시 미스 후 크롤링 시나리오"""
        mock_price_service = AsyncMock()
        mock_price_service.search_price.return_value = {
            "lowest_price": 120000,
            "link": "https://prod.danawa.com/info/?pcode=67890",
            "is_cheaper": True,
            "price_diff": -30000,
            "status": "MISS",
            "message": "다나와에서 새로 검색했습니다."
        }
        mock_price_service.log_search = AsyncMock()
        
        app.dependency_overrides[get_price_service] = lambda: mock_price_service
        
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/price/search",
                json={
                    "product_name": "삼성 갤럭시 S24",
                    "current_price": 150000
                }
            )
        
        app.dependency_overrides.clear()
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["lowest_price"] == 120000
    
    async def test_search_price_not_found(self) -> None:
        """상품을 찾을 수 없는 경우"""
        with patch('src.api.price_routes.get_price_service') as mock_service:
            mock_price_service = AsyncMock()
            mock_price_service.search_price.return_value = {
                "lowest_price": 0,
                "link": "",
                "is_cheaper": False,
                "price_diff": 0,
                "status": "FAIL",
                "message": "검색 결과를 찾을 수 없습니다."
            }
            mock_price_service.log_search = AsyncMock()
            mock_service.return_value = mock_price_service
            
            async with AsyncClient(app=app, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/price/search",
                    json={
                        "product_name": "존재하지않는상품12345"
                    }
                )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "fail"
            assert data["data"] is None
    
    async def test_search_price_invalid_request(self) -> None:
        """잘못된 요청"""
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/price/search",
                json={}
            )
        
        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
class TestStatisticsAPI:
    """통계 API 테스트"""
    
    async def test_get_statistics(self) -> None:
        """통계 조회"""
        with patch('src.api.price_routes.SearchLogRepository') as mock_repo:
            # Mock 리포지토리 설정
            mock_repo_instance = MagicMock()
            mock_repo_instance.get_total_count.return_value = 100
            mock_repo_instance.get_cache_hit_count.return_value = 70
            
            # Mock 인기 검색어
            from collections import namedtuple
            PopularQuery = namedtuple('PopularQuery', ['query_name', 'count'])
            mock_repo_instance.get_popular_queries.return_value = [
                PopularQuery(query_name="아이폰 15", count=20),
                PopularQuery(query_name="삼성 갤럭시", count=15)
            ]
            
            mock_repo.return_value = mock_repo_instance
            
            async with AsyncClient(app=app, base_url="http://testserver") as client:
                response = await client.get("/api/v1/stats")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_searches"] == 100
            assert data["cache_hits"] == 70
            assert data["hit_rate"] == 70.0
            assert len(data["popular_queries"]) == 2
