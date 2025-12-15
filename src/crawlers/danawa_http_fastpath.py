"""Compatibility wrapper for Danawa HTTP Fast Path.

실제 구현은 [src/crawlers/danawa/http_fastpath.py](src/crawlers/danawa/http_fastpath.py) 및
[src/crawlers/danawa/http_fastpath_parsing.py](src/crawlers/danawa/http_fastpath_parsing.py)로 분리되었습니다.
"""

from src.crawlers.danawa.http_fastpath import DanawaHttpFastPath, FastPathNoResults
from src.crawlers.danawa.http_fastpath_parsing import (
    FastPathResult,
    extract_pcode_from_href,
    has_product_fingerprint,
    has_search_fingerprint,
    is_blocked_html,
    is_no_results_html,
    is_probably_invalid_html,
    parse_product_lowest_price,
    parse_search_pcandidates,
)

__all__ = [
    "DanawaHttpFastPath",
    "FastPathNoResults",
    "FastPathResult",
    "extract_pcode_from_href",
    "has_product_fingerprint",
    "has_search_fingerprint",
    "is_blocked_html",
    "is_no_results_html",
    "is_probably_invalid_html",
    "parse_product_lowest_price",
    "parse_search_pcandidates",
]
