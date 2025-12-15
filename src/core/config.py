"""설정 관리 - 환경 변수 로드 및 검증"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 데이터베이스
    database_url: str = ""
    
    # Redis
    redis_url: str = ""
    cache_ttl: int = 21600  # 6시간
    
    # 크롤러
    crawler_timeout: int = 30000
    crawler_user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    crawler_max_retries: int = 3
    crawler_rate_limit_min: float = 0.5
    crawler_rate_limit_max: float = 1.5

    # 하이브리드(HTTP Fast Path → Playwright Fallback) 성능 설정
    crawler_total_budget_ms: int = 6000
    crawler_http_timeout_ms: int = 5000
    crawler_http_impersonate: str = "chrome110"
    crawler_http_max_clients: int = 20
    crawler_enable_price_trend: bool = False

    # Playwright 동시성 제한(서버 터짐 방지)
    crawler_browser_concurrency: int = 2

    # Fast Path 회로차단(CB): 연속 실패 시 잠깐 Fast Path 스킵
    crawler_fastpath_fail_threshold: int = 5
    crawler_fastpath_open_seconds: int = 60

    # Fast Path HTML 검증(캐시 오염 방지)
    crawler_fastpath_min_html_length: int = 5000
    
    # API
    api_title: str = "최저가 탐지 서비스"
    api_version: str = "1.0.0"
    api_description: str = "Cache-First 전략으로 최저가를 빠르게 검색합니다."
    
    # 로깅
    log_level: str = "INFO"
    
    @field_validator("cache_ttl")
    @classmethod
    def validate_cache_ttl(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("cache_ttl must be positive")
        return v
    
    @field_validator("crawler_timeout")
    @classmethod
    def validate_crawler_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("crawler_timeout must be positive")
        return v

    @field_validator("crawler_total_budget_ms", "crawler_http_timeout_ms")
    @classmethod
    def validate_crawler_budgets(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("crawler budgets must be positive")
        return v

    @field_validator("crawler_browser_concurrency")
    @classmethod
    def validate_crawler_concurrency(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("crawler_browser_concurrency must be positive")
        return v

    @field_validator("database_url", "redis_url")
    @classmethod
    def validate_required_urls(cls, v: str) -> str:
        if not v:
            raise ValueError("database_url and redis_url must not be empty")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
