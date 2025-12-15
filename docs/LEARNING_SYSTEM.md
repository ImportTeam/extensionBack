# 🎓 검색 실패 학습 시스템

## 개요

사용자의 검색 요청이 실패한 경우, 해당 패턴을 자동으로 **NeonDB에 저장**하고 이를 분석하여 **지속적으로 정규화 규칙을 개선**하는 시스템입니다.

### 핵심 개념

```
사용자 검색 요청
    ↓
검색 실패 시 DB 저장
    ↓
주기적 분석 (대시보드)
    ↓
개선 제안 생성
    ↓
정규화 규칙 수동/자동 업데이트
```

## 시스템 구조

### 1. 데이터 모델

#### SearchFailure 테이블

```python
search_failures
├── id: int (PK)
├── original_query: str          # 사용자 입력 ("Apple 2024 에어팟 4...")
├── normalized_query: str        # 정규화된 쿼리 ("에어팟 4 이어폰")
├── candidates: JSON             # 시도한 검색 후보 ["후보1", "후보2", ...]
├── attempted_count: int         # 시도 횟수
├── error_message: str           # 에러 메시지
├── category_detected: str       # 감지된 카테고리 ("earphone", "laptop" 등)
├── brand: str                   # 추출된 브랜드 ("Apple")
├── model: str                   # 추출된 모델명 ("에어팟 4")
├── is_resolved: str             # "pending" | "manual_fixed" | "auto_learned" | "not_product"
├── correct_product_name: str    # 사용자 수정 상품명
├── correct_pcode: str           # 올바른 pcode
├── created_at: datetime         # 생성 시간 (인덱스됨)
└── updated_at: datetime         # 수정 시간
```

### 2. Repository 계층

[src/repositories/search_failure_repository.py]

```python
SearchFailureRepository
├── record_failure()              # 실패 기록 저장
├── get_by_original_query()       # 원본 쿼리로 조회
├── get_recent_failures()         # 최근 실패 기록 조회
├── mark_resolved()               # 실패 해결 표시
├── get_failure_stats()           # 통계 조회
└── get_common_failures()         # 반복되는 실패 패턴
```

### 3. 분석 서비스

[src/services/search_failure_analyzer.py]

```python
SearchFailureAnalyzer
├── get_analytics_dashboard()     # 분석 대시보드
├── get_category_analysis()       # 카테고리별 분석
├── export_learning_data()        # 학습 데이터 내보내기 (JSON/CSV)
└── get_improvement_suggestions() # 개선 제안 생성
```

### 4. API 엔드포인트

[src/routes/analytics_router.py]

#### 분석 대시보드

```
GET /api/analytics/dashboard
```

응답:
```json
{
  "stats": {
    "total": 150,
    "pending": 45,
    "resolved": 105,
    "by_category": [
      {"category": "earphone", "count": 20},
      {"category": "laptop", "count": 15},
      {"category": "monitor", "count": 10}
    ]
  },
  "common_failures": [
    {
      "original_query": "Apple 2024 에어팟 4 액티브...",
      "normalized_query": "에어팟 4 이어폰",
      "category": "earphone",
      "failure_count": 5
    }
  ],
  "resolution_rate": 70.0,
  "pending_rate": 30.0
}
```

#### 가장 많은 실패 케이스

```
GET /api/analytics/common-failures?limit=20
```

#### 카테고리별 분석

```
GET /api/analytics/category-analysis
```

#### 개선 제안

```
GET /api/analytics/improvements
```

응답:
```json
{
  "suggestions": [
    {
      "type": "pattern",
      "pattern": "Apple 2024 에어팟 4 액티브...",
      "normalized": "에어팟 4 이어폰",
      "category": "earphone",
      "occurrences": 5,
      "suggestion": "Consider adding special handling for pattern...",
      "priority": "HIGH"
    }
  ],
  "total": 2
}
```

#### 학습 데이터 내보내기

```
GET /api/analytics/export?format=json  # 또는 csv
```

#### 실패 기록 해결

```
POST /api/analytics/resolve/123
{
  "status": "manual_fixed",
  "correct_product_name": "Apple AirPods 4",
  "correct_pcode": "12345"
}
```

## 통합 흐름

### 검색 실패 시 자동 기록

[src/services/price_search_service.py]

```python
async def search_price(self, product_name: str):
    try:
        # 검색 시도...
        result = await crawler.search_lowest_price(normalized_name)
    
    except ProductNotFoundException:
        # 실패 기록 저장
        self._record_search_failure(
            product_name=product_name,
            normalized_name=normalized_name,
            error_message=str(e)
        )
```

### 실패 기록 저장 프로세스

1. **기본 정보 수집**
   - 원본 상품명: `"Apple 2024 에어팟 4 액티브 노이즈 캔슬링..."`
   - 정규화된 상품명: `"에어팟 4 이어폰"`
   - 시도한 후보들: `["에어팟 4 이어폰", "Apple 2024 에어팟 4", ...]`

2. **메타 정보 추출**
   - 카테고리 감지: `"earphone"`
   - 브랜드 추출: `"Apple"`
   - 모델명 추출: `"에어팟 4"`

