"""다나와 Playwright 공용 브라우저/컨텍스트 관리.

DanawaCrawler에서 브라우저 관리 코드를 분리해 파일 크기를 줄이고,
워밍업/정리/재시도를 한 곳에서 다룹니다.
"""

from __future__ import annotations

import asyncio
import platform
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from src.core.config import settings
from src.core.logging import logger
from src.core.exceptions import BrowserException


_shared_lock = asyncio.Lock()
_shared_playwright: Optional[Playwright] = None
_shared_browser: Optional[Browser] = None
_shared_context: Optional[BrowserContext] = None


def build_launch_args() -> list[str]:
    args: list[str] = [
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-default-apps",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    if platform.system().lower() == "linux":
        args.extend(["--no-sandbox", "--disable-setuid-sandbox"])

    deduped: list[str] = []
    seen: set[str] = set()
    for a in args:
        if a not in seen:
            seen.add(a)
            deduped.append(a)
    return deduped


async def ensure_shared_browser() -> tuple[Playwright | None, Browser, BrowserContext]:
    global _shared_playwright, _shared_browser, _shared_context

    async with _shared_lock:
        if _shared_browser is not None:
            try:
                if _shared_browser.is_connected() and _shared_context is not None:
                    return _shared_playwright, _shared_browser, _shared_context
            except Exception:
                pass

        # cleanup
        if _shared_context is not None:
            try:
                await _shared_context.close()
            except Exception:
                pass
            _shared_context = None

        if _shared_browser is not None:
            try:
                await _shared_browser.close()
            except Exception:
                pass
            _shared_browser = None

        if _shared_playwright is not None:
            try:
                await _shared_playwright.stop()
            except Exception:
                pass
            _shared_playwright = None

        last_err: Optional[Exception] = None
        for attempt in range(1, max(1, settings.crawler_max_retries) + 1):
            try:
                logger.info(f"[Playwright] Launching browser (attempt {attempt}/{settings.crawler_max_retries})...")
                pw = await asyncio.wait_for(
                    async_playwright().start(),
                    timeout=20.0,  # Playwright 시작에 최대 20초
                )
                
                browser = await asyncio.wait_for(
                    pw.chromium.launch(
                        headless=True,
                        args=build_launch_args(),
                        timeout=settings.crawler_timeout,
                    ),
                    timeout=25.0,  # 브라우저 론칭에 최대 25초
                )

                context = await browser.new_context(
                    user_agent=settings.crawler_user_agent,
                    locale="ko-KR",
                    extra_http_headers={
                        "Referer": "https://www.danawa.com/",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                    },
                )

                _shared_playwright = pw
                _shared_browser = browser
                _shared_context = context
                logger.info("[Playwright] Browser launched successfully (shared)")
                return pw, browser, context
            except asyncio.TimeoutError as e:
                last_err = e
                logger.error(f"[Playwright] Launch timeout (attempt {attempt}/{settings.crawler_max_retries}): {type(e).__name__}")
                try:
                    if _shared_browser is not None:
                        await _shared_browser.close()
                except Exception:
                    pass
                _shared_browser = None
                try:
                    if _shared_playwright is not None:
                        await _shared_playwright.stop()
                except Exception:
                    pass
                _shared_playwright = None
                _shared_context = None
                wait_time = min(2.0 * attempt, 10.0)  # 최대 10초까지 지수적 증가
                logger.info(f"[Playwright] Waiting {wait_time:.1f}s before retry...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                last_err = e
                logger.error(f"[Playwright] Failed to launch browser (attempt {attempt}/{settings.crawler_max_retries}): {type(e).__name__}: {e}")
                try:
                    if _shared_browser is not None:
                        await _shared_browser.close()
                except Exception:
                    pass
                _shared_browser = None
                try:
                    if _shared_playwright is not None:
                        await _shared_playwright.stop()
                except Exception:
                    pass
                _shared_playwright = None
                _shared_context = None
                wait_time = min(2.0 * attempt, 10.0)
                logger.info(f"[Playwright] Waiting {wait_time:.1f}s before retry...")
                await asyncio.sleep(wait_time)

        raise BrowserException(f"[Playwright] Browser launch failed after retries: {last_err}")


async def shutdown_shared_browser() -> None:
    global _shared_playwright, _shared_browser, _shared_context

    async with _shared_lock:
        if _shared_context is not None:
            try:
                await _shared_context.close()
            except Exception:
                pass
            _shared_context = None
        if _shared_browser is not None:
            try:
                await _shared_browser.close()
            except Exception:
                pass
            _shared_browser = None
        if _shared_playwright is not None:
            try:
                await _shared_playwright.stop()
            except Exception:
                pass
            _shared_playwright = None


async def warmup() -> None:
    await ensure_shared_browser()


async def new_page():
    _pw, browser, context = await ensure_shared_browser()
    return await (context.new_page() if context is not None else browser.new_page())
