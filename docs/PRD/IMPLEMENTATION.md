# Implementation Overview

요약
- 다나와(Danawa)에서 상품의 최저가(Top3 쇼핑몰)와 관련 메타데이터(무료배송 여부 포함)를 수집하고 제공하는 백엔드 서비스입니다.
- 입력 방식: `url` / `pcode` / `q`(상품명) 지원
- 주요 기술: FastAPI, Playwright, Redis(Upstash), PostgreSQL(선택)

Quick Start
- Playwright 설치: `playwright install chromium`
- 환경복사: `cp .env.example .env` → `.env`에 Redis/Postgres 설정

아키텍처 요약
- API: FastAPI 기반, 경로 접두사 `/api/v1` (상세 엔드포인트는 API_SPEC.md 참고)
- Crawler: `src/crawlers/danawa_crawler.py` — Playwright로 상품 페이지 로드 & DOM 파싱
- Cache: `src/services/cache_service.py` (Redis)
- DB 로그: `src/repositories/search_log_repository.py`

핵심 모듈
- `src/crawlers/danawa_crawler.py`
  - 검색 모드: `url`, `pcode`, `q(상품명)` 지원, 내부적으로 `extract_pcode_from_url()` 사용
  - 주요 셀렉터: `#lowPriceCompanyArea .box__mall-price .list__mall-price .list-item`
  - 반환: `product_name`, `pcode`, `lowest_price`, `top_prices`(Top3), `price_trend`(선택)
  - `price_trend` 추출: 현재 ECharts 및 전역 변수 접근 실패 가능성 존재 — 빈 배열로 처리

- `src/utils/url_utils.py`: 다나와 URL → `pcode` 변환기
- `src/schemas/price_schema.py`: Pydantic 응답 모델
- `src/services/price_search_service.py`: Cache-first 전략
- `src/api/price_routes.py`: 라우트 정의 및 파라미터 검증

캐시 정책
- 기본 TTL: 6시간(21600초)
- 캐시 키: `sha256` 기반 해시(`url|pcode|q` 조합)

환경 변수
- `UPSTASH_REDIS_URL` (rediss://) — 필수
- `DATABASE_URL` (선택) — 로그 저장용
- `PLAYWRIGHT_BROWSERS_PATH` — 로컬 Playwright 위치(환경에 따라 설정)

테스트
- 단위: `pytest tests/ -k unit` (42개 테스트)
- 통합(실브라우저): `LIVE_CRAWL=1 pytest tests/integration/test_live_crawl_real.py` (3개 테스트)

확장 및 개선 포인트
- 차트(가격 추이) 데이터 소스 식별(API 역공학 또는 ECharts 인스턴스 접근 개선)
- 브라우저 컨텍스트 재사용으로 동시성/속도 개선
- 실패 이벤트 및 지표 수집(모니터링)

