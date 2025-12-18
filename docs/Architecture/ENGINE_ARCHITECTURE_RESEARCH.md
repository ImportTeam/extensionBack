# 크롤러 엔진 아키텍처 리서치

## 프로젝트 재정의

이 프로젝트는 **CRUD API가 아니라 Cache-First · Budget-Aware · Fallback-Driven Crawler Engine**이다.

### 핵심 키워드
- **Budget (시간/리소스 예산)**
- **Fast Path / Slow Path 분기**
- **Failure-aware**
- **Stateful Cache**
- **Orchestration 중심**

---

## 1. Scrapy Architecture (Event-Driven Engine)

### 핵심 구조
```
Engine (Central Controller)
  ├── Scheduler (Request Queue)
  ├── Downloader (HTTP Fetcher)
  ├── Spider (Response Processor)
  ├── Downloader Middleware (Request/Response Interceptor)
  ├── Spider Middleware (Spider Input/Output Handler)
  └── Item Pipeline (Data Processing)
```

### Data Flow (Event Loop)
1. **Engine** → Spider: 초기 Requests 요청
2. **Engine** → Scheduler: Requests 스케줄링
3. **Scheduler** → Engine: 다음 Request 반환
4. **Engine** → Downloader: Request 전송 (Downloader Middleware 통과)
5. **Downloader** → Engine: Response 생성 (Downloader Middleware 통과)
6. **Engine** → Spider: Response 처리 (Spider Middleware 통과)
7. **Spider** → Engine: Items + 새 Requests 반환
8. **Engine** → Item Pipeline: Items 전송
9. **Engine** → Scheduler: 새 Requests 전송
10. **반복**: Scheduler가 비면 종료

### 주요 특징
- **Engine이 모든 컴포넌트 간 데이터 흐름 제어**
- **Middleware를 통한 Request/Response 변환**
- **Twisted 기반 비동기 이벤트 루프**
- **Scheduler가 Request 우선순위/순서 관리**

### 시사점
✅ Engine 중심 설계 → Orchestrator 패턴
✅ Middleware 체계 → Fast/Slow Path 분기점
✅ 우선순위 큐 → Budget 관리 가능
✅ Item Pipeline → 결과 표준화 레이어

---

## 2. Crawlee Architecture (Context-Driven Pipeline)

### 핵심 구조
```
Crawler (Orchestrator)
  ├── RequestQueue (Dynamic Queue with Deduplication)
  ├── Autoscaling (Budget-aware Concurrency)
  ├── Context (Request + Page + Queue + Storage)
  ├── Router (URL Pattern Matching)
  ├── Storage Client (Dataset/KV Store/Request Queue)
  └── Event System (Lifecycle Hooks)
```

### Request Queue 특징
- **Breadth-first / Depth-first 지원**
- **자동 중복 제거 (Deduplication)**
- **Persistence (로컬 storage + 메모리)**
- **우선순위 큐 (`foremost` position)**

### Context-Aware Helpers
```python
async def handler(context):
    # context.request - 현재 요청
    # context.page - Playwright/Puppeteer 페이지
    # context.enqueue_links() - 자동 큐 추가 (전략: All/SameHostname/SameDomain)
    # context.push_data() - 자동 Dataset 저장
```

### Autoscaling 메커니즘
```python
ConcurrencySettings(
    min_concurrency=2,      # 최소 동시 작업
    max_concurrency=10,     # 최대 동시 작업 (Budget)
)
```

### Fallback Handler 패턴
```python
@router.failed_handler
async def failed_request_handler(context):
    # 실패한 요청 로깅/저장
    # Fallback 로직 실행
```

### 시사점
✅ RequestQueue = Budget-aware 큐
✅ Context = 모든 필요 도구 주입 (DI)
✅ Autoscaling = 리소스 예산 관리
✅ Router = Fast/Slow Path 분기
✅ Failed Handler = Failure-aware 설계

---

## 3. Apify SDK (Actor Lifecycle Management)

### Actor Lifecycle
```python
async with Actor:
    # 1. Init: 환경 설정, 스토리지 초기화
    actor_input = await Actor.get_input()
    
    # 2. Execute: 메인 로직
    request_queue = await Actor.open_request_queue()
    
    # 3. Event Handling
    Actor.on(Event.PERSIST_STATE, save_state)
    Actor.on(Event.MIGRATING, handle_migration)
    Actor.on(Event.ABORTING, cleanup)
    
    # 4. Exit: 자동 정리
```

