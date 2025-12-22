"""매주 분석 리포트 생성 스케줄러"""

from datetime import datetime
import asyncio
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.core.database import SessionLocal
from src.services.impl.analytics_service import AnalyticsService


class WeeklyAnalyticsScheduler:
    """주간 분석 리포트 생성 스케줄러"""
    
    @staticmethod
    async def run_weekly_analysis():
        """주간 분석 실행"""
        db = SessionLocal()
        try:
            logger.info("[Scheduler] Starting weekly analysis report generation...")
            
            service = AnalyticsService(db)
            
            # 1. 주간 리포트 생성
            report = service.generate_weekly_report()
            logger.info(f"[Scheduler] Weekly report generated: success_rate={report['summary'].get('success_rate')}%")
            
            # 2. 개선 권장사항 생성
            recommendations = service.get_improvement_recommendations()
            logger.info(f"[Scheduler] Generated {len(recommendations.get('recommendations', []))} recommendations")
            
            # 3. 결과를 로그에 저장 (실제로는 별도 테이블에 저장 가능)
            _log_weekly_analysis(report, recommendations)
            
            logger.info("[Scheduler] Weekly analysis completed successfully")
            return {
                "status": "success",
                "report": report,
                "recommendations": recommendations,
            }
            
        except Exception as e:
            logger.error(f"[Scheduler] Failed to run weekly analysis: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }
        finally:
            db.close()
    
    @staticmethod
    def schedule_with_apscheduler():
        """APScheduler를 사용한 스케줄링 설정"""
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = BackgroundScheduler()
        
        # 매주 월요일 09:00에 실행
        scheduler.add_job(
            WeeklyAnalyticsScheduler.run_weekly_analysis,
            trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
            id="weekly_analysis",
            name="Weekly Analytics Report",
            replace_existing=True,
        )
        
        logger.info("[Scheduler] Weekly analysis job scheduled for every Monday at 09:00")
        return scheduler


def _log_weekly_analysis(report: dict, recommendations: dict):
    """분석 결과를 로그에 저장"""
    logger.info("[Analytics Report] " + "="*80)
    logger.info(f"[Analytics Report] Generated: {report.get('generated_at')}")
    logger.info("[Analytics Report] SUMMARY:")
    
    summary = report.get("summary", {})
    logger.info(f"  - Total searches: {summary.get('total_searches')}")
    logger.info(f"  - Success rate: {summary.get('success_rate')}%")
    logger.info(f"  - Cache hit: {summary.get('cache_hit_count')}")
    logger.info(f"  - FastPath success: {summary.get('fastpath_success_count')}")
    logger.info(f"  - SlowPath success: {summary.get('slowpath_success_count')}")
    logger.info(f"  - Avg response time: {summary.get('avg_elapsed_ms')}ms")
    
    logger.info("[Analytics Report] PERFORMANCE:")
    perf = report.get("performance", {})
    logger.info(f"  - P50: {perf.get('p50_ms')}ms")
    logger.info(f"  - P95: {perf.get('p95_ms')}ms")
    logger.info(f"  - P99: {perf.get('p99_ms')}ms")
    
    logger.info("[Analytics Report] PRICE SAVINGS:")
    price = report.get("price_savings", {})
    logger.info(f"  - Total saved: ₩{price.get('total_saved'):,}")
    logger.info(f"  - Avg saved: ₩{price.get('avg_saved_amount'):,.0f}")
    logger.info(f"  - Avg rate: {price.get('avg_saved_rate')}%")
    
    logger.info("[Analytics Report] RECOMMENDATIONS:")
    for i, rec in enumerate(recommendations.get("recommendations", []), 1):
        logger.info(f"  {i}. [{rec.get('type')}] {rec.get('message')}")
        logger.info(f"     Action: {rec.get('action')}")
    
    logger.info("[Analytics Report] " + "="*80)


# 수동 테스트용
if __name__ == "__main__":
    import asyncio
    result = asyncio.run(WeeklyAnalyticsScheduler.run_weekly_analysis())
    print(result)
