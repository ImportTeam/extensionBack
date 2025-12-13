# 최저가 탐지 서비스 Backend

FastAPI + Playwright 기반 다나와 최저가 크롤링 서비스

## 🚀 빠른 시작

### 1. Playwright 설치

```bash
playwright install chromium
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 Redis, PostgreSQL URL 설정
```

### 3. 서버 실행

```bash
python main.py
```

서버: `http://0.0.0.0:8000`

## 🧪 테스트 실행

```bash
pytest tests/ -v
```

**결과**: ✅ 35개 테스트 전부 통과

## 📁 프로젝트 구조

```
src/
├── app.py                  # FastAPI 앱 팩토리
├── api/                    # API 라우터
├── core/                   # 핵심 설정 (config, database, exceptions)
├── services/               # 비즈니스 로직 (cache, price_search)
├── repositories/           # 데이터 액세스 레이어
├── crawlers/               # 다나와 크롤러 (2단계: 검색 → 상품 페이지)
├── schemas/                # Pydantic 모델
└── utils/                  # 유틸리티 함수

main.py                     # 진입점 (12줄)
```

## 🎯 주요 기능

1. **Cache-First 전략**: Redis 6시간 TTL
2. **2단계 크롤링**: 다나와 검색 → 상품 상세 페이지
3. **검색 로그**: PostgreSQL 저장 + 통계 API

## 📡 API

### POST /api/v1/price/search

```json
{
  "product_name": "아이폰 15",
  "current_price": 150000
}
```

### GET /health

Redis + PostgreSQL 상태 체크

## 🛠️ 기술 스택

- FastAPI 0.109.0
- Playwright 1.41.0 (Headless Chromium)
- Redis (Upstash) + PostgreSQL (Neon)
- pytest + mypy

## 📊 코드 품질

- **커버리지**: 65% (API 90%+, Utils 90%+)
- **타입 안전**: 전체 코드 타입 힌트
- **테스트**: 35개 (Unit + Integration)
- **아키텍처**: App Factory Pattern, SRP 준수
# extensionBack
