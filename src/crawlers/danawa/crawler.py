"""다나와 크롤러 - 웹 스크래핑만 담당

NOTE: 파일이 커지는 문제를 줄이기 위해 Playwright 브라우저/페이지 설정과
HTTP Fast Path 구현은 `src/crawlers/danawa/` 하위 모듈로 분리되었습니다.
"""

from __future__ import annotations

import asyncio
import random
from typing import Dict, List, Optional

from playwright.async_api import Browser, Page

from src.core.config import settings
from src.core.logging import logger

from src.crawlers.danawa.http_fastpath import DanawaHttpFastPath
from src.crawlers.danawa.playwright_browser import (
    ensure_shared_browser,
    new_page as _new_page,
    shutdown_shared_browser as _shutdown_pw,
    warmup as _warmup_pw,
)
from src.crawlers.danawa.playwright_pages import configure_page

from .detail import get_product_lowest_price
from .orchestrator import search_lowest_price as _search_lowest_price
from .price_trend import extract_price_trend
from .search import search_product


class DanawaCrawler:
    """다나와 크롤러 - SRP: 웹 스크래핑만 담당"""

    # 공유 브라우저는 `src/crawlers/danawa/playwright_browser.py`에서 관리

    # Playwright 동시성 제한 (서버 보호)
    _browser_sema: Optional[asyncio.Semaphore] = None

    # Fast Path 회로차단(CB)
    _fastpath_fail_count: int = 0
    _fastpath_open_until: float = 0.0
    # Usage metrics
    _metrics_fastpath_hits: int = 0
    _metrics_fastpath_misses: int = 0
    _metrics_playwright_hits: int = 0
    _metrics_playwright_failures: int = 0

    def __init__(self) -> None:
        self.browser: Optional[Browser] = None
        self.search_url = "https://search.danawa.com/dsearch.php"
        self.product_url = "https://prod.danawa.com/info/"
        self._http = DanawaHttpFastPath()

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
    def _metric_fastpath_hit(cls) -> None:
        cls._metrics_fastpath_hits += 1

    @classmethod
    def _metric_fastpath_miss(cls) -> None:
        cls._metrics_fastpath_misses += 1

    @classmethod
    def _metric_playwright_hit(cls) -> None:
        cls._metrics_playwright_hits += 1

    @classmethod
    def _metric_playwright_failure(cls) -> None:
        cls._metrics_playwright_failures += 1

    @classmethod
    def _fastpath_is_open(cls) -> bool:
        return asyncio.get_running_loop().time() < cls._fastpath_open_until

    @classmethod
    def _fastpath_on_fail(cls) -> None:
        cls._fastpath_fail_count += 1
        threshold = getattr(settings, "crawler_fastpath_fail_threshold", 5)
        if cls._fastpath_fail_count >= threshold:
            open_seconds = getattr(settings, "crawler_fastpath_open_seconds", 60)
            cls._fastpath_open_until = asyncio.get_running_loop().time() + float(open_seconds)
            cls._fastpath_fail_count = 0

    @classmethod
    def _fastpath_on_success(cls) -> None:
        cls._fastpath_fail_count = 0
        cls._fastpath_open_until = 0.0

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

    async def _search_product(self, search_query: str) -> Optional[str]:
        return await search_product(self._create_page, self.search_url, search_query)

    async def _get_product_lowest_price(
        self,
        page: Page,
        product_code: str,
        search_query: str,
    ) -> Optional[Dict]:
        return await get_product_lowest_price(
            page=page,
            product_url_base=self.product_url,
            product_code=product_code,
            search_query=search_query,
        )

    async def _extract_price_trend(self, page: Page) -> list[Dict]:
        return await extract_price_trend(page)
