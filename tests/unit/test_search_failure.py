"""검색 실패 학습 시스템 테스트"""
import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from src.repositories.search_failure_repository import SearchFailureRepository
from src.services.search_failure_analyzer import SearchFailureAnalyzer
from src.core.database import get_db


@pytest.fixture
def test_failures(db: Session):
    """테스트 데이터 생성"""
    test_data = [
        {
            "original": "Apple 2024 에어팟 4 액티브 노이즈 캔슬링 블루투스 이어폰",
            "normalized": "에어팟 4 이어폰",
            "category": "earphone",
            "brand": "Apple",
            "model": "에어팟 4"
        },
        {
            "original": "베이직스 2024 베이직북 14 N-시리즈BasicWhite · 256GB · 8GB · WIN11 Home",
            "normalized": "베이직스 베이직북 14",
            "category": "laptop",
            "brand": "베이직스",
            "model": "베이직북 14"
        },
        {
            "original": "LG UltraFine OLED Pro 32UP550-W 프로페셔널 모니터",
            "normalized": "LG UltraFine OLED Pro 32UP550",
            "category": "monitor",
            "brand": "LG",
            "model": "UltraFine 32UP550"
        }
    ]
    
    failure_ids = []
    for data in test_data:
        failure = SearchFailureRepository.record_failure(
            db=db,
            original_query=data["original"],
            normalized_query=data["normalized"],
            candidates=[
                data["normalized"],
                f"{data['brand']} {data['model']}",
                data["model"],
                data["brand"]
            ],
            error_message="검색 결과를 찾을 수 없습니다.",
            category_detected=data["category"],
            brand=data["brand"],
            model=data["model"]
        )
        failure_ids.append(failure.id)
    
    return failure_ids


class TestSearchFailureLogging:
    """실패 로깅 테스트"""
    
    def test_record_failure(self, db: Session):
        """실패 기록"""
        failure = SearchFailureRepository.record_failure(
            db=db,
            original_query="테스트 상품",
            normalized_query="테스트",
            candidates=["테스트", "상품"],
            error_message="Not found"
        )
        
        assert failure.id is not None
        assert failure.original_query == "테스트 상품"
        assert failure.is_resolved == "pending"
    
    def test_mark_resolved(self, db: Session, test_failures):
        """실패 해결 표시"""
        failure_id = test_failures[0]
        
        # 수동 수정으로 표시
        resolved = SearchFailureRepository.mark_resolved(
            db=db,
            failure_id=failure_id,
            status="manual_fixed",
            correct_product_name="Apple AirPods 4",
            correct_pcode="12345"
        )
        
        assert resolved.is_resolved == "manual_fixed"
        assert resolved.correct_product_name == "Apple AirPods 4"
        assert resolved.correct_pcode == "12345"
    
    def test_get_by_original_query(self, db: Session, test_failures):
        """원본 쿼리로 조회"""
        failure = SearchFailureRepository.get_by_original_query(
            db=db,
            original_query="Apple 2024 에어팟 4 액티브 노이즈 캔슬링 블루투스 이어폰"
        )
        
        assert failure is not None
        assert failure.category_detected == "earphone"


class TestSearchFailureAnalysis:
    """실패 분석 테스트"""
    
    def test_get_analytics_dashboard(self, db: Session, test_failures):
        """분석 대시보드"""
        dashboard = SearchFailureAnalyzer.get_analytics_dashboard(db)
        
        assert dashboard["stats"]["total"] == 3
        assert dashboard["stats"]["pending"] == 3
        assert dashboard["stats"]["resolved"] == 0
        assert len(dashboard["common_failures"]) > 0
    
    def test_get_common_failures(self, db: Session, test_failures):
        """가장 많은 실패 케이스"""
        # 같은 쿼리로 여러 번 실패 기록
        for _ in range(3):
            SearchFailureRepository.record_failure(
                db=db,
                original_query="Apple 2024 에어팟 4 액티브 노이즈 캔슬링 블루투스 이어폰",
                normalized_query="에어팟 4 이어폰",
                candidates=["에어팟 4"],
                error_message="Not found"
            )
        
        common = SearchFailureRepository.get_common_failures(db, limit=5)
        
        # 가장 많이 실패한 케이스가 최상단에 있는지 확인
        assert len(common) > 0
        assert common[0]["failure_count"] >= 3
    
    def test_export_learning_data_json(self, db: Session, test_failures):
        """학습 데이터 내보내기 (JSON)"""
        data = SearchFailureAnalyzer.export_learning_data(db, format="json")
        
        assert data is not None
        
        import json
        parsed = json.loads(data)
        assert len(parsed) >= 3
        assert "original" in parsed[0]
        assert "normalized" in parsed[0]
    
    def test_export_learning_data_csv(self, db: Session, test_failures):
        """학습 데이터 내보내기 (CSV)"""
        data = SearchFailureAnalyzer.export_learning_data(db, format="csv")
        
        assert data is not None
        assert "original_query" in data or "original" in data
    
    def test_get_improvement_suggestions(self, db: Session):
        """개선 제안"""
        # 같은 패턴으로 5회 이상 실패 기록
        for i in range(5):
            SearchFailureRepository.record_failure(
                db=db,
                original_query="반복되는 실패 패턴",
                normalized_query="반복",
                candidates=["반복"]
            )
        
        suggestions = SearchFailureAnalyzer.get_improvement_suggestions(db)
        
        assert len(suggestions) > 0
        assert suggestions[0]["priority"] == "HIGH"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
