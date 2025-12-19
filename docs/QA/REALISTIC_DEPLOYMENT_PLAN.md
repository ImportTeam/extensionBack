# 🚀 현실적인 배포 전략: Render 무료 → 유료 로드맵

**작성**: 악독한 QA 팀장이 깨우친 진실
**목표**: 실제로 돌아가는 시스템 배포
**비용 최소화**: ✓
**품질 최대화**: ✓

---

## 📊 문제 진단

### 현재 상황

```
importBack 시스템 요구사항:
├─ FastPath: HTTP 크롤링 (메모리 ~100MB)
├─ SlowPath: Playwright 자동화 (메모리 300-500MB)
└─ 동시 사용자: 20명 지원 필요

Render 무료 플랜:
├─ 메모리: 512MB
├─ CPU: 0.5 vCPU (공유)
└─ 결론: Playwright 불가능 💀
```

### 핵심 질문

| 질문 | 현재 상태 | 필요 상태 |
|------|---------|---------|
| FastPath는 돌아가나? | ✓ 가능 | ✓ 필수 |
| SlowPath는 돌아가나? | ❌ OOM | ✓ 필수 |
| IP 차단 시 대응? | ❌ 없음 | ✓ 필수 |
| 모니터링? | ❌ 없음 | ✓ 필수 |

---

## 🎯 3단계 배포 전략

### Phase 1: FastPath만 (긴급 배포, 1주일)

**목표**: 동작하는 MVP를 빠르게 배포

**구성**:
```python
# src/engine/orchestrator.py - 수정 필요
class SearchOrchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.fastpath = FastPathExecutor()
        # ❌ self.slowpath = None (비활성화)
        # ❌ self.playwright = None (메모리 절약)
    
    async def search(self, query: str) -> SearchResult:
        # 캐시 확인
        cached = await self.cache.get(query)
        if cached:
            return cached
        
        # FastPath만 시도
        try:
            result = await self.fastpath.search(query)
            await self.cache.set(query, result)
            return result
        except Exception as e:
            # 모든 실패를 SERVICE_UNAVAILABLE로 반환
            logger.error(f"Search failed: {e}")
            raise ServiceUnavailableException(
                "현재 검색이 불가능합니다. 잠시 후 다시 시도해주세요."
            )
```

**배포 플랜**:
```bash
# 1. Render 무료 배포
git push origin main
# Render가 자동으로 배포

# 2. 환경 변수 설정
ENVIRONMENT=production
LOG_LEVEL=INFO
FEATURES_SLOWPATH_ENABLED=false  # SlowPath 비활성화

# 3. 테스트
curl -X POST "https://importback.onrender.com/api/v1/price/search" \
  -H "Content-Type: application/json" \
  -d '{"product_name":"아이패드 프로 11","current_price":1500000}'
```

**제약**:
- ✓ 메모리 512MB 충분
- ✓ 비용 $0
- ❌ SlowPath 없음
- ❌ IP 차단 시 100% 실패
- ⚠️ 성공률 약 60%

**생존 기간**: 1개월 (IP 차단되기 전)

---

### Phase 2: 프록시 추가 + FastPath 강화 (2-3주)

**목표**: IP 차단 대응

**구현**:
```python
# src/crawlers/proxy_rotator.py (새 파일)
class ProxyRotator:
    def __init__(self):
        self.proxies = [
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080",
            "socks5://proxy3.example.com:1080",
        ]
        self.current_index = 0
        self.failures = defaultdict(int)
    
    def get_next_proxy(self):
        """차단된 프록시 스킵"""
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_index % len(self.proxies)]
            self.current_index += 1
            
            if self.failures[proxy] < 5:  # 5회 이상 실패하면 건너뛰기
                return proxy
        
        # 모든 프록시 고장 → 리셋
        self.failures.clear()
        return self.proxies[0]
    
    def record_failure(self, proxy: str):
        self.failures[proxy] += 1
        logger.warning(f"Proxy {proxy} failed {self.failures[proxy]} times")
```

**환경 변수**:
```bash
# .env.production
PROXIES="http://p1:8080,http://p2:8080,socks5://p3:1080"
PROXY_ROTATION_ENABLED=true
PROXY_FAILURE_THRESHOLD=5
```

**비용**:
```
프록시 서비스: 월 $20-50
(Oxylabs, Bright Data, Smartproxy 등)

선택지:
- Bright Data: $75/월 (1GB 데이터)
- Oxylabs: $50/월 (스타터)
- Smartproxy: $25/월 (기본)

→ 추천: Smartproxy $25/월
```

**배포**:
```bash
# 1. 코드 푸시
git push origin feature/proxy-rotation

# 2. Render 환경 변수 업데이트
PROXIES="..."  # .env에서 복사

# 3. 재배포
# Render가 자동으로 감지하고 재시작

# 4. 모니터링
curl https://importback.onrender.com/api/v1/analytics/stats?period=24h
# 응답: success_rate이 60% → 85% 상승?
```

**효과**:
- ✓ IP 차단 우회 가능
- ✓ 성공률 60% → 80-85%
- ❌ SlowPath 여전히 없음
- ⚠️ 메모리 여전히 512MB

