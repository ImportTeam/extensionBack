"""Cache Adapter - Adapts CacheService to Engine's expected interface

Provides a thin wrapper around the existing CacheService to match
the interface expected by SearchOrchestrator.
"""

from typing import Optional

from src.core.logging import logger
from src.services.impl.cache_service import CacheService


class CacheAdapter:
    """Cache 서비스 어댑터

    기존 CacheService를 SearchOrchestrator가 기대하는 인터페이스로 변환합니다.

    기존 CacheService:
        - get(product_name) -> CachedPrice or None
        - set(product_name, price_data) -> bool

    Engine 기대 인터페이스:
        - get(query, timeout=0.2) -> dict or None
        - set(query, data, ttl=21600) -> None
    """

    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Args:
            cache_service: CacheService 인스턴스 (없으면 내부 생성)
        """
        self.cache_service = cache_service or CacheService()

    async def get(self, query: str, timeout: float = 0.2) -> Optional[dict]:
        """캐시 조회

        Args:
            query: 검색어
            timeout: 타임아웃 (초) - CacheService는 동기이므로 무시

        Returns:
            dict or None: 캐시된 데이터
                - product_url or url: 상품 URL
                - price: 가격
        """
        try:
            cached = self.cache_service.get(query)
            if cached:
                # CachedPrice -> dict 변환
                return {
                    "product_url": cached.product_url,
                    "price": cached.lowest_price,
                    "product_name": cached.product_name,
                    "mall": cached.mall,
                    "free_shipping": cached.free_shipping,
                }
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    async def set(self, query: str, data: dict, ttl: int = 21600) -> None:
        """캐시 저장

        Args:
            query: 검색어
            data: 저장할 데이터
                - product_url or url: 상품 URL
                - price: 가격
            ttl: TTL (초)
        """
        try:
            # dict -> CacheService 형식 변환
            price_data = {
                "url": data.get("product_url") or data.get("url"),
                "price": data.get("price"),
            }
            self.cache_service.set(query, price_data)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
