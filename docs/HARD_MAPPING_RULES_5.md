# Hard Mapping 보완 규칙 5가지 (필수 구현사항)

## 개요

다음 5가지 규칙은 **프로덕션에서 터질 수 있는 포인트**를 사전에 방지하기 위한 필수 사항입니다.

---

## 📋 Rule 1: Longest Match First (가장 긴 키 우선)

### 문제
```python
# ❌ 잘못된 순서
mapping = {
    "맥북": "Apple 맥북",           # ← 먼저 매칭되면 오류!
    "맥북 에어": "Apple 맥북 에어",
    "맥북 에어 15": "Apple 맥북 에어 15"
}

input = "맥북 에어 15"
# 결과: "Apple 맥북" (❌ 잘못된 결과)
```

### 해결
```python
# ✅ 올바른 순서 (길이 내림차순)
keys = sorted(mapping.keys(), key=len, reverse=True)
# ["맥북 에어 15", "맥북 에어", "맥북"]

input = "맥북 에어 15"
# 결과: "Apple 맥북 에어 15" (✅ 정확)
```

### 구현
```python
def apply_hard_mapping(text: str, mapping: dict) -> str:
    # Step 1: 길이 내림차순 정렬
    sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
    
    # Step 2: 첫 매칭에서 반환
    for key in sorted_keys:
        if key in text:
            return mapping[key]
    
    return text  # 매칭 실패
```

---

## 🔤 Rule 2: Case/Space Normalization 후 매칭

### 문제
```python
mapping = {
    "macbook": "Apple 맥북"
}

# 사용자 입력
input1 = "MacBook"  # ❌ 대문자
input2 = "MAC  BOOK"  # ❌ 공백 다중
input3 = "MAC BOOK"  # ❌ 공백

# 결과: 모두 매칭 실패 ❌
```

### 해결
```python
def normalize_for_matching(text: str) -> str:
    """Hard Mapping 전 입력 정규화"""
    # 1. 소문자화
    text = text.lower()
    
    # 2. 다중 공백 → 단일 공백
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 3. 한글-영문 경계 공백 정규화
    text = re.sub(r'(?<=[\uAC00-\uD7A3])(?=[A-Za-z])', ' ', text)
    text = re.sub(r'(?<=[A-Za-z])(?=[\uAC00-\uD7A3])', ' ', text)
    
    # 4. 특수문자 제거 (하이픈, 언더스코어만 보존)
    text = re.sub(r'[^\w\s\-_가-힣]', '', text)
    
    return text

# 사용자 원문은 보존
original = input  # "MacBook"

# 정규화본으로 매칭
normalized = normalize_for_matching(original)  # "macbook"
matched = apply_hard_mapping(normalized, mapping)  # "Apple 맥북"

# 원문 유지하면서 결과는 매칭값
result = matched  # "Apple 맥북"
```

### 구현 위치
```
normalize.py의 normalize_search_query() 첫 부분:

def normalize_search_query(text: str) -> str:
    # 1️⃣ 정규화 (Case/Space)
    normalized = normalize_for_matching(text)
    
    # 2️⃣ Hard Mapping 적용 (Level 0) ← 여기!
    hard_mapped = apply_hard_mapping(normalized, hard_mapping_dict)
    if hard_mapped != normalized:
        return hard_mapped
    
    # 3️⃣ 이후 단계들...
```

---

## 🎯 Rule 3: Hard Mapping = normalize의 "0단계" (Execution Order)

### PRD 명시
```
Hard Mapping은:

1. 모든 정규화 로직보다 먼저 실행되며
2. 매칭 성공 시 즉시 반환한다
3. 다른 단계(Synonym, Fallback)를 건너뛴다

실행 순서:
├─ 0️⃣ Hard Mapping (즉시 반환)
├─ 1️⃣ Synonym (Hard Mapping 실패 시)
├─ 2️⃣ IT/비IT 노이즈 제거
├─ 3️⃣ 구분자 제거
└─ 4️⃣ 최종 정규화
```

### 코드
```python
def normalize_search_query(text: str) -> str:
    if not text:
        return ""
    
    # ⭐ Level 0: Hard Mapping (최우선)
    hard_mapped = apply_hard_mapping(text)
    if hard_mapped != text:
        logger.info(f"Level 0 Hard Mapping: '{text}' → '{hard_mapped}'")
        return hard_mapped
    
    # 이후 나머지 단계...
```

---

## 🛡️ Rule 4: 액세서리 필터 (안전장치)

