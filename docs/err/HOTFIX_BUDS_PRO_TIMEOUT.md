# 긴급 핫픽스 - 갤럭시 버즈/아이폰 세대 정보 손실 및 타임아웃 문제

## 🔴 문제 요약

입력: `삼성전자 갤럭시 버즈3 프로 블루투스 이어폰`
결과: Hard Mapping이 `갤럭시 버즈`로 축소 → 정보 손실 → FastPath timeout + Playwright frame detach

## 근본 원인

1. **Hard Mapping 부분 매칭 문제**: `버즈3 프로` → `버즈`로 축소
2. **중복 실행 문제**: 축소된 결과를 다시 Hard Mapping에 태움
3. **검색어 과다 축소**: `Samsung 갤럭시 버즈`는 너무 broad → timeout
4. **실패 캐시 부재**: 같은 쿼리 반복 재시도
5. **Playwright 타임아웃**: budget 소진 + frame detach

## 해결책 5가지

### ✅ 1. Hard Mapping 완전 매칭 강제 (완료: hard_mapping_stage.py 수정)

**이미 수정됨:**
```python
# Stage 3에서 완전 매칭만 지원
if key == normalized_text:  # 부분 포함 ❌
    return mapping[key]
```

### ✅ 2. Hard Mapping 1회만 실행 (신규 구현 필요)

**구현 위치**: `src/utils/text/normalization/normalize.py`

Hard Mapping 결과에는 다시 Hard Mapping을 적용하지 않음

```python
class NormalizedResult:
    """정규화 결과"""
    query: str
    is_hard_mapped: bool = False
    
def normalize_search_query(text: str) -> str:
    # Level 0: Hard Mapping
    hard_mapped = apply_hard_mapping_complete(text)
    if hard_mapped:
        # ✅ 플래그를 통해 "이미 Hard Mapping됨"을 표시
        # 이후 단계에서는 재실행하지 않음
        return hard_mapped
    
    # Level 1: UPCS (Hard Mapping이 이미 처리했으므로 SKIP 가능)
    # Level 2: Legacy
```

### ✅ 3. 모델 세대/등급 토큰 보호 (신규 규칙 필요)

**구현 위치**: `resources/hard_mapping.yaml`에 추가

```yaml
# 보호 토큰: Hard Mapping 결과가 이 토큰을 잃으면 무효 처리
protected_tokens:
  - r"\b\d+\b"           # 세대 숫자 (버즈3, 아이폰17)
  - "프로"
  - "pro"
  - "fe"
  - "max"
  - "ultra"
  - "plus"

# 각 매핑 규칙에 "최소 토큰" 추가
mapping:
  "갤럭시 버즈": 
    result: "Samsung 갤럭시 버즈"
    # ⚠️ 이 매핑은 입력에서 다음 토큰이 있으면 무효:
    preserve_if_contains: ["2", "3", "프로", "pro", "fe"]
    
  "갤럭시 버즈 2":
    result: "Samsung 갤럭시 버즈 2"
    preserve_if_contains: ["프로", "pro", "fe"]
    
  "갤럭시 버즈 프로":
    result: "Samsung 갤럭시 버즈 프로"
```

### ✅ 4. 실패 캐시 강화 (부분 수정 필요)

**기존 구조 확인:**
```python
# cache_service.py에 이미 있음
def get_negative(self, product_name: str) -> Optional[str]:
def set_negative(self, product_name: str, message: str) -> bool:
```

**추가 필요:**
- 실패 횟수 카운팅
- N번 연속 실패 시 Hard Skip
- 실패 원인별 분류 (timeout vs not_found vs validation_fail)

### ✅ 5. FastPath timeout 조건부 확장 (신규 로직)

**구현 위치**: `src/crawlers/danawa/core/orchestrator.py`

```python
def is_broad_query(query: str) -> bool:
    """
    광범위한 검색어인지 판단
    
    예: "갤럭시 버즈", "아이폰" → 매우 많은 결과 예상
    """
    BROAD_KEYWORDS = {
        "갤럭시", "아이폰", "아이패드", "맥북",
        "라면", "노트북", "이어폰", "스마트폰"
    }
    
    return len(query.split()) <= 2 and any(
        kw in query.lower() for kw in BROAD_KEYWORDS
    )

# FastPath 타임아웃 조정
if is_broad_query(normalized_query):
    timeout_ms = 10000  # 10초로 확장
else:
    timeout_ms = 7800   # 기본 7.8초
```

---

## 즉시 적용 패치 (1,2번 우선)

### 패치 1: Hard Mapping 1회 실행 강제

