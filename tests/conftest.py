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
    """샘플 가격 데이터"""
    return {
        "product_name": "삼성 갤럭시 S24",
        "current_url": "https://prod.danawa.com/info/?pcode=9876543",
        "current_price": 1299000,
    }


@pytest.fixture
def sample_crawl_result():
    """샘플 크롤링 결과"""
    return {
        "product_url": "https://example.com/product/123",
        "price": 500000,
        "title": "샘플 상품",
        "source": "test_source",
    }


@pytest.fixture
def sample_invalid_data():
    """샘플 무효 데이터"""
    return {
        "product_name": "<script>alert('xss')</script>",
        "current_url": "invalid_url",
        "current_price": -1000,
    }