### Event System
- **SYSTEM_INFO**: CPU/메모리 사용량 모니터링
- **MIGRATING**: 서버 마이그레이션 시 상태 저장
- **ABORTING**: 강제 종료 시 정리 작업
- **PERSIST_STATE**: 주기적 상태 저장

### Storage 추상화
```python
# Dataset: 결과 데이터
await Actor.push_data({"url": url, "title": title})

# Key-Value Store: 상태/설정
await Actor.set_value('STATE', {"progress": 50})

# Request Queue: URL 큐
request_queue = await Actor.open_request_queue()
```

### 시사점
✅ Context Manager = 자동 초기화/정리
✅ Event System = 외부 신호 대응
✅ Storage 추상화 = 영속 계층 분리
✅ Metamorph = Actor 전환 (Fallback 활용 가능)

---

## 4. FastAPI Best Practices (HTTP Engine 분리)

### 프로젝트 구조
```
src/
├── api/             # HTTP Translator (FastAPI routes)
│   └── price.py
├── engine/          # Core Engine Layer
│   ├── search_facade.py   # 진입점
│   ├── budget.py          # 시간/리소스 예산
│   ├── pipeline.py        # 실행 파이프라인
│   └── result.py          # 결과 표준화
├── crawlers/        # Execution Subsystem
│   └── danawa/
│       ├── boundary/       # FastPath
│       ├── core/           # Orchestration
│       ├── playwright/     # SlowPath
│       └── metrics/        # Observability
├── services/        # Decision Layer
│   ├── cache/
│   ├── analysis/
│   └── normalization/
└── repositories/    # Persistence
```

### 핵심 원칙
1. **HTTP는 껍데기** - FastAPI는 Engine의 입구일 뿐
2. **CRUD Layering 금지** - Pipeline Layering 사용
3. **Crawlers는 독립된 Execution Subsystem**
4. **utils는 Pure Function만 (IO/상태 없음)**

### 파이프라인 설계
```
Router
 → SearchFacade
    → CacheStrategy
    → FastPathExecutor
    → FallbackExecutor
    → FailureAnalyzer
```

### 시사점
✅ HTTP와 Engine 완전 분리
✅ Pipeline 단계별 모듈화
✅ Services = 결정, Crawlers = 실행
✅ utils는 도메인 침범 금지

---

## 5. 통합 패턴 정리

### 공통 아키텍처 원리

#### A. Orchestrator 중심 설계
- **Scrapy**: Engine이 모든 흐름 제어
- **Crawlee**: Crawler가 Context + Queue + Router 관리
- **Apify**: Actor가 Lifecycle + Event + Storage 관리
- **FastAPI BP**: SearchFacade가 파이프라인 진입점

#### B. Request Queue + Priority
- **Scrapy**: Scheduler (우선순위 큐)
- **Crawlee**: RequestQueue (foremost position, BFS/DFS)
- **현재 프로젝트**: Redis Cache (6h TTL) → Queue로 확장 필요

#### C. Fast/Slow Path 분기
- **Scrapy**: Downloader Middleware로 분기
- **Crawlee**: Router + Failed Handler
- **현재 프로젝트**: HTTP FastPath → Playwright Fallback

#### D. Budget Management
- **Crawlee**: ConcurrencySettings (min/max)
- **현재 프로젝트**: 12초 타임아웃 → Budget Manager 필요

#### E. Failure Handling
- **Scrapy**: Retry Middleware + Error Callbacks
- **Crawlee**: Failed Request Handler + 재시도 로직
- **Apify**: ABORTING Event + 상태 저장
- **현재 프로젝트**: search_failure_repository → Analyzer로 확장

#### F. Storage 추상화
- **Crawlee**: Dataset/KV Store/Request Queue
- **Apify**: Actor Storage (영속/메모리 혼합)
- **현재 프로젝트**: PostgreSQL + Redis → 추상화 필요

---

## 6. 현재 프로젝트 매핑

### 기존 구조
```
src/
├── api/routes/
├── services/
│   └── impl/
│       └── price_search_service.py  # ⚠️ Orchestrator 역할 혼재
├── crawlers/danawa/
│   ├── boundary/    # FastPath
│   ├── playwright/  # SlowPath
│   └── core/        # Orchestrator
├── repositories/    # Storage
└── utils/           # ⚠️ 일부 domain 침범
```

