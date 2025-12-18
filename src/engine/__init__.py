"""Engine Layer - Core Orchestration and Pipeline Management

This module provides the core engine layer for the crawler, implementing:
- SearchOrchestrator: Main entry point for search execution
- BudgetManager: Time/resource budget management (12s timeout)
- SearchResult: Standardized result format
- ExecutionStrategy: Fast/Slow path decision logic
- CacheAdapter: Cache service adapter
- Exceptions: Standardized exception hierarchy
"""

from .budget import BudgetConfig, BudgetManager
from .cache_adapter import CacheAdapter
from .exceptions import (
    BlockedError,
    BudgetExhaustedError,
    CrawlerException,
    ParsingError,
    ProductNotFoundException,
    TimeoutError,
)
from .orchestrator import SearchOrchestrator
from .result import SearchResult, SearchStatus
from .strategy import ExecutionPath, ExecutionStrategy

__all__ = [
    "SearchOrchestrator",
    "BudgetManager",
    "BudgetConfig",
    "CacheAdapter",
    "SearchResult",
    "SearchStatus",
    "ExecutionStrategy",
    "ExecutionPath",
    # Exceptions
    "CrawlerException",
    "TimeoutError",
    "ParsingError",
    "BlockedError",
    "ProductNotFoundException",
    "BudgetExhaustedError",
]
