"""검색 실패 분석 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.services.impl.search_failure_analyzer import SearchFailureAnalyzer
from src.repositories.impl.search_failure_repository import SearchFailureRepository
from src.core.logging import logger

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
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


@router.get("/common-failures")
async def get_common_failures(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """가장 많은 실패 케이스"""
    try:
        failures = SearchFailureRepository.get_common_failures(db, limit=limit)
        return {"failures": failures}
    except Exception as e:
        logger.error(f"Error getting common failures: {e}")
        raise HTTPException(status_code=500, detail="Failed to get common failures")


@router.get("/category-analysis")
async def get_category_analysis(db: Session = Depends(get_db)):
    """카테고리별 분석"""
    try:
        analysis = SearchFailureAnalyzer.get_category_analysis(db)
        return analysis
    except Exception as e:
        logger.error(f"Error getting category analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to get category analysis")


@router.get("/improvements")
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


@router.get("/export")
async def export_learning_data(
    format: str = "json",
    db: Session = Depends(get_db)
):
    """
    학습용 데이터 내보내기
    
    Query Params:
    - format: json | csv
    """
    if format not in ["json", "csv"]:
        raise HTTPException(status_code=400, detail="Invalid format")
    
    try:
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


@router.post("/resolve/{failure_id}")
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
