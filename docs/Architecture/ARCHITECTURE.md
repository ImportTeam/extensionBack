# Extension BE 아키텍쳐

## 전체 흐름도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        사용자 입력 (product_id)                              │
│                  "Apple 아이폰 17 Pro 자급제 화이트"                         │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                    ┌─────────────────▼─────────────────┐
                    │   PriceSearchService.search_price │
                    │                                   │
                    │ 1. normalize_search_query() 호출   │
                    │ 2. 정규화 결과로 캐시 키/검색 생성  │
                    │ 3. DanawaCrawler.search_lowest_    │
                    │    price(normalized_name)         │
                    └──────────┬────────┬────────────────┘
                               │        │
                ┌──────────────┘        └──────────────┐
                │ 캐시 확인              크롤링 준비    │
                ▼                                     ▼
    ┌──────────────────────┐                  (정규화 결과)
    │ Cache Layer          │          "apple 아이폰 17 pro"
    │ (Redis/DB)           │
    │ Key: hash된 캐시키   │
    └────────┬─────────────┘
             │ 미스
             ▼
    ┌────────────────────────────────────────────────────────┐
    │        🔴 Level 0: Hard Mapping                         │
    │        (완전 매칭 + 정규화된 완전 매칭)                 │
    │                                                         │
    │ normalize_search_query()                               │
    │   │                                                     │
    │   └─ apply_hard_mapping_complete()                     │
    │        │                                                │
    │        ├─ Stage 1: 액세서리 필터?                       │
    │        │  예: "케이스" 키워드 없음 → 진행                │
    │        │                                                │
    │        ├─ Stage 2: normalize_for_hard_mapping()        │
    │        │  입력: "Apple 아이폰 17 Pro 자급제"            │
    │        │  출력: "apple 아이폰 17 pro"                  │
    │        │                                                │
    │        ├─ Stage 3: 완전 매칭                            │
    │        │  YAML key == "apple 아이폰 17 pro"?           │
    │        │  ❌ 없음 (부분 포함은 불가!)                   │
    │        │                                                │
    │        └─ Stage 4,5: 검증 & 반환                        │
    │           ❌ 결과 없음 → 다음 레벨로                    │
    │                                                         │
    │ 결과: None                                              │
    └─────────────────┬────────────────────────────────────┘
                      │
                      ▼
    ┌────────────────────────────────────────────────────────┐
    │        🟡 Level 1: Synonym                              │
    │        (의미 확장만 - 축소는 금지)                      │
    │                                                         │
    │ 입력: "apple 아이폰 17 pro"                            │
    │                                                         │
    │ Synonym 규칙 적용:                                      │
    │ · 색상 제거: "화이트" → 제거                           │
    │ · 조건 제거: "자급제" → 제거                           │
    │ · 영문 변형 추가                                        │
    │ · 모델 축소는 아직 금지                                 │
    │                                                         │
    │ 생성 후보:                                              │
    │ [                                                       │
    │   "apple 아이폰 17 pro",  ← 원본 (색상 제거)           │
    │   "아이폰 17 pro",         ← 한글만                     │
    │   "iphone 17 pro",         ← 영문                      │
    │ ]                                                       │
    │                                                         │
    │ 각 후보로 다나와 검색 시도                              │
    │                                                         │
    │  성공 → 결과 반환 & 캐시                              │
    │ ❌ 모두 실패 → 다음 레벨로                             │
    └─────────────────┬────────────────────────────────────┘
                      │
                      ▼
    ┌────────────────────────────────────────────────────────┐
    │        🟢 Level 2: Fallback                             │
    │        (의미 축소 허용 + 검증 Gate)                    │
    │                                                         │
    │ 입력 분석:                                              │
    │ · 브랜드: "Apple"                                       │
    │ · 모델: "아이폰 17"                                     │
    │ · 카테고리: "phone"                                     │
    │                                                         │
    │ Fallback 후보 생성 (의미 축소 시작):                   │
    │ Tier 1: "apple 아이폰 17"      ← 변형 제거             │
    │ Tier 2: "apple 아이폰"         ← 모델 제거             │
    │ Tier 3: "apple"               ← 브랜드만               │
    │ Tier 4: "스마트폰", "휴대폰"   ← 카테고리               │
    │                                                         │
    │ 각 후보 순회:                                           │
    │ ┌─────────────────────────────────────┐                │
    │ │ for candidate in candidates:        │                │
    │ │   result = search(candidate)        │                │
    │ │   if not result: continue           │                │
    │ │                                     │                │
    │ │   ⚠️ Validation Gate 검사:          │                │
    │ │   · 카테고리 호환성?                 │                │
    │ │   · 키워드 겹침도 > 30%?            │                │
    │ │   · 브랜드 일치?                    │                │
    │ │                                     │                │
    │ │    통과 → 결과 반환 & 캐시         │                │
    │ │   ❌ 실패 → 다음 후보                │                │
    │ └─────────────────────────────────────┘                │
    │                                                         │
    │ 결과:  Apple 아이폰 15 (최저가 계산)                  │
    │ 또는: ❌ ProductNotFoundException                       │
    └────────────────────────────────────────────────────────┘
```

---

## 상세 데이터 흐름

### 시나리오 1: Hard Mapping 히트 

```
입력: "MACBOOK AIR 15"
  ↓
Level 0: Hard Mapping
  · normalize: "macbook air 15"
  · YAML key "macbook air 15" 존재
  ·  반환: "Apple 맥북 에어 15"
  ↓
⏱️ 시간: ~1ms
💾 캐시: 저장
📊 성공률: 100% (확실한 케이스)
```

### 시나리오 2: Synonym 히트 

```
입력: "Apple 아이폰 17 Pro 자급제"
  ↓
