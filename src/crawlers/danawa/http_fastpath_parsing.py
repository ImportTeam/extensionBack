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
    # 최소한의, 문맥적으로 명확한 차단/챌린지 문구만 보관합니다.
    "접속이 차단되었습니다",
    "access denied",
    "captcha",
    "캡차",
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
    # 엄격한 차단 문구만 매칭
    return any(k in lowered for k in _BLOCK_KEYWORDS)


def get_blocked_keyword(html: str) -> Optional[str]:
    if not html:
        return None
    lowered = html.lower()
    for k in _BLOCK_KEYWORDS:
        if k in lowered:
            return k
    return None


def is_probably_invalid_html(html: str) -> bool:
    """200 OK라도 실질적으로 차단/빈페이지/챌린지일 수 있어 1차 방어.

    변경된 정책:
    - 긍정 검사(primary): 검색 결과/상품 지문이 있으면 정상으로 판단
    - 짧은 응답(예: <5KB)은 의심
    - 명확한 차단 문구가 있을 때만 차단으로 판단
    - 큰 응답(예: >50KB)은 정상으로 신뢰
    """
    if not html:
        return True

    # 짧은 응답은 의심 (일반 차단/챌린지 페이지는 보통 작음)
    min_len = getattr(settings, "crawler_fastpath_min_html_length", 5000)
    if len(html) < min_len:
        return True

    # 긍정 검사: 검색 결과 또는 상품 상세 지문이 있으면 정상
    try:
        if has_search_fingerprint(html) or has_product_fingerprint(html):
            return False
    except Exception:
        # 파싱 오류가 생기면 보수적으로 invalid로 처리
        return True

    # 명확한 차단 문구가 있는 경우에만 차단으로 판단
    lowered = html.lower()
    for kw in _BLOCK_KEYWORDS:
        if kw in lowered:
            return True

    # 큰 페이지(예: >50KB)는 정상일 가능성이 높으므로 신뢰
    if len(html) > getattr(settings, "crawler_fastpath_trust_large_html_size", 50000):
        return False

    # 그 외에는 의심
    return True


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

    # 액세서리 필터용 키워드 (대소문자 무관)
    accessory_keywords = {
        "케이스", "필름", "파우치", "키스킨", "충전기", "거치대",
        "스탠드", "가방", "커버", "보호필름", "강화유리", "어댑터",
        "케이블", "허브", "젠더", "독", "도킹", "스티커", "키캡",
        "글래스", "glass", "펜슬", "pencil", "펜", "pen", "키보드", "keyboard",
        "마우스", "mouse", "트랙패드", "trackpad", "실리콘", "silicon"
    }

    scored: List[tuple[float, str]] = []
    for node in links[: max_candidates * 3]:
        href = node.attributes.get("href") or ""
        pcode = extract_pcode_from_href(href)
        if not pcode:
            continue
        text = (node.text() or "").strip()
        text_lower = text.lower()
        
        # 액세서리 키워드가 있으면 스킵 (본체가 아님)
        found_accessory = [kw for kw in accessory_keywords if kw in text_lower]
        if found_accessory:
            continue
        
        score = weighted_match_score(query, text)
        if score > 0:
            scored.append((score, pcode))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in scored[:max_candidates]]


_TITLE_NOISE_PATTERNS = (
    # UI 버튼/네비게이션
    r"\bVS\s*검색하기\b",
    r"\bVS\s*검색\s*도움말\b",
    r"추천상품과\s*스펙비교하세요\.?",
    r"\b닫기\b",
    # 기타 UI 텍스트
    r"스펙\s*비교",
    r"상품\s*추천",
    r"고객\s*리뷰",
)

# 모델명 패턴: (A1234CD/K), [MFH34KH/A], 등의 괄호/대괄호 안 내용
_MODEL_CODE_PATTERN = r"[\(\[].*?[\)\]]"


def clean_display_text(text: str) -> str:
    """DB/FE용 텍스트에서 불필요한 노이즈, 모델명, 과도한 공백을 제거합니다.
    
    제거 대상:
    - UI 버튼/네비게이션 텍스트 (VS검색하기, 닫기 등)
    - 모델명 (MFHP4KH/A 같은 괄호/대괄호 안의 SKU)
    - 과도한 줄바꿈/공백
    """
    if not text:
        return ""
    
    cleaned = text
    
    # 1. 모델명 제거 (괄호/대괄호 안의 SKU)
    cleaned = re.sub(_MODEL_CODE_PATTERN, " ", cleaned)
    
    # 2. UI 텍스트 제거
    for pat in _TITLE_NOISE_PATTERNS:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
    
    # 3. 과도한 공백/줄바꿈 정리 (공백문자 모두 포함)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    return cleaned


def parse_product_lowest_price(html: str, fallback_name: str, product_url: str) -> Optional[FastPathResult]:
    """상품 상세 HTML에서 최저가/상위 가격을 파싱."""
    parser = HTMLParser(html)

    title_node = parser.css_first(".prod_tit")
    raw_title = (title_node.text().strip() if title_node and title_node.text() else fallback_name)
    product_name = clean_display_text(raw_title)

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

        # 가격 하한 체크(옵션): 액세서리/오탐을 줄이기 위한 방어 장치
        # 기본값(0)은 비활성화
        min_price_threshold = getattr(settings, "crawler_min_price_threshold", 0)
        if min_price_threshold and price_value < min_price_threshold:
            continue

        mall_img = item.css_first(".box__logo img")
        mall_name = mall_img.attributes.get("alt") if mall_img else None

        delivery_node = item.css_first(".box__delivery")
        delivery_text = delivery_node.text().strip() if delivery_node and delivery_node.text() else ""
        delivery_text = clean_display_text(delivery_text)
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
