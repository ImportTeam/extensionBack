# Fallback + Validation Gate - Level 2

## 핵심 원칙

> **Fallback은 "마지막 수단"**
> 
> · 여기서만 의미 축소 허용
> · 하지만 반드시 결과 검증 필수
> · 오매핑 가능성이 높으므로 Safety Gate 필수

---

## 전체 정규화 파이프라인

```
입력: "Apple 아이폰 17 Pro 자급제"
│
├─ Level 0: Hard Mapping (완전 매칭)
│   ├─ 정규화: "apple 아이폰 17 pro"
│   ├─ YAML key와 완전 매칭?
│   └─ ❌ 없음 → 다음 단계
│
├─ Level 1: Synonym (의미 확장만)
│   ├─ 후보 생성: ["apple 아이폰 17 pro", "아이폰 17 pro", "iphone 17"]
│   ├─ 각 후보로 다나와 검색 시도
│   └─ ✅ 성공하면 결과 반환
│
├─ Level 2: Fallback (의미 축소 허용 + 검증)
│   ├─ 브랜드 + 모델 추출
│   ├─ 카테고리별 후보 생성
│   ├─ 각 후보로 검색 시도
│   ├─ ⚠️ 결과 검증 Gate 통과?
│   │   ├─ ✅ 통과 → 결과 반환 (캐시)
│   │   └─ ❌ 실패 → 다음 후보
│   └─ 모든 후보 실패 → ProductNotFoundException
│
└─ (Playwright Fallback은 여기 이후, 별도)
```

---

## Level 2: Fallback 상세 설계

### 단계 1: 입력 분석

```python
def analyze_input(product_name: str) -> dict:
    """
    입력을 분석하여 구조 파악
    
    반환:
    {
        "brand": "Apple",
        "model": "아이폰 17",
        "variant": "Pro",
        "specs": {"color": "white", "storage": "256gb"},
        "category": "phone",
        "condition": "자급제"
    }
    """
```

**분석 규칙:**

```yaml
# 카테고리 감지
phone:
  keywords: ["아이폰", "iphone", "폰", "핸드폰"]
  brand_map:
    "apple": "iPhone"
    "samsung": "Galaxy"
    "lg": "LG Phone"

laptop:
  keywords: ["맥북", "노트북", "그램", "갤럭시북"]
  brand_map:
    "apple": "MacBook"
    "lg": "LG Gram"

audio:
  keywords: ["에어팟", "헤드폰", "이어폰", "스피커"]
  brand_map:
    "apple": "AirPods"
    "sony": "Sony"

food:
  keywords: ["라면", "라면", "컵라면", "스프"]
  brand_map:
    "농심": "Nongshim"
    "삼양": "Samyang"
```

### 단계 2: Fallback 후보 생성

**원칙:**

```
브랜드 + 모델 우선
→ 모델 축소 (변형 제거)
→ 브랜드만
→ 카테고리 기반 자동 생성
```

**예시:**

```python
input_text = "Apple 아이폰 17 Pro 자급제 화이트"

candidates = [
    # Tier 1: 원본 (Synonym에서 생성한 것들)
    "Apple 아이폰 17 Pro",           # 원본
    "아이폰 17 Pro",
    "iPhone 17 Pro",
    
    # Tier 2: 변형 제거 (Pro 제거)
    "Apple 아이폰 17",               # 모델만
    "아이폰 17",
    "iPhone 17",
    
    # Tier 3: 기본 모델 (세대도 제거)
    "Apple 아이폰",                  # 브랜드+카테고리
    "아이폰",
    "iPhone",
    
    # Tier 4: 카테고리 검색
    "스마트폰",
    "휴대폰",
]
```

### 단계 3: 각 후보로 검색

```python
async def search_with_candidates(
    candidates: list[str],
    crawler: DanawaCrawler,
    validation_gate: ValidationGate,
) -> Optional[dict]:
    """
    각 후보를 순회하며 검색 시도
    
    ✅ 성공 조건: 검색 결과 + 검증 통과
    """
    for candidate in candidates:
        try:
            # 다나와 검색 (HTTP + Playwright)
            result = await crawler.search_lowest_price(candidate)
            
            if not result:
                continue  # 검색 실패 → 다음 후보
            
            # ⚠️ 검증 Gate 통과?
            is_valid = validation_gate.validate(
                original_input=product_name,
                search_query=candidate,
                search_result=result
            )
            
            if is_valid:
                logger.info(f"✅ Fallback success with candidate: {candidate}")
                return result
            else:
                logger.warning(f"❌ Validation failed for candidate: {candidate}")
                continue
        
        except Exception as e:
            logger.debug(f"Search error for candidate '{candidate}': {e}")
            continue
    
    return None  # 모든 후보 실패
```

