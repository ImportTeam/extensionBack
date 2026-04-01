"""설정 관리 - 환경 변수 로드 및 검증"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)


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
    # NOTE: 기본값은 '안정성 우선'으로 여유있게 설정합니다.
    # - crawler_http_timeout_ms: HTTP fast path 전체 예산 (10초)
    # - crawler_http_request_timeout_ms: HTTP 단일 요청 타임아웃(검색 페이지 등)
    #   → 다나와는 1~2MB 페이지를 5~7초에 로드하므로 7초로 설정
    # - crawler_http_product_timeout_ms: HTTP 상품 상세 페이지 타임아웃
    crawler_total_budget_ms: int = 9000
    crawler_http_timeout_ms: int = 8500
    crawler_http_request_timeout_ms: int = 2500
    crawler_http_product_timeout_ms: int = 3500
    crawler_http_impersonate: str = "chrome110"
    crawler_http_max_clients: int = 30
    crawler_enable_price_trend: bool = False
    crawler_http_max_search_candidates: int = 3
    crawler_http_max_pcodes_per_candidate: int = 3

    # Playwright 동시성 제한(서버 터짐 방지)
    crawler_browser_concurrency: int = 2

    # SlowPath 백엔드 선택
    # - playwright: 기존 Playwright 기반 SlowPath
    # - disabled: 브라우저 기반 폴백 비활성화(저메모리 환경용)
    # - drissionpage: (옵션) DrissionPage 기반 SlowPath (의존성 설치 필요)
    crawler_slowpath_backend: str = "disabled"

    # 앱 시작 시 Playwright 브라우저를 미리 띄울지 여부
    # 기본값은 False: 요청에서 HTTP Fast Path가 실패할 때만 lazy-launch
    crawler_playwright_warmup: bool = False

    # Fast Path 회로차단(CB): 연속 실패 시 잠깐 Fast Path 스킵
    crawler_fastpath_fail_threshold: int = 5
    crawler_fastpath_open_seconds: int = 60

    # Fast Path HTML 검증(캐시 오염 방지)
    crawler_fastpath_min_html_length: int = 5000

    # Fast Path 파싱에서 너무 싼 가격(액세서리/오탐) 배제용 하한
    # 0이면 비활성화
    crawler_min_price_threshold: int = 0
    
    # API
    api_title: str = "최저가 탐지 서비스"
    api_version: str = "1.0.0"
    api_description: str = "Cache-First 전략으로 최저가를 빠르게 검색합니다."

    # FE(브라우저) 타임아웃보다 짧게 서버에서 하드 캡을 걸어
    # 요청이 매달린 채로 클라이언트에서 타임아웃되는 상황을 줄입니다.
    # 🔴 기가차드 수정: Playwright 폴백 고려하여 20초로 상향 (기존 14초)
    api_price_search_timeout_s: float = 11.0

    # Engine Orchestrator budget
    engine_total_budget_s: float = 10.0
    engine_cache_timeout_s: float = 0.3
    engine_fastpath_timeout_s: float = 8.5
    engine_slowpath_timeout_s: float = 0.2
    
    # 로깅
    log_level: str = "INFO"
    
    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if self.cache_ttl <= 0:
            raise ValueError("cache_ttl must be positive")
        if self.crawler_timeout <= 0:
            raise ValueError("crawler_timeout must be positive")
        if self.crawler_min_price_threshold < 0:
            raise ValueError("crawler_min_price_threshold must be >= 0")
        if self.crawler_total_budget_ms <= 0 or self.crawler_http_timeout_ms <= 0:
            raise ValueError("crawler budgets must be positive")
        if self.crawler_http_request_timeout_ms <= 0 or self.crawler_http_product_timeout_ms <= 0:
            raise ValueError("crawler request/product budgets must be positive")
        if self.crawler_http_max_search_candidates <= 0 or self.crawler_http_max_pcodes_per_candidate <= 0:
            raise ValueError("crawler http candidate limits must be positive")
        if self.crawler_browser_concurrency <= 0:
            raise ValueError("crawler_browser_concurrency must be positive")
        if self.crawler_slowpath_backend not in {"playwright", "disabled", "drissionpage"}:
            raise ValueError("crawler_slowpath_backend must be one of ['disabled', 'drissionpage', 'playwright']")
        if not self.database_url or not self.redis_url:
            raise ValueError("database_url and redis_url must not be empty")

        engine_values = (
            self.engine_total_budget_s,
            self.engine_cache_timeout_s,
            self.engine_fastpath_timeout_s,
            self.engine_slowpath_timeout_s,
            self.api_price_search_timeout_s,
        )
        if any(value <= 0 for value in engine_values):
            raise ValueError("engine/api budgets must be positive")

        phase_sum = (
            self.engine_cache_timeout_s
            + self.engine_fastpath_timeout_s
            + self.engine_slowpath_timeout_s
        )
        if phase_sum > self.engine_total_budget_s:
            raise ValueError("engine phase budgets must not exceed engine_total_budget_s")

        return self
    
    class Config:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        case_sensitive = False


settings = Settings()
