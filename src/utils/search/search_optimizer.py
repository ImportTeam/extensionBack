"""다나와 검색 자동완성 활용한 스마트 정규화"""
import re
from typing import Optional
from src.core.logging import logger
from src.utils.resource_loader import load_search_substitutions, load_search_categories


class DanawaSearchHelper:
    """다나와 검색 최적화 헬퍼 - 다나와 자동완성과 계층적 폴백 검색 활용"""
    
    def __init__(self):
        # 리소스에서 카테고리 설정 로드
        categories = load_search_categories()
        
        # 카테고리별 핵심 토큰
        self.category_keywords = {
            cat: set(info.get("keywords", [])) 
            for cat, info in categories.items()
        }
        
        # 카테고리 감지 키워드
        self.category_patterns = {
            cat: info.get("pattern", "") 
            for cat, info in categories.items()
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
        """계층적 폴백 검색 후보 생성 (효율적)"""
        from src.utils.text import clean_product_name, normalize_search_query
        
        candidates = []
        seen = set()
        
        def add_candidate(cand: str):
            if cand and cand not in seen:
                seen.add(cand)
                candidates.append(cand)

        # 1. 정규화된 전체 (이미 충분히 정제됨)
        normalized = normalize_search_query(product_name)
        add_candidate(normalized)
        
        # 2. 브랜드 + 모델명 추출
        brand, model = self.extract_brand_and_model(product_name)
        if brand and model:
            # 모델에서 과도한 스펙 제거
            model_cleaned = re.sub(r'\s*\d+(\.\d+)?[GgTt][Bb]\s*', '', model)
            add_candidate(f"{brand} {model_cleaned}".strip())
        
        # 3. 모델명만 (처음 2-3개 단어)
        if model:
            model_tokens = model.split()[:3]
            if model_tokens:
                add_candidate(" ".join(model_tokens))
        
        # 4. 브랜드만
        if brand:
            add_candidate(brand)
        
        # 5. 대체 검색어
        substitutions = load_search_substitutions()
        product_lower = product_name.lower()
        for kr_term, en_terms in substitutions.items():
            if kr_term in product_name or kr_term.lower() in product_lower:
                for en in en_terms:
                    add_candidate(en)
        
        # 중복 제거 (순서 유지)
        return candidates if candidates else [clean_product_name(product_name)]
    
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
