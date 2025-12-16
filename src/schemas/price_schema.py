"""Pydantic 스키마 정의"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class PriceSearchRequest(BaseModel):
    """최저가 검색 요청"""
    product_name: str = Field(..., min_length=1, description="검색할 상품명")
    current_price: Optional[int] = Field(None, ge=0, description="현재 가격")
    current_url: Optional[str] = Field(None, description="현재 URL")
    product_code: Optional[str] = Field(None, description="다나와 상품 코드(pcode)")


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
    is_cheaper: bool = Field(..., description="더 저렴한지 여부")
    price_diff: int = Field(..., description="가격 차이")
    lowest_price: int = Field(..., ge=0, description="최저가")
    link: str = Field(..., description="상품 링크")
    mall: str | None = Field(None, description="최저가 쇼핑몰")
    free_shipping: bool | None = Field(None, description="최저가 무료배송 여부")
    top_prices: list[MallPrice] | None = Field(None, description="쇼핑몰별 최저가 Top N")
    price_trend: list[PriceTrendPoint] | None = Field(None, description="최저가 추이")


class PriceSearchResponse(BaseModel):
    """최저가 검색 응답"""
    status: str = Field(..., description="success or fail")
    data: Optional[PriceData] = Field(None, description="가격 정보")
    message: str = Field(..., description="응답 메시지")


class CachedPrice(BaseModel):
    """캐시된 가격 정보"""
    product_name: str
    lowest_price: int
    link: str
    source: str
    mall: str | None = None
    free_shipping: bool | None = None
    top_prices: list[MallPrice] | None = None
    price_trend: list[PriceTrendPoint] | None = None
    updated_at: str


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
