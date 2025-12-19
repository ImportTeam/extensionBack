# API 레퍼런스

**버전**: 1.0.0
**베이스 URL**: `/api/v1`
**응답 형식**: JSON
**인증**: 불필요 (공개 API)

---

## 목차
1. [개요](#개요)
2. [가격 검색 API](#가격-검색-api)
3. [상태 확인 API](#상태-확인-api)
4. [분석 API](#분석-api)
5. [에러 코드](#에러-코드)

---

## 개요

importBack API는 상품의 최저가를 탐지하는 REST API입니다.

### 기본 사항

- **프로토콜**: HTTP/1.1, HTTP/2
- **응답 형식**: JSON (UTF-8)
- **타임아웃**: 12초
- **속도 제한**: 제한 없음 (현재)
- **CORS**: 모든 원본 허용

### 응답 구조

모든 API 응답은 다음 구조를 따릅니다:

```json
{
  "status": "success|error|warning",
  "data": { /* 응답 데이터 */ },
  "message": "사람이 읽을 수 있는 메시지",
  "error_code": "선택적 에러 코드"
}
```

### HTTP 상태 코드

| 코드 | 의미 | 예 |
|-----|------|-----|
| 200 | OK | 성공적인 응답 |
| 400 | Bad Request | 유효하지 않은 입력 |
| 500 | Internal Server Error | 서버 오류 |
| 503 | Service Unavailable | 모든 검색 경로 실패 |

---

## 가격 검색 API

### POST /price/search

상품의 최저가를 검색합니다.

**요청**:

```http
POST /api/v1/price/search HTTP/1.1
Host: api.importback.com
Content-Type: application/json

{
  "product_name": "Apple 2025 아이패드 프로 11",
  "current_price": 1517000,
  "current_url": "https://example.com/product/ipad"
}
```

**요청 필드**:

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `product_name` | string | ✓ | - | 검색할 상품명 (1-500자) |
| `current_price` | integer | ✗ | null | 현재 가격 (0-1,000,000,000원) |
| `current_url` | string | ✗ | null | 상품 링크 (유효한 URL) |

**요청 검증**:

```json
{
  "product_name": {
    "min_length": 1,
    "max_length": 500,
    "required": true,
    "forbidden_chars": ["<", ">", "script", "javascript"]
  },
  "current_price": {
    "type": "integer",
    "min": 0,
    "max": 1000000000,
    "required": false
  },
  "current_url": {
    "protocol": ["http", "https"],
    "required": false
  }
}
```

**응답 (성공)**:

```json
{
  "status": "success",
  "data": {
    "product_name": "Apple 2025 아이패드 프로 11",
    "lowest_price": 1299000,
    "current_price": 1517000,
    "price_diff": 218000,
    "is_cheaper": true,
    "link": "https://prod.danawa.com/info/?pcode=9876543",
    "source": "fastpath",
    "elapsed_ms": 234.5
  },
  "message": "다나와에서 218,000원 저렴한 가격 발견!"
}
```

**응답 필드 설명**:

| 필드 | 타입 | 설명 |
|------|------|------|
| `product_name` | string | 정규화된 상품명 |
| `lowest_price` | integer | 발견된 최저가 (원) |
| `current_price` | integer \| null | 입력한 현재 가격 (요청에 없으면 null) |
| `price_diff` | integer | 절약 금액 (낮은 가격 - 현재 가격) |
| `is_cheaper` | boolean | 다나와 가격이 더 낮은지 여부 |
| `link` | string | 다나와 상품 링크 |
| `source` | string | 검색 출처 (`cache`, `fastpath`, `slowpath`) |
| `elapsed_ms` | float | 검색 소요 시간 (밀리초) |

**응답 (상품 미발견)**:

```json
{
  "status": "error",
  "data": null,
  "message": "입력하신 상품을 찾을 수 없습니다.",
  "error_code": "PRODUCT_NOT_FOUND"
}
```

**응답 (타임아웃)**:

```json
{
  "status": "error",
  "data": null,
  "message": "검색 시간이 초과되었습니다.",
  "error_code": "TIMEOUT"
}
```

**응답 (봇 차단)**:

```json
{
  "status": "error",
  "data": null,
  "message": "현재 서비스를 이용할 수 없습니다.",
  "error_code": "BLOCKED"
}
```

**응답 (서비스 불가)**:

```json
{
  "status": "error",
  "data": null,
  "message": "문제가 계속되면 관리자에게 문의해주세요.",
  "error_code": "SERVICE_UNAVAILABLE"
}
```

### 사용 예

#### cURL

```bash
curl -X POST "http://localhost:8000/api/v1/price/search" \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "아이패드 프로 11",
    "current_price": 1517000
  }'
```

#### Python (requests)

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/price/search",
    json={
        "product_name": "아이패드 프로 11",
        "current_price": 1517000,
    },
)

if response.status_code == 200:
    data = response.json()["data"]
    print(f"최저가: {data['lowest_price']:,}원")
    print(f"절약금: {data['price_diff']:,}원")
else:
    error = response.json()
    print(f"에러: {error['message']}")
```

#### JavaScript (fetch)

```javascript
const response = await fetch("http://localhost:8000/api/v1/price/search", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    product_name: "아이패드 프로 11",
    current_price: 1517000,
  }),
});

const result = await response.json();

if (result.status === "success") {
  const { lowest_price, price_diff, is_cheaper } = result.data;
  console.log(`최저가: ${lowest_price.toLocaleString()}원`);
  console.log(`절약금: ${price_diff.toLocaleString()}원`);
} else {
  console.error(result.message);
}
```

---

## 상태 확인 API

### GET /health

서비스의 상태를 확인합니다.

**요청**:

```http
GET /api/v1/health HTTP/1.1
Host: api.importback.com
```

**응답 (정상)**:

```json
{
  "status": "healthy",
  "timestamp": "2025-12-19T10:30:00Z",
  "version": "1.0.0",
  "dependencies": {
    "redis": "connected",
    "database": "connected",
    "playwright": "ready"
  }
}
```

**응답 (문제)**:

```json
{
  "status": "degraded",
  "timestamp": "2025-12-19T10:31:00Z",
  "version": "1.0.0",
  "dependencies": {
    "redis": "disconnected",
    "database": "connected",
    "playwright": "ready"
  },
  "message": "Redis 연결이 끊어졌습니다. 캐시 기능이 제한됩니다."
}
```

### GET /health/dependencies

세부 의존성 상태를 확인합니다.

**응답**:

```json
{
  "redis": {
    "status": "connected",
    "latency_ms": 2.3,
    "memory_used": "125.5 MB",
    "keys_count": 5432
  },
  "database": {
    "status": "connected",
    "latency_ms": 5.1,
    "pool_size": 10,
    "active_connections": 3
  },
  "playwright": {
    "status": "ready",
    "browser_version": "131.0.0",
    "instances_running": 0,
    "memory_usage": "45.2 MB"
  }
}
```

---

## 분석 API

### GET /analytics/stats

검색 통계를 조회합니다. (선택 사항)

**요청**:

```http
GET /api/v1/analytics/stats?period=24h HTTP/1.1
Host: api.importback.com
```

**쿼리 파라미터**:

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `period` | string | `24h` | 통계 기간 (`1h`, `24h`, `7d`, `30d`) |

**응답**:

```json
{
  "status": "success",
  "data": {
    "period": "24h",
    "total_searches": 5234,
    "successful_searches": 4890,
    "failed_searches": 344,
    "success_rate": 93.4,
    "average_response_time_ms": 1245.5,
    "cache_hit_rate": 72.1,
    "source_distribution": {
      "cache": 72.1,
      "fastpath": 23.5,
      "slowpath": 4.4
    },
    "average_savings": 85420,
    "products_searched": 2150,
    "unique_users": 890
  }
}
```

---

## 에러 코드

### 검증 에러 (400)

| 에러 코드 | 메시지 | 원인 |
|----------|--------|------|
| `INVALID_PRODUCT_NAME` | "상품명은 1자 이상 500자 이하여야 합니다." | 상품명 길이 부적절 |
| `INVALID_PRICE` | "가격은 0원 이상 1,000,000,000원 이하여야 합니다." | 가격 범위 초과 |
| `INVALID_URL` | "유효한 URL을 입력해주세요." | URL 형식 오류 |
| `FORBIDDEN_CHARACTERS` | "상품명에 포함할 수 없는 문자가 있습니다." | 위험한 문자 포함 |

### 크롤러 에러 (503)

| 에러 코드 | 메시지 | 원인 | 복구 방법 |
|----------|--------|------|---------|
| `PRODUCT_NOT_FOUND` | "입력하신 상품을 찾을 수 없습니다." | 상품 미발견 | 상품명 다시 확인 |
| `NETWORK_TIMEOUT` | "검색 시간이 초과되었습니다." | 네트워크 느림 | 잠시 후 재시도 |
| `BLOCKED` | "현재 서비스를 이용할 수 없습니다." | 봇 차단 | 1시간 후 재시도 |
| `BROWSER_ERROR` | "현재 서비스를 이용할 수 없습니다." | 브라우저 오류 | 관리자에 문의 |
| `SERVICE_UNAVAILABLE` | "모든 검색이 실패했습니다." | 모든 경로 실패 | 잠시 후 재시도 |

### 시스템 에러 (500)

| 에러 코드 | 메시지 | 원인 |
|----------|--------|------|
| `DATABASE_ERROR` | "데이터베이스 오류가 발생했습니다." | DB 연결 실패 |
| `CACHE_ERROR` | "캐시 오류가 발생했습니다." | Redis 연결 실패 |
| `INTERNAL_ERROR` | "내부 오류가 발생했습니다." | 예상 치 못한 오류 |

---

## 성능 최적화 팁

### 1. 캐시 활용
- 같은 상품을 여러 번 검색하면 캐시에서 즉시 반환 (50-100ms)
- 응답의 `source` 필드로 캐시 여부 확인 가능

### 2. 배치 검색
```javascript
// ❌ 느림: 순차 요청
for (let product of products) {
  const result = await search(product);
}

// ✓ 빠름: 병렬 요청
const results = await Promise.all(
  products.map(p => search(p))
);
```

### 3. 에러 처리
```javascript
try {
  const result = await search(product);
  // 성공 처리
} catch (error) {
  if (error.error_code === "PRODUCT_NOT_FOUND") {
    // 상품 없음 - UI 표시
  } else if (error.error_code === "BLOCKED") {
    // 봇 차단 - 잠시 후 재시도
    setTimeout(() => retry(), 60000);
  } else {
    // 일반 오류 - 재시도
  }
}
```

---

**마지막 업데이트**: 2025-12-19
**API 버전**: 1.0.0
**상태**: Production Ready ✓
