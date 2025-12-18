# Engine 아키텍처 적용 계획

## 현황 분석

### 현재 프로젝트의 정체
이 프로젝트는 **Cache-First · Budget-Aware · Fallback-Driven Crawler Engine**이다.
- ❌ CRUD API가 아님
- ❌ User/Auth/Item 중심 서버가 아님
- ✅ 고성능 크롤링/분석 엔진을 HTTP로 감싼 서비스

### 핵심 요구사항
1. **Budget**: 최대 12초 예산 (Cache 200ms, FastPath 3s, SlowPath 9s)
2. **Fast/Slow Path**: HTTP → Playwright Fallback
3. **Failure-aware**: 실패 유형별 분류 및 재시도
4. **Stateful Cache**: Redis 6h TTL
5. **Orchestration**: 단계별 실행 제어

---

## Phase 1: Engine Layer 생성

### 목표
현재 흩어진 orchestration 로직을 독립된 Engine Layer로 분리

### 디렉토리 구조
```
src/
├── api/
│   └── routes/
│       └── price_routes.py           # HTTP Translator만
│
├── engine/                            # 🔥 NEW
│   ├── __init__.py
│   ├── orchestrator.py                # SearchOrchestrator
│   ├── budget.py                      # BudgetManager
│   ├── result.py                      # SearchResult 표준화
│   └── strategy.py                    # Execution Strategy
│
├── crawlers/
│   └── danawa/
│       ├── __init__.py
│       ├── fastpath/                  # 🔥 RENAMED from boundary
│       │   ├── __init__.py
│       │   ├── http_search.py
│       │   └── parser.py
│       ├── slowpath/                  # 🔥 RENAMED from playwright
│       │   ├── __init__.py
│       │   └── browser_search.py
│       ├── core/
│       │   └── orchestrator.py        # → engine/orchestrator.py로 이동 예정
│       └── metrics/
│
├── services/
│   └── impl/
│       ├── cache_service.py
│       ├── price_search_service.py    # → engine으로 이동 예정
│       └── search_failure_service.py
│
├── repositories/
└── utils/
```

### 단계별 작업

#### Step 1.1: engine/ 기본 구조 생성
```python
# src/engine/__init__.py
from .orchestrator import SearchOrchestrator
from .budget import BudgetManager
from .result import SearchResult, SearchStatus
from .strategy import ExecutionStrategy

__all__ = [
    'SearchOrchestrator',
    'BudgetManager', 
    'SearchResult',
    'SearchStatus',
    'ExecutionStrategy',
]
```

#### Step 1.2: BudgetManager 구현
```python
# src/engine/budget.py
from dataclasses import dataclass
from time import time
from typing import Optional

@dataclass
class BudgetConfig:
    """예산 설정"""
    total_budget: float = 12.0      # 전체 예산
    cache_timeout: float = 0.2      # Cache 조회 최대 시간
    fastpath_timeout: float = 3.0   # FastPath 최대 시간
    slowpath_timeout: float = 9.0   # SlowPath 최대 시간
    min_remaining: float = 1.0      # 실행 최소 여유 시간

class BudgetManager:
    """시간/리소스 예산 관리자"""
    
    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()
        self.start_time: Optional[float] = None
        self._checkpoints: dict[str, float] = {}
    
    def start(self) -> None:
        """예산 측정 시작"""
        self.start_time = time()
        self._checkpoints.clear()
    
    def checkpoint(self, name: str) -> None:
        """체크포인트 기록"""
        if self.start_time is None:
            raise RuntimeError("Budget not started")
        self._checkpoints[name] = time() - self.start_time
    
    def elapsed(self) -> float:
        """경과 시간"""
        if self.start_time is None:
            return 0.0
        return time() - self.start_time
    
    def remaining(self) -> float:
        """남은 예산"""
        return max(0.0, self.config.total_budget - self.elapsed())
    
    def can_execute_fastpath(self) -> bool:
        """FastPath 실행 가능 여부"""
        return self.remaining() >= self.config.fastpath_timeout
    
    def can_execute_slowpath(self) -> bool:
        """SlowPath 실행 가능 여부"""
        return self.remaining() >= self.config.slowpath_timeout
    
    def is_exhausted(self) -> bool:
        """예산 소진 여부"""
        return self.remaining() < self.config.min_remaining
    
    def get_timeout_for(self, stage: str) -> float:
        """단계별 타임아웃 계산"""
        remaining = self.remaining()
        
        if stage == "cache":
            return min(self.config.cache_timeout, remaining)
        elif stage == "fastpath":
            return min(self.config.fastpath_timeout, remaining)
        elif stage == "slowpath":
            return min(self.config.slowpath_timeout, remaining)
        else:
            return remaining
    
    def get_report(self) -> dict:
        """예산 사용 리포트"""
        return {
            "total_budget": self.config.total_budget,
            "elapsed": self.elapsed(),
            "remaining": self.remaining(),
            "checkpoints": self._checkpoints,
            "is_exhausted": self.is_exhausted(),
        }
```

