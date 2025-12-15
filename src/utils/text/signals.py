"""Signal extraction utilities for product matching."""

from __future__ import annotations

import re

from .cleaning import clean_product_name, split_kr_en_boundary


def extract_model_codes(text: str) -> list[str]:
    """상품명에서 모델코드 후보를 추출합니다.

    예: '... BB1422SS-N' -> ['BB1422SS-N']
    """
    if not text:
        return []

    normalized = split_kr_en_boundary(clean_product_name(text))
    tokens = [t for t in normalized.split() if t]

    # (영문+숫자 조합) 또는 (대문자/숫자/하이픈 조합) 형태의 토큰을 모델코드로 간주
    mixed_re = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9][A-Za-z0-9\-_]{2,}$")
    caps_re = re.compile(r"^[A-Z0-9][A-Z0-9\-_]{4,}$")

    blacklist = {
        "WIN10", "WIN11", "WINDOWS", "HOME", "PRO", "SSD", "HDD", "NVME",
        "RAM", "PCIE", "PCIe",
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
    """상품명 매칭에 중요한 '범용' 신호를 추출합니다.

    특정 제품군(예: 맥북/아이폰)에 하드코딩하지 않고, 아래 일반 규칙으로 신호를 뽑습니다.
    - 모델코드(영문+숫자 혼합, 하이픈 포함)
    - 단위가 붙은 숫자(인치/형/cm/mm/GB/TB/Hz/W 등)
    - 3자리 이상 숫자(대개 GPU/제품번호/시리즈 등)
    - 연도(19xx/20xx)
    - '이름 + 번호' 패턴(예: "아이폰 15", "맥북 에어 13")
    """
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

    # 단위가 붙은 숫자 (예: 13인치, 15 형, 256GB, 2.4GHz)
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

    # 3자리 이상 숫자 토큰 (예: 4050, 14900, 9800 등)
    big_numbers = set(re.findall(r"\b\d{3,6}\b", normalized))

    # 이름 + 번호 (1~2단어 이름 뒤에 1~2자리 숫자)
    # 예: "아이폰 15", "맥북 에어 13", "갤럭시 S24"(S24는 분리된 경우만)
    named_numbers: dict[str, set[str]] = {}
    stop_prefix = {
        "win", "windows", "홈", "home", "pro", "프로",
        "정품", "리퍼", "새제품", "중고",
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
