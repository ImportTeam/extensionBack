# 🎓 검색 실패 학습 시스템 - 구현 완료

## 📋 개요

검색 실패 패턴을 **NeonDB에 자동으로 저장**하고, **분석 대시보드를 통해 시각화**하며, **데이터 기반으로 지속적 개선**하는 시스템을 완성했습니다.

```
사용자 요청 → 검색 실패 → 자동 저장 → 분석 → 개선 제안 → 수동/자동 학습
```

---

## ✅ 구현된 기능

### 1️⃣ 자동 실패 기록

검색이 실패할 때마다 **자동으로 NeonDB에 저장**:

```python
# price_search_service.py에서 자동 호출
self._record_search_failure(
    product_name=product_name,
    normalized_name=normalized_name,
    error_message=str(e)
)
```

**저장되는 정보**:
- 원본 상품명: `"Apple 2024 에어팟 4 액티브 노이즈 캔슬링..."`
- 정규화된 상품명: `"에어팟 4 이어폰"`
- 시도한 후보들: `["에어팟 4 이어폰", "Apple 에어팟 4", ...]`
- 카테고리: `"earphone"`
- 브랜드/모델: `"Apple"`, `"에어팟 4"`
- 에러 메시지: `"No products found"`
- 타임스탬프: `2024-12-14 10:30:00`

### 2️⃣ 분석 대시보드

`/api/analytics/dashboard`로 실시간 통계 조회:

```json
{
  "stats": {
    "total": 150,           // 전체 실패
    "pending": 45,          // 미해결
    "resolved": 105,        // 해결됨
    "by_category": [        // 카테고리별
      {"category": "earphone", "count": 20},
      {"category": "laptop", "count": 15}
    ]
  },
  "resolution_rate": 70.0,  // 해결율
  "pending_rate": 30.0      // 미해결율
}
```

### 3️⃣ 반복 패턴 감지

동일한 검색어가 반복적으로 실패하면 자동 감지:

```
Apple 2024 에어팟 4 액티브... → 3회 반복 → HIGH 우선순위
```

### 4️⃣ 개선 제안 자동 생성

**우선순위별로 정렬된 제안**:

```json
{
  "type": "pattern",
  "pattern": "Apple 2024 에어팟 4 액티브...",
  "occurrences": 5,
  "priority": "HIGH",
  "suggestion": "Consider adding special handling for this pattern"
}
```

### 5️⃣ 학습 데이터 내보내기

JSON/CSV 형식으로 내보내서 **ML 모델 학습에 사용 가능**:

```bash
curl http://localhost:8000/api/analytics/export?format=json
```

### 6️⃣ 피드백 루프

사용자가 올바른 상품명을 입력하면 저장:

```bash
POST /api/analytics/resolve/123
{
  "status": "manual_fixed",
  "correct_product_name": "Apple AirPods 4",
  "correct_pcode": "12345"
}
```

---

## 📊 데이터 구조

### search_failures 테이블

```sql
CREATE TABLE search_failures (
    id INT PRIMARY KEY AUTO_INCREMENT,
    original_query VARCHAR(255) NOT NULL,        -- 원본 쿼리
    normalized_query VARCHAR(255) NOT NULL,      -- 정규화된 쿼리
    candidates TEXT NOT NULL,                    -- 시도한 후보들 (JSON)
    attempted_count INT,                         -- 시도 횟수
    error_message VARCHAR(512),                  -- 에러 메시지
    category_detected VARCHAR(50),               -- 감지된 카테고리
    brand VARCHAR(100),                          -- 추출된 브랜드
    model VARCHAR(100),                          -- 추출된 모델명
    is_resolved VARCHAR(50) DEFAULT 'pending',   -- pending/manual_fixed/auto_learned
    correct_product_name VARCHAR(255),           -- 올바른 상품명
    correct_pcode VARCHAR(20),                   -- 올바른 pcode
    created_at TIMESTAMP,                        -- 생성 시간
    updated_at TIMESTAMP,                        -- 수정 시간
    
    INDEX ix_original_query (original_query),
    INDEX ix_created_at (created_at),
    INDEX ix_is_resolved (is_resolved)
);
```

---

## 🔌 API 엔드포인트

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| **GET** | `/api/analytics/dashboard` | 분석 대시보드 |
| **GET** | `/api/analytics/common-failures` | 반복되는 실패 패턴 |
| **GET** | `/api/analytics/category-analysis` | 카테고리별 분석 |
| **GET** | `/api/analytics/improvements` | 개선 제안 |
| **GET** | `/api/analytics/export?format=json\|csv` | 학습 데이터 내보내기 |
| **POST** | `/api/analytics/resolve/{id}` | 실패 기록 해결 표시 |

---

