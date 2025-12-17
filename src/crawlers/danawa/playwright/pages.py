"""다나와 Playwright page 설정/보조 함수.

Page 생성 후 라우팅(리소스 차단), 헤더 설정 등 공통 설정을 분리합니다.
"""

from __future__ import annotations

from playwright.async_api import Page

from src.core.config import settings


async def configure_page(page: Page) -> Page:
    page.set_default_timeout(settings.crawler_timeout)

    async def _route_handler(route, request):
        try:
            if request.resource_type in {"image", "media", "font", "stylesheet"}:
                try:
                    await route.abort()
                except Exception:
                    return
                return
            url = (request.url or "").lower()
            if any(
                url.endswith(ext)
                for ext in (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".webp",
                    ".svg",
                    ".woff",
                    ".woff2",
                    ".ttf",
                    ".css",
                )
            ):
                try:
                    await route.abort()
                except Exception:
                    return
                return
        except Exception:
            return

        try:
            await route.continue_()
        except Exception:
            return

    try:
        await page.route("**/*", _route_handler)
    except Exception:
        pass

    await page.set_extra_http_headers(
        {
            "User-Agent": settings.crawler_user_agent,
            "Referer": "https://www.danawa.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )

    return page
