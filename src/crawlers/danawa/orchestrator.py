"""HTTP Fast Path → Playwright fallback 오케스트레이션."""

from __future__ import annotations

import asyncio
from typing import Dict, Optional

from src.core.config import settings
from src.core.exceptions import CrawlerException, ProductNotFoundException
from src.core.logging import logger
from src.utils.text_utils import clean_product_name, normalize_search_query

from .http_fastpath import FastPathNoResults, FastPathProductFetchFailed


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
    # Playwright 폴백까지 고려해 HTTP에만 예산을 몰아주지 않도록 분배합니다.
    # (FE 15초 타임아웃을 피하려면 전체 요청이 budget 내에 끝나야 함)
    http_budget_ms = int(
        min(
            getattr(settings, "crawler_http_timeout_ms", 1200),
            max(500, int(total_budget_ms * 0.65)),
        )
    )

    def _remaining_budget_s() -> float:
        elapsed_ms = int((loop.time() - started) * 1000)
        return max(0.0, (total_budget_ms - elapsed_ms) / 1000.0)

    cleaned_name = clean_product_name(product_name)
    normalized_name = normalize_search_query(product_name)
    logger.info(f"[CRAWL] Starting search for: {cleaned_name} (budget: {total_budget_ms}ms)")

    page = None
    try:
        # 0) Fast Path (HTTP) - pcode가 없는 경우에만 수행
        if not product_code:
            try:
                if not crawler._fastpath_is_open():
                    logger.info(f"[HTTP-FASTPATH] Phase 1 - Attempting curl-based HTTP search (timeout: {http_budget_ms}ms)")
                    from src.utils.search_optimizer import DanawaSearchHelper

                    helper = DanawaSearchHelper()
                    candidates = helper.generate_search_candidates(product_name)
                    # NOTE: HTTP fast path 내부에서 URL별 timeout을 관리하지만,
                    # 외부 wait_for가 더 짧으면(예: 상품 상세 6~7초) 중간에 취소되어
                    # 'TimeoutError'로 떨어질 수 있습니다. 그래서 phase budget + 여유를 둡니다.
                    fast = await asyncio.wait_for(
                        crawler._http.search_lowest_price(
                            query=product_name,
                            candidates=candidates,
                            total_timeout_ms=http_budget_ms,
                        ),
                        timeout=max(0.2, (http_budget_ms / 1000.0) + 2.0),
                    )
                    if fast:
                        elapsed_ms = int((loop.time() - started) * 1000)
                        logger.info(f"[HTTP-FASTPATH] ✅ Phase 1 SUCCESS - Found price via curl (result: {fast.get('lowest_price', 0)}원 from {fast.get('mall', '?')} | elapsed: {elapsed_ms}ms)")
                        crawler._fastpath_on_success()
                        crawler._metric_fastpath_hit()
                        return fast
                    logger.warning(f"[HTTP-FASTPATH] ⚠️  Phase 1 RETURNED NONE - Will fallback to Playwright")
                    crawler._fastpath_on_fail()
                    crawler._metric_fastpath_miss()
                else:
                    logger.warning(f"[HTTP-FASTPATH] ⚠️  Circuit breaker OPEN (too many failures) - Skipping HTTP, going straight to Playwright")
                    crawler._metric_fastpath_miss()
            except FastPathNoResults:
                logger.info("[HTTP-FASTPATH] ✅ Phase 1 - No products found confirmation (confirmed empty result, skipping Playwright)")
                raise ProductNotFoundException(f"No products found for: {product_name}")
            except FastPathProductFetchFailed as e:
                # pcode는 찾았는데 HTTP 상세가 차단/파싱 실패한 케이스: Playwright는 재검색하지 말고 상세로 직행
                logger.warning(
                    f"[HTTP-FASTPATH] ⚠️  Phase 1 PARTIAL - Got pcode={e.pcode} but product detail failed ({e.reason}); will fetch detail via Playwright"
                )
                crawler._fastpath_on_fail()
                crawler._metric_fastpath_miss()
                product_code = e.pcode
            except Exception as e:
                logger.warning(
                    f"[HTTP-FASTPATH] ❌ Phase 1 EXCEPTION: {type(e).__name__} - {repr(e)[:100]} | Falling back to Playwright"
                )
                crawler._fastpath_on_fail()
                crawler._metric_fastpath_miss()

        # Playwright는 예산 내에서만 수행(하드 캡). FE(15s)보다 먼저 응답해야 합니다.
        remaining_s = _remaining_budget_s()
        logger.info(
            f"[PLAYWRIGHT] Phase 2 - Fallback to Playwright browser mode (remaining_budget: {remaining_s:.2f}s)"
        )

        # 예산이 거의 없으면 Playwright를 시도하지 않고 빠르게 실패 처리
        if remaining_s < 0.8:
            raise asyncio.TimeoutError("crawl_budget_exhausted_before_playwright")

        # 1단계: 검색 페이지에서 상품 찾기 (이미 코드가 주어지면 스킵)
        if not product_code:
            # Playwright 검색: 남은 예산 안에서만
            # 검색+상세를 모두 해야 하므로, 검색에 너무 오래 쓰지 않게 상한을 둡니다.
            remaining_s = _remaining_budget_s()
            min_search_s = 1.0
            min_detail_s = 1.2
            if remaining_s < (min_search_s + min_detail_s + 0.2):
                raise asyncio.TimeoutError("insufficient_budget_for_playwright_search_and_detail")

            playwright_search_timeout = min(3.0, max(min_search_s, remaining_s * 0.45))
            sem_timeout = min(remaining_s, playwright_search_timeout + 1.0)
            acquired = await crawler._acquire_browser_semaphore_with_timeout(sem_timeout)
            if not acquired:
                raise ProductNotFoundException(f"Concurrency busy for: {product_name}")
            try:
                logger.debug(f"[PLAYWRIGHT] Phase 2-A - Launching browser search (timeout: {playwright_search_timeout:.1f}s)")
                product_code = await asyncio.wait_for(
                    crawler._search_product(product_name),
                    timeout=playwright_search_timeout,
                )
                logger.info(f"[PLAYWRIGHT] Phase 2-A ✅ Found product pcode: {product_code}")
            except asyncio.TimeoutError:
                logger.error(f"[PLAYWRIGHT] Phase 2-A ❌ Search timeout after {playwright_search_timeout}s")
                raise
            finally:
                crawler._release_browser_semaphore()

        if not product_code:
            raise ProductNotFoundException(f"No products found for: {product_name}")

        # 2단계: 상품 상세 페이지에서 최저가 추출
        await crawler._rate_limit()
        # Playwright 상세: 남은 예산 안에서만
        remaining_s = _remaining_budget_s()
        if remaining_s < 1.0:
            raise asyncio.TimeoutError("insufficient_budget_for_playwright_detail")
        playwright_detail_timeout = min(6.0, max(1.0, remaining_s - 0.2))
        sem_timeout = min(remaining_s, playwright_detail_timeout + 1.0)
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
                crawler._get_product_lowest_price(page, product_code, cleaned_name),
                timeout=playwright_detail_timeout,
            )
            if result:
                elapsed_ms = int((loop.time() - started) * 1000)
                logger.info(f"[PLAYWRIGHT] Phase 2-B ✅ SUCCESS - Got price from Playwright (result: {result.get('lowest_price', 0)}원 from {result.get('mall', '?')} | elapsed: {elapsed_ms}ms)")
                crawler._metric_playwright_hit()
            else:
                logger.error(f"[PLAYWRIGHT] Phase 2-B ❌ No price data returned")
                crawler._metric_playwright_failure()
        except asyncio.TimeoutError:
            logger.error(f"[PLAYWRIGHT] Phase 2-B ❌ Detail page timeout after {playwright_detail_timeout}s")
            crawler._metric_playwright_failure()
            raise
        except Exception as e:
            logger.error(f"[PLAYWRIGHT] Phase 2-B ❌ Detail page error: {type(e).__name__}: {repr(e)[:100]}")
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
