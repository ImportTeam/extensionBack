"""Backward compatible wrapper.

Actual implementation lives in `src.utils.text.utils.prices`.
"""

from .utils.prices import extract_price_from_text

__all__ = [
    "extract_price_from_text",
]
