"""Text cleaning helpers."""

from __future__ import annotations

import re


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

    import re
    normalized = re.sub(r'(?<=[\uAC00-\uD7A3])(?=[A-Za-z0-9])', ' ', text)
    normalized = re.sub(r'(?<=[A-Za-z0-9])(?=[\uAC00-\uD7A3])', ' ', normalized)
    # collapse multi spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()