## 🧪 테스트 현황

**8개 테스트 모두 통과** ✅

```bash
✓ test_record_failure                 # 실패 기록 저장
✓ test_mark_resolved                  # 해결 표시
✓ test_get_by_original_query          # 쿼리로 조회
✓ test_get_analytics_dashboard        # 대시보드
✓ test_get_common_failures            # 반복 패턴
✓ test_export_learning_data_json      # JSON 내보내기
✓ test_export_learning_data_csv       # CSV 내보내기
✓ test_get_improvement_suggestions    # 개선 제안
```

---

## 📁 생성된 파일

### 핵심 구현

```
src/
├── repositories/
│   ├── models/
│   │   ├── __init__.py                          [NEW]
│   │   └── search_failure.py                    [NEW] 170줄
│   └── search_failure_repository.py             [NEW] 120줄
├── services/
│   ├── price_search_service.py                  [MODIFIED] 실패 로깅 통합
│   └── search_failure_analyzer.py               [NEW] 150줄
└── routes/
    └── analytics_router.py                      [NEW] 180줄
```

### 통합 및 설정

```
src/
├── app.py                                       [MODIFIED] 라우터 등록
└── core/
    └── database.py                              (기존)

tests/
├── unit/
│   └── test_search_failure.py                   [NEW] 180줄 (8 테스트)
└── conftest.py                                  [MODIFIED] db fixture 추가
```

### 문서

```
LEARNING_SYSTEM.md                              [NEW] 상세 문서
LEARNING_QUICKSTART.md                          [NEW] 빠른 시작
demo_learning_system.py                         [NEW] 데모 스크립트
```

---

## 🚀 사용 방법

### 1단계: 테이블 생성

```bash
python -c "
from src.core.database import Base, engine
from src.repositories.models.search_failure import SearchFailure
Base.metadata.create_all(bind=engine)
"
```

### 2단계: 서버 시작

```bash
python main.py
```

### 3단계: API 호출

#### 대시보드 조회
```bash
curl http://localhost:8000/api/analytics/dashboard
```

#### 반복 실패 패턴 확인
```bash
curl http://localhost:8000/api/analytics/common-failures?limit=20
```

#### 개선 제안 확인
```bash
curl http://localhost:8000/api/analytics/improvements
```

#### 학습 데이터 내보내기
```bash
curl http://localhost:8000/api/analytics/export?format=json > learning_data.json
```

#### 실패 기록 해결
```bash
curl -X POST http://localhost:8000/api/analytics/resolve/123 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "manual_fixed",
    "correct_product_name": "Apple AirPods 4",
    "correct_pcode": "12345"
  }'
```

---

## 📈 향후 개선 로드맵

### Phase 2: 자동 규칙 생성
```python
# 실패 패턴 → 정규화 규칙 자동 생성
def auto_generate_rules(failures: List[SearchFailure]):
    pass
```

### Phase 3: ML 기반 최적화
```python
# 학습된 모델로 검색어 자동 최적화
def ml_optimize_query(original: str) -> str:
    pass
```

### Phase 4: 자동 학습 루프
```python
# 사용자 피드백 → 규칙 자동 업데이트
def auto_learn_from_feedback():
    pass
```

---

## 🎯 핵심 이점

| 측면 | 이전 | 이후 |
|------|------|------|
| **데이터 추적** | ❌ 수동 기록 불가 | ✅ 자동 저장 |
| **분석** | ❌ 불가능 | ✅ 실시간 대시보드 |
| **패턴 발견** | ❌ 추측에 의존 | ✅ 데이터 기반 감지 |
| **개선** | ❌ 무작위 규칙 추가 | ✅ 우선순위 기반 개선 |
| **확장성** | ❌ 규칙 폭발 | ✅ 무제한 확장 가능 |
| **학습** | ❌ 불가능 | ✅ ML 학습 데이터 제공 |

---

## 📞 지원

더 자세한 정보는:
- [LEARNING_SYSTEM.md](LEARNING_SYSTEM.md) - 상세 설명서
- [LEARNING_QUICKSTART.md](LEARNING_QUICKSTART.md) - 빠른 시작
- [demo_learning_system.py](demo_learning_system.py) - 실행 가능한 데모

---

## ✨ 요약

✅ **완전 자동화**: 검색 실패가 즉시 NeonDB에 저장
✅ **실시간 분석**: 대시보드로 패턴 시각화
✅ **스마트 제안**: 우선순위별 개선 제안
✅ **학습 데이터**: ML 학습에 바로 사용 가능
✅ **피드백 루프**: 사용자 수정 정보 저장
✅ **확장성**: 무한 확장 가능한 설계

**이제 검색 실패는 더 이상 문제가 아닙니다. 데이터입니다! 📊**
