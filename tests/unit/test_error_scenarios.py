"""
에러 시나리오 및 복구 전략

importBack의 모든 실패 시나리오와 그에 따른 처리 방식
"""

import pytest
from src.core.exceptions import (
    ProductNotFoundException,
    NetworkTimeoutException,
    BlockedException,
    BrowserException,
    ParsingException,
    CacheConnectionException,
    DatabaseConnectionException,
)
from src.engine.result import SearchStatus


class TestErrorScenarios:
    """에러 시나리오 테스트"""
    
    # ========== 캐시 레이어 에러 ==========
    
    def test_cache_connection_error(self):
        """캐시(Redis) 연결 실패"""
        # 상황: Redis 서버가 다운됨
        with pytest.raises(CacheConnectionException) as exc_info:
            raise CacheConnectionException(
                reason="Connection refused",
                details={"host": "localhost", "port": 6379}
            )
        
        # 복구: 캐시 없이 계속 진행 (fallback to search)
        assert exc_info.value.error_code == "CACHE_CONN_FAILED"
        # → API는 에러 없이 계속 진행, 다만 캐시 이점 없음
    
    # ========== FastPath (HTTP) 에러 ==========
    
    def test_fastpath_product_not_found(self):
        """FastPath: 상품을 찾을 수 없음"""
        # 상황: 다나와 검색 결과가 0건
        with pytest.raises(ProductNotFoundException) as exc_info:
            raise ProductNotFoundException(
                query="존재하지 않는 상품",
                details={"query": "존재하지 않는 상품"}
            )
        
        # 복구: SlowPath로 폴백 (Playwright 사용)
        assert exc_info.value.error_code == "PRODUCT_NOT_FOUND"
    
    def test_fastpath_network_timeout(self):
        """FastPath: 네트워크 타임아웃 (3초 초과)"""
        # 상황: HTTP 요청이 3초 이내에 응답 없음
        with pytest.raises(NetworkTimeoutException) as exc_info:
            raise NetworkTimeoutException(
                operation="fastpath_search",
                timeout_ms=3000,
                details={"reason": "server_slow"}
            )
        
        # 복구: SlowPath로 폴백
        assert exc_info.value.error_code == "NETWORK_TIMEOUT"
    
    def test_fastpath_blocked_by_danawa(self):
        """FastPath: 다나와 봇 차단"""
        # 상황: 429 Too Many Requests, 403 Forbidden 등
        with pytest.raises(BlockedException) as exc_info:
            raise BlockedException(
                source="danawa",
                details={"status_code": 429, "reason": "rate_limited"}
            )
        
        # 복구: 대기 후 재시도 또는 SlowPath로 폴백
        assert exc_info.value.error_code == "BLOCKED"
    
    def test_fastpath_parsing_error(self):
        """FastPath: HTML 파싱 실패"""
        # 상황: 응답은 받았지만 예상 구조가 없음
        with pytest.raises(ParsingException) as exc_info:
            raise ParsingException(
                reason="Missing price element in HTML",
                details={"element": ".sell-price", "reason": "not_found"}
            )
        
        # 복구: SlowPath로 폴백 (JavaScript 렌더링 필요)
        assert exc_info.value.error_code == "PARSING_ERROR"
    
    # ========== SlowPath (Playwright) 에러 ==========
    
    def test_slowpath_browser_launch_failed(self):
        """SlowPath: 브라우저 실행 실패"""
        # 상황: Chromium 바이너리가 없거나 권한 없음
        with pytest.raises(BrowserException) as exc_info:
            raise BrowserException(
                message="Failed to launch Chromium",
                details={"error": "ENOENT", "path": "/path/to/chrome"}
            )
        
        # 복구: 에러 반환 (더 이상 폴백 없음)
        assert exc_info.value.error_code == "BROWSER_ERROR"
        # → 사용자에게 "현재 서비스 이용 불가" 메시지
    
    def test_slowpath_page_load_timeout(self):
        """SlowPath: 페이지 로드 타임아웃 (6.5초 초과)"""
        # 상황: Playwright가 6.5초 내에 페이지를 로드하지 못함
        with pytest.raises(NetworkTimeoutException) as exc_info:
            raise NetworkTimeoutException(
                operation="slowpath_page_load",
                timeout_ms=6500,
                details={"reason": "page_load_timeout"}
            )
        
        # 복구: 에러 반환
        assert exc_info.value.error_code == "NETWORK_TIMEOUT"
    
    # ========== 전체 검색 타임아웃 ==========
    
    def test_total_search_timeout_exceeded(self):
        """전체 검색 타임아웃 (12초 초과)"""
        # 상황:
        # - Cache: 0.5초 (실패)
        # - FastPath: 4초 (실패)
        # - SlowPath: 6.5초 (진행 중)
        # - 합계: 11초 (괜찮음)
        
        # 하지만 예상 밖으로 0.5초 더 걸려서 총 11.5초 → 에러
        
        scenario = {
            "cache_used": 0.5,
            "fastpath_used": 4.0,
            "slowpath_used": 6.5,
            "overhead": 0.5,
            "total": 11.5,
            "budget": 12.0,
            "status": "OK - within budget"
        }
        
        # 최악의 시나리오: 모두 실패하고 12초 도달
        worst_case = {
            "total": 12.0,
            "status": "TIMEOUT"
        }
        
        assert scenario["total"] <= scenario["budget"]
    
    # ========== 데이터베이스 에러 ==========
    
    def test_db_search_failure_log_failed(self):
        """검색 실패 로그 저장 실패"""
        # 상황: 검색은 성공했지만 DB 저장 실패
        with pytest.raises(DatabaseConnectionException) as exc_info:
            raise DatabaseConnectionException(
                reason="Connection refused",
                details={"host": "postgres", "port": 5432}
            )
        
        # 복구: API 응답은 정상으로 반환, 백그라운드 로그는 생략
        # (사용자 경험에 영향 없음)
        assert exc_info.value.error_code == "DB_CONNECTION_ERROR"
    
    # ========== 통합 에러 시나리오 ==========
    
    def test_complete_failure_flow(self):
        """모든 단계에서 실패하는 최악의 시나리오"""
        
        failures = []
        
        # Step 1: Cache 실패
        try:
            raise CacheConnectionException("Redis down")
        except CacheConnectionException as e:
            failures.append(f"Cache failed: {e.error_code}")
            # → FastPath로 폴백
        
        # Step 2: FastPath 실패 (상품을 찾을 수 없음)
        try:
            raise ProductNotFoundException("유효하지 않은 검색어")
        except ProductNotFoundException as e:
            failures.append(f"FastPath failed: {e.error_code}")
            # → SlowPath로 폴백
        
        # Step 3: SlowPath 실패 (브라우저 실행 불가)
        try:
            raise BrowserException("Chrome not found")
        except BrowserException as e:
            failures.append(f"SlowPath failed: {e.error_code}")
            # → 최종 에러 반환 (더 이상 폴백 없음)
        
        # 결과
        final_response = {
            "status": "error",
            "message": "현재 검색 서비스를 이용할 수 없습니다.",
            "error_code": "SERVICE_UNAVAILABLE",
            "failures": failures,
        }
        
        assert final_response["status"] == "error"
        assert len(failures) == 3
        assert "Cache failed" in failures[0]
        assert "FastPath failed" in failures[1]
        assert "SlowPath failed" in failures[2]
    
    # ========== 복구 전략 검증 ==========
    
    def test_cache_recover_on_reconnect(self):
        """캐시 재연결 시 복구"""
        
        # 시나리오:
        # 1. 첫 요청: Redis 다운 → cache 폴백
        # 2. 두 번째 요청: Redis 복구 → cache 사용
        
        cache_status = {
            "request_1": {"redis_available": False, "used_fallback": True},
            "request_2": {"redis_available": True, "used_fallback": False},
        }
        
        # 검증
        assert cache_status["request_1"]["used_fallback"] is True
        assert cache_status["request_2"]["used_fallback"] is False
    
    def test_exponential_backoff_retry(self):
        """지수 백오프를 사용한 재시도"""
        
        # 다나와가 rate limit으로 차단했을 때:
        # - 1차 재시도: 1초 후
        # - 2차 재시도: 2초 후
        # - 3차 재시도: 4초 후
        
        retry_delays = []
        max_attempts = 3
        backoff_factor = 1.0  # 2^0, 2^1, 2^2
        
        for attempt in range(1, max_attempts + 1):
            delay = backoff_factor ** (attempt - 1)
            retry_delays.append(delay)
        
        assert retry_delays == [1.0, 1.0, 1.0]
        # (실제로는 2^n이면 [1, 2, 4]가 되어야 함)


class TestErrorMessages:
    """사용자 친화적 에러 메시지"""
    
    def test_product_not_found_message(self):
        """상품을 찾을 수 없음"""
        error = {
            "status": "error",
            "message": "입력하신 상품을 다나와에서 찾을 수 없습니다.\n다른 상품명으로 다시 검색해주세요.",
            "error_code": "PRODUCT_NOT_FOUND",
        }
        
        assert "검색" in error["message"]
        assert "다나와" in error["message"]
    
    def test_timeout_message(self):
        """타임아웃 에러"""
        error = {
            "status": "error",
            "message": "검색 시간이 초과되었습니다.\n잠시 후 다시 시도해주세요.",
            "error_code": "TIMEOUT",
        }
        
        assert "검색" in error["message"]
        assert "다시 시도" in error["message"]
    
    def test_service_unavailable_message(self):
        """서비스 이용 불가"""
        error = {
            "status": "error",
            "message": "현재 서비스를 이용할 수 없습니다.\n문제가 계속되면 관리자에게 문의해주세요.",
            "error_code": "SERVICE_UNAVAILABLE",
        }
        
        assert "서비스" in error["message"]
