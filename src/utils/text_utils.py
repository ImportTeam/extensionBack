"""텍스트 처리 유틸리티 - 통합 모듈

이전 구조:
- text/core/cleaning.py
- text/core/tokenize.py  
- text/matching/similarity.py
- text/matching/matching.py
- text/matching/signals.py
- text/utils/prices.py

→ 모두 text_utils.py로 통합
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from src.core.logging import logger
from src.utils.resource_loader import (
    load_search_categories,
    load_matching_variants,
    load_accessory_keywords,
    load_matching_signals,
)


# ==================== Core: 기본 정제 함수 ====================

def clean_product_name(product_name: str) -> str:
    """
    상품명에서 불필요한 특수문자, 괄호 안의 내용 제거
    
    예시:
    - "[카드할인] 삼성 오디세이 G5" -> "삼성 오디세이 G5"
    - "아이폰 15 프로 (자급제)" -> "아이폰 15 프로"
    
    Args:
        product_name: 원본 상품명
        
    Returns:
        정제된 상품명
    """
    if not product_name:
        return ""

    def _extract_m_chips(text: str) -> list[str]:
        # 'M5', 'm5', 'M5모델' 등 다양한 표기를 모두 포착
        chips = []
        for m in re.finditer(r"(?i)M\s*(\d+)", text or ""):
            n = m.group(1)
            if n:
                chips.append(f"M{n}")
        # 중복 제거 (순서 유지)
        seen: set[str] = set()
        out: list[str] = []
        for c in chips:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _preserve_important_tokens(match: re.Match[str]) -> str:
        inner = match.group(1) or ""
        chips = _extract_m_chips(inner)
        if not chips:
            return " "
        return " " + " ".join(chips) + " "

    # 대괄호/소괄호 내용은 보통 옵션/노이즈지만, 칩셋(M1~) 같은 핵심 토큰은 보존
    cleaned = re.sub(r"\[(.*?)\]", _preserve_important_tokens, product_name)
    cleaned = re.sub(r"\((.*?)\)", _preserve_important_tokens, cleaned)
    
    # 특수문자 제거 (하이픈, 언더스코어는 유지)
    cleaned = re.sub(r'[^\w\s\-_가-힣]', '', cleaned)
    
    # 다중 공백을 단일 공백으로
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()


def split_kr_en_boundary(text: str) -> str:
    """
    한글과 영어/숫자가 붙어 있는 경우 경계에 공백을 삽입합니다.

    예: 'N-시리즈BasicWhite' -> 'N-시리즈 BasicWhite'
    """
    if not text:
        return text

    normalized = re.sub(r'(?<=[\uAC00-\uD7A3])(?=[A-Za-z0-9])', ' ', text)
    normalized = re.sub(r'(?<=[A-Za-z0-9])(?=[\uAC00-\uD7A3])', ' ', normalized)
    # collapse multi spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()


# Kiwi 인스턴스 (lazy loading)
_KIWI_INSTANCE = None


def _get_kiwi():
    """Kiwi 토크나이저를 lazy loading으로 가져옵니다."""
    global _KIWI_INSTANCE
    if _KIWI_INSTANCE is not None:
        return _KIWI_INSTANCE

    try:
        from kiwipiepy import Kiwi
        _KIWI_INSTANCE = Kiwi()
        return _KIWI_INSTANCE
    except Exception:
        _KIWI_INSTANCE = None
        return None


def tokenize_keywords(text: str) -> set[str]:
    """검색/매칭용 키워드 토큰화.

    - Kiwi 사용 가능: 명사/영문/숫자 위주로 토큰화
    - 불가: 정규식 기반 폴백
    """
    if not text:
        return set()

    cleaned = split_kr_en_boundary(clean_product_name(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return set()

    kiwi = _get_kiwi()
    if kiwi is not None:
        try:
            results = kiwi.tokenize(cleaned)
            tokens = set()
            for token in results:
                form = token.form
                tag = token.tag
                if tag in ("NNG", "NNP", "NNB", "SL", "SN", "MAG", "VA", "VV", "XR"):
                    tokens.add(form)
                elif re.match(r"[A-Za-z0-9]+", form):
                    tokens.add(form)
            return tokens
        except Exception:
            pass

    # Fallback: 정규식
    words = re.findall(r"[가-힣A-Za-z0-9]+", cleaned)
    return set(w for w in words if len(w) >= 2 or w.isdigit())


# ==================== Matching: 유사도 & 매칭 ====================


@dataclass
class MatchDecision:
    """상품명 매칭 판정 결과."""

    score: float
    accepted: bool
    required_hits: list[str]
    required_missing: list[str]
    forbidden_hits: list[str]
    reason: str
    query_signals: dict
    candidate_signals: dict

def calculate_similarity(text1: str, text2: str) -> float:
    """두 텍스트의 유사도를 계산 (폴백).

    rapidfuzz가 없는 환경에서:
    - 한국어 띄어쓰기/붙임(예: '맥북 에어' vs '맥북에어')
    - 한글/숫자/영문 경계(예: '에어13' vs '에어 13')
    를 견딜 수 있도록 토큰 Jaccard + 공백무시 bigram Jaccard를 혼합합니다.
    """
    if not text1 or not text2:
        return 0.0

    def _prep(text: str) -> str:
        t = split_kr_en_boundary(clean_product_name(text))
        t = re.sub(r"\s+", " ", t).strip().lower()
        return t

    def _nospace(text: str) -> str:
        # 공백/탭 제거 + 비교에 방해되는 문장부호 제거
        t = re.sub(r"\s+", "", text)
        t = re.sub(r"[^0-9a-zA-Z가-힣]", "", t)
        return t

    def _bigrams(s: str) -> set[str]:
        if not s:
            return set()
        if len(s) == 1:
            return {s}
        return {s[i : i + 2] for i in range(len(s) - 1)}

    p1 = _prep(text1)
    p2 = _prep(text2)

    words1 = set(p1.split())
    words2 = set(p2.split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    token_sim = len(intersection) / len(union) if union else 0.0

    # 토큰 기반이 약한(붙임/띄어쓰기 차이) 경우를 보완
    ns1 = _nospace(p1)
    ns2 = _nospace(p2)
    # 너무 짧은 문자열의 포함 판정은 과매칭 위험 → 길이 조건
    if min(len(ns1), len(ns2)) >= 6 and (ns1 in ns2 or ns2 in ns1):
        ns_sim = 0.98
    else:
        b1 = _bigrams(ns1)
        b2 = _bigrams(ns2)
        b_union = b1.union(b2)
        ns_sim = (len(b1.intersection(b2)) / len(b_union)) if b_union else 0.0

    # 경험적으로 token_sim이 안정적이고 ns_sim이 회복용이므로 가중 평균
    return max(token_sim, ns_sim * 0.85)


def fuzzy_score(query: str, candidate: str) -> float:
    """두 문자열의 유사도 점수(0~100).

    rapidfuzz가 설치되어 있으면 WRatio를 사용하고,
    없으면 기존 calculate_similarity를 사용합니다.
    """
    if not query or not candidate:
        return 0.0

    try:
        from rapidfuzz import fuzz, utils
        return float(fuzz.WRatio(query, candidate, processor=utils.default_process))
    except Exception:
        return calculate_similarity(query, candidate) * 100.0


def is_accessory_trap(query: str, candidate: str) -> bool:
    """액세서리 오탐 감지 (케이스, 필름 등)"""
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


def _normalize_for_matching(text: str) -> str:
    normalized = split_kr_en_boundary(clean_product_name(text or ""))
    normalized = normalized.lower()
    normalized = normalized.replace("애플", "apple")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _detect_variants(text: str) -> set[str]:
    lowered = _normalize_for_matching(text)
    detected: set[str] = set()
    for group in load_matching_variants():
        if isinstance(group, list):
            standard = str(group[0]).lower()
            for synonym in group:
                if str(synonym).lower() in lowered:
                    detected.add(standard)
        else:
            token = str(group).lower()
            if token in lowered:
                detected.add(token)
    return detected


def _detect_interfaces(text: str) -> set[str]:
    lowered = _normalize_for_matching(text)
    interfaces: set[str] = set()
    if "usb-c" in lowered or "usbc" in lowered or "c타입" in lowered or "type-c" in lowered:
        interfaces.add("usb-c")
    if "lightning" in lowered or "라이트닝" in lowered:
        interfaces.add("lightning")
    return interfaces


def _detect_categories(text: str) -> set[str]:
    lowered = _normalize_for_matching(text)
    categories = load_search_categories()
    hits: set[str] = set()
    for category, info in categories.items():
        pattern = str(info.get("pattern", "")).strip()
        if pattern and re.search(pattern, lowered, re.IGNORECASE):
            hits.add(category)
            continue
        for keyword in info.get("keywords", []):
            if str(keyword).lower() in lowered:
                hits.add(category)
                break
    return hits


def _detect_generations(normalized_text: str, named_numbers: dict[str, set[str]]) -> set[str]:
    generations = {f"{num}세대" for num in re.findall(r"\b(\d{1,2})\s*세대\b", normalized_text)}
    for values in named_numbers.values():
        for value in values:
            generations.add(value)
    return generations


def _resolve_non_main_hits(query: str, candidate: str) -> list[str]:
    resources = load_accessory_keywords()
    query_normalized = _normalize_for_matching(query)
    candidate_normalized = _normalize_for_matching(candidate)
    query_categories = _detect_categories(query)

    forbidden_pool = set(resources.get("non_main_product_keywords", set()))
    for category in query_categories:
        forbidden_pool.update(resources.get("category_non_main_keywords", {}).get(category, set()))

    if any(_normalize_for_matching(keyword) in query_normalized for keyword in forbidden_pool):
        return []

    hits = []
    for keyword in forbidden_pool:
        normalized_keyword = _normalize_for_matching(keyword)
        if not normalized_keyword:
            continue
        if normalized_keyword in candidate_normalized and normalized_keyword not in query_normalized:
            hits.append(keyword)

    unique_hits: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        key = hit.lower()
        if key not in seen:
            seen.add(key)
            unique_hits.append(hit)
    return unique_hits


def _base_weighted_match_score(query: str, candidate: str) -> float:
    """기존 가중치 점수 계산."""
    if not query or not candidate:
        return 0.0

    if is_accessory_trap(query, candidate):
        return 0.0

    def _nospace(s: str) -> str:
        s = (s or "").lower()
        s = s.replace("년형", "").replace("년식", "")
        s = s.replace("애플", "apple")
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

    if q["variants"] or c["variants"]:
        if q["variants"] != c["variants"]:
            logger.debug(f"Variant mismatch: query={q['variants']} vs candidate={c['variants']}")
            score -= 45.0

    m_chip_pattern = r"(?i)M\s*(\d+)"
    q_chips = set(re.findall(m_chip_pattern, query))
    c_chips = set(re.findall(m_chip_pattern, candidate))
    if q_chips and c_chips and q_chips != c_chips:
        logger.debug(f"Chip mismatch (disqualify): query={q_chips} vs candidate={c_chips}")
        return 0.0
    if q_chips and c_chips and q_chips == c_chips:
        score += 5.0

    screen_size_pattern = r"\b(10|11|12|13|14|15|16|17)(?:\s*인치|\s*inch|\s*\")?"
    q_screens = set(re.findall(screen_size_pattern, query, re.IGNORECASE))
    c_screens = set(re.findall(screen_size_pattern, candidate, re.IGNORECASE))
    if q_screens and c_screens and q_screens != c_screens:
        logger.debug(f"Screen size mismatch (disqualify): query={q_screens} vs candidate={c_screens}")
        return 0.0
    if q_screens and c_screens and q_screens == c_screens:
        score += 3.0

    for unit_q in q["unit_numbers"]:
        if unit_q not in c["unit_numbers"]:
            score -= 10.0

    if q["years"] and c["years"] and q["years"] != c["years"]:
        score -= 15.0

    if q["model_codes"] and c["model_codes"]:
        if q["model_codes"].intersection(c["model_codes"]):
            score += 20.0
        else:
            score -= 20.0

    return max(0.0, score)


def evaluate_match(query: str, candidate: str, *, min_score: float = 35.0) -> MatchDecision:
    """필수 신호/금지 신호를 반영한 매칭 판정."""
    if not query or not candidate:
        return MatchDecision(
            score=0.0,
            accepted=False,
            required_hits=[],
            required_missing=["invalid_input"],
            forbidden_hits=[],
            reason="invalid_input",
            query_signals={},
            candidate_signals={},
        )

    q_signals = extract_product_signals(query)
    c_signals = extract_product_signals(candidate)
    required_hits: list[str] = []
    required_missing: list[str] = []

    forbidden_hits = _resolve_non_main_hits(query, candidate)
    if forbidden_hits:
        return MatchDecision(
            score=0.0,
            accepted=False,
            required_hits=required_hits,
            required_missing=required_missing,
            forbidden_hits=forbidden_hits,
            reason="forbidden_non_main_product",
            query_signals=q_signals,
            candidate_signals=c_signals,
        )

    if q_signals["variants"]:
        if q_signals["variants"].issubset(c_signals["variants"]):
            required_hits.extend(sorted(f"variant:{value}" for value in q_signals["variants"]))
        else:
            required_missing.extend(sorted(f"variant:{value}" for value in q_signals["variants"] - c_signals["variants"]))

    if q_signals["interfaces"]:
        if q_signals["interfaces"].issubset(c_signals["interfaces"]):
            required_hits.extend(sorted(f"interface:{value}" for value in q_signals["interfaces"]))
        else:
            required_missing.extend(sorted(f"interface:{value}" for value in q_signals["interfaces"] - c_signals["interfaces"]))

    if q_signals["years"] and c_signals["years"]:
        if q_signals["years"].issubset(c_signals["years"]):
            required_hits.extend(sorted(f"year:{value}" for value in q_signals["years"]))
        else:
            required_missing.extend(sorted(f"year:{value}" for value in q_signals["years"] - c_signals["years"]))

    for key, values in q_signals["named_numbers"].items():
        candidate_values = c_signals["named_numbers"].get(key, set())
        if values and values.issubset(candidate_values):
            required_hits.extend(sorted(f"named:{key}:{value}" for value in values))
        elif values:
            required_missing.extend(sorted(f"named:{key}:{value}" for value in values - candidate_values))

    generation_required_categories = {"earphone", "phone", "tablet"}
    if q_signals["generations"] and q_signals["categories"].intersection(generation_required_categories):
        if q_signals["generations"].intersection(c_signals["generations"]):
            required_hits.extend(sorted(f"generation:{value}" for value in q_signals["generations"].intersection(c_signals["generations"])))
        else:
            required_missing.extend(sorted(f"generation:{value}" for value in q_signals["generations"]))

    if required_missing:
        return MatchDecision(
            score=0.0,
            accepted=False,
            required_hits=required_hits,
            required_missing=required_missing,
            forbidden_hits=[],
            reason="missing_required_signals",
            query_signals=q_signals,
            candidate_signals=c_signals,
        )

    score = _base_weighted_match_score(query, candidate)
    accepted = score >= min_score
    reason = "accepted" if accepted else "low_score"
    return MatchDecision(
        score=score,
        accepted=accepted,
        required_hits=required_hits,
        required_missing=[],
        forbidden_hits=[],
        reason=reason,
        query_signals=q_signals,
        candidate_signals=c_signals,
    )


def weighted_match_score(query: str, candidate: str) -> float:
    """가중치 매칭 스코어 (신호 기반 보정)"""
    return evaluate_match(query, candidate).score


# ==================== Signals: 신호 추출 ====================

def extract_model_codes(text: str) -> list[str]:
    """상품명에서 모델코드 후보를 추출합니다.

    예: '... BB1422SS-N' -> ['BB1422SS-N']
    """
    if not text:
        return []

    normalized = split_kr_en_boundary(clean_product_name(text))
    tokens = [t for t in normalized.split() if t]

    mixed_re = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9][A-Za-z0-9\-_]{2,}$")
    caps_re = re.compile(r"^[A-Z0-9][A-Z0-9\-_]{4,}$")

    signals = load_matching_signals()
    blacklist = signals["model_code_blacklist"]

    codes: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if tok in blacklist:
            continue
        if mixed_re.match(tok) or caps_re.match(tok):
            if tok not in seen:
                seen.add(tok)
                codes.append(tok)

    return codes


def extract_product_signals(text: str) -> dict:
    """상품명 매칭에 중요한 '범용' 신호를 추출합니다."""
    if not text:
        return {
            "years": set(),
            "model_codes": set(),
            "unit_numbers": set(),
            "big_numbers": set(),
            "named_numbers": {},
            "variants": set(),
            "interfaces": set(),
            "categories": set(),
            "generations": set(),
        }

    normalized = split_kr_en_boundary(clean_product_name(text))

    years = set(int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", normalized))

    model_codes = set(extract_model_codes(normalized))

    unit_numbers: set[str] = set()
    unit_patterns = [
        r"\b\d{1,3}(?:\.\d+)?\s*(?:인치|inch|\"|형)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:GB|TB|MB|KB)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:Hz|kHz|MHz|GHz)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:W|w)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:cm|mm)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:kg|g)\b",
    ]
    for pat in unit_patterns:
        for m in re.findall(pat, normalized, flags=re.IGNORECASE):
            unit_numbers.add(re.sub(r"\s+", "", m).lower())

    big_numbers = set(re.findall(r"\b\d{3,6}\b", normalized))

    named_numbers: dict[str, set[str]] = {}
    signals = load_matching_signals()
    stop_prefix = signals["named_number_stop_prefixes"]
    generic_named_number_prefixes = {
        "인텔", "intel", "코어", "core", "지포스", "geforce", "rtx", "gtx", "라이젠", "ryzen"
    }
    
    for name, num in re.findall(
        r"\b([A-Za-z가-힣]{2,}(?:\s+[A-Za-z가-힣]{2,})?)\s*(\d{1,2})\b",
        normalized,
    ):
        key = re.sub(r"\s+", " ", name).strip().lower()
        if not key or key in stop_prefix or key in generic_named_number_prefixes:
            continue
        named_numbers.setdefault(key, set()).add(num)

    return {
        "years": years,
        "model_codes": model_codes,
        "unit_numbers": unit_numbers,
        "big_numbers": big_numbers,
        "named_numbers": named_numbers,
        "variants": _detect_variants(normalized),
        "interfaces": _detect_interfaces(normalized),
        "categories": _detect_categories(normalized),
        "generations": _detect_generations(normalized, named_numbers),
    }


def parse_fe_options_text(options_text: str) -> list[tuple[str, str]]:
    """FE에서 전달된 options 문자열을 (key, value) 쌍으로 파싱.

    지원 포맷 예:
    - "색상: 스페이스 블랙"
    - "CPU 모델명 × GPU 모델명 × RAM용량 × 저장용량 × 키보드 언어: M5 10코어 × 10코어 × 16GB × 512GB × 한글"
    - 위 두 포맷이 ","로 함께 들어오는 케이스
    """
    if not options_text:
        return []

    text = re.sub(r"\s+", " ", str(options_text)).strip()
    if not text:
        return []

    pairs: list[tuple[str, str]] = []

    # 쉼표로 1차 분리
    parts = [p.strip() for p in text.split(",") if p.strip()]
    for part in parts:
        if ":" not in part:
            continue

        left, right = part.split(":", 1)
        left = left.strip()
        right = right.strip()

        # 단일 key:value
        if "×" not in left and "×" not in right:
            if left and right:
                pairs.append((left, right))
            continue

        # 다중 키/값: keys "×" values
        keys = [k.strip() for k in left.split("×") if k.strip()]
        values = [v.strip() for v in right.split("×") if v.strip()]

        for k, v in zip(keys, values):
            if k and v:
                pairs.append((k, v))

    return pairs


def build_option_query_tokens(
    selected_pairs: list[tuple[str, str]],
    *,
    max_tokens: int = 10,
) -> list[str]:
    """signals.yaml 규칙을 기반으로 옵션 쌍을 검색 쿼리 토큰으로 변환."""
    if not selected_pairs:
        return []

    signals = load_matching_signals()
    allow_keys: set[str] = set(signals.get("option_keys_allowlist", set()))
    deny_keys: set[str] = set(signals.get("option_keys_denylist", set()))
    value_blacklist: set[str] = set(signals.get("option_value_blacklist_terms", set()))
    drop_regex: list[str] = list(signals.get("option_value_drop_regex", []))

    compiled = []
    for pat in drop_regex:
        try:
            compiled.append(re.compile(pat))
        except re.error:
            continue

    tokens: list[str] = []
    seen: set[str] = set()

    for key, value in selected_pairs:
        k = re.sub(r"\s+", " ", str(key)).strip()
        v = re.sub(r"\s+", " ", str(value)).strip()
        if not k or not v:
            continue

        # 키 denylist
        if any(d in k for d in deny_keys):
            continue

        # 키 allowlist (비어있으면 allow-all)
        if allow_keys and k not in allow_keys:
            continue

        # 값 블랙리스트/정규식
        lower_v = v.lower()
        if any(term in v for term in value_blacklist):
            continue
        if any(rx.search(v) for rx in compiled):
            continue

        # 값 정리: 불필요한 구두점/공백 정리
        v_norm = v.replace("·", " ")
        v_norm = re.sub(r"\s+", " ", v_norm).strip()
        # 색상 등은 공백 제거한 형태도 검색 성능이 좋아서 같이 맞춰줌
        if k in {"색상"}:
            v_norm = v_norm.replace(" ", "")

        # 다나와 상품명에는 보통 '저장용량:512GB'처럼 키가 안 붙고 값만 등장
        # → 검색 토큰은 값 중심으로 사용
        token = v_norm
        if token.lower() in seen:
            continue
        seen.add(token.lower())
        tokens.append(token)
        if len(tokens) >= max_tokens:
            break

    return tokens


# ==================== Utils: 가격 추출 ====================

def extract_price_from_text(price_text: str) -> int:
    """가격 텍스트에서 숫자만 추출."""
    if not price_text:
        return 0

    numbers = re.findall(r"[\d,]+", price_text)

    if not numbers:
        return 0

    price_str = max(numbers, key=len)

    try:
        return int(price_str.replace(",", ""))
    except ValueError:
        return 0


# ==================== 추가 함수 (누락된 함수들) ====================

def build_cache_key(product_name: str) -> str:
    """캐시 키 생성 (정규화된 상품명 기반)
    
    Note: 이 함수는 clean_product_name의 alias입니다.
    orchestrator.py와 price_search_service.py에서 사용됩니다.
    """
    return clean_product_name(product_name)


def normalize_for_search_query(product_name: str) -> str:
    """검색 쿼리용 정규화 (간단한 버전)
    
    Note: 전체 정규화는 normalize_search_query를 사용하세요.
    이 함수는 간단한 정제만 수행합니다.
    """
    return clean_product_name(product_name)


# ==================== Export ====================

__all__ = [
    # Core
    "clean_product_name",
    "split_kr_en_boundary",
    "tokenize_keywords",
    # Matching
    "calculate_similarity",
    "fuzzy_score",
    "is_accessory_trap",
    "evaluate_match",
    "MatchDecision",
    "weighted_match_score",
    # Signals
    "extract_model_codes",
    "extract_product_signals",
    # Utils
    "extract_price_from_text",
    # 추가 (누락된 함수)
    "build_cache_key",
    "normalize_for_search_query",
]
