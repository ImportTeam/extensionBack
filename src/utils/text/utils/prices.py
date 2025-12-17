"""Price extraction helpers."""

from __future__ import annotations

import re


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
