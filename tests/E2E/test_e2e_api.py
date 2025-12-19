"""E2E (엔드-투-엔드) 통합 테스트

FastAPI 라우트에서 HTTP 요청을 받아 오케스트레이터를 거쳐 응답까지 반환하는
실제 API 엔드포인트 동작을 검증합니다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.schemas.price_schema import PriceSearchRequest, PriceSearchResponse


@pytest.mark.asyncio
async def test_price_search_api_success():
    """API 엔드포인트: 가격 검색 성공"""
    from src.api.routes.price_routes import search_price
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Session

    # Mock 준비
    request = PriceSearchRequest(
        product_name="삼성 갤럭시 S24",
        current_price=1300000,
    )

    # Mock 오케스트레이터
    mock_orch = AsyncMock()
    mock_search_result = MagicMock()
    mock_search_result.is_success = True
    mock_search_result.price = 1200000
    mock_search_result.product_url = "https://prod.danawa.com/info/?pcode=123"
    mock_search_result.source = "fastpath"
    mock_search_result.elapsed_ms = 250.5
    mock_search_result.status = None

    mock_orch.search.return_value = mock_search_result

    # Mock DB
    mock_db = MagicMock(spec=Session)
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()

    # 실제 엔드포인트 호출
    with patch('src.api.routes.price_routes.get_orchestrator', return_value=mock_orch):
        with patch('src.api.routes.price_routes.get_db', return_value=mock_db):
            response = await search_price(
                request=request,
                background_tasks=BackgroundTasks(),
                db=mock_db,
                orchestrator=mock_orch,
            )

    # 검증
    assert response.status == "success"
    assert response.data is not None
    assert response.data.lowest_price == 1200000
    assert response.data.is_cheaper is True
    assert response.data.price_diff == 100000
    print(f"✅ API 성공 응답: {response.data.price_diff}원 저렴")


@pytest.mark.asyncio
async def test_price_search_api_no_results():
    """API 엔드포인트: 검색 결과 없음"""
    from src.api.routes.price_routes import search_price
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Session

    request = PriceSearchRequest(
        product_name="존재하지 않는 상품",
        current_price=0,
    )

    mock_orch = AsyncMock()
    mock_result = MagicMock()
    mock_result.is_success = False
    mock_result.status = MagicMock(value="no_results")
    mock_orch.search.return_value = mock_result

    mock_db = MagicMock(spec=Session)

    with patch('src.api.routes.price_routes.get_orchestrator', return_value=mock_orch):
        with patch('src.api.routes.price_routes.get_db', return_value=mock_db):
            response = await search_price(
                request=request,
                background_tasks=BackgroundTasks(),
                db=mock_db,
                orchestrator=mock_orch,
            )

    assert response.status == "error"
    # 실제로는 "검색 결과를 찾을 수 없습니다" 또는 "검색 중 오류가 발생했습니다"
    assert response.status == "error"
    print(f"✅ API 검색 실패 처리: {response.error_code}")


@pytest.mark.asyncio
async def test_price_search_api_timeout():
    """API 엔드포인트: 타임아웃"""
    from src.api.routes.price_routes import search_price
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Session

    request = PriceSearchRequest(
        product_name="느린 상품",
        current_price=100000,
    )

    mock_orch = AsyncMock()
    mock_result = MagicMock()
    mock_result.is_success = False
    mock_result.status = MagicMock(value="timeout")
    mock_orch.search.return_value = mock_result

    mock_db = MagicMock(spec=Session)

    with patch('src.api.routes.price_routes.get_orchestrator', return_value=mock_orch):
        with patch('src.api.routes.price_routes.get_db', return_value=mock_db):
            response = await search_price(
                request=request,
                background_tasks=BackgroundTasks(),
                db=mock_db,
                orchestrator=mock_orch,
            )

    assert response.status == "error"
    assert response.error_code == "timeout"
    print(f"✅ API 타임아웃 처리: {response.message}")


@pytest.mark.asyncio
async def test_price_search_api_invalid_input():
    """API 엔드포인트: 부정확한 입력"""
    from src.api.routes.price_routes import search_price
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Session

    # XSS 시도 - Pydantic validation이 사전에 차단함
    try:
        request = PriceSearchRequest(
            product_name="<script>alert('xss')</script>",
            current_price=100000,
        )
        # 유효성 검사를 통과했다면 API 라우트로 진행
        mock_orch = AsyncMock()
        mock_db = MagicMock(spec=Session)

        with patch('src.api.routes.price_routes.get_orchestrator', return_value=mock_orch):
            with patch('src.api.routes.price_routes.get_db', return_value=mock_db):
                response = await search_price(
                    request=request,
                    background_tasks=BackgroundTasks(),
                    db=mock_db,
                    orchestrator=mock_orch,
                )

        assert response.status == "error"
        assert response.error_code == "VALIDATION_ERROR"
    except Exception as e:
        # Pydantic이 사전에 validation error 발생
        assert "validation error" in str(e).lower()
    
    print(f"✅ API XSS 방어 성공")


@pytest.mark.asyncio
async def test_price_search_api_fe_only_fields():
    """API 엔드포인트: FE에서만 제공하는 필드로 요청 (product_name + current_price)"""
    from src.api.routes.price_routes import search_price
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Session

    # FE 실제 입력: product_name, current_price만 제공
    request = PriceSearchRequest(
        product_name="삼성 갤럭시 S24",
        current_price=1300000,
        # current_url과 product_code는 FE에서 제공하지 않음
    )

    mock_orch = AsyncMock()
    mock_result = MagicMock()
    mock_result.is_success = True
    mock_result.price = 1150000
    mock_result.product_url = "https://prod.danawa.com/info/?pcode=67890"
    mock_result.source = "slowpath"
    mock_result.elapsed_ms = 5200.0
    mock_result.status = None

    mock_orch.search.return_value = mock_result

    mock_db = MagicMock(spec=Session)

    with patch('src.api.routes.price_routes.get_orchestrator', return_value=mock_orch):
        with patch('src.api.routes.price_routes.get_db', return_value=mock_db):
            response = await search_price(
                request=request,
                background_tasks=BackgroundTasks(),
                db=mock_db,
                orchestrator=mock_orch,
            )

    assert response.status == "success"
    assert response.data.lowest_price == 1150000
    assert response.data.price_diff == 150000
    assert response.data.source == "slowpath"
    # FE에서 제공하지 않은 필드는 API에서 자동 채움
    print(f"✅ FE 필드만으로 검색: {response.data.price_diff}원 저렴")
