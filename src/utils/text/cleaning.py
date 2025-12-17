"""Backward compatible wrapper.

Actual implementation lives in `src.utils.text.core.cleaning`.
"""

from .core.cleaning import clean_product_name, split_kr_en_boundary

__all__ = [
    "clean_product_name",
    "split_kr_en_boundary",
]
