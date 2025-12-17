"""Matching package.

Public surface stays compatible with the old `src.utils.text.matching` module.
"""

from .matching import is_accessory_trap, weighted_match_score
from .signals import extract_model_codes, extract_product_signals
from .similarity import calculate_similarity, fuzzy_score
from ..normalization.normalize import normalize_search_query

__all__ = [
    "is_accessory_trap",
    "weighted_match_score",
    "extract_model_codes",
    "extract_product_signals",
    "calculate_similarity",
    "fuzzy_score",
    "normalize_search_query",
]
