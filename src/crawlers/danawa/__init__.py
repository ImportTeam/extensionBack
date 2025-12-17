"""Danawa crawler modules (hybrid HTTP + Playwright).

공개 API는 이 파일에서만 export합니다.

구조:
- core/ : DanawaCrawler + orchestrator
- metrics/ : Circuit Breaker + 메트릭
- boundary/ : HTTP Fast Path + Timeout Manager
- playwright/ : Playwright 관리 (브라우저, 페이지, 검색, 상세)
"""

from .core import DanawaCrawler

__all__ = ["DanawaCrawler"]
