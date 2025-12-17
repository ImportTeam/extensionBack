"""HTTP Fast Path → Playwright fallback 오케스트레이션.

책임:
- HTTP Fast Path 시도
- Playwright 폴백 관리
- 타임아웃/예산 관리
- 에러 핸들링
"""

from __future__ import annotations

import asyncio
from typing import Dict, Optional

from src.core.config import settings
from src.core.exceptions import CrawlerException, ProductNotFoundException
from src.core.logging import logger
from src.utils.text import clean_product_name, normalize_search_query

from src.crawlers.danawa.boundary import (
    TimeoutManager,
    FastPathNoResults,
    FastPathProductFetchFailed,
)
from src.crawlers.danawa.playwright.search import search_product
from src.crawlers.danawa.playwright.detail import get_product_lowest_price


async def search_lowest_price(
    crawler,
    product_name: str,
    product_code: Optional[str] = None,
) -> Optional[Dict]:
    """다나와에서 상품 검색 후 최저가 반환 (HTTP → Playwright)."""
    total_budget_ms = int(getattr(settings, "crawler_total_budget_ms", 4000))
    timeout_mgr = TimeoutManager(total_budget_ms)
    cb = crawler._get_circuit_breaker()

    cleaned_name = clean_product_name(product_name)
    normalized_name = normalize_search_query(product_name)
    logger.info(f"[CRAWL] Starting search for: {cleaned_name} (budget: {total_budget_ms}ms)")

    page = None
    try:
        # 0) Fast Path (HTTP) - pcode가 없는 경우에만 수행
        if not product_code:
            try:
                if not cb.is_open():
                    logger.info(
                        f"[HTTP-FASTPATH] Phase 1 - Attempting curl-based HTTP search "
                        f"(timeout: {timeout_mgr.budget.http_budget_ms}ms)"
                    )
                    from src.utils.search import DanawaSearchHelper

                    helper = DanawaSearchHelper()
                    candidates = helper.generate_search_candidates(product_name)
                    
                    fast = await asyncio.wait_for(
                        crawler._http.search_lowest_price(
                            query=product_name,
                            candidates=candidates,
                            total_timeout_ms=timeout_mgr.budget.http_budget_ms,
                        ),
                        timeout=timeout_mgr.budget.http_budget_s + 2.0,
                    )
                    if fast:
                        elapsed_ms = timeout_mgr.elapsed_ms
                        logger.info(
                            f"[HTTP-FASTPATH] ✅ Phase 1 SUCCESS - Found price via curl "
                            f"(result: {fast.get('lowest_price', 0)}원 from {fast.get('mall', '?')} | "
                            f"elapsed: {elapsed_ms}ms)"
                        )
                        cb.record_success()
                        return fast
                    logger.warning(f"[HTTP-FASTPATH] ⚠️  Phase 1 RETURNED NONE - Will fallback to Playwright")
                    cb.record_failure()
                else:
                    remaining_time = cb.get_remaining_open_time()
                    logger.warning(
                        f"[HTTP-FASTPATH] ⚠️  Circuit breaker OPEN ({remaining_time:.1f}s remaining) - "
                        f"Skipping HTTP, going straight to Playwright"
                    )
                    cb.record_failure()
            except FastPathNoResults:
                logger.info("[HTTP-FASTPATH] ✅ Phase 1 - No products found confirmation (skipping Playwright)")
                raise ProductNotFoundException(f"No products found for: {product_name}")
            except FastPathProductFetchFailed as e:
                logger.warning(
                    f"[HTTP-FASTPATH] ⚠️  Phase 1 PARTIAL - Got pcode={e.pcode} but product detail failed "
                    f"({e.reason}); will fetch detail via Playwright"
                )
                cb.record_failure()
                product_code = e.pcode
            except Exception as e:
                logger.warning(
                    f"[HTTP-FASTPATH] ❌ Phase 1 EXCEPTION: {type(e).__name__} - {repr(e)[:100]} | "
                    f"Falling back to Playwright"
                )
                cb.record_failure()

        # Playwright는 예산 내에서만 수행
        remaining_s = timeout_mgr.remaining_s
        logger.info(f"[PLAYWRIGHT] Phase 2 - Fallback to Playwright browser mode (remaining_budget: {remaining_s:.2f}s)")

        if remaining_s < 0.8:
            raise asyncio.TimeoutError("crawl_budget_exhausted_before_playwright")

        # 1단계: 검색 페이지에서 상품 찾기 (이미 코드가 주어지면 스킵)
        if not product_code:
            if not timeout_mgr.has_minimum_for_playwright_search():
                raise asyncio.TimeoutError("insufficient_budget_for_playwright_search_and_detail")

            playwright_search_timeout = timeout_mgr.get_playwright_search_timeout()
            sem_timeout = min(timeout_mgr.remaining_s, playwright_search_timeout + 1.0)
            acquired = await crawler._acquire_browser_semaphore_with_timeout(sem_timeout)
            if not acquired:
                raise ProductNotFoundException(f"Concurrency busy for: {product_name}")
            try:
                logger.debug(f"[PLAYWRIGHT] Phase 2-A - Launching browser search (timeout: {playwright_search_timeout:.1f}s)")
                product_code = await asyncio.wait_for(
                    search_product(
                        crawler._create_page,
                        crawler.search_url,
                        product_name,
                        overall_timeout_s=playwright_search_timeout,
                    ),
                    timeout=playwright_search_timeout,
                )
                logger.info(f"[PLAYWRIGHT] Phase 2-A ✅ Found product pcode: {product_code}")
                cb.metrics.record_playwright_hit()
            except asyncio.TimeoutError:
                logger.error(f"[PLAYWRIGHT] Phase 2-A ❌ Search timeout after {playwright_search_timeout}s")
                cb.metrics.record_playwright_failure()
                raise
            finally:
                crawler._release_browser_semaphore()

        if not product_code:
            raise ProductNotFoundException(f"No products found for: {product_name}")

        # 2단계: 상품 상세 페이지에서 최저가 추출
        await crawler._rate_limit()
        remaining_s = timeout_mgr.remaining_s
        if remaining_s < 1.0:
            raise asyncio.TimeoutError("insufficient_budget_for_playwright_detail")
        
        playwright_detail_timeout = timeout_mgr.get_playwright_detail_timeout()
        sem_timeout = min(timeout_mgr.remaining_s, playwright_detail_timeout + 1.0)
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
            logger.debug(f"[PLAYWRIGHT] Phase 2-B - Fetching product details (timeout: {playwright_detail_timeout:.1f}s)")
            result = await asyncio.wait_for(
                get_product_lowest_price(page, crawler.product_url, product_code, cleaned_name),
                timeout=playwright_detail_timeout,
            )
            if result:
                elapsed_ms = timeout_mgr.elapsed_ms
                logger.info(
                    f"[PLAYWRIGHT] Phase 2-B ✅ SUCCESS - Got price from Playwright "
                    f"(result: {result.get('lowest_price', 0)}원 from {result.get('mall', '?')} | "
                    f"elapsed: {elapsed_ms}ms)"
                )
                cb.metrics.record_playwright_hit()
            else:
                logger.error(f"[PLAYWRIGHT] Phase 2-B ❌ No price data returned")
                cb.metrics.record_playwright_failure()
        except asyncio.TimeoutError:
            logger.error(f"[PLAYWRIGHT] Phase 2-B ❌ Detail page timeout after {playwright_detail_timeout}s")
            cb.metrics.record_playwright_failure()
            raise
        except Exception as e:
            logger.error(
                f"[PLAYWRIGHT] Phase 2-B ❌ Detail page error: {type(e).__name__}: {repr(e)[:100]}"
            )
            cb.metrics.record_playwright_failure()
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
            try:
                await page.close()
            except Exception:
                pass
