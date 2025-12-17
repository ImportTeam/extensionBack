"""헬스 체크 엔드포인트"""
from fastapi import APIRouter, Depends
from datetime import datetime

from src.schemas.price_schema import HealthResponse
from src.services.impl.cache_service import CacheService
from src.api.routes.price_routes import get_cache_service
from src.core.database import engine
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
    # Redis 체크
    redis_ok = cache_service.health_check()
    
    # DB 체크
    try:
        with engine.connect():
            db_ok = True
    except Exception:
        db_ok = False
    
    status = "ok" if redis_ok and db_ok else "degraded"
    
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
