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
        
        # 다나와 URL은 pcode 또는 prod_id 형태가 모두 존재합니다.
        # (예: 검색결과/외부몰 브릿지 링크는 prod_id를 사용)
        for key in ("pcode", "prod_id"):
            if key in query_params:
                value = query_params[key][0]
                if value.isdigit():
                    return value
        
        # Fallback: 정규식으로 pcode/prod_id 패턴 찾기
        match = re.search(r'(?:pcode|prod_id)=(\d+)', url)
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