### 문제
```python
# Hard Mapping에
mapping = {
    "아이폰 15": "Apple 아이폰 15"
}

# 사용자 입력
input = "아이폰 15 케이스"

# ❌ 케이스 상품인데 아이폰으로 매핑됨!
result = "Apple 아이폰 15"
```

### 해결
```python
ACCESSORY_KEYWORDS = {
    "케이스", "커버", "필름", "보호필름",
    "거치대", "스탠드", "파우치", "가방",
    "번들", "세트", "구성", "포함", "충전기",
    "어댑터", "케이블", "허브"
}

def should_skip_hard_mapping(text: str) -> bool:
    """액세서리 키워드 감지 시 Hard Mapping 스킵"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in ACCESSORY_KEYWORDS)

def apply_hard_mapping_safe(text: str) -> str:
    # 1️⃣ 액세서리 체크
    if should_skip_hard_mapping(text):
        logger.debug(f"Skipping Hard Mapping: accessory detected in '{text}'")
        return text  # Hard Mapping 스킵, 다음 단계로
    
    # 2️⃣ 안전하면 Hard Mapping 적용
    return apply_hard_mapping(text)
```

### 테스트
```python
# ✅ Hard Mapping 적용
"아이폰 15" → "Apple 아이폰 15"

# ❌ Hard Mapping 스킵 (액세서리)
"아이폰 15 케이스" → Hard Mapping 스킵
→ Synonym 단계로 이동
→ 최종: "아이폰 15" 또는 fallback
```

---

## ⚖️ Rule 5: 95% 이상 확실한 것만 매핑

### 원칙
```
Hard Mapping에 들어갈 기준:

이 매핑이 틀릴 가능성이 5% 이하인가?

YES → Hard Mapping에 포함 ✅
NO  → Synonym 또는 Fallback으로 이동 ❌
```

### 예시

#### ✅ Hard Mapping에 포함 (99% 확실)
```yaml
"맥북": "Apple 맥북"              # 99%: 맥북 = Apple 제품
"그램": "LG 그램"                # 99%: 그램 = LG 제품
"갤럭시북": "Samsung 갤럭시북"   # 99%: 갤럭시북 = Samsung
```

#### ❌ Hard Mapping 제외 (50% 이하 확실)
```yaml
# 이런 건 쓸 수 없다:
"버즈": ???  # 버즈 = Samsung? Beats? 불명확 ❌
"아이폰 15": ???  # 색상/용량 정보 포함 시 모호 ❌
"컴퓨터": ???  # 너무 범용 ❌

# → 대신 Synonym이나 Fallback에서 처리
```

### 체크리스트 (매핑 추가 시마다)
```python
def validate_hard_mapping_entry(key: str, value: str) -> bool:
    """Hard Mapping 항목 검증"""
    
    # 1. 브랜드 명시 여부
    if not has_brand(value):
        logger.warning(f"Missing brand: {key} → {value}")
        return False
    
    # 2. 모호성 검사
    if is_ambiguous(key):
        logger.warning(f"Ambiguous key: {key}")
        return False
    
    # 3. 액세서리 감지
    if contains_accessory(key):
        logger.warning(f"Accessory detected: {key}")
        return False
    
    return True
```

---

## 📊 최종 체크리스트

Hard Mapping 구현 시 확인사항:

- [ ] YAML 파일 로드 (keys 길이 내림차순 정렬)
- [ ] Case/Space Normalization 적용
- [ ] Hard Mapping = normalize_search_query 첫 단계
- [ ] 액세서리 필터 구현
- [ ] 95% 이상 확실한 항목만 매핑
- [ ] 로깅 (각 단계 Level별)
- [ ] 단위 테스트 (test_hard_mapping.py)
- [ ] 통합 테스트 (test_live_crawl_real.py)
- [ ] 모니터링 (크롤링 성공률 대시보드)

---

## 🎯 구현 순서

1. **hard_mapping.yaml 로드** (resources/)
2. **normalize.py 수정** (5가지 규칙 적용)
3. **테스트 작성** (test_hard_mapping.py)
4. **모니터링** (성공률 확인)

이제 **다음 선택지** 중 하나를 고르세요:

1️⃣ **normalize.py에 Hard Mapping 코드 적용**
2️⃣ **Hard Mapping/Synonym/Fallback 우선순위 다이어그램 (시각화)**
3️⃣ **Hard Mapping 실패 사례 & 금지 케이스 정의**
