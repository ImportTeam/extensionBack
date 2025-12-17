"""해싱 유틸리티"""
import hashlib


def hash_string(text: str) -> str:
    """
    문자열을 MD5 해시로 변환
    
    Args:
        text: 해시할 문자열
        
    Returns:
        MD5 해시 문자열
    """
    return hashlib.md5(text.encode()).hexdigest()


def generate_cache_key(product_name: str) -> str:
    """
    상품명으로 캐시 키 생성
    
    Args:
        product_name: 상품명
        
    Returns:
        Redis 캐시 키
    """
    from src.utils.text import clean_product_name
    
    cleaned = clean_product_name(product_name)
    hashed = hash_string(cleaned)
    return f"price:{hashed}"


def generate_negative_cache_key(product_name: str) -> str:
    """상품명으로 '부정 캐시'(검색 실패/미발견) 키 생성"""
    from src.utils.text import clean_product_name

    cleaned = clean_product_name(product_name)
    hashed = hash_string(cleaned)
    return f"price:neg:{hashed}"
