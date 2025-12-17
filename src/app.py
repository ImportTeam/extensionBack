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
    # 기본 정책: HTTP Fast Path 먼저, Playwright는 실패 시에만 lazy-launch
    # 필요하면 env로 crawler_playwright_warmup=true 설정하여 warmup 가능
    if getattr(settings, "crawler_playwright_warmup", False):
        try:
            from src.crawlers.danawa import DanawaCrawler

            await DanawaCrawler.warmup()
        except Exception:
            # 워밍업 실패가 앱 시작을 막지 않도록 무시
            pass
    logger.info("Application started")
    yield
    logger.info("Shutting down application...")
    try:
        from src.crawlers.danawa import DanawaCrawler
        from src.crawlers.http_client import shutdown_shared_http_client

        await DanawaCrawler.shutdown_shared_browser()
        await shutdown_shared_http_client()
    except Exception:
        # 종료 훅에서의 예외는 앱 종료를 막지 않도록 무시
        pass


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

# 앱 인스턴스 생성 (uvicorn이 로드할 수 있도록)
app = create_app()