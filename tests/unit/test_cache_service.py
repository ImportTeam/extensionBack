"""캐시 서비스 유닛 테스트 (Mock 사용)"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services import CacheService
from src.schemas.price_schema import CachedPrice
from src.core.exceptions import CacheException


class TestCacheService:
    """캐시 서비스 테스트"""
    
    @patch('src.services.impl.cache_service.Redis')
    def test_init_success(self, mock_redis):
        """Redis 연결 성공"""
        mock_redis.from_url.return_value.ping.return_value = True
        
        service = CacheService()
        assert service.redis_client is not None
        mock_redis.from_url.return_value.ping.assert_called_once()
    
    @patch('src.services.impl.cache_service.Redis')
    def test_init_failure(self, mock_redis):
        """Redis 연결 실패"""
        mock_redis.from_url.return_value.ping.side_effect = Exception("Connection failed")
        
        with pytest.raises(CacheException):
            CacheService()
    
    @patch('src.services.impl.cache_service.Redis')
    def test_get_cache_hit(self, mock_redis):
        """캐시 히트"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = '{"product_name": "테스트", "lowest_price": 100000, "link": "http://test.com", "source": "danawa", "mall": "G마켓", "free_shipping": true, "top_prices": [{"rank":1,"mall":"G마켓","price":100000,"free_shipping":true,"delivery":"무료배송","link":"http://test.com"}], "price_trend": [{"label":"1개월","price":100000}], "updated_at": "2024-01-01T00:00:00"}'
        mock_redis.from_url.return_value = mock_client
        
        service = CacheService()
        result = service.get("테스트 상품")
        
        assert result is not None
        assert isinstance(result, CachedPrice)
        assert result.lowest_price == 100000
    
    @patch('src.services.impl.cache_service.Redis')
    def test_get_cache_miss(self, mock_redis):
        """캐시 미스"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = None
        mock_redis.from_url.return_value = mock_client
        
        service = CacheService()
        result = service.get("존재하지 않는 상품")
        
        assert result is None
    
    @patch('src.services.impl.cache_service.Redis')
    def test_set_cache(self, mock_redis):
        """캐시 저장"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.from_url.return_value = mock_client
        
        service = CacheService()
        price_data = {
            "product_name": "테스트",
            "lowest_price": 100000,
            "link": "http://test.com",
            "source": "danawa",
            "mall": "G마켓",
            "free_shipping": True,
            "top_prices": [
                {"rank": 1, "mall": "G마켓", "price": 100000, "free_shipping": True, "delivery": "무료배송", "link": "http://test.com"}
            ],
            "price_trend": [
                {"label": "1개월", "price": 100000}
            ],
            "updated_at": "2024-01-01T00:00:00"
        }
        
        result = service.set("테스트 상품", price_data)
        
        assert result is True
        mock_client.setex.assert_called_once()
    
    @patch('src.services.impl.cache_service.Redis')
    def test_delete_cache(self, mock_redis):
        """캐시 삭제"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.delete.return_value = 1
        mock_redis.from_url.return_value = mock_client
        
        service = CacheService()
        result = service.delete("테스트 상품")
        
        assert result is True
        mock_client.delete.assert_called_once()
    
    @patch('src.services.impl.cache_service.Redis')
    def test_health_check(self, mock_redis):
        """헬스 체크"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.from_url.return_value = mock_client
        
        service = CacheService()
        assert service.health_check() is True

    @patch('src.services.impl.cache_service.Redis')
    def test_negative_cache(self, mock_redis):
        """부정 캐시(get_negative/set_negative)"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = '{"message": "No products found"}'
        mock_redis.from_url.return_value = mock_client

        service = CacheService()
        msg = service.get_negative("존재하지않는상품123")
        assert msg == "No products found"

        ok = service.set_negative("존재하지않는상품123", "No products found", ttl_seconds=60)
        assert ok is True
        mock_client.setex.assert_called()
