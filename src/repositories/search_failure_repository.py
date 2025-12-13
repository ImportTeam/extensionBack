"""검색 실패 기록 저장소"""
import json
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from src.repositories.models.search_failure import SearchFailure


class SearchFailureRepository:
    """검색 실패 데이터 접근 계층"""
    
    @staticmethod
    def record_failure(
        db: Session,
        original_query: str,
        normalized_query: str,
        candidates: List[str],
        attempted_count: int = 1,
        error_message: Optional[str] = None,
        category_detected: Optional[str] = None,
        brand: Optional[str] = None,
        model: Optional[str] = None
    ) -> SearchFailure:
        """검색 실패 기록"""
        failure = SearchFailure(
            original_query=original_query,
            normalized_query=normalized_query,
            candidates=json.dumps(candidates, ensure_ascii=False),
            attempted_count=attempted_count,
            error_message=error_message,
            category_detected=category_detected,
            brand=brand,
            model=model
        )
        db.add(failure)
        db.commit()
        db.refresh(failure)
        return failure
    
    @staticmethod
    def get_by_original_query(
        db: Session,
        original_query: str
    ) -> Optional[SearchFailure]:
        """원본 쿼리로 조회"""
        return db.query(SearchFailure).filter(
            SearchFailure.original_query == original_query
        ).first()
    
    @staticmethod
    def get_recent_failures(
        db: Session,
        days: int = 7,
        limit: int = 100
    ) -> List[SearchFailure]:
        """최근 실패 기록 조회"""
        since = datetime.utcnow() - timedelta(days=days)
        return db.query(SearchFailure).filter(
            SearchFailure.created_at >= since,
            SearchFailure.is_resolved == "pending"
        ).order_by(
            desc(SearchFailure.created_at)
        ).limit(limit).all()
    
    @staticmethod
    def mark_resolved(
        db: Session,
        failure_id: int,
        status: str = "manual_fixed",
        correct_product_name: Optional[str] = None,
        correct_pcode: Optional[str] = None
    ) -> SearchFailure:
        """실패 기록을 해결됨으로 표시"""
        failure = db.query(SearchFailure).filter(
            SearchFailure.id == failure_id
        ).first()
        
        if failure:
            failure.is_resolved = status
            if correct_product_name:
                failure.correct_product_name = correct_product_name
            if correct_pcode:
                failure.correct_pcode = correct_pcode
            failure.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(failure)
        
        return failure
    
    @staticmethod
    def get_failure_stats(db: Session) -> dict:
        """실패 통계"""
        total = db.query(func.count(SearchFailure.id)).scalar()
        pending = db.query(func.count(SearchFailure.id)).filter(
            SearchFailure.is_resolved == "pending"
        ).scalar()
        resolved = db.query(func.count(SearchFailure.id)).filter(
            SearchFailure.is_resolved != "pending"
        ).scalar()
        
        # 카테고리별 통계
        by_category = db.query(
            SearchFailure.category_detected,
            func.count(SearchFailure.id).label('count')
        ).filter(
            SearchFailure.is_resolved == "pending"
        ).group_by(
            SearchFailure.category_detected
        ).order_by(
            desc('count')
        ).all()
        
        return {
            "total": total or 0,
            "pending": pending or 0,
            "resolved": resolved or 0,
            "by_category": [
                {"category": cat or "unknown", "count": cnt}
                for cat, cnt in by_category
            ]
        }
    
    @staticmethod
    def get_common_failures(
        db: Session,
        limit: int = 20
    ) -> List[dict]:
        """가장 많은 실패 케이스"""
        results = db.query(
            SearchFailure.original_query,
            SearchFailure.normalized_query,
            SearchFailure.category_detected,
            func.count(SearchFailure.id).label('failure_count')
        ).filter(
            SearchFailure.is_resolved == "pending"
        ).group_by(
            SearchFailure.original_query,
            SearchFailure.normalized_query,
            SearchFailure.category_detected
        ).order_by(
            desc('failure_count')
        ).limit(limit).all()
        
        return [
            {
                "original_query": r[0],
                "normalized_query": r[1],
                "category": r[2],
                "failure_count": r[3]
            }
            for r in results
        ]
