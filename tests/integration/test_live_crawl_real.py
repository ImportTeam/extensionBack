"""실제 FE 시나리오 기반 통합 테스트

FE가 보내는 정보:
- product_name: 쿠팡/지마켓/11번가 등에서 가져온 상품명
- current_url: 해당 쇼핑몰의 상품 URL (다나와 URL 아님!)
- current_price: 해당 쇼핑몰의 현재 가격

백엔드가 하는 일:
1) 상품명을 정규화해서 다나와에서 검색
2) 동일 제품 찾아서 크롤링
3) 최저가 / 최저가 구매 링크 / 무료배송 정보 반환
4) Redis에 캐시 저장

주의: 네트워크/브라우저 자원이 필요합니다. 환경 변수 LIVE_CRAWL=1 일 때만 실행됩니다.
"""
import os
import pytest
from src.services.cache_service import CacheService
from src.services.price_search_service import PriceSearchService
from src.utils.text_utils import clean_product_name

pytestmark = pytest.mark.asyncio


# ============================================================================
# FE 시나리오 1: 쿠팡에서 본 상품 → 다나와 최저가 비교 (맥북프로)
# ============================================================================
@pytest.mark.skipif(os.getenv("LIVE_CRAWL") != "1", reason="LIVE_CRAWL=1 일 때만 실행")
async def test_coupang_product_to_danawa():
    """쿠팡 상품 → 다나와 최저가 비교
    
    FE가 쿠팡에서 보고 있는 상품 정보를 보내면,
    백엔드가 다나와에서 동일 제품을 찾아 최저가를 알려줌
    """
    # FE에서 보내는 데이터 (쿠팡 상품 - 맥북프로 M4)
    product_name = "Apple 맥북프로 14 M4 Pro 12코어"
    current_url = "https://www.coupang.com/vp/products/9128826497"  # 쿠팡 URL (다나와 아님!)
    current_price = 2890000  # 쿠팡에서 보고 있는 가격

    cache = CacheService()
    service = PriceSearchService(cache)
    
    # 캐시 초기화
    search_key = clean_product_name(product_name)
    cache.delete(search_key)
    cache.delete_negative(search_key)

    # API 호출 (FE → BE)
    result = await service.search_price(
        product_name=product_name,
        current_price=current_price,
        product_code=None  # FE는 다나와 pcode를 모름
    )

    # 1. 검색 성공 검증
    assert result["status"] != "FAIL", f"❌ 검색 실패: {result['message']}"
    assert result["lowest_price"] > 0, "최저가는 0보다 커야 함"
    
    # 2. 최저가 정보 검증
    assert result.get("link"), "최저가 구매 링크가 없음"
    assert result.get("mall"), "최저가 쇼핑몰명이 없음"
    assert result.get("free_shipping") is not None, "무료배송 여부가 없음"
    
    # 3. 가격 비교 정보 검증
    assert "is_cheaper" in result, "is_cheaper 필드 없음"
    assert "price_diff" in result, "price_diff 필드 없음"
    
    # 4. TOP3 쇼핑몰 정보 검증
    top_prices = result.get("top_prices") or []
    assert len(top_prices) >= 1, "최소 1개 쇼핑몰 정보 필요"
    
    for idx, item in enumerate(top_prices):
        assert item.get("rank") == idx + 1
        assert item.get("mall"), f"쇼핑몰명 없음 (rank {idx+1})"
        assert item.get("price") > 0, f"가격 없음 (rank {idx+1})"
        assert "free_shipping" in item, f"무료배송 여부 없음 (rank {idx+1})"
        assert item.get("link"), f"구매 링크 없음 (rank {idx+1})"
    
    # 5. Redis 캐시 저장 검증
    cached = cache.get(search_key)
    assert cached is not None, "❌ Redis에 캐시가 저장되지 않음"
    assert cached.lowest_price == result["lowest_price"]
    
    # 결과 출력
    print(f"\n✅ 쿠팡 → 다나와 최저가 비교 성공!")
    print(f"  📦 상품명: {product_name[:50]}...")
    print(f"  🏷️ 쿠팡 가격: {current_price:,}원")
    print(f"  💰 다나와 최저가: {result['lowest_price']:,}원 ({result['mall']})")
    print(f"  📊 가격차이: {result['price_diff']:,}원 ({'더 저렴' if result['is_cheaper'] else '더 비쌈'})")
    print(f"  🚚 무료배송: {'예' if result['free_shipping'] else '아니오'}")
    print(f"  🔗 구매 링크: {result['link'][:60]}...")
    print(f"  📋 TOP3: {len(top_prices)}개 쇼핑몰")


