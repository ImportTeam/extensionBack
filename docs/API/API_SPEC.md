# API Spec

Base Path: `/api/v1`

## Endpoints

### POST /api/v1/price/search — 최저가 검색

#### 주요 시나리오
**FE가 쿠팡/지마켓/11번가 등에서 상품 정보를 가져와서 다나와 최저가와 비교하는 경우**

FE는 다나와 URL을 알지 못합니다. FE가 보내는 정보:
- `product_name`: 외부 쇼핑몰에서 가져온 상품명
- `current_url`: 외부 쇼핑몰의 상품 URL (다나와 URL 아님!)
- `current_price`: 외부 쇼핑몰에서 표시되는 현재 가격

백엔드가 하는 일:
1. 상품명을 정규화해서 다나와에서 검색
2. 동일 제품을 찾아서 크롤링
3. 최저가 / 최저가 구매 링크 / 무료배송 정보 반환

#### Request Body (JSON)
```json
{
  "product_name": "Apple 맥북프로 14 M4 Pro 12코어",  // required
  "current_price": 2890000,                          // optional - 가격 비교에 필요
  "current_url": "https://www.coupang.com/vp/...",   // optional - 외부 쇼핑몰 URL (참고용)
  "product_code": null                               // optional - FE는 보통 모름
}
```

#### Example Request (쿠팡에서 본 맥북프로)
```
POST /api/v1/price/search
Content-Type: application/json

{
  "product_name": "Apple 맥북프로 14 M4 Pro 12코어",
  "current_price": 2890000,
  "current_url": "https://www.coupang.com/vp/products/9128826497"
}
```

#### Success Response (200)
```json
{
  "status": "success",
  "data": {
    "is_cheaper": true,
    "price_diff": 178160,
    "lowest_price": 2711840,
    "link": "https://prod.danawa.com/bridge/loadingBridge.html?...",
    "mall": "G마켓",
    "free_shipping": true,
    "top_prices": [
      {"rank": 1, "mall": "G마켓", "price": 2711840, "free_shipping": true, "delivery": "무료배송", "link": "https://..."},
      {"rank": 2, "mall": "옥션", "price": 2711840, "free_shipping": true, "delivery": "무료배송", "link": "https://..."},
      {"rank": 3, "mall": "11번가", "price": 2711850, "free_shipping": true, "delivery": "빠른배송\n무료배송", "link": "https://..."}
    ],
    "price_trend": []
  },
  "message": "검색 성공"
}
```

#### Response Fields
| Field | Type | Description |
|-------|------|-------------|
| `is_cheaper` | boolean | 다나와 최저가가 current_price보다 저렴한지 |
| `price_diff` | int | 가격 차이 (current_price - lowest_price) |
| `lowest_price` | int | 다나와 최저가 |
| `link` | string | 최저가 쇼핑몰 구매 링크 (bridge URL) |
| `mall` | string | 최저가 쇼핑몰명 |
| `free_shipping` | boolean | 무료배송 여부 |
| `top_prices` | array | 최저가 TOP3 쇼핑몰 정보 |
| `price_trend` | array | 가격 추이 (현재 미지원, 빈 배열 반환) |

#### Error Responses
| Code | Description |
|------|-------------|
| 400 | 입력값 누락 또는 형식 오류 |
| 404 | 상품을 찾을 수 없음 |
| 500 | 크롤러/외부 의존성 실패 |

---

## 입력 품질 가이드라인

### current_price가 중요한 이유
- `current_price`를 보내야 `is_cheaper`/`price_diff`를 정확히 계산할 수 있습니다.
- `current_price`가 없으면 `is_cheaper=false`, `price_diff=0`으로 반환됩니다.

### 상품명 정규화
서버는 자동으로 상품명을 정규화하지만, 성공률을 높이려면:
- **권장**: "브랜드 + 모델명" 위주로 짧게 보내기
  - ✅ `"Apple 맥북프로 14 M4 Pro"`
  - ✅ `"삼성전자 갤럭시 버즈3 프로"`
  - ❌ `"베이직스 2024 베이직북 14 N-시리즈BasicWhite · 256GB · 8GB · WIN11 Home · BB1422SS-N"`

### 검색 실패 시
- 검색 결과가 없으면 60초간 네거티브 캐시가 설정됩니다.
- 같은 상품명으로 재검색해도 60초 동안은 즉시 실패 응답을 받습니다.

---

## Cache 동작

### 정상 캐시 (Positive Cache)
- TTL: 6시간 (21600초)
- 동일 상품명 검색 시 캐시에서 즉시 응답

### 네거티브 캐시 (Negative Cache)
- TTL: 60초
- 검색 실패 시 설정되어 무한 재시도 방지
- 60초 후 재검색 가능

---

## Client-side Recommendations
- Request timeout: 15초
- AbortController로 이전 요청 취소 (새 검색 시작 시)
- Transient error에 대한 retry/backoff 구현
