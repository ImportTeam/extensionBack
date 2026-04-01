"""다나와 HTTP Fast Path (curl_cffi + HTML 파싱)

- 네트워크(fetch) 로직과 파싱 로직을 분리해 테스트/튜닝 포인트를 명확히 합니다.
"""

from __future__ import annotations

import asyncio
import html as _html
import re
from typing import Optional, List
from urllib.parse import quote

from src.core.config import settings
from src.core.logging import logger
from src.crawlers.http_client import get_shared_http_client
from src.utils.resource_loader import load_accessory_keywords

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

    @staticmethod
    def _extract_html_title(html_text: str) -> str:
        if not html_text:
            return ""
        m = re.search(r"<title>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            return ""
        title = _html.unescape(m.group(1))
        title = re.sub(r"\s+", " ", title).strip()
        return title

    async def _fetch_html(self, url: str, timeout_ms: int) -> Optional[str]:
        # Increased minimum from 0.2s to 1.0s for realistic network conditions
        timeout_s = max(1.0, timeout_ms / 1000.0)

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
        # 🔴 기가차드 최종 실무 해결: 단순 고정값
        # total_timeout_ms=12000 → search_budget_ms=9600 (80%), product=2400
        search_budget_ms = int(max(500, total_timeout_ms * 0.8))
        product_budget_floor_ms = 300
        if search_budget_ms > total_timeout_ms - product_budget_floor_ms:
            search_budget_ms = max(500, total_timeout_ms - product_budget_floor_ms)
        search_deadline = loop.time() + (search_budget_ms / 1000.0)

        # 첫 후보만 시도 (성공 시 끝, 실패 시 Playwright로 바로 넣어가기)
        max_candidates = 1
        # Increased from 1 to 5: 액세서리 1개 나와도 다음 후보 계속 검사
        max_pcodes_per_candidate = 5

        def _is_likely_accessory(product_name: str) -> bool:
            """상품명으로 명백한 액세서리(필름/케이스 등)만 정밀 필터링.

            개선: 브랜드만 있는 제품은 필터링하지 않음.
            대신 브랜드 + 액세서리 키워드가 함께 있는 경우만 필터링.
            (예: "폰트리 힐링쉴드" O, "폰트리 맥북" X)
            """
            name_lower = (product_name or "").lower()
            
            # YAML 파일에서 로드
            keywords_data = load_accessory_keywords()
            accessory_keywords = keywords_data.get("accessory_keywords", set())
            accessory_brands = keywords_data.get("accessory_brands", set())
            
            # 키워드 기반 필터링 (우선순위: 최고, 강한 신호)
            matched_keywords = [k for k in accessory_keywords if k in name_lower]
            if matched_keywords:
                logger.info(f"[ACCESSORY_FILTER] Matched keywords: {matched_keywords[:3]} in '{product_name[:80]}' → SKIP")
                return True
            
            # 제조사/브랜드 기반 필터링 (보조 신호, 약한 신호만)
            # 주의: 브랜드만 있으면 필터링하지 않음 (오탐 방지)
            # "폰트리" 브랜드 있고 + 액세서리 표시까지 있을 때만 필터
            matched_brands = [b for b in accessory_brands if b.lower() in name_lower]
            if matched_brands:
                logger.debug(f"[ACCESSORY_FILTER] Detected accessory brand: {matched_brands} in '{product_name[:80]}' (but no keyword, keeping for now)")
            
            return False  # 브랜드만으로는 필터링하지 않음

        # Note: Probing removed to save time. We'll fail fast on actual fetch if host is down.
        chosen_pcode: Optional[str] = None
        chosen_result: Optional[dict] = None
        seen_pcodes: set[str] = set()  # 🔴 기가차드 수정: 중복 분석 방지
        # 개별 요청 타임아웃: 고정값 8s (다나와 페이지 완전 로드에 필요)
        per_try_ms = 8000
        
        for idx, cand in enumerate(candidates[:max_candidates]):
            # IMPORTANT:
            # - 각 candidate로 검색 페이지를 fetch 했다면,
            #   결과 점수화/상세 검증도 동일한 candidate 기준으로 해야 합니다.
            # - 그렇지 않으면 (예: 원본 query에 연도 '2025'가 포함된 경우)
            #   점수 필터(40/45점)에 의해 pcode가 모두 탈락할 수 있습니다.
            scoring_query = cand

            remaining_search_ms = int(max(0.0, (search_deadline - loop.time()) * 1000.0))
            if remaining_search_ms <= 0:
                logger.info("[FAST_PATH] Search budget exhausted before search fetch")
                break

            search_url = f"{self.search_url}?query={quote(cand)}&originalQuery={quote(cand)}"
            html = await self._fetch_html(search_url, timeout_ms=per_try_ms)
            if not html:
                continue

            try:
                if not has_search_fingerprint(html):
                    # Fingerprint 없음 → 정말 검색 결과가 없는지 확인
                    # NOTE: is_no_results_html()은 오탐이 많을 수 있으므로,
                    # fingerprint가 없을 때만 사용
                    if is_no_results_html(html):
                        logger.info(f"[FAST_PATH] No results page detected for candidate {idx+1}")
                        raise FastPathNoResults(query)
                    else:
                        logger.info(f"[FAST_PATH] No search fingerprint found for candidate {idx+1}")
                        continue
            except FastPathNoResults:
                raise
            except Exception:
                continue

            pcodes = parse_search_pcandidates(html, query=scoring_query, max_candidates=12)
            if not pcodes:
                continue

            # 상위 pcode 여러 개를 실제 상품 상세로 검증해 액세서리/오탐을 회피
            for pcode_rank, pcode in enumerate(pcodes[:max_pcodes_per_candidate], start=1):
                if pcode in seen_pcodes:
                    continue
                seen_pcodes.add(pcode)

                remaining_total_ms = int(max(0.0, (deadline - loop.time()) * 1000.0))
                if remaining_total_ms <= 0:
                    logger.info("[FAST_PATH] Total budget exhausted before product fetch")
                    break

                # Product page fetch: 상품 상세는 더 느릴 수 있어 별도 타임아웃을 둡니다.
                # Increased minimum from 300ms to 3000ms (3s) for realistic network conditions
                configured_product_timeout_ms = int(getattr(settings, "crawler_http_product_timeout_ms", 6000))
                product_timeout_ms = int(max(3000, min(configured_product_timeout_ms, remaining_total_ms)))

                product_url = f"{self.product_url}?pcode={pcode}&keyword={quote(scoring_query)}"
                product_html = await self._fetch_html(product_url, timeout_ms=product_timeout_ms)
                if not product_html:
                    continue

                try:
                    if not has_product_fingerprint(product_html):
                        logger.info(f"[FAST_PATH] No product fingerprint found for pcode={pcode}")
                        continue
                except Exception:
                    continue

                parsed = parse_product_lowest_price(product_html, fallback_name=scoring_query, product_url=product_url)
                if not parsed:
                    continue

                # 상품명 기반 액세서리 필터링
                # NOTE: parse_product_lowest_price() 내부에서 표시용 클리닝이 적용되며,
                # 괄호 안(예: "(액정보호필름...)"")이 삭제될 수 있습니다.
                # 그래서 원본 HTML <title>도 함께 검사합니다.
                html_title = self._extract_html_title(product_html)
                if _is_likely_accessory(parsed.product_name) or (html_title and _is_likely_accessory(html_title)):
                    logger.info(
                        f"[FAST_PATH] Skipping likely accessory based on product name: "
                        f"(pcode={pcode}, name='{parsed.product_name[:50]}...', title='{html_title[:50]}...')"
                    )
                    continue

                from datetime import datetime

                chosen_pcode = pcode
                chosen_result = {
                    "product_name": parsed.product_name,
                    "lowest_price": parsed.lowest_price,
                    "price": parsed.lowest_price,  # alias for orchestrator
                    "product_url": parsed.link,  # full URL
                    "link": parsed.link,
                    "source": "danawa",
                    "mall": parsed.mall,
                    "free_shipping": parsed.free_shipping,
                    "top_prices": parsed.top_prices,
                    "price_trend": parsed.price_trend,
                    "pcode": chosen_pcode,  # product ID
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

    async def fetch_product_by_code(
        self,
        query: str,
        product_code: str,
        timeout_ms: int,
    ) -> Optional[dict]:
        """pcode가 이미 있을 때 상품 상세 페이지만 직접 조회."""
        if not product_code or not product_code.isdigit() or timeout_ms <= 0:
            return None

        product_url = f"{self.product_url}?pcode={product_code}&keyword={quote(query)}"
        product_html = await self._fetch_html(url=product_url, timeout_ms=timeout_ms)
        if not product_html:
            return None

        try:
            if not has_product_fingerprint(product_html):
                logger.info(f"[FAST_PATH] No product fingerprint found for direct pcode={product_code}")
                return None
        except Exception:
            return None

        parsed = parse_product_lowest_price(
            product_html,
            fallback_name=query,
            product_url=product_url,
        )
        if not parsed:
            return None

        from datetime import datetime

        return {
            "product_name": parsed.product_name,
            "lowest_price": parsed.lowest_price,
            "price": parsed.lowest_price,
            "product_url": parsed.link,
            "link": parsed.link,
            "source": "danawa",
            "mall": parsed.mall,
            "free_shipping": parsed.free_shipping,
            "top_prices": parsed.top_prices,
            "price_trend": parsed.price_trend,
            "pcode": product_code,
            "updated_at": datetime.now().isoformat(),
            "_path": "http_fastpath_direct",
        }