---

### Phase 3: SlowPath 외부화 (1개월)

**목표**: 완전 기능 구현

**선택지 분석**:

#### 옵션 A: Render 유료 + 로컬 Playwright

```
비용: Render Pro $70/월
장점:
  ✓ Playwright 직접 호스팅
  ✓ 응답 속도 빠름
  ✓ 통합 간단

단점:
  ✗ 비용이 매달 청구됨
  ✗ 메모리 부족 시 또 업그레이드 필요
```

#### 옵션 B: Browserless.io 외부 서비스

```
비용: Browserless $50/월 (250 세션/월)
장점:
  ✓ Render 무료 사용 가능
  ✓ Playwright 관리됨
  ✓ 자동 스케일링

단점:
  ✗ 네트워크 레이턴시 (100-200ms 추가)
  ✗ 외부 의존성
  ✗ API 호출 비용 계산 복잡
```

#### 옵션 C: AWS Lambda + Docker (최적)

```
비용: AWS Lambda Pay-as-you-go
  - 128MB 메모리: $0.0000083/초
  - 월 1,000회 x 6초 = 6,000초
  - 비용: $0.05/월
  + 다른 AWS 서비스: ~$5-20/월

장점:
  ✓ 매우 저렴
  ✓ 스케일링 자동
  ✓ SlowPath 분리 가능

단점:
  ✗ 설정 복잡
  ✗ 콜드 스타트 5-10초
  ✗ 엔지니어링 난이도 높음
```

**추천 조합**:
```
Phase 3-1 (빠른 배포):
  - Render Free (FastPath)
  - Browserless.io (SlowPath)
  - Smartproxy (프록시)
  - 월 비용: $0 + $50 + $25 = $75

Phase 3-2 (최적화):
  - AWS Lambda (SlowPath)
  - Render Free (FastPath)
  - Smartproxy (프록시)
  - 월 비용: $0 + $5-10 + $25 = $30-35
```

---

## 📋 Phase 1 구현 상세 (지금 바로)

### Step 1: SlowPath 비활성화

**파일**: [src/engine/orchestrator.py](src/engine/orchestrator.py)

```python
class SearchOrchestrator:
    def __init__(self, config: BudgetConfig, ...):
        self.config = config
        self.fastpath_executor = fastpath
        self.slowpath_executor = None  # ← 비활성화
        
        # 환경 변수로 제어
        self.slowpath_enabled = os.getenv("FEATURES_SLOWPATH_ENABLED", "false") == "true"
    
    async def search(self, query: str, budget_ms: int = 12000) -> SearchResult:
        # 캐시 확인
        cached = await self._check_cache(query)
        if cached:
            return cached
        
        # FastPath만 실행
        try:
            result = await asyncio.wait_for(
                self.fastpath_executor.search(query),
                timeout=self.config.fastpath_timeout / 1000.0
            )
            result.source = "fastpath"
            
            # 캐시 저장
            await self._save_to_cache(query, result)
            return result
        
        except asyncio.TimeoutError:
            raise TimeoutException("검색 시간이 초과되었습니다.")
        except Exception as e:
            logger.error(f"FastPath failed: {e}")
            raise ServiceUnavailableException(
                "현재 검색이 불가능합니다. 잠시 후 다시 시도해주세요."
            )
```

### Step 2: Render 배포 설정

**파일**: `render.yaml`

```yaml
services:
  - type: web
    name: importback
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: |
      python -m alembic upgrade head && \
      gunicorn src.app:app -w 2 -b 0.0.0.0:10000
    
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: LOG_LEVEL
        value: INFO
      - key: FEATURES_SLOWPATH_ENABLED
        value: "false"
      - key: REDIS_URL
        fromDatabase: redis
      - key: DATABASE_URL
        fromDatabase: postgres
    
    disk:
      name: importback-disk
      mountPath: /data
      sizeGB: 1

databases:
  - name: postgres
    plan: free
  - name: redis
    plan: free
```

### Step 3: 환경 변수 설정

**Render 대시보드**:
```
Environment → Environment Variables 추가:

ENVIRONMENT = production
LOG_LEVEL = INFO
FEATURES_SLOWPATH_ENABLED = false
REDIS_URL = redis://...  (자동 생성)
DATABASE_URL = postgresql://...  (자동 생성)
```

### Step 4: 헬스 체크

**테스트**:
```bash
# 배포 후 30초 대기
sleep 30

# 헬스 체크
curl https://importback.onrender.com/api/v1/health

# 응답
{
  "status": "healthy",
  "dependencies": {
    "redis": "connected",
    "database": "connected",
    "playwright": "disabled"  # ← 중요
  }
}

# 기능 테스트
curl -X POST "https://importback.onrender.com/api/v1/price/search" \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "MacBook Pro 14",
    "current_price": 1990000
  }'

# 응답
{
  "status": "success",
  "data": {
    "lowest_price": 1899000,
    "is_cheaper": true,
    "source": "fastpath"
  }
}
```

---

