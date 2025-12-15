"""Playwright 기반 최저가 추이 데이터 추출."""

from __future__ import annotations

from typing import Dict

from playwright.async_api import Page

from src.core.logging import logger


async def extract_price_trend(page: Page) -> list[Dict]:
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
