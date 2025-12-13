# 🔍 최저가 탐지 서비스 (Production Ready)

Cache-First 전략을 사용한 프로덕션 레벨 최저가 검색 백엔드 서비스입니다.

## ✨ 주요 특징

- **Clean Architecture**: SRP 원칙 준수, 계층별 책임 분리
- **Test Coverage**: 유닛/통합 테스트 포함 (pytest)
- **Type Safety**: Pydantic을 통한 강력한 타입 검증
- **Async First**: FastAPI + Playwright 비동기 처리
- **Production Ready**: 로깅, 에러 핸들링, 헬스 체크

## 📋 기술 스택

- **Language**: Python 3.10+
- **Framework**: FastAPI (비동기 처리)
- **Crawling**: Playwright (Headless Browser)
- **Database**: PostgreSQL (Neon) - 로그 저장
- **Cache**: Redis (Upstash) - 6시간 TTL
- **Deploy**: Render (Docker)
- **Testing**: pytest, pytest-asyncio, pytest-cov

## 📂 프로젝트 구조

```
importBack/
├── src/                          # 소스 코드
│   ├── api/                      # API 엔드포인트
│   │   ├── health_routes.py      # 헬스 체크
│   │   └── price_routes.py       # 가격 검색
│   ├── core/                     # 핵심 설정
│   │   ├── config.py             # 환경 설정
│   │   ├── database.py           # DB 연결
│   │   ├── exceptions.py         # 커스텀 예외
│   │   └── logging.py            # 로깅 설정
│   ├── services/                 # 비즈니스 로직
│   │   ├── cache_service.py      # Redis 캐싱
│   │   └── price_search_service.py  # 가격 검색
│   ├── repositories/             # 데이터 액세스
│   │   ├── models.py             # DB 모델
│   │   └── search_log_repository.py  # 로그 저장
│   ├── crawlers/                 # 웹 크롤러
│   │   └── danawa_crawler.py     # 다나와 크롤러
│   ├── schemas/                  # Pydantic 스키마
│   │   └── price_schema.py       # API 스키마
│   └── utils/                    # 유틸리티
│       ├── text_utils.py         # 텍스트 처리
│       └── hash_utils.py         # 해싱
├── tests/                        # 테스트 코드
│   ├── unit/                     # 유닛 테스트
│   │   ├── test_text_utils.py
│   │   ├── test_hash_utils.py
│   │   └── test_cache_service.py
│   └── integration/              # 통합 테스트
│       └── test_api.py
├── main.py                       # FastAPI 앱
├── requirements.txt              # 의존성
├── pytest.ini                    # pytest 설정
├── Dockerfile                    # Docker 이미지
├── Procfile                      # Render 배포
└── README.md                     # 문서

```

## 🚀 시작하기

### 1. 환경 변수 설정

```bash
cp .env.example .env
```

**`.env` 파일 내용:**
```env
DATABASE_URL=postgresql://user:password@your-neon-host/dbname
REDIS_URL=rediss://default:password@your-upstash-host:port
CACHE_TTL=21600
CRAWLER_TIMEOUT=30000
LOG_LEVEL=INFO
```

### 2. 의존성 설치

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

### 3. 로컬 실행

```bash
# 개발 서버 실행
uvicorn main:app --reload --port 8000

# 또는
python main.py
```

서버: http://localhost:8000  
API 문서: http://localhost:8000/docs

## 🧪 테스트

### 전체 테스트 실행

```bash
# 모든 테스트 실행 + 커버리지
pytest

# 커버리지 리포트
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### 특정 테스트 실행

```bash
# 유닛 테스트만
pytest tests/unit/

# 통합 테스트만
pytest tests/integration/

# 특정 파일
pytest tests/unit/test_text_utils.py

# 특정 테스트 케이스
pytest tests/unit/test_text_utils.py::TestCleanProductName::test_remove_brackets
```

### 테스트 커버리지 목표

- 유닛 테스트: 80% 이상
- 통합 테스트: 주요 API 엔드포인트 전체

## 📡 API 명세

### 1. 헬스 체크

```http
GET /health
```

**응답:**
```json
{
  "status": "ok",
  "timestamp": "2024-12-11T10:00:00",
  "version": "1.0.0"
}
```

### 2. 최저가 검색

```http
POST /api/v1/price/search
Content-Type: application/json
```

**요청:**
```json
{
  "product_name": "아이폰 15 프로 128GB",
  "current_price": 1350000,
  "current_url": "https://coupang.com/..."
}
```

**응답 (성공):**
```json
{
  "status": "success",
  "data": {
    "is_cheaper": true,
    "price_diff": -100000,
    "lowest_price": 1250000,
    "link": "http://danawa.com/product/..."
  },
  "message": "캐시에서 발견했습니다."
}
```

### 3. 통계

```http
GET /api/v1/stats
```

**응답:**
```json
{
  "total_searches": 1523,
  "cache_hits": 1024,
  "hit_rate": 67.23,
  "popular_queries": [
    {"name": "아이폰 15 프로", "count": 45},
    {"name": "삼성 갤럭시 S24", "count": 38}
  ]
}
```

## 🏗️ 아키텍처 원칙

### SRP (Single Responsibility Principle)

각 모듈은 단일 책임만 가집니다:

- **CacheService**: Redis 캐싱만 담당
- **DanawaCrawler**: 웹 스크래핑만 담당
- **PriceSearchService**: 비즈니스 로직 조율
- **SearchLogRepository**: DB 접근만 담당
- **API Routes**: HTTP 요청/응답 처리만

### 계층 구조

```
API Layer (FastAPI Routes)
    ↓