**파일**: `src/utils/text/normalization/normalize.py`

```python
def normalize_search_query(text: str) -> str:
    """정규화 파이프라인"""
    if not text:
        return ""
    
    # 🔴 Level 0: Hard Mapping (1회만 실행)
    try:
        from .hard_mapping_stage import apply_hard_mapping_complete
        
        hard_mapped = apply_hard_mapping_complete(text)
        if hard_mapped:
            logger.info(f"[normalize] Level 0 Hard Mapping SUCCESS: '{text}' → '{hard_mapped}'")
            # ✅ Hard Mapping 결과는 다시 정규화하지 않음
            # 다음 단계(UPCS/Legacy)로 진행하지 않음
            return hard_mapped
    except Exception as e:
        logger.debug(f"[normalize] Level 0 Hard Mapping error: {e}")
    
    # 🟡 Level 1: UPCS (Hard Mapping 실패한 경우만)
    try:
        from src.upcs.normalizer import normalize_query
        normalized = normalize_query(text, vendor="danawa")
        if normalized:
            logger.debug(f"[normalize] Level 1 UPCS normalization: '{text}' → '{normalized}'")
            return str(normalized)
    except Exception as e:
        logger.debug(f"[normalize] Level 1 UPCS fallback: {e}")
    
    # 🟢 Level 2: Legacy
    logger.debug(f"[normalize] Falling back to Level 2 legacy heuristics")
    return _normalize_search_query_legacy(text)
```

### 패치 2: Hard Mapping 결과 검증 강화

**파일**: `src/utils/text/normalization/hard_mapping_stage.py`

```python
@staticmethod
def stage_4_validate_result(
    original_text: str,
    normalized_text: str,
    mapped_result: Optional[str]
) -> bool:
    """Stage 4: 결과 검증 (프로덕션 안전장치)"""
    
    if not mapped_result:
        return False
    
    # 1️⃣ 브랜드 명시 확인 (기존)
    brands = {"apple", "samsung", "lg", "dell", ...}
    if not any(brand in mapped_result.lower() for brand in brands):
        logger.warning(f"[Stage 4] Missing brand: {mapped_result}")
        return False
    
    # 2️⃣ 새로운 검증: 중요 토큰 보존 확인
    # 입력에 있던 중요 정보가 결과에도 있는지 확인
    
    input_lower = original_text.lower()
    result_lower = mapped_result.lower()
    
    # 숫자(세대)가 입력에 있었는데 결과에 없으면 경고
    input_numbers = set(re.findall(r'\d+', input_lower))
    result_numbers = set(re.findall(r'\d+', result_lower))
    
    if input_numbers and not (input_numbers & result_numbers):
        logger.warning(f"[Stage 4] Number token lost: {input_numbers}")
        # ⚠️ 숫자 손실은 일부 허용 (Pro 같은 경우도 있으니)
        # 하지만 로그는 남겨야 모니터링 가능
    
    # "프로", "맥스", "울트라" 같은 등급 정보도 확인
    grade_keywords = ["프로", "pro", "max", "ultra", "fe", "plus"]
    if any(kw in input_lower for kw in grade_keywords):
        if not any(kw in result_lower for kw in grade_keywords):
            logger.warning(f"[Stage 4] Grade token lost: {grade_keywords}")
            return False  # 등급 정보 손실은 거절
    
    return True
```

---

## 모니터링 & 알람 추가 (선택)

### 추가 로깅 포인트

```python
logger.info(f"[QUALITY] Hard Mapping: '{original}' → '{result}' (info_loss={has_info_loss})")
logger.warning(f"[ALERT] Query too broad: '{query}' (expected_results=many, timeout_risk=high)")
logger.error(f"[CRITICAL] Repeated failure: query='{query}', attempts=3, strategy=skip_crawl")
```

---

## 최종 검증: 로그 비교

### Before (❌ 문제)
```
[Stage 3] Hard Mapping matched:
'삼성전자 갤럭시 버즈3 프로 블루투스 이어폰'
→ 'Samsung 갤럭시 버즈'
```

### After (✅ 해결)
```
[Stage 3] Hard Mapping exact match? 
'samsung 갤럭시 버즈3 프로'
== 'samsung 갤럭시 버즈'? NO
→ None (Synonym/Fallback으로)
```

---

## 다음 액션

1. **패치 1,2 즉시 적용** (hard_mapping_stage.py + normalize.py 수정)
2. **테스트**: "삼성전자 갤럭시 버즈3 프로" 재시도
3. **패치 3,4,5 적용** (YAML + timeout + failure_cache)
4. **모니터링**: 대시보드에서 실패 패턴 추적