# ============================================================================
# FE 시나리오 2: 11번가에서 본 상품 → 다나와 최저가 비교 (에어팟)
# ============================================================================
@pytest.mark.skipif(os.getenv("LIVE_CRAWL") != "1", reason="LIVE_CRAWL=1 일 때만 실행")
async def test_11st_product_to_danawa():
    """11번가 상품 → 다나와 최저가 비교"""
    # FE에서 보내는 데이터 (11번가 상품 - 에어팟 프로)
    product_name = "Apple 에어팟 프로 2세대"
    current_url = "https://www.11st.co.kr/products/12345678"  # 11번가 URL
    current_price = 329000

    cache = CacheService()
    service = PriceSearchService(cache)
    
    search_key = clean_product_name(product_name)
    cache.delete(search_key)
    cache.delete_negative(search_key)

    result = await service.search_price(
        product_name=product_name,
        current_price=current_price,
        product_code=None
    )

    assert result["status"] != "FAIL", f"❌ 검색 실패: {result['message']}"
    assert result["lowest_price"] > 0
    assert result.get("link")
    assert result.get("mall")
    
    # Redis 캐시 검증
    cached = cache.get(search_key)
    assert cached is not None, "❌ Redis에 캐시가 저장되지 않음"
    
    print(f"\n✅ 11번가 → 다나와 최저가 비교 성공!")
    print(f"  📦 상품명: {product_name}")
    print(f"  🏷️ 11번가 가격: {current_price:,}원")
    print(f"  💰 다나와 최저가: {result['lowest_price']:,}원 ({result['mall']})")
    print(f"  📊 가격차이: {result['price_diff']:,}원")


# ============================================================================
# FE 시나리오 3: 캐시 히트 테스트 (같은 상품 2번 요청)
# ============================================================================
@pytest.mark.skipif(os.getenv("LIVE_CRAWL") != "1", reason="LIVE_CRAWL=1 일 때만 실행")
async def test_cache_hit_scenario():
    """같은 상품 2번 요청 시 캐시 히트"""
    product_name = "삼성전자 갤럭시 버즈3 프로"
    current_price = 289000

    cache = CacheService()
    service = PriceSearchService(cache)
    
    search_key = clean_product_name(product_name)
    cache.delete(search_key)
    cache.delete_negative(search_key)

    # 1차 요청: 캐시 MISS → 크롤링
    result1 = await service.search_price(
        product_name=product_name,
        current_price=current_price,
        product_code=None
    )
    assert result1["status"] == "MISS", "1차 요청은 캐시 MISS여야 함"
    
    # 2차 요청: 캐시 HIT
    result2 = await service.search_price(
        product_name=product_name,
        current_price=current_price,
        product_code=None
    )
    assert result2["status"] == "HIT", "2차 요청은 캐시 HIT여야 함"
    assert result2["lowest_price"] == result1["lowest_price"], "캐시된 가격과 동일해야 함"
    
    print(f"\n✅ 캐시 히트 테스트 성공!")
    print(f"  1차: {result1['status']} (크롤링)")
    print(f"  2차: {result2['status']} (캐시)")
    print(f"  가격: {result1['lowest_price']:,}원")


# ============================================================================
# FE 시나리오 4: 지마켓에서 본 상품 (간단한 상품명 - LG 그램)
# ============================================================================
@pytest.mark.skipif(os.getenv("LIVE_CRAWL") != "1", reason="LIVE_CRAWL=1 일 때만 실행")
async def test_gmarket_simple_product():
    """지마켓 상품 (간단한 상품명) → 다나와 최저가"""
    product_name = "LG전자 그램 15 2024"
    current_url = "https://item.gmarket.co.kr/Item?goodscode=12345"
    current_price = 1500000

    cache = CacheService()
    service = PriceSearchService(cache)
    
    search_key = clean_product_name(product_name)
    cache.delete(search_key)
    cache.delete_negative(search_key)

    result = await service.search_price(
        product_name=product_name,
        current_price=current_price,
        product_code=None
    )

    assert result["status"] != "FAIL", f"❌ 검색 실패: {result['message']}"
    assert result["lowest_price"] > 0
    
    # Redis 캐시 검증
    cached = cache.get(search_key)
    assert cached is not None, "❌ Redis에 캐시가 저장되지 않음"
    
    print(f"\n✅ 지마켓 → 다나와 최저가 비교 성공!")
    print(f"  📦 상품명: {product_name}")
    print(f"  🏷️ 지마켓 가격: {current_price:,}원")
    print(f"  💰 다나와 최저가: {result['lowest_price']:,}원 ({result['mall']})")


