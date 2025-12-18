"""Search query normalization (Hard Mapping + legacy heuristics + UPCS fallback)."""

from __future__ import annotations

import re

from src.core.logging import logger
from src.utils.resource_loader import load_normalization_rules

from ..core.cleaning import clean_product_name, split_kr_en_boundary


def normalize_search_query(text: str, skip_hard_mapping: bool = False) -> str:
    """외부 쇼핑몰 상품명을 다나와 검색에 적합하게 정규화합니다.
    
    📋 정규화 파이프라인 (우선순위 순):
    
    0 Level 0: Hard Mapping (강제 변환, 즉시 반환)
        └─ 5단계: 액세서리필터 → 정규화 → 매핑 → 검증 → 반환
        └─ ⚠️ 멱등성: 이미 Hard Mapping된 결과는 재실행 금지
    
    1 Level 1: UPCS 기반 정규화
        └─ 설정 기반 정규화 시도
    
    2 Level 2: 레거시 휴리스틱
        └─ IT/비IT 분류 → 노이즈 제거
    
    Args:
        text: 정규화할 검색어
        skip_hard_mapping: True → Hard Mapping 스킵 (이미 Hard Mapped된 결과)
    """
    if not text:
        return ""

    # 🔴 Level 0: Hard Mapping (가장 우선)
    # Rule 3: Execution Stage 0 - 모든 단계보다 먼저 실행
    # 💡 Idempotency: skip_hard_mapping=True면 Hard Mapping 재실행 금지
    if not skip_hard_mapping:
        try:
            from .hard_mapping_stage import apply_hard_mapping_complete
            
            hard_mapped = apply_hard_mapping_complete(text)
            if hard_mapped:
                logger.info(f"[normalize] Level 0 Hard Mapping SUCCESS: '{text}' → '{hard_mapped}'")
                # 🎯 Hard Mapping 성공 시 UPCS/Legacy 스킵 (멱등성 유지)
                return hard_mapped
        except Exception as e:
            logger.debug(f"[normalize] Level 0 Hard Mapping error: {type(e).__name__}: {e}")
    else:
        logger.debug(f"[normalize] Skipping Level 0 Hard Mapping (already hard-mapped)")

    # 🟡 Level 1: UPCS 기반 정규화
    try:
        from src.upcs.normalizer import normalize_query

        normalized = normalize_query(text, vendor="danawa")
        if normalized:
            logger.debug(f"[normalize] Level 1 UPCS normalization: '{text}' → '{normalized}'")
            return str(normalized)
    except Exception as e:
        logger.debug(f"[normalize] Level 1 UPCS fallback: {type(e).__name__}: {e}")

    # 🟢 Level 2: 레거시 휴리스틱
    logger.debug(f"[normalize] Falling back to Level 2 legacy heuristics")
    return _normalize_search_query_legacy(text)


def _normalize_search_query_legacy(text: str) -> str:
    """레거시 휴리스틱 정규화(설정 로딩 실패 시 폴백)."""
    if not text:
        return ""

    # 리소스 로드
    it_rules = load_normalization_rules(is_it=True)
    non_it_rules = load_normalization_rules(is_it=False)

    def is_likely_it_query(value: str) -> bool:
        if not value:
            return False

        v = value.lower()
        non_it_strong = non_it_rules.get("non_it_strong", [])
        it_signals = it_rules.get("it_signals", [])

        score = 0
        if any(w in v for w in non_it_strong):
            score -= 3
        if any(w in v for w in it_signals):
            score += 2
        
        # 용량/단위 패턴
        if re.search(r"\b\d+\s*(gb|tb|mb|khz|mhz|ghz|hz)\b", v):
            score += 2
        # M칩 패턴
        if re.search(r"\b(m\s*\d+)\b", v, flags=re.IGNORECASE):
            score += 2
        # 그래픽카드 패턴
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

    # 🔴 기가차드 수정: "블루투스" -> "투스" 방지를 위한 보호 로직
    protected_terms = {"블루투스": "__BT_PROTECT__", "블랙박스": "__BB_PROTECT__"}
    for term, protect in protected_terms.items():
        cleaned = cleaned.replace(term, protect)

    # 색상 분리 (리소스에서 로드)
    colors = "|".join(it_rules.get("colors", []))
    if colors:
        cleaned = re.sub(f"({colors})([가-힣])", r"\1 \2", cleaned)

    # 보호 토큰 복구
    for term, protect in protected_terms.items():
        cleaned = cleaned.replace(protect, term)

    cleaned = re.sub(r"([가-힣])([A-Z])", r"\1 \2", cleaned)

    if is_it:
        # 용량 및 규격 제거
        units = "|".join(it_rules.get("storage_units", ["GB", "TB", "MB"]))
        cleaned = re.sub(rf"\b\d+\s*({units})\b", " ", cleaned, flags=re.IGNORECASE)
        
        specs = "|".join(it_rules.get("storage_specs", []))
        if specs:
            cleaned = re.sub(rf"\b({specs})\b", " ", cleaned, flags=re.IGNORECASE)

    if is_it:
        # 🔴 기가차드 수정: OS 에디션으로서의 Pro/Home만 제거 (iPhone Pro 등 보호)
        os_names = "|".join(it_rules.get("operating_systems", ["Windows", "Win"]))
        cleaned = re.sub(
            rf"\b({os_names})\s*(HOME|PRO|Home|Pro)\b",
            r"\1",
            cleaned,
            flags=re.IGNORECASE,
        )
        # 단독 OS 이름 제거
        cleaned = re.sub(rf"\b({os_names})\b", " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\b(\d+)\s*세대\b", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b세대\b", " ", cleaned, flags=re.IGNORECASE)
    
    if is_it:
        cpu_brands = "|".join(it_rules.get("cpu_brands", ["인텔", "라이젠", "AMD"]))
        cleaned = re.sub(rf"\b({cpu_brands})\s+\d+", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b시리즈\b", " ", cleaned, flags=re.IGNORECASE)

    # 공통 노이즈 제거 (정품, 리퍼 등)
    conditions = "|".join(non_it_rules.get("product_conditions", []))
    if conditions:
        cleaned = re.sub(rf"\b({conditions})\b", " ", cleaned, flags=re.IGNORECASE)

    if is_it:
        # 기능, 포트, 액세서리 제거
        features = "|".join(it_rules.get("it_features", []))
        if features:
            cleaned = re.sub(rf"\b({features})\b", " ", cleaned, flags=re.IGNORECASE)
            
        ports = "|".join(it_rules.get("port_types", []))
        if ports:
            cleaned = re.sub(rf"\b({ports})\b", " ", cleaned, flags=re.IGNORECASE)
            
        accessories = "|".join(it_rules.get("it_accessories", []))
        if accessories:
            cleaned = re.sub(rf"\b({accessories})\b", " ", cleaned, flags=re.IGNORECASE)

        # 색상 제거
        if colors:
            cleaned = re.sub(rf"\b({colors})\b", " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\b([A-BD-Z])\s+", " ", cleaned)

    # 숫자+단위 조합 제거
    cleaned = re.sub(
        r"\b\d{1,2}\b(?=\s*(코어|core|스레드|thread|와트|w|hz|Hz|GHz|MHz)\b)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned
