"""Backward compatible wrapper.

Actual implementation lives in `src.utils.text.normalization.resources`.
"""

from .normalization.resources import NormalizationContext, normalize_search_query_with_resources

__all__ = [
    "NormalizationContext",
    "normalize_search_query_with_resources",
]
