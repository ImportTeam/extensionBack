"""검색 실패 분석 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.services.impl.search_failure_analyzer import SearchFailureAnalyzer
from src.repositories.impl.search_failure_repository import SearchFailureRepository
from src.services.impl.analytics_service import AnalyticsService
from src.core.logging import logger
from src.core.security import SecurityValidator
from src.core.exceptions import ValidationException
from datetime import datetime

analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@analytics_router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """
    분석 대시보드
    
    Return:
    {
        "stats": {
            "total": 150,
            "pending": 45,
            "resolved": 105,
            "by_category": [
                {"category": "earphone", "count": 20},
                ...
            ]
        },
        "common_failures": [...],
        "resolution_rate": 70.0,
        "pending_rate": 30.0
    }
    """
    try:
        dashboard = SearchFailureAnalyzer.get_analytics_dashboard(db)
        return dashboard
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard")


@analytics_router.get("/common-failures")
async def get_common_failures(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """가장 많은 실패 케이스"""
    try:
        # 입력 검증: limit은 1-500 범위
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            raise HTTPException(
                status_code=400,
                detail="limit must be between 1 and 500"
            )
        
        failures = SearchFailureRepository.get_common_failures(db, limit=limit)
        return {"failures": failures}
    except HTTPException:
        raise
    except ValidationException as e:
        logger.warning(f"Validation error: {e.error_code}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting common failures: {e}")
        raise HTTPException(status_code=500, detail="Failed to get common failures")


@analytics_router.get("/category-analysis")
async def get_category_analysis(db: Session = Depends(get_db)):
    """카테고리별 분석"""
    try:
        analysis = SearchFailureAnalyzer.get_category_analysis(db)
        return analysis
    except Exception as e:
        logger.error(f"Error getting category analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to get category analysis")


@analytics_router.get("/improvements")
async def get_improvement_suggestions(db: Session = Depends(get_db)):
    """개선 제안"""
    try:
        suggestions = SearchFailureAnalyzer.get_improvement_suggestions(db)
        return {
            "suggestions": suggestions,
            "total": len(suggestions)
        }
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get suggestions")


@analytics_router.get("/export")
async def export_learning_data(
    format: str = "json",
    db: Session = Depends(get_db)
):
    """
    학습용 데이터 내보내기
    
    Query Params:
    - format: json | csv
    """
    try:
        # 입력 검증: format 값 검증 및 보안 체크
        if format not in ["json", "csv"]:
            raise HTTPException(status_code=400, detail="Invalid format")
        
        # format 값이 안전한 문자열인지 확인
        try:
            SecurityValidator.validate_query(format)
        except ValueError as e:
            logger.warning(f"Security validation failed for format: {e}")
            raise HTTPException(status_code=400, detail="Invalid format parameter")
        
        data = SearchFailureAnalyzer.export_learning_data(db, format=format)
        
        if not data:
            raise HTTPException(status_code=404, detail="No data to export")
        
        if format == "json":
            import json
            return json.loads(data)
        else:
            return {"csv": data}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail="Failed to export data")


@analytics_router.post("/resolve/{failure_id}")
async def resolve_failure(
    failure_id: int,
    status: str,
    correct_product_name: Optional[str] = None,
    correct_pcode: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    실패 기록 해결됨으로 표시
    
    Args:
    - failure_id: 실패 기록 ID
    - status: manual_fixed | auto_learned | not_product
    - correct_product_name: 올바른 상품명 (선택)
    - correct_pcode: 올바른 pcode (선택)
    """
    try:
        failure = SearchFailureRepository.mark_resolved(
            db,
            failure_id,
            status=status,
            correct_product_name=correct_product_name,
            correct_pcode=correct_pcode
        )
        
        if not failure:
            raise HTTPException(status_code=404, detail="Failure not found")
        
        return {
            "id": failure.id,
            "status": failure.is_resolved,
            "message": "Success"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving failure: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve failure")


# ========================= NEW: 주간 분석 리포트 API =========================


@analytics_router.get("/v2/weekly-report")
async def get_weekly_report(db: Session = Depends(get_db)):
    """주간 분석 리포트
    
    Returns:
        - 총 검색 수, 성공률, 평균 응답시간
        - 출처별 성공률 (cache/fastpath/slowpath)
        - 인기 검색어, 실패한 검색어
        - 가격 절감 분석
        - 옵션 효율성 분석
    """
    try:
        service = AnalyticsService(db)
        report = service.generate_weekly_report()
        
        return {
            "status": "success",
            "data": report,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[Analytics] Failed to get weekly report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"분석 생성 실패: {str(e)}")


@analytics_router.get("/v2/recommendations")
async def get_improvement_recommendations(db: Session = Depends(get_db)):
    """크롤링 개선 권장사항
    
    Returns:
        - FastPath 성공률 개선 권장
        - 실패한 검색어 패턴
        - 문제 상품 식별
        - 옵션 효율성 인사이트
        - 성능 최적화 포인트
    """
    try:
        service = AnalyticsService(db)
        recommendations = service.get_improvement_recommendations()
        
        return {
            "status": "success",
            "data": recommendations,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[Analytics] Failed to get recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"권장사항 생성 실패: {str(e)}")


@analytics_router.get("/v2/daily-snapshot")
async def get_daily_snapshot(days: Optional[int] = 1, db: Session = Depends(get_db)):
    """일일 스냅샷 (대시보드용)
    
    Args:
        days: 분석 기간 (기본값: 1일)
        
    Returns:
        - 총 검색 수
        - 성공률
        - 캐시 히트율
        - 평균 응답시간
        - 절감액 합계
        - 출처별 분석
    """
    try:
        if days < 1 or days > 30:
            raise ValueError("days는 1~30 사이여야 합니다")
        
        service = AnalyticsService(db)
        snapshot = service.get_daily_snapshot(days=days)
        
        return {
            "status": "success",
            "data": snapshot,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Analytics] Failed to get snapshot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"스냅샷 생성 실패: {str(e)}")


