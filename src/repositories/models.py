"""데이터베이스 모델"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Index
from src.core.database import Base


class SearchLog(Base):
    """검색 로그 테이블"""
    
    __tablename__ = "search_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    query_name = Column(String, nullable=False, index=True)
    origin_price = Column(Integer, nullable=True)
    found_price = Column(Integer, nullable=True)
    status = Column(String, nullable=False, index=True)  # HIT, MISS, FAIL
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    
    # 복합 인덱스 (통계 쿼리 최적화)
    __table_args__ = (
        Index('idx_status_created', 'status', 'created_at'),
        Index('idx_query_created', 'query_name', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<SearchLog(id={self.id}, query={self.query_name}, status={self.status})>"