---

## Validation Gate (검증 안전장치)

### 핵심: "입력과 결과가 충분히 관련 있는가?"

```python
class ValidationGate:
    """Fallback 단계에서 검색 결과의 타당성 검증"""
    
    def validate(
        self,
        original_input: str,
        search_query: str,
        search_result: dict,
    ) -> bool:
        """
        세 가지 차원의 검증:
        1. 카테고리 일치도
        2. 키워드 겹침도
        3. 브랜드 일치도
        """
        
        # 검증 1: 카테고리 일치
        input_category = detect_category(original_input)
        result_category = detect_category(search_result["product_name"])
        
        if not self._categories_compatible(input_category, result_category):
            return False  # 너무 다른 카테고리 ❌
        
        # 검증 2: 키워드 겹침
        input_tokens = tokenize(original_input)
        result_tokens = tokenize(search_result["product_name"])
        
        overlap_ratio = len(set(input_tokens) & set(result_tokens)) / len(set(input_tokens) | set(result_tokens))
        
        if overlap_ratio < 0.3:  # 30% 이상 겹쳐야 함
            return False
        
        # 검증 3: 브랜드 일치
        input_brand = extract_brand(original_input)
        result_brand = extract_brand(search_result["product_name"])
        
        if input_brand and result_brand and input_brand != result_brand:
            return False  # 브랜드가 다르면 ❌
        
        return True  # ✅ 모든 검증 통과
    
    def _categories_compatible(self, cat1: str, cat2: str) -> bool:
        """카테고리 호환성 확인"""
        compatible_map = {
            "phone": ["phone", "smartphone"],
            "laptop": ["laptop", "notebook", "macbook"],
            "audio": ["audio", "earphone", "headphone"],
            "food": ["food", "ramyeon", "snack"],
        }
        return cat2 in compatible_map.get(cat1, [])
```

### 검증 케이스

| 입력 | 검색 쿼리 | 결과 | 검증 | 판정 |
|-----|---------|------|------|------|
| "Apple 아이폰 17" | "아이폰" | Apple 아이폰 15 | 카테고리 ✅, 브랜드 ✅, 키워드 85% | ✅ 통과 |
| "Apple 아이폰 17" | "아이폰" | Samsung 갤럭시 S24 | 카테고리 ✅, 브랜드 ❌ | ❌ 실패 |
| "맥북 에어" | "노트북" | LG 그램 16 | 카테고리 ✅, 브랜드 ❌, 키워드 0% | ❌ 실패 |
| "삼양 불닭" | "라면" | 농심 신라면 | 카테고리 ✅, 브랜드 ❌ | ❌ 실패 |

---

## 구현 파일 구조

```
src/utils/search/
├── fallback_helper.py (새 파일)
│   ├─ analyze_input()
│   ├─ generate_fallback_candidates()
│   └─ ValidationGate
│
└── search_optimizer.py (수정)
    ├─ 기존: generate_search_candidates()
    └─ 개선: generate_fallback_candidates() 추가
```

### fallback_helper.py (신규)

