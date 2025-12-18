# 📊 현재 상품명 정규화 시스템 분석 & 개선 전략

## 1️⃣ 현재 시스템 아키텍처

```
FE (사용자 입력)
      ↓
product_name: String
      ↓
[BE API] /api/v1/price/search
      ↓
PriceSearchService.search_price()
      ↓
normalize_search_query(product_name)  ← ⭐ 여기서 정규화
      ↓
search_key = clean_product_name(normalized_name)  ← 캐시 키 생성
      ↓
DanawaCrawler.search_lowest_price(product_name)  ← 원본명 전달
      ↓
HTTP Fast Path / Playwright
      ↓
최저가 결과
```

---

## 2️⃣ 현재 정규화 파이프라인

### 파일 구조
```
src/utils/text/
├── __init__.py                          # 공개 API
├── core/
│   ├── cleaning.py                      # 기본 정제 (clean_product_name)
│   ├── tokenize.py                      # 토큰화
│
├── normalization/
│   ├── normalize.py                     # 메인 정규화 ⭐
│   ├── kiwi.py                          # 형태소 분석 (선택)
│   ├── resources.py                     # UPCS 기반 (deprecated)
│
├── matching/
│   ├── matching.py                      # 유사도 계산
│   ├── signals.py                       # 신호 추출
│   ├── similarity.py                    # 퍼지 매칭
│
└── utils/
    └── (가격 추출 등)
```

---

## 3️⃣ 정규화 프로세스 (상세)

### normalize_search_query() 호출 순서

```python
normalize_search_query(text)
    ↓
1️⃣ UPCS 기반 정규화 시도
    └─ normalize_query(text, vendor="danawa")
    
    ↓ (실패 시)
    
2️⃣ 레거시 휴리스틱 정규화 (_normalize_search_query_legacy)
    ↓
    [Step 1] IT/비IT 상품 분류
    └─ is_likely_it_query(text) → IT 신호 스코링
    
    ↓
    [Step 2] 마크업 제거
    └─ "VS 검색", "검색 도움말" 등 제거
    
    ↓
    [Step 3] 구분자 기준 분할 (·, •, |)
    └─ "제품명 · 스펙" → "제품명"만 추출
    
    ↓
    [Step 4] 기본 정제
    └─ clean_product_name()
       ├─ 괄호 내용 제거 (예: "(자급제)" → "")
       ├─ M칩 보존 (예: "M5" 추출 유지)
       └─ 특수문자 제거
    
    ↓
    [Step 5] 한글-영문 경계 공백 삽입
    └─ split_kr_en_boundary()
       └─ "BasicWhite" → "Basic White"
    
    ↓
    [Step 6] IT 상품 노이즈 제거 (IF is_it)
    ├─ 용량 제거: "256GB" → ""
    ├─ CPU 제거: "인텔 i5" → ""
    ├─ 메모리 제거: "DDR5" → ""
    ├─ OS 제거: "WIN11 Home" → ""
    ├─ 색상 제거: "화이트", "블랙" → ""
    ├─ 포트 정규화: "USB-C" → "C"
    └─ 액세서리 단어 제거: "케이스", "필름" → ""
    
    ↓
    [Step 7] 다중 공백 정리
    └─ 다중 공백 → 단일 공백
    
    ↓
    정규화된 검색어 반환
```

---

## 4️⃣ 현재 시스템의 문제점

### ❌ Problem 1: 모든 상품에 일률적 정규화
```
상황:
- IT 상품: "에어팟 프로 2세대" 정규화 ✅ 좋음
- 식품: "농심 신라면 블랙" → "신라면" (색상 제거 되서 오류)
- 패션: "나이키 검은색 러닝화" → "나이키" (너무 많이 제거)
```

### ❌ Problem 2: 하드 매핑 없음
```
사용자 입력: "맥북 에어 15"
다나와 검색 성공 확률: 70%

더 나은 결과:
사용자 입력 → "Apple 맥북 에어 15" 강제 변환
다나와 검색 성공 확률: 95%
```

### ❌ Problem 3: Fallback 전략 부재
```
현재:
1차 검색 실패 → 즉시 Playwright 전환

개선안:
1차 검색 실패 → 2차/3차 쿼리 자동 생성
  예: "에어팟" → "Apple 에어팟" → "에어팟 프로"
```

---

## 5️⃣ 90% 성공률 달성 전략

### 🎯 3단계 접근

