"""Weighted matching helpers."""

from __future__ import annotations

import re

from .signals import extract_product_signals
from .similarity import fuzzy_score
from .tokenize import tokenize_keywords
from .cleaning import clean_product_name, split_kr_en_boundary


def is_accessory_trap(query: str, candidate: str) -> bool:
    if not query or not candidate:
        return False

    accessory_keywords = {
        "케이스",
        "커버",
        "키스킨",
        "스킨",
        "필름",
        "보호필름",
        "강화유리",
        "거치대",
        "스탠드",
        "파우치",
        "가방",
        "충전기",
        "어댑터",
        "케이블",
        "허브",
        "젠더",
        "독",
        "도킹",
        "키보드커버",
        "키보드덮개",
        "교체용",
        "전용",
        "호환",
        "리필",
        "리필용",
        "스티커",
        "보호",
        "케이스형",
        "키캡",
        "키패드",
    }

    main_product_hints = {
        "노트북",
        "랩탑",
        "맥북",
        "울트라북",
        "태블릿",
        "아이패드",
        "스마트폰",
        "핸드폰",
        "아이폰",
        "갤럭시",
        "모니터",
        "tv",
        "데스크탑",
        "본체",
        "카메라",
        "렌즈",
        "이어폰",
        "헤드폰",
        "스피커",
        "마우스",
    }

    q_tokens = tokenize_keywords(query)
    c_tokens = tokenize_keywords(candidate)

    suspicious = c_tokens.intersection(accessory_keywords)
    if not suspicious:
        return False

    if not suspicious.isdisjoint(q_tokens):
        return False

    if q_tokens.isdisjoint(main_product_hints):
        return False

    return True


def weighted_match_score(query: str, candidate: str) -> float:
    if not query or not candidate:
        return 0.0

    if is_accessory_trap(query, candidate):
        return 0.0

    base = fuzzy_score(query, candidate)

    q = extract_product_signals(query)
    c = extract_product_signals(candidate)

    score = base

    if q["model_codes"] and c["model_codes"]:
        if q["model_codes"].isdisjoint(c["model_codes"]):
            score -= 40.0
        else:
            score += 10.0
    elif q["model_codes"] and not c["model_codes"]:
        score -= 18.0

    if q["unit_numbers"] and c["unit_numbers"]:
        if q["unit_numbers"].isdisjoint(c["unit_numbers"]):
            score -= 22.0
        else:
            score += 6.0

    if q["big_numbers"]:
        if q["big_numbers"].isdisjoint(c["big_numbers"]):
            score -= 15.0
        else:
            score += 3.0

    q_named: dict[str, set[str]] = q["named_numbers"]
    c_named: dict[str, set[str]] = c["named_numbers"]
    common_keys = set(q_named.keys()).intersection(c_named.keys())
    mismatch = False
    matched = False
    for k in common_keys:
        if q_named[k] and c_named[k]:
            if q_named[k].isdisjoint(c_named[k]):
                mismatch = True
            else:
                matched = True
    if mismatch:
        score -= 28.0
    elif matched:
        score += 8.0

    if q["years"] and c["years"]:
        if q["years"].isdisjoint(c["years"]):
            score -= 6.0
        else:
            score += 2.0

    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return float(score)


