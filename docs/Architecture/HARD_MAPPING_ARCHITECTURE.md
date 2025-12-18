# Hard Mapping 아키텍처

## 핵심 원칙

> **Hard Mapping = 완전 매칭 (완전 정규화 후)**
>
> 완전 정규화란: **Hard Mapping 전용 정규화 함수를 통과한 결과 문자열**

---

## 구조도

```
┌─────────────────────────────────────────────────────────┐
│ 입력: 사용자 product_id (원문)                             │
│ 예: "MacBook Air 15", "MACBOOK AIR 15", "맥북 에어 15"   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ normalize_for_hard_mapping │  ◀─ 전용 정규화
        │ (hard_mapping_utils.py)    │     · 소문자
        │                            │     · 공백 정리
        │                            │     · KR-EN 경계 공백
        │                            │     · 특수문자 제거
        └────────────┬───────────────┘
                     │
                     ▼ "macbook air 15"
        ┌────────────────────────────┐
        │ load_hard_mapping() 로드   │
        │ (hard_mapping_loader.py)   │  ◀─ YAML 키도 같은 함수로
        │                            │     정규화되어 저장됨
        └────────────┬───────────────┘
                     │
                     ▼ mapping 검사
        ┌────────────────────────────┐
        │ Stage 3: 완전 매칭          │
        │ if key == normalized_text: │  ◀─ 부분 포함 ❌
        │    return mapping[key]     │     완전 일치만 
        └────────────┬───────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
    매칭됨                  ❌ 매칭 실패
        │                         │
        ▼                         ▼
   Stage 4,5             Synonym 단계로
   (검증 & 반환)          (다음 레벨)
```

---

## 구현 상세

### 1️⃣ Hard Mapping 전용 정규화 함수

**파일**: `src/utils/text/normalization/hard_mapping_utils.py`

```python
def normalize_for_hard_mapping_match(text: str) -> str:
    """Hard Mapping 매칭용 정규화.
    
    이 함수는 YAML 로드, Stage 2, Stage 3 전 모두에서
    동일하게 적용되어야 한다.
    
    이를 통해 "완전 매칭"의 기준이 명확해진다.
    """
    if not text:
        return ""
    
    # 1️ 소문자
    normalized = text.lower()
    
    # 2️ 공백 정규화
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # 3️ 한글-영문 경계 공백
    normalized = re.sub(r'(?<=[\uAC00-\uD7A3])(?=[A-Za-z])', ' ', normalized)
    normalized = re.sub(r'(?<=[A-Za-z])(?=[\uAC00-\uD7A3])', ' ', normalized)
    
    # 4️ 특수문자 제거 (하이픈, 언더스코어 보존)
    normalized = re.sub(r'[^\w\s\-_가-힣]', '', normalized)
    
    # 5️ 공백 재정리
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized
```

### 2️⃣ YAML 로더 - 키 정규화

**파일**: `src/utils/text/normalization/hard_mapping_loader.py`

```python
def load_hard_mapping() -> Dict[str, str]:
    """YAML 로드 시 키를 Hard Mapping 전용 정규화로 변환."""
    
    raw_mapping = yaml.safe_load(f)["mapping"]
    
    #  각 키를 normalize_for_hard_mapping_match()로 정규화
    normalized_mapping = {}
    for raw_key, value in raw_mapping.items():
        norm_key = normalize_for_hard_mapping_match(raw_key)
        if norm_key:
            normalized_mapping[norm_key] = value
    
    return normalized_mapping
```

### 3️ Hard Mapping Stage 2 - 일관된 정규화

**파일**: `src/utils/text/normalization/hard_mapping_stage.py`

```python
@staticmethod
def stage_2_normalize_for_matching(text: str) -> str:
    """Stage 2: 정규화.
    
     normalize_for_hard_mapping_match()를 호출
    (YAML 로더와 동일한 함수 사용)
    """
    normalized = normalize_for_hard_mapping_match(text)
    logger.debug(f"[Stage 2] Normalized: '{text}' → '{normalized}'")
    return normalized
```

### 4️ Hard Mapping Stage 3 - 완전 매칭

**파일**: `src/utils/text/normalization/hard_mapping_stage.py`

```python
@staticmethod
def stage_3_apply_hard_mapping(normalized_text: str) -> Optional[str]:
    """Stage 3: 완전 매칭만.
    
     normalized_text는 이미 Stage 2에서
       normalize_for_hard_mapping_match()로 정규화됨
    
     mapping의 키도 같은 함수로 정규화되어 저장됨
    
     따라서 키 == normalized_text 비교는 안전함
    """
    mapping = load_hard_mapping()  # 키가 이미 정규화됨
    sorted_keys = get_sorted_mapping_keys()
    
    for key in sorted_keys:
        if key == normalized_text:  # 완전 매칭만
            return mapping[key]
    
    return None
```

---

## 핵심 보장사항

| 조건 | 동작 | 결과 |
|------|------|------|
| 입력: `"MacBook Air 15"` | normalize → `"macbook air 15"` |  YAML key와 매칭 |
| 입력: `"MACBOOK AIR 15"` | normalize → `"macbook air 15"` |  YAML key와 매칭 |
| 입력: `"맥북 에어 15"` | normalize → `"macbook air 15"` |  YAML key와 매칭 |
| 입력: `"apple 아이폰 17 pro"` | normalize → `"apple 아이폰 17 pro"` | ❌ YAML에 없음 |
| 입력: `"아이폰"` + `"apple 아이폰 15"` | Stage 3에서 부분 포함 시도 | ❌ 완전 매칭만 허용 |

---

## 완성 체크리스트

- [x] `normalize_for_hard_mapping_match()` 함수 정의
- [x] YAML 로더에서 키 정규화 적용
- [x] Stage 2에서 공용 정규화 함수 호출
- [x] Stage 3에서 완전 매칭만 실행
- [ ] **Synonym 단계 설계** (다음)
- [ ] **Fallback + 검증 Gate** (다음)
- [ ] **최종 아키텍처 다이어그램** (다음)

---

## 문제 시나리오 재검증

### 문제 1: "Apple 아이폰 17 Pro" → "Apple 아이폰 Air" (오매핑)

**수정 전:**
```
입력: "apple 아이폰 17 pro"
→ Stage 3: "아이폰" 키가 부분 포함되므로 매칭
→ ❌ 반환: "Apple 아이폰"
```

**수정 후:**
```
입력: "apple 아이폰 17 pro"
→ 정규화: "apple 아이폰 17 pro"
→ Stage 3: "apple 아이폰 17 pro" == YAML key? 아니오
→  반환: None (Synonym 단계로)
```

### 문제 2: "화이트 × B182W13" → "LG 냉장고 B182DS13"

**수정 전:**
```
입력이 Hard Mapping에 규칙으로 있었나? (분석 필요)
```

**수정 후:**
```
입력: "화이트 × b182w13"
→ 정규화: "화이트 b182w13"
→ Stage 3: YAML key에 없음
→  반환: None
```