### 개선 방향

#### Phase 1: Engine Layer 분리
```
src/
├── api/             # HTTP Translator
├── engine/          # 🔥 NEW
│   ├── orchestrator.py        # 메인 엔진
│   ├── budget_manager.py      # 12초 예산 관리
│   ├── request_queue.py       # Redis 기반 큐
│   └── result_normalizer.py   # 결과 표준화
├── crawlers/danawa/
│   ├── fastpath/    # HTTP 빠른 경로
│   ├── slowpath/    # Playwright 느린 경로
│   └── metrics/     # Observability
├── services/
│   ├── cache/       # 캐시 전략
│   ├── analysis/    # 실패 분석
│   └── normalization/  # 정규화
└── repositories/    # 영속 계층
```

#### Phase 2: Pipeline 명확화
```python
# engine/orchestrator.py
class SearchOrchestrator:
    def __init__(self, budget_manager, cache_service, fastpath, slowpath):
        self.budget = budget_manager
        self.cache = cache_service
        self.fastpath = fastpath
        self.slowpath = slowpath
    
    async def execute(self, query: str) -> SearchResult:
        # 1. Budget 체크
        if not self.budget.can_execute():
            raise BudgetExhaustedError()
        
        # 2. Cache 확인
        cached = await self.cache.get(query)
        if cached:
            return cached
        
        # 3. FastPath 시도
        try:
            result = await self.fastpath.search(query, timeout=3.0)
            await self.cache.set(query, result)
            return result
        except (TimeoutError, ParsingError):
            pass
        
        # 4. SlowPath Fallback
        result = await self.slowpath.search(query, timeout=9.0)
        await self.cache.set(query, result)
        return result
```

#### Phase 3: Budget Manager
```python
# engine/budget_manager.py
class BudgetManager:
    def __init__(self, max_duration: float = 12.0):
        self.max_duration = max_duration
        self.start_time = None
    
    def start(self):
        self.start_time = time.time()
    
    def remaining(self) -> float:
        if not self.start_time:
            return self.max_duration
        elapsed = time.time() - self.start_time
        return max(0, self.max_duration - elapsed)
    
    def can_execute(self) -> bool:
        return self.remaining() > 1.0  # 최소 1초 필요
```

---

## 7. 레퍼런스 요약

### Scrapy (96.3 benchmark)
- **강점**: Event-driven engine, Middleware 체계, 우선순위 큐
- **적용**: Engine 중심 설계, Request/Response 파이프라인

### Crawlee Python (62.8 benchmark)
- **강점**: Context-aware helpers, Autoscaling, RequestQueue, Router
- **적용**: Budget-aware 동시성, Failed Handler, Context 주입

### Apify SDK (86.9 benchmark)
- **강점**: Actor Lifecycle, Event System, Storage 추상화
- **적용**: 상태 관리, Event 기반 제어, 영속화 전략

### FastAPI Best Practices (15.1k stars)
- **강점**: HTTP/Engine 분리, Pipeline 모듈화, Domain 기준 구조
- **적용**: API Layer 최소화, Engine Layer 독립, 명확한 역할 분리

---

## 8. 다음 단계

### A. SearchFacade / Pipeline 스켈레톤 구현
- engine/orchestrator.py 생성
- FastPath/SlowPath 추상화
- Result 표준화

### B. Budget Manager 실제 구현
- 12초 타임아웃 관리
- 단계별 시간 할당 (Cache 200ms, FastPath 3s, SlowPath 9s)
- Timeout 전파 메커니즘

### C. FastPath ↔ Playwright Fallback 알고리즘
- Failure 유형 분류 (timeout/blocked/parse_error)
- 재시도 전략 (exponential backoff)
- Circuit Breaker 패턴

### D. 500 오류 구조적 분석
- Error Chain 추적
- Failure Log 분석
- Bottleneck 식별

---

## 참고 문서
- Scrapy Architecture: https://docs.scrapy.org/en/latest/topics/architecture.html
- Crawlee Python: https://crawlee.dev/python
- Apify SDK Python: https://docs.apify.com/sdk/python
- FastAPI Best Practices: https://github.com/zhanymkanov/fastapi-best-practices
