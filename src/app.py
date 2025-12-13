"""FastAPI 앱 팩토리"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.core.config import settings
from src.core.database import init_db
from src.core.logging import logger
from src.api import health_routes, price_routes
from src.routes import analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기"""
    logger.info("Starting application...")
    init_db()
    logger.info("Application started")
    yield
    logger.info("Shutting down application...")


def create_app() -> FastAPI:
    """
    FastAPI 앱 생성 (Factory Pattern)
    
    Returns:
        FastAPI 앱 인스턴스
    """
    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        lifespan=lifespan
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 라우터 등록
    app.include_router(health_routes.router)
    app.include_router(price_routes.router)
    app.include_router(analytics_router.router)
    
    return app
