# 배포 및 운영 가이드

**목적**: 개발 환경에서 프로덕션까지 안전하게 배포하고 운영하는 방법
**작성일**: 2025-12-19
**대상**: DevOps 엔지니어, 백엔드 개발자

---

## 목차
1. [사전 준비](#사전-준비)
2. [개발 환경 설정](#개발-환경-설정)
3. [테스트 및 검증](#테스트-및-검증)
4. [프로덕션 배포](#프로덕션-배포)
5. [모니터링 및 로깅](#모니터링-및-로깅)
6. [장애 대응](#장애-대응)
7. [성능 튜닝](#성능-튜닝)

---

## 사전 준비

### 시스템 요구사항

```
OS: Linux (Ubuntu 20.04 LTS) 또는 macOS
CPU: 4 코어 이상
메모리: 8GB 이상
디스크: 50GB 이상 (데이터베이스, 캐시)
```

### 필수 소프트웨어

```bash
# 1. Python 3.11+
python --version
# Python 3.11.0

# 2. Node.js 18+
node --version
# v18.0.0

# 3. Docker & Docker Compose
docker --version
# Docker version 24.0.0

# 4. PostgreSQL 15+
psql --version
# psql (PostgreSQL) 15.0

# 5. Redis 7+
redis-cli --version
# redis-cli 7.0.0
```

### 계정 및 권한

```bash
# importback 사용자 생성
sudo useradd -m -s /bin/bash importback
sudo usermod -aG docker importback

# 디렉토리 권한 설정
sudo chown -R importback:importback /opt/importback
chmod 755 /opt/importback
```

---

## 개발 환경 설정

### 1단계: 저장소 클론

```bash
cd /opt
git clone https://github.com/yourorg/importback.git
cd importback
git checkout main
```

### 2단계: Python 환경 설정

```bash
# 가상 환경 생성
python -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 개발 의존성 설치
pip install pytest pytest-cov pytest-asyncio mypy black flake8
```

### 3단계: Node.js 환경 설정

```bash
# 의존성 설치
npm install
# 또는 pnpm
pnpm install

# 타입 체크 도구 설치 확인
npm run type-check
```

### 4단계: 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# 내용 수정
cat > .env << 'EOF'
ENVIRONMENT=development
LOG_LEVEL=DEBUG
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://importback:password@localhost:5432/importback_dev
CRAWLER_TIMEOUT=12000
CRAWLER_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CRAWLER_MAX_RETRIES=3
CRAWLER_PLAYWRIGHT_WARMUP=false
EOF
```

### 5단계: 데이터베이스 초기화

```bash
# PostgreSQL 서비스 시작
docker run -d \
  --name importback-postgres \
  -e POSTGRES_USER=importback \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=importback_dev \
  -p 5432:5432 \
  postgres:15

# 마이그레이션 실행
python -m alembic upgrade head

# 확인
psql -U importback -h localhost -d importback_dev -c "\dt"
```

### 6단계: Redis 초기화

```bash
# Redis 서비스 시작
docker run -d \
  --name importback-redis \
  -p 6379:6379 \
  redis:7 redis-server --appendonly yes

# 확인
redis-cli ping
# PONG
```

### 7단계: 로컬 서버 실행

```bash
# uvicorn으로 실행
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000

# 또는 gunicorn으로 실행
gunicorn src.app:app -w 4 -b 0.0.0.0:8000 --reload
```

**확인**:
```bash
# 다른 터미널에서
curl http://localhost:8000/api/v1/health
```

---

## 테스트 및 검증

### 타입 검사

```bash
# MyPy 실행 (strict 모드)
mypy src/

# 결과: Success: no issues found in 70 source files
```

### 단위 테스트

```bash
# 모든 테스트 실행
pytest tests/unit -v

# 커버리지 포함
pytest tests/unit --cov=src --cov-report=html

# 특정 테스트만 실행
pytest tests/unit/test_business_logic.py -v -k "test_name_plus_price_search"
```

### 통합 테스트

```bash
# 통합 테스트 실행 (실제 다나와 호출)
pytest tests/integration -v

# 경고: 실제 네트워크 요청이 발생합니다
```

### 성능 테스트

```bash
# 벤치마크 실행
pytest tests/performance -v --benchmark-only

# 결과 분석
# FastPath 평균: 234ms
# SlowPath 평균: 3.5s
# Cache 평균: 45ms
```

### 코드 스타일 검사

```bash
# Black 포맷팅 (자동)
black src/ tests/

# Flake8 린팅
flake8 src/ tests/

# isort 임포트 정렬
isort src/ tests/
```

---

## 프로덕션 배포

### 배포 전 체크리스트

- [ ] 모든 테스트 통과
- [ ] MyPy 타입 체크 통과
- [ ] 코드 리뷰 완료
- [ ] 환경 변수 설정 완료
- [ ] 데이터베이스 마이그레이션 테스트
- [ ] 보안 감사 완료
- [ ] 성능 테스트 완료

### 배포 프로세스 (Blue-Green)

```bash
# 1단계: 새 버전 빌드
docker build -t importback:v1.0.0 .

# 2단계: 레지스트리에 푸시
docker tag importback:v1.0.0 registry.example.com/importback:v1.0.0
docker push registry.example.com/importback:v1.0.0

# 3단계: Green 환경 시작 (새 버전)
docker-compose -f docker-compose.prod.yml up -d importback-green

# 4단계: 헬스 체크
sleep 10
curl http://localhost:8001/api/v1/health

# 5단계: 응답 확인 후 트래픽 전환
# nginx.conf 수정: upstream server를 green으로 변경
# nginx 리로드

# 6단계: Blue 환경 중지 (구 버전)
docker-compose -f docker-compose.prod.yml stop importback-blue
```

### Docker Compose 설정 예

**docker-compose.prod.yml**:
```yaml
version: '3.9'

services:
  # PostgreSQL
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis
  redis:
    image: redis:7
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # importBack App (Green)
  importback-green:
    image: registry.example.com/importback:latest
    environment:
      ENVIRONMENT: production
      LOG_LEVEL: INFO
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
    ports:
      - "8001:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # importBack App (Blue)
  importback-blue:
    image: registry.example.com/importback:previous
    environment:
      ENVIRONMENT: production
      LOG_LEVEL: INFO
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Nginx (로드 밸런서/프록시)
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - importback-blue
      - importback-green
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Nginx 설정 예

**nginx.conf**:
```nginx
http {
  upstream importback_backend {
    server importback-blue:8000 max_fails=3 fail_timeout=30s;
    # server importback-green:8000 max_fails=3 fail_timeout=30s;
  }

  server {
    listen 80;
    server_name api.importback.com;

    location / {
      proxy_pass http://importback_backend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      
      # 타임아웃 설정
      proxy_connect_timeout 5s;
      proxy_send_timeout 12s;
      proxy_read_timeout 12s;
    }

    # 헬스 체크 엔드포인트
    location /health {
      access_log off;
      proxy_pass http://importback_backend/api/v1/health;
    }
  }
}
```

---

## 모니터링 및 로깅

### 로깅 설정

**src/core/logging.py**:
```python
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s"
        },
        "json": {
            "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "json",
            "filename": "/var/log/importback/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
        },
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file"],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### 주요 로그 포인트

```
1. API 요청 도착
   [2025-12-19 10:30:00] INFO [api.routes:45] POST /api/v1/price/search from 192.168.1.1

2. 캐시 조회
   [2025-12-19 10:30:00] DEBUG [cache:120] Cache hit for key: a3f2e1d4...

3. 검색 시작
   [2025-12-19 10:30:00] INFO [orchestrator:200] Starting search for "아이패드 프로 11"

4. FastPath 성공
   [2025-12-19 10:30:00] INFO [fastpath:450] Found price 1299000 in 234ms

5. 응답 반환
   [2025-12-19 10:30:00] INFO [api.routes:60] Response: 200 OK (234ms)
```

### 메트릭 수집

```bash
# Prometheus 메트릭 예
importback_searches_total{status="success"} 5234
importback_searches_total{status="error"} 344
importback_response_time_seconds{path="/price/search", le="0.5"} 3600
importback_cache_hits_total 3760
importback_cache_misses_total 1474
```

### Grafana 대시보드

주요 시각화:
1. **실시간 응답 시간**: 평균, P50, P95, P99
2. **캐시 히트율**: 시간별 추세
3. **에러율**: 에러 타입별 분포
4. **리소스 사용량**: CPU, 메모리, 디스크
5. **데이터베이스 상태**: 연결 수, 쿼리 성능

---

## 장애 대응

### 시나리오 1: Redis 다운

**증상**:
- 응답 시간 증가 (캐시 없음)
- 에러 로그에 "CacheConnectionException"

**대응**:
```bash
# 1. Redis 상태 확인
redis-cli ping

# 2. Redis 재시작
docker restart importback-redis

# 3. 캐시 초기화
redis-cli FLUSHALL

# 4. 서비스 재시작 (선택)
docker restart importback-blue
```

**예상 영향**:
- 캐시 히트율: 100% → 0%
- 평균 응답 시간: 500ms → 3000ms
- 서비스는 정상 작동 (캐시 없이)

### 시나리오 2: 다나와 봇 차단

**증상**:
- 에러 로그에 "BlockedException" 급증
- 응답: HTTP 429 Too Many Requests

**대응**:
```bash
# 1. 요청 속도 감소 (nginx 설정 변경)
# 동시 연결 제한 설정

# 2. User-Agent 로테이션
# config에서 여러 User-Agent 설정

# 3. 재시도 간격 증가
# exponential backoff 적용

# 4. IP 로테이션 (프록시 사용)
# 필요시 프록시 풀 설정
```

**예상 영향**:
- SlowPath 사용 증가
- 응답 시간 증가
- 성공률 감소 (임시)

### 시나리오 3: 데이터베이스 다운

**증상**:
- 에러 로그에 "DatabaseConnectionException"
- 로그 저장 실패

**대응**:
```bash
# 1. PostgreSQL 상태 확인
pg_isready -h localhost -p 5432

# 2. PostgreSQL 재시작
docker restart importback-postgres

# 3. 데이터베이스 복구
psql -U importback -d importback -f /backup/latest.sql

# 4. 마이그레이션 재실행
python -m alembic upgrade head
```

**예상 영향**:
- 검색 기능: 정상 (로그 없이)
- 분석 데이터: 손실 (일부)
- API 응답: 정상

### 시나리오 4: 브라우저 크래시

**증상**:
- SlowPath 에러: "BrowserException"
- Playwright 프로세스 없음

**대응**:
```bash
# 1. 프로세스 상태 확인
ps aux | grep chromium

# 2. 남은 프로세스 정리
pkill -f chromium

# 3. 서비스 재시작
docker restart importback-blue

# 4. 브라우저 설치 확인
python -m playwright install
```

**예상 영향**:
- SlowPath 불가
- FastPath만 사용
- 봇 차단 시 서비스 불가

---

## 성능 튜닝

### 1. Redis 최적화

```
# redis.conf
# 메모리 최적화
maxmemory 1gb
maxmemory-policy allkeys-lru

# 느린 쿼리 로깅
slowlog-log-slower-than 10000
slowlog-max-len 128

# 지속성
appendonly yes
appendfsync everysec
```

### 2. PostgreSQL 최적화

```sql
-- 커넥션 풀 크기
-- pgBouncer 또는 PgPool 사용
-- max_connections = 100
-- 적절한 풀 크기: 4 ~ 8 (CPU 코어)

-- 인덱스 추가
CREATE INDEX idx_search_failures_created_at ON search_failures(created_at DESC);
CREATE INDEX idx_cache_entries_expires_at ON cache_entries(expires_at);

-- 분석 쿼리 최적화
ANALYZE;
VACUUM;
```

### 3. 애플리케이션 튜닝

```python
# Gunicorn 워커 수
# 권장값: (CPU 코어 수 * 2) + 1
workers = 9  # 4 코어 시스템

# 타임아웃
timeout = 30  # 30초

# 최대 요청 수
max_requests = 1000
max_requests_jitter = 50
```

### 4. 네트워크 최적화

```bash
# TCP 튜닝
sysctl -w net.core.somaxconn=1024
sysctl -w net.ipv4.tcp_max_syn_backlog=2048

# 연결 재사용
net.ipv4.tcp_tw_reuse=1
net.ipv4.tcp_fin_timeout=30
```

---

## 재해 복구

### 백업 전략

```bash
# 1. 일일 데이터베이스 백업 (자동)
0 2 * * * /opt/importback/scripts/backup-db.sh

# 2. 일일 Redis 백업 (자동)
0 3 * * * /opt/importback/scripts/backup-redis.sh

# 3. 백업 검증
/opt/importback/scripts/verify-backups.sh

# 4. 백업 저장소 설정 (S3)
aws s3 sync /backups/importback s3://importback-backups/
```

### 복구 절차

```bash
# 1. 백업 목록 확인
aws s3 ls s3://importback-backups/

# 2. 백업 다운로드
aws s3 cp s3://importback-backups/db-2025-12-19.sql .

# 3. 데이터베이스 복구
dropdb importback_prod
createdb importback_prod
psql importback_prod < db-2025-12-19.sql

# 4. 서비스 재시작
docker restart importback-blue

# 5. 검증
curl http://localhost:8000/api/v1/health
```

---

**마지막 업데이트**: 2025-12-19
**상태**: Production Ready ✓
