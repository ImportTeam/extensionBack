"""다나와 HTTP Fast Path (curl_cffi + HTML 파싱)

- 네트워크(fetch) 로직과 파싱 로직을 분리해 테스트/튜닝 포인트를 명확히 합니다.
"""

from __future__ import annotations

import asyncio
from typing import Optional, List
from urllib.parse import quote

from src.core.config import settings
from src.core.logging import logger
from src.crawlers.http_client import get_shared_http_client

from .http_fastpath_parsing import (
    is_probably_invalid_html,
    is_no_results_html,
    has_search_fingerprint,
    has_product_fingerprint,
    parse_search_pcandidates,
    parse_product_lowest_price,
)


class FastPathNoResults(Exception):
    """Fast Path에서 '검색 결과 없음'을 확인한 경우.

    이 경우는 네트워크/차단 실패가 아니므로 Playwright로 폴백하지 않도록
    상위 레이어에서 별도 처리하는 것이 바람직합니다.
    """


class DanawaHttpFastPath:
    """curl_cffi + selectolax 기반 Fast Path."""

    def __init__(self) -> None:
        self.search_url = "https://search.danawa.com/dsearch.php"
        self.product_url = "https://prod.danawa.com/info/"

    async def _fetch_html(self, url: str, timeout_ms: int) -> Optional[str]:
        timeout_s = max(0.2, timeout_ms / 1000.0)

        try:
            logger.info(f"[FAST_PATH_HTTP] Fetching {url[:80]}... (timeout={timeout_s:.1f}s)")
            client = get_shared_http_client()
            res = await client.get_text(url, timeout_s=timeout_s)
            if not res:
                return None
            status, html = res
            if status != 200:
                logger.info(f"[FAST_PATH_HTTP] Non-200 status: {status}")
                return None
            if not html or is_probably_invalid_html(html):
                logger.info(f"[FAST_PATH_HTTP] Blocked or invalid HTML (len={len(html) if html else 0})")
                return None
            logger.info(f"[FAST_PATH_HTTP] OK (len={len(html)})")
            return html
        except Exception as e:
            logger.info(f"[FAST_PATH_HTTP] Fetch failed: {type(e).__name__}: {repr(e)}")
            return None

    async def _probe_host(self, url: str, timeout_ms: int = 2000) -> bool:
        """간단한 HEAD 요청으로 대상 도메인 접근성 확인 (네트워크/차단 여부 판별)."""
        timeout_s = max(0.5, timeout_ms / 1000.0)
        try:
            logger.info(f"[FAST_PATH_HTTP] Probing host for {url[:80]} (timeout={timeout_s:.1f}s)")
            client = get_shared_http_client()
            status = await client.head_status(url, timeout_s=timeout_s)
            ok = status is not None and ((200 <= status < 400) or status == 405)
            logger.info(f"[FAST_PATH_HTTP] Probe {'OK' if ok else 'FAIL'} (status={status})")
            return ok
        except Exception as e:
            logger.info(f"[FAST_PATH_HTTP] Probe failed: {type(e).__name__}: {repr(e)}")
            return False

    async def search_lowest_price(self, query: str, candidates: List[str], total_timeout_ms: int) -> Optional[dict]:
        """검색→pcode 선택→상세 파싱까지 Fast Path로 수행."""
        if total_timeout_ms <= 0:
            return None

        logger.info(f"[FAST_PATH] search_lowest_price: query='{query[:50]}...', candidates={len(candidates)}")

        loop = asyncio.get_running_loop()
        deadline = loop.time() + (total_timeout_ms / 1000.0)

        # 검색 페이지와 상품 상세 페이지 모두를 처리해야 하므로 예산을 분리해 사용
        search_budget_ms = int(max(500, total_timeout_ms * 0.6))
        product_budget_floor_ms = 300
        if search_budget_ms > total_timeout_ms - product_budget_floor_ms:
            search_budget_ms = max(500, total_timeout_ms - product_budget_floor_ms)
        search_deadline = loop.time() + (search_budget_ms / 1000.0)

        max_candidates = 2

        # 사전 probe: 호스트 접근성이 약하면 바로 실패 처리
        try:
            probe_ok = await self._probe_host(self.search_url, timeout_ms=min(total_timeout_ms, 2000))
            if not probe_ok:
                logger.info("[FAST_PATH] Host probe failed, skipping HTTP fast path")
                return None
        except Exception:
            logger.info("[FAST_PATH] Host probe exception, skipping HTTP fast path")

        chosen_pcode: Optional[str] = None
        for idx, cand in enumerate(candidates[:max_candidates]):
            remaining_search_ms = int(max(0.0, (search_deadline - loop.time()) * 1000.0))
            if remaining_search_ms <= 0:
                logger.info("[FAST_PATH] Search budget exhausted before search fetch")
                break

            per_try_ms = int(min(max(300, getattr(settings, "crawler_http_timeout_ms", 2000)), remaining_search_ms))
            search_url = f"{self.search_url}?query={quote(cand)}&originalQuery={quote(cand)}"
            html = await self._fetch_html(search_url, timeout_ms=per_try_ms)
            if not html:
                continue

            if is_no_results_html(html):
                logger.info(f"[FAST_PATH] No results page detected for candidate {idx+1}")
                raise FastPathNoResults(query)

            try:
                if not has_search_fingerprint(html):
                    logger.info(f"[FAST_PATH] No search fingerprint found for candidate {idx+1}")
                    continue
            except Exception:
                continue

            pcodes = parse_search_pcandidates(html, query=query, max_candidates=12)
            if pcodes:
                chosen_pcode = pcodes[0]
                logger.info(f"[FAST_PATH] Chosen pcode={chosen_pcode} from candidate {idx+1}")
                break

        if not chosen_pcode:
            logger.info("[FAST_PATH] No pcode found from any candidate")
            return None

        remaining_ms = int(max(0.0, (deadline - loop.time()) * 1000.0))
        if remaining_ms <= 0:
            logger.info("[FAST_PATH] Budget exhausted before product fetch")
            return None

        product_url = f"{self.product_url}?pcode={chosen_pcode}&keyword={quote(query)}"
        html = await self._fetch_html(product_url, timeout_ms=max(300, remaining_ms))
        if not html:
            logger.info(f"[FAST_PATH] Product page fetch failed for pcode={chosen_pcode}")
            return None

        try:
            if not has_product_fingerprint(html):
                logger.info(f"[FAST_PATH] No product fingerprint found for pcode={chosen_pcode}")
                return None
        except Exception:
            return None

        parsed = parse_product_lowest_price(html, fallback_name=query, product_url=product_url)
        if not parsed:
            logger.info(f"[FAST_PATH] Parsing failed for pcode={chosen_pcode}")
            return None

        from datetime import datetime

        return {
            "product_name": parsed.product_name,
            "lowest_price": parsed.lowest_price,
            "link": parsed.link,
            "source": "danawa",
            "mall": parsed.mall,
            "free_shipping": parsed.free_shipping,
            "top_prices": parsed.top_prices,
            "price_trend": parsed.price_trend,
            "updated_at": datetime.now().isoformat(),
            "_path": "http_fastpath",
        }
