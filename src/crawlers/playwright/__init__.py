"""Playwright module for Danawa crawler."""

from .browser import ensure_shared_browser, shutdown_shared_browser, warmup, new_page
from .pages import configure_page

__all__ = [
    "ensure_shared_browser",
    "shutdown_shared_browser",
    "warmup",
    "new_page",
    "configure_page",
]
