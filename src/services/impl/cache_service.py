"""Redis 캐시 서비스 - 캐싱 로직만 담당"""
import json
from typing import Optional
from redis import Redis

from src.core.config import settings
from src.core.logging import logger
from src.core.exceptions import CacheException
from src.schemas.price_schema import CachedPrice
from src.utils.hash import generate_cache_key, generate_negative_cache_key


class CacheService:
    """Redis 캐시 관리 서비스"""
    
    def __init__(self):
        """Redis 클라이언트 초기화"""
        try:
            self.redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 연결 테스트
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise CacheException(f"Redis connection failed: {e}")
    
    def get(self, product_name: str) -> Optional[CachedPrice]:
        """
        캐시된 가격 정보 조회
        
        Args:
            product_name: 상품명
            
        Returns:
            CachedPrice 객체 또는 None
        """
        try:
            cache_key = generate_cache_key(product_name)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                logger.info(f"Cache hit for key: {cache_key}")
                data = json.loads(cached_data)
                return CachedPrice(**data)
            
            logger.info(f"Cache miss for key: {cache_key}")
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode cached data: {e}")
            return None
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None
    
    def set(self, product_name: str, price_data: dict) -> bool:
        """
        가격 정보 캐싱
        
        Args:
            product_name: 상품명
            price_data: 저장할 가격 데이터
            
        Returns:
            성공 여부
        """
        try:
            cache_key = generate_cache_key(product_name)
            cached_value = json.dumps(price_data, ensure_ascii=False)
            
            self.redis_client.setex(
                cache_key,
                settings.cache_ttl,
                cached_value
            )

            # 저장 확인용 TTL 로그 (운영 디버깅 도움)
            try:
                ttl = self.redis_client.ttl(cache_key)
            except Exception:
                ttl = settings.cache_ttl
            logger.info(f"Cache set for key: {cache_key}, TTL: {ttl}s")
            return True
            
        except Exception as e:
            logger.error(f"Cache write error: {e}")
            raise CacheException(f"Failed to write cache: {e}")

    def get_negative(self, product_name: str) -> Optional[str]:
        """최근 '검색 실패'를 짧게 캐시한 경우 메시지를 반환"""
        try:
            cache_key = generate_negative_cache_key(product_name)
            cached_data = self.redis_client.get(cache_key)
            if not cached_data:
                return None
            data = json.loads(cached_data)
            msg = data.get("message")
            return msg if isinstance(msg, str) and msg else None
        except Exception:
            return None

    def set_negative(self, product_name: str, message: str, ttl_seconds: int = 60) -> bool:
        """검색 실패(미발견) 결과를 짧게 캐시하여 과도한 재시도를 완화"""
        try:
            cache_key = generate_negative_cache_key(product_name)
            payload = json.dumps({"message": message}, ensure_ascii=False)
            self.redis_client.setex(cache_key, ttl_seconds, payload)
            logger.info(f"Negative cache set for key: {cache_key}, TTL: {ttl_seconds}s")
            return True
        except Exception as e:
            logger.error(f"Negative cache write error: {e}")
            return False

    def delete_negative(self, product_name: str) -> bool:
        """부정 캐시 삭제"""
        try:
            cache_key = generate_negative_cache_key(product_name)
            result = self.redis_client.delete(cache_key)
            return result > 0
        except Exception:
            return False
    
    def delete(self, product_name: str) -> bool:
        """
        캐시 삭제
        
        Args:
            product_name: 상품명
            
        Returns:
            성공 여부
        """
        try:
            cache_key = generate_cache_key(product_name)
            result = self.redis_client.delete(cache_key)
            logger.info(f"Cache deleted for key: {cache_key}")
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def health_check(self) -> bool:
        """Redis 연결 상태 확인"""
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
