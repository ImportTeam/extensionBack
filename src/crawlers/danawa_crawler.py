"""Backward-compatible wrapper for Danawa crawler.

The implementation was modularized under `src/crawlers/danawa/`.
Keep importing `DanawaCrawler` from here to avoid breaking existing code.
"""

from __future__ import annotations

from src.crawlers.danawa.crawler import DanawaCrawler

__all__ = ["DanawaCrawler"]

