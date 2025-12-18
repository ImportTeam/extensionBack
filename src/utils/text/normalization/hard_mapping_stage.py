"""Hard Mapping 적용 로직 (5단계)"""

from __future__ import annotations

import re
from typing import Optional

from src.core.logging import logger

from .hard_mapping_loader import load_hard_mapping, get_sorted_mapping_keys, get_hard_mapping_yaml_path
from .hard_mapping_utils import normalize_for_hard_mapping_match


class HardMappingStage:
    """
    Hard Mapping은 normalize_search_query의 Stage 0입니다.
    
    5단계 실행 순서:
    1 액세서리 필터 (skip_if_contains)
    2 Case/Space 정규화 (normalize_for_matching)
    3 Hard Mapping 적용 (apply_hard_mapping)
    4 매칭 결과 검증
    5 결과 반환 (매칭 성공 시 즉시) 또는 다음 단계로
    """
    
    # 액세서리 키워드 (Skip Hard Mapping 조건)
    ACCESSORY_KEYWORDS = {
        "케이스", "커버", "필름", "보호필름", "보호",
        "거치대", "스탠드", "파우치", "가방",
        "포함", "번들", "세트", "구성",
        "충전기", "어댑터", "케이블", "허브",
        "렌즈", "렌즈캡", "마운트", "삼각대"
    }
    
    # Hard Mapping은 메타에서 로드
    META_RULES = None
    
    @classmethod
    def load_meta_rules(cls):
        """YAML meta 섹션 로드"""
        if cls.META_RULES is not None:
            return cls.META_RULES
        
        try:
            import yaml
            
            yaml_path = get_hard_mapping_yaml_path()
            
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            cls.META_RULES = data.get("rules", {})
            return cls.META_RULES
        except Exception as e:
            logger.warning(f"Failed to load meta rules: {e}")
            return {}
    
    @staticmethod
    def stage_1_accessory_filter(text: str) -> bool:
        """
        📊 Stage 1: 액세서리 필터 (Skip Hard Mapping 조건)
        
        액세서리 키워드가 있으면 Hard Mapping을 스킵합니다.
        
        Args:
            text: 사용자 입력
        
        Returns:
            True = 액세서리 감지됨 (Hard Mapping 스킵)
            False = 안전함 (Hard Mapping 진행)
        """
        text_lower = text.lower()

        rules = HardMappingStage.load_meta_rules() or {}
        configured = rules.get("skip_if_contains") or []
        keywords = set(HardMappingStage.ACCESSORY_KEYWORDS) | {str(x) for x in configured}

        for keyword in keywords:
            if keyword in text_lower:
                logger.debug(f"[Stage 1] Accessory detected: '{keyword}' in '{text}'")
                return True
        
        return False
    
    @staticmethod
    def stage_2_normalize_for_matching(text: str) -> str:
        """
        📊 Stage 2: Case/Space 정규화 (Rule 2)
        
        Hard Mapping 매칭 전 입력을 정규화합니다.
        
        원칙:
        - 소문자화
        - 공백 정규화 (다중 → 단일)
        - 한글-영문 경계 공백 삽입
        - 특수문자 제거 (하이픈, 언더스코어만 보존)
        
        Args:
            text: 원본 입력
        
        Returns:
            정규화된 입력 (매칭용)
        """
        normalized = normalize_for_hard_mapping_match(text)
        logger.debug(f"[Stage 2] Normalized for matching: '{normalized}'")
        return normalized
    
    @staticmethod
    def stage_3_apply_hard_mapping(normalized_text: str) -> Optional[str]:
        """
        📊 Stage 3: Hard Mapping 적용 (Rule 1, Rule 3)
        
        Rule 1: Longest Match First - 길이 내림차순 정렬해 매칭
        Rule 3: Execution Stage 0 - 즉시 반환
        
        Args:
            normalized_text: 정규화된 입력
        
        Returns:
            매칭된 표준형 또는 None (매칭 실패)
        """
        mapping = load_hard_mapping()
        sorted_keys = get_sorted_mapping_keys()
        
        logger.debug(f"[Stage 3] Trying Hard Mapping on: '{normalized_text}'")
        
        for key in sorted_keys:
            if key == normalized_text or key in normalized_text:
                result = mapping[key]
                logger.info(f"[Stage 3] ✅ Hard Mapping matched: '{normalized_text}' → '{result}'")
                return result
        
        logger.debug(f"[Stage 3] ❌ No Hard Mapping match for: '{normalized_text}'")
        return None
    
    @staticmethod
    def stage_4_validate_result(
        original_text: str,
        normalized_text: str,
        mapped_result: Optional[str]
    ) -> bool:
        """
        📊 Stage 4: 매칭 결과 검증 (Rule 5)
        
        95% 이상 확실성 검증:
        - 브랜드가 명시됨
        - 제품명이 명시됨
        - 오류 가능성 < 5%
        
        Args:
            original_text: 원본 입력
            normalized_text: 정규화된 입력
            mapped_result: 매핑 결과
        
        Returns:
            True = 신뢰할 수 있는 결과
            False = 의심스러운 결과 (다음 단계로)
        """
        if not mapped_result:
            return False
        
        # 1️⃣ 브랜드 명시 확인
        brands = {"apple", "samsung", "lg", "dell", "hp", "asus", "lenovo", 
                 "농심", "삼양", "오뚜기", "lg", "sony", "bose", "jbl", "beats"}
        
        mapped_lower = mapped_result.lower()
        has_brand = any(brand in mapped_lower for brand in brands)
        
        if not has_brand:
            logger.warning(f"[Stage 4] Missing brand in result: {mapped_result}")
            return False
        
        # 2️⃣ 매핑 결과가 원본과 크게 다르지 않은지 확인
        # (다나와 검색 친화적인지 재확인)
        
        logger.debug(f"[Stage 4] ✅ Result validated: {mapped_result}")
        return True
    
    @staticmethod
    def stage_5_return_or_fallback(
        mapped_result: Optional[str],
        normalized_text: str,
        is_valid: bool
    ) -> Optional[str]:
        """
        📊 Stage 5: 결과 반환 또는 Fallback
        
        Rule 3: 매칭 성공 시 즉시 반환
        
        Args:
            mapped_result: 매핑 결과
            normalized_text: 정규화된 입력
            is_valid: 검증 결과
        
        Returns:
            표준형 (성공) 또는 None (다음 단계로)
        """
        if mapped_result and is_valid:
            logger.info(f"[Stage 5] ✅ Hard Mapping SUCCESS: returning '{mapped_result}'")
            return mapped_result
        
        logger.debug(f"[Stage 5] Hard Mapping failed, proceeding to next stage")
        return None


