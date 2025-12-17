"""Backward compatible wrapper.

Actual implementation lives in `src.utils.text.core.tokenize`.
"""

from .core.tokenize import _KIWI_INSTANCE, _get_kiwi, tokenize_keywords

__all__ = [
    "_KIWI_INSTANCE",
    "_get_kiwi",
    "tokenize_keywords",
]
