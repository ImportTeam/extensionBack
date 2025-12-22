"""분석 Service - 비즈니스 로직"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from src.repositories.impl.analytics_repository import AnalyticsRepository
from src.core.logging import logger


class AnalyticsService:
    """검색 데이터 분석 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = AnalyticsRepository(db)

    def generate_weekly_report(self) -> Dict[str, Any]:
        """주간 분석 리포트 생성
        
        Returns:
            Dict: 주간 통계, 성공률, 성능, 트렌드 등 종합 리포트
        """
        logger.info("[Analytics] Generating weekly report")
        
        try:
            weekly_stats = self.repository.get_weekly_stats(days=7)
            source_stats = self.repository.get_success_rate_by_source(days=7)
            failed_queries = self.repository.get_failed_queries(days=7, limit=20)
            trending_queries = self.repository.get_trending_queries(days=7, limit=20)
            performance = self.repository.get_performance_metrics(days=7)
            price_analysis = self.repository.get_price_diff_analysis(days=7)
            options_effectiveness = self.repository.get_options_effectiveness(days=7)
            
            report = {
                "generated_at": datetime.utcnow().isoformat(),
                "period": "7_days",
                "summary": weekly_stats,
                "by_source": source_stats,
                "performance": performance,
                "price_savings": price_analysis,
                "options_effectiveness": options_effectiveness,
                "top_queries": trending_queries,
                "failed_queries": failed_queries,
            }
            
            logger.info(f"[Analytics] Weekly report generated: success_rate={weekly_stats.get('success_rate')}%")
            return report
            
        except Exception as e:
            logger.error(f"[Analytics] Failed to generate weekly report: {e}", exc_info=True)
            raise

    def get_improvement_recommendations(self) -> Dict[str, Any]:
        """크롤링 개선 권장사항 도출
        
        Returns:
            Dict: 개선 포인트들
        """
        logger.info("[Analytics] Analyzing improvement recommendations")
        
        try:
            failed_queries = self.repository.get_failed_queries(days=7, limit=50)
            source_stats = self.repository.get_success_rate_by_source(days=7)
            product_issues = self.repository.get_problematic_product_ids(days=7, limit=30)
            options_effect = self.repository.get_options_effectiveness(days=7)
            
            recommendations = {
                "timestamp": datetime.utcnow().isoformat(),
                "recommendations": [],
            }
            
            # 1. 낮은 성공률 검사
            overall_success_rate = None
            for stat in source_stats:
                if stat["source"] == "fastpath":
                    if stat["success_rate"] < 70:
                        recommendations["recommendations"].append({
                            "type": "fastpath_improvement",
                            "priority": "high",
                            "message": f"FastPath 성공률이 낮음: {stat['success_rate']}% (목표: 85%+)",
                            "action": "FastPath 검색 로직 및 필터링 규칙 검토 필요",
                            "data": stat,
                        })
            
            # 2. 실패한 검색어 분석
            if failed_queries:
                top_failed = failed_queries[:10]
                recommendations["recommendations"].append({
                    "type": "failed_queries_pattern",
                    "priority": "high",
                    "message": f"상위 10개 실패 쿼리 감지 ({len(failed_queries)}개 총 실패)",
                    "action": "해당 쿼리들에 대해 검색 후보 전략 조정",
                    "data": top_failed,
                })
            
            # 3. 문제 상품 ID 분석
            if product_issues:
                critical_products = [p for p in product_issues if p.get("failure_rate", 0) > 50]
                if critical_products:
                    recommendations["recommendations"].append({
                        "type": "problematic_products",
                        "priority": "medium",
                        "message": f"문제 상품 감지: {len(critical_products)}개 상품이 50% 이상 실패율",
                        "action": "해당 상품 페이지 구조 분석 및 크롤러 업데이트",
                        "data": critical_products[:5],
                    })
            
            # 4. 옵션 효율성 분석
            if options_effect.get("improvement", 0) > 0:
                recommendations["recommendations"].append({
                    "type": "options_improvement",
                    "priority": "high",
                    "message": f"옵션 포함 검색이 더 효과적: +{options_effect['improvement']}% 개선",
                    "action": "사용자에게 더 많은 옵션 입력을 유도 (UI/UX 개선)",
                    "data": options_effect,
                })
            elif options_effect.get("improvement", 0) < -5:
                recommendations["recommendations"].append({
                    "type": "options_issue",
                    "priority": "medium",
                    "message": f"옵션 포함 검색이 오히려 낮음: {options_effect['improvement']}%",
                    "action": "옵션 필터링 로직 검토 필요",
                    "data": options_effect,
                })
            
            # 5. 성능 개선
            perf = self.repository.get_performance_metrics(days=7)
            if perf.get("p99_ms", 0) > 10000:  # P99가 10초 이상
                recommendations["recommendations"].append({
                    "type": "performance",
                    "priority": "medium",
                    "message": f"응답 시간이 느림: P99={perf['p99_ms']}ms (목표: <5000ms)",
                    "action": "느린 쿼리 최적화, 캐시 전략 검토",
                    "data": perf,
                })
            
            logger.info(f"[Analytics] Generated {len(recommendations['recommendations'])} recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"[Analytics] Failed to generate recommendations: {e}", exc_info=True)
            raise

    def get_daily_snapshot(self, days: int = 1) -> Dict[str, Any]:
        """일일 스냅샷 (대시보드용)
        
        Args:
            days: 분석 기간
            
        Returns:
            Dict: 간단한 통계
        """
        try:
            stats = self.repository.get_weekly_stats(days=days)
            source_stats = self.repository.get_success_rate_by_source(days=days)
            perf = self.repository.get_performance_metrics(days=days)
            price = self.repository.get_price_diff_analysis(days=days)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "period_days": days,
                "total_searches": stats["total_searches"],
                "success_rate": stats["success_rate"],
                "cache_hit_rate": round(stats["cache_hit_count"] / stats["total_searches"] * 100, 2) if stats["total_searches"] > 0 else 0.0,
                "avg_response_time_ms": perf["avg_ms"],
                "total_saved_amount": price["total_saved"],
                "avg_saved_rate": price["avg_saved_rate"],
                "source_breakdown": source_stats,
            }
            
        except Exception as e:
            logger.error(f"[Analytics] Failed to get daily snapshot: {e}", exc_info=True)
            raise
