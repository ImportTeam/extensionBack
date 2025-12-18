"""Weighted matching helpers."""

from __future__ import annotations

import re

from src.core.logging import logger
from src.utils.resource_loader import load_matching_variants, load_accessory_keywords

from .signals import extract_product_signals
from .similarity import fuzzy_score
from ..core.tokenize import tokenize_keywords
from ..core.cleaning import clean_product_name, split_kr_en_boundary


def is_accessory_trap(query: str, candidate: str) -> bool:
    if not query or not candidate:
        return False

    resources = load_accessory_keywords()
    accessory_keywords = resources["accessory_keywords"]
    main_product_hints = resources["main_product_hints"]

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

    # 띄어쓰기/붙임 차이를 견디기 위해 공백 제거 버전도 같이 평가
    def _nospace(s: str) -> str:
        s = (s or "").lower()
        s = re.sub(r"\s+", "", s)
        s = re.sub(r"[^0-9a-zA-Z가-힣]", "", s)
        return s

    base = max(
        fuzzy_score(query, candidate),
        fuzzy_score(_nospace(query), _nospace(candidate)),
    )

    q = extract_product_signals(query)
    c = extract_product_signals(candidate)

    score = base

    # [핵심] 제품군(Pro/Air/Max/Mini/Ultra/FE) 불일치 - 강한 필터
    # iPad, iPhone, Galaxy 등 공통 적용
    variants_data = load_matching_variants()
    q_lower = query.lower()
    c_lower = candidate.lower()
    
    q_variants = set()
    c_variants = set()
    
    for v_group in variants_data:
        # v_group은 [standard, synonym1, synonym2, ...] 형태
        if isinstance(v_group, list):
            standard = v_group[0]
            for synonym in v_group:
                if synonym in q_lower:
                    q_variants.add(standard)
                if synonym in c_lower:
                    c_variants.add(standard)
        else:
            # 하위 호환성 (단일 문자열인 경우)
            if v_group in q_lower:
                q_variants.add(v_group)
            if v_group in c_lower:
                c_variants.add(v_group)

    if q_variants or c_variants:
        # 둘 중 하나라도 variant가 있는데 서로 다르면 (Pro vs Air, Pro vs None 등)
        if q_variants != c_variants:
            logger.debug(f"Variant mismatch: query={q_variants} vs candidate={c_variants}")
            score -= 45.0

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
