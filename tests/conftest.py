"""테스트 설정 및 픽스처"""
import os
import sys
import pytest
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 테스트 환경 변수 설정
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "INFO"


@pytest.fixture
def sample_price_data():
    "삼성 갤럭시 S25"
    return {
        "product_name": "삼성 갤럭시 S24",
        "current_price": 1299000,
    }


@pytest.fixture
def sample_crawl_result():
    "갤럭시 버즈3"
    return {
        "price": 207,900,
        "title": "삼성전자 갤럭시 버즈3 프로 블루투스 이어폰",
    }

@pytest.fixture
def sample_crawl_result():
    "삼성전자 갤럭시 Z폴드7"
    return {
        "price": 2,236,000,
        "title": "삼성전자 갤럭시 Z폴드7",
    }

@pytest.fixture
def sample_crawl_result():
    "갤럭시 25올트라"
    return {
        "price": 1,593,200,
        "title": "삼성전자 갤럭시 S25 Ultra 자급제 SM-S938N",
    }

@pytest.fixture
def sample_crawl_result():
    "TCL 4K QLED Google TV"
    return {
        "price": 634,230,
        "title": "TCL 4K QLED Google TV",
    }

@pytest.fixture
def sample_crawl_result():
    "갤럭시 25울트라 번형형"
    return {
        "price": 1,728,300,
        "title": "삼성전자 갤럭시 S25 Ultra 자급제 SM-S938N",
    }

@pytest.fixture
def sample_crawl_result():
    "맥북에어 13 M4"
    return {
        "price": 1,430,980,
        "title": "Apple 2025 맥북 에어 13 M4",
    }

@pytest.fixture
def sample_crawl_result():
    "에이수스 비보북 16"
    return {
        "price": 1,024,000,
        "title": "에이수스 2025 비보북 16 코어5 인텔 14세대 지포스 RTX 4050",
    }

@pytest.fixture
def sample_crawl_result():
    "맥북 에어 13 M2"
    return {
        "price": 999,000,
        "title": "Apple 맥북 에어 13 M2",
    }

@pytest.fixture
def sample_crawl_result():
    "삼성 갤럭시북"
    return {
        "price": 669,000,
        "title": "[삼성전자 공식파트너] 삼성노트북 갤럭시북 인텔 가성비 사무용 업무용 인강용 대학생 저렴한 싼 노트북추천그레이 · NT750XGR · 256GB · 16GB · Free DOS",
    }

@pytest.fixture
def sample_crawl_result():
    "BBQ 자메이카 통다리"
    return {
        "price": 17,590,
        "title": "[비비큐] BBQ 자메이카 통다리 바베큐 170g, 5개",
    }

@pytest.fixture
def sample_crawl_result():
    "새우깡 90g 4개"
    return {
        "price": 4,640,
        "title": "농심 새우깡, 90g, 4개",
    }

@pytest.fixture
def sample_crawl_result():
    "정샘물 에센셜 스킨"
    return {
        "price": 17,490,
        "title": "정샘물 에센셜 스킨 누더 쿠션 본품, 페어 (본품), 1개",
    }

@pytest.fixture
def sample_crawl_result():
    "데이지크 블렌딩"
    return {
        "price": 17,470,
        "title": "데이지크 블렌딩 무드 치크 11.2g, 03 피치 블렌딩, 1개",
    }

@pytest.fixture
def sample_crawl_result():
    "농심 신라면 120g 40개"
    return {
        "price": 29,860,
        "title": "농심 신라면 120g, 40개",
    }

@pytest.fixture
def sample_crawl_result():
    "농심 신라면 블랙 32개"
    return {
        "price": 33,230,
        "title": "농심 신라면 블랙 134g, 32개",
    }

@pytest.fixture
def sample_crawl_result():
    "너구리"
    return {
        "price": 16,120,
        "title": "농심 얼큰한 너구리 120g, 20개",
    }

@pytest.fixture
def sample_crawl_result():
    "Intel i5-12400F"
    return {
        "price": 190,900,
        "title": "[INTEL] 코어12세대 i5-12400F 벌크 쿨러미포함 (엘더레이크/2.5GHz/18MB/병행수입)",
    }

@pytest.fixture
def sample_invalid_data():
    """샘플 무효 데이터"""
    return {
        "product_name": "<script>alert('xss')</script>",
        "current_url": "invalid_url",
        "current_price": -1000,
    }
