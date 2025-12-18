"""Crawler Result Standard Format

크롤러 실행 결과의 표준 형식을 정의합니다.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class CrawlResult:
    """크롤링 결과 표준 포맷

    Attributes:
        product_url: 상품 상세 페이지 URL
        price: 최저가 (정수)
        product_name: 상품명 (선택사항)
        metadata: 추가 메타데이터 (선택사항)
    """

    product_url: str
    price: int
    product_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlResult":
        """딕셔너리에서 CrawlResult 생성

        Args:
            data: 크롤링 결과 데이터

        Returns:
            CrawlResult 인스턴스
        """
        return cls(
            product_url=data["product_url"],
            price=data["price"],
            product_name=data.get("product_name"),
            metadata=data.get("metadata"),
        )
