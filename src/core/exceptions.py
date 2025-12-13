"""커스텀 예외 정의"""


class PriceDetectorException(Exception):
    """기본 예외 클래스"""
    pass


class CrawlerException(PriceDetectorException):
    """크롤러 관련 예외"""
    pass


class CacheException(PriceDetectorException):
    """캐시 관련 예외"""
    pass


class DatabaseException(PriceDetectorException):
    """데이터베이스 관련 예외"""
    pass


class ValidationException(PriceDetectorException):
    """유효성 검증 예외"""
    pass


class ProductNotFoundException(CrawlerException):
    """상품을 찾을 수 없을 때"""
    pass


class BrowserException(CrawlerException):
    """브라우저 실행 오류"""
    pass
