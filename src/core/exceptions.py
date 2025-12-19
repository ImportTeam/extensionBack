"""커스텀 예외 정의 (Structured Exception Hierarchy)"""
from typing import Any, Optional


# 기본 예외 클래스
class PriceDetectorException(Exception):
    """기본 예외 클래스 - 모든 커스텀 예외의 부모"""
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", details: Optional[dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


# 크롤러 관련 예외
class CrawlerException(PriceDetectorException):
    """크롤러 관련 예외의 기본 클래스"""
    def __init__(self, message: str, error_code: str = "CRAWLER_ERROR", details: Optional[dict[str, Any]] = None):
        super().__init__(message, error_code or "CRAWLER_ERROR", details)


class ProductNotFoundException(CrawlerException):
    """상품을 찾을 수 없을 때"""
    def __init__(self, query: str, details: Optional[dict[str, Any]] = None):
        message = f"Product not found for query: {query}"
        super().__init__(message, "PRODUCT_NOT_FOUND", details or {"query": query})


class BrowserException(CrawlerException):
    """브라우저 실행 오류"""
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message, "BROWSER_ERROR", details)


class NetworkTimeoutException(CrawlerException):
    """네트워크 타임아웃 예외"""
    def __init__(self, operation: str, timeout_ms: int, details: Optional[dict[str, Any]] = None):
        message = f"Network timeout during '{operation}' after {timeout_ms}ms"
        super().__init__(message, "NETWORK_TIMEOUT", 
                        details or {"operation": operation, "timeout_ms": timeout_ms})


class ParsingException(CrawlerException):
    """HTML/데이터 파싱 오류"""
    def __init__(self, reason: str, details: Optional[dict[str, Any]] = None):
        message = f"Failed to parse response: {reason}"
        super().__init__(message, "PARSING_ERROR", details or {"reason": reason})


class BlockedException(CrawlerException):
    """봇 감지/차단 예외"""
    def __init__(self, source: str, details: Optional[dict[str, Any]] = None):
        message = f"Request blocked by {source} (possible bot detection)"
        super().__init__(message, "BLOCKED", details or {"source": source})


# 캐시 관련 예외
class CacheException(PriceDetectorException):
    """캐시 관련 예외"""
    def __init__(self, message: str, error_code: str = "CACHE_ERROR", details: Optional[dict[str, Any]] = None):
        super().__init__(message, error_code or "CACHE_ERROR", details)


class CacheConnectionException(CacheException):
    """캐시 연결 실패"""
    def __init__(self, reason: str, details: Optional[dict[str, Any]] = None):
        message = f"Failed to connect to cache: {reason}"
        super().__init__(message, "CACHE_CONNECTION_ERROR", details)


class CacheSerializationException(CacheException):
    """캐시 직렬화/역직렬화 오류"""
    def __init__(self, operation: str, reason: str, details: Optional[dict[str, Any]] = None):
        message = f"Cache {operation} failed: {reason}"
        super().__init__(message, "CACHE_SERIALIZATION_ERROR", 
                        details or {"operation": operation, "reason": reason})


# 데이터베이스 관련 예외
class DatabaseException(PriceDetectorException):
    """데이터베이스 관련 예외"""
    def __init__(self, message: str, error_code: str = "DB_ERROR", details: Optional[dict[str, Any]] = None):
        super().__init__(message, error_code or "DB_ERROR", details)


class DatabaseConnectionException(DatabaseException):
    """DB 연결 실패"""
    def __init__(self, reason: str, details: Optional[dict[str, Any]] = None):
        message = f"Database connection failed: {reason}"
        super().__init__(message, "DB_CONNECTION_ERROR", details)


class DatabaseQueryException(DatabaseException):
    """DB 쿼리 실행 오류"""
    def __init__(self, query: str, reason: str, details: Optional[dict[str, Any]] = None):
        message = f"Database query failed: {reason}"
        super().__init__(message, "DB_QUERY_ERROR", 
                        details or {"query": query, "reason": reason})


# 유효성 검증 관련 예외
class ValidationException(PriceDetectorException):
    """유효성 검증 예외"""
    def __init__(self, field: str, reason: str, details: Optional[dict[str, Any]] = None):
        message = f"Validation failed for '{field}': {reason}"
        super().__init__(message, "VALIDATION_ERROR", 
                        details or {"field": field, "reason": reason})


class InvalidQueryException(ValidationException):
    """유효하지 않은 검색어"""
    def __init__(self, reason: str, details: Optional[dict[str, Any]] = None):
        super().__init__("query", reason, details)


class InvalidPriceException(ValidationException):
    """유효하지 않은 가격"""
    def __init__(self, price: Any, reason: str, details: Optional[dict[str, Any]] = None):
        super().__init__("price", f"{reason} (value: {price})", details)


class InvalidURLException(ValidationException):
    """유효하지 않은 URL"""
    def __init__(self, url: str, reason: str, details: Optional[dict[str, Any]] = None):
        super().__init__("url", f"{reason} (url: {url})", details)


# 예산/시간 관련 예외
class BudgetExhaustedException(PriceDetectorException):
    """예산 소진"""
    def __init__(self, remaining_ms: float, details: Optional[dict[str, Any]] = None):
        message = f"Budget exhausted (remaining: {remaining_ms}ms)"
        super().__init__(message, "BUDGET_EXHAUSTED", 
                        details or {"remaining_ms": remaining_ms})


class TimeoutException(PriceDetectorException):
    """타임아웃 예외"""
    def __init__(self, operation: str, timeout_s: float, details: Optional[dict[str, Any]] = None):
        message = f"Operation '{operation}' timed out after {timeout_s}s"
        super().__init__(message, "TIMEOUT", 
                        details or {"operation": operation, "timeout_s": timeout_s})
