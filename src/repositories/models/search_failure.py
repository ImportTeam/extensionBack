"""검색 실패 분석용 모델"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from src.core.database import Base


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
    
    # 타임스탐프
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<SearchFailure(id={self.id}, query={self.original_query[:30]})>"
