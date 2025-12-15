"""텍스트 처리 유틸리티

Backward compatible wrapper.
The actual implementations live in `src/utils/text/*`.
"""

from __future__ import annotations

from .text.cleaning import clean_product_name, split_kr_en_boundary
from .text.matching import is_accessory_trap, normalize_search_query, weighted_match_score
from .text.prices import extract_price_from_text
from .text.signals import extract_model_codes, extract_product_signals
from .text.similarity import calculate_similarity, fuzzy_score
from .text.tokenize import _KIWI_INSTANCE, _get_kiwi, tokenize_keywords

__all__ = [
    "_KIWI_INSTANCE",
    "_get_kiwi",
    "tokenize_keywords",
    "clean_product_name",
    "split_kr_en_boundary",
    "extract_price_from_text",
    "calculate_similarity",
    "normalize_search_query",
    "extract_model_codes",
    "fuzzy_score",
    "extract_product_signals",
    "is_accessory_trap",
    "weighted_match_score",
]
