"""로깅 설정"""
import logging
import sys
from src.core.config import settings


def setup_logging() -> logging.Logger:
    """로거 초기화 및 설정"""
    
    logger = logging.getLogger("price_detector")
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # 포맷터
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


logger = setup_logging()
