"""Signal extraction utilities for product matching."""

from __future__ import annotations

import re

from ..core.cleaning import clean_product_name, split_kr_en_boundary


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

    blacklist = {
        "WIN10",
        "WIN11",
        "WINDOWS",
        "HOME",
        "PRO",
        "SSD",
        "HDD",
        "NVME",
        "RAM",
        "PCIE",
        "PCIe",
    }

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
    stop_prefix = {
        "win",
        "windows",
        "홈",
        "home",
        "pro",
        "프로",
        "정품",
        "리퍼",
        "새제품",
        "중고",
    }
    for name, num in re.findall(
        r"\b([A-Za-z가-힣]{2,}(?:\s+[A-Za-z가-힣]{2,})?)\s*(\d{1,2})\b",
        normalized,
    ):
        key = re.sub(r"\s+", " ", name).strip().lower()
        if not key or key in stop_prefix:
            continue
        named_numbers.setdefault(key, set()).add(num)

    return {
        "years": years,
        "model_codes": model_codes,
        "unit_numbers": unit_numbers,
        "big_numbers": big_numbers,
        "named_numbers": named_numbers,
    }
