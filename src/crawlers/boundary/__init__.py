"""HTTP Fast Path 처리 (네트워크, 파싱, 타임아웃)."""

from .timeout_manager import TimeoutManager, TimeoutBudget
from .http_fastpath import DanawaHttpFastPath, FastPathNoResults, FastPathProductFetchFailed
from .http_fastpath_parsing import (
    FastPathResult,
    is_probably_invalid_html,
    is_no_results_html,
    has_search_fingerprint,
    has_product_fingerprint,
    parse_search_pcandidates,
    parse_product_lowest_price,
)

__all__ = [
    "TimeoutManager",
    "TimeoutBudget",
    "DanawaHttpFastPath",
    "FastPathNoResults",
    "FastPathProductFetchFailed",
    "FastPathResult",
    "is_probably_invalid_html",
    "is_no_results_html",
    "has_search_fingerprint",
    "has_product_fingerprint",
    "parse_search_pcandidates",
    "parse_product_lowest_price",
]
