"""
수동 크롤러 테스트 - 실제 다나와에서 가격 가져오기 확인
"""
import asyncio
from src.crawlers.danawa_crawler import DanawaCrawler


async def test_real_crawling():
    """실제 다나와 크롤링 테스트"""
    test_products = [
        "맥북",
        "아이폰 15 프로",
        "존재하지않는상품12345"
    ]
    
    async with DanawaCrawler() as crawler:
        for product in test_products:
            print(f"\n{'='*60}")
            print(f"검색: {product}")
            print('='*60)
            
            try:
                result = await crawler.search_lowest_price(product)
                
                if result:
                    print(f"✅ 성공")
                    print(f"  - 상품명: {result['product_name']}")
                    print(f"  - 최저가: {result['lowest_price']:,}원")
                    print(f"  - 쇼핑몰: {result.get('mall', 'N/A')}")
                    print(f"  - 링크: {result['link']}")
                else:
                    print("❌ 결과 없음")
                    
            except Exception as e:
                print(f"❌ 에러: {e}")


if __name__ == "__main__":
    asyncio.run(test_real_crawling())
