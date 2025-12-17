"""Weighted matching helpers."""

from __future__ import annotations

import re

from src.core.logging import logger

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

    # [핵심] 제품군(Pro/Air/Max/Mini) 불일치 - 강한 필터
    ipad_variants = {"pro", "air", "max", "mini"}
    q_ipad = any(word in query.lower() for word in ipad_variants)
    c_ipad = any(word in candidate.lower() for word in ipad_variants)
    
    if q_ipad and c_ipad:
        # 둘 다 iPad인데 variant가 다르면 (Pro vs Air)
        q_variant = [w for w in ipad_variants if w in query.lower()]
        c_variant = [w for w in ipad_variants if w in candidate.lower()]
        if q_variant and c_variant and q_variant != c_variant:
            logger.debug(f"iPad variant mismatch: query={q_variant} vs candidate={c_variant}")
            score -= 50.0  # 강한 패널티

    # [핵심] CPU/칩셋 정보 추출 및 비교 (M5 vs M3 등)
    # - 쿼리가 특정 M칩을 요구하고 후보가 다른 M칩을 명시하면: 하드 제외(0점)
    # - 둘 다 같은 M칩이면 보너스
    m_chip_pattern = r"(?i)M\s*(\d+)"  # M1, M2, ... (공백/붙임 허용)
    q_chips = set(re.findall(m_chip_pattern, query))
    c_chips = set(re.findall(m_chip_pattern, candidate))

    if q_chips and c_chips and q_chips != c_chips:
        logger.debug(f"Chip mismatch (disqualify): query={q_chips} vs candidate={c_chips}")
        return 0.0
    if q_chips and c_chips and q_chips == c_chips:
        score += 5.0

    # [핵심] 화면 크기(11/13/15 등) 불일치 - 하드 제외
    # iPad Pro 11 vs 13, MacBook 13 vs 15 등은 완전히 다른 제품
    screen_size_pattern = r"\b(10|11|12|13|14|15|16|17)(?:\s*인치|\s*inch|\s*\")?"
    q_screen = set(re.findall(screen_size_pattern, query.lower()))
    c_screen = set(re.findall(screen_size_pattern, candidate.lower()))
    
    if q_screen and c_screen and q_screen != c_screen:
        logger.debug(f"Screen size mismatch (disqualify): query={q_screen} vs candidate={c_screen}")
        return 0.0
    if q_screen and c_screen and q_screen == c_screen:
        score += 8.0  # 같은 크기면 보너스

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

    # 0) 설정 기반(resources/) 정규화 우선 시도
    # - 도메인/태그 기반 정책으로 '블랙' 같은 토큰을 상황에 맞게 보존/제거
    # - 실패 시(의존성/설정 오류 등) 기존 휴리스틱으로 폴백
    try:
        from .normalization_resources import normalize_search_query_with_resources

        normalized = normalize_search_query_with_resources(text, vendor="danawa")
        if normalized:
            return normalized
    except Exception as e:
        logger.debug(f"resource-based normalization fallback: {type(e).__name__}: {e}")

    return _normalize_search_query_legacy(text)


