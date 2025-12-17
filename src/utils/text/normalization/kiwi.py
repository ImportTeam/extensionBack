"""Kiwi 형태소 분석기 기반 고급 정규화 (선택사항)

현재는 정규식 개선으로 충분히 해결되었지만, 미래에 더 정확한 처리가 필요할 때
이 함수를 사용할 수 있습니다.

사용 방법:
  1. pip install kiwipiepy
  2. normalize_search_query_kiwi 함수 사용
"""

from typing import Optional


def normalize_search_query_kiwi(text: str) -> Optional[str]:
    """Kiwi 형태소 분석기를 이용한 고급 정규화 (선택사항)

    반환값:
    - None: kiwipiepy 미설치 또는 오류 발생
    - str: 정규화된 검색어
    """
    try:
        from kiwipiepy import Kiwi
    except ImportError:
        return None

    if not text:
        return ""

    try:
        kiwi = Kiwi()

        tech_terms = [
            "에어팟",
            "에어팟프로",
            "맥북",
            "아이폰",
            "갤럭시",
            "버즈",
            "애플워치",
            "비스포크",
            "그램",
            "이온",
            "오디세이",
            "RTX",
            "GTX",
            "iPad",
            "MacBook",
            "iPhone",
            "AppleWatch",
        ]
        for term in tech_terms:
            kiwi.add_user_word(term, tag="NNP", score=10)

        tokens = kiwi.tokenize(text, normalize_coda=True)

        stop_words = {
            "화이트",
            "블랙",
            "실버",
            "골드",
            "그레이",
            "블루",
            "핑크",
            "레드",
            "세대",
            "시리즈",
            "정품",
            "리퍼",
            "중고",
            "새제품",
            "블루투스",
            "무선",
            "유선",
            "이어폰",
            "헤드폰",
            "케이스",
            "커버",
            "필름",
            "가방",
            "파우치",
        }

        result_tokens = []
        for token in tokens:
            word = token.form
            tag = token.tag

            if tag not in ["NNG", "NNP", "SL", "SN"]:
                continue

            if word in stop_words:
                continue

            result_tokens.append(word)

        normalized = " ".join(result_tokens)
        import re

        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized if normalized else None

    except Exception:
        return None
