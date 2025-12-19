"""헬스 체크 엔드포인트"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime

from src.schemas.price_schema import HealthResponse
from src.services.impl.cache_service import CacheService
from src.api.routes.price_routes import get_cache_service
from src.core.database import engine
from src.core.exceptions import (
    CacheConnectionException,
    DatabaseConnectionException,
)
from src.core.logging import logger
from src import __version__

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(cache_service: CacheService = Depends(get_cache_service)):
    """
    헬스 체크 엔드포인트
    
    - 서버 상태
    - Redis 연결 상태
    - DB 연결 상태
    """
    redis_ok = False
    db_ok = False
    
    # Redis 체크
    try:
        redis_ok = cache_service.health_check()
    except CacheConnectionException as e:
        logger.warning(f"Cache connection failed: {e.error_code}")
        redis_ok = False
    except Exception as e:
        logger.error(f"Unexpected cache error: {e}")
        redis_ok = False
    
    # DB 체크
    try:
        with engine.connect() as connection:
            # 간단한 쿼리로 연결 확인
            connection.exec_driver_sql("SELECT 1")
            db_ok = True
    except DatabaseConnectionException as e:
        logger.warning(f"Database connection failed: {e.error_code}")
        db_ok = False
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        db_ok = False
    
    status = "ok" if redis_ok and db_ok else ("degraded" if redis_ok or db_ok else "error")
    
    return HealthResponse(
        status=status,
        timestamp=datetime.now(),
        version=__version__
    )


@router.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "최저가 탐지 서비스",
        "version": __version__,
        "docs": "/docs"
    }

    try:
        redis_ok = cache_service.health_check()
    except CacheConnectionException as e:
        logger.warning(f"Cache connection failed: {e.error_code}")
        redis_ok = False
    except Exception as e:
        logger.error(f"Unexpected cache error: {e}")
        redis_ok = False
    
    # DB 체크
    try:
        with engine.connect() as connection:
            # 간단한 쿼리로 연결 확인
            connection.exec_driver_sql("SELECT 1")
            db_ok = True
    except DatabaseConnectionException as e:
        logger.warning(f"Database connection failed: {e.error_code}")
        db_ok = False
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        db_ok = False
    
    status = "ok" if redis_ok and db_ok else ("degraded" if redis_ok or db_ok else "error")
    
    return HealthResponse(
        status=status,
        timestamp=datetime.now(),
        version=__version__
    )


@router.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "최저가 탐지 서비스",
        "version": __version__,
        "docs": "/docs"
    }
