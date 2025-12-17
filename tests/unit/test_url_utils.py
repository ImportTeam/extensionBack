"""URL 파싱 유틸 테스트"""
import pytest
from src.utils.url_utils import extract_pcode_from_url
from src.utils.url_utils import normalize_href


class TestExtractPcodeFromUrl:
    """URL에서 pcode 추출 테스트"""
    
    def test_extract_pcode_standard_url(self):
        """표준 다나와 URL"""
        url = "https://prod.danawa.com/info/?pcode=70250585&keyword=맥북&cate=11236463"
        assert extract_pcode_from_url(url) == "70250585"
    
    def test_extract_pcode_minimal_url(self):
        """최소 형태 URL"""
        url = "https://prod.danawa.com/info/?pcode=12345"
        assert extract_pcode_from_url(url) == "12345"
    
    def test_extract_pcode_with_fragment(self):
        """Fragment가 있는 URL"""
        url = "https://prod.danawa.com/info/?pcode=99999#spec"
        assert extract_pcode_from_url(url) == "99999"
    
    def test_extract_pcode_query_string_order(self):
        """pcode가 중간에 있는 경우"""
        url = "https://prod.danawa.com/info/?keyword=test&pcode=55555&cate=123"
        assert extract_pcode_from_url(url) == "55555"

    def test_extract_pcode_from_prod_id_bridge_url(self):
        """검색 결과/외부몰 브릿지 링크(prod_id)에서도 코드 추출"""
        url = (
            "https://prod.danawa.com/bridge/go_link_goods.php?cate_c1=224"
            "&cate_c2=49729&cate_c3=49740&cmpny_c=EE128&link_prod_c=4605258019"
            "&prod_id=65920016&linkYN=Y&fee_type=T"
        )
        assert extract_pcode_from_url(url) == "65920016"
    
    def test_extract_pcode_invalid_url(self):
        """잘못된 URL"""
        assert extract_pcode_from_url("invalid_url") is None
        assert extract_pcode_from_url("https://example.com") is None
        assert extract_pcode_from_url("") is None
    
    def test_extract_pcode_non_numeric(self):
        """pcode가 숫자가 아닌 경우"""
        url = "https://prod.danawa.com/info/?pcode=abc123"
        assert extract_pcode_from_url(url) is None

    def test_extract_pcode_non_numeric_prod_id(self):
        """prod_id가 숫자가 아닌 경우"""
        url = "https://prod.danawa.com/bridge/go_link_goods.php?prod_id=abc123"
        assert extract_pcode_from_url(url) is None
    
    def test_extract_pcode_missing_pcode(self):
        """pcode 파라미터가 없는 경우"""
        url = "https://prod.danawa.com/info/?keyword=맥북"
        assert extract_pcode_from_url(url) is None

def test_normalize_href():
    assert normalize_href("//example.com/a") == "https://example.com/a"
    assert normalize_href("/info/?pcode=1", base_url="https://prod.danawa.com") == "https://prod.danawa.com/info/?pcode=1"
    assert normalize_href("https://prod.danawa.com/info/?pcode=1") == "https://prod.danawa.com/info/?pcode=1"