```
1️⃣ 하드 매핑 (Hard Mapping) - 브랜드 통일
   ├─ "맥북" → "Apple 맥북"
   ├─ "갤럭시북" → "Samsung 갤럭시북"
   ├─ "그램" → "LG 그램"
   └─ 리소스: resources/hard_mapping.json
   
   목표 달성률: 60% → 75%

2️⃣ 동의어 치환 (Synonym Mapping)
   ├─ "에어팟프로" → "에어팟 프로"
   ├─ "갤북" → "갤럭시북"
   └─ 리소스: resources/mappings/synonyms.global.yaml
   
   목표 달성률: 75% → 85%

3️⃣ 다단계 Fallback 쿼리 생성
   ├─ 1차: 정규화된 전체 쿼리
   ├─ 2차: 브랜드 + 모델만
   ├─ 3차: 모델명만
   ├─ 4차: 동의어 변환
   └─ 리소스: src/utils/search/search_optimizer.py
   
   목표 달성률: 85% → 90%+
```

---

## 6️⃣ 현재 코드 위치 & 역할

### 핵심 파일 (개선 필요)

| 파일 | 역할 | 상태 |
|------|------|------|
| `normalize.py` | 메인 정규화 로직 | ⚠️ IT/비IT 분류에만 의존 |
| `clean_product_name()` | 기본 정제 | ✅ 기본 정상 |
| `DanawaSearchHelper.generate_search_candidates()` | Fallback 쿼리 생성 | 🔄 개선 필요 |
| `resources/hard_mapping.json` | 브랜드 강제 매핑 | ❌ 존재하지 않음 |
| `resources/mappings/synonyms.global.yaml` | 동의어 사전 | ❌ 사용 안 됨 |

---

## 7️⃣ 개선 구현 순서

### Phase 1: Hard Mapping 시스템 구축
```
목표: 60% → 75%
파일: resources/hard_mapping.json 생성

예시:
{
  "맥북": "Apple 맥북",
  "갤럭시북": "Samsung 갤럭시북",
  "그램": "LG 그램",
  "아이폰": "Apple 아이폰",
  "에어팟": "Apple 에어팟"
}

구현:
- normalize.py에 hard_mapping 로드 추가
- 정규화 1단계에서 hard_mapping 확인
```

### Phase 2: Synonym 치환 강화
```
목표: 75% → 85%
파일: 기존 synonyms.global.yaml 활용

구현:
- normalize.py에서 synonyms 로드 & 치환
- 토큰 단위로 동의어 자동 변환
```

### Phase 3: Fallback 쿼리 자동 생성
```
목표: 85% → 90%
파일: search_optimizer.py 개선

현재:
- 정규화된 쿼리
- 브랜드 + 모델
- 모델명
- 브랜드

개선:
- 정규화된 쿼리
- Hard Mapped 쿼리
- 동의어 변환 쿼리
- 브랜드 + 핵심 모델
- 최종 폴백 (모델/브랜드)
```

---

## 8️⃣ 성공 시나리오 예시

### 시나리오: "화이트케이스 Apple 에어팟 프로 2세대 블루투스 이어폰"

```
입력:
화이트케이스 Apple 에어팟 프로 2세대 블루투스 이어폰

1️⃣ Hard Mapping 확인
   없음 (이미 "에어팟"이 명시됨)

2️⃣ 정규화 (기존)
   → "Apple 에어팟 프로 2"

3️⃣ Fallback 쿼리 생성 (신규)
   쿼리 1: "Apple 에어팟 프로 2"
   쿼리 2: "에어팟 프로 2"
   쿼리 3: "Apple 에어팟"
   쿼리 4: "에어팟"

4️⃣ 다나와 검색 시도
   ✅ 쿼리 1에서 검색 성공!
```

---

## 9️⃣ 실제 구현 계획

### 파일 수정 대상

1. **normalize.py** (핵심)
   - Hard Mapping 로드 및 1차 적용
   - Synonym 치환 추가
   - 로깅 강화

2. **search_optimizer.py**
   - generate_search_candidates() 확장
   - 다단계 쿼리 생성 로직 개선

3. **resources/** 생성/수정
   - hard_mapping.json 생성
   - synonyms 활용 활성화

4. **테스트**
   - test_text_utils.py 확장
   - test_live_crawl_real.py에서 90% 달성 확인

---

## 🔟 마일스톤

| Phase | 구현 | 목표율 | 시간 |
|-------|------|--------|------|
| 1 | Hard Mapping | 75% | 2시간 |
| 2 | Synonym 강화 | 85% | 3시간 |
| 3 | Fallback 최적화 | 90%+ | 4시간 |
| 4 | 테스트 & 검증 | - | 2시간 |

---

## 💡 다음 스텝

1. `resources/hard_mapping.json` 생성 및 로드 로직 작성
2. `normalize.py` 개선 (hard_mapping + synonym 적용)
3. `search_optimizer.py` fallback 쿼리 확장
4. 통합 테스트 & 실시간 크롤링 성공률 검증

준비됐습니다! 👍
