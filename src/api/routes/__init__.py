"""API routes package."""

from .health_routes import router as health_router
from .price_routes import router as price_router, get_cache_service
from .analytics_routes import analytics_router

__all__ = ["health_router", "price_router", "analytics_router", "get_cache_service"]
