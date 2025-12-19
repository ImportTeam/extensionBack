"""전역 테스트 설정 (PRD 준수)

역할:
- 테스트 환경 구성
- 공통 Dummy/Fake 주입
- 전역 상태 초기화

금지:
- 실제 상품 데이터
- Stress/E2E 시나리오 데이터
- API payload 대량 데이터
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pytest


# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session", autouse=True)
def test_env() -> None:
    """테스트 환경 변수 설정 (세션 전역)"""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["LOG_LEVEL"] = "INFO"


@dataclass
class DummyCache:
    """오케스트레이터 Unit 테스트용 더미 캐시

    - async get/set 지원
    - 저장된 값을 메모리에 유지
    """

    store: dict[str, dict[str, Any]]
    set_calls: int = 0

    async def get(self, key: str, timeout: float) -> Optional[dict[str, Any]]:
        _ = timeout
        return self.store.get(key)

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        _ = ttl
        self.set_calls += 1
        self.store[key] = value


@pytest.fixture
def dummy_cache() -> DummyCache:
    return DummyCache(store={})



# ============================================================================
# API 테스트용 픽스처
# ============================================================================

@pytest.fixture
def api_base_url():
    """API 베이스 URL (localhost:8000)"""
    return "http://localhost:8000"


@pytest.fixture
def api_search_payload_galaxy_buds3():
    """갤럭시 버즈3 검색 요청 (FE에서 보내는 형식)"""
    return {
        "product_name": "삼성전자 갤럭시 버즈3 프로 블루투스 이어폰",
        "current_price": 207900,
    }


@pytest.fixture
def api_search_payload_galaxy_s25_ultra():
    """갤럭시 S25 Ultra 검색 요청"""
    return {
        "product_name": "삼성전자 갤럭시 S25 Ultra 자급제",
        "current_price": 1593200,
    }


@pytest.fixture
def api_search_payload_macbook_m4():
    """맥북 에어 M4 검색 요청"""
    return {
        "product_name": "Apple 2025 맥북 에어 13 M4",
        "current_price": 1430980,
    }


@pytest.fixture
def api_search_payload_shin_ramyeon():
    """신라면 검색 요청"""
    return {
        "product_name": "농심 신라면 120g",
        "current_price": 29860,
    }


@pytest.fixture
def api_search_payload_intel_cpu():
    """Intel i5-12400F 검색 요청"""
    return {
        "product_name": "Intel 코어12세대 i5-12400F 벌크",
        "current_price": 190900,
    }


@pytest.fixture
def api_search_payloads_diverse():
    """다양한 상품 검색 요청 목록 (Unit/Coverage 테스트용)"""
    return [
        {
            "product_name": "삼성전자 갤럭시 버즈3 프로",
            "current_price": 207900,
        },
        {
            "product_name": "Apple 2025 맥북 에어 13 M4",
            "current_price": 1430980,
        },
        {
            "product_name": "농심 신라면 120g",
            "current_price": 2986,
        },
        {
            "product_name": "Intel i5-12400F 벌크",
            "current_price": 190900,
        },
        {
            "product_name": "TCL 4K QLED Google TV 55인치",
            "current_price": 634230,
        },
    ]


@pytest.fixture
def api_invalid_payloads():
    """무효한 API 요청 목록 (에러 처리 테스트용)"""
    return {
        "missing_product_name": {
            "current_price": 100000,
        },
        "empty_product_name": {
            "product_name": "",
            "current_price": 100000,
        },
        "negative_price": {
            "product_name": "아이폰",
            "current_price": -1000,
        },
        "non_numeric_price": {
            "product_name": "아이폰",
            "current_price": "가격",
        },
        "xss_injection": {
            "product_name": "<script>alert('xss')</script>",
            "current_price": 100000,
        },
    }


@pytest.fixture
def api_stress_payloads():
    """스트레스 테스트용 요청 목록 (100개 다양한 상품)"""
    base_products = [
        ("갤럭시 버즈3 프로", 207900),
        ("Apple 맥북 에어 M4", 1430980),
        ("삼성 갤럭시 S25", 1593200),
        ("TCL 4K TV 55인치", 634230),
        ("신라면 120g", 2986),
        ("Intel i5-12400F", 190900),
        ("애플 아이패드 프로 11", 1299000),
        ("LG 올레드 TV 55인치", 2500000),
        ("에이수스 비보북 16", 1024000),
        ("삼성 노트북 갤럭시북", 669000),
    ]
    
    payloads = []
    for i in range(10):
        for product_name, price in base_products:
            payloads.append({
                "product_name": f"{product_name} #{i}",
                "current_price": price + (i * 10000),
            })
    return payloads


@pytest.fixture
def expected_response_schema():
    """기대하는 API 응답 스키마"""
    return {
        "status": str,
        "data": {
            "is_cheaper": bool,
            "price_diff": int,
            "lowest_price": int,
            "link": str,
            "mall": str,
            "free_shipping": bool,
            "top_prices": list,
        },
        "message": str,
    }