#### Step 1.3: SearchResult 표준화
```python
# src/engine/result.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class SearchStatus(str, Enum):
    """검색 상태"""
    SUCCESS = "success"              # 성공
    CACHE_HIT = "cache_hit"          # 캐시 히트
    FASTPATH_SUCCESS = "fastpath_success"  # FastPath 성공
    SLOWPATH_SUCCESS = "slowpath_success"  # SlowPath 성공
    TIMEOUT = "timeout"              # 타임아웃
    PARSE_ERROR = "parse_error"      # 파싱 오류
    BLOCKED = "blocked"              # 차단
    NO_RESULTS = "no_results"        # 결과 없음
    BUDGET_EXHAUSTED = "budget_exhausted"  # 예산 소진

@dataclass
class SearchResult:
    """검색 결과 표준 포맷"""
    status: SearchStatus
    product_url: Optional[str] = None
    price: Optional[int] = None
    
    # 메타데이터
    query: Optional[str] = None
    source: Optional[str] = None  # "cache" | "fastpath" | "slowpath"
    elapsed_ms: Optional[float] = None
    
    # 디버깅 정보
    error_message: Optional[str] = None
    budget_report: Optional[dict] = None
    
    @classmethod
    def from_cache(cls, product_url: str, price: int, query: str, elapsed_ms: float):
        """캐시에서 반환"""
        return cls(
            status=SearchStatus.CACHE_HIT,
            product_url=product_url,
            price=price,
            query=query,
            source="cache",
            elapsed_ms=elapsed_ms,
        )
    
    @classmethod
    def from_fastpath(cls, product_url: str, price: int, query: str, elapsed_ms: float):
        """FastPath에서 반환"""
        return cls(
            status=SearchStatus.FASTPATH_SUCCESS,
            product_url=product_url,
            price=price,
            query=query,
            source="fastpath",
            elapsed_ms=elapsed_ms,
        )
    
    @classmethod
    def from_slowpath(cls, product_url: str, price: int, query: str, elapsed_ms: float):
        """SlowPath에서 반환"""
        return cls(
            status=SearchStatus.SLOWPATH_SUCCESS,
            product_url=product_url,
            price=price,
            query=query,
            source="slowpath",
            elapsed_ms=elapsed_ms,
        )
    
    @classmethod
    def timeout(cls, query: str, elapsed_ms: float, budget_report: dict):
        """타임아웃"""
        return cls(
            status=SearchStatus.TIMEOUT,
            query=query,
            elapsed_ms=elapsed_ms,
            budget_report=budget_report,
            error_message="Search timeout exceeded",
        )
    
    @classmethod
    def parse_error(cls, query: str, elapsed_ms: float, error: str):
        """파싱 오류"""
        return cls(
            status=SearchStatus.PARSE_ERROR,
            query=query,
            elapsed_ms=elapsed_ms,
            error_message=error,
        )
```

