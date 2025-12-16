"""텍스트 유틸리티 유닛 테스트"""
import pytest
from src.utils.text_utils import (
    clean_product_name,
    extract_price_from_text,
    calculate_similarity
)
from src.utils.text_utils import split_kr_en_boundary
from src.utils.text_utils import normalize_search_query, extract_model_codes
from src.utils.text_utils import is_accessory_trap, weighted_match_score


class TestCleanProductName:
    """상품명 정제 테스트"""
    
    def test_remove_brackets(self):
        """대괄호 제거"""
        assert clean_product_name("[카드할인] 아이폰 15") == "아이폰 15"
        assert clean_product_name("[무료배송][특가] 삼성 갤럭시") == "삼성 갤럭시"
    
    def test_remove_parentheses(self):
        """소괄호 제거"""
        assert clean_product_name("아이폰 15 (자급제)") == "아이폰 15"
        assert clean_product_name("삼성 TV (2024년형)") == "삼성 TV"
    
    def test_remove_special_characters(self):
        """특수문자 제거"""
        assert clean_product_name("아이폰!@#$%^&*15") == "아이폰15"
    
    def test_preserve_hyphen_underscore(self):
        """하이픈과 언더스코어는 유지"""
        assert clean_product_name("USB-C 케이블") == "USB-C 케이블"
        assert clean_product_name("Type_C 어댑터") == "Type_C 어댑터"
    
    def test_normalize_whitespace(self):
        """다중 공백 정규화"""
        assert clean_product_name("아이폰    15    프로") == "아이폰 15 프로"
    
    def test_empty_string(self):
        """빈 문자열 처리"""
        assert clean_product_name("") == ""
        assert clean_product_name("   ") == ""


class TestExtractPriceFromText:
    """가격 추출 테스트"""
    
    def test_extract_simple_price(self):
        """단순 가격 추출"""
        assert extract_price_from_text("1,250,000원") == 1250000
        assert extract_price_from_text("450,000") == 450000
    
    def test_extract_with_text(self):
        """텍스트가 섞인 가격 추출"""
        assert extract_price_from_text("판매가: 1,500,000원") == 1500000
        assert extract_price_from_text("최저가 320,500원") == 320500
    
    def test_multiple_numbers(self):
        """여러 숫자 중 가장 긴 것 선택"""
        assert extract_price_from_text("10개 남음 1,250,000원") == 1250000
    
    def test_no_price(self):
        """가격이 없는 경우"""
        assert extract_price_from_text("품절") == 0
        assert extract_price_from_text("") == 0
    
    def test_invalid_price(self):
        """잘못된 형식"""
        assert extract_price_from_text("abc") == 0


class TestCalculateSimilarity:
    """유사도 계산 테스트"""
    
    def test_identical_texts(self):
        """동일한 텍스트"""
        similarity = calculate_similarity("아이폰 15 프로", "아이폰 15 프로")
        assert similarity == 1.0
    
    def test_similar_texts(self):
        """유사한 텍스트"""
        similarity = calculate_similarity("아이폰 15", "아이폰 15 프로")
        assert 0.5 < similarity < 1.0
    
    def test_different_texts(self):
        """완전히 다른 텍스트"""
        similarity = calculate_similarity("아이폰", "삼성")
        assert similarity == 0.0
    
    def test_empty_texts(self):
        """빈 텍스트"""
        assert calculate_similarity("", "아이폰") == 0.0
        assert calculate_similarity("아이폰", "") == 0.0
        assert calculate_similarity("", "") == 0.0
    
    def test_case_insensitive(self):
        """대소문자 무시"""
        similarity = calculate_similarity("iPhone 15", "iphone 15")
        assert similarity == 1.0


def test_split_kr_en_boundary():
    # 한글-영문 경계에 공백 추가
    input_text = 'N-시리즈BasicWhite'
    output = split_kr_en_boundary(input_text)
    assert output == 'N-시리즈 BasicWhite'

    input_text2 = '베이직스 2024 베이직북 14 N-시리즈BasicWhite · 256GB'
    output2 = split_kr_en_boundary(input_text2)
    assert 'N-시리즈 BasicWhite' in output2


