"""Backward compatible wrapper.

Actual implementation lives in `src.utils.text.matching.signals`.
"""

from .matching.signals import extract_model_codes, extract_product_signals

__all__ = [
    "extract_model_codes",
    "extract_product_signals",
]
