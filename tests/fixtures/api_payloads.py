"""API Payload 테스트 자산

규칙:
- FE 요청과 동일한 형태만 사용
- 다나와 URL 포함 금지 (요청에 포함하지 않음)

현재 백엔드 스키마 기준:
- product_name (필수)
- current_price (옵션)
"""

API_PAYLOADS = {
    "base_url": "http://localhost:8000",
    "search_success_candidate": {
        "product_name": "농심 신라면 120g",
        "current_price": 2986,
    },
    "search_success_electronics": {
        "product_name": "삼성전자 갤럭시 버즈3 프로",
        "current_price": 207900,
    },
    "search_no_result": {
        "product_name": "절대로존재하지않는가짜상품명_zzzz",
        "current_price": 12345,
    },
    "search_timeout_candidate": {
        "product_name": "Apple 2025 맥북 에어 13 M4",
        "current_price": 1430980,
    },
}
