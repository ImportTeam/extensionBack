"""다나와 HTTP Fast Path - HTML 파싱/검증 유틸.

이 모듈은 네트워크(fetch)와 분리된 순수 파싱/검증 로직을 담습니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List, Dict

from selectolax.parser import HTMLParser

from src.core.config import settings
from src.core.logging import logger
from src.utils.text_utils import extract_price_from_text, weighted_match_score
from src.utils.url import normalize_href


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
    # 다나와 검색결과는 여러 형태의 링크를 사용합니다.
    # - https://prod.danawa.com/info/?pcode=123
    # - https://prod.danawa.com/bridge/go_link_goods.php?...&prod_id=123
    for pat in (r"[?&]pcode=(\d+)", r"[?&]prod_id=(\d+)"):
        m = re.search(pat, href)
        if m:
            return m.group(1)
    # Fallback: query param 경계가 없는 경우까지 커버
    for pat in (r"pcode=(\d+)", r"prod_id=(\d+)"):
        m = re.search(pat, href)
        if m:
            return m.group(1)
    return None


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
        # 🔴 기가차드 최종 수정: FastPath에서 점수 필터 제거
        # 이유: selector 구조 변화로 인한 오탐을 막으려 했지만,
        # 역으로 정확한 pcode 후보까지 버리는 악순환 발생
        # → pcode가 존재하면 일단 반환, 최종 검증은 가격 파싱으로
        scored.append((score, pcode))

    scored.sort(key=lambda t: t[0], reverse=True)

    if scored:
        return [p for _, p in scored[:max_candidates]]

    # 폴백: 구조 변경/동적 링크로 selector가 실패했을 때를 대비해
    # HTML에서 직접 pcode/prod_id를 추출합니다.
    # (상세 페이지에서 다시 검증하므로 여기서는 후보를 넉넉히 확보하는 것이 이득)
    logger.debug(f"[FAST_PATH] Selector fallback: extracting pcode from raw HTML")
    pcodes = re.findall(r"(?:pcode|prod_id)=(\d{5,})", html)
    if not pcodes:
        logger.debug(f"[FAST_PATH] No pcode found in raw HTML either")
        return []

    uniq: List[str] = []
    seen: set[str] = set()
    for p in pcodes:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
            logger.debug(f"[FAST_PATH] Regex extracted pcode: {p}")
        if len(uniq) >= max_candidates:
            break
    return uniq


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
    
    # 🔴 기가차드 최종 실무 해결: FastPath에서 상품명 검증 제거
    # 이유:
    # - 이미 다나와 HTML을 정확히 파싱했으므로, pcode가 존재하면 그 자체가 검증 완료
    # - 한국어 띄어쓰기/붙임/UI 노이즈로 인한 점수 오판이 더 큰 피해
    # - 최종 검증은 가격 파싱 성공 여부 + 금액 합리성으로 충분
    # - 따라서 여기서는 pcode를 얻었으면 일단 반환하고, Playwright와 병렬로 진행

    # DB/FE 표시용으로만 클리닝 수행
    product_name = clean_display_text(raw_title)

    items = parser.css("#lowPriceCompanyArea .box__mall-price .list__mall-price .list-item")
    if not items:
        # 🔴 기가차드 수정: 대표 최저가 영역 시도 (쇼핑몰 목록이 없는 경우)
        rep_price_node = parser.css_first(".lowest_area .price_sect .num, .lowest_area .price_sect .price_num, .lowest_price .num")
        if rep_price_node:
            rep_price_text = rep_price_node.text().strip()
            rep_price_value = extract_price_from_text(rep_price_text)
            if rep_price_value > 0:
                rep_mall_node = parser.css_first(".lowest_area .mall_name, .lowest_price .mall_name, .lowest_area .mall_logo img")
                if rep_mall_node and rep_mall_node.tag == "img":
                    rep_mall_name = rep_mall_node.attributes.get("alt") or "다나와최저가"
                else:
                    rep_mall_name = rep_mall_node.text().strip() if rep_mall_node else "다나와최저가"
                
                return FastPathResult(
                    product_name=product_name,
                    lowest_price=rep_price_value,
                    link=product_url,
                    mall=rep_mall_name,
                    free_shipping=None,
                    top_prices=[],
                    price_trend=[],
                )
        return None

    top_items = items[:3]
    top_prices: List[Dict[str, object]] = []

    lowest_price: Optional[int] = None
    lowest_mall: str | None = None
    lowest_free_shipping: bool | None = None
    lowest_purchase_link: Optional[str] = None

    for idx, item in enumerate(top_items):
        price_node = item.css_first(".sell-price .text__num")
        if not price_node:
            # 구조 변경 대응
            price_node = item.css_first(".price .num, .text__num")
            
        price_text = price_node.text().strip() if price_node and price_node.text() else ""
        price_value = extract_price_from_text(price_text)
        if price_value <= 0:
            continue

        # 가격 하한 체크(옵션): 액세서리/오탐을 줄이기 위한 방어 장치
        # 기본값(0)은 비활성화
        min_price_threshold = getattr(settings, "crawler_min_price_threshold", 0)
        if min_price_threshold and price_value < min_price_threshold:
            continue

        # 🔴 기가차드 수정: 쇼핑몰 이름 추출 강화
        mall_img = item.css_first(".box__logo img")
        mall_name = mall_img.attributes.get("alt") if mall_img else None
        
        if not mall_name:
            mall_text_node = item.css_first(".box__logo .text, .mall-name")
            if mall_text_node:
                mall_name = mall_text_node.text().strip()
        
        mall_name = mall_name or "알 수 없음"

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
