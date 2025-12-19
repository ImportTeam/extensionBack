# importBack 기술 아키텍처 & 데이터 흐름 가이드

**프로젝트명**: importBack - 최저가 탐지 서비스
**작성일**: 2025-12-19
**상태**: 프로덕션 레벨 (MyPy strict 통과, 테스트 완료)

---

## 📋 목차
1. [시스템 아키텍처](#시스템-아키텍처)
2. [데이터 흐름](#데이터-흐름)
3. [핵심 컴포넌트](#핵심-컴포넌트)
4. [에러 처리 및 복구](#에러-처리-및-복구)
5. [성능 최적화](#성능-최적화)
6. [배포 및 운영](#배포-및-운영)

---

## 시스템 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (React)                     │
│                                                               │
│  상품명 + 현재가격                                            │
│  예: {"product_name": "아이패드 프로 11", "current_price": 1517000}
└────────────────┬────────────────────────────────────────────┘
                 │ HTTP POST /api/v1/price/search
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    HTTP API Layer (FastAPI)                  │
│                    src/api/routes/price_routes.py            │
│                                                               │
│  ✓ 입력 검증 (Pydantic)                                      │
│  ✓ 보안 검증 (SecurityValidator)                            │
│  ✓ 요청 정규화                                              │
└────────────────┬────────────────────────────────────────────┘
                 │ 검증된 요청
                 ▼
┌─────────────────────────────────────────────────────────────┐
│            Engine Layer (SearchOrchestrator)                 │
│            src/engine/orchestrator.py                        │
│                                                               │
│  12초 예산 관리:                                             │
│  ├─ Cache: 0.5초 (4%)                                       │
│  ├─ FastPath: 4초 (33%)                                    │
│  └─ SlowPath: 6.5초 (54%)                                  │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
    [Cache]          [FastPath OR SlowPath]
```

### 계층별 역할

| 계층 | 컴포넌트 | 역할 | 타임아웃 |
|------|---------|------|--------|
| **API** | FastAPI Routes | HTTP 요청 수신, 검증 | - |
| **Engine** | SearchOrchestrator | 검색 파이프라인 조율 | 12초 |
| **Cache** | CacheAdapter + Redis | 캐시된 결과 반환 | 0.5초 |
| **FastPath** | FastPathExecutor | HTTP 기반 검색 | 4초 |
| **SlowPath** | SlowPathExecutor | Playwright 검색 | 6.5초 |
| **Storage** | PostgreSQL | 검색 실패 로그 저장 | - |

---

## 데이터 흐름

### 정상 흐름 (성공 케이스)

```
사용자 입력
    │
    │ 상품명: "Apple 2025 아이패드 프로 11"
    │ 현재가: 1,517,000원
    │
    ▼
[1] 입력 검증 (Pydantic)
    ├─ product_name 길이: 1-500자 ✓
    ├─ current_price 범위: 0-10억원 ✓
    ├─ current_url 프로토콜: http/https ✓
    └─ 위험한 문자 필터링 ✓
    │
    ▼
[2] 검색 정규화
    ├─ 공백 제거
    ├─ 특수문자 처리
    ├─ 한글/영문 분리
    └─ 결과: "apple 2025 ipad pro 11"
    │
    ▼
[3] 캐시 확인 (0.5초)
    │
    ├─ MISS: 캐시에 없음 → [4]로 진행
    │
    └─ HIT: 캐시에 있음 → [결과 반환]
         ✓ source: "cache"
         ✓ elapsed_ms: 50ms
    │
    ▼
[4] FastPath 검색 (4초)
    │
    ├─ 다나와 검색 API 호출
    ├─ HTML 파싱
    ├─ 최저가 추출
    │
    ├─ SUCCESS: 상품 발견 → [6]로 진행
    │  ✓ price: 1,299,000원
    │  ✓ link: https://prod.danawa.com/info/?pcode=9876543
    │  ✓ source: "fastpath"
    │
    └─ FAILURE: 상품 없음 → [5]로 진행
         ✗ ProductNotFoundException
         ✗ BlockedException (429 Too Many Requests)
         ✗ ParsingException
    │
    ▼
[5] SlowPath 검색 (6.5초) - FastPath 실패시만 실행
    │
    ├─ Playwright 브라우저 시작
    ├─ 다나와 검색 페이지 로드
    ├─ JavaScript 렌더링
    ├─ DOM 쿼리로 최저가 추출
    │
    ├─ SUCCESS: 상품 발견 → [6]로 진행
    │  ✓ price: 1,299,000원
    │  ✓ source: "slowpath"
    │
    └─ FAILURE: 상품 없음 → [에러 반환]
         ✗ BrowserException
         ✗ NetworkTimeoutException
    │
    ▼
[6] 결과 처리
    │
    ├─ 캐시 저장 (TTL: 1시간)
    ├─ 데이터베이스 로그 저장 (백그라운드)
    └─ API 응답 생성
    │
    ▼
[7] API 응답
    {
      "status": "success",
      "data": {
        "product_name": "Apple 2025 아이패드 프로 11",
        "lowest_price": 1299000,
        "link": "https://prod.danawa.com/info/?pcode=9876543",
        "is_cheaper": true,
        "price_diff": 218000,
        "source": "fastpath",
        "elapsed_ms": 234.5
      },
      "message": "다나와에서 218,000원 저렴한 가격 발견!"
    }
```

### 실패 흐름 (에러 케이스)

```
사용자 입력 (존재하지 않는 상품)
    │
    ▼
[1] 입력 검증 ✓
    │
    ▼
[2] 캐시 확인
    └─ MISS: 캐시에 없음
    │
    ▼
[3] FastPath 검색 (4초)
    │
    ├─ 다나와 검색 결과: 0건
    └─ ProductNotFoundException
    │
    ▼
[4] SlowPath 검색 (6.5초)
    │
    ├─ Playwright로 재검색
    ├─ 결과: 0건
    └─ ProductNotFoundException
    │
    ▼
[5] 에러 응답
    {
      "status": "error",
      "data": null,
      "message": "입력하신 상품을 다나와에서 찾을 수 없습니다.",
      "error_code": "PRODUCT_NOT_FOUND"
    }
```

---

## 핵심 컴포넌트

### 1. SearchOrchestrator (검색 조율자)
**파일**: `src/engine/orchestrator.py`

역할: 전체 검색 파이프라인 관리
- Cache 레이어 확인
- 타임아웃 예산 관리
- FastPath → SlowPath 폴백
- 최종 결과 조합

```python
# 사용 예
orchestrator = SearchOrchestrator(
    cache_service=cache_adapter,
    fastpath_executor=fastpath,
    slowpath_executor=slowpath,
    budget_config=BudgetConfig(total_budget=12.0),
)

result = await orchestrator.search(
    query="아이패드 프로 11",
    budget_ms=12000,
)
```

### 2. BudgetConfig (예산 관리)
**파일**: `src/engine/budget.py`

역할: 각 레이어별 타임아웃 할당
- 전체 예산: 12초
- 각 레이어: 명시적 할당
- 런타임 검증

```python
config = BudgetConfig(
    total_budget=12.0,      # 12초
    cache_timeout=0.5,      # 4%
    fastpath_timeout=4.0,   # 33%
    slowpath_timeout=6.5,   # 54%
)
```

### 3. CacheAdapter (캐시 추상화)
**파일**: `src/engine/cache_adapter.py`

역할: Redis와의 상호작용
- 캐시 키 생성 (해시)
- 직렬화/역직렬화
- TTL 관리

```python
# 캐시 키 예
cache_key = sha256("apple 2025 ipad pro 11")
cache_value = {
    "product_name": "...",
    "lowest_price": 1299000,
    "updated_at": "2025-12-19T10:30:00Z",
}
```

### 4. FastPathExecutor (HTTP 검색)
**파일**: `src/crawlers/fastpath_executor.py`

역할: HTTP 기반 빠른 검색
- 다나와 검색 API 호출
- 응답 파싱
- 최저가 추출

**장점**:
- ✓ 빠름 (보통 200-500ms)
- ✓ 비용 낮음
- ✓ 안정적

**단점**:
- ✗ 페이지 구조 변경에 약함
- ✗ JavaScript 렌더링 불가

### 5. SlowPathExecutor (Playwright 검색)
**파일**: `src/crawlers/slowpath_executor.py`

역할: Playwright 기반 고급 검색
- 브라우저 자동화
- JavaScript 실행
- 복잡한 DOM 처리

**장점**:
- ✓ JavaScript 지원
- ✓ 동적 페이지 처리
- ✓ 매우 신뢰도 높음

**단점**:
- ✗ 느림 (보통 3-8초)
- ✗ 리소스 많이 사용
- ✗ 브라우저 관리 필요

---

## 에러 처리 및 복구

### 예외 계층 구조

```
PriceDetectorException (기본)
│
├─ CrawlerException
│  ├─ ProductNotFoundException (상품 미발견)
│  ├─ NetworkTimeoutException (네트워크 타임아웃)
│  ├─ BlockedException (봇 차단)
│  ├─ BrowserException (브라우저 오류)
│  └─ ParsingException (파싱 오류)
│
├─ CacheException
│  ├─ CacheConnectionException (캐시 연결 실패)
│  └─ CacheSerializationException (직렬화 오류)
│
├─ DatabaseException
│  ├─ DatabaseConnectionException (DB 연결 실패)
│  └─ DatabaseQueryException (쿼리 실행 오류)
│
├─ ValidationException
│  ├─ InvalidQueryException (유효하지 않은 검색어)
│  ├─ InvalidPriceException (유효하지 않은 가격)
│  └─ InvalidURLException (유효하지 않은 URL)
│
└─ TimeoutException (전체 타임아웃)
```

### 폴백 전략

```
Cache 실패
    │ (에러 무시, 진행)
    ▼
FastPath 실패
    │ (ProductNotFoundException, BlockedException, NetworkTimeoutException)
    ▼
SlowPath 시도
    │
    ├─ 성공 → 결과 반환
    │
    └─ 실패 → 에러 반환
        └─ BrowserException, NetworkTimeoutException
```

### 에러별 사용자 메시지

| 에러 코드 | 원인 | 사용자 메시지 |
|---------|------|-----------|
| `PRODUCT_NOT_FOUND` | 상품 미발견 | "입력하신 상품을 찾을 수 없습니다." |
| `NETWORK_TIMEOUT` | 타임아웃 | "검색 시간이 초과되었습니다." |
| `BLOCKED` | 봇 차단 | "현재 서비스를 이용할 수 없습니다." |
| `BROWSER_ERROR` | 브라우저 오류 | "현재 서비스를 이용할 수 없습니다." |
| `SERVICE_UNAVAILABLE` | 모든 경로 실패 | "문제가 계속되면 관리자에게 문의해주세요." |

---

## 성능 최적화

### 1. 캐시 전략

**캐시 키 생성**:
```python
# 안전한 해시 기반 키
cache_key = sha256(normalized_query.encode()).hexdigest()
# 예: "a3f2e1d4c5b6a7f8e9d0c1b2a3f4e5d6"
```

**TTL (Time To Live)**:
- 정상 결과: 1시간 (3600초)
- 미발견 결과: 5분 (300초)
- 실패 결과: 1분 (60초)

**캐시 무효화**:
- 매일 자정 (00:00) 전체 초기화
- 수동 초기화 가능

### 2. 타임아웃 최적화

**현재 할당** (실제 성능 기반):
```
Cache:    0.5초 (연결, 조회)
FastPath: 4.0초 (HTTP, 파싱)
SlowPath: 6.5초 (브라우저 시작, 페이지 로드, DOM 쿼리)
─────────────────
합계:    12.0초
```

**개선 여지**:
- FastPath는 보통 300-500ms → 4초는 충분한 여유
- SlowPath는 보통 2-4초 → 6.5초는 여유 있음
- 캐시 히트율 높아지면 불필요

### 3. 동시성 처리

**Redis 동시 접근**:
```python
# 안전한 설정 (기본값)
redis_client = Redis(
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    max_connections=50,  # 동시 연결 제한
)
```

**브라우저 인스턴스 공유**:
```python
# 글로벌 싱글톤 (스레드-세이프)
_shared_browser: Optional[Browser] = None
_shared_lock: asyncio.Lock = asyncio.Lock()

async with _shared_lock:
    if _shared_browser is None:
        _shared_browser = await create_browser()
```

---

## 배포 및 운영

### 환경 변수

```bash
# .env 파일
ENVIRONMENT=production           # production or development
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://user:pass@localhost/importback
CRAWLER_TIMEOUT=12000            # ms
CRAWLER_USER_AGENT="Mozilla/5.0..."
CRAWLER_MAX_RETRIES=3
CRAWLER_PLAYWRIGHT_WARMUP=false  # Playwright 사전 시작 여부
```

### 프로덕션 체크리스트

- [ ] MyPy strict 모드 통과
- [ ] 모든 테스트 통과
- [ ] Redis 연결 확인
- [ ] PostgreSQL 연결 확인
- [ ] Playwright 브라우저 설치 확인
- [ ] 환경 변수 설정
- [ ] 로그 레벨 설정
- [ ] 모니터링 설정
- [ ] 에러 트래킹 설정 (Sentry 등)

### 모니터링 포인트

```
1. API 응답 시간
   - 평균: < 2초 (캐시 히트)
   - 평균: 3-5초 (FastPath)
   - 평균: 4-8초 (SlowPath)

2. 캐시 히트율
   - 목표: > 70%
   - 모니터링: Redis INFO stats

3. 에러율
   - 목표: < 2%
   - 세부: ProductNotFoundException, Timeout 등

4. 리소스 사용량
   - Redis 메모리: < 1GB
   - 브라우저 프로세스: < 4개 동시
   - 데이터베이스 연결: < 10개

5. 다나와 차단 여부
   - 모니터링: BlockedException 빈도
   - 조치: 재시도 간격 증가, User-Agent 로테이션
```

### 장애 대응

**시나리오 1: Redis 다운**
- 영향: 캐시 미사용, 응답 속도 저하
- 대응: Cache 계층 무시, FastPath/SlowPath 계속 실행
- 복구: Redis 재시작 (자동 재연결)

**시나리오 2: 다나와 봇 차단**
- 영향: FastPath 실패, SlowPath로 폴백
- 대응: 요청 간격 증가, User-Agent 변경
- 복구: 일정 시간 후 자동 재시도

**시나리오 3: Playwright 브라우저 크래시**
- 영향: SlowPath 이용 불가
- 대응: 브라우저 자동 재시작
- 복구: 장애 지속 시 서비스 일시 중단

---

## 개발자 가이드

### 로컬 개발 환경 설정

```bash
# 1. 의존성 설치
pip install -r requirements.txt
pnpm install

# 2. Redis 시작
docker run -d -p 6379:6379 redis:7

# 3. PostgreSQL 시작
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=pass postgres:15

# 4. 환경 변수 설정
cp .env.example .env

# 5. 데이터베이스 초기화
python -m alembic upgrade head

# 6. 서버 시작
uvicorn src.app:app --reload

# 7. 테스트 실행
pytest tests/ -v

# 8. 타입 체크
mypy src/
```

### 코드 스타일 가이드

```python
# ✓ 좋음
result = EdgeCaseHandler.safe_int(value, min_val=0, max_val=10**9)

# ✗ 나쁨
result = int(value)  # 예외 처리 없음

# ✓ 좋음
try:
    price = request.current_price
    if price is not None and price > 0:
        # 처리
except (TypeError, ValueError) as e:
    logger.error(f"Error: {e}")

# ✗ 나쁨
except Exception:  # 너무 일반적
    pass

# ✓ 좋음
if request.current_price is not None:
    is_cheaper = lowest_price < request.current_price

# ✗ 나쁨
is_cheaper = lowest_price < request.current_price  # None 체크 없음
```

---

## 참고 문서

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Pydantic 검증](https://docs.pydantic.dev/)
- [Playwright 가이드](https://playwright.dev/)
- [Redis 명령어](https://redis.io/commands/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)

---

**마지막 업데이트**: 2025-12-19
**담당자**: Engineering Team
**상태**: Production Ready ✓
