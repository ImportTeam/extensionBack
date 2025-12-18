"""Backward-compatible import shim.

기존 코드/테스트에서 `from src.utils.url import ...` 를 사용하던 경로를
`src.utils.url_utils`로 매핑합니다.

새 코드는 `src.utils.url_utils`를 직접 import 해주세요.
"""

from __future__ import annotations

from .url_utils import *  # noqa: F403
