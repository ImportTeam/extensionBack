"""Backward compatible wrapper.

Actual implementation lives in `src.utils.text.matching.similarity`.
"""

from .matching.similarity import calculate_similarity, fuzzy_score

__all__ = [
    "calculate_similarity",
    "fuzzy_score",
]
