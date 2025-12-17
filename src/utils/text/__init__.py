"""Text utilities (modularized).

Public API is kept stable while implementation is organized under:
- core/
- matching/
- normalization/
- utils/
"""

from .core.cleaning import clean_product_name, split_kr_en_boundary
from .core.tokenize import tokenize_keywords
from .matching import (
    calculate_similarity,
    extract_model_codes,
    extract_product_signals,
    fuzzy_score,
    is_accessory_trap,
    weighted_match_score,
)
from .normalization import normalize_search_query
from .utils import extract_price_from_text

__all__ = [
    # core
    "clean_product_name",
    "split_kr_en_boundary",
    "tokenize_keywords",
    # matching/sim
    "fuzzy_score",
    "calculate_similarity",
    "weighted_match_score",
    "is_accessory_trap",
    # signals
    "extract_model_codes",
    "extract_product_signals",
    # normalization
    "normalize_search_query",
    # prices
    "extract_price_from_text",
]