def _normalize_search_query_legacy(text: str) -> str:
    """레거시 휴리스틱 정규화(설정 로딩 실패 시 폴백)."""
    if not text:
        return ""

    def is_likely_it_query(value: str) -> bool:
        """휴리스틱으로 IT/전자제품 쿼리인지 판단.

        - IT 쿼리에서만 색상/액세서리/스펙 제거를 강하게 적용
        - 식품/생활용품 등 일반 상품 쿼리에서는 색상(예: '신라면 블랙')을 보존
        """
        if not value:
            return False

        v = value.lower()

        non_it_strong = {
            # 식품
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
            # 생활/뷰티
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

    # === Phase 0: 원본에서 먼저 분리/노이즈 제거 ===
    # clean_product_name에서 '·' 같은 구분자가 제거되므로, 반드시 그 전에 split해야 함.
    raw = text
    # 쿠팡/확장프로그램 등에서 붙는 노이즈 제거
    raw = re.sub(r"\bVS\s*검색.*$", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\b검색\s*도움말\b", " ", raw)
    raw = re.sub(r"\bVS\s*검색하기\b", " ", raw, flags=re.IGNORECASE)

    # 분기 판단(IT vs 일반)은 원본(스펙 포함)에서 해야 정확도가 높음
    # 예: "... · 256GB · WIN11" 같이 뒤쪽 스펙에 IT 신호가 몰려있는 경우
    is_it = is_likely_it_query(raw)

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

    # [추가] 색상+명사 합성어 분리 (예: 화이트케이스 -> 화이트 케이스)
    # 색상 단어 바로 뒤에 다른 한글이 붙어있으면 띄워줌
    colors = "화이트|블랙|실버|골드|그레이|블루|핑크|레드|그린|퍼플|로즈|샴페인|뉴트럼|차콜|브론즈|건메탈"
    cleaned = re.sub(f"({colors})([가-힣])", r"\1 \2", cleaned)

    # [추가] 한글+영어 붙은 것 분리 (예: 이어폰C -> 이어폰 C)
    cleaned = re.sub(r"([가-힣])([A-Z])", r"\1 \2", cleaned)

    # === Phase 2: 명백한 스펙 제거 ===
    # NOTE: IT 쿼리에서만 강하게 적용합니다. (일반 상품은 숫자/단위가 중요할 수 있음)
    if is_it:
        # 용량 (256GB, 1TB 등)
        cleaned = re.sub(r"\b\d+\s*(GB|TB|MB|KB)\b", " ", cleaned, flags=re.IGNORECASE)

        # 메모리 타입
        cleaned = re.sub(r"\b(DDR\d+|LPDDR\d+|GDDR\d+)\b", " ", cleaned, flags=re.IGNORECASE)

        # 저장소 타입
        cleaned = re.sub(r"\b(SSD|HDD|NVME|NVMe)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 연도 (2024, 2025 등)
    # NOTE: 연도는 모델 식별에 중요한 경우가 있어 제거하지 않습니다.
    
    # 운영체제 (IT)
    if is_it:
        cleaned = re.sub(r"\b(WIN(?:DOWS)?\s*\d+|Windows|HOME|PRO|Home|Pro)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 프로세서 세대/종류 (인텔 14세대, 라이젠 8000 등)
    # [수정] "2세대" -> "2"로 숫자만 남김 (기존에 숫자까지 삭제되는 버그 수정)
    cleaned = re.sub(r"\b(\d+)\s*세대\b", r"\1", cleaned, flags=re.IGNORECASE)  # "2세대" -> "2"
    cleaned = re.sub(r"\b세대\b", " ", cleaned, flags=re.IGNORECASE)  # 숫자 없는 "세대"만 삭제
    if is_it:
        cleaned = re.sub(r"\b(인텔|라이젠|AMD)\s+\d+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b시리즈\b", " ", cleaned, flags=re.IGNORECASE)
    
    if is_it:
        # 스펙 기술 용어
        cleaned = re.sub(r"\b(코어|GHZ|MHZ|GHz|MHz|IPS|VA|FIPS)\b", " ", cleaned, flags=re.IGNORECASE)

        # 그래픽 관련 (RTX, GTX 등 지포스/라데온 모델명은 유지하되, 순수 기술 스펙은 제거)
        cleaned = re.sub(r"\b지포스\s+", " ", cleaned, flags=re.IGNORECASE)

        # 오디오 관련 스펙
        cleaned = re.sub(r"\b(액티브|노이즈|캔슬링|무선|유선|블루투스|입체음향|돌비)\b", " ", cleaned, flags=re.IGNORECASE)

        # 연결/포트 관련: USB-C/Type-C/C타입은 "C"로 표준화 후 보존
        cleaned = re.sub(r"\b(USB\s*-?\s*C|Type\s*-?\s*C|C\s*타입)\b", " C ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(HDMI|DP|Thunderbolt|3\.5mm|이어폰)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # [수정] "C타입" 같은 케이블/포트 타입은 보존하되, "이어폰"은 제거
    # 따라서 위의 \b(이어폰)\b 제거 로직을 유지하되, C/Type-C 같은 영문 타입 표기는 보존됨
    
    # 상품 상태(공통): 정품/중고 등은 대부분 노이즈
    cleaned = re.sub(r"\b(정품|리퍼|새제품|중고|리뉴얼)\b", " ", cleaned, flags=re.IGNORECASE)

    # 구성/패키지 관련(IT): 옵션 키워드가 검색을 흐리는 경우가 많음
    if is_it:
        cleaned = re.sub(r"\b(패키지|세트|구성|포함|별도|추가)\b", " ", cleaned, flags=re.IGNORECASE)

        # 액세서리 필터(IT)
        cleaned = re.sub(r"\b(케이스|필름|커버|보호|가방|파우치|포우치|스킨|스티커|도킹|거치대)\b", " ", cleaned, flags=re.IGNORECASE)

        # 색상 제거(IT): 일반적으로 식별에 도움 적음. (일반 상품은 색상/라인업명이 될 수 있어 보존)
        cleaned = re.sub(
            r"\b(화이트|블랙|실버|골드|그레이|블루|핑크|레드|그린|퍼플|로즈|샴페인|뉴트럼|차콜|브론즈|건메탈)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
    
    # === Phase 3: 단독 영어 단어 제거 (BasicWhite의 White 같은 것) ===
    # 단독 대문자 영어 토큰 (BB1422SS-N의 N 같은 하나 글자는 제거, 하지만 모델명 보존)
    # N-시리즈 → 제거하되, RTX 4050은 유지
    cleaned = re.sub(r"\b([A-BD-Z])\s+", " ", cleaned)  # 단독 대문자 제거 (C는 USB-C용으로 보존)
    
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
