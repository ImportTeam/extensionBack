from src.crawlers.boundary.http_fastpath_parsing import (
    parse_product_lowest_price,
    parse_search_pcandidates,
)
from src.utils.text_utils import evaluate_match


def test_evaluate_match_rejects_non_main_product_candidate():
    query = "Apple 2025 에어팟 프로 3 USB-C 블루투스 이어폰"
    candidate = "(새제품) 에어팟 프로 2세대 USB-C 한쪽 왼쪽 유닛 에어팟 왼쪽 A3048 단품 본체미포함"

    decision = evaluate_match(query, candidate)

    assert decision.accepted is False
    assert "왼쪽" in decision.forbidden_hits or "한쪽" in decision.forbidden_hits
    assert decision.reason == "forbidden_non_main_product"


def test_evaluate_match_rejects_missing_required_signals():
    query = "Apple 2025 에어팟 프로 3 USB-C 블루투스 이어폰"
    candidate = "Apple 에어팟 2세대 라이트닝 블루투스 이어폰"

    decision = evaluate_match(query, candidate)

    assert decision.accepted is False
    assert any(item.startswith("variant:pro") for item in decision.required_missing)
    assert any(item.startswith("interface:usb-c") for item in decision.required_missing)


def test_evaluate_match_allows_explicit_non_main_query():
    query = "에어팟 프로 왼쪽 유닛"
    candidate = "에어팟 프로 왼쪽 유닛 단품"

    decision = evaluate_match(query, candidate)

    assert decision.accepted is True
    assert decision.forbidden_hits == []


def test_parse_search_pcandidates_skips_non_main_candidate():
    html = """
    <html>
      <body>
        <div class="prod_item">
          <div class="prod_name">
            <a href="https://prod.danawa.com/info/?pcode=11111">
              에어팟 프로 2세대 USB-C 한쪽 왼쪽 유닛 단품
            </a>
          </div>
        </div>
        <div class="prod_item">
          <div class="prod_name">
            <a href="https://prod.danawa.com/info/?pcode=22222">
              Apple 에어팟 프로 3 USB-C 블루투스 이어폰
            </a>
          </div>
        </div>
      </body>
    </html>
    """

    candidates = parse_search_pcandidates(
        html,
        query="Apple 2025 에어팟 프로 3 USB-C 블루투스 이어폰",
        max_candidates=5,
    )

    assert candidates == ["22222"]


def test_parse_product_lowest_price_rejects_non_main_detail_title():
    html = """
    <html>
      <body>
        <div class="prod_tit">에어팟 프로 2세대 USB-C 한쪽 왼쪽 유닛 단품 본체미포함</div>
        <div id="lowPriceCompanyArea">
          <div class="box__mall-price">
            <ul class="list__mall-price">
              <li class="list-item">
                <span class="sell-price"><span class="text__num">199,000</span></span>
                <div class="box__logo"><img alt="테스트몰" /></div>
                <div class="box__delivery">무료배송</div>
                <a class="link__full-cover" href="https://shop.example/item"></a>
              </li>
            </ul>
          </div>
        </div>
      </body>
    </html>
    """

    result = parse_product_lowest_price(
        html,
        fallback_name="Apple 2025 에어팟 프로 3 USB-C 블루투스 이어폰",
        product_url="https://prod.danawa.com/info/?pcode=11111",
    )

    assert result is None