## 📊 단계별 마일스톤

### Week 1: Phase 1 배포

```
Day 1-2:
  [ ] SlowPath 비활성화 코드 수정
  [ ] Render 설정 파일 생성
  [ ] 로컬 테스트 완료

Day 3:
  [ ] Git push
  [ ] Render 자동 배포
  [ ] 헬스 체크 확인

Day 4-5:
  [ ] 성능 모니터링 (응답 시간, 성공률)
  [ ] 사용자 피드백 수집

Day 6-7:
  [ ] IP 차단 여부 모니터링
  [ ] 로그 분석
```

**목표**:
- ✓ 서비스 정상 작동
- ✓ 응답 시간 1-3초 (FastPath)
- ✓ 성공률 60-70%

---

### Week 2-3: Phase 2 프록시 추가

```
Day 8-10:
  [ ] ProxyRotator 클래스 구현
  [ ] 테스트 완료
  [ ] Smartproxy 계정 생성

Day 11-14:
  [ ] 프록시 통합
  [ ] Render 환경 변수 업데이트
  [ ] 배포 & 모니터링

목표:
  - ✓ IP 차단 시 자동 우회
  - ✓ 성공률 60% → 80%+
```

---

### Week 4+: Phase 3 SlowPath

```
선택:

옵션 1 (빠름, 비쌈):
  [ ] Browserless.io API 통합
  [ ] SlowPath를 Browserless 호출로 변경
  [ ] 배포
  
  비용: +$50/월

옵션 2 (최적, 복잡함):
  [ ] AWS Lambda 함수 생성
  [ ] Playwright 패키징
  [ ] SlowPath를 Lambda 호출로 변경
  [ ] 배포

  비용: +$5-10/월
```

---

## 💰 비용 로드맵

### Phase 1 (현재 → 1주)
```
Render Free:   $0/월
Redis Free:    $0/월
PostgreSQL:    $0/월
프록시:        $0/월
─────────────────────
합계:          $0/월 ✅
```

**문제**: IP 차단 위험

### Phase 2 (1주 → 3주)
```
Render Free:   $0/월
프록시:        $25/월 (Smartproxy)
─────────────────────
합계:          $25/월

성공률: 60% → 80%+
```

**개선**: 대부분의 요청 처리 가능

### Phase 3-1 (3주 → 1개월, 빠른 배포)
```
Render Free:   $0/월
프록시:        $25/월
Browserless:   $50/월
─────────────────────
합계:          $75/월

성공률: 80% → 95%+
응답 속도: 1-3초 (FastPath) + 2-5초 (SlowPath)
```

### Phase 3-2 (1개월+, 최적화)
```
Render Free:   $0/월
프록시:        $25/월
AWS Lambda:    $10/월
─────────────────────
합계:          $35/월

성공률: 95%+
응답 속도: 1-3초 (FastPath) + 2-5초 (SlowPath, Lambda)
```

---

## ⚠️ 리스크 관리

### 리스크 1: IP 차단 (Week 2)

**시나리오**:
```
배포 후 3-7일: FastPath 성공률 급락 (0-20%)
원인: 다나와가 Render의 AWS IP 범위 차단

대응:
1. 프록시 서비스 즉시 활성화 (Phase 2 스킵)
2. 또는 IP 화이트리스트 요청 (다나와에 연락)
```

**모니터링**:
```python
# src/monitoring/metrics.py
class FailureRateMonitor:
    async def check_fastpath_health(self):
        failure_rate = await self.get_failure_rate(hours=1)
        
        if failure_rate > 0.5:  # 50% 이상 실패
            AlertService.critical(
                subject="FastPath 실패율 급상승",
                details=f"실패율: {failure_rate*100:.1f}%"
            )
```

### 리스크 2: 메모리 부족 (Week 1-2)

**모니터링**:
```bash
# Render 대시보드에서 확인
- Memory Usage
- CPU Usage
- Restart Count
```

**기준**:
- ✓ 메모리 < 400MB (512MB 중)
- ✓ CPU < 50%
- ✓ 재시작 없음

### 리스크 3: 정규화 오류 (진행 중)

**감시**:
```python
# 모든 검색 결과에 대해
if abs(lowest_price - current_price) > current_price * 0.7:
    logger.warning(
        f"Price mismatch: {lowest_price} vs {current_price} "
        f"(diff: {abs(lowest_price - current_price)})"
    )
```

---

## 📈 성공 기준

| 단계 | 지표 | 기준 | 상태 |
|------|------|------|------|
| Phase 1 | 성공률 | > 50% | ⚠️ |
| Phase 1 | 응답 시간 | < 5초 | ✓ |
| Phase 2 | 성공률 | > 80% | ⚠️ |
| Phase 2 | IP 차단 우회 | 작동 | ⚠️ |
| Phase 3 | 성공률 | > 95% | ⚠️ |
| Phase 3 | P95 응답 | < 8초 | ⚠️ |

---

**상태**: 🟡 Ready to Start

**다음 단계**: Phase 1 구현 (이번 주 시작)

**담당**: 개발팀 (1-2명, 1주 소요)