Level 0: Hard Mapping
  · "apple 아이폰 17 pro" ❌ YAML 없음
  ↓
Level 1: Synonym
  · 후보: ["apple 아이폰 17 pro", "아이폰 17 pro", "iphone 17 pro"]
  · 첫 후보 검색: "apple 아이폰 17 pro"
  ·  다나와 검색 결과: Apple 아이폰 17 가격 정보
  ↓
⏱️ 시간: ~2-3초 (웹 검색)
💾 캐시: 저장
📊 성공률: 90%+ (충분한 정보 제공)
```

### 시나리오 3: Fallback 히트 + 검증 

```
입력: "Apple 아이폰 17 Pro 자급제 화이트"
  ↓
Level 0: Hard Mapping ❌
  · "apple 아이폰 17 pro" 없음
  ↓
Level 1: Synonym ❌
  · 모든 후보 검색 실패
  ↓
Level 2: Fallback
  · 후보 생성: ["apple 아이폰 17", "apple 아이폰", "apple", "스마트폰"]
  
  · 후보 1: "apple 아이폰 17"
    검색 결과: Apple 아이폰 15 + 16 + 17
    검증:
      · 카테고리: phone == phone 
      · 키워드: 80% 겹침 
      · 브랜드: Apple == Apple 
    →  통과 → 결과 반환
  ↓
⏱️ 시간: ~3-4초
💾 캐시: 저장
📊 성공률: 75~85% (검증으로 오매핑 방지)
```

### 시나리오 4: 모든 단계 실패 ❌

```
입력: "화이트 × B182W13"  (랜덤 문자열)
  ↓
Level 0: Hard Mapping ❌
Level 1: Synonym ❌
Level 2: Fallback
  · 후보 생성: ["b182w13", "b182", "..."]
  · 모든 후보 검색 결과 또는 검증 실패
  ↓
🚫 ProductNotFoundException
  성공률: 0% (정보 부족)
```

---

## 성능 특성

| 단계 | 시간 | 성공률 | 확실성 | 비용 |
|-----|-----|------|--------|------|
| Level 0 (Hard Mapping) | ~1ms | 60-70% | 95%+ | 무료 |
| Level 1 (Synonym) | ~2-3s | 85-90% | 85%+ | 저 (HTTP) |
| Level 2 (Fallback) | ~3-4s | 75-85% | 70-75% | 중 (Playwright) |
| Level 3 (Playwright) | ~5-8s | 90%+ | 50-60% | 고 (무거움) |

### 목표 성능

```
전체 성공률: 90%+ (모든 단계 포함)
평균 응답 시간: < 4초
오매핑율: < 5%
```

---

## 구현 체크리스트

### Phase 1: Hard Mapping ( 완료)
- [x] `normalize_for_hard_mapping_match()` 정의
- [x] Hard Mapping YAML 로더 명시화
- [x] Stage 2,3 일관성 확보
- [x] 테스트: `test_hard_mapping.py`

### Phase 2: Synonym (📋 다음)
- [ ] `synonyms.yaml` 리소스 작성
- [ ] `src/utils/text/normalization/synonyms.py` 구현
- [ ] `normalize.py`에 Level 1 통합
- [ ] 테스트: `test_synonym.py`

### Phase 3: Fallback (📋 다음)
- [ ] `src/utils/search/fallback_helper.py` 구현
- [ ] `ValidationGate` 구현
- [ ] `normalize.py`에 Level 2 통합
- [ ] 테스트: `test_fallback.py`

### Phase 4: 모니터링 (📋 다음)
- [ ] 단계별 성공률 로깅
- [ ] 오매핑 감지 알람
- [ ] 대시보드 구성

---

## 의사결정 트리 (사용자 입력 → 최종 결과)

```
입력 수신
│
├─ Hard Mapping (Level 0)
│  ├─ 액세서리 필터? → YES ─→ 스킵 ─┐
│  ├─ 정규화 후 YAML 키 == 입력? → YES ─→ 반환 
│  └─ NO ──────────┐
│                  │
├─ Synonym (Level 1)
│  ├─ 의미 확장 후보 생성
│  ├─ 각 후보로 검색
│  ├─ 검색 성공? → YES ─→ 반환 
│  └─ 모두 실패 ──→ 다음
│
├─ Fallback (Level 2)
│  ├─ 입력 분석 (카테고리/브랜드/모델)
│  ├─ 축소된 후보 생성
│  ├─ 각 후보로 검색
│  ├─ 검증 Gate 통과? ──→ YES ─→ 반환 
│  └─ 모두 실패 ─┐
│               │
└─ Playwright (Fallback)
   ├─ 브라우저 자동화 검색
   ├─ 성공? ──→ YES ─→ 반환 
   └─ 실패? ──→ ProductNotFoundException ❌
```

---

## 다음 구현 순서 (권장)

1.  **Hard Mapping 아키텍처** - 완료
2. ⏳ **Synonym 단계** - 다음 (YAML + Python 구현)
3. ⏳ **Fallback 단계** - 그 다음 (검증 Gate)
4. ⏳ **통합 테스트** - 전체 파이프라인
5. ⏳ **모니터링 & 튜닝** - 실운영

---

## 마지막 체크: "프로덕션 정답 구조"

| 항목 | 달성 | 상태 |
|-----|------|------|
|  Hard Mapping 완전 매칭 | YES | 완료 |
|  정규화 기준 명시화 | YES | 완료 |
|  Synonym 확장 전용 원칙 | YES | 설계 |
|  Fallback + 검증 Gate | YES | 설계 |
|  오매핑 방지 안전장치 | YES | 설계 |
|  성능 특성 정의 | YES | 문서화 |
|  테스트 체계 | YES | 기초 |


