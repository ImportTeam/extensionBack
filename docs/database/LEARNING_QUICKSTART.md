# 검색 실패 학습 시스템 빠른 시작

## 설정

### 1. 데이터베이스 마이그레이션

```bash
python -c "
from src.core.database import Base, engine
from src.repositories.models.search_failure import SearchFailure

Base.metadata.create_all(bind=engine)
print('✅ search_failures 테이블이 생성되었습니다.')
"
```

### 2. 환경 변수 확인

`.env` 파일에 `DATABASE_URL`이 설정되어 있는지 확인:

```dotenv
DATABASE_URL=postgresql://user:password@host/db
```

## 사용법

### API 사용

#### 1. 분석 대시보드 조회

```bash
curl http://localhost:8000/api/analytics/dashboard
```

결과:
```json
{
  "stats": {
    "total": 150,
    "pending": 45,
    "resolved": 105,
    "by_category": [...]
  },
  "resolution_rate": 70.0,
  "pending_rate": 30.0
}
```

#### 2. 반복되는 실패 패턴 조회

```bash
curl http://localhost:8000/api/analytics/common-failures?limit=20
```

#### 3. 개선 제안 확인

```bash
curl http://localhost:8000/api/analytics/improvements
```

#### 4. 학습 데이터 내보내기

```bash
# JSON 형식
curl http://localhost:8000/api/analytics/export?format=json > failures.json

# CSV 형식
curl http://localhost:8000/api/analytics/export?format=csv > failures.csv
```

#### 5. 실패 기록 해결 표시

```bash
curl -X POST http://localhost:8000/api/analytics/resolve/123 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "manual_fixed",
    "correct_product_name": "Apple AirPods 4",
    "correct_pcode": "12345"
  }'
```

## 테스트

```bash
# 모든 학습 시스템 테스트 실행
pytest tests/unit/test_search_failure.py -v

# 특정 테스트만 실행
pytest tests/unit/test_search_failure.py::TestSearchFailureAnalysis::test_get_analytics_dashboard -v
```

## 데이터 흐름

```
검색 요청 (product_name)
    ↓
정규화 → 크롤링 시도
    ↓
실패 → SearchFailureRepository.record_failure()
    ↓
NeonDB에 저장
    ├── 원본 쿼리
    ├── 정규화된 쿼리
    ├── 시도한 후보들
    ├── 카테고리
    ├── 브랜드/모델
    └── 에러 메시지
    ↓
분석 대시보드에서 조회
    ├── 총 실패율
    ├── 카테고리별 분석
    ├── 반복 패턴
    └── 개선 제안
```

## 파일 구조

```
src/
├── repositories/
│   ├── models/
│   │   └── search_failure.py          # SearchFailure 모델
│   └── search_failure_repository.py   # 데이터 접근 계층
├── services/
│   ├── price_search_service.py        # 검색 실패 로깅 통합
│   └── search_failure_analyzer.py     # 분석 서비스
└── routes/
    └── analytics_router.py             # API 엔드포인트

tests/
└── unit/
    └── test_search_failure.py         # 유닛 테스트 (8개)

LEARNING_SYSTEM.md                     # 상세 문서
```

## 주요 기능

✅ **자동 실패 기록**: 검색 실패 시 자동으로 DB 저장
✅ **분석 대시보드**: 실시간 실패율 및 패턴 분석
✅ **반복 패턴 감지**: 3회 이상 반복되는 패턴 자동 감지
✅ **개선 제안**: 우선순위와 함께 개선안 제시
✅ **데이터 내보내기**: JSON/CSV 형식으로 학습 데이터 내보내기
✅ **피드백 루프**: 사용자 수정 정보 저장 후 향후 학습에 활용

## 다음 단계

1. **분석 대시보드 확인**
   ```bash
   curl http://localhost:8000/api/analytics/dashboard
   ```

2. **실패 패턴 조회**
   ```bash
   curl http://localhost:8000/api/analytics/common-failures
   ```

3. **개선 제안 검토**
   ```bash
   curl http://localhost:8000/api/analytics/improvements
   ```

4. **수동 수정 (필요시)**
   ```bash
   curl -X POST http://localhost:8000/api/analytics/resolve/ID \
     -d '{"status": "manual_fixed", "correct_product_name": "..."}'
   ```

## 자세한 정보

[LEARNING_SYSTEM.md](LEARNING_SYSTEM.md) 참조