@analytics_router.get("/v2/success-rate")
async def get_success_rate(days: Optional[int] = 7, db: Session = Depends(get_db)):
    """출처별 성공률 상세 분석
    
    Args:
        days: 분석 기간 (기본값: 7일)
        
    Returns:
        - cache: 캐시 성공률
        - fastpath: HTTP 크롤러 성공률
        - slowpath: Playwright 크롤러 성공률
    """
    try:
        if days < 1 or days > 30:
            raise ValueError("days는 1~30 사이여야 합니다")
        
        service = AnalyticsService(db)
        stats = service.repository.get_success_rate_by_source(days=days)
        
        return {
            "status": "success",
            "data": {
                "period_days": days,
                "sources": stats,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Analytics] Failed to get success rate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/v2/failed-queries")
async def get_failed_queries(days: Optional[int] = 7, limit: Optional[int] = 20, db: Session = Depends(get_db)):
    """실패한 검색어 분석
    
    Args:
        days: 분석 기간 (기본값: 7일)
        limit: 조회 개수 (기본값: 20)
        
    Returns:
        - 검색어, 실패 횟수, 마지막 시도
    """
    try:
        if days < 1 or days > 30:
            raise ValueError("days는 1~30 사이여야 합니다")
        if limit < 1 or limit > 100:
            raise ValueError("limit는 1~100 사이여야 합니다")
        
        service = AnalyticsService(db)
        failed = service.repository.get_failed_queries(days=days, limit=limit)
        
        return {
            "status": "success",
            "data": {
                "period_days": days,
                "count": len(failed),
                "failed_queries": failed,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Analytics] Failed to get failed queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/v2/trending-queries")
async def get_trending_queries(days: Optional[int] = 7, limit: Optional[int] = 20, db: Session = Depends(get_db)):
    """인기 검색어 분석
    
    Args:
        days: 분석 기간 (기본값: 7일)
        limit: 조회 개수 (기본값: 20)
        
    Returns:
        - 검색어, 총 검색 수, 성공 수, 성공률
    """
    try:
        if days < 1 or days > 30:
            raise ValueError("days는 1~30 사이여야 합니다")
        if limit < 1 or limit > 100:
            raise ValueError("limit는 1~100 사이여야 합니다")
        
        service = AnalyticsService(db)
        trending = service.repository.get_trending_queries(days=days, limit=limit)
        
        return {
            "status": "success",
            "data": {
                "period_days": days,
                "count": len(trending),
                "trending_queries": trending,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Analytics] Failed to get trending queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/v2/performance")
async def get_performance_metrics(days: Optional[int] = 7, db: Session = Depends(get_db)):
    """성능 메트릭 (응답시간 분석)
    
    Args:
        days: 분석 기간 (기본값: 7일)
        
    Returns:
        - 평균, 최소, 최대, 50/95/99 percentile (ms)
    """
    try:
        if days < 1 or days > 30:
            raise ValueError("days는 1~30 사이여야 합니다")
        
        service = AnalyticsService(db)
        perf = service.repository.get_performance_metrics(days=days)
        
        return {
            "status": "success",
            "data": {
                "period_days": days,
                "metrics": perf,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Analytics] Failed to get performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/v2/price-savings")
async def get_price_savings(days: Optional[int] = 7, db: Session = Depends(get_db)):
    """가격 절감 분석
    
    Args:
        days: 분석 기간 (기본값: 7일)
        
    Returns:
        - 총 절감액, 평균 절감액, 절감율, 건수
    """
    try:
        if days < 1 or days > 30:
            raise ValueError("days는 1~30 사이여야 합니다")
        
        service = AnalyticsService(db)
        savings = service.repository.get_price_diff_analysis(days=days)
        
        return {
            "status": "success",
            "data": {
                "period_days": days,
                "analysis": savings,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Analytics] Failed to get price savings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/v2/options-effectiveness")
async def get_options_effectiveness(days: Optional[int] = 7, db: Session = Depends(get_db)):
    """옵션 효율성 분석
    
    Args:
        days: 분석 기간 (기본값: 7일)
        
    Returns:
        - 옵션 포함 vs 미포함 성공률 비교
        - 개선율
    """
    try:
        if days < 1 or days > 30:
            raise ValueError("days는 1~30 사이여야 합니다")
        
        service = AnalyticsService(db)
        effectiveness = service.repository.get_options_effectiveness(days=days)
        
        return {
            "status": "success",
            "data": {
                "period_days": days,
                "analysis": effectiveness,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Analytics] Failed to get options effectiveness: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
