"""Danawa crawler modules (hybrid HTTP + Playwright).

구조:
- crawler.py : DanawaCrawler (진입점, SRP 유지)
- orchestrator.py : 오케스트레이션 로직 (HTTP → Playwright)
- metrics/ : Circuit Breaker + 메트릭
- boundary/ : HTTP Fast Path + Timeout Manager
- playwright/ : Playwright 관리 (브라우저, 페이지, 검색, 상세)
"""

from .crawler import DanawaCrawler

__all__ = ["DanawaCrawler"]
