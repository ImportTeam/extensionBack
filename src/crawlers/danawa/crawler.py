"""다나와 크롤러 - 웹 스크래핑만 담당

NOTE: 파일이 커지는 문제를 줄이기 위해 아래 모듈로 분리되었습니다.
- src/crawlers/danawa/metrics/ : Circuit Breaker + Metrics
- src/crawlers/danawa/boundary/ : HTTP Fast Path + Timeout Manager
- src/crawlers/danawa/playwright/ : Playwright 관리
- src/crawlers/danawa/orchestrator.py : 오케스트레이션 로직
"""

from __future__ import annotations

import asyncio
import random
from typing import Dict, List, Optional

from playwright.async_api import Browser, Page

from src.core.config import settings
from src.core.logging import logger

from src.crawlers.danawa.boundary import (
    DanawaHttpFastPath,
    TimeoutManager,
    FastPathNoResults,
    FastPathProductFetchFailed,
)
from src.crawlers.danawa.metrics import CircuitBreaker
from src.crawlers.danawa.playwright import (
    ensure_shared_browser,
    new_page as _new_page,
    shutdown_shared_browser as _shutdown_pw,
    warmup as _warmup_pw,
    configure_page,
)

from .orchestrator import search_lowest_price as _search_lowest_price


class DanawaCrawler:
    """다나워 크롤러 - SRP: 웹 스크래핑만 담당"""

    # Playwright 동시성 제한 (서버 보호)
    _browser_sema: Optional[asyncio.Semaphore] = None

    # Circuit Breaker (HTTP Fast Path 모니터링)
    _circuit_breaker: Optional[CircuitBreaker] = None

    def __init__(self) -> None:
        self.browser: Optional[Browser] = None
        self.search_url = "https://search.danawa.com/dsearch.php"
        self.product_url = "https://prod.danawa.com/info/"
        self._http = DanawaHttpFastPath()

    @classmethod
    def _get_circuit_breaker(cls) -> CircuitBreaker:
        """Circuit Breaker 싱글톤 반환."""
        if cls._circuit_breaker is None:
            threshold = getattr(settings, "crawler_fastpath_fail_threshold", 5)
            open_duration = getattr(settings, "crawler_fastpath_open_seconds", 60.0)
            cls._circuit_breaker = CircuitBreaker(fail_threshold=threshold, open_duration_sec=open_duration)
        return cls._circuit_breaker

    @classmethod
    def _get_browser_semaphore(cls) -> asyncio.Semaphore:
        if cls._browser_sema is None:
            cls._browser_sema = asyncio.Semaphore(getattr(settings, "crawler_browser_concurrency", 2))
        return cls._browser_sema

    @classmethod
    async def _acquire_browser_semaphore_with_timeout(cls, timeout: float) -> bool:
        """세마포어를 타임아웃으로 획득 시도 후 결과 반환 (True=획득)."""
        sem = cls._get_browser_semaphore()
        try:
            await asyncio.wait_for(sem.acquire(), timeout=timeout)
            return True
        except Exception:
            return False

    @classmethod
    def _release_browser_semaphore(cls) -> None:
        sem = cls._get_browser_semaphore()
        try:
            sem.release()
        except Exception:
            pass

    @classmethod
    async def shutdown_shared_browser(cls) -> None:
        """프로세스 종료 시 공유 브라우저를 정리합니다."""
        await _shutdown_pw()

    @classmethod
    async def warmup(cls) -> None:
        """앱 시작 시 브라우저/컨텍스트를 미리 준비해 첫 요청 지연을 줄입니다."""
        await _warmup_pw()

    async def __aenter__(self) -> "DanawaCrawler":
        """Context manager 진입 - 브라우저 시작"""
        # Fast Path(HTTP) 성공 시 Playwright 자체가 필요 없으므로 lazy-init 합니다.
        self.browser = None
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager 종료 - 브라우저 종료"""
        # 공유 브라우저는 재사용하므로 여기서 닫지 않습니다.
        # 프로세스 종료 시 shutdown_shared_browser()에서 정리합니다.
        return

    async def _rate_limit(self) -> None:
        """Rate limiting - 요청 간격 조절"""
        delay = random.uniform(
            settings.crawler_rate_limit_min,
            settings.crawler_rate_limit_max
        )
        await asyncio.sleep(delay)
        logger.debug(f"Rate limit delay: {delay:.2f}s")

    async def _create_page(self) -> Page:
        """새 페이지 생성 및 설정"""
        _pw, browser, _ctx = await ensure_shared_browser()
        self.browser = browser
        page = await _new_page()
        return await configure_page(page)

    async def search_lowest_price(self, product_name: str, product_code: Optional[str] = None) -> Optional[Dict]:
        return await _search_lowest_price(self, product_name=product_name, product_code=product_code)

    @property
    def metrics(self):
        """Circuit Breaker의 메트릭 반환."""
        return self._get_circuit_breaker().metrics

    def get_status(self) -> Dict:
        """크롤러 상태 반환."""
        cb = self._get_circuit_breaker()
        return {
            "circuit_breaker": {
                "status": "OPEN" if cb.is_open() else "CLOSED",
                "fail_count": cb._fail_count,
                "threshold": cb.fail_threshold,
            },
            "metrics": {
                "fastpath_hits": cb.metrics.fastpath_hits,
                "fastpath_misses": cb.metrics.fastpath_misses,
                "playwright_hits": cb.metrics.playwright_hits,
                "playwright_failures": cb.metrics.playwright_failures,
                "fastpath_success_rate": cb.metrics.fastpath_success_rate,
                "playwright_success_rate": cb.metrics.playwright_success_rate,
            },
        }

