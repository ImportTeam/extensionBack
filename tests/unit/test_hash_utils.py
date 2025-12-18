"""해싱 유틸리티 유닛 테스트"""
import pytest
from src.utils.hash_utils import hash_string, generate_cache_key


class TestHashUtils:
    """해싱 유틸리티 테스트"""
    
    def test_hash_string_consistency(self):
        """동일한 입력에 대한 일관성"""
        text = "아이폰 15 프로"
        hash1 = hash_string(text)
        hash2 = hash_string(text)
        assert hash1 == hash2
    
    def test_hash_string_different_inputs(self):
        """다른 입력에 대한 다른 해시"""
        hash1 = hash_string("아이폰 15")
        hash2 = hash_string("아이폰 16")
        assert hash1 != hash2
    
    def test_hash_string_length(self):
        """MD5 해시 길이 확인 (32자)"""
        hashed = hash_string("test")
        assert len(hashed) == 32
    
    def test_generate_cache_key_format(self):
        """캐시 키 포맷 확인"""
        key = generate_cache_key("아이폰 15 프로")
        assert key.startswith("price:")
        assert len(key) == 38  # "price:" (6) + MD5 (32)
    
    def test_generate_cache_key_cleans_name(self):
        """상품명 정제 후 키 생성"""
        key1 = generate_cache_key("[할인] 아이폰 15")
        key2 = generate_cache_key("아이폰 15")
        assert key1 == key2
