"""Backward-compatible import shim.

기존 코드/테스트에서 `from src.utils.text import ...` 를 사용하던 경로를
현재 구현으로 매핑합니다.
"""

from __future__ import annotations

from .text_utils import *  # noqa: F403
from .normalization.normalize import normalize_search_query  # noqa: F401
