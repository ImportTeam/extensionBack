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
        """브랜드와 모델명 추출 (연도 등 노이즈 건너뛰기)"""
        from src.utils.text_utils import clean_product_name, split_kr_en_boundary
        
        cleaned = clean_product_name(product_name)
        normalized = split_kr_en_boundary(cleaned)
        tokens = normalized.split()
        
        if len(tokens) == 0:
            return "", ""
        
        # 첫 번째 토큰 = 브랜드 (Apple, Samsung, LG 등)
        brand = tokens[0]
        
        # 연도 토큰 건너뛰기 (예: Apple 2025 맥북 -> brand=Apple, model_start=맥북)
        start_idx = 1
        if len(tokens) > 1 and re.match(r"^(19|20)\d{2}$", tokens[1]):
            start_idx = 2
        
        # 2~3번째 토큰 = 모델명 (에어팟, 갤럭시버즈 등)
        model = " ".join(tokens[start_idx:start_idx+3]) if len(tokens) > start_idx else ""
        
        return brand, model
    
    def generate_search_candidates(self, product_name: str) -> list[str]:
        """계층적 폴백 검색 후보 생성 (효율적)
        
        우선순위:
        1. 연도 제거 + 칩셋 유지 버전 (정확도 우선)
        2. 연도 제거 + 칩셋 제거 버전 (광범위)
        3. 연도만 제거 버전
        3. 정규화된 버전
        4. 브랜드 + 모델 (칩셋 포함)
        5. 모델명만
        6. 브랜드만
        """
        from src.utils.text_utils import clean_product_name
        from src.utils.normalization.normalize import normalize_search_query
        
        candidates = []
        seen = set()
        
        def add_candidate(cand: str, reason: str = ""):
            if not cand: return
            cand = cand.strip()
            if cand and cand.lower() not in seen:
                seen.add(cand.lower())
                candidates.append(cand)
                if reason:
                    logger.debug(f"[SearchCandidates] Added: '{cand}' ({reason})")

        # 🔴 핵심 1: 연도 제거 (칩셋은 유지) - 옵션/세대까지 반영 가능
        # 예: "Apple 2025 맥북 에어 15 M4" → "Apple 맥북 에어 15 M4"
        no_year_keep_chip = re.sub(r"\b(19|20)\d{2}\b", " ", product_name)
        no_year_keep_chip = re.sub(r"\s+", " ", no_year_keep_chip).strip()
        if no_year_keep_chip and no_year_keep_chip.lower() != product_name.lower():
            add_candidate(no_year_keep_chip, reason="연도 제거(칩셋 유지)")

        # 🔴 핵심 2: 연도 제거 + 칩셋 제거(광범위) - 출시 전/희소 모델 대비
        # 예: "... M4" → "..." (단, 맥북 등은 칩셋이 중요하므로 1번을 먼저 둠)
        no_year_drop_chip = re.sub(r"\bM\s*\d+\b", " ", no_year_keep_chip, flags=re.IGNORECASE)
        no_year_drop_chip = re.sub(r"\s+", " ", no_year_drop_chip).strip()
        if no_year_drop_chip and no_year_drop_chip.lower() not in seen:
            add_candidate(no_year_drop_chip, reason="연도 제거+칩셋 제거(광범위)")
        
        # 연도 제거만(중복 방지용) - 유지/제거 버전에서 이미 커버되지만, 안전망으로 둠
        no_year = no_year_keep_chip
        if no_year and no_year.lower() not in seen:
            add_candidate(no_year, reason="연도 제거")
        
        # 정규화된 전체
        normalized = normalize_search_query(product_name)
        add_candidate(normalized, reason="정규화 버전")
        
        # 브랜드 + 모델명 추출 (연도 제외)
        brand, model = self.extract_brand_and_model(product_name)
        if brand and model:
            # 모델에서 과도한 스펙 제거
            model_cleaned = re.sub(r'\s*\d+(\.\d+)?[GgTt][Bb]\s*', '', model).strip()
            add_candidate(f"{brand} {model_cleaned}", reason="브랜드+모델명")
            
            # 칩셋 정보가 있다면 포함 (M1, M2, M3, M4 등)
            m_chip = re.search(r"(?i)M\s*\d+", product_name)
            if m_chip:
                add_candidate(f"{brand} {model_cleaned} {m_chip.group()}".strip(), reason="브랜드+모델+칩셋")
        
        # 모델명만 (처음 2-3개 단어)
        if model:
            model_tokens = model.split()[:3]
            if model_tokens:
                add_candidate(" ".join(model_tokens), reason="모델명만")
        
        # 브랜드만
        if brand:
            add_candidate(brand, reason="브랜드만")
        
        # 대체 검색어 (맥북 -> MacBook 등)
        substitutions = load_search_substitutions()
        product_lower = product_name.lower()
        for kr_term, en_terms in substitutions.items():
            if kr_term in product_name or kr_term.lower() in product_lower:
                for en in en_terms:
                    add_candidate(en, reason=f"대체검색어 ({kr_term}→{en})")
        
        logger.info(f"[SearchCandidates] Generated {len(candidates)} candidates for '{product_name}': {candidates}")
        return candidates if candidates else [clean_product_name(product_name)]
    
    def get_smart_search_query(self, product_name: str) -> str:
        """가장 효율적인 검색어 반환 (우선순위: 정규화 → 브랜드+모델 → 모델)"""
        from src.utils.normalization.normalize import normalize_search_query
        
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
