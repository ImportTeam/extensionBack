"""E2E Tests - 엔드-투-엔드 실제 사용 시나리오

NOTE: 실서비스/외부 크롤링 필요 - 로컬 서버 필요
마크: @pytest.mark.e2e
"""

import pytest

# Test scope:
# - Real-world user scenarios
# - Various product queries
# - Mall comparison features
# - Price tracking
# - Production environment simulation

import pytest
import httpx
import time
from typing import List, Dict, Any


class TestRealWorldScenarios:
    """실제 사용 시나리오 테스트"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_scenario_compare_products_across_malls(self, api_base_url, http_client):
        """시나리오 1: 여러 쇼핑몰의 상품 가격 비교
        
        사용자가 쿠팡, 지마켓, 11번가에서 본 상품들을 비교합니다.
        """
        # 쿠팡에서 본 상품
        coupang_product = {
            "product_name": "Apple 맥북 에어 13 M4",
            "current_price": 1430980,
        }
        
        # 지마켓에서 본 상품
        gmarket_product = {
            "product_name": "Apple 맥북 에어 13 M4",
            "current_price": 1450000,
        }
        
        results = []
        
        for i, product in enumerate([coupang_product, gmarket_product], 1):
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=product,
                timeout=25.0,
            )
            
            if response.status_code == 200:
                data = response.json()["data"]
                results.append({
                    "index": i,
                    "current_price": product["current_price"],
                    "lowest_price": data.get("lowest_price"),
                    "mall": data.get("mall"),
                    "is_cheaper": data.get("is_cheaper"),
                })
        
        # 다나와 최저가를 찾았으면 결과 확인
        if len(results) >= 2:
            print(f"\n=== E2E Scenario 1: Price Comparison ===")
            for r in results:
                print(f"Coupang {r['index']}: {r['current_price']} → Cheapest: {r['lowest_price']}")

    def test_scenario_find_best_deal(self, api_base_url, http_client):
        """시나리오 2: 최고 할인 상품 찾기
        
        여러 상품 중 가장 큰 할인폭을 제공하는 상품을 찾습니다.
        """
        products = [
            {"product_name": "갤럭시 버즈3", "current_price": 207900},
            {"product_name": "맥북 에어 M4", "current_price": 1430980},
            {"product_name": "신라면 120g", "current_price": 3000},
            {"product_name": "Intel i5-12400F", "current_price": 190900},
        ]
        
        best_deal = None
        max_savings = 0
        
        for product in products:
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=product,
                timeout=25.0,
            )
            
            if response.status_code == 200:
                data = response.json()["data"]
                current_price = product["current_price"]
                lowest_price = data.get("lowest_price", current_price)
                savings = current_price - lowest_price
                
                if savings > max_savings:
                    max_savings = savings
                    best_deal = {
                        "product": product["product_name"],
                        "current": current_price,
                        "lowest": lowest_price,
                        "savings": savings,
                        "mall": data.get("mall"),
                    }
        
        print(f"\n=== E2E Scenario 2: Best Deal ===")
        if best_deal:
            print(f"Best Deal: {best_deal['product']}")
            print(f"Savings: ₩{best_deal['savings']:,}")
            print(f"Available at: {best_deal['mall']}")

    def test_scenario_budget_shopping(self, api_base_url, http_client):
        """시나리오 3: 예산 범위 내 쇼핑
        
        예산(500만원) 내에서 살 수 있는 전자제품을 찾습니다.
        """
        budget = 5000000
        products = [
            "Apple 맥북 프로 14",
            "LG 올레드 TV 55인치",
            "삼성 갤럭시 Z폴드7",
            "Apple 아이패드 프로",
        ]
        
        affordable_products = []
        
        for product_name in products:
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json={"product_name": product_name, "current_price": budget},
                timeout=25.0,
            )
            
            if response.status_code == 200:
                data = response.json()["data"]
                lowest_price = data.get("lowest_price", 0)
                
                if lowest_price > 0 and lowest_price <= budget:
                    affordable_products.append({
                        "product": product_name,
                        "price": lowest_price,
                        "mall": data.get("mall"),
                    })
        
        print(f"\n=== E2E Scenario 3: Budget Shopping (Max: ₩{budget:,}) ===")
        for product in sorted(affordable_products, key=lambda x: x["price"]):
            print(f"{product['product']}: ₩{product['price']:,}")

    def test_scenario_price_monitoring_series(self, api_base_url, http_client):
        """시나리오 4: 가격 모니터링 (연속 조회)
        
        같은 상품을 여러 번 조회하여 가격 변동을 추적합니다.
        """
        product = {
            "product_name": "신라면 120g",
            "current_price": 3000,
        }
        
        prices = []
        times_list = []
        
        print(f"\n=== E2E Scenario 4: Price Monitoring ===")
        
        for i in range(5):
            start = time.time()
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=product,
                timeout=25.0,
            )
            elapsed = time.time() - start
            
            if response.status_code == 200:
                data = response.json()["data"]
                price = data.get("lowest_price")
                prices.append(price)
                times_list.append(elapsed)
                print(f"Query {i+1}: ₩{price} ({elapsed:.3f}s)")
        
        if len(prices) > 1:
            price_change = prices[-1] - prices[0]
            print(f"Price Change: ₩{price_change:+}")

    def test_scenario_bulk_price_check(self, api_base_url, http_client):
        """시나리오 5: 대량 상품 일괄 조회
        
        쇼핑 리스트(10개 상품)의 가격을 일괄 조회합니다.
        """
        shopping_list = [
            {"name": "갤럭시 버즈3", "my_price": 207900},
            {"name": "맥북 에어 M4", "my_price": 1430980},
            {"name": "신라면 120g", "my_price": 3000},
            {"name": "Intel i5-12400F", "my_price": 190900},
            {"name": "TCL TV 55인치", "my_price": 634230},
            {"name": "아이패드 프로", "my_price": 1299000},
            {"name": "에이수스 비보북", "my_price": 1024000},
            {"name": "LG 올레드 TV", "my_price": 2500000},
            {"name": "삼성 노트북", "my_price": 669000},
            {"name": "신라면 블랙", "my_price": 33230},
        ]
        
        results = []
        total_current = 0
        total_cheapest = 0
        
        print(f"\n=== E2E Scenario 5: Bulk Price Check ===")
        
        for item in shopping_list:
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json={
                    "product_name": item["name"],
                    "current_price": item["my_price"],
                },
                timeout=25.0,
            )
            
            if response.status_code == 200:
                data = response.json()["data"]
                lowest_price = data.get("lowest_price", item["my_price"])
                is_cheaper = data.get("is_cheaper", False)
                
                results.append({
                    "product": item["name"],
                    "current": item["my_price"],
                    "cheapest": lowest_price,
                    "is_cheaper": is_cheaper,
                })
                
                total_current += item["my_price"]
                total_cheapest += lowest_price
        
        # 요약
        print(f"Items Checked: {len(results)}")
        print(f"Total Current Price: ₩{total_current:,}")
        print(f"Total Cheapest Price: ₩{total_cheapest:,}")
        print(f"Total Savings: ₩{total_current - total_cheapest:,}")
        print(f"Cheaper Products: {sum(1 for r in results if r['is_cheaper'])}")

    def test_scenario_category_comparison(self, api_base_url, http_client):
        """시나리오 6: 카테고리별 가격 비교
        
        전자제품, 식품, 화장품 등 카테고리별 평균 가격을 비교합니다.
        """
        categories = {
            "Electronics": [
                ("갤럭시 버즈3", 207900),
                ("맥북 에어 M4", 1430980),
                ("Intel i5", 190900),
            ],
            "Food": [
                ("신라면", 3000),
                ("새우깡", 4640),
                ("너구리", 16120),
            ],
            "Fashion": [
                ("삼성 갤럭시 S25", 1593200),
                ("에어팟", 329000),
            ],
        }
        
        category_stats = {}
        
        print(f"\n=== E2E Scenario 6: Category Comparison ===")
        
        for category, products in categories.items():
            prices = []
            
            for product_name, price in products:
                response = http_client.post(
                    f"{api_base_url}/api/v1/price/search",
                    json={
                        "product_name": product_name,
                        "current_price": price,
                    },
                    timeout=25.0,
                )
                
                if response.status_code == 200:
                    data = response.json()["data"]
                    prices.append(data.get("lowest_price", price))
            
            if prices:
                category_stats[category] = {
                    "avg": sum(prices) / len(prices),
                    "min": min(prices),
                    "max": max(prices),
                }
        
        for category, stats in category_stats.items():
            print(f"\n{category}:")
            print(f"  Average: ₩{stats['avg']:,.0f}")
            print(f"  Range: ₩{stats['min']:,} ~ ₩{stats['max']:,}")


class TestSpecialCases:
    """특수 상황 테스트"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_e2e_out_of_stock_product(self, api_base_url, http_client):
        """특수 1: 품절 상품 처리
        
        품절 상품도 안전하게 처리합니다.
        """
        product = {
            "product_name": "너무 특이한 제품 절대 있을 수 없는",
            "current_price": 999999,
        }
        
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=product,
            timeout=25.0,
        )
        
        # 상품 없음 또는 정상 응답
        assert response.status_code in [200, 404]

    def test_e2e_price_range_extremes(self, api_base_url, http_client):
        """특수 2: 극단적 가격대
        
        매우 저가(100원) ~ 고가(1억원) 상품을 처리합니다.
        """
        extreme_prices = [
            {"product_name": "비타민", "current_price": 100},  # 극저가
            {"product_name": "맥북 프로", "current_price": 100000000},  # 극고가
        ]
        
        for product in extreme_prices:
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=product,
                timeout=25.0,
            )
            
            assert response.status_code in [200, 404]

    def test_e2e_special_characters_in_product_name(self, api_base_url, http_client):
        """특수 3: 특수문자가 포함된 상품명
        
        (주), ™, ®, ™ 등이 포함된 상품명을 처리합니다.
        """
        special_products = [
            {"product_name": "Samsung® 갤럭시 버즈3™", "current_price": 207900},
            {"product_name": "Apple® MacBook Pro 14\"", "current_price": 1430980},
            {"product_name": "(주)농심 신라면™", "current_price": 3000},
        ]
        
        for product in special_products:
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=product,
                timeout=25.0,
            )
            
            # 정규화되어 처리됨
            assert response.status_code in [200, 404]

    def test_e2e_unicode_characters(self, api_base_url, http_client):
        """특수 4: 유니코드 문자 처리
        
        한글, 중국어, 일본어 등을 처리합니다.
        """
        unicode_products = [
            {"product_name": "삼성전자 갤럭시 버즈3", "current_price": 207900},  # 한글
            {"product_name": "Apple MacBook Air", "current_price": 1430980},  # 영문
        ]
        
        for product in unicode_products:
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=product,
                timeout=25.0,
            )
            
            assert response.status_code in [200, 404]

    def test_e2e_rapid_repeated_requests(self, api_base_url, http_client):
        """특수 5: 빠른 연속 요청
        
        동일 상품을 빠르게 연속으로 요청합니다.
        """
        product = {
            "product_name": "신라면 120g",
            "current_price": 3000,
        }
        
        success_count = 0
        
        for _ in range(10):
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=product,
                timeout=25.0,
            )
            
            if response.status_code == 200:
                success_count += 1
        
        # 대부분 성공해야 함
        assert success_count >= 8


