"""HTTP Fast Path → Playwright fallback 오케스트레이션."""

from __future__ import annotations

import asyncio
from typing import Dict, Optional

from src.core.config import settings
from src.core.exceptions import CrawlerException, ProductNotFoundException
from src.core.logging import logger
from src.utils.text_utils import clean_product_name, normalize_search_query

from .http_fastpath import FastPathNoResults


async def search_lowest_price(
    crawler,
    product_name: str,
    product_code: Optional[str] = None,
) -> Optional[Dict]:
    """다나와에서 상품 검색 후 최저가 반환 (HTTP → Playwright)."""
    # 전체 시간 예산 내에서: HTTP Fast Path → Playwright Fallback
    loop = asyncio.get_running_loop()
    started = loop.time()
    total_budget_ms = int(getattr(settings, "crawler_total_budget_ms", 4000))
    http_budget_ms = int(min(getattr(settings, "crawler_http_timeout_ms", 1200), total_budget_ms))

    def _remaining_budget_s() -> float:
        elapsed_ms = int((loop.time() - started) * 1000)
        return max(0.0, (total_budget_ms - elapsed_ms) / 1000.0)

    cleaned_name = clean_product_name(product_name)
    normalized_name = normalize_search_query(product_name)
    logger.info(f"Searching for: {cleaned_name}")

    page = None
    try:
        # 0) Fast Path (HTTP) - pcode가 없는 경우에만 수행
        if not product_code:
            try:
                if not crawler._fastpath_is_open():
                    logger.info(f"[FAST_PATH] Attempting HTTP fast path for: {cleaned_name}")
                    from src.utils.search_optimizer import DanawaSearchHelper

                    helper = DanawaSearchHelper()
                    candidates = helper.generate_search_candidates(product_name)
                    fast = await asyncio.wait_for(
                        crawler._http.search_lowest_price(
                            query=product_name,
                            candidates=candidates,
                            total_timeout_ms=http_budget_ms,
                        ),
                        timeout=max(0.2, http_budget_ms / 1000.0),
                    )
                    if fast:
                        logger.info(f"[FAST_PATH] ✅ Success via HTTP ({fast.get('lowest_price', 0)}원)")
                        crawler._fastpath_on_success()
                        crawler._metric_fastpath_hit()
                        return fast
                    logger.info(f"[FAST_PATH] ❌ HTTP returned None, falling back to Playwright")
                    crawler._fastpath_on_fail()
                    crawler._metric_fastpath_miss()
                else:
                    logger.info(f"[FAST_PATH] Circuit breaker OPEN, skipping HTTP fast path")
                    crawler._metric_fastpath_miss()
            except FastPathNoResults:
                logger.info("[FAST_PATH] ✅ No results confirmed via HTTP, skipping Playwright")
                raise ProductNotFoundException(f"No products found for: {product_name}")
            except Exception as e:
                logger.warning(
                    f"[FAST_PATH] ❌ Exception: {type(e).__name__}: {repr(e)}, falling back to Playwright"
                )
                crawler._fastpath_on_fail()
                crawler._metric_fastpath_miss()

        # Playwright는 전체 예산을 초과하지 않도록 남은 시간 내에서만 실행
        remaining_s = _remaining_budget_s()
        if remaining_s <= 0.0:
            raise CrawlerException(f"Budget exceeded before Playwright fallback: {total_budget_ms}ms")
        logger.info(f"[PLAYWRIGHT] Fallback mode (remaining_budget={remaining_s:.2f}s)")

        # 1단계: 검색 페이지에서 상품 찾기 (이미 코드가 주어지면 스킵)
        if not product_code:
            remaining_s = _remaining_budget_s()
            if remaining_s <= 0.0:
                raise CrawlerException(f"Budget exceeded before Playwright search: {total_budget_ms}ms")

            playwright_search_timeout = min(8.0, max(0.2, remaining_s))
            sem_timeout = playwright_search_timeout + 1.0
            acquired = await crawler._acquire_browser_semaphore_with_timeout(sem_timeout)
            if not acquired:
                raise ProductNotFoundException(f"Concurrency busy for: {product_name}")
            try:
                product_code = await asyncio.wait_for(
                    crawler._search_product(product_name),
                    timeout=playwright_search_timeout,
                )
            except asyncio.TimeoutError:
                logger.error(f"[PLAYWRIGHT] Search timeout after {playwright_search_timeout}s")
                raise
            finally:
                crawler._release_browser_semaphore()

        if not product_code:
            raise ProductNotFoundException(f"No products found for: {product_name}")

        # 2단계: 상품 상세 페이지에서 최저가 추출
        await crawler._rate_limit()
        remaining_s = _remaining_budget_s()
        if remaining_s <= 0.0:
            raise CrawlerException(f"Budget exceeded before Playwright detail: {total_budget_ms}ms")

        playwright_detail_timeout = min(6.0, max(0.2, remaining_s))
        sem_timeout = playwright_detail_timeout + 1.0
        acquired = await crawler._acquire_browser_semaphore_with_timeout(sem_timeout)
        if not acquired:
            raise CrawlerException(f"Playwright concurrency busy for: {product_name}")
        try:
            page = await crawler._create_page()
            # Playwright 내부 selector timeout은 충분히 확보
            try:
                page.set_default_timeout(8000)
            except Exception:
                pass
            result = await asyncio.wait_for(
                crawler._get_product_lowest_price(page, product_code, cleaned_name),
                timeout=playwright_detail_timeout,
            )
            logger.info(f"[PLAYWRIGHT] ✅ Success ({result.get('lowest_price', 0)}원)")
            crawler._metric_playwright_hit()
        except asyncio.TimeoutError:
            logger.error(f"[PLAYWRIGHT] Detail page timeout after {playwright_detail_timeout}s")
            crawler._metric_playwright_failure()
            raise
        except Exception as e:
            logger.error(f"[PLAYWRIGHT] Detail page error: {type(e).__name__}: {repr(e)}")
            crawler._metric_playwright_failure()
            raise
        finally:
            crawler._release_browser_semaphore()

        if not result:
            raise ProductNotFoundException(f"No price information for: {product_name}")

        logger.info(f"Found product: {result['product_name']} - {result['lowest_price']}원")
        return result

    except ProductNotFoundException:
        raise
    except Exception as e:
        logger.error(f"Crawling error for '{product_name}': {e}")
        raise CrawlerException(f"Crawling failed: {e}")
    finally:
        if page:
            await page.close()
