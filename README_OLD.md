# 🔍 최저가 탐지 서비스

Cache-First 전략의 프로덕션 레벨 최저가 검색 API

## 🚀 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt
playwright install chromium

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일 편집

# 3. 개발 서버 실행
python main.py

# 또는
./scripts/dev.sh
```

API 문서: http://localhost:8000/docs

## 📦 프로젝트 구조

```
.
├── main.py              # 진입점 (index.ts 스타일)
├── src/
│   ├── app.py           # App Factory
│   ├── api/             # API Routes
│   ├── core/            # Config, DB, Logging
│   ├── services/        # Business Logic
│   ├── repositories/    # Data Access
│   ├── crawlers/        # Web Scraping
│   ├── schemas/         # Pydantic Models
│   └── utils/           # Utilities
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml       # 프로젝트 설정 (pip install -e .)
└── scripts/             # 유틸리티 스크립트
```

## 🧪 테스트

```bash
# 전체 테스트
pytest

# 커버리지 포함
pytest --cov=src --cov-report=html

# 또는 스크립트 사용
./scripts/test.sh
```

## 🔍 타입 체크

```bash
# mypy 설치 (처음만)
pip install -e ".[dev]"

# 타입 체크
mypy src

# 또는 스크립트 사용
./scripts/typecheck.sh
```

## 📡 API

### 최저가 검색

```http
POST /api/v1/price/search
Content-Type: application/json

{
  "product_name": "맥북",
  "current_price": 2900000
}
```

**응답:**
```json
{
  "status": "success",
  "data": {
    "is_cheaper": true,
    "price_diff": -188040,
    "lowest_price": 2711960,
    "link": "https://prod.danawa.com/info/?pcode=70250585"
  },
  "message": "캐시에서 발견했습니다."
}
```

### 통계

```http
GET /api/v1/stats
```

### 헬스 체크

```http
GET /health
```

## 🐳 Docker

```bash
# 빌드
docker build -t price-detector .

# 실행
docker run -p 10000:10000 --env-file .env price-detector
```

## 🌐 배포 (Render)

1. GitHub에 푸시
2. Render 대시보드에서 New Web Service
3. 환경 변수 설정:
   - `DATABASE_URL`
   - `REDIS_URL`
   - `CACHE_TTL=21600`

## 🏗️ 개발

### App Factory 패턴

```python
# src/app.py - App 생성
def create_app() -> FastAPI:
    app = FastAPI(...)
    app.include_router(...)
    return app

# main.py - 진입점 (index.ts 스타일)
from src.app import create_app
app = create_app()
```

### 의존성 관리

```bash
# 설치
pip install -e .

# 개발 의존성 포함
pip install -e ".[dev]"
```

## 📝 라이선스

MIT
