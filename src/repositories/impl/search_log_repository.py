"""검색 로그 리포지토리 - DB 접근 로직"""
from typing import List, Optional, Any, cast
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from src.repositories.models import SearchLog
from src.core.logging import logger
from src.core.exceptions import DatabaseException

class SearchLogRepository:
    """검색 로그 데이터 액세스 레이어"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        query_name: str,
        origin_price: Optional[int],
        found_price: Optional[int],
        status: str
    ) -> SearchLog:
        """검색 로그 생성"""
        try:
            log = SearchLog(
                query_name=query_name,
                origin_price=origin_price,
                found_price=found_price,
                status=status
            )
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            logger.info(f"Search log created: {log.id}")
            return log
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create search log: {e}")
            raise DatabaseException(f"Failed to create search log: {e}")
    
    def get_by_id(self, log_id: int) -> Optional[SearchLog]:
        """ID로 로그 조회"""
        return self.db.query(SearchLog).filter(SearchLog.id == log_id).first()
    
    def get_total_count(self) -> int:
        """전체 검색 횟수"""
        return self.db.query(func.count(SearchLog.id)).scalar() or 0
    
    def get_cache_hit_count(self) -> int:
        """캐시 히트 횟수"""
        return self.db.query(func.count(SearchLog.id)).filter(
            SearchLog.status == "HIT"
        ).scalar() or 0
    
    def get_popular_queries(self, limit: int = 5) -> List[tuple[str, int]]:
        """인기 검색어 조회 ([(query_name, count), ...])"""
        rows: List[Any] = self.db.query(
            SearchLog.query_name,
            func.count(SearchLog.id).label('count')
        ).group_by(
            SearchLog.query_name
        ).order_by(
            desc('count')
        ).limit(limit).all()

        return [
            (
                cast(str, getattr(row, "query_name", "")),
                int(cast(Any, getattr(row, "count", 0)))
            )
            for row in rows
        ]
    
    def get_recent_logs(self, limit: int = 10) -> List[SearchLog]:
        """최근 로그 조회"""
        return self.db.query(SearchLog).order_by(
            desc(SearchLog.created_at)
        ).limit(limit).all()
    
    def get_logs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[SearchLog]:
        """기간별 로그 조회"""
        return self.db.query(SearchLog).filter(
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date
        ).all()
    
    def get_statistics(self, days: int = 7) -> dict:
        """통계 정보"""
        start_date = datetime.now() - timedelta(days=days)
        
        total = self.db.query(func.count(SearchLog.id)).filter(
            SearchLog.created_at >= start_date
        ).scalar() or 0
        
        hits = self.db.query(func.count(SearchLog.id)).filter(
            SearchLog.created_at >= start_date,
            SearchLog.status == "HIT"
        ).scalar() or 0
        
        misses = self.db.query(func.count(SearchLog.id)).filter(
            SearchLog.created_at >= start_date,
            SearchLog.status == "MISS"
        ).scalar() or 0
        
        fails = self.db.query(func.count(SearchLog.id)).filter(
            SearchLog.created_at >= start_date,
            SearchLog.status == "FAIL"
        ).scalar() or 0
        
        return {
            "period_days": days,
            "total_searches": total,
            "cache_hits": hits,
            "cache_misses": misses,
            "failures": fails,
            "hit_rate": round((hits / total * 100), 2) if total > 0 else 0
        }
