"""엣지 케이스 및 보안 테스트"""
import pytest
from src.core.security import SecurityValidator
from src.utils.edge_cases import EdgeCaseHandler
from src.core.exceptions import (
    InvalidQueryException,
    InvalidPriceException,
    ValidationException,
)


class TestSecurityValidation:
    """보안 검증 테스트"""
    
    def test_query_with_sql_injection(self):
        """SQL Injection 시도 차단"""
        with pytest.raises(ValueError):
            SecurityValidator.validate_query("test'; DROP TABLE users; --")
    
    def test_query_with_xss(self):
        """XSS 시도 차단"""
        with pytest.raises(ValueError):
            SecurityValidator.validate_query("<script>alert('xss')</script>")
    
    def test_query_length_limit(self):
        """쿼리 길이 제한"""
        with pytest.raises(ValueError):
            SecurityValidator.validate_query("a" * 501)
    
    def test_valid_query(self):
        """유효한 쿼리"""
        assert SecurityValidator.validate_query("삼성 갤럭시 S24") is True
    
    def test_price_negative(self):
        """음수 가격 거절"""
        with pytest.raises(ValueError):
            SecurityValidator.validate_price(-1000)
    
    def test_price_too_large(self):
        """초과 높은 가격 거절"""
        with pytest.raises(ValueError):
            SecurityValidator.validate_price(10**10)
    
    def test_valid_price(self):
        """유효한 가격"""
        assert SecurityValidator.validate_price(500000) is True
    
    def test_url_without_protocol(self):
        """프로토콜 없는 URL 거절"""
        with pytest.raises(ValueError):
            SecurityValidator.validate_url("example.com")
    
    def test_valid_url(self):
        """유효한 URL"""
        assert SecurityValidator.validate_url("https://prod.danawa.com/info/?pcode=123") is True


class TestEdgeCaseHandler:
    """엣지 케이스 처리 테스트"""
    
    def test_safe_get_on_none(self):
        """None 딕셔너리 접근"""
        result = EdgeCaseHandler.safe_get(None, "key", default="default")
        assert result == "default"
    
    def test_safe_get_missing_key(self):
        """없는 키 접근"""
        data = {"existing": "value"}
        result = EdgeCaseHandler.safe_get(data, "missing", default="default")
        assert result == "default"
    
    def test_safe_get_type_mismatch(self):
        """타입 불일치"""
        data = {"price": "not_an_int"}
        result = EdgeCaseHandler.safe_get(data, "price", default=0, expected_type=int)
        assert result == 0
    
    def test_safe_int_from_none(self):
        """None에서 정수 변환"""
        result = EdgeCaseHandler.safe_int(None, default=0)
        assert result == 0
    
    def test_safe_int_from_string(self):
        """문자열에서 정수 변환"""
        result = EdgeCaseHandler.safe_int("12345")
        assert result == 12345
    
    def test_safe_int_below_min(self):
        """최소값 미만"""
        result = EdgeCaseHandler.safe_int(-5, default=0, min_val=0)
        assert result == 0
    
    def test_safe_int_exceeds_max(self):
        """최대값 초과"""
        result = EdgeCaseHandler.safe_int(1000, default=0, max_val=500)
        assert result == 0
    
    def test_safe_str_on_none(self):
        """None 문자열 변환"""
        result = EdgeCaseHandler.safe_str(None, default="default")
        assert result == "default"
    
    def test_safe_str_truncate(self):
        """긴 문자열 절단"""
        long_str = "a" * 100
        result = EdgeCaseHandler.safe_str(long_str, max_length=50)
        assert len(result) == 50
    
    def test_safe_list_on_none(self):
        """None 리스트 변환"""
        result = EdgeCaseHandler.safe_list(None)
        assert result == []
    
    def test_safe_list_from_tuple(self):
        """튜플을 리스트로 변환"""
        result = EdgeCaseHandler.safe_list((1, 2, 3))
        assert result == [1, 2, 3]
    
    def test_safe_index_on_empty_list(self):
        """빈 리스트 인덱싱"""
        result = EdgeCaseHandler.safe_index([], 0, default="default")
        assert result == "default"
    
    def test_safe_index_out_of_range(self):
        """범위 초과 인덱싱"""
        result = EdgeCaseHandler.safe_index([1, 2, 3], 10, default="default")
        assert result == "default"
    
    def test_safe_index_valid(self):
        """유효한 인덱싱"""
        result = EdgeCaseHandler.safe_index([10, 20, 30], 1)
        assert result == 20
    
    def test_validate_non_empty_empty(self):
        """빈 문자열 검증"""
        with pytest.raises(ValueError):
            EdgeCaseHandler.validate_non_empty("")
    
    def test_validate_non_empty_valid(self):
        """유효한 문자열 검증"""
        result = EdgeCaseHandler.validate_non_empty("  hello  ")
        assert result == "hello"
    
    def test_validate_positive_zero(self):
        """0 검증 (양수 아님)"""
        with pytest.raises(ValueError):
            EdgeCaseHandler.validate_positive(0)
    
    def test_validate_positive_valid(self):
        """유효한 양수 검증"""
        result = EdgeCaseHandler.validate_positive(42)
        assert result == 42
    
    def test_validate_non_negative_negative(self):
        """음수 검증 (음이 아님)"""
        with pytest.raises(ValueError):
            EdgeCaseHandler.validate_non_negative(-1)
    
    def test_validate_non_negative_zero(self):
        """0 검증 (음이 아님)"""
        result = EdgeCaseHandler.validate_non_negative(0)
        assert result == 0


class TestTimeoutHandling:
    """타임아웃 처리 테스트"""
    
    @pytest.mark.asyncio
    async def test_timeout_on_slow_operation(self):
        """느린 작업 타임아웃"""
        import asyncio
        
        async def slow_op():
            await asyncio.sleep(2)
            return "done"
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_op(), timeout=0.5)
    
    def test_budget_allocation(self):
        """예산 할당 검증"""
        from src.engine.budget import BudgetConfig
        
        config = BudgetConfig()
        total = config.cache_timeout + config.fastpath_timeout + config.slowpath_timeout
        assert total <= config.total_budget


class TestNullSafety:
    """Null safety 테스트"""
    
    def test_result_with_missing_fields(self):
        """결과 객체에 필드 누락"""
        # 이 테스트는 실제 CrawlResult 객체를 사용해야 함
        result = {
            "product_url": None,
            "price": None,
        }
        
        # safe_get으로 안전하게 접근
        url = EdgeCaseHandler.safe_get(result, "product_url")
        price = EdgeCaseHandler.safe_int(
            EdgeCaseHandler.safe_get(result, "price"),
            default=0
        )
        
        assert url is None
        assert price == 0