```python
from typing import Dict, List, Optional
from src.core.logging import logger

class FallbackHelper:
    """Fallback 단계 헬퍼"""
    
    CATEGORY_KEYWORDS = {
        "phone": {"아이폰", "갤럭시", "폰", "핸드폰", "iphone", "galaxy"},
        "laptop": {"맥북", "노트북", "그램", "갤럭시북", "노북"},
        "audio": {"에어팟", "이어폰", "헤드폰", "스피커", "airpods"},
        "food": {"라면", "컵라면", "스프", "라면"},
    }
    
    def analyze_input(self, text: str) -> Dict:
        """입력 구조 분석"""
        category = self.detect_category(text)
        brand = self.extract_brand(text)
        model = self.extract_model(text)
        
        return {
            "original": text,
            "category": category,
            "brand": brand,
            "model": model,
        }
    
    def generate_fallback_candidates(self, analysis: Dict) -> List[str]:
        """Fallback 후보 생성 (의미 축소 시작)"""
        candidates = []
        
        # Tier 1: 브랜드 + 모델 (일부 변형 제거)
        if analysis["brand"] and analysis["model"]:
            candidates.append(f"{analysis['brand']} {analysis['model']}")
        
        # Tier 2: 모델만
        if analysis["model"]:
            candidates.append(analysis["model"])
        
        # Tier 3: 브랜드만
        if analysis["brand"]:
            candidates.append(analysis["brand"])
        
        # Tier 4: 카테고리 기반
        category = analysis["category"]
        if category == "phone":
            candidates.extend(["스마트폰", "휴대폰"])
        elif category == "laptop":
            candidates.extend(["노트북", "컴퓨터"])
        elif category == "audio":
            candidates.extend(["이어폰", "오디오"])
        elif category == "food":
            candidates.extend(["라면", "음식"])
        
        return candidates
    
    def detect_category(self, text: str) -> Optional[str]:
        """카테고리 감지"""
        text_lower = text.lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return category
        return None


class ValidationGate:
    """검증 Gate"""
    
    def validate(
        self,
        original_input: str,
        search_result: Dict
    ) -> bool:
        """
        반환: True = 검증 통과, False = 거부
        """
        # 1. 카테고리 호환성
        input_cat = self._detect_category(original_input)
        result_cat = self._detect_category(search_result.get("product_name", ""))
        
        if not self._is_compatible_category(input_cat, result_cat):
            logger.debug(f"Category mismatch: {input_cat} vs {result_cat}")
            return False
        
        # 2. 키워드 겹침 (최소 30%)
        input_tokens = set(original_input.lower().split())
        result_tokens = set(search_result.get("product_name", "").lower().split())
        
        if not input_tokens or not result_tokens:
            return True  # 분석 불가능하면 허용
        
        overlap = len(input_tokens & result_tokens) / len(input_tokens | result_tokens)
        if overlap < 0.3:
            logger.debug(f"Keyword overlap too low: {overlap:.2%}")
            return False
        
        # 3. 결과의 신뢰도 (최저가가 있는가?)
        if not search_result.get("lowest_price"):
            return False
        
        logger.debug(f"Validation passed: overlap={overlap:.2%}")
        return True
    
    def _detect_category(self, text: str) -> Optional[str]:
        """카테고리 감지"""
        helper = FallbackHelper()
        analysis = helper.analyze_input(text)
        return analysis.get("category")
    
    def _is_compatible_category(self, cat1: str, cat2: str) -> bool:
        """카테고리 호환성"""
        compatible = {
            "phone": ["phone", "smartphone"],
            "laptop": ["laptop", "notebook"],
            "audio": ["audio", "earphone"],
            "food": ["food", "ramyeon"],
        }
        return cat2 in compatible.get(cat1, [])
```

---

## 테스트 케이스 (Fallback)

```python
class TestFallbackAndValidation:
    
    def test_fallback_candidate_generation(self):
        """Fallback 후보 생성"""
        helper = FallbackHelper()
        analysis = helper.analyze_input("Apple 아이폰 17 Pro 자급제")
        
        candidates = helper.generate_fallback_candidates(analysis)
        
        assert "Apple 아이폰" in candidates or "아이폰" in candidates
        assert len(candidates) > 0
    
    def test_validation_pass_same_brand(self):
        """검증 통과: 브랜드 일치"""
        gate = ValidationGate()
        
        result = {
            "product_name": "Apple 아이폰 15",
            "lowest_price": 500000,
        }
        
        is_valid = gate.validate("Apple 아이폰 17", result)
        assert is_valid is True  # ✅ 브랜드 같음
    
    def test_validation_fail_different_brand(self):
        """검증 실패: 브랜드 다름"""
        gate = ValidationGate()
        
        result = {
            "product_name": "Samsung 갤럭시 S24",
            "lowest_price": 500000,
        }
        
        is_valid = gate.validate("Apple 아이폰 17", result)
        assert is_valid is False  # ❌ 브랜드 다름
    
    def test_validation_fail_no_price(self):
        """검증 실패: 가격 없음"""
        gate = ValidationGate()
        
        result = {
            "product_name": "Apple 아이폰 15",
            "lowest_price": None,  # ❌ 가격 없음
        }
        
        is_valid = gate.validate("Apple 아이폰", result)
        assert is_valid is False
```

---

## 다음 단계

1. ✅ Hard Mapping 아키텍처 명시화
2. ✅ Synonym 규칙 설계
3. ✅ Fallback + 검증 Gate 설계
4. 📊 **최종 아키텍처 다이어그램** (마지막 문서)