#### Step 1.4: ExecutionStrategy
```python
# src/engine/strategy.py
from enum import Enum
from typing import Protocol

class ExecutionPath(str, Enum):
    """실행 경로"""
    CACHE = "cache"
    FASTPATH = "fastpath"
    SLOWPATH = "slowpath"

class SearchExecutor(Protocol):
    """검색 실행자 인터페이스"""
    async def execute(self, query: str, timeout: float) -> SearchResult:
        ...

class ExecutionStrategy:
    """실행 전략 결정"""
    
    @staticmethod
    def should_fallback_to_slowpath(error: Exception) -> bool:
        """SlowPath로 Fallback 여부 결정"""
        # TimeoutError: FastPath 타임아웃
        # ParsingError: HTML 구조 변경
        # BlockedError: 차단 감지
        from crawlers.danawa.core.exceptions import (
            TimeoutError,
            ParsingError,
            BlockedError,
        )
        
        return isinstance(error, (TimeoutError, ParsingError, BlockedError))
    
    @staticmethod
    def get_retry_count(error: Exception) -> int:
        """재시도 횟수 결정"""
        from crawlers.danawa.core.exceptions import (
            TimeoutError,
            ParsingError,
            BlockedError,
        )
        
        if isinstance(error, TimeoutError):
            return 1  # 타임아웃은 1회만
        elif isinstance(error, ParsingError):
            return 0  # 파싱 오류는 재시도 무의미
        elif isinstance(error, BlockedError):
            return 2  # 차단은 2회 재시도
        else:
            return 0
```

#### Step 1.5: SearchOrchestrator 구현
```python
# src/engine/orchestrator.py
from typing import Optional
from src.core.logging import logger
from .budget import BudgetManager, BudgetConfig
from .result import SearchResult, SearchStatus
from .strategy import ExecutionStrategy, ExecutionPath

class SearchOrchestrator:
    """검색 엔진 오케스트레이터"""
    
    def __init__(
        self,
        cache_service,
        fastpath_executor,
        slowpath_executor,
        budget_config: Optional[BudgetConfig] = None,
    ):
        self.cache = cache_service
        self.fastpath = fastpath_executor
        self.slowpath = slowpath_executor
        self.budget_manager = BudgetManager(budget_config)
        self.strategy = ExecutionStrategy()
    
    async def search(self, query: str) -> SearchResult:
        """통합 검색 실행"""
        self.budget_manager.start()
        logger.info(f"Search started: {query}")
        
        try:
            # 1. Cache 확인
            result = await self._try_cache(query)
            if result:
                return result
            
            # 2. FastPath 시도
            result = await self._try_fastpath(query)
            if result:
                return result
            
            # 3. SlowPath Fallback
            result = await self._try_slowpath(query)
            if result:
                return result
            
            # 4. 모든 경로 실패
            return SearchResult(
                status=SearchStatus.NO_RESULTS,
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                budget_report=self.budget_manager.get_report(),
            )
        
        except Exception as e:
            logger.error(f"Search failed: {query}", exc_info=True)
            return SearchResult.parse_error(
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                error=str(e),
            )
    
    async def _try_cache(self, query: str) -> Optional[SearchResult]:
        """Cache 조회"""
        try:
            timeout = self.budget_manager.get_timeout_for("cache")
            cached = await self.cache.get(query, timeout=timeout)
            
            if cached:
                self.budget_manager.checkpoint("cache_hit")
                logger.info(f"Cache hit: {query}")
                return SearchResult.from_cache(
                    product_url=cached["url"],
                    price=cached["price"],
                    query=query,
                    elapsed_ms=self.budget_manager.elapsed() * 1000,
                )
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
        
        self.budget_manager.checkpoint("cache_miss")
        return None
    
    async def _try_fastpath(self, query: str) -> Optional[SearchResult]:
        """FastPath 시도"""
        if not self.budget_manager.can_execute_fastpath():
            logger.warning("FastPath skipped: budget exhausted")
            return None
        
        try:
            timeout = self.budget_manager.get_timeout_for("fastpath")
            result = await self.fastpath.execute(query, timeout=timeout)
            
            self.budget_manager.checkpoint("fastpath_success")
            logger.info(f"FastPath success: {query}")
            
            # Cache 저장
            await self.cache.set(query, result, ttl=21600)  # 6h
            
            return SearchResult.from_fastpath(
                product_url=result.product_url,
                price=result.price,
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
            )
        
        except Exception as e:
            self.budget_manager.checkpoint("fastpath_failed")
            logger.warning(f"FastPath failed: {e}")
            
            # Fallback 여부 결정
            if not self.strategy.should_fallback_to_slowpath(e):
                raise
        
        return None
    
    async def _try_slowpath(self, query: str) -> Optional[SearchResult]:
        """SlowPath 시도"""
        if not self.budget_manager.can_execute_slowpath():
            logger.error("SlowPath skipped: budget exhausted")
            return SearchResult.timeout(
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
                budget_report=self.budget_manager.get_report(),
            )
        
        try:
            timeout = self.budget_manager.get_timeout_for("slowpath")
            result = await self.slowpath.execute(query, timeout=timeout)
            
            self.budget_manager.checkpoint("slowpath_success")
            logger.info(f"SlowPath success: {query}")
            
            # Cache 저장
            await self.cache.set(query, result, ttl=21600)  # 6h
            
            return SearchResult.from_slowpath(
                product_url=result.product_url,
                price=result.price,
                query=query,
                elapsed_ms=self.budget_manager.elapsed() * 1000,
            )
        
        except Exception as e:
            self.budget_manager.checkpoint("slowpath_failed")
            logger.error(f"SlowPath failed: {e}")
            raise
```

