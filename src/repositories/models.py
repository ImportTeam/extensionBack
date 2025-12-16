"""데이터베이스 모델"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Index, Text
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


class PriceCache(Base):
    """영속 가격 캐시 테이블 (Redis 미스 시 DB에서 재사용).

    - cache_key: 정규화된 검색 키(서비스에서 사용하는 search_key)
    - payload_json: 크롤러 결과(dict)를 JSON으로 직렬화한 값
    """

    __tablename__ = "price_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, nullable=False, unique=True, index=True)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), index=True)

    __table_args__ = (
        Index("idx_price_cache_key_updated", "cache_key", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<PriceCache(key={self.cache_key}, updated_at={self.updated_at})>"
