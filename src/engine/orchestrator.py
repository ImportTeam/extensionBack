"""Search Orchestrator - Main Engine Entry Point

Coordinates the entire search pipeline:
1. Cache lookup
2. FastPath execution (HTTP)
3. SlowPath fallback (Playwright)
4. Result normalization
"""

from typing import Optional

from src.core.logging import logger

from .budget import BudgetConfig, BudgetManager
from .result import SearchResult, SearchStatus
from .strategy import ExecutionStrategy


class SearchOrchestrator:
    """검색 엔진 오케스트레이터

    Cache → FastPath → SlowPath 파이프라인을 관리하고
    12초 예산 내에서 최적의 결과를 반환합니다.

    Usage:
        orchestrator = SearchOrchestrator(
            cache_service=cache_service,
            fastpath_executor=fastpath_executor,
            slowpath_executor=slowpath_executor,
        )

        result = await orchestrator.search("삼성 갤럭시 S24")

        if result.is_success:
            print(f"Product: {result.product_url}, Price: {result.price}")
        else:
            print(f"Error: {result.error_message}")
    """

    def __init__(
        self,
        cache_service,
        fastpath_executor,
        slowpath_executor,
        budget_config: Optional[BudgetConfig] = None,
    ):
        """
        Args:
            cache_service: 캐시 서비스 (get/set 메서드 구현)
            fastpath_executor: FastPath 실행자 (execute 메서드 구현)
            slowpath_executor: SlowPath 실행자 (execute 메서드 구현)
            budget_config: 예산 설정 (기본값: 12초)
        """
        self.cache = cache_service
        self.fastpath = fastpath_executor
        self.slowpath = slowpath_executor
        self.budget_manager = BudgetManager(budget_config)
        self.strategy = ExecutionStrategy()

    async def search(self, query: str) -> SearchResult:
        """통합 검색 실행

        Cache → FastPath → SlowPath 순서로 실행하며,
        각 단계는 예산 내에서만 실행됩니다.

        Args:
            query: 검색어

        Returns:
            SearchResult: 표준화된 검색 결과
        """
        self.budget_manager.start()
        logger.info(f"Search started: query='{query}'")

        try:
            # 1. Cache 확인
            result = await self._try_cache(query)
            if result:
                logger.info(f"Search completed from cache: query='{query}'")
                return result

            # 2. FastPath 시도
            result = await self._try_fastpath(query)
            if result:
                logger.info(f"Search completed from fastpath: query='{query}'")
                return result

            # 3. SlowPath Fallback
            result = await self._try_slowpath(query)
            if result:
                logger.info(f"Search completed from slowpath: query='{query}'")
                return result

            # 4. 모든 경로 실패
            logger.warning(f"No results found: query='{query}'")
            return SearchResult.no_results(
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
            )

        except Exception as e:
            logger.error(f"Search failed: query='{query}'", exc_info=True)
            return SearchResult.parse_error(
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                error=str(e),
            )

    async def _try_cache(self, query: str) -> Optional[SearchResult]:
        """Cache 조회 시도

        Args:
            query: 검색어

        Returns:
            Optional[SearchResult]: 캐시 히트 시 결과, 미스 시 None
        """
        try:
            timeout = self.budget_manager.get_timeout_for("cache")
            cached = await self.cache.get(query, timeout=timeout)

            if cached:
                self.budget_manager.checkpoint("cache_hit")
                logger.debug(f"Cache hit: query='{query}'")
                return SearchResult.from_cache(
                    product_url=cached.get("url") or cached.get("product_url"),
                    price=cached.get("price"),
                    query=query,
                    elapsed_ms=self.budget_manager.elapsed() * 1000,
                )
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")

        self.budget_manager.checkpoint("cache_miss")
        return None

    async def _try_fastpath(self, query: str) -> Optional[SearchResult]:
        """FastPath 실행 시도

        Args:
            query: 검색어

        Returns:
            Optional[SearchResult]: 성공 시 결과, 실패 시 None
        """
        if not self.budget_manager.can_execute_fastpath():
            logger.warning(
                f"FastPath skipped: budget exhausted (remaining: {self.budget_manager.remaining():.2f}s)"
            )
            return None

        try:
            timeout = self.budget_manager.get_timeout_for("fastpath")
            logger.debug(f"FastPath executing: query='{query}', timeout={timeout:.2f}s")

            result = await self.fastpath.execute(query, timeout=timeout)

            self.budget_manager.checkpoint("fastpath_success")
            logger.info(
                f"FastPath success: query='{query}', elapsed={self.budget_manager.elapsed():.2f}s"
            )

            # Cache 저장
            await self._save_to_cache(query, result)

            return SearchResult.from_fastpath(
                product_url=result.product_url,
                price=result.price,
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
            )

        except Exception as e:
            self.budget_manager.checkpoint("fastpath_failed")
            logger.warning(f"FastPath failed: query='{query}', error={type(e).__name__}")

            # Fallback 여부 결정
            if not self.strategy.should_fallback_to_slowpath(e):
                logger.error(f"FastPath failed without fallback: {e}")
                raise

        return None

    async def _try_slowpath(self, query: str) -> Optional[SearchResult]:
        """SlowPath 실행 시도

        Args:
            query: 검색어

        Returns:
            Optional[SearchResult]: 성공 시 결과

        Raises:
            Exception: SlowPath 실행 실패
        """
        if not self.budget_manager.can_execute_slowpath():
            logger.error(
                f"SlowPath skipped: budget exhausted (remaining: {self.budget_manager.remaining():.2f}s)"
            )
            return SearchResult.budget_exhausted(
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                budget_report=self.budget_manager.get_report(),
            )

        try:
            timeout = self.budget_manager.get_timeout_for("slowpath")
            logger.debug(f"SlowPath executing: query='{query}', timeout={timeout:.2f}s")

            result = await self.slowpath.execute(query, timeout=timeout)

            self.budget_manager.checkpoint("slowpath_success")
            logger.info(
                f"SlowPath success: query='{query}', elapsed={self.budget_manager.elapsed():.2f}s"
            )

            # Cache 저장
            await self._save_to_cache(query, result)

            return SearchResult.from_slowpath(
                product_url=result.product_url,
                price=result.price,
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
            )

        except Exception as e:
            self.budget_manager.checkpoint("slowpath_failed")
            logger.error(f"SlowPath failed: query='{query}', error={type(e).__name__}", exc_info=True)
            raise

    async def _save_to_cache(self, query: str, result) -> None:
        """결과를 캐시에 저장

        Args:
            query: 검색어
            result: 크롤링 결과
        """
        try:
            cache_data = {
                "product_url": result.product_url,
                "price": result.price,
            }
            await self.cache.set(query, cache_data, ttl=21600)  # 6시간
            logger.debug(f"Result cached: query='{query}'")
        except Exception as e:
            logger.warning(f"Failed to save to cache: {e}")
