"""데이터베이스 모델"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Index, Text, DateTime, Float
from src.core.database import Base


class SearchLog(Base):
    """검색 로그 테이블"""
    
    __tablename__ = "search_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    query_name = Column(String, nullable=False, index=True)
    origin_price = Column(Integer, nullable=True)
    found_price = Column(Integer, nullable=True)
    product_id = Column(String, nullable=True, index=True)  # pcode 등
    status = Column(String, nullable=False, index=True)  # HIT, MISS, FAIL
    source = Column(String, nullable=True)  # cache, fastpath, slowpath
    elapsed_ms = Column(Float, nullable=True)  # 검색 소요 시간
    top_prices = Column(Text, nullable=True)  # JSON: TOP 3 가격 목록 (크롤링 강화용)
    price_trend = Column(Text, nullable=True)  # JSON: 가격 변동 추이
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


class SearchFailure(Base):
    """검색 실패 기록 (학습 데이터)"""
    
    __tablename__ = "search_failures"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 사용자 입력
    original_query = Column(String(255), nullable=False, index=True)  # 원본 상품명
    normalized_query = Column(String(255), nullable=False)  # 정규화된 상품명
    
    # 검색 시도 정보
    candidates = Column(Text, nullable=False)  # JSON: 시도한 후보들
    attempted_count = Column(Integer, default=1)  # 시도 횟수
    
    # 메타 정보
    error_message = Column(String(512), nullable=True)  # 에러 메시지
    category_detected = Column(String(50), nullable=True)  # 감지된 카테고리
    brand = Column(String(100), nullable=True)  # 추출된 브랜드
    model = Column(String(100), nullable=True)  # 추출된 모델명
    
    # 사용자 피드백 (향후)
    is_resolved = Column(String(50), default="pending")  # pending, manual_fixed, auto_learned, not_product
    correct_product_name = Column(String(255), nullable=True)  # 사용자가 수정한 올바른 상품명
    correct_pcode = Column(String(20), nullable=True)  # 올바른 pcode
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<SearchFailure(id={self.id}, query={self.original_query[:30]})>"