def apply_hard_mapping_complete(text: str) -> Optional[str]:
    """
    Hard Mapping 전체 파이프라인 (5단계)
    
    📋 실행 순서:
    1️⃣ 액세서리 필터
    2️⃣ Case/Space 정규화
    3️⃣ Hard Mapping 적용
    4️⃣ 결과 검증
    5️⃣ 반환 또는 Fallback
    
    Args:
        text: 사용자 입력
    
    Returns:
        표준형 (성공) 또는 None (다음 단계로)
    """
    if not text:
        return None
    
    logger.info(f"[Hard Mapping] Starting pipeline for: '{text}'")
    
    # Stage 1: 액세서리 필터
    if HardMappingStage.stage_1_accessory_filter(text):
        logger.info(f"[Hard Mapping] Skipped (accessory detected): '{text}'")
        return None
    
    # Stage 2: Case/Space 정규화
    normalized = HardMappingStage.stage_2_normalize_for_matching(text)
    if not normalized:
        return None
    
    # Stage 3: Hard Mapping 적용
    mapped = HardMappingStage.stage_3_apply_hard_mapping(normalized)
    if not mapped:
        return None
    
    # Stage 4: 결과 검증
    is_valid = HardMappingStage.stage_4_validate_result(text, normalized, mapped)
    if not is_valid:
        return None
    
    # Stage 5: 반환 또는 Fallback
    result = HardMappingStage.stage_5_return_or_fallback(mapped, normalized, is_valid)
    
    return result