---

## Phase 2: FastPath/SlowPath 추상화

### 목표
boundary/ → fastpath/, playwright/ → slowpath/로 명확한 역할 분리

### Step 2.1: Executor 인터페이스 정의
```python
# src/crawlers/danawa/__init__.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class CrawlResult:
    """크롤링 결과"""
    product_url: str
    price: int
    metadata: dict = None

class SearchExecutor(ABC):
    """검색 실행자 추상 인터페이스"""
    
    @abstractmethod
    async def execute(self, query: str, timeout: float) -> CrawlResult:
        """검색 실행"""
        pass
```

### Step 2.2: FastPath Executor
```python
# src/crawlers/danawa/fastpath/__init__.py
from ..executor import SearchExecutor, CrawlResult
from .http_search import DanawaHttpSearch
from .parser import DanawaParser

class FastPathExecutor(SearchExecutor):
    """HTTP 기반 빠른 경로"""
    
    def __init__(self):
        self.http_search = DanawaHttpSearch()
        self.parser = DanawaParser()
    
    async def execute(self, query: str, timeout: float) -> CrawlResult:
        # 기존 boundary/ 로직 사용
        html = await self.http_search.fetch(query, timeout=timeout)
        result = self.parser.parse(html)
        
        return CrawlResult(
            product_url=result["url"],
            price=result["price"],
            metadata={"method": "fastpath"}
        )
```

### Step 2.3: SlowPath Executor
```python
# src/crawlers/danawa/slowpath/__init__.py
from ..executor import SearchExecutor, CrawlResult
from .browser_search import PlaywrightSearch

class SlowPathExecutor(SearchExecutor):
    """Playwright 기반 느린 경로"""
    
    def __init__(self):
        self.browser_search = PlaywrightSearch()
    
    async def execute(self, query: str, timeout: float) -> CrawlResult:
        # 기존 playwright/ 로직 사용
        result = await self.browser_search.search(query, timeout=timeout)
        
        return CrawlResult(
            product_url=result.url,
            price=result.price,
            metadata={"method": "slowpath"}
        )
```

---

## Phase 3: API Layer 최소화

### 목표
FastAPI routes는 HTTP → Engine 번역만 담당

### Step 3.1: price_routes.py 단순화
```python
# src/api/routes/price_routes.py
from fastapi import APIRouter, Depends, HTTPException
from src.engine import SearchOrchestrator, SearchStatus
from src.schemas.price_schema import PriceResponse

router = APIRouter(prefix="/price", tags=["price"])

async def get_orchestrator() -> SearchOrchestrator:
    """Orchestrator DI"""
    from src.crawlers.danawa.fastpath import FastPathExecutor
    from src.crawlers.danawa.slowpath import SlowPathExecutor
    from src.services.impl.cache_service import CacheService
    
    return SearchOrchestrator(
        cache_service=CacheService(),
        fastpath_executor=FastPathExecutor(),
        slowpath_executor=SlowPathExecutor(),
    )

@router.get("/search", response_model=PriceResponse)
async def search_price(
    query: str,
    orchestrator: SearchOrchestrator = Depends(get_orchestrator),
):
    """가격 검색 (Engine으로 위임)"""
    result = await orchestrator.search(query)
    
    if result.status in [SearchStatus.CACHE_HIT, SearchStatus.FASTPATH_SUCCESS, SearchStatus.SLOWPATH_SUCCESS]:
        return PriceResponse(
            url=result.product_url,
            price=result.price,
            source=result.source,
            elapsed_ms=result.elapsed_ms,
        )
    else:
        raise HTTPException(
            status_code=500 if result.status == SearchStatus.TIMEOUT else 404,
            detail=result.error_message or "Search failed",
        )
```