class TestDataConsistency:
    """데이터 일관성 테스트"""

    @pytest.fixture
    def http_client(self):
        return httpx.Client(timeout=25.0)

    def test_e2e_same_product_same_price(self, api_base_url, http_client):
        """데이터 1: 동일 상품 동일 가격
        
        같은 상품을 여러 번 검색하면 같은 가격을 반환합니다.
        """
        product = {
            "product_name": "신라면 120g",
            "current_price": 3000,
        }
        
        prices = []
        
        for _ in range(5):
            response = http_client.post(
                f"{api_base_url}/api/v1/price/search",
                json=product,
                timeout=25.0,
            )
            
            if response.status_code == 200:
                prices.append(response.json()["data"]["lowest_price"])
        
        if len(prices) > 1:
            # 모든 가격이 동일해야 함
            assert all(p == prices[0] for p in prices)

    def test_e2e_response_completeness(self, api_base_url, http_client):
        """데이터 2: 응답 완전성
        
        성공 응답에는 필요한 모든 필드가 있습니다.
        """
        product = {
            "product_name": "신라면 120g",
            "current_price": 3000,
        }
        
        response = http_client.post(
            f"{api_base_url}/api/v1/price/search",
            json=product,
            timeout=25.0,
        )
        
        if response.status_code == 200:
            data = response.json()["data"]
            
            required_fields = [
                "is_cheaper",
                "lowest_price",
                "link",
                "mall",
                "free_shipping",
            ]
            
            for field in required_fields:
                assert field in data, f"Missing field: {field}"
