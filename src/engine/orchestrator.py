"""Search Orchestrator - Main Engine Entry Point (Hardened)

Coordinates the entire search pipeline:
1. Cache lookup
2. FastPath execution (HTTP)
3. SlowPath fallback (Playwright)
4. Result normalization

V2: Enhanced with type safety, comprehensive exception handling, and null safety
"""

from typing import Optional, Dict, Any
from asyncio import TimeoutError as AsyncTimeoutError

from src.core.logging import logger
from src.core.exceptions import ProductNotFoundException

from .budget import BudgetConfig, BudgetManager
from .result import SearchResult, SearchStatus
from .strategy import ExecutionStrategy


class SearchOrchestrator:
    """검색 엔진 오케스트레이터 (안전화 버전)

    Cache → FastPath → SlowPath 파이프라인을 관리하고
    12초 예산 내에서 최적의 결과를 반환합니다.

    개선사항:
    - 모든 반환값 검증 (Null safety)
    - 명시적 예외 처리
    - 타입 힌트 강화
    - 상세한 로깅
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
        if not cache_service:
            raise ValueError("cache_service must not be None")
        if not fastpath_executor:
            raise ValueError("fastpath_executor must not be None")
        if not slowpath_executor:
            raise ValueError("slowpath_executor must not be None")
        
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

        Raises:
            ValueError: query가 유효하지 않은 경우
        """
        if not query or not isinstance(query, str):
            raise ValueError(f"Invalid query: {query}")

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
            logger.error(f"Search failed: query='{query}', error={type(e).__name__}", exc_info=True)
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

            if not cached:
                self.budget_manager.checkpoint("cache_miss")
                return None

            self.budget_manager.checkpoint("cache_hit")
            logger.debug(f"Cache hit: query='{query}'")
            
            # Null safety: URL과 가격이 존재하는지 확인
            product_url = cached.get("url") or cached.get("product_url")
            price = cached.get("price")
            
            if not product_url:
                logger.warning(f"Cache missing product_url: {cached}")
                return None
            
            if price is None:
                logger.warning(f"Cache missing price: {cached}")
                return None
            
            # Type safety: 가격이 유효한 정수인지 확인
            try:
                price_int = int(price)
                if price_int <= 0:
                    logger.warning(f"Invalid price in cache: {price}")
                    return None
            except (TypeError, ValueError) as e:
                logger.warning(f"Cache price is not a valid integer: {price}, error={e}")
                return None
            
            return SearchResult.from_cache(
                product_url=product_url,
                price=price_int,
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
            )
        
        except AsyncTimeoutError as e:
            logger.warning(f"Cache lookup timeout: {e}")
            return None
        except Exception as e:
            logger.warning(f"Cache lookup failed: {type(e).__name__}: {e}")
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

            # Result validation
            if not result:
                logger.error(f"FastPath returned None result")
                return None
            
            if not hasattr(result, 'product_url') or not hasattr(result, 'price'):
                logger.error(f"FastPath result missing required attributes")
                return None
            
            product_url = getattr(result, 'product_url', None)
            price = getattr(result, 'price', None)
            
            if not product_url:
                logger.warning(f"FastPath result missing product_url")
                return None
            
            if price is None:
                logger.warning(f"FastPath result missing price")
                return None
            
            # Type validation for price
            try:
                price_int = int(price)
                if price_int <= 0:
                    logger.warning(f"FastPath returned invalid price: {price}")
                    return None
            except (TypeError, ValueError) as e:
                logger.warning(f"FastPath price is not a valid integer: {price}, error={e}")
                return None

            self.budget_manager.checkpoint("fastpath_success")
            logger.info(
                f"FastPath success: query='{query}', price={price_int}, elapsed={self.budget_manager.elapsed():.2f}s"
            )

            # Extract metadata (product_id, top_prices)
            metadata = getattr(result, 'metadata', {}) or {}
            product_id = metadata.get('product_id') or metadata.get('pcode')
            top_prices = metadata.get('top_prices')

            # Cache 저장
            await self._save_to_cache(query, product_url, price_int)

            return SearchResult.from_fastpath(
                product_url=product_url,
                price=price_int,
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                product_id=product_id,
                top_prices=top_prices,
            )

        except AsyncTimeoutError as e:
            self.budget_manager.checkpoint("fastpath_failed")
            logger.warning(f"FastPath timeout: query='{query}', remaining_budget={self.budget_manager.remaining():.2f}s")
            if self.strategy.should_fallback_to_slowpath(e):
                return None
            raise
        except ProductNotFoundException as e:
            self.budget_manager.checkpoint("fastpath_failed")
            logger.debug(f"FastPath: no results found for query='{query}'")
            if self.strategy.should_fallback_to_slowpath(e):
                return None
            raise
        except Exception as e:
            self.budget_manager.checkpoint("fastpath_failed")
            logger.warning(f"FastPath failed: query='{query}', error={type(e).__name__}: {e}")

            # Fallback 여부 결정
            if not self.strategy.should_fallback_to_slowpath(e):
                logger.error(f"FastPath failed without fallback capability: {type(e).__name__}")
                raise

        return None

    async def _try_slowpath(self, query: str) -> Optional[SearchResult]:
        """SlowPath 실행 시도

        Args:
            query: 검색어

        Returns:
            Optional[SearchResult]: 성공 시 결과, None 또는 예외

        Raises:
            Exception: SlowPath 실행 실패 및 회복 불가능한 경우
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

            # Result validation
            if not result:
                logger.error(f"SlowPath returned None result")
                raise ValueError("SlowPath returned None result")
            
            if not hasattr(result, 'product_url') or not hasattr(result, 'price'):
                logger.error(f"SlowPath result missing required attributes")
                raise ValueError("SlowPath result missing required attributes")
            
            product_url = getattr(result, 'product_url', None)
            price = getattr(result, 'price', None)
            
            if not product_url:
                logger.error(f"SlowPath result missing product_url")
                raise ValueError("SlowPath result missing product_url")
            
            if price is None:
                logger.error(f"SlowPath result missing price")
                raise ValueError("SlowPath result missing price")
            
            # Type validation for price
            try:
                price_int = int(price)
                if price_int <= 0:
                    logger.error(f"SlowPath returned invalid price: {price}")
                    raise ValueError(f"Invalid price from SlowPath: {price}")
            except (TypeError, ValueError) as e:
                logger.error(f"SlowPath price is not a valid integer: {price}, error={e}")
                raise ValueError(f"Invalid price format from SlowPath: {price}") from e

            self.budget_manager.checkpoint("slowpath_success")
            logger.info(
                f"SlowPath success: query='{query}', price={price_int}, elapsed={self.budget_manager.elapsed():.2f}s"
            )

            # Extract metadata (product_id, top_prices)
            metadata = getattr(result, 'metadata', {}) or {}
            product_id = metadata.get('product_id') or metadata.get('pcode')
            top_prices = metadata.get('top_prices')

            # Cache 저장
            await self._save_to_cache(query, product_url, price_int)

            return SearchResult.from_slowpath(
                product_url=product_url,
                price=price_int,
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                product_id=product_id,
                top_prices=top_prices,
            )

        except (AsyncTimeoutError, TimeoutError):
            # Catch both asyncio.TimeoutError and built-in TimeoutError
            self.budget_manager.checkpoint("slowpath_failed")
            logger.error(f"SlowPath timeout: query='{query}'")
            return SearchResult.timeout(
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                budget_report=self.budget_manager.get_report(),
            )
        except ProductNotFoundException:
            self.budget_manager.checkpoint("slowpath_failed")
            logger.info(f"SlowPath: no results for query='{query}'")
            return SearchResult.no_results(
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
            )
        except Exception as e:
            # Known error mapping for better API error_code
            from src.core.exceptions import BlockedException, ParsingException, TimeoutException

            self.budget_manager.checkpoint("slowpath_failed")

            if isinstance(e, BlockedException):
                logger.warning(f"SlowPath blocked: query='{query}'")
                return SearchResult.blocked(
                    query=query,
                    elapsed_ms=self.budget_manager.elapsed() * 1000,
                )

            if isinstance(e, TimeoutException):
                logger.warning(f"SlowPath timeout(exception): query='{query}', error={e}")
                return SearchResult.timeout(
                    query=query,
                    elapsed_ms=self.budget_manager.elapsed() * 1000,
                    budget_report=self.budget_manager.get_report(),
                )

            if isinstance(e, ParsingException):
                logger.warning(f"SlowPath parse error: query='{query}', error={e}")
                return SearchResult.parse_error(
                    query=query,
                    elapsed_ms=self.budget_manager.elapsed() * 1000,
                    error=str(e),
                )

            logger.error(
                f"SlowPath failed: query='{query}', error={type(e).__name__}: {e}",
                exc_info=True,
            )
            return SearchResult.parse_error(
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                error=str(e),
            )

    async def _save_to_cache(self, query: str, product_url: str, price: int) -> None:
        """결과를 캐시에 저장

        Args:
            query: 검색어
            product_url: 상품 URL
            price: 가격

        Raises:
            None: 캐시 저장 실패해도 무시
        """
        try:
            # Validation
            if not query or not isinstance(query, str):
                logger.warning(f"Invalid query for cache: {query}")
                return
            
            if not product_url or not isinstance(product_url, str):
                logger.warning(f"Invalid product_url for cache: {product_url}")
                return
            
            if not isinstance(price, int) or price <= 0:
                logger.warning(f"Invalid price for cache: {price}")
                return
            
            cache_data: Dict[str, Any] = {
                "product_url": product_url,
                "price": price,
            }
            await self.cache.set(query, cache_data, ttl=21600)  # 6시간
            logger.debug(f"Result cached: query='{query}', price={price}")
        
        except AsyncTimeoutError as e:
            logger.warning(f"Cache set timeout: {e}")
        except Exception as e:
            logger.warning(f"Failed to save to cache: {type(e).__name__}: {e}")
            # Cache 저장 실패는 치명적이지 않으므로 무시