# ============================================================================
# FE 시나리오 5: 복잡한 상품명 (스펙 덕지덕지 - 삼성 갤럭시북)
# ============================================================================
@pytest.mark.skipif(os.getenv("LIVE_CRAWL") != "1", reason="LIVE_CRAWL=1 일 때만 실행")
async def test_complex_product_name_normalization():
    """복잡한 상품명 정규화 후 검색"""
    # 쿠팡에서 흔히 보이는 스펙이 덕지덕지 붙은 상품명
    product_name = "삼성전자 갤럭시북4 프로 NT940XGK"
    current_url = "https://www.coupang.com/vp/products/7654321"
    current_price = 2190000

    cache = CacheService()
    service = PriceSearchService(cache)
    
    search_key = clean_product_name(product_name)
    cache.delete(search_key)
    cache.delete_negative(search_key)

    result = await service.search_price(
        product_name=product_name,
        current_price=current_price,
        product_code=None
    )

    # 정규화 덕분에 검색 성공해야 함
    assert result["status"] != "FAIL", f"❌ 검색 실패: {result['message']}"
    assert result["lowest_price"] > 0
    
    print(f"\n✅ 복잡한 상품명 검색 성공!")
    print(f"  원본: {product_name}")
    print(f"  정규화: {search_key}")
    print(f"  최저가: {result['lowest_price']:,}원")


# ============================================================================
# FE 시나리오 6: 상품명만으로 검색 (URL/가격 없이)
# ============================================================================
@pytest.mark.skipif(os.getenv("LIVE_CRAWL") != "1", reason="LIVE_CRAWL=1 일 때만 실행")
async def test_product_name_only():
    """상품명만으로 검색 (URL, 가격 없이)"""
    product_name = "에어팟 프로 2세대"

    cache = CacheService()
    service = PriceSearchService(cache)
    
    search_key = clean_product_name(product_name)
    cache.delete(search_key)
    cache.delete_negative(search_key)

    result = await service.search_price(
        product_name=product_name,
        current_price=None,  # 가격 없음
        product_code=None
    )

    assert result["status"] != "FAIL", f"❌ 검색 실패: {result['message']}"
    assert result["lowest_price"] > 0
    assert result.get("link")
    assert result.get("mall")
    
    # 가격 비교 정보는 current_price가 없으므로 기본값
    # current_price=None이면 is_cheaper=False, price_diff=0이 정상
    assert result["is_cheaper"] is False  # 비교 불가
    assert result["price_diff"] == 0  # current_price가 없어서 비교 불가
    
    print(f"\n✅ 상품명만으로 검색 성공!")
    print(f"  검색어: {product_name}")
    print(f"  최저가: {result['lowest_price']:,}원 ({result['mall']})")


# ============================================================================
# Redis 캐시 상태 확인용 헬퍼 테스트
# ============================================================================
@pytest.mark.skipif(os.getenv("LIVE_CRAWL") != "1", reason="LIVE_CRAWL=1 일 때만 실행")
async def test_redis_connection_and_ttl():
    """Redis 연결 및 TTL 확인"""
    cache = CacheService()
    
    # 연결 확인
    assert cache.health_check() is True, "❌ Redis 연결 실패"
    
    # 테스트용 키 저장
    test_data = {
        "product_name": "테스트 상품",
        "lowest_price": 100000,
        "link": "https://test.com",
        "source": "danawa",
        "mall": "테스트몰",
        "free_shipping": True,
        "top_prices": [],
        "price_trend": [],
        "updated_at": "2024-01-01T00:00:00"
    }
    
    cache.set("테스트 상품", test_data)
    
    # 캐시 조회
    cached = cache.get("테스트 상품")
    assert cached is not None, "❌ 캐시 저장/조회 실패"
    assert cached.lowest_price == 100000
    
    # TTL 확인
    from src.utils.hash_utils import generate_cache_key
    cache_key = generate_cache_key("테스트 상품")
    ttl = cache.redis_client.ttl(cache_key)
    assert ttl > 0, "❌ TTL이 설정되지 않음"
    
    # 정리
    cache.delete("테스트 상품")
    
    print(f"\n✅ Redis 연결 및 캐시 테스트 성공!")
    print(f"  연결: OK")
    print(f"  TTL: {ttl}초")
