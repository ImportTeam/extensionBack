"""Tokenization utilities for matching."""

from __future__ import annotations

import re

from .cleaning import clean_product_name, split_kr_en_boundary


_KIWI_INSTANCE = None


def _get_kiwi():
    global _KIWI_INSTANCE
    if _KIWI_INSTANCE is not None:
        return _KIWI_INSTANCE

    try:
        from kiwipiepy import Kiwi

        _KIWI_INSTANCE = Kiwi()
        return _KIWI_INSTANCE
    except Exception:
        _KIWI_INSTANCE = None
        return None


def tokenize_keywords(text: str) -> set[str]:
    """검색/매칭용 키워드 토큰화.

    - Kiwi 사용 가능: 명사/영문/숫자 위주로 토큰화
    - 불가: 정규식 기반 폴백
    """
    if not text:
        return set()

    cleaned = split_kr_en_boundary(clean_product_name(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return set()

    stopwords = {
        "vs검색하기",
        "vs검색",
        "검색하기",
        "검색",
        "도움말",
    }

    kiwi = _get_kiwi()
    if kiwi is not None:
        tokens: list[str] = []
        try:
            for t in kiwi.tokenize(cleaned):
                # N*: 명사, SL: 외국어, SN: 숫자
                if t.tag.startswith("NN") or t.tag in {"SL", "SN"}:
                    form = (t.form or "").strip().lower()
                    if not form:
                        continue
                    if form in stopwords:
                        continue
                    tokens.append(form)
        except Exception:
            tokens = []

        if tokens:
            return set(tokens)

    # 폴백: 한글/영문/숫자 토큰
    rough = re.sub(r"[^\w\s가-힣]", " ", cleaned)
    toks = {t.lower() for t in rough.split() if t}
    return {t for t in toks if t not in stopwords}
