"""Cache Adapter - Enhanced Type Safety Version"""

from typing import Optional, Dict, Any, Union
from asyncio import TimeoutError as AsyncTimeoutError

from src.core.logging import logger
from src.services.impl.cache_service import CacheService


class CacheAdapter:
    """Cache 서비스 어댑터 (타입 안전 버전)

    기존 CacheService를 SearchOrchestrator가 기대하는 인터페이스로 변환합니다.
    모든 메서드에 완전한 타입 힌트 및 예외 처리 추가.
    """

    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Args:
            cache_service: CacheService 인스턴스 (없으면 내부 생성)
            
        Raises:
            ValueError: cache_service가 None인 경우
        """
        if cache_service is None:
            self.cache_service = CacheService()
        else:
            self.cache_service = cache_service

    async def get(self, query: str, timeout: float = 0.2) -> Optional[Dict[str, Any]]:
        """캐시 조회

        Args:
            query: 검색어
            timeout: 타임아웃 (초) - CacheService는 동기이므로 무시

        Returns:
            dict or None: 캐시된 데이터
                {
                    "product_url": str,
                    "price": int,
                    "product_name": Optional[str],
                    "mall": Optional[str],
                    "free_shipping": Optional[bool],
                }

        Raises:
            None: 모든 예외는 로깅되고 None 반환
        """
        try:
            if not query or not isinstance(query, str):
                logger.warning(f"Invalid query for cache.get: {query}")
                return None
            
            cached = self.cache_service.get(query)
            if not cached:
                return None
            
            # Type conversion
            result: Dict[str, Any] = {
                "product_url": cached.product_url,
                "price": int(cached.lowest_price),
                "product_name": cached.product_name,
                "mall": cached.mall,
                "free_shipping": cached.free_shipping,
            }
            
            # Validation
            if not result["product_url"] or result["price"] <= 0:
                logger.warning(f"Invalid cache data: {result}")
                return None
            
            return result
        
        except AsyncTimeoutError as e:
            logger.warning(f"Cache get timeout: {e}")
            return None
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(f"Cache data deserialization failed: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {type(e).__name__}: {e}")
            return None

    async def set(self, query: str, data: Dict[str, Any], ttl: int = 21600) -> None:
        """캐시 저장

        Args:
            query: 검색어
            data: 저장할 데이터
                {
                    "product_url": str,
                    "price": int,
                    "product_name": Optional[str],
                }
            ttl: TTL (초)

        Raises:
            None: 모든 예외는 로깅됨
        """
        try:
            if not query or not isinstance(query, str):
                logger.warning(f"Invalid query for cache.set: {query}")
                return
            
            if not data or not isinstance(data, dict):
                logger.warning(f"Invalid data for cache.set: {data}")
                return
            
            # Validation
            product_url = data.get("product_url")
            price = data.get("price")
            product_name = data.get("product_name")
            
            if not product_url or not isinstance(product_url, str):
                logger.warning(f"Missing or invalid product_url in cache data")
                return
            
            if price is None:
                logger.warning(f"Missing price in cache data")
                return
            
            try:
                price_int = int(price)
                if price_int <= 0:
                    logger.warning(f"Invalid price value: {price_int}")
                    return
            except (TypeError, ValueError) as e:
                logger.warning(f"Price is not a valid integer: {price}, error={e}")
                return
            
            # Build cache data
            price_data: Dict[str, Union[str, int]] = {
                "product_url": product_url,
                "price": price_int,
            }
            
            if product_name and isinstance(product_name, str):
                price_data["product_name"] = product_name
            
            # CacheService는 동기이므로 직접 호출
            self.cache_service.set(query, price_data)
        
        except AsyncTimeoutError as e:
            logger.warning(f"Cache set timeout: {e}")
        except Exception as e:
            logger.warning(f"Cache set failed: {type(e).__name__}: {e}")
