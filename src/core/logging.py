"""로깅 설정 (Security Enhanced)"""
import logging
import sys
import os
from src.core.config import settings


# Production 환경에서는 DEBUG 로그 비활성화
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"


def setup_logging() -> logging.Logger:
    """로거 초기화 및 설정"""
    
    logger = logging.getLogger("price_detector")
    
    # Production에서는 최소 INFO 레벨
    log_level = settings.log_level.upper()
    if IS_PRODUCTION and log_level == "DEBUG":
        log_level = "INFO"
    
    logger.setLevel(getattr(logging, log_level))
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    
    # 포맷터 (민감 정보 제외)
    if IS_PRODUCTION:
        # Production: 최소 정보만
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        # Development: 상세 정보
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    console_handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(console_handler)
    
    return logger


logger = setup_logging()


def sanitize_for_log(value: str, max_length: int = 100) -> str:
    """민감 정보 제거 후 로깅용 문자열 반환
    
    Args:
        value: 로깅할 문자열
        max_length: 최대 길이
        
    Returns:
        제거된 문자열
    """
    if not value:
        return "[empty]"
    
    # 민감한 패턴 마스킹
    patterns_to_mask = [
        ('password', '***'),
        ('token', '***'),
        ('api_key', '***'),
        ('secret', '***'),
    ]
    
    result = value
    for pattern, mask in patterns_to_mask:
        if pattern.lower() in result.lower():
            result = mask
            break
    
    # 길이 초과 시 절단
    if len(result) > max_length:
        result = result[:max_length] + "..."
    
    return result
