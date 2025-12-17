"""Backward compatible wrapper.

Actual implementation lives in `src.utils.text.normalization.kiwi`.
"""

from .normalization.kiwi import normalize_search_query_kiwi

__all__ = [
    "normalize_search_query_kiwi",
]