Service Layer (Business Logic)
    ↓
Repository Layer (Data Access)
    ↓
External Services (Redis, Playwright, PostgreSQL)
```

### 의존성 주입

FastAPI의 Dependency Injection을 활용:

```python
def get_price_service(
    cache_service: CacheService = Depends(get_cache_service)
) -> PriceSearchService:
    return PriceSearchService(cache_service)
```

## 🐳 Docker

### 로컬 빌드 및 실행

```bash
# 이미지 빌드
docker build -t price-detector .

# 컨테이너 실행
docker run -p 10000:10000 \
  -e DATABASE_URL="postgresql://..." \
  -e REDIS_URL="rediss://..." \
  price-detector
```

### Docker Compose (선택사항)

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "10000:10000"
    env_file:
      - .env
```

## 🌐 Render 배포

### 1. GitHub 연동

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main
```

### 2. Render 설정

**Environment**: Docker

**환경 변수:**
```
DATABASE_URL=postgresql://...
REDIS_URL=rediss://...
CACHE_TTL=21600
CRAWLER_TIMEOUT=30000
LOG_LEVEL=INFO
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

### 3. 배포

Render 대시보드에서 **Deploy** 클릭

## 📊 모니터링 및 로깅

### 로그 레벨

- `DEBUG`: 상세한 디버깅 정보
- `INFO`: 일반 정보 (기본값)
- `WARNING`: 경고
- `ERROR`: 오류

### 로그 확인

```bash
# 로컬
tail -f logs/app.log

# Docker
docker logs -f <container_id>

# Render
Render 대시보드 > Logs 탭
```

## 🛠️ 트러블슈팅

### Playwright 브라우저 오류

```bash
playwright install --with-deps chromium
```

### Redis 연결 오류

`.env` 파일의 `REDIS_URL` 확인:
```
rediss://default:password@host:port
```

### PostgreSQL 연결 오류

Neon 연결 문자열에 `sslmode=require` 추가:
```
postgresql://user:pass@host/db?sslmode=require
```

### 테스트 실패

```bash
# 캐시 정리
pytest --cache-clear

# 상세 출력
pytest -vv -s
```

## 📈 성능 최적화

### 캐시 전략

- **TTL**: 6시간 (상품 가격 변동 주기 고려)
- **캐시 키**: MD5 해싱으로 충돌 방지
- **캐시 히트율**: 70% 이상 목표

### 크롤러 최적화

- **Rate Limiting**: 0.5~1.5초 랜덤 딜레이
- **Timeout**: 30초
- **상위 3개 상품만 파싱**: 응답 속도 개선

### 데이터베이스

- **인덱스**: `query_name`, `status`, `created_at`
- **연결 풀**: 5개 연결, 최대 10개

## 📝 개발 가이드

### 새 기능 추가

1. `src/` 하위에 모듈 생성
2. 테스트 코드 작성 (`tests/unit/`, `tests/integration/`)
3. 테스트 실행 및 커버리지 확인
4. 코드 리뷰 후 병합

### 코드 스타일

- **Linting**: `flake8`, `black`
- **Type Hints**: 모든 함수에 타입 힌트 작성
- **Docstring**: 모든 public 함수에 docstring

### 커밋 컨벤션

```
feat: 새로운 기능
fix: 버그 수정
test: 테스트 추가/수정
refactor: 리팩토링
docs: 문서 수정
```

## 🤝 기여

이슈 및 PR을 환영합니다!

1. Fork
2. Feature 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 테스트 작성 및 실행
4. 커밋 (`git commit -m 'feat: Add amazing feature'`)
5. Push (`git push origin feature/amazing-feature`)
6. Pull Request 생성

## 📄 라이선스

MIT License

## 📞 문의

프로젝트 관련 문의는 이슈를 생성해주세요.
