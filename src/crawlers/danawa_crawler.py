"""다나와 크롤러 - 웹 스크래핑만 담당"""
import asyncio
import random
from typing import Optional, Dict, List
from urllib.parse import quote
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError, Playwright

from src.core.config import settings
from src.core.logging import logger
from src.core.exceptions import CrawlerException, ProductNotFoundException, BrowserException
from src.utils.text_utils import (
    clean_product_name,
    extract_price_from_text,
    calculate_similarity,
    split_kr_en_boundary,
    normalize_search_query,
    extract_model_codes,
    fuzzy_score,
    weighted_match_score,
)
from src.utils.url_utils import normalize_href


class DanawaCrawler:
    """다나와 크롤러 - SRP: 웹 스크래핑만 담당"""
    
    def __init__(self) -> None:
        self.browser: Optional[Browser] = None
        self.search_url = "https://search.danawa.com/dsearch.php"
        self.product_url = "https://prod.danawa.com/info/"
        self._playwright: Optional[Playwright] = None
    
    async def __aenter__(self) -> "DanawaCrawler":
        """Context manager 진입 - 브라우저 시작"""
        try:
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.info("Browser launched successfully")
            return self
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise BrowserException(f"Browser launch failed: {e}")
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager 종료 - 브라우저 종료"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")
        if self._playwright:
            await self._playwright.stop()
    
    async def _rate_limit(self) -> None:
        """Rate limiting - 요청 간격 조절"""
        delay = random.uniform(
            settings.crawler_rate_limit_min,
            settings.crawler_rate_limit_max
        )
        await asyncio.sleep(delay)
        logger.debug(f"Rate limit delay: {delay:.2f}s")
    
    async def _create_page(self) -> Page:
        """새 페이지 생성 및 설정"""
        if not self.browser:
            raise BrowserException("Browser not initialized")
        
        page = await self.browser.new_page()
        page.set_default_timeout(settings.crawler_timeout)
        
        await page.set_extra_http_headers({
            'User-Agent': settings.crawler_user_agent
        })
        
        return page
    
    
    async def search_lowest_price(self, product_name: str, product_code: Optional[str] = None) -> Optional[Dict]:
        """
        다나와에서 상품 검색 후 최저가 반환
        
        실제 프로덕션 다나와 구조:
        1. 검색 페이지에서 상품 찾기
        2. 첫 번째 상품의 상세 페이지로 이동
        3. 상세 페이지에서 쇼핑몰별 최저가 추출
        
        Args:
            product_name: 검색할 상품명
            
        Returns:
            {
                "product_name": str,
                "lowest_price": int,
                "link": str,
                "source": "danawa",
                "updated_at": str
            }
            
        Raises:
            ProductNotFoundException: 상품을 찾을 수 없을 때
            CrawlerException: 크롤링 실패 시
        """
        if not self.browser:
            raise BrowserException("Browser not initialized. Use 'async with' statement.")
        
        await self._rate_limit()
        
        cleaned_name = clean_product_name(product_name)
        normalized_name = normalize_search_query(product_name)
        logger.info(f"Searching for: {cleaned_name}")
        
        page = None
        try:
            # 1단계: 검색 페이지에서 상품 찾기 (이미 코드가 주어지면 스킵)
            if not product_code:
                # 원본 상품명을 기준으로 후보 생성/매칭해야 (13/15 등) 신호를 잃지 않습니다.
                product_code = await self._search_product(product_name)
            
            if not product_code:
                raise ProductNotFoundException(f"No products found for: {product_name}")
            
            # 2단계: 상품 상세 페이지에서 최저가 추출
            page = await self._create_page()
            result = await self._get_product_lowest_price(page, product_code, cleaned_name)
            
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
    
    async def _search_product(self, search_query: str) -> Optional[str]:
        """
        검색 페이지에서 상품 코드 추출 (계층적 폴백 검색)
        
        Args:
            search_query: 검색 쿼리
            
        Returns:
            상품 코드(pcode) 또는 None
        """
        from src.utils.search_optimizer import DanawaSearchHelper
        
        page = await self._create_page()
        
        try:
            # 스마트 검색 후보 생성 (계층적 폴백)
            helper = DanawaSearchHelper()
            candidates = helper.generate_search_candidates(search_query)
            
            logger.debug(f"Search candidates (smart): {candidates}")
            
            # 첫 번째 후보부터 검색 시작
            found = False
            for idx, cand in enumerate(candidates):
                logger.debug(f"Trying search (attempt {idx+1}): {cand}")
                search_url = f"{self.search_url}?query={quote(cand)}&originalQuery={quote(cand)}"
                await page.goto(search_url, wait_until='domcontentloaded')
                
                try:
                    await page.wait_for_selector('.prod_item, a[href*="pcode="]', timeout=3000 if idx > 0 else 5000)
                    found = True
                    break
                except PlaywrightTimeoutError:
                    if idx < len(candidates) - 1:
                        continue
                    break
            
            if not found:
                return None
            
            # 검색 결과(여러 개)에서 "원본 쿼리"와 가장 일치하는 상품을 선택
            href = None
            best_href = None
            best_score = 0.0

            prod_links = await page.query_selector_all('.prod_item .prod_name a[href*="pcode="]')
            links_to_score = prod_links[:12] if prod_links else await page.query_selector_all('a[href*="pcode="]')
            if not links_to_score:
                return None

            for link in links_to_score:
                try:
                    link_text = (await link.inner_text()) or (await link.get_attribute('title')) or ''
                    score = weighted_match_score(search_query, link_text)
                    logger.debug(f"Candidate link text: {link_text[:100]} score={score}")
                    if score > best_score:
                        best_score = score
                        best_href = await link.get_attribute('href')
                except Exception:
                    continue

            # 너무 낮은 점수면(검색 결과가 엉뚱함) 첫 번째 결과로 폴백
            if best_href and best_score >= 60.0:
                href = best_href
            else:
                first_product = await page.query_selector('.prod_item .prod_name a[href*="pcode="]')
                href = await first_product.get_attribute('href') if first_product else best_href

            if not href or 'pcode=' not in href:
                return None
            
            # pcode 추출
            import re
            match = re.search(r'pcode=(\d+)', href)
            if match:
                return match.group(1)
            
            return None
            
        finally:
            await page.close()
    
    async def _get_product_lowest_price(
        self,
        page: Page,
        product_code: str,
        search_query: str
    ) -> Optional[Dict]:
        """
        상품 상세 페이지에서 쇼핑몰별 최저가 Top 1 추출
        
        실제 다나와 HTML 구조:
        div#lowPriceCompanyArea > div.box__mall-price > ul.list__mall-price > li.list-item
        - 첫 번째 list-item이 최저가 (badge__lowest 표시)
        - 가격: .sell-price .text__num
        - 쇼핑몰: .box__logo img[alt]
        
        Args:
            page: Playwright 페이지
            product_code: 상품 코드
            search_query: 검색한 상품명
            
        Returns:
            최저가 정보 또는 None
        """
        try:
            # 상품 상세 페이지 이동
            product_url = f"{self.product_url}?pcode={product_code}&keyword={quote(search_query)}"
            await page.goto(product_url, wait_until='domcontentloaded')
            
            # 가격 영역 대기
            try:
                await page.wait_for_selector('#lowPriceCompanyArea', timeout=5000)
            except PlaywrightTimeoutError:
                logger.warning(f"Price area not found for pcode: {product_code}")
                return None

            # 배송비 포함 토글이 있으면 켜기 (가격 비교 품질 향상)
            try:
                toggle = page.locator('#add_delivery')
                if await toggle.count() > 0:
                    is_checked = await toggle.is_checked()
                    if not is_checked:
                        label = page.locator('label:has(#add_delivery)')
                        if await label.count() > 0:
                            await label.first.click()
                        else:
                            await toggle.first.click(force=True)
                        await page.wait_for_timeout(400)
            except Exception as e:
                logger.debug(f"Delivery toggle interaction skipped: {e}")
            
            # 상품명 추출
            product_name_elem = await page.query_selector('.prod_tit')
            product_name = search_query
            if product_name_elem:
                product_name = await product_name_elem.inner_text()
                product_name = product_name.strip()
            
            # 최저가 추이 데이터 추출
            price_trend = await self._extract_price_trend(page)
            
            # 쇼핑몰별 최저가 - Top 3 (최저가 계산은 첫 번째 기준)
            price_items = await page.query_selector_all(
                '#lowPriceCompanyArea .box__mall-price .list__mall-price .list-item'
            )

            if not price_items:
                logger.warning("No mall price found")
                return None

            top_items = price_items[:3]
            top_prices: List[Dict[str, object]] = []

            lowest_price = None
            lowest_mall = "알 수 없음"
            lowest_free_shipping = None
            lowest_purchase_link: str | None = None

            for idx, item in enumerate(top_items):
                price_elem = await item.query_selector('.sell-price .text__num')
                if not price_elem:
                    continue

                price_text = await price_elem.inner_text()
                price_value = extract_price_from_text(price_text)
                if price_value <= 0:
                    continue

                mall_elem = await item.query_selector('.box__logo img')
                mall_name = await mall_elem.get_attribute('alt') if mall_elem else "알 수 없음"

                delivery_elem = await item.query_selector('.box__delivery')
                delivery_text = (await delivery_elem.inner_text()) if delivery_elem else ""
                delivery_text = delivery_text.strip() if delivery_text else ""
                free_shipping = "무료" in delivery_text

                link_elem = await item.query_selector('a.link__full-cover')
                link = await link_elem.get_attribute('href') if link_elem else ""
                link = normalize_href(link or "")

                top_prices.append({
                    "rank": idx + 1,
                    "mall": mall_name or "알 수 없음",
                    "price": price_value,
                    "free_shipping": free_shipping,
                    "delivery": delivery_text or "",
                    "link": link or ""
                })

                if lowest_price is None:
                    lowest_price = price_value
                    lowest_mall = mall_name or "알 수 없음"
                    lowest_free_shipping = free_shipping
                    lowest_purchase_link = link or None

            if lowest_price is None:
                logger.warning("Parsed prices are invalid")
                return None

            from datetime import datetime
            return {
                "product_name": product_name,
                "lowest_price": lowest_price,
                # API 응답의 link는 '최저가 쇼핑몰 구매 링크'를 우선 반환
                "link": lowest_purchase_link or product_url,
                "source": "danawa",
                "mall": lowest_mall,
                "free_shipping": lowest_free_shipping,
                "top_prices": top_prices,
                "price_trend": price_trend,
                "updated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting product price: {e}")
            return None
    
    async def _extract_price_trend(self, page: Page) -> list[Dict]:
        """
        최저가 추이 그래프 데이터 추출
        
        다나와는 ECharts를 사용하며, 차트 데이터는:
        1) 차트 렌더링 대기 후 ECharts 인스턴스에서 추출
        2) 네트워크 요청에서 AJAX 데이터 캡처
        3) 페이지 소스의 JavaScript 변수에서 파싱 (Fallback)
        
        Returns:
            [{"label": "11/13", "price": 2700000}, ...]
        """
        try:
            # 네트워크 요청 감시 (AJAX로 차트 데이터를 가져오는 경우)
            price_trend_data = []
            
            async def handle_response(response):
                try:
                    # 가격 추이 API 요청 감지
                    if 'graph' in response.url.lower() or 'chart' in response.url.lower() or 'price' in response.url.lower():
                        if response.status == 200:
                            try:
                                json_data = await response.json()
                                # 다나와 API 응답 구조에 맞춰 파싱
                                if isinstance(json_data, dict):
                                    # 일반적인 차트 데이터 구조
                                    if 'data' in json_data or 'priceData' in json_data:
                                        logger.info(f"Found price trend API: {response.url}")
                                        # 실제 데이터 구조는 API 확인 후 구현
                            except Exception:
                                pass
                except Exception:
                    pass
            
            page.on('response', handle_response)
            
            # 차트 영역이 렌더링될 때까지 대기
            try:
                await page.wait_for_selector('#graphAreaSmall canvas', timeout=3000)
                # 차트 애니메이션 및 AJAX 완료 대기
                await page.wait_for_timeout(1000)
            except Exception:
                logger.warning("Chart element not found or timeout")
            
            # ECharts 인스턴스에서 데이터 추출
            chart_data = await page.evaluate("""
                () => {
                    try {
                        const chartEl = document.querySelector('#graphAreaSmall');
                        if (!chartEl) {
                            console.log('Chart element not found');
                            return null;
                        }
                        
                        // ECharts 인스턴스 가져오기
                        if (typeof echarts === 'undefined') {
                            console.log('ECharts library not loaded');
                            return null;
                        }
                        
                        const instance = echarts.getInstanceByDom(chartEl);
                        if (!instance) {
                            console.log('ECharts instance not found');
                            return null;
                        }
                        
                        const option = instance.getOption();
                        console.log('ECharts option:', option);
                        
                        if (!option || !option.series || !option.series[0]) {
                            console.log('No series data');
                            return null;
                        }
                        
                        const series = option.series[0];
                        const xAxis = option.xAxis && option.xAxis[0];
                        
                        if (!series.data) {
                            console.log('No series.data');
                            return null;
                        }
                        
                        const labels = xAxis && xAxis.data ? xAxis.data : [];
                        const prices = series.data;
                        
                        console.log('Labels:', labels);
                        console.log('Prices:', prices);
                        
                        return prices.map((price, idx) => {
                            // 가격이 배열인 경우 (예: [timestamp, value])
                            const priceValue = Array.isArray(price) ? price[1] : price;
                            return {
                                label: labels[idx] || `Point ${idx + 1}`,
                                price: parseInt(priceValue) || 0
                            };
                        }).filter(item => item.price > 0);
                    } catch (e) {
                        console.error('ECharts extraction error:', e);
                        return null;
                    }
                }
            """)
            
            if chart_data and isinstance(chart_data, list) and len(chart_data) > 0:
                logger.info(f"✅ Extracted {len(chart_data)} price trend points from ECharts")
                return chart_data
            
            # Fallback 1: 페이지 전역 변수 확인
            logger.info("Trying to extract price trend from global variables")
            global_data = await page.evaluate("""
                () => {
                    // 다나와는 때때로 전역 변수에 차트 데이터를 저장
                    if (typeof lowPriceGraphData !== 'undefined') {
                        return lowPriceGraphData;
                    }
                    if (typeof priceGraphData !== 'undefined') {
                        return priceGraphData;
                    }
                    if (typeof window.productGraphData !== 'undefined') {
                        return window.productGraphData;
                    }
                    return null;
                }
            """)
            
            if global_data:
                logger.info(f"Found global chart data: {type(global_data)}")
                # 데이터 구조 파싱 (실제 구조 확인 후 구현)
            
            # Fallback 2: 페이지 소스에서 JavaScript 변수 파싱
            logger.info("Trying to extract price trend from page source")
            content = await page.content()
            
            import re
            
            # 패턴 1: xAxis data와 series data 찾기
            x_match = re.search(r'xAxis.*?data\s*:\s*\[(.*?)\]', content, re.DOTALL)
            y_match = re.search(r'series.*?data\s*:\s*\[(.*?)\]', content, re.DOTALL)
            
            if x_match and y_match:
                try:
                    # 라벨 추출
                    x_data_str = x_match.group(1)
                    labels = re.findall(r'["\']([^"\']+)["\']', x_data_str)
                    
                    # 가격 추출
                    y_data_str = y_match.group(1)
                    prices = re.findall(r'(\d+)', y_data_str)
                    
                    if labels and prices:
                        trend_data = []
                        for idx, price_str in enumerate(prices):
                            if idx < len(labels):
                                trend_data.append({
                                    "label": labels[idx],
                                    "price": int(price_str)
                                })
                        
                        if trend_data:
                            logger.info(f"✅ Extracted {len(trend_data)} price trend points from source")
                            return trend_data
                except Exception as e:
                    logger.error(f"Error parsing trend data from source: {e}")
            
            logger.warning("❌ No price trend data found (ECharts, globals, and source parsing all failed)")
            return []
            
        except Exception as e:
            logger.error(f"Error extracting price trend: {e}")
            return []

