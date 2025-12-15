"""Similarity helpers."""

from __future__ import annotations


def calculate_similarity(text1: str, text2: str) -> float:
    """
    두 텍스트의 유사도를 계산 (간단한 단어 매칭 기반)
    
    Args:
        text1: 첫 번째 텍스트
        text2: 두 번째 텍스트
        
    Returns:
        0.0 ~ 1.0 사이의 유사도 점수
    """
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)


def fuzzy_score(query: str, candidate: str) -> float:
    """두 문자열의 유사도 점수(0~100).

    rapidfuzz가 설치되어 있으면 WRatio를 사용하고,
    없으면 기존 calculate_similarity를 사용합니다.
    """
    if not query or not candidate:
        return 0.0

    try:
        from rapidfuzz import fuzz, utils  # type: ignore

        # WRatio는 다양한 스코어러를 조합해 일반적인 상품명 매칭에 더 안정적입니다.
        return float(fuzz.WRatio(query, candidate, processor=utils.default_process))
    except Exception:
        return calculate_similarity(query, candidate) * 100.0
