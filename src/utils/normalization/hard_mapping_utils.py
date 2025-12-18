"""Hard Mapping 내부에서만 쓰는 매칭용 정규화 유틸.

Hard Mapping은 '규칙 기반 강제 변환'이므로,
입력/키를 동일한 규칙으로 정규화한 뒤 매칭해야 안정적으로 동작합니다.
"""

from __future__ import annotations

import re


def normalize_for_hard_mapping_match(text: str) -> str:
    """Hard Mapping 매칭용 정규화.

    - 소문자화
    - 공백 정규화
    - 한글-영문 경계 공백 삽입
    - 특수문자 제거(하이픈/언더스코어는 보존)
    """
    if not text:
        return ""

    normalized = text.lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()

    normalized = re.sub(r"(?<=[\uAC00-\uD7A3])(?=[A-Za-z])", " ", normalized)
    normalized = re.sub(r"(?<=[A-Za-z])(?=[\uAC00-\uD7A3])", " ", normalized)

    normalized = re.sub(r"[^\w\s\-_가-힣]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