3. **DB 저장**
   ```python
   SearchFailureRepository.record_failure(
       db=session,
       original_query=product_name,
       normalized_query=normalized_name,
       candidates=candidates,
       category_detected=category,
       brand=brand,
       model=model,
       error_message=error_message
   )
   ```

## 사용 시나리오

### 시나리오 1: 검색 실패 분석

**UI**: 분석 대시보드

```bash
# 1. 현재 상태 조회
curl http://localhost:8000/api/analytics/dashboard

# 결과 분석:
# - 총 실패: 150건
# - 미해결: 45건
# - 해결율: 70%
# - 카테고리별 분포 확인
```

### 시나리오 2: 반복되는 실패 패턴 발견

```bash
# 1. 가장 많은 실패 케이스 확인
curl http://localhost:8000/api/analytics/common-failures?limit=20

# 결과: "Apple 2024 에어팟 4 액티브..." 패턴이 5회 반복

# 2. 개선 제안 확인
curl http://localhost:8000/api/analytics/improvements

# 제안: "earphone 카테고리에서 특별한 처리 고려"
```

### 시나리오 3: 수동 수정 및 학습

```bash
# 사용자가 올바른 상품명 입력
curl -X POST http://localhost:8000/api/analytics/resolve/123 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "manual_fixed",
    "correct_product_name": "Apple AirPods 4",
    "correct_pcode": "12345"
  }'

# 이 정보는 나중에 ML 모델 학습에 사용됨
```

### 시나리오 4: 학습 데이터 내보내기

```bash
# JSON 형식으로 학습 데이터 내보내기
curl http://localhost:8000/api/analytics/export?format=json > failures.json

# 결과:
# [
#   {
#     "id": 1,
#     "original": "Apple 2024 에어팟 4 액티브...",
#     "normalized": "에어팟 4 이어폰",
#     "category": "earphone",
#     "brand": "Apple",
#     "model": "에어팟 4",
#     "status": "pending",
#     "created": "2024-12-14T10:30:00"
#   }
# ]
```

## 데이터베이스 마이그레이션

### 테이블 생성

```python
from src.core.database import Base, engine
from src.repositories.models.search_failure import SearchFailure

Base.metadata.create_all(bind=engine)
```

또는 Alembic:

```bash
alembic upgrade head
```

## 테스트

### 단위 테스트 실행

```bash
pytest tests/unit/test_search_failure.py -v
```

**테스트 케이스**:
- ✅ `test_record_failure`: 실패 기록 저장
- ✅ `test_mark_resolved`: 실패 해결 표시
- ✅ `test_get_by_original_query`: 쿼리로 조회
- ✅ `test_get_analytics_dashboard`: 대시보드
- ✅ `test_get_common_failures`: 반복 패턴
- ✅ `test_export_learning_data_json`: JSON 내보내기
- ✅ `test_export_learning_data_csv`: CSV 내보내기
- ✅ `test_get_improvement_suggestions`: 개선 제안

## 향후 개선 방향

### Phase 2: 자동 학습

```python
# 실패 패턴 분석을 통해 정규화 규칙 자동 생성
def auto_learn_normalization_rules(failures: List[SearchFailure]):
    """
    실패 패턴 분석 → 정규화 규칙 자동 생성
    """
    pass
```

### Phase 3: ML 기반 개선

```python
# 머신러닝 모델을 통한 검색어 최적화
def ml_optimize_search_query(original_query: str) -> str:
    """
    학습된 모델을 이용해 최적 검색어 자동 생성
    """
    pass
```

### Phase 4: 피드백 루프

```python
# 사용자 피드백 → 자동 규칙 업데이트
def apply_user_feedback_loop():
    """
    1. 사용자가 올바른 상품명 입력
    2. 유사한 패턴 자동 감지
    3. 정규화 규칙 업데이트
    """
    pass
```

## 성능 고려사항

### 인덱스

- `is_resolved`: 미해결 기록 빠른 조회
- `created_at`: 기간별 조회
- `original_query`: 중복 검사

### 데이터 정리

```python
# 월 1회: 해결된 이전 데이터 보관
SELECT * FROM search_failures 
WHERE is_resolved != 'pending' 
  AND created_at < NOW() - INTERVAL 30 DAY
ORDER BY created_at DESC;
```

## 모니터링

### 주요 메트릭

1. **실패율**: `pending / total * 100`
2. **해결율**: `resolved / total * 100`
3. **카테고리별 문제점**: 특정 카테고리의 높은 실패율
4. **패턴 반복**: 3회 이상 반복되는 패턴

### 알림 설정 (향후)

```python
if failure_rate > 10:  # 실패율 10% 이상
    send_alert("검색 실패율 높음: {:.1f}%".format(failure_rate))
```

## 결론

이 시스템을 통해:

✅ **데이터 기반 개선**: 추측이 아닌 실제 데이터로 규칙 개선
✅ **자동화**: 수동 규칙 추가의 반복 작업 최소화
✅ **확장성**: 새로운 상품 유형 추가 시 자동으로 학습
✅ **추적성**: 모든 실패 패턴을 기록하고 분석 가능