def normalize_search_query(text: str) -> str:
    """외부 쇼핑몰 상품명을 다나와 검색에 적합하게 정규화합니다.

    목표: 한글 브랜드/제품명 중심으로 남기되, 상품 식별에 중요한 토큰(모델 번호, 화면 크기,
    칩셋/세대 등)은 보존하고, 검색 방해가 되는 스펙/옵션 토큰만 제거합니다.
    
    최적화 전략:
    1. 특수 구분자 이후 제거 (스펙의 99%)
    2. 대문자 영어만 제거 (모델명이 아닌 것)
    3. 알려진 스펙 키워드 제거
    4. 불필요한 상품 설명 제거
    """
    if not text:
        return ""

    # === Phase 0: 원본에서 먼저 분리/노이즈 제거 ===
    # clean_product_name에서 '·' 같은 구분자가 제거되므로, 반드시 그 전에 split해야 함.
    raw = text
    # 쿠팡/확장프로그램 등에서 붙는 노이즈 제거
    raw = re.sub(r"\bVS\s*검색.*$", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\b검색\s*도움말\b", " ", raw)
    raw = re.sub(r"\bVS\s*검색하기\b", " ", raw, flags=re.IGNORECASE)

    # 쿠팡 스타일: "상품명 · 옵션1 · 옵션2" 또는 "상품명 | 옵션"
    for sep in ['·', '•', '|']:
        if sep in raw:
            raw = raw.split(sep)[0].strip()
            break

    cleaned = clean_product_name(raw)
    cleaned = split_kr_en_boundary(cleaned)

    # === Phase 1: (잔존하는) 구분자 처리 보강 ===
    for sep in ['·', '•', '|']:
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0].strip()
            break

    # === Phase 2: 명백한 스펙 제거 ===
    # 용량 (256GB, 1TB 등)
    cleaned = re.sub(r"\b\d+\s*(GB|TB|MB|KB)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 메모리 타입
    cleaned = re.sub(r"\b(DDR\d+|LPDDR\d+|GDDR\d+)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 저장소 타입
    cleaned = re.sub(r"\b(SSD|HDD|NVME|NVMe)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 연도 (2024, 2025 등)
    # NOTE: 연도는 모델 식별에 중요한 경우가 있어 제거하지 않습니다.
    
    # 운영체제
    cleaned = re.sub(r"\b(WIN(?:DOWS)?\s*\d+|Windows|HOME|PRO|Home|Pro)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 프로세서 세대/종류 (인텔 14세대, 라이젠 8000 등)
    cleaned = re.sub(r"\b(\d+\s*)?세대\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(인텔|라이젠|AMD)\s+\d+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(세대|시리즈)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 스펙 기술 용어
    cleaned = re.sub(r"\b(코어|GHZ|MHZ|GHz|MHz|IPS|VA|FIPS)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 그래픽 관련 (RTX, GTX 등 지포스/라데온 모델명은 유지하되, 순수 기술 스펙은 제거)
    cleaned = re.sub(r"\b지포스\s+", " ", cleaned, flags=re.IGNORECASE)
    
    # 오디오 관련 스펙
    cleaned = re.sub(r"\b(액티브|노이즈|캔슬링|무선|유선|블루투스|입체음향|돌비)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 연결/포트 관련
    cleaned = re.sub(r"\b(USB-?C|Type-?C|HDMI|DP|Thunderbolt|3\.5mm|이어폰)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 상품 상태/구성 (정품, 리퍼, 세트, 구성, 포함 등)
    cleaned = re.sub(r"\b(정품|리퍼|새제품|중고|리뉴얼|패키지|세트|구성|포함|별도|추가)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 색상 (색상은 검색에 별로 도움이 안 되고, 상품 구분을 복잡하게 함)
    cleaned = re.sub(r"\b(화이트|블랙|실버|골드|그레이|블루|핑크|레드|그린|퍼플|로즈|샴페인|뉴트럼|차콜|브론즈|건메탈)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # === Phase 3: 단독 영어 단어 제거 (BasicWhite의 White 같은 것) ===
    # 단독 대문자 영어 토큰 (BB1422SS-N의 N 같은 하나 글자는 제거, 하지만 모델명 보존)
    # N-시리즈 → 제거하되, RTX 4050은 유지
    cleaned = re.sub(r"\b([A-Z])\s+", " ", cleaned)  # 단독 대문자 제거
    
    # === Phase 4: 숫자 토큰 정리 (필요한 숫자는 보존) ===
    # 1~2자리 숫자는 화면 크기(13/15), 제품 모델(아이폰 15), 세대 등의 핵심 식별자일 수 있어
    # 전역 제거를 하지 않습니다. 대신 명백한 스펙 컨텍스트(코어/스레드/와트 등) 앞의 숫자만 제거합니다.
    cleaned = re.sub(
        r"\b\d{1,2}\b(?=\s*(코어|core|스레드|thread|와트|w|hz|Hz|GHz|MHz)\b)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    
    # === Phase 5: 공백 정리 ===
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    return cleaned
