from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.config import Settings, settings
from src.crawlers.boundary.http_fastpath import DanawaHttpFastPath


def test_settings_default_to_http_only():
    local_settings = Settings(
        database_url="sqlite:///test.db",
        redis_url="redis://localhost:6379/0",
    )

    assert local_settings.crawler_slowpath_backend == "disabled"
    assert local_settings.api_price_search_timeout_s == 11.0


def test_get_orchestrator_uses_disabled_slowpath(monkeypatch: pytest.MonkeyPatch):
    from src.api.routes import price_routes

    class FakeCacheAdapter:
        def __init__(self, cache_service):
            self.cache_service = cache_service

    class FakeFastPathExecutor:
        pass

    class FakeDisabledSlowPathExecutor:
        pass

    class FakeSearchOrchestrator:
        def __init__(self, cache_service, fastpath_executor, slowpath_executor, budget_config):
            self.cache_service = cache_service
            self.fastpath_executor = fastpath_executor
            self.slowpath_executor = slowpath_executor
            self.budget_config = budget_config

    monkeypatch.setattr(price_routes, "_orchestrator", None)
    monkeypatch.setattr(price_routes.settings, "crawler_slowpath_backend", "disabled")
    monkeypatch.setattr(price_routes, "CacheAdapter", FakeCacheAdapter)
    monkeypatch.setattr(price_routes, "FastPathExecutor", FakeFastPathExecutor)
    monkeypatch.setattr(price_routes, "DisabledSlowPathExecutor", FakeDisabledSlowPathExecutor)
    monkeypatch.setattr(
        price_routes,
        "SlowPathExecutor",
        lambda: (_ for _ in ()).throw(AssertionError("Playwright slowpath should not be created")),
    )
    monkeypatch.setattr(price_routes, "SearchOrchestrator", FakeSearchOrchestrator)

    orchestrator = price_routes.get_orchestrator(cache_service=SimpleNamespace())

    assert isinstance(orchestrator.slowpath_executor, FakeDisabledSlowPathExecutor)


@pytest.mark.asyncio
async def test_fastpath_can_fall_through_to_next_candidate(monkeypatch: pytest.MonkeyPatch):
    fastpath = DanawaHttpFastPath()
    requests: list[str] = []

    search_html = """
    <html><body>
      <div class="prod_item"><div class="prod_name">
        <a href="https://prod.danawa.com/info/?pcode=11111">부분품 유닛 단품</a>
      </div></div>
      <div class="prod_item"><div class="prod_name">
        <a href="https://prod.danawa.com/info/?pcode=22222">ASUS TUF 게이밍 F16 코어 i7 RTX 5060</a>
      </div></div>
    </body></html>
    """
    product_html = """
    <html><body>
      <div class="prod_tit">ASUS TUF 게이밍 F16 코어 i7 RTX 5060</div>
      <div id="lowPriceCompanyArea">
        <div class="box__mall-price">
          <ul class="list__mall-price">
            <li class="list-item">
              <span class="sell-price"><span class="text__num">1,899,000</span></span>
              <div class="box__logo"><img alt="테스트몰" /></div>
              <div class="box__delivery">무료배송</div>
              <a class="link__full-cover" href="https://shop.example/item"></a>
            </li>
          </ul>
        </div>
      </div>
    </body></html>
    """

    async def fake_fetch_html(url: str, timeout_ms: int):
        requests.append(url)
        if "dsearch.php" in url:
            return search_html
        if "pcode=22222" in url:
            return product_html
        return None

    monkeypatch.setattr(fastpath, "_fetch_html", fake_fetch_html)
    monkeypatch.setattr(settings, "crawler_http_request_timeout_ms", 2500)
    monkeypatch.setattr(settings, "crawler_http_product_timeout_ms", 3500)
    monkeypatch.setattr(settings, "crawler_http_max_search_candidates", 2)
    monkeypatch.setattr(settings, "crawler_http_max_pcodes_per_candidate", 2)

    result = await fastpath.search_lowest_price(
        query="에이수스 2025 TUF 게이밍 F16 코어i7 인텔 14세대 지포스 RTX 5060",
        candidates=[
            "에이수스 2025 TUF 게이밍 F16 코어i7 인텔 14세대 지포스 RTX 5060",
            "ASUS TUF 게이밍 F16 코어 i7 RTX 5060",
        ],
        total_timeout_ms=8500,
    )

    assert result is not None
    assert result["pcode"] == "22222"
    assert any("dsearch.php" in url for url in requests)
    assert any("pcode=22222" in url for url in requests)


@pytest.mark.asyncio
async def test_fastpath_stops_when_detail_budget_cannot_be_reserved(monkeypatch: pytest.MonkeyPatch):
    fastpath = DanawaHttpFastPath()
    called = {"fetch": 0}

    async def fake_fetch_html(url: str, timeout_ms: int):
        called["fetch"] += 1
        return None

    monkeypatch.setattr(fastpath, "_fetch_html", fake_fetch_html)
    monkeypatch.setattr(settings, "crawler_http_request_timeout_ms", 2500)
    monkeypatch.setattr(settings, "crawler_http_product_timeout_ms", 3500)

    result = await fastpath.search_lowest_price(
        query="테스트 상품",
        candidates=["테스트 상품"],
        total_timeout_ms=2000,
    )

    assert result is None
    assert called["fetch"] == 0
