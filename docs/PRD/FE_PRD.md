
# Frontend PRD (Product Requirements Document)

목표
- 사용자가 빠르게 다나와 상품의 최저가(Top3) 및 가격 추이를 확인할 수 있는 직관적이고 반응성 좋은 UI 제공

주요 사용자 흐름
1. 사용자가 검색창에 `URL`, `pcode`, 또는 `상품명`을 입력
2. 클라이언트가 `POST /api/v1/price/search`에 JSON으로 요청
3. 결과 표시: `ProductCard` → `TopPricesList` → `PriceTrendChart`
4. 쇼핑몰 항목 클릭 시 `link`로 새 탭 이동

컴포넌트 명세
- `SearchBar`
  - Props: `onSearch(payload: {product_name?, current_url?, product_code?, current_price?})`
  - UX: 입력값 자동 인식 및 유효성 검사(URL 형식, 숫자 등)
  - 키보드: 엔터 제출

- `ProductCard`
  - 표시: `product_name`, `pcode`, `lowest_price`, `price_diff`, `is_cheaper` 배지, `cached` 뱃지

- `TopPricesList`
  - 각 항목: `rank`, `mall`, `price`, `free_shipping`, `delivery`, `link`(오픈 새탭)
  - UI: 가격-쇼핑몰 행 클릭 시 `analytics` 트리거 후 `link` 이동

- `PriceTrendChart`
  - 입력: `price_trend: Array<{label, price}>`
  - 라이브러리 권장: `echarts` (일관성 유지) / `chart.js` 대안
  - 동작: 데이터가 없을 경우 "추이 데이터 없음" 메시지 표시, 새로고침 버튼 제공

데이터 매핑
- API `PriceSearchResponse.data` → UI
  - `product_name` → `ProductCard.title`
  - `lowest_price` → `ProductCard.price`
  - `top_prices` → `TopPricesList.items`
  - `is_cheaper`, `price_diff` → `ProductCard` 배지/보조 텍스트
  - `price_trend` → `PriceTrendChart.series` (빈 배열 처리)

상태 및 에러 처리
- 로딩: `skeleton`/스피너 표시
- 실패: 사용자 친화적 메시지(예: "상품을 찾을 수 없습니다.") 및 재시도 버튼
- 빈 추이: 별도 메시지 및 엔드포인트 재시도 버튼

UX/성능 권장사항
- 검색 버튼 클릭 시 이전 요청 취소(AbortController)
- 응답이 캐시인지 여부는 UI에서 보이지 않음; 로그/운영에서 모니터링
- 모바일 우선: 카드형 레이아웃
- 요청 실패 시 1회 자동 재시도(지수적 백오프)

보안/접근성
- 링크에 `rel="noopener noreferrer"` 적용
- aria-label, aria-live로 스크린리더 호환성 확보

개발/통합 세부사항
- 요청 예시
```
fetch('/api/v1/price/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ product_name: '삼성 로봇청소기' })
})
.then(r => r.json())
.then(render)
```

미구현/한계
- 가격 추이(`price_trend`)는 크롤러에서 확보되지 않을 수 있습니다(현재 선택적 필드). UI는 이를 정상 처리해야 합니다.

