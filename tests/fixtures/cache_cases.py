"""캐시 케이스 자산

오케스트레이터는 cache.get()에서 dict를 기대하며,
키는 url/product_url 둘 다 허용합니다.
"""

CACHE_CASES = {
    "valid_product_url": {
        "product_url": "https://prod.danawa.com/bridge/loadingBridge.html?pcode=123",
        "price": 2986,
    },
    "valid_url_alias": {
        "url": "https://prod.danawa.com/bridge/loadingBridge.html?pcode=123",
        "price": 2986,
    },
    "missing_url": {
        "price": 2986,
    },
    "missing_price": {
        "product_url": "https://prod.danawa.com/bridge/loadingBridge.html?pcode=123",
    },
    "invalid_price": {
        "product_url": "https://prod.danawa.com/bridge/loadingBridge.html?pcode=123",
        "price": -1,
    },
}
