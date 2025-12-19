"""Pydantic 스키마 정의 (Security & Validation Enhanced)"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class PriceSearchRequest(BaseModel):
    """최저가 검색 요청 (입력 검증 강화)"""
    product_name: str = Field(..., min_length=1, max_length=500, description="검색할 상품명")
    current_price: Optional[int] = Field(None, ge=0, le=10**9, description="현재 가격 (0~10억)")
    current_url: Optional[str] = Field(None, max_length=2048, description="현재 URL")
    product_code: Optional[str] = Field(None, max_length=50, description="다나와 상품 코드(pcode)")
    
    @field_validator('product_name')
    @classmethod
    def validate_product_name(cls, v: str) -> str:
        """제품명 검증: 특수문자 제한"""
        if not v or not v.strip():
            raise ValueError('상품명은 공백만으로 구성될 수 없습니다')
        # 위험한 문자 체크 (SQL injection 방지)
        dangerous_chars = ['<', '>', '"', "'", '\\', '\0', '\n', '\r']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f'상품명에 허용되지 않는 문자가 포함되어 있습니다: {char}')
        return v.strip()
    
    @field_validator('current_url')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """URL 검증"""
        if v is None:
            return None
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL은 http:// 또는 https://로 시작해야 합니다')
        return v
    
    @field_validator('product_code')
    @classmethod
    def validate_product_code(cls, v: Optional[str]) -> Optional[str]:
        """제품 코드 검증: 숫자만 허용"""
        if v is None:
            return None
        if not v.isdigit():
            raise ValueError('제품 코드는 숫자만 포함되어야 합니다')
        return v


class MallPrice(BaseModel):
    """쇼핑몰별 가격"""
    rank: int = Field(..., ge=1, description="순위")
    mall: str = Field(..., description="쇼핑몰명")
    price: int = Field(..., ge=0, description="가격")
    free_shipping: bool = Field(..., description="무료배송 여부")
    delivery: str = Field(..., description="배송 정보 원문")
    link: str = Field(..., description="상품 링크")


class PriceTrendPoint(BaseModel):
    """최저가 추이 데이터 포인트"""
    label: str = Field(..., description="구간 라벨 또는 날짜")
    price: int = Field(..., ge=0, description="가격")


class PriceData(BaseModel):
    """가격 정보"""
    product_name: str = Field(..., description="찾은 상품명")
    product_id: str | None = Field(None, description="상품 ID (pcode 등)")
    is_cheaper: bool = Field(..., description="더 저렴한지 여부")
    price_diff: int = Field(..., description="가격 차이")
    lowest_price: int = Field(..., ge=0, description="최저가")
    link: str = Field(..., description="상품 링크")
    mall: str | None = Field(None, description="최저가 쇼핑몰")
    free_shipping: bool | None = Field(None, description="최저가 무료배송 여부")
    top_prices: list[MallPrice] | None = Field(None, description="쇼핑몰별 최저가 Top N")
    price_trend: list[PriceTrendPoint] | None = Field(None, description="최저가 추이")
    
    # Engine Layer 메타데이터
    source: str = Field(..., description="결과 출처: cache | fastpath | slowpath")
    elapsed_ms: float = Field(..., ge=0, description="검색 소요 시간 (밀리초)")


class PriceSearchResponse(BaseModel):
    """최저가 검색 응답"""
    status: str = Field(..., description="success or fail")
    data: Optional[PriceData] = Field(None, description="가격 정보")
    message: str = Field(..., description="응답 메시지")
    error_code: str | None = Field(None, description="에러 코드 (fail 시)")


class CachedPrice(BaseModel):
    """캐시된 가격 정보 (strict typing)"""
    product_name: str = Field(..., description="상품명")
    lowest_price: int = Field(..., ge=0, description="최저가")
    product_url: str = Field(..., description="상품 URL")  # link → product_url로 통일
    source: str = Field(..., description="cache | fastpath | slowpath")
    mall: str | None = Field(None, description="쇼핑몰")
    free_shipping: bool | None = Field(None, description="무료배송")
    top_prices: list[MallPrice] | None = Field(None, description="TOP 가격")
    price_trend: list[PriceTrendPoint] | None = Field(None, description="가격 추이")
    updated_at: str = Field(..., description="업데이트 시간")


class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    status: str
    timestamp: datetime
    version: str


class PopularQuery(BaseModel):
    """인기 검색어"""
    name: str
    count: int


class StatisticsResponse(BaseModel):
    """통계 응답"""
    total_searches: int
    cache_hits: int
    hit_rate: float
    popular_queries: List[PopularQuery]
