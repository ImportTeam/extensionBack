"""엣지 케이스 처리 유틸리티"""
from typing import TypeVar, Optional, List, Dict, Any, Type
import functools
from src.core.logging import logger

T = TypeVar('T')


class EdgeCaseHandler:
    """엣지 케이스 처리 및 Null-safety 보장"""
    
    @staticmethod
    def safe_get(obj: Optional[Dict[str, Any]], key: str, 
                 default: Optional[T] = None, 
                 expected_type: Optional[Type] = None) -> Optional[T]:
        """딕셔너리 안전 접근
        
        Args:
            obj: 딕셔너리
            key: 키
            default: 기본값
            expected_type: 예상 타입
            
        Returns:
            값 또는 기본값
            
        Raises:
            TypeError: 타입 불일치
        """
        if obj is None:
            logger.debug(f"Attempting to access key '{key}' on None object")
            return default
        
        if not isinstance(obj, dict):
            logger.error(f"Expected dict but got {type(obj).__name__}")
            return default
        
        value: Any = obj.get(key, default)
        
        if value is not None and expected_type is not None:
            if not isinstance(value, expected_type):
                logger.warning(
                    f"Type mismatch for key '{key}': "
                    f"expected {expected_type.__name__} but got {type(value).__name__}"
                )
                return default
        
        return value  # type: ignore[no-any-return]
    
    @staticmethod
    def safe_int(value: Any, default: int = 0, min_val: Optional[int] = None, 
                 max_val: Optional[int] = None) -> int:
        """안전한 정수 변환
        
        Args:
            value: 변환할 값
            default: 변환 실패 시 기본값
            min_val: 최소값
            max_val: 최대값
            
        Returns:
            정수값
        """
        try:
            if value is None:
                logger.debug("Attempting to convert None to int")
                return default
            
            int_val = int(value)
            
            # Range checking
            if min_val is not None and int_val < min_val:
                logger.warning(f"Value {int_val} is below minimum {min_val}")
                return default
            
            if max_val is not None and int_val > max_val:
                logger.warning(f"Value {int_val} exceeds maximum {max_val}")
                return default
            
            return int_val
        
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert '{value}' to int: {e}")
            return default
    
    @staticmethod
    def safe_str(value: Any, default: str = "", max_length: Optional[int] = None) -> str:
        """안전한 문자열 변환
        
        Args:
            value: 변환할 값
            default: 변환 실패 시 기본값
            max_length: 최대 길이
            
        Returns:
            문자열
        """
        try:
            if value is None:
                return default
            
            str_val = str(value).strip()
            
            if not str_val:
                return default
            
            if max_length and len(str_val) > max_length:
                logger.warning(
                    f"String exceeds max length {max_length}: {len(str_val)} chars"
                )
                return str_val[:max_length]
            
            return str_val
        
        except Exception as e:
            logger.warning(f"Failed to convert '{value}' to str: {e}")
            return default
    
    @staticmethod
    def safe_list(value: Any, default: Optional[List] = None) -> List:
        """안전한 리스트 접근
        
        Args:
            value: 접근할 값
            default: 기본값
            
        Returns:
            리스트
        """
        if value is None:
            return default or []
        
        if isinstance(value, list):
            return value
        
        if isinstance(value, (tuple, set)):
            return list(value)
        
        logger.warning(f"Expected list but got {type(value).__name__}")
        return default or []
    
    @staticmethod
    def safe_index(lst: List, index: int, default: Optional[T] = None) -> Optional[T]:
        """안전한 리스트 인덱싱
        
        Args:
            lst: 리스트
            index: 인덱스
            default: 기본값
            
        Returns:
            요소 또는 기본값
        """
        if not isinstance(lst, list):
            logger.warning(f"Expected list but got {type(lst).__name__}")
            return default
        
        if not lst:
            logger.debug("Attempting to access index on empty list")
            return default
        
        try:
            if index < 0 or index >= len(lst):
                logger.debug(f"Index {index} out of range for list of length {len(lst)}")
                return default
            
            return lst[index]  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Error accessing list index {index}: {e}")
            return default
    
    @staticmethod
    def validate_non_empty(value: Optional[str], field_name: str = "field") -> str:
        """비어있지 않은 문자열 검증
        
        Args:
            value: 검증할 문자열
            field_name: 필드명 (로깅용)
            
        Returns:
            검증된 문자열
            
        Raises:
            ValueError: 값이 비어있거나 None인 경우
        """
        if not value or not value.strip():
            raise ValueError(f"{field_name} cannot be empty or None")
        return value.strip()
    
    @staticmethod
    def validate_positive(value: int, field_name: str = "value") -> int:
        """양수 검증
        
        Args:
            value: 검증할 정수
            field_name: 필드명 (로깅용)
            
        Returns:
            검증된 정수
            
        Raises:
            ValueError: 값이 0 이하인 경우
        """
        if value <= 0:
            raise ValueError(f"{field_name} must be positive (got {value})")
        return value
    
    @staticmethod
    def validate_non_negative(value: int, field_name: str = "value") -> int:
        """음이 아닌 정수 검증
        
        Args:
            value: 검증할 정수
            field_name: 필드명 (로깅용)
            
        Returns:
            검증된 정수
            
        Raises:
            ValueError: 값이 음수인 경우
        """
        if value < 0:
            raise ValueError(f"{field_name} must be non-negative (got {value})")
        return value


# 재시도 데코레이터
def retry_on_exception(max_attempts: int = 3, backoff_factor: float = 1.0):
    """재시도 데코레이터
    
    Args:
        max_attempts: 최대 시도 횟수
        backoff_factor: 지수 백오프 계수
    """
    import asyncio
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            last_exception: Optional[Exception] = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_attempts:
                        wait_time = backoff_factor ** (attempt - 1)
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed. Last error: {e}"
                        )
            
            if last_exception is not None:
                raise last_exception
            else:
                raise RuntimeError("Unexpected state: no exception recorded")
        
        return async_wrapper
    
    return decorator
