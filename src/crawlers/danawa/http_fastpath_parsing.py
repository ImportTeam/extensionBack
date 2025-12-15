"""다나와 HTTP Fast Path - HTML 파싱/검증 유틸.

이 모듈은 네트워크(fetch)와 분리된 순수 파싱/검증 로직을 담습니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List, Dict

from selectolax.parser import HTMLParser

from src.core.config import settings
from src.utils.text_utils import extract_price_from_text, weighted_match_score
from src.utils.url_utils import normalize_href


_BLOCK_KEYWORDS = (
    "로봇",
    "robot",
    "captcha",
    "캡차",
    "접근이 제한",
    "access denied",
    "차단",
    "cloudflare",
    "just a moment",
    "challenge",
    "verify you are human",
)


_NO_RESULTS_KEYWORDS = (
    "검색 결과가 없습니다",
    "검색결과가 없습니다",
    "검색 결과가 없",
    "검색결과가 없",
    "결과가 없습니다",
)


@dataclass
class FastPathResult:
    product_name: str
    lowest_price: int
    link: str
    mall: str | None
    free_shipping: bool | None
    top_prices: List[Dict[str, object]] | None
    price_trend: List[Dict] | None


def is_blocked_html(html: str) -> bool:
    if not html:
        return True
    lowered = html.lower()
    return any(k in lowered for k in _BLOCK_KEYWORDS)


def is_probably_invalid_html(html: str) -> bool:
    """200 OK라도 실질적으로 차단/빈페이지/챌린지일 수 있어 1차 방어."""
    if not html:
        return True
    min_len = getattr(settings, "crawler_fastpath_min_html_length", 5000)
    if len(html) < min_len:
        return True
    if is_blocked_html(html):
        return True
    return False


def is_no_results_html(html: str) -> bool:
    if not html:
        return False
    lowered = html.lower()
    return any(k in lowered for k in _NO_RESULTS_KEYWORDS)


def has_search_fingerprint(html: str) -> bool:
    parser = HTMLParser(html)
    return bool(parser.css_first(".prod_item") or parser.css_first('a[href*="pcode="]'))


def has_product_fingerprint(html: str) -> bool:
    parser = HTMLParser(html)
    return bool(parser.css_first("#lowPriceCompanyArea") or parser.css_first(".prod_tit"))


def extract_pcode_from_href(href: str) -> Optional[str]:
    if not href:
        return None
    m = re.search(r"pcode=(\d+)", href)
    return m.group(1) if m else None


def parse_search_pcandidates(html: str, query: str, max_candidates: int = 12) -> List[str]:
    """검색 결과 HTML에서 pcode 후보를 점수화해 반환."""
    parser = HTMLParser(html)

    links = parser.css(".prod_item .prod_name a")
    if not links:
        links = parser.css('a[href*="pcode="]')

    scored: List[tuple[float, str]] = []
    for node in links[: max_candidates * 3]:
        href = node.attributes.get("href") or ""
        pcode = extract_pcode_from_href(href)
        if not pcode:
            continue
        text = (node.text() or "").strip()
        score = weighted_match_score(query, text)
        scored.append((score, pcode))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in scored[:max_candidates]]


def parse_product_lowest_price(html: str, fallback_name: str, product_url: str) -> Optional[FastPathResult]:
    """상품 상세 HTML에서 최저가/상위 가격을 파싱."""
    parser = HTMLParser(html)

    title_node = parser.css_first(".prod_tit")
    product_name = (title_node.text().strip() if title_node and title_node.text() else fallback_name)

    items = parser.css("#lowPriceCompanyArea .box__mall-price .list__mall-price .list-item")
    if not items:
        return None

    top_items = items[:3]
    top_prices: List[Dict[str, object]] = []

    lowest_price: Optional[int] = None
    lowest_mall: str | None = None
    lowest_free_shipping: bool | None = None
    lowest_purchase_link: Optional[str] = None

    for idx, item in enumerate(top_items):
        price_node = item.css_first(".sell-price .text__num")
        price_text = price_node.text().strip() if price_node and price_node.text() else ""
        price_value = extract_price_from_text(price_text)
        if price_value <= 0:
            continue

        mall_img = item.css_first(".box__logo img")
        mall_name = mall_img.attributes.get("alt") if mall_img else None

        delivery_node = item.css_first(".box__delivery")
        delivery_text = delivery_node.text().strip() if delivery_node and delivery_node.text() else ""
        free_shipping = "무료" in delivery_text

        link_node = item.css_first("a.link__full-cover")
        link = normalize_href((link_node.attributes.get("href") if link_node else "") or "")

        top_prices.append(
            {
                "rank": idx + 1,
                "mall": mall_name or "알 수 없음",
                "price": price_value,
                "free_shipping": free_shipping,
                "delivery": delivery_text,
                "link": link,
            }
        )

        if lowest_price is None:
            lowest_price = price_value
            lowest_mall = mall_name or "알 수 없음"
            lowest_free_shipping = free_shipping
            lowest_purchase_link = link or None

    if lowest_price is None:
        return None

    return FastPathResult(
        product_name=product_name,
        lowest_price=lowest_price,
        link=lowest_purchase_link or product_url,
        mall=lowest_mall,
        free_shipping=lowest_free_shipping,
        top_prices=top_prices,
        price_trend=[],
    )
