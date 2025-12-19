"""테스트 설정 및 픽스처"""
import os
import sys
import pytest
from pathlib import Path
from typing import Dict, Any

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 테스트 환경 변수 설정
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "INFO"


# ============================================================================
# 기본 테스트 데이터 픽스처 (18개 실제 상품)
# ============================================================================

@pytest.fixture
def sample_price_data():
    """샘플 가격 검색 요청"""
    return {
        "product_name": "삼성 갤럭시 S24",
        "current_price": 1299000,
    }


# 전자제품 (고가)
@pytest.fixture
def crawl_galaxy_buds3():
    """갤럭시 버즈3 - 이어폰"""
    return {
        "price": 207900,
        "title": "삼성전자 갤럭시 버즈3 프로 블루투스 이어폰",
    }

@pytest.fixture
def crawl_galaxy_zfold7():
    """갤럭시 Z폴드7 - 폴더블 스마트폰"""
    return {
        "price": 2236000,
        "title": "삼성전자 갤럭시 Z폴드7",
    }

@pytest.fixture
def crawl_galaxy_s25_ultra():
    """갤럭시 S25 Ultra - 플래그십"""
    return {
        "price": 1593200,
        "title": "삼성전자 갤럭시 S25 Ultra 자급제 SM-S938N",
    }

@pytest.fixture
def crawl_tcl_tv():
    """TCL 4K QLED Google TV - TV"""
    return {
        "price": 634230,
        "title": "TCL 4K QLED Google TV 55인치",
    }

@pytest.fixture
def crawl_macbook_m4():
    """맥북 에어 13 M4 - 노트북"""
    return {
        "price": 1430980,
        "title": "Apple 2025 맥북 에어 13 M4",
    }

@pytest.fixture
def crawl_asus_vivobook():
    """에이수스 비보북 16 - 노트북"""
    return {
        "price": 1024000,
        "title": "에이수스 2025 비보북 16 코어5 인텔 14세대 지포스 RTX 4050",
    }

@pytest.fixture
def crawl_macbook_m2():
    """맥북 에어 13 M2 - 구형 노트북"""
    return {
        "price": 999000,
        "title": "Apple 맥북 에어 13 M2",
    }

@pytest.fixture
def crawl_samsung_notebook():
    """삼성 갤럭시북 - 노트북"""
    return {
        "price": 669000,
        "title": "삼성전자 공식 삼성노트북 갤럭시북 인텔 NT750XGR",
    }

# 중저가 상품
@pytest.fixture
def crawl_bbq_chicken():
    """BBQ 자메이카 통다리 - 식품"""
    return {
        "price": 17590,
        "title": "[비비큐] BBQ 자메이카 통다리 바베큐 170g, 5개",
    }

@pytest.fixture
def crawl_shrimp_snack():
    """새우깡 90g 4개 - 간식"""
    return {
        "price": 4640,
        "title": "농심 새우깡, 90g, 4개",
    }

@pytest.fixture
def crawl_skin_essence():
    """정샘물 에센셜 스킨 - 화장품"""
    return {
        "price": 17490,
        "title": "정샘물 에센셜 스킨 누더 쿠션 본품, 페어",
    }

@pytest.fixture
def crawl_blending_cheek():
    """데이지크 블렌딩 - 화장품"""
    return {
        "price": 17470,
        "title": "데이지크 블렌딩 무드 치크 11.2g, 03 피치",
    }

@pytest.fixture
def crawl_shin_ramyeon_40():
    """농심 신라면 120g 40개 - 라면"""
    return {
        "price": 29860,
        "title": "농심 신라면 120g, 40개",
    }

@pytest.fixture
def crawl_shin_ramyeon_black():
    """농심 신라면 블랙 32개 - 라면"""
    return {
        "price": 33230,
        "title": "농심 신라면 블랙 134g, 32개",
    }

@pytest.fixture
def crawl_noguri():
    """농심 너구리 20개 - 라면"""
    return {
        "price": 16120,
        "title": "농심 얼큰한 너구리 120g, 20개",
    }

@pytest.fixture
def crawl_intel_cpu():
    """Intel i5-12400F - CPU"""
    return {
        "price": 190900,
        "title": "[INTEL] 코어12세대 i5-12400F 벌크 쿨러미포함",
    }


# ============================================================================
# 에러 시나리오 픽스처
# ============================================================================

@pytest.fixture
def sample_invalid_data():
    """샘플 무효 데이터 - XSS, 유효하지 않은 URL, 음수 가격"""
    return {
        "product_name": "<script>alert('xss')</script>",
        "current_url": "invalid_url",
        "current_price": -1000,
    }

@pytest.fixture
def sample_missing_data():
    """필수 필드 누락 데이터"""
    return {
        "product_name": "",
        "current_price": None,
    }

@pytest.fixture
def sample_extreme_data():
    """극단값 테스트 데이터"""
    return {
        "product_name": "A" * 1000,  # 매우 긴 상품명
        "current_price": 999999999999,  # 매우 큰 가격
    }


# ============================================================================
# 스트레스 테스트 픽스처
# ============================================================================

@pytest.fixture
def stress_test_queries():
    """스트레스 테스트용 대량 쿼리 (100개)"""
    products = [
        "아이폰 16 Pro",
        "갤럭시 S25",
        "픽셀 9",
        "삼성 QN90D TV",
        "LG 올레드 TV",
        "맥북 프로 14",
        "맥북 에어 M4",
        "아이패드 프로 11",
        "아이패드 에어",
        "아이패드 미니",
    ]
    
    # 10배 반복해서 100개 생성
    return [f"{product} #{i % 10}" for i in range(100) for product in products]


# ============================================================================
# 봇 차단 시뮬레이션 픽스처
# ============================================================================

@pytest.fixture
def bot_blocking_scenarios():
    """봇 차단 시뮬레이션 시나리오"""
    return {
        "ip_blocked": {
            "status_code": 403,
            "error": "IP차단",
            "expected": "FastPath 실패 → SlowPath 시도",
        },
        "user_agent_blocked": {
            "status_code": 403,
            "error": "User-Agent 차단",
            "expected": "FastPath 실패 → SlowPath 시도",
        },
        "rate_limited": {
            "status_code": 429,
            "error": "Too Many Requests",
            "expected": "요청 대기 후 재시도",
        },
        "cloudflare_challenge": {
            "status_code": 202,
            "error": "Cloudflare 챌린지",
            "expected": "SlowPath (JavaScript 필요)",
        },
    }


# ============================================================================
# 캐시 검증 픽스처
# ============================================================================

@pytest.fixture
def cache_test_data():
    """캐시 테스트 데이터"""
    return {
        "fast_moving_product": {
            "query": "신상 아이폰",
            "price_variance": 50000,  # 가격 변동 폭
            "check_interval": 3600,  # 1시간마다 업데이트
        },
        "stable_product": {
            "query": "라면",
            "price_variance": 100,  # 가격 거의 변하지 않음
            "check_interval": 86400,  # 1일마다 확인
        },
    }


@pytest.fixture
def concurrent_request_data():
    """동시 요청 테스트 데이터"""
    return {
        "user_count": 20,
        "requests_per_user": 5,
        "total_requests": 100,  # 20 * 5
        "cache_hit_expected": "70%+",
    }
