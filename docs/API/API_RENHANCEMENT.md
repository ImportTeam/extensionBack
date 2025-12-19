# API Response Enhancement: TOP 3 Prices + Product ID

**Date**: 2025-12-19  
**Status**: ✅ **IMPLEMENTED**

---

## 🎯 Enhancement Summary

API 응답에 **TOP 3 가격 리스트**와 **product_id (pcode)** 추가로 캐싱 및 추적 개선.

### Before
```json
{
  "status": "success",
  "data": {
    "lowest_price": 27620,
    "link": "https://...",
    "top_prices": null  // ❌ 없음
  }
}
```

### After
```json
{
  "status": "success",
  "data": {
    "product_id": "637342",  // ✅ pcode for tracking
    "lowest_price": 27620,
    "link": "https://...",
    "top_prices": [  // ✅ TOP 3 with full details
      {
        "rank": 1,
        "mall": "11번가",
        "price": 27620,
        "free_shipping": false,
        "delivery": "빠른배송...",
        "link": "https://prod.danawa.com/bridge/..."
      },
      {
        "rank": 2,
        "mall": "옥션",
        "price": 27630,
        "link": "https://..."
      },
      {
        "rank": 3,
        "mall": "...",
        "price": 27900,
        "link": "https://..."
      }
    ]
  }
}
```

---

## 🔧 Implementation Details

### 1. Schema Changes

#### `src/engine/result.py` - SearchResult
```python
@dataclass
class SearchResult:
    # Added fields
    product_id: Optional[str] = None  # danawa pcode
    top_prices: Optional[list[dict]] = None  # TOP 3 list
```

#### `src/schemas/price_schema.py` - PriceData
```python
class PriceData(BaseModel):
    product_id: str | None  # NEW: pcode for tracking/caching
    top_prices: list[MallPrice] | None  # Already existed, now populated
```

---

### 2. Data Flow

```
Crawler (FastPath/SlowPath)
  ↓ (returns dict with pcode + top_prices)
Executor (fastpath_executor.py)
  ↓ (wraps in CrawlResult.metadata)
Orchestrator (orchestrator.py)
  ↓ (extracts metadata → SearchResult)
API Route (price_routes.py)
  ↓ (converts to PriceData with MallPrice[])
Response
```

---

### 3. File Changes

#### ✅ `src/engine/result.py`
- Added `product_id` and `top_prices` fields
- Updated factory methods: `from_cache()`, `from_fastpath()`, `from_slowpath()`

#### ✅ `src/schemas/price_schema.py`
- Added `product_id` field to `PriceData`

#### ✅ `src/crawlers/fastpath_executor.py`
- Extract `pcode` and `top_prices` from result
- Pack into `CrawlResult.metadata`

#### ✅ `src/crawlers/boundary/http_fastpath.py`
- Include `pcode` in result dict
- Add `price` and `product_url` aliases for orchestrator

#### ✅ `src/engine/orchestrator.py`
- Extract `metadata.product_id` and `metadata.top_prices`
- Pass to `SearchResult.from_fastpath()` / `from_slowpath()`

#### ✅ `src/api/routes/price_routes.py`
- Extract `result.product_id` and `result.top_prices`
- Convert to `MallPrice` schema (TOP 3 only)
- Return in `PriceData`

---

## 📊 Benefits

### 1. Product ID (pcode)
- **Tracking**: 동일 상품을 DB에서 추적 가능
- **Caching**: pcode 기반 캐시 키 생성 가능
- **Analytics**: 인기 상품 분석

### 2. TOP 3 Prices
- **Price Comparison**: 여러 쇼핑몰 가격 비교
- **User Choice**: 사용자가 선택할 수 있는 옵션 제공
- **Transparency**: 최저가 외 대안 표시

### 3. Full URL per Mall
- **Direct Purchase**: 각 쇼핑몰로 바로 이동 가능
- **Affiliate Links**: 쇼핑몰별 어필리에이트 적용 가능
- **Better UX**: 사용자 편의성 향상

---

## 🧪 Test Result

```bash
curl -X POST http://localhost:8000/api/v1/price/search \
  -d '{"product_name": "농심 신라면 120g", "current_price": 2986}'
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "product_id": "637342",
    "lowest_price": 27620,
    "top_prices": [
      {
        "rank": 1,
        "mall": "11번가",
        "price": 27620,
        "link": "https://prod.danawa.com/bridge/..."
      },
      {
        "rank": 2,
        "mall": "옥션",
        "price": 27630,
        "link": "https://prod.danawa.com/bridge/..."
      },
      {
        "rank": 3,
        "price": 27900,
        "link": "https://prod.danawa.com/bridge/..."
      }
    ]
  }
}
```

---

## 📝 API Documentation Update

### Response Schema

```typescript
interface PriceData {
  product_name: string;
  product_id: string | null;  // ✨ NEW: danawa pcode
  is_cheaper: boolean;
  price_diff: number;
  lowest_price: number;
  link: string;
  mall: string | null;
  free_shipping: boolean | null;
  top_prices: MallPrice[] | null;  // ✨ NOW POPULATED (TOP 3)
  price_trend: PriceTrendPoint[] | null;
  source: string;
  elapsed_ms: number;
}

interface MallPrice {
  rank: number;
  mall: string;
  price: number;
  free_shipping: boolean;
  delivery: string;
  link: string;  // Full purchase URL
}
```

---

## 🔮 Future Enhancements

### 1. Database Schema
```sql
CREATE TABLE products (
  id SERIAL PRIMARY KEY,
  pcode VARCHAR(50) UNIQUE NOT NULL,  -- danawa product code
  name VARCHAR(500),
  category VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE price_history (
  id SERIAL PRIMARY KEY,
  pcode VARCHAR(50) REFERENCES products(pcode),
  price INT NOT NULL,
  mall VARCHAR(100),
  recorded_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Enhanced Caching
```python
# Cache by pcode (more accurate)
cache_key = f"price:pcode:{pcode}"

# Store with product_id and top_prices
cache_value = {
    "product_id": pcode,
    "lowest_price": 27620,
    "top_prices": [...],
    "updated_at": "2025-12-19T..."
}
```

### 3. Analytics
- Track most searched pcode
- Price trend by pcode
- Popular malls by product category

---

**결론**: ✅ **TOP 3 prices + product_id 완벽 구현 완료**
