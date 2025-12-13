"""검색 실패 분석 및 학습 서비스"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.repositories.search_failure_repository import SearchFailureRepository
from src.core.logging import logger


class SearchFailureAnalyzer:
    """검색 실패 패턴 분석 및 학습"""
    
    @staticmethod
    def get_analytics_dashboard(db: Session) -> Dict:
        """분석 대시보드"""
        stats = SearchFailureRepository.get_failure_stats(db)
        common = SearchFailureRepository.get_common_failures(db, limit=20)
        
        return {
            "stats": stats,
            "common_failures": common,
            "resolution_rate": (
                (stats["resolved"] / stats["total"] * 100) 
                if stats["total"] > 0 else 0
            ),
            "pending_rate": (
                (stats["pending"] / stats["total"] * 100) 
                if stats["total"] > 0 else 0
            )
        }
    
    @staticmethod
    def get_category_analysis(db: Session) -> Dict[str, any]:
        """카테고리별 분석"""
        dashboard = SearchFailureAnalyzer.get_analytics_dashboard(db)
        
        analysis = {}
        for category_stat in dashboard["stats"]["by_category"]:
            cat = category_stat["category"]
            analysis[cat] = {
                "failure_count": category_stat["count"],
                "resolution_rate": 0  # 추후 개선
            }
        
        return analysis
    
    @staticmethod
    def export_learning_data(
        db: Session,
        format: str = "json"
    ) -> Optional[str]:
        """
        학습용 데이터 내보내기
        
        Format options:
        - json: JSON 형식
        - csv: CSV 형식
        """
        failures = SearchFailureRepository.get_recent_failures(
            db, days=30, limit=500
        )
        
        if not failures:
            logger.warning("No failures to export")
            return None
        
        if format == "json":
            import json
            data = [
                {
                    "id": f.id,
                    "original": f.original_query,
                    "normalized": f.normalized_query,
                    "category": f.category_detected,
                    "brand": f.brand,
                    "model": f.model,
                    "candidates": json.loads(f.candidates),
                    "error": f.error_message,
                    "status": f.is_resolved,
                    "created": f.created_at.isoformat()
                }
                for f in failures
            ]
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "id", "original", "normalized", "category", 
                    "brand", "model", "error", "status", "created"
                ]
            )
            writer.writeheader()
            
            for f in failures:
                writer.writerow({
                    "id": f.id,
                    "original": f.original_query,
                    "normalized": f.normalized_query,
                    "category": f.category_detected,
                    "brand": f.brand,
                    "model": f.model,
                    "error": f.error_message,
                    "status": f.is_resolved,
                    "created": f.created_at.isoformat()
                })
            
            return output.getvalue()
        
        return None
    
    @staticmethod
    def get_improvement_suggestions(db: Session) -> List[Dict]:
        """개선 제안"""
        common = SearchFailureRepository.get_common_failures(db, limit=10)
        suggestions = []
        
        for failure in common:
            if failure["failure_count"] >= 3:  # 3회 이상 반복되는 패턴
                suggestions.append({
                    "type": "pattern",
                    "pattern": failure["original_query"],
                    "normalized": failure["normalized_query"],
                    "category": failure["category"],
                    "occurrences": failure["failure_count"],
                    "suggestion": f"Consider adding special handling for pattern: {failure['original_query']}",
                    "priority": "HIGH" if failure["failure_count"] >= 5 else "MEDIUM"
                })
        
        return suggestions
