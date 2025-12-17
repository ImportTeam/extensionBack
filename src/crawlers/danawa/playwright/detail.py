"""상품 상세 페이지 파싱 (Playwright)."""

from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import quote

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.core.config import settings
from src.core.logging import logger
from src.utils.text_utils import extract_price_from_text
from src.utils.url_utils import normalize_href

from .price_trend import extract_price_trend


async def get_product_lowest_price(
    page: Page,
    product_url_base: str,
    product_code: str,
    search_query: str,
) -> Optional[Dict]:
    """
    상품 상세 페이지에서 쇼핑몰별 최저가 Top 1 추출

    실제 다나와 HTML 구조:
    div#lowPriceCompanyArea > div.box__mall-price > ul.list__mall-price > li.list-item
    - 첫 번째 list-item이 최저가 (badge__lowest 표시)
    - 가격: .sell-price .text__num
    - 쇼핑몰: .box__logo img[alt]

    Args:
        page: Playwright 페이지
        product_url_base: 상품 상세 base URL (예: https://prod.danawa.com/info/)
        product_code: 상품 코드
        search_query: 검색한 상품명

    Returns:
        최저가 정보 또는 None
    """
    try:
        # 상품 상세 페이지 이동
        product_url = f"{product_url_base}?pcode={product_code}&keyword={quote(search_query)}"
        await page.goto(product_url, wait_until='domcontentloaded')

        # 가격 영역 대기
        try:
            await page.wait_for_selector('#lowPriceCompanyArea', timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning(f"Price area not found for pcode: {product_code}")
            return None

        # 배송비 포함 토글이 있으면 켜기 (가격 비교 품질 향상)
        try:
            toggle = page.locator('#add_delivery')
            if await toggle.count() > 0:
                is_checked = await toggle.is_checked()
                if not is_checked:
                    label = page.locator('label:has(#add_delivery)')
                    if await label.count() > 0:
                        await label.first.click()
                    else:
                        await toggle.first.click(force=True)
                    await page.wait_for_timeout(400)
        except Exception as e:
            logger.debug(f"Delivery toggle interaction skipped: {e}")

        # 상품명 추출
        product_name_elem = await page.query_selector('.prod_tit')
        product_name = search_query
        if product_name_elem:
            product_name = await product_name_elem.inner_text()
            product_name = product_name.strip()

        # 최저가 추이 데이터는 비용이 크므로 기본 비활성화(성능 우선)
        price_trend: list[Dict] = []
        if getattr(settings, "crawler_enable_price_trend", False):
            price_trend = await extract_price_trend(page)

        # 쇼핑몰별 최저가 - Top 3 (최저가 계산은 첫 번째 기준)
        price_items = await page.query_selector_all(
            '#lowPriceCompanyArea .box__mall-price .list__mall-price .list-item'
        )

        if not price_items:
            logger.warning("No mall price found")
            return None

        top_items = price_items[:3]
        top_prices: List[Dict[str, object]] = []

        lowest_price = None
        lowest_mall = "알 수 없음"
        lowest_free_shipping = None
        lowest_purchase_link: str | None = None

        for idx, item in enumerate(top_items):
            price_elem = await item.query_selector('.sell-price .text__num')
            if not price_elem:
                continue

            price_text = await price_elem.inner_text()
            price_value = extract_price_from_text(price_text)
            if price_value <= 0:
                continue

            mall_elem = await item.query_selector('.box__logo img')
            mall_name = await mall_elem.get_attribute('alt') if mall_elem else "알 수 없음"

            delivery_elem = await item.query_selector('.box__delivery')
            delivery_text = (await delivery_elem.inner_text()) if delivery_elem else ""
            delivery_text = delivery_text.strip() if delivery_text else ""
            free_shipping = "무료" in delivery_text

            link_elem = await item.query_selector('a.link__full-cover')
            link = await link_elem.get_attribute('href') if link_elem else ""
            link = normalize_href(link or "")

            top_prices.append({
                "rank": idx + 1,
                "mall": mall_name or "알 수 없음",
                "price": price_value,
                "free_shipping": free_shipping,
                "delivery": delivery_text or "",
                "link": link or ""
            })

            if lowest_price is None:
                lowest_price = price_value
                lowest_mall = mall_name or "알 수 없음"
                lowest_free_shipping = free_shipping
                lowest_purchase_link = link or None

        if lowest_price is None:
            logger.warning("Parsed prices are invalid")
            return None

        from datetime import datetime

        return {
            "product_name": product_name,
            "lowest_price": lowest_price,
            # API 응답의 link는 '최저가 쇼핑몰 구매 링크'를 우선 반환
            "link": lowest_purchase_link or product_url,
            "source": "danawa",
            "mall": lowest_mall,
            "free_shipping": lowest_free_shipping,
            "top_prices": top_prices,
            "price_trend": price_trend,
            "updated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting product price: {e}")
        return None
