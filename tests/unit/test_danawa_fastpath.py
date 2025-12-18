from src.crawlers.boundary.http_fastpath_parsing import (
    extract_pcode_from_href,
    has_product_fingerprint,
    has_search_fingerprint,
    is_probably_invalid_html,
    parse_product_lowest_price,
)


def test_extract_pcode_from_href():
    assert extract_pcode_from_href("/info/?pcode=12345") == "12345"
    assert extract_pcode_from_href("https://prod.danawa.com/info/?pcode=999") == "999"
    assert extract_pcode_from_href("/info/?foo=bar") is None


def test_fastpath_blocking_min_length_and_fingerprint():
    tiny = "<html><body>hi</body></html>"
    assert is_probably_invalid_html(tiny) is True

    search_html = """
    <html><body>
      <div class='prod_item'>
        <div class='prod_name'><a href='/info/?pcode=123'>Apple MacBook</a></div>
      </div>
    </body></html>
    """ + ("x" * 6000)
    assert is_probably_invalid_html(search_html) is False
    assert has_search_fingerprint(search_html) is True

    product_html = """
    <html><body>
      <div class='prod_tit'>Some Product</div>
      <div id='lowPriceCompanyArea'>
        <div class='box__mall-price'>
          <ul class='list__mall-price'>
            <li class='list-item'>
              <span class='sell-price'><span class='text__num'>1,234</span></span>
              <span class='box__logo'><img alt='MallA'/></span>
              <span class='box__delivery'>무료배송</span>
              <a class='link__full-cover' href='https://example.com/buy'></a>
            </li>
          </ul>
        </div>
      </div>
    </body></html>
    """ + ("x" * 6000)
    assert has_product_fingerprint(product_html) is True


def test_parse_product_lowest_price_basic():
    html = """
    <html><body>
      <div class='prod_tit'>Parsed Name</div>
      <div id='lowPriceCompanyArea'>
        <div class='box__mall-price'>
          <ul class='list__mall-price'>
            <li class='list-item'>
              <span class='sell-price'><span class='text__num'>12,345</span></span>
              <span class='box__logo'><img alt='MallA'/></span>
              <span class='box__delivery'>무료배송</span>
              <a class='link__full-cover' href='https://example.com/buy'></a>
            </li>
          </ul>
        </div>
      </div>
    </body></html>
    """ + ("x" * 6000)

    result = parse_product_lowest_price(html, fallback_name="Fallback", product_url="https://prod")
    assert result is not None
    assert result.product_name == "Parsed Name"
    assert result.lowest_price == 12345
    assert result.link == "https://example.com/buy"
