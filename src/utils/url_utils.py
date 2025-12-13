"""URL 파싱 유틸리티"""
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs


def extract_pcode_from_url(url: str) -> Optional[str]:
    """
    다나와 URL에서 상품 코드(pcode) 추출
    
    Examples:
        >>> extract_pcode_from_url("https://prod.danawa.com/info/?pcode=70250585&keyword=맥북")
        '70250585'
        >>> extract_pcode_from_url("https://prod.danawa.com/info/?pcode=12345")
        '12345'
        >>> extract_pcode_from_url("invalid")
        None
    
    Args:
        url: 다나와 상품 URL
        
    Returns:
        pcode 또는 None
    """
    if not url:
        return None
    
    try:
        # Query string에서 pcode 추출
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        if 'pcode' in query_params:
            pcode = query_params['pcode'][0]
            # 숫자만 포함되어 있는지 확인
            if pcode.isdigit():
                return pcode
        
        # Fallback: 정규식으로 pcode= 패턴 찾기
        match = re.search(r'pcode=(\d+)', url)
        if match:
            return match.group(1)
        
        return None
    
    except Exception:
        return None


def normalize_href(href: str, base_url: str = "https://prod.danawa.com") -> str:
    """상대/프로토콜-상대 href를 절대 URL로 정규화합니다.

    - "//host/path" -> "https://host/path"
    - "/path" -> "{base_url}/path"
    - "http(s)://..." -> 그대로
    """
    if not href:
        return ""

    h = href.strip()
    if not h:
        return ""

    if h.startswith("//"):
        return f"https:{h}"

    if h.startswith("/"):
        return f"{base_url}{h}"

    return h
