"""공유 HTTP 클라이언트 (curl_cffi)

- Fast Path에서 요청마다 AsyncSession을 만들면 TLS/커넥션 오버헤드가 커져서
  타임아웃/지연이 악화될 수 있어 프로세스 단위로 세션을 재사용합니다.
- 앱 종료 시 close()로 정리합니다.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Dict

from curl_cffi.requests import AsyncSession

from src.core.config import settings
from src.core.logging import logger


class SharedHttpClient:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._session: Optional[AsyncSession] = None

    async def _ensure_session(self) -> AsyncSession:
        async with self._lock:
            if self._session is not None:
                return self._session
            self._session = AsyncSession(
                impersonate=settings.crawler_http_impersonate,
                headers=self.default_headers(),
                allow_redirects=True,
                max_clients=int(getattr(settings, "crawler_http_max_clients", 20)),
                trust_env=False,
            )
            return self._session

    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": settings.crawler_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.danawa.com/",
        }

    async def get_text(
        self,
        url: str,
        *,
        timeout_s: float,
        headers: Optional[Dict[str, str]] = None,
        follow_redirects: bool = True,
    ) -> Optional[tuple[int, str]]:
        sess = await self._ensure_session()
        try:
            resp = await sess.get(
                url,
                headers=headers,
                timeout=timeout_s,
                allow_redirects=follow_redirects,
            )
            status = getattr(resp, "status_code", 0) or 0
            text = getattr(resp, "text", "") or ""
            return status, text
        except Exception as e:
            logger.info(f"[HTTP_CLIENT] GET failed: {type(e).__name__}: {repr(e)}")
            return None

    async def head_status(self, url: str, *, timeout_s: float) -> Optional[int]:
        sess = await self._ensure_session()
        try:
            resp = await sess.head(url, timeout=timeout_s, allow_redirects=True)
            return getattr(resp, "status_code", None)
        except Exception as e:
            logger.info(f"[HTTP_CLIENT] HEAD failed: {type(e).__name__}: {repr(e)}")
            return None

    async def close(self) -> None:
        async with self._lock:
            if self._session is None:
                return
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None


_shared_http_client = SharedHttpClient()


def get_shared_http_client() -> SharedHttpClient:
    return _shared_http_client


async def shutdown_shared_http_client() -> None:
    await _shared_http_client.close()
