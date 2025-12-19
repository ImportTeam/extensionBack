"""
CSP Header 설정
보안 미들웨어 및 검증 함수
"""

import hashlib
from typing import Optional
from fastapi import Request
from src.core.logging import logger, sanitize_for_log


class SecurityValidator:
    """입력 보안 검증"""
    
    MAX_QUERY_LENGTH = 500
    MAX_URL_LENGTH = 2048
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
    
    # 위험한 문자 (SQL Injection, XSS 방지)
    DANGEROUS_CHARS = ['<', '>', '"', "'", '\\', '\0', '\n', '\r', ';', '--', '/*', '*/']
    
    @staticmethod
    def validate_query(query: str) -> bool:
        """검색어 검증
        
        Args:
            query: 검색어
            
        Returns:
            유효성 여부
            
        Raises:
            ValueError: 유효하지 않은 입력
        """
        if not query:
            raise ValueError("검색어는 필수입니다")
        
        if len(query) > SecurityValidator.MAX_QUERY_LENGTH:
            raise ValueError(f"검색어는 {SecurityValidator.MAX_QUERY_LENGTH}자 이하여야 합니다")
        
        # 위험한 문자 체크
        for char in SecurityValidator.DANGEROUS_CHARS:
            if char in query:
                logger.warning(
                    f"검색어에 위험한 문자 감지: {sanitize_for_log(char)}"
                )
                raise ValueError("검색어에 허용되지 않는 문자가 포함되어 있습니다")
        
        return True
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """URL 검증
        
        Args:
            url: URL 문자열
            
        Returns:
            유효성 여부
            
        Raises:
            ValueError: 유효하지 않은 URL
        """
        if not url:
            raise ValueError("URL은 필수입니다")
        
        if len(url) > SecurityValidator.MAX_URL_LENGTH:
            raise ValueError(f"URL은 {SecurityValidator.MAX_URL_LENGTH}자 이하여야 합니다")
        
        if not url.startswith(('http://', 'https://')):
            raise ValueError("URL은 http:// 또는 https://로 시작해야 합니다")
        
        return True
    
    @staticmethod
    def validate_price(price: int) -> bool:
        """가격 검증
        
        Args:
            price: 가격
            
        Returns:
            유효성 여부
            
        Raises:
            ValueError: 유효하지 않은 가격
        """
        if price < 0:
            raise ValueError("가격은 음수일 수 없습니다")
        
        if price > 10**9:
            raise ValueError("가격이 너무 큽니다 (최대 10억원)")
        
        return True
    
    @staticmethod
    def hash_input(input_str: str) -> str:
        """입력값 해시 (로깅/캐싱용)
        
        Args:
            input_str: 입력 문자열
            
        Returns:
            SHA256 해시값
        """
        return hashlib.sha256(input_str.encode()).hexdigest()[:16]


async def log_request(request: Request) -> None:
    """요청 로깅 (민감 정보 제외)
    
    Args:
        request: FastAPI Request 객체
    """
    method = request.method
    path = request.url.path
    
    # 쿼리 파라미터 (민감 정보 제거)
    query_params = {}
    for key, value in request.query_params.items():
        query_params[key] = sanitize_for_log(str(value), max_length=50)
    
    # 로깅
    if query_params:
        logger.debug(f"{method} {path}?{query_params}")
    else:
        logger.debug(f"{method} {path}")


def is_safe_for_logging(value: Optional[str]) -> bool:
    """로깅 안전성 확인
    
    Args:
        value: 확인할 값
        
    Returns:
        로깅 가능 여부
    """
    if value is None:
        return True
    
    sensitive_keywords = ['password', 'token', 'key', 'secret', 'api', 'auth']
    
    for keyword in sensitive_keywords:
        if keyword.lower() in str(value).lower():
            return False
    
    return True
