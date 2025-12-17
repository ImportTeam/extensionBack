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
    get_blocked_keyword,
)


class FastPathNoResults(Exception):
    """Fast Path에서 '검색 결과 없음'을 확인한 경우.

    이 경우는 네트워크/차단 실패가 아니므로 Playwright로 폴백하지 않도록
    상위 레이어에서 별도 처리하는 것이 바람직합니다.
    """


class FastPathProductFetchFailed(Exception):
    """Fast Path에서 pcode는 찾았지만, 상품 상세(fetch/파싱)에 실패한 경우."""

    def __init__(self, pcode: str, reason: str) -> None:
        super().__init__(f"FastPath product fetch failed for pcode={pcode}: {reason}")
        self.pcode = pcode
        self.reason = reason


class DanawaHttpFastPath:
    """curl_cffi + selectolax 기반 Fast Path."""

    def __init__(self) -> None:
        self.search_url = "https://search.danawa.com/dsearch.php"
        self.product_url = "https://prod.danawa.com/info/"

    async def _fetch_html(self, url: str, timeout_ms: int) -> Optional[str]:
        timeout_s = max(0.2, timeout_ms / 1000.0)

        try:
            # Log URL with reasonable truncation (120 chars) for debugging
            url_display = url if len(url) <= 120 else url[:120] + "..."
            logger.info(f"[FAST_PATH_HTTP] Fetching {url_display} (timeout={timeout_s:.1f}s)")
            client = get_shared_http_client()
            res = await client.get_text(url, timeout_s=timeout_s)
            if not res:
                return None
            status, html = res
            if status != 200:
                logger.info(f"[FAST_PATH_HTTP] Non-200 status: {status}")
                return None
            if not html or is_probably_invalid_html(html):
                kw = get_blocked_keyword(html or "")
                if kw:
                    logger.info(f"[FAST_PATH_HTTP] Blocked or invalid HTML (len={len(html) if html else 0}, blocked_keyword={kw})")
                else:
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
        max_pcodes_per_candidate = 4

        def _is_likely_accessory(product_name: str) -> bool:
            """상품명으로 명백한 액세서리(필름/케이스 등) 오탐을 완화.

            NOTE: Fast Path는 상세페이지 가격 검증이 1차 방어이고,
            여기서는 '브랜드/라벨' 기반으로 강한 액세서리 신호만 얕게 필터링합니다.
            """
            name_lower = (product_name or "").lower()
            accessory_brand_hints = (
                # 보호필름/액세서리에서 자주 등장하는 브랜드/라벨(최소한만 유지)
                "힐링쉴드",
                "폰트리",
                "슈피겐",
                "신지모루",
                "스코코",
                "좀비베리어",
            )
            return any(h.lower() in name_lower for h in accessory_brand_hints)

        # Note: Probing removed to save time. We'll fail fast on actual fetch if host is down.
        chosen_pcode: Optional[str] = None
        chosen_result: Optional[dict] = None
        # 개별 요청마다 고정 타임아웃 적용 (phase budget과 분리)
        per_try_ms = int(getattr(settings, "crawler_http_request_timeout_ms", getattr(settings, "crawler_http_timeout_ms", 4000)))
        
        for idx, cand in enumerate(candidates[:max_candidates]):
            remaining_search_ms = int(max(0.0, (search_deadline - loop.time()) * 1000.0))
            if remaining_search_ms <= 0:
                logger.info("[FAST_PATH] Search budget exhausted before search fetch")
                break

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
            if not pcodes:
                continue

            # 상위 pcode 여러 개를 실제 상품 상세로 검증해 액세서리/오탐을 회피
            for pcode_rank, pcode in enumerate(pcodes[:max_pcodes_per_candidate], start=1):
                remaining_total_ms = int(max(0.0, (deadline - loop.time()) * 1000.0))
                if remaining_total_ms <= 0:
                    logger.info("[FAST_PATH] Total budget exhausted before product fetch")
                    break

                # Product page fetch: 상품 상세는 더 느릴 수 있어 별도 타임아웃을 둡니다.
                configured_product_timeout_ms = int(getattr(settings, "crawler_http_product_timeout_ms", 6000))
                product_timeout_ms = int(max(300, min(configured_product_timeout_ms, remaining_total_ms)))

                product_url = f"{self.product_url}?pcode={pcode}&keyword={quote(query)}"
                product_html = await self._fetch_html(product_url, timeout_ms=product_timeout_ms)
                if not product_html:
                    continue

                try:
                    if not has_product_fingerprint(product_html):
                        logger.info(f"[FAST_PATH] No product fingerprint found for pcode={pcode}")
                        continue
                except Exception:
                    continue

                parsed = parse_product_lowest_price(product_html, fallback_name=query, product_url=product_url)
                if not parsed:
                    continue

                # 상품명 기반 액세서리 필터링 (상품명에 명백한 액세서리 키워드가 있으면 스킵)
                if _is_likely_accessory(parsed.product_name):
                    logger.info(
                        f"[FAST_PATH] Skipping likely accessory based on product name: "
                        f"(pcode={pcode}, name='{parsed.product_name[:50]}...')"
                    )
                    continue

                from datetime import datetime

                chosen_pcode = pcode
                chosen_result = {
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
                logger.info(
                    f"[FAST_PATH] ✅ SUCCESS - Selected pcode={chosen_pcode} (candidate={idx+1}, pcode_rank={pcode_rank})"
                )
                break

            if chosen_result:
                break  # 성공하면 더 이상 시도 안 함

        if not chosen_pcode or not chosen_result:
            logger.info("[FAST_PATH] No pcode found from any candidate")
            return None

        return chosen_result
