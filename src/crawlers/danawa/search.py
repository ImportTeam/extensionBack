"""검색 페이지에서 상품 코드(pcode) 추출 (Playwright)."""

from __future__ import annotations

import re
from typing import Awaitable, Callable, Optional
from urllib.parse import quote

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.core.logging import logger
from src.utils.text_utils import weighted_match_score


async def search_product(
    create_page: Callable[[], Awaitable[Page]],
    search_url_base: str,
    search_query: str,
) -> Optional[str]:
    """
    검색 페이지에서 상품 코드 추출 (계층적 폴백 검색)

    Args:
        create_page: 설정 완료된 Page를 생성하는 async factory
        search_url_base: 검색 base URL (예: https://search.danawa.com/dsearch.php)
        search_query: 검색 쿼리

    Returns:
        상품 코드(pcode) 또는 None
    """
    from src.utils.search_optimizer import DanawaSearchHelper

    page = await create_page()

    try:
        # 스마트 검색 후보 생성 (계층적 폴백)
        helper = DanawaSearchHelper()
        candidates = helper.generate_search_candidates(search_query)

        logger.debug(f"Search candidates (smart): {candidates}")

        # 첫 번째 후보부터 검색 시작
        found = False
        for idx, cand in enumerate(candidates):
            logger.debug(f"Trying search (attempt {idx+1}): {cand}")
            search_url = f"{search_url_base}?query={quote(cand)}&originalQuery={quote(cand)}"
            await page.goto(search_url, wait_until='domcontentloaded')

            try:
                await page.wait_for_selector('.prod_item, a[href*="pcode="]', timeout=3000 if idx > 0 else 5000)
                found = True
                break
            except PlaywrightTimeoutError:
                if idx < len(candidates) - 1:
                    continue
                break

        if not found:
            return None

        # 검색 결과(여러 개)에서 "원본 쿼리"와 가장 일치하는 상품을 선택
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
                score = weighted_match_score(search_query, link_text)
                logger.debug(f"Candidate link text: {link_text[:100]} score={score}")
                if score > best_score:
                    best_score = score
                    best_href = await link.get_attribute('href')
            except Exception:
                continue

        # 너무 낮은 점수면(검색 결과가 엉뚱함) 첫 번째 결과로 폴백
        if best_href and best_score >= 60.0:
            href = best_href
        else:
            first_product = await page.query_selector('.prod_item .prod_name a[href*="pcode="]')
            href = await first_product.get_attribute('href') if first_product else best_href

        if not href or 'pcode=' not in href:
            return None

        # pcode 추출
        match = re.search(r'pcode=(\d+)', href)
        if match:
            return match.group(1)

        return None

    finally:
        await page.close()
