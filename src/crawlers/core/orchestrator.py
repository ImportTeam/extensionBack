"""HTTP Fast Path → Playwright fallback 오케스트레이션.

책임:
- HTTP Fast Path 시도
- Playwright 폴백 관리
- 타임아웃/예산 관리
- 에러 핸들링
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional, cast

from src.core.config import settings
from src.core.exceptions import CrawlerException, ProductNotFoundException
from src.core.logging import logger
from src.utils.text_utils import clean_product_name, build_cache_key, normalize_for_search_query
from src.utils.normalization.normalize import normalize_search_query

from src.crawlers.boundary import (
    TimeoutManager,
    FastPathNoResults,
    FastPathProductFetchFailed,
)
from src.crawlers.playwright.search import search_product
from src.crawlers.playwright.detail import get_product_lowest_price


def is_broad_query(product_name: str) -> bool:
    """🔴 Broad query 감지 (timeout 확장 필요)
    
    검색어가 너무 광범위하면 다나와가 많은 결과를 반환하고,
    페이지 로딩/렌더링이 오래 걸림 → timeout 확장 필요
    
    Broad query 판정 기준:
    - 3자 이하 (예: "갤럭시 버즈" → 검색 결과 5000+개)
    - 숫자/모델명 없음 (예: "맥북" vs "맥북 에어 15")
    - 한글-영문 섞임 없음 (예: "MacBook Air" → 구체적)
    """
    cleaned = clean_product_name(product_name).strip()
    
    # 🔍 판정 로직
    # 1) 너무 짧음 (3자 이하) + 숫자 없음
    if len(cleaned) <= 3 and not re.search(r'\d', cleaned):
        logger.warning(f"[Broad] Detected: '{product_name}' is too short + no model number")
        return True
    
    # 2) 명백히 generic한 키워드 (단일 브랜드명만)
    generic_keywords = {
        "갤럭시", "아이폰", "맥북", "맥", "갤럭시북", "그램", 
        "갤럭시탭", "아이패드", "에어팟", "galaxy", "macbook"
    }
    if cleaned.lower() in generic_keywords:
        logger.warning(f"[Broad] Detected: '{product_name}' is generic brand name")
        return True
    
    # 3) "버즈", "워치" 같은 카테고리 + 숫자 없음
    category_only = {"버즈", "워치", "태블릿", "폰", "노트북"}
    if any(kw in cleaned for kw in category_only) and not re.search(r'\d', cleaned):
        logger.warning(f"[Broad] Detected: '{product_name}' is category + no generation")
        return True
    
    return False


async def search_lowest_price(
    crawler,
    product_name: str,
    product_code: Optional[str] = None,
) -> Optional[Dict]:
    """다나와에서 상품 검색 후 최저가 반환 (HTTP → Playwright).
    
    📝 Note: product_name은 이미 정규화된 쿼리입니다.
    - PriceSearchService에서 normalize_search_query() 적용 후 전달
    - 여기서는 순수 정제(clean)만 수행, 재정규화는 하지 않음
    
    🔴 Broad Query Detection:
    - "갤럭시 버즈" 같은 검색어 → timeout 확장 (5s → 10s)
    - 다나와의 과도한 결과 반환 방지
    """
    # 🔴 기가차드 수정: 예산 분리 (HTTP 10s, Playwright 15s)
    # 이제 settings에서 가져오지 않고 명시적으로 할당
    total_budget_ms = 25000 
    
    timeout_mgr = TimeoutManager(total_budget_ms)
    cb = crawler._get_circuit_breaker()

    normalized_search_term = normalize_for_search_query(product_name)
    cleaned_name = build_cache_key(normalized_search_term)  # 순수 정제만
    logger.info(f"[CRAWL] Starting search: {product_name} (HTTP: 10s, PW: 15s)")

    # 🔴 기가차드 수정: 검색 후보를 미리 생성하여 HTTP와 Playwright에서 공유 (중복 분석 방지)
    from src.utils.search.search_optimizer import DanawaSearchHelper
    helper = DanawaSearchHelper()
    candidates = helper.generate_search_candidates(product_name)
    logger.info(f"[CRAWL] Using search candidates: {candidates}")

    # 실제 크롤링(검색/검증)에 사용할 대표 쿼리.
    # 연도(2025) 같은 토큰이 다나와 상품명에 없을 수 있어,
    # 후보 1번(보통 연도 제거 버전)을 primary로 삼아 점수화/검증 일관성을 유지합니다.
    primary_query = candidates[0] if candidates else product_name

    page = None
    try:
        # 0) Fast Path (HTTP) - pcode가 없는 경우에만 수행
        if not product_code:
            try:
                if not cb.is_open():
                    # 🔴 기가차드 설계: 너무 짧거나 범용적인 쿼리는 HTTP FastPath 스킵
                    if is_broad_query(product_name) or product_name.count(" ") < 1:
                        logger.warning(f"[HTTP-FASTPATH] ⏩ Skipping HTTP for broad/short query: '{product_name}'")
                    else:
                        logger.info(f"[HTTP-FASTPATH] Phase 1 - Attempting curl-based HTTP search (timeout: 12s)")
                        
                        # HTTP 페이즈 시작
                        timeout_mgr.start_phase()
                        fast = await asyncio.wait_for(
                            crawler._http.search_lowest_price(
                                query=primary_query,
                                candidates=candidates,
                                total_timeout_ms=12000, # 12s (단순하게 충분히 확보)
                            ),
                            timeout=14.0, # 여유분 포함
                        )
                        if fast:
                            logger.info(f"[HTTP-FASTPATH] ✅ Phase 1 SUCCESS (elapsed: {timeout_mgr.phase_elapsed_ms}ms)")
                            cb.record_success()
                            return cast(dict[str, Any] | None, fast)
                        logger.warning(f"[HTTP-FASTPATH] ⚠️  Phase 1 RETURNED NONE")
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
        # 🔴 기가차드 수정: Playwright 페이즈 시작 (독립 예산 15s)
        timeout_mgr.start_phase()
        logger.info(f"[PLAYWRIGHT] Phase 2 - Fallback to Playwright (Budget: 15s)")

        # 1단계: 검색 페이지에서 상품 찾기
        # 💡 기가차드 수정: product_code가 있어도 나중에 실패하면 검색으로 폴백할 수 있도록 구조 변경
        async def _get_pcode_via_search():
            # 이전 8초는 다나와 검색 페이지에 너무 짧아 goto timeout(6s)로 실패가 잦았습니다.
            # Playwright 전체 예산(15s) 내에서 검색에 더 많은 시간을 배정합니다.
            remaining_pw_s = timeout_mgr.phase_remaining_ms_playwright / 1000.0
            # 검색은 최소 12초, 최대 14초까지 (남은 예산 내)
            playwright_search_timeout = max(12.0, min(14.0, remaining_pw_s))
            sem_timeout = 10.0
            acquired = await crawler._acquire_browser_semaphore_with_timeout(sem_timeout)
            if not acquired:
                raise ProductNotFoundException(f"Concurrency busy for: {product_name}")
            try:
                logger.debug(f"[PLAYWRIGHT] Phase 2-A - Launching browser search (timeout: {playwright_search_timeout}s)")
                pcode = await asyncio.wait_for(
                    search_product(
                        crawler._create_page,
                        crawler.search_url,
                        primary_query,
                        overall_timeout_s=playwright_search_timeout,
                        candidates=candidates, # 🔴 공유된 후보 사용
                    ),
                    timeout=playwright_search_timeout + 2.0,
                )
                if pcode:
                    logger.info(f"[PLAYWRIGHT] Phase 2-A ✅ Found product pcode: {pcode}")
                    cb.metrics.record_playwright_hit()
                return pcode
            except asyncio.TimeoutError:
                logger.error(f"[PLAYWRIGHT] Phase 2-A ❌ Search timeout")
                cb.metrics.record_playwright_failure()
                return None
            finally:
                crawler._release_browser_semaphore()

        if not product_code:
            product_code = await _get_pcode_via_search()

        if not product_code:
            raise ProductNotFoundException(f"No products found for: {product_name}")

        # 2단계: 상품 상세 페이지에서 최저가 추출
        async def _fetch_detail(pcode: str) -> Optional[dict]:
            await crawler._rate_limit()
            remaining_pw_s = timeout_mgr.phase_remaining_ms_playwright / 1000.0
            if remaining_pw_s < 2.0:
                return None
            
            playwright_detail_timeout = min(10.0, remaining_pw_s)
            sem_timeout = playwright_detail_timeout + 2.0
            acquired = await crawler._acquire_browser_semaphore_with_timeout(sem_timeout)
            if not acquired:
                return None
            try:
                page = await crawler._create_page()
                try:
                    page.set_default_timeout(10000)
                except Exception:
                    pass
                logger.debug(f"[PLAYWRIGHT] Phase 2-B - Fetching details for pcode={pcode}")
                return await asyncio.wait_for(
                    get_product_lowest_price(page, crawler.product_url, pcode, cleaned_name),
                    timeout=playwright_detail_timeout + 2.0,
                )
            except Exception as e:
                logger.error(f"[PLAYWRIGHT] Phase 2-B ❌ Detail error for {pcode}: {e}")
                return None
            finally:
                crawler._release_browser_semaphore()

        result = await _fetch_detail(product_code)
        
        # 💡 기가차드 수정: 만약 제공된 pcode가 mismatch 등으로 실패했다면, 검색을 통해 다시 시도
        if not result and product_name:
            logger.warning(f"[PLAYWRIGHT] Provided pcode {product_code} failed. Retrying via search...")
            new_pcode = await _get_pcode_via_search()
            if new_pcode and new_pcode != product_code:
                result = await _fetch_detail(new_pcode)

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
