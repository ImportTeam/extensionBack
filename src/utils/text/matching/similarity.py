"""Similarity helpers."""

from __future__ import annotations

import re

from ..core.cleaning import clean_product_name, split_kr_en_boundary


def calculate_similarity(text1: str, text2: str) -> float:
    """두 텍스트의 유사도를 계산 (폴백).

    rapidfuzz가 없는 환경에서:
    - 한국어 띄어쓰기/붙임(예: '맥북 에어' vs '맥북에어')
    - 한글/숫자/영문 경계(예: '에어13' vs '에어 13')
    를 견딜 수 있도록 토큰 Jaccard + 공백무시 bigram Jaccard를 혼합합니다.
    """
    if not text1 or not text2:
        return 0.0

    def _prep(text: str) -> str:
        t = split_kr_en_boundary(clean_product_name(text))
        t = re.sub(r"\s+", " ", t).strip().lower()
        return t

    def _nospace(text: str) -> str:
        # 공백/탭 제거 + 비교에 방해되는 문장부호 제거
        t = re.sub(r"\s+", "", text)
        t = re.sub(r"[^0-9a-zA-Z가-힣]", "", t)
        return t

    def _bigrams(s: str) -> set[str]:
        if not s:
            return set()
        if len(s) == 1:
            return {s}
        return {s[i : i + 2] for i in range(len(s) - 1)}

    p1 = _prep(text1)
    p2 = _prep(text2)

    words1 = set(p1.split())
    words2 = set(p2.split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    token_sim = len(intersection) / len(union) if union else 0.0

    # 토큰 기반이 약한(붙임/띄어쓰기 차이) 경우를 보완
    ns1 = _nospace(p1)
    ns2 = _nospace(p2)
    # 너무 짧은 문자열의 포함 판정은 과매칭 위험 → 길이 조건
    if min(len(ns1), len(ns2)) >= 6 and (ns1 in ns2 or ns2 in ns1):
        ns_sim = 0.98
    else:
        b1 = _bigrams(ns1)
        b2 = _bigrams(ns2)
        b_union = b1.union(b2)
        ns_sim = (len(b1.intersection(b2)) / len(b_union)) if b_union else 0.0

    # 경험적으로 token_sim이 안정적이고 ns_sim이 회복용이므로 가중 평균
    return max(token_sim, ns_sim * 0.85)


def fuzzy_score(query: str, candidate: str) -> float:
    """두 문자열의 유사도 점수(0~100).

    rapidfuzz가 설치되어 있으면 WRatio를 사용하고,
    없으면 기존 calculate_similarity를 사용합니다.
    """
    if not query or not candidate:
        return 0.0

    try:
        from rapidfuzz import fuzz, utils

        return float(fuzz.WRatio(query, candidate, processor=utils.default_process))
    except Exception:
        return calculate_similarity(query, candidate) * 100.0
