"""Search query normalization (legacy heuristics + UPCS fallback)."""

from __future__ import annotations

import re

from src.core.logging import logger

from ..core.cleaning import clean_product_name, split_kr_en_boundary


def normalize_search_query(text: str) -> str:
    """외부 쇼핑몰 상품명을 다나와 검색에 적합하게 정규화합니다."""
    if not text:
        return ""

    # 0) UPCS 기반 정규화 우선 시도
    try:
        from src.upcs.normalizer import normalize_query

        normalized = normalize_query(text, vendor="danawa")
        if normalized:
            return str(normalized)
    except Exception as e:
        logger.debug(f"UPCS normalization fallback: {type(e).__name__}: {e}")

    return _normalize_search_query_legacy(text)


def _normalize_search_query_legacy(text: str) -> str:
    """레거시 휴리스틱 정규화(설정 로딩 실패 시 폴백)."""
    if not text:
        return ""

    def is_likely_it_query(value: str) -> bool:
        if not value:
            return False

        v = value.lower()

        non_it_strong = {
            "라면",
            "컵라면",
            "과자",
            "김치",
            "참치",
            "햇반",
            "우유",
            "커피",
            "차",
            "소스",
            "간장",
            "된장",
            "고추장",
            "샴푸",
            "린스",
            "바디",
            "세제",
            "치약",
            "마스크팩",
            "화장품",
        }

        it_signals = {
            "애플",
            "apple",
            "삼성",
            "lg",
            "샤오미",
            "노트북",
            "맥북",
            "아이폰",
            "아이패드",
            "갤럭시",
            "에어팟",
            "버즈",
            "태블릿",
            "스마트폰",
            "이어폰",
            "헤드폰",
            "모니터",
            "그래픽",
            "rtx",
            "gtx",
            "ssd",
            "usb",
            "type-c",
            "usb-c",
            "m1",
            "m2",
            "m3",
            "m4",
            "m5",
            "intel",
            "i3",
            "i5",
            "i7",
            "i9",
            "ryzen",
        }

        score = 0
        if any(w in v for w in non_it_strong):
            score -= 3
        if any(w in v for w in it_signals):
            score += 2
        if re.search(r"\b\d+\s*(gb|tb|mb|khz|mhz|ghz|hz)\b", v):
            score += 2
        if re.search(r"\b(m\s*\d+)\b", v, flags=re.IGNORECASE):
            score += 2
        if re.search(r"\b(rtx\s*\d+|gtx\s*\d+)\b", v, flags=re.IGNORECASE):
            score += 2

        return score >= 2

    raw = text
    raw = re.sub(r"\bVS\s*검색.*$", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\b검색\s*도움말\b", " ", raw)
    raw = re.sub(r"\bVS\s*검색하기\b", " ", raw, flags=re.IGNORECASE)

    is_it = is_likely_it_query(raw)

    for sep in ["·", "•", "|"]:
        if sep in raw:
            raw = raw.split(sep)[0].strip()
            break

    cleaned = clean_product_name(raw)
    cleaned = split_kr_en_boundary(cleaned)

    for sep in ["·", "•", "|"]:
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0].strip()
            break

    colors = "화이트|블랙|실버|골드|그레이|블루|핑크|레드|그린|퍼플|로즈|샴페인|뉴트럼|차콜|브론즈|건메탈"
    cleaned = re.sub(f"({colors})([가-힣])", r"\1 \2", cleaned)

    cleaned = re.sub(r"([가-힣])([A-Z])", r"\1 \2", cleaned)

    if is_it:
        cleaned = re.sub(r"\b\d+\s*(GB|TB|MB|KB)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(DDR\d+|LPDDR\d+|GDDR\d+)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(SSD|HDD|NVME|NVMe)\b", " ", cleaned, flags=re.IGNORECASE)

    if is_it:
        cleaned = re.sub(
            r"\b(WIN(?:DOWS)?\s*\d+|Windows|HOME|PRO|Home|Pro)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

    cleaned = re.sub(r"\b(\d+)\s*세대\b", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b세대\b", " ", cleaned, flags=re.IGNORECASE)
    if is_it:
        cleaned = re.sub(r"\b(인텔|라이젠|AMD)\s+\d+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b시리즈\b", " ", cleaned, flags=re.IGNORECASE)

    if is_it:
        cleaned = re.sub(r"\b(코어|GHZ|MHZ|GHz|MHz|IPS|VA|FIPS)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b지포스\s+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"\b(액티브|노이즈|캔슬링|무선|유선|블루투스|입체음향|돌비)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\b(USB\s*-?\s*C|Type\s*-?\s*C|C\s*타입)\b", " C ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(HDMI|DP|Thunderbolt|3\.5mm|이어폰)\b", " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\b(정품|리퍼|새제품|중고|리뉴얼)\b", " ", cleaned, flags=re.IGNORECASE)

    if is_it:
        cleaned = re.sub(r"\b(패키지|세트|구성|포함|별도|추가)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"\b(케이스|필름|커버|보호|가방|파우치|포우치|스킨|스티커|도킹|거치대)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\b(화이트|블랙|실버|골드|그레이|블루|핑크|레드|그린|퍼플|로즈|샴페인|뉴트럼|차콜|브론즈|건메탈)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

    cleaned = re.sub(r"\b([A-BD-Z])\s+", " ", cleaned)

    cleaned = re.sub(
        r"\b\d{1,2}\b(?=\s*(코어|core|스레드|thread|와트|w|hz|Hz|GHz|MHz)\b)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned
