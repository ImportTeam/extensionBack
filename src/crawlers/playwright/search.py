"""검색 페이지에서 상품 코드(pcode) 추출 (Playwright)."""

from __future__ import annotations

import re
from typing import Awaitable, Callable, Optional
from urllib.parse import quote

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.core.logging import logger
from src.utils.text import weighted_match_score


async def search_product(
    create_page: Callable[[], Awaitable[Page]],
    search_url_base: str,
    search_query: str,
    *,
    overall_timeout_s: Optional[float] = None,
    candidates: Optional[list[str]] = None,
) -> Optional[str]:
    """
    검색 페이지에서 상품 코드 추출 (계층적 폴백 검색)

    Args:
        create_page: 설정 완료된 Page를 생성하는 async factory
        search_url_base: 검색 base URL (예: https://search.danawa.com/dsearch.php)
        search_query: 검색 쿼리
        candidates: 미리 생성된 검색 후보 리스트 (없으면 생성)

    Returns:
        상품 코드(pcode) 또는 None
    """
    from src.utils.search import DanawaSearchHelper

    page = await create_page()

    try:
        # 스마트 검색 후보 생성 (계층적 폴백)
        if not candidates:
            helper = DanawaSearchHelper()
            candidates = helper.generate_search_candidates(search_query)

        logger.debug(f"Search candidates (smart): {candidates}")

        # 첫 번째 후보부터 검색 시작
        found = False
        used_query = search_query
        for idx, cand in enumerate(candidates):
            logger.debug(f"Trying search (attempt {idx+1}): {cand}")
            search_url = f"{search_url_base}?query={quote(cand)}&originalQuery={quote(cand)}"

            # orchestrator에서 전체 예산으로 asyncio.wait_for를 걸기 때문에,
            # 여기서는 Playwright 레벨 timeout도 그 범위 안으로 맞춰
            # 취소(cancellation)로 인한 noisy error(net::ERR_ABORTED 등)를 줄입니다.
            if overall_timeout_s is not None:
                goto_timeout_ms = max(800, int(overall_timeout_s * 1000 * 0.75))
                await page.goto(search_url, wait_until='domcontentloaded', timeout=goto_timeout_ms)
                selector_timeout_ms = max(800, int(overall_timeout_s * 1000 * 0.85))
            else:
                await page.goto(search_url, wait_until='domcontentloaded')
                selector_timeout_ms = 3000 if idx > 0 else 5000

            try:
                await page.wait_for_selector('.prod_item, a[href*="pcode="]', timeout=selector_timeout_ms)
                found = True
                used_query = cand
                break
            except PlaywrightTimeoutError:
                if idx < len(candidates) - 1:
                    continue
                break

        if not found:
            return None

        # 검색 결과(여러 개)에서 "실제로 사용한 쿼리(used_query)"와 가장 일치하는 상품을 선택
        href = None
        best_href = None
        best_score = 0.0

        prod_links = await page.query_selector_all('.prod_item .prod_name a[href*="pcode="]')
        links_to_score = prod_links[:12] if prod_links else await page.query_selector_all('a[href*="pcode="]')
        if not links_to_score:
            return None

        for link in links_to_score:
            try:
                link_text = (await link.inner_text()) or (await link.get_attribute('title')) or ''
                score = weighted_match_score(used_query, link_text)
                logger.debug(f"Candidate link text: {link_text[:100]} score={score}")
                if score > best_score:
                    best_score = score
                    best_href = await link.get_attribute('href')
            except Exception:
                continue

        # 🔴 기가차드 수정: 너무 낮은 점수면(검색 결과가 엉뚱함) 결과 없음 처리 (오매핑 방지)
        if best_href and best_score >= 45.0:
            href = best_href
        else:
            logger.warning(f"[PLAYWRIGHT] No candidate matched query '{used_query}' with sufficient score (best: {best_score:.1f})")
            return None

        if not href or 'pcode=' not in href:
            return None

        # pcode 추출
        match = re.search(r'pcode=(\d+)', href)
        if match:
            return match.group(1)

        return None

    finally:
        try:
            await page.close()
        except Exception:
            pass