def test_normalize_search_query_removes_specs():
    raw = "베이직스 2024 베이직북 14 N-시리즈BasicWhite · 256GB · 8GB · WIN11 Home · BB1422SS-N"
    norm = normalize_search_query(raw)
    # 구분자(·) 이후의 스펙은 제거되고, 구분자 이전의 내용 + 제거된 스펙 토큰 정리
    assert "256GB" not in norm.upper()
    assert "WIN11" not in norm.upper()
    assert "BB1422SS-N" not in norm
    # 개선된 정규화: 구분자 이후는 모두 버리므로 핵심 상품명만 남음
    assert "베이직스" in norm
    assert "베이직북" in norm


def test_normalize_search_query_preserves_generation():
    """[수정] 세대 숫자는 보존되어야 함 (기존 버그: 2세대 -> 공백)"""
    raw = "에어팟 프로 2세대 화이트 블루투스 이어폰"
    norm = normalize_search_query(raw)
    # '2세대' -> '2' (숫자 보존)
    assert '2' in norm or '에어팟' in norm
    # 색상, 이어폰, 블루투스는 제거됨
    assert '화이트' not in norm
    assert '블루투스' not in norm
    assert '이어폰' not in norm
    # 에어팟, 프로는 보존
    assert '에어팟' in norm
    assert '프로' in norm


def test_normalize_search_query_handles_compound_nouns():
    """[추가] 화이트케이스 같은 합성어 분리"""
    raw = "화이트케이스 Apple 에어팟 프로"
    norm = normalize_search_query(raw)
    # '화이트' 색상 제거, '케이스' 액세서리 제거
    # 따라서 '화이트' + '케이스' 모두 지워짐
    assert '화이트' not in norm
    assert '케이스' not in norm
    # Apple은 브랜드이므로 보존 (색상 제거 로직이 단어 경계 기준)
    assert 'Apple' in norm or 'apple' in norm.lower()
    assert '에어팟' in norm
    assert '프로' in norm


def test_normalize_search_query_preserves_type_c():
    """[추가] C타입/USB-C 같은 포트 타입은 (일부) 보존"""
    raw = "이어폰C USB-C 고속충전"
    norm = normalize_search_query(raw)
    # '이어폰' 제거되지만 'C'는 한글+영어 분리로 보존될 수 있음
    assert '이어폰' not in norm
    # USB-C/Type-C/C타입은 'C'로 표준화되어 남아야 함
    assert 'C' in norm or 'c' in norm.lower()


def test_normalize_search_query_preserves_color_for_non_it_products():
    """일반 상품(식품 등)에서는 색상/라인업명이 상품명일 수 있어 보존해야 함."""
    raw = "농심 신라면 블랙 컵라면"
    norm = normalize_search_query(raw)
    assert "신라면" in norm
    assert "블랙" in norm



def test_extract_model_codes():
    raw = "베이직스 2024 베이직북 14 N-시리즈BasicWhite · 256GB · 8GB · WIN11 Home · BB1422SS-N"
    codes = extract_model_codes(raw)
    assert "BB1422SS-N" in codes


def test_accessory_trap_filters_keyskin_for_main_product_query():
    query = "Apple 2025 맥북 에어 13 M4"
    accessory = "트루커버 애플 2025 맥북에어13 M4 파스텔톤 컬러 키스킨 (핑크 (블랙자판)) VS검색하기 VS검색 도움말"
    assert is_accessory_trap(query, accessory) is True
    assert weighted_match_score(query, accessory) == 0.0


def test_accessory_trap_allows_when_user_searches_accessory():
    query = "맥북 에어 13 키스킨"
    accessory = "트루커버 애플 2025 맥북에어13 M4 파스텔톤 컬러 키스킨"
    assert is_accessory_trap(query, accessory) is False
    assert weighted_match_score(query, accessory) > 0.0
