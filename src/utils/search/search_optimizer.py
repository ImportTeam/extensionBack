"""다나와 검색 자동완성 활용한 스마트 정규화"""
import re
from typing import Optional
from src.core.logging import logger


class DanawaSearchHelper:
    """다나와 검색 최적화 헬퍼 - 다나와 자동완성과 계층적 폴백 검색 활용"""
    
    def __init__(self):
        # 카테고리별 핵심 토큰 (자동완성에서 자주 보이는 패턴)
        self.category_keywords = {
            "earphone": {"이어폰", "에어팟", "버즈", "이어버드", "헤드폰"},
            "laptop": {"노트북", "랩탑", "맥북", "그램", "갤럭시북"},
            "monitor": {"모니터", "디스플레이", "패널"},
            "phone": {"폰", "아이폰", "갤럭시", "핸드폰"},
            "tablet": {"태블릿", "아이패드"},
        }
        
        # 카테고리 감지 키워드
        self.category_patterns = {
            "earphone": r"(이어폰|에어팟|버즈|이어버드|헤드폰|AirPods)",
            "laptop": r"(노트북|랩탑|맥북|그램|갤럭시북|북)",
            "monitor": r"(모니터|디스플레이|패널)",
            "phone": r"(폰|아이폰|갤럭시|핸드폰|스마트폰)",
            "tablet": r"(태블릿|아이패드|패드)",
        }
    
    def detect_category(self, product_name: str) -> Optional[str]:
        """상품 카테고리 감지"""
        for category, pattern in self.category_patterns.items():
            if re.search(pattern, product_name, re.IGNORECASE):
                return category
        return None
    
    def extract_brand_and_model(self, product_name: str) -> tuple[str, str]:
        """브랜드와 모델명 추출"""
        from src.utils.text import clean_product_name, split_kr_en_boundary
        
        cleaned = clean_product_name(product_name)
        normalized = split_kr_en_boundary(cleaned)
        tokens = normalized.split()
        
        if len(tokens) == 0:
            return "", ""
        
        # 첫 번째 토큰 = 브랜드 (Apple, Samsung, LG 등)
        brand = tokens[0]
        
        # 2~3번째 토큰 = 모델명 (에어팟, 갤럭시버즈 등)
        model = " ".join(tokens[1:4]) if len(tokens) > 1 else ""
        
        return brand, model
    
    def generate_search_candidates(self, product_name: str) -> list[str]:
        """계층적 폴백 검색 후보 생성 (효율적)
        
        순서대로 시도하면 대부분 처음 2-3개 내에서 검색 성공:
        1. 정규화된 전체 검색어
        2. 브랜드 + 모델 (핵심만)
        3. 모델명만
        4. 브랜드만
        5. 대체 검색어 (예: "맥북" → "MacBook", "Apple laptop" 등)
        """
        from src.utils.text import clean_product_name, normalize_search_query
        
        candidates = []
        product_lower = (product_name or "").lower()
        
        # 1. 정규화된 전체 (이미 충분히 정제됨)
        normalized = normalize_search_query(product_name)
        if normalized:
            candidates.append(normalized)
        
        # 2. 브랜드 + 모델명 추출
        brand, model = self.extract_brand_and_model(product_name)
        if brand and model:
            # 모델에서 과도한 스펙 제거
            model_cleaned = re.sub(r'\s*\d+(\.\d+)?[GgTt][Bb]\s*', '', model)
            candidates.append(f"{brand} {model_cleaned}".strip())
        
        # 3. 모델명만 (처음 2-3개 단어)
        if model:
            model_tokens = model.split()[:3]
            if model_tokens:
                candidates.append(" ".join(model_tokens))
        
        # 4. 브랜드만
        if brand:
            candidates.append(brand)
        
        # 5. 대체 검색어 (특정 키워드 최소 변형)
        # NOTE: 이 로직은 '검색 후보 생성'에 한정합니다(정규화 SRP와 분리).
        substitutions: dict[str, list[str]] = {
            "맥북": ["MacBook", "MacBook Air", "Mac"],
            "아이폰": ["iPhone"],
            "아이패드": ["iPad"],
            "에어팟": ["AirPods"],
            "애플워치": ["Apple Watch"],
            "갤럭시": ["Galaxy"],
        }
        for kr_term, en_terms in substitutions.items():
            if kr_term in product_name or kr_term.lower() in product_lower:
                candidates.extend(en_terms)
        
        # 중복 제거 (순서 유지)
        deduped = []
        seen = set()
        for c in candidates:
            c = c.strip()
            if c and c not in seen:
                seen.add(c)
                deduped.append(c)
        
        return deduped if deduped else [clean_product_name(product_name)]
    
    def get_smart_search_query(self, product_name: str) -> str:
        """가장 효율적인 검색어 반환 (우선순위: 정규화 → 브랜드+모델 → 모델)"""
        from src.utils.text import normalize_search_query
        
        # 카테고리 감지
        category = self.detect_category(product_name)
        logger.debug(f"Detected category: {category}")
        
        # 정규화된 검색어 사용 (이미 충분함)
        normalized = normalize_search_query(product_name)
        if normalized and len(normalized.split()) >= 2:
            return normalized
        
        # Fallback: 브랜드 + 모델
        brand, model = self.extract_brand_and_model(product_name)
        if brand and model:
            return f"{brand} {model.split()[0] if model.split() else ''}".strip()
        
        # 최후의 수단: 원본
        return product_name
