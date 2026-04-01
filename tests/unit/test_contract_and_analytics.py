from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app import create_app
from src.core.config import Settings
from src.api.routes.price_routes import search_price
from src.engine.result import SearchResult
from src.repositories.impl.search_log_repository import SearchLogRepository
from src.repositories.models import SearchLog
from src.scheduler.weekly_analytics import WeeklyAnalyticsScheduler
from src.schemas.price_schema import PriceSearchRequest
from src.core.database import Base


class StubOrchestrator:
    def __init__(self, result: SearchResult):
        self.result = result
        self.calls: list[tuple[str, str | None]] = []

    async def search(self, query: str, product_code: str | None = None) -> SearchResult:
        self.calls.append((query, product_code))
        return self.result


@pytest.mark.asyncio
async def test_price_search_request_accepts_options_and_options_text():
    request_from_alias = PriceSearchRequest(product_name="맥북", options="색상: 스페이스 블랙")
    request_from_name = PriceSearchRequest(product_name="맥북", options_text="색상: 스페이스 블랙")

    assert request_from_alias.options_text == "색상: 스페이스 블랙"
    assert request_from_name.options_text == "색상: 스페이스 블랙"


@pytest.mark.asyncio
async def test_search_response_uses_actual_product_name_and_preserves_metadata():
    orchestrator = StubOrchestrator(
        SearchResult.from_slowpath(
            product_url="https://prod.danawa.com/info/?pcode=12345",
            price=199000,
            query="정규화 검색어",
            elapsed_ms=321.0,
            product_id="12345",
            product_name="Apple 맥북 에어 13 M4",
            mall="쿠팡",
            free_shipping=True,
            top_prices=[
                {
                    "rank": 1,
                    "mall": "쿠팡",
                    "price": 199000,
                    "free_shipping": True,
                    "delivery": "무료배송",
                    "link": "https://shop.example/item",
                }
            ],
            price_trend=[{"label": "1일", "price": 199000}],
        )
    )

    response = await search_price(
        request=PriceSearchRequest(
            product_name="맥북",
            current_price=220000,
            product_code="12345",
        ),
        background_tasks=BackgroundTasks(),
        db=SimpleNamespace(),  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
    )

    assert response.status == "success"
    assert response.data is not None
    assert response.data.product_name == "Apple 맥북 에어 13 M4"
    assert response.data.mall == "쿠팡"
    assert response.data.free_shipping is True
    assert response.data.price_trend is not None
    assert response.data.price_trend[0].label == "1일"
    assert orchestrator.calls == [("맥북", "12345")]


@pytest.mark.asyncio
async def test_search_uses_pcode_extracted_from_current_url():
    orchestrator = StubOrchestrator(
        SearchResult.from_fastpath(
            product_url="https://prod.danawa.com/info/?pcode=98765",
            price=150000,
            query="정규화 검색어",
            elapsed_ms=111.0,
            product_id="98765",
            product_name="추출된 상품",
        )
    )

    response = await search_price(
        request=PriceSearchRequest(
            product_name="맥북",
            current_url="https://prod.danawa.com/info/?pcode=98765",
        ),
        background_tasks=BackgroundTasks(),
        db=SimpleNamespace(),  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
    )

    assert response.status == "success"
    assert orchestrator.calls == [("맥북", "98765")]


def test_search_log_statistics_count_success_cache_hits_and_legacy_hits():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    db.add_all(
        [
            SearchLog(query_name="q1", status="SUCCESS", source="cache"),
            SearchLog(query_name="q2", status="HIT", source=None),
            SearchLog(query_name="q3", status="FAIL", source="fastpath"),
        ]
    )
    db.commit()

    repo = SearchLogRepository(db)
    stats = repo.get_statistics(days=7)

    assert repo.get_cache_hit_count() == 2
    assert stats["cache_hits"] == 2
    assert stats["failures"] == 1


def test_weekly_scheduler_runs_synchronously(monkeypatch: pytest.MonkeyPatch):
    calls = {"report": 0, "recommendations": 0, "closed": 0}

    class FakeSession:
        def close(self):
            calls["closed"] += 1

    class FakeAnalyticsService:
        def __init__(self, db):
            self.db = db

        def generate_weekly_report(self):
            calls["report"] += 1
            return {
                "generated_at": "2026-01-01T00:00:00",
                "summary": {
                    "success_rate": 95,
                    "total_searches": 10,
                    "cache_hit_count": 3,
                    "fastpath_success_count": 4,
                    "slowpath_success_count": 2,
                    "avg_elapsed_ms": 120.0,
                },
                "performance": {"p50_ms": 100.0, "p95_ms": 180.0, "p99_ms": 220.0},
                "price_savings": {
                    "total_saved": 10000,
                    "avg_saved_amount": 5000.0,
                    "avg_saved_rate": 12.3,
                },
            }

        def get_improvement_recommendations(self):
            calls["recommendations"] += 1
            return {"recommendations": []}

    monkeypatch.setattr("src.scheduler.weekly_analytics.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr("src.scheduler.weekly_analytics.AnalyticsService", FakeAnalyticsService)

    assert inspect.iscoroutinefunction(WeeklyAnalyticsScheduler.run_weekly_analysis) is False

    result = WeeklyAnalyticsScheduler.run_weekly_analysis()

    assert result["status"] == "success"
    assert calls == {"report": 1, "recommendations": 1, "closed": 1}


def test_settings_validate_engine_budget_consistency():
    Settings(
        database_url="sqlite:///test.db",
        redis_url="redis://localhost:6379/0",
        engine_total_budget_s=12.0,
        engine_cache_timeout_s=0.5,
        engine_fastpath_timeout_s=8.0,
        engine_slowpath_timeout_s=3.0,
    )

    with pytest.raises(ValueError):
        Settings(
            database_url="sqlite:///test.db",
            redis_url="redis://localhost:6379/0",
            engine_total_budget_s=5.0,
            engine_cache_timeout_s=1.0,
            engine_fastpath_timeout_s=3.0,
            engine_slowpath_timeout_s=2.0,
        )


@pytest.mark.asyncio
async def test_app_lifecycle_owns_scheduler(monkeypatch: pytest.MonkeyPatch):
    events = {"start": 0, "shutdown": 0}

    class FakeScheduler:
        def __init__(self):
            self.running = False

        def start(self):
            self.running = True
            events["start"] += 1

        def shutdown(self, wait: bool = False):
            assert wait is False
            self.running = False
            events["shutdown"] += 1

    monkeypatch.setattr("src.app.init_db", lambda: None)
    monkeypatch.setattr("src.app.shutdown_shared_http_client", None, raising=False)
    monkeypatch.setattr(
        "src.scheduler.weekly_analytics.WeeklyAnalyticsScheduler.schedule_with_apscheduler",
        lambda: FakeScheduler(),
    )
    monkeypatch.setattr(
        "src.crawlers.http_client.shutdown_shared_http_client",
        lambda: None,
    )

    app = create_app()
    async with app.router.lifespan_context(app):
        assert hasattr(app.state, "weekly_scheduler")
        assert app.state.weekly_scheduler.running is True

    assert events == {"start": 1, "shutdown": 1}
    assert hasattr(app.state, "weekly_scheduler") is False
