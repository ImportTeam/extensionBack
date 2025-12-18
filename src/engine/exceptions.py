"""Crawler Exceptions - Standardized exception hierarchy

Defines all exceptions used by the crawler engine and executors.
"""


class CrawlerException(Exception):
    """크롤러 기본 예외"""

    pass


class TimeoutError(CrawlerException):
    """타임아웃 예외

    FastPath/SlowPath 실행 시 타임아웃이 발생한 경우
    """

    pass


class ParsingError(CrawlerException):
    """파싱 오류 예외

    HTML 구조 변경 등으로 파싱이 실패한 경우
    """

    pass


class BlockedError(CrawlerException):
    """차단 예외

    봇 차단이 감지된 경우
    """

    pass


class ProductNotFoundException(CrawlerException):
    """상품을 찾을 수 없음

    검색 결과가 없거나 상품 URL이 유효하지 않은 경우
    """

    pass


class BudgetExhaustedError(CrawlerException):
    """예산 소진 예외

    12초 예산이 소진되어 더 이상 실행할 수 없는 경우
    """

    pass


# Backward compatibility - 기존 코드와의 호환성 유지
FastPathNoResults = ProductNotFoundException
FastPathProductFetchFailed = ParsingError
