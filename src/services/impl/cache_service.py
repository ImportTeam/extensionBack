"""Redis 캐시 서비스 - 캐싱 로직만 담당"""
import json
from typing import Optional
from urllib.parse import urlparse, urlunparse

from redis import Redis

from src.core.config import settings
from src.core.logging import logger
from src.core.exceptions import (
    CacheConnectionException,
    CacheSerializationException,
)
from src.schemas.price_schema import CachedPrice
from src.utils.hash_utils import generate_cache_key, generate_negative_cache_key


class CacheService:
    """Redis 캐시 관리 서비스"""

    @staticmethod
    def _resolve_redis_url(redis_url: str) -> str:
        """Upstash 같은 TLS 전용 Redis는 rediss://로 보정한다."""
        parsed = urlparse(redis_url)
        if parsed.scheme == "redis" and parsed.hostname and parsed.hostname.endswith("upstash.io"):
            return urlunparse(parsed._replace(scheme="rediss"))
        return redis_url
    
    def __init__(self):
        """Redis 클라이언트 초기화"""
        self.redis_client = None
        try:
            redis_url = self._resolve_redis_url(settings.redis_url)
            self.redis_client = Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 연결 테스트
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
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
                try:
                    data = json.loads(cached_data)
                    return CachedPrice(**data)
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    # Corrupted or schema-mismatched cache - delete and treat as miss
                    logger.warning(f"Cache data deserialization failed: {type(e).__name__}: {e}")
                    try:
                        self.redis_client.delete(cache_key)
                        logger.info(f"Deleted corrupted cache for key: {cache_key}")
                    except Exception:
                        pass
                    return None
            
            logger.info(f"Cache miss for key: {cache_key}")
            return None
            
        except Exception as e:
            # Cache errors should not break the request - treat as miss
            logger.warning(f"Cache read error (treating as miss): {type(e).__name__}: {e}")
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
            try:
                cached_value = json.dumps(price_data, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to serialize cache data: {e}")
                raise CacheSerializationException(
                    operation="write",
                    reason="Failed to serialize cache data",
                    details={"error": str(e)}
                )
            
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
            
        except CacheSerializationException:
            raise
        except Exception as e:
            logger.error(f"Cache write error: {e}")
            raise CacheConnectionException(
                reason="Failed to write cache",
                details={"error": str(e)}
            )

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

    def get_failure_count(self, product_name: str) -> int:
        """🔴 반복 실패 횟수 조회 (Hard Skip 판단용)
        
        Returns:
            N번 연속 실패 카운트
        """
        try:
            cache_key = f"{generate_negative_cache_key(product_name)}:fail_count"
            count = self.redis_client.get(cache_key)
            return int(count) if count else 0
        except Exception:
            return 0

    def increment_failure_count(self, product_name: str, max_count: int = 3) -> int:
        """🔴 실패 카운트 증가 (N번 실패하면 Hard Skip)
        
        Args:
            product_name: 상품명
            max_count: Hard Skip 임계값 (기본 3회)
            
        Returns:
            현재 실패 카운트
        """
        try:
            cache_key = f"{generate_negative_cache_key(product_name)}:fail_count"
            current_count = self.redis_client.incr(cache_key)
            # TTL = 부정 캐시 TTL의 2배 (충분한 관찰 기간)
            self.redis_client.expire(cache_key, 120)
            logger.warning(f"[Failure] {product_name}: fail_count={current_count}/{max_count}")
            return int(current_count)
        except Exception as e:
            logger.error(f"Failed to increment failure count: {e}")
            return 1

    def reset_failure_count(self, product_name: str) -> bool:
        """🟢 실패 카운트 초기화 (성공 시)"""
        try:
            cache_key = f"{generate_negative_cache_key(product_name)}:fail_count"
            result = self.redis_client.delete(cache_key)
            return result > 0
        except Exception:
            return False

    def should_hard_skip(self, product_name: str, max_failures: int = 3) -> bool:
        """🔴 Hard Skip 판정 (N번 연속 실패 → 즉시 거절)
        
        Returns:
            True → 이 쿼리는 이미 N번 실패했으므로 즉시 ProductNotFoundException 반환
        """
        failure_count = self.get_failure_count(product_name)
        if failure_count >= max_failures:
            logger.warning(f"[Hard Skip] {product_name}: fail_count={failure_count} >= {max_failures}")
            return True
        return False

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
