"""테스트 자산(데이터) 레이어

규칙:
- 로직 없음 (단순 dict/list/primitive)
- 엔진/네트워크 의존 없음
"""

from .products import PRODUCTS
from .api_payloads import API_PAYLOADS
from .bot_scenarios import BOT_SCENARIOS
from .cache_cases import CACHE_CASES

__all__ = [
    "PRODUCTS",
    "API_PAYLOADS",
    "BOT_SCENARIOS",
    "CACHE_CASES",
]