---

## Phase 4: 테스트 전략

### Step 4.1: BudgetManager 단위 테스트
```python
# tests/unit/test_budget_manager.py
import pytest
import asyncio
from src.engine.budget import BudgetManager, BudgetConfig

def test_budget_start():
    manager = BudgetManager()
    manager.start()
    assert manager.elapsed() >= 0

def test_budget_remaining():
    config = BudgetConfig(total_budget=10.0)
    manager = BudgetManager(config)
    manager.start()
    
    assert manager.remaining() <= 10.0
    assert manager.remaining() >= 0

async def test_budget_exhaustion():
    config = BudgetConfig(total_budget=0.1)
    manager = BudgetManager(config)
    manager.start()
    
    await asyncio.sleep(0.2)
    assert manager.is_exhausted()
```

### Step 4.2: Orchestrator 통합 테스트
```python
# tests/integration/test_orchestrator.py
import pytest
from src.engine import SearchOrchestrator, SearchStatus

@pytest.mark.asyncio
async def test_cache_hit(mock_cache, mock_fastpath, mock_slowpath):
    orchestrator = SearchOrchestrator(
        cache_service=mock_cache,
        fastpath_executor=mock_fastpath,
        slowpath_executor=mock_slowpath,
    )
    
    result = await orchestrator.search("삼성 갤럭시")
    assert result.status == SearchStatus.CACHE_HIT
    assert result.source == "cache"

@pytest.mark.asyncio
async def test_fastpath_fallback(mock_cache_miss, mock_fastpath_timeout, mock_slowpath):
    orchestrator = SearchOrchestrator(
        cache_service=mock_cache_miss,
        fastpath_executor=mock_fastpath_timeout,
        slowpath_executor=mock_slowpath,
    )
    
    result = await orchestrator.search("삼성 갤럭시")
    assert result.status == SearchStatus.SLOWPATH_SUCCESS
    assert result.source == "slowpath"
```

---

## Phase 5: 마이그레이션 순서

### 순서 (충돌 최소화)
1. ✅ **engine/ 디렉토리 생성** (신규 코드, 기존 영향 없음)
2. ✅ **BudgetManager 구현 + 테스트**
3. ✅ **SearchResult 표준화**
4. ✅ **ExecutionStrategy 구현**
5. ✅ **SearchOrchestrator 구현**
6. 🔄 **FastPath/SlowPath Executor 래퍼 생성**
7. 🔄 **API Layer 수정** (price_routes.py → Orchestrator 사용)
8. 🔄 **기존 price_search_service.py 제거**
9. 🔄 **통합 테스트 실행**
10. ✅ **문서화 업데이트**

---

## 예상 효과

### Before (현재)
```
HTTP → PriceSearchService (복잡한 로직 혼재)
  ├── Cache 체크
  ├── Normalization
  ├── DanawaOrchestrator 호출
  │   ├── FastPath (boundary/)
  │   └── SlowPath (playwright/)
  └── 결과 반환
```

### After (개선)
```
HTTP (단순 번역)
  ↓
SearchOrchestrator (Engine Layer)
  ├── BudgetManager (12초 예산 관리)
  ├── Cache Strategy
  ├── FastPath Executor (독립)
  ├── SlowPath Executor (독립)
  └── Result Normalizer (표준화)
```

### 개선점
1. **역할 명확화**: HTTP/Engine/Executor 완전 분리
2. **Budget 가시화**: 12초 예산 명시적 관리
3. **Fallback 로직 명확화**: Strategy 패턴으로 분리
4. **테스트 용이성**: 각 컴포넌트 독립 테스트 가능
5. **확장성**: 새로운 Path 추가 용이 (예: GraphQL Path)

---

## 참고
- Scrapy Engine Pattern
- Crawlee Orchestration
- FastAPI Best Practices (HTTP/Engine 분리)
