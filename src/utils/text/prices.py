"""Price extraction helpers."""

from __future__ import annotations

import re


def extract_price_from_text(price_text: str) -> int:
    """
    가격 텍스트에서 숫자만 추출
    
    예시:
    - "1,250,000원" -> 1250000
    - "450,000" -> 450000
    - "판매가: 1,500,000원" -> 1500000
    
    Args:
        price_text: 가격이 포함된 텍스트
        
    Returns:
        추출된 가격 (정수)
    """
    if not price_text:
        return 0
    
    # 숫자와 쉼표만 추출
    numbers = re.findall(r'[\d,]+', price_text)
    
    if not numbers:
        return 0
    
    # 가장 긴 숫자 문자열 선택 (보통 가격이 가장 긴 숫자)
    price_str = max(numbers, key=len)
    
    # 쉼표 제거 후 정수 변환
    try:
        return int(price_str.replace(',', ''))
    except ValueError:
        return 0
