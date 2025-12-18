"""Utilities package - Flat structure (no nested directories)

베스트 프랙티스:
- Google Python Style Guide: 한 모듈에 여러 클래스/함수 가능
- FastAPI Best Practices: Flat is better than nested
- Python Zen: Simple is better than complex
"""

# Hash utilities
from .hash_utils import hash_string, generate_cache_key, generate_negative_cache_key

# URL utilities
from .url_utils import extract_pcode_from_url, normalize_href

# Search helper
from .search.search_optimizer import DanawaSearchHelper

# Text utilities (통합 완료)
from .text_utils import (
    clean_product_name,
    split_kr_en_boundary,
    tokenize_keywords,
    fuzzy_score,
    calculate_similarity,
    weighted_match_score,
    is_accessory_trap,
    extract_model_codes,
    extract_product_signals,
    extract_price_from_text,
    build_cache_key,
    normalize_for_search_query,
)

# Normalization (복잡해서 별도 디렉토리 유지)
from .normalization import normalize_search_query

__all__ = [
    # hash
    "hash_string",
    "generate_cache_key",
    "generate_negative_cache_key",
    # url
    "extract_pcode_from_url",
    "normalize_href",
    # search
    "DanawaSearchHelper",
    # text
    "clean_product_name",
    "split_kr_en_boundary",
    "tokenize_keywords",
    "fuzzy_score",
    "calculate_similarity",
    "weighted_match_score",
    "is_accessory_trap",
    "extract_model_codes",
    "extract_product_signals",
    "extract_price_from_text",
    "build_cache_key",
    "normalize_for_search_query",
    # normalization
    "normalize_search_query",
]
