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
    
    장점:
    - 한글 형태소 분석으로 정확한 단어 분리
    - 품사 태깅으로 필요한 단어만 추출
    - 복합명사(화이트케이스) 자동 처리
    
    제약:
    - 초기 로딩 약간의 시간 소요
    - 첫 실행 시 설정 필요
    
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
        
        # IT 제품명에 자주 나오는 고유명사 등록 (선택사항)
        tech_terms = [
            "에어팟", "에어팟프로", "맥북", "아이폰", "갤럭시", "버즈",
            "애플워치", "비스포크", "그램", "이온", "오디세이", "RTX", "GTX",
            "iPad", "MacBook", "iPhone", "AppleWatch"
        ]
        for term in tech_terms:
            kiwi.add_user_word(term, tag='NNP', score=10)
        
        # 형태소 분석 (normalize_coda=True로 받침 정규화)
        tokens = kiwi.tokenize(text, normalize_coda=True)
        
        # 제거할 불용어
        stop_words = {
            # 색상
            "화이트", "블랙", "실버", "골드", "그레이", "블루", "핑크", "레드",
            # 세대/시리즈
            "세대", "시리즈",
            # 상태/정보
            "정품", "리퍼", "중고", "새제품",
            # 기술명사 (검색에 방해)
            "블루투스", "무선", "유선", "이어폰", "헤드폰",
            # 액세서리
            "케이스", "커버", "필름", "가방", "파우치",
        }
        
        result_tokens = []
        for token in tokens:
            word = token.form
            tag = token.tag
            
            # 필요한 품사만 추출
            # NNG: 일반명사, NNP: 고유명사, SL: 알파벳, SN: 숫자
            if tag not in ['NNG', 'NNP', 'SL', 'SN']:
                continue
            
            # 불용어 필터
            if word in stop_words:
                continue
            
            result_tokens.append(word)
        
        normalized = " ".join(result_tokens)
        # 최종 공백 정리
        import re
        normalized = re.sub(r"\s+", " ", normalized).strip()
        
        return normalized if normalized else None
    
    except Exception as e:
        # Kiwi 오류 발생 시 원래 정규식 함수 사용으로 폴백
        print(f"⚠️  Kiwi 처리 중 오류: {e}")
        return None


# 테스트 코드
if __name__ == "__main__":
    test_cases = [
        "에어팟 프로 2세대 화이트 블루투스 이어폰",
        "화이트케이스 Apple 에어팟 프로",
        "MacBook Air 15인치 M2 스타라이트",
    ]
    
    print("=" * 80)
    print("Kiwi 형태소 분석 기반 정규화 (선택사항)")
    print("=" * 80)
    
    for text in test_cases:
        result = normalize_search_query_kiwi(text)
        if result is None:
            print(f"⚠️  Kiwi 미설치 또는 오류. 정규식 함수 사용 권장.")
            break
        print(f"\n원본:    {text}")
        print(f"Kiwi:   {result}")
    else:
        print("\n✅ Kiwi 형태소 분석 완료")
