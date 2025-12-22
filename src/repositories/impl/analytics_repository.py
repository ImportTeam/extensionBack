"""분석 Repository - SearchLog 데이터 분석 쿼리"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import func, and_, or_, text
from sqlalchemy.orm import Session

from src.repositories.models import SearchLog


class AnalyticsRepository:
    """검색 로그 분석 쿼리"""

    def __init__(self, db: Session):
        self.db = db

    def get_weekly_stats(self, days: int = 7) -> Dict[str, Any]:
        """주간 통계
        
        Args:
            days: 분석 기간 (기본값: 7일)
            
        Returns:
            Dict: 성공률, 평균 시간, 총 검색 수 등
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 기본 통계
        total_searches = self.db.query(SearchLog).filter(
            SearchLog.created_at >= cutoff_date
        ).count()
        
        if total_searches == 0:
            return {
                "period_days": days,
                "total_searches": 0,
                "success_count": 0,
                "success_rate": 0.0,
                "avg_elapsed_ms": 0.0,
                "cache_hit_count": 0,
                "fastpath_success_count": 0,
                "slowpath_success_count": 0,
                "failure_count": 0,
            }
        
        # 성공한 검색
        successful = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.status == "SUCCESS"
            )
        ).count()
        
        # 실패한 검색
        failed = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.status.in_(["FAIL", "ERROR"])
            )
        ).count()
        
        # 평균 소요 시간
        avg_time = self.db.query(func.avg(SearchLog.elapsed_ms)).filter(
            SearchLog.created_at >= cutoff_date
        ).scalar() or 0.0
        
        # 출처별 통계
        cache_hits = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.source == "cache",
                SearchLog.status == "SUCCESS"
            )
        ).count()
        
        fastpath_success = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.source == "fastpath",
                SearchLog.status == "SUCCESS"
            )
        ).count()
        
        slowpath_success = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.source == "slowpath",
                SearchLog.status == "SUCCESS"
            )
        ).count()
        
        return {
            "period_days": days,
            "total_searches": total_searches,
            "success_count": successful,
            "success_rate": round(successful / total_searches * 100, 2) if total_searches > 0 else 0.0,
            "avg_elapsed_ms": round(avg_time, 2),
            "cache_hit_count": cache_hits,
            "fastpath_success_count": fastpath_success,
            "slowpath_success_count": slowpath_success,
            "failure_count": failed,
        }

    def get_success_rate_by_source(self, days: int = 7) -> List[Dict[str, Any]]:
        """출처별 성공률
        
        Args:
            days: 분석 기간
            
        Returns:
            List: 출처별 성공/전체/성공률
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        sources = ["cache", "fastpath", "slowpath"]
        results = []
        
        for source in sources:
            total = self.db.query(SearchLog).filter(
                and_(
                    SearchLog.created_at >= cutoff_date,
                    SearchLog.source == source
                )
            ).count()
            
            success = self.db.query(SearchLog).filter(
                and_(
                    SearchLog.created_at >= cutoff_date,
                    SearchLog.source == source,
                    SearchLog.status == "SUCCESS"
                )
            ).count()
            
            avg_time = self.db.query(func.avg(SearchLog.elapsed_ms)).filter(
                and_(
                    SearchLog.created_at >= cutoff_date,
                    SearchLog.source == source
                )
            ).scalar() or 0.0
            
            results.append({
                "source": source,
                "total": total,
                "success": success,
                "success_rate": round(success / total * 100, 2) if total > 0 else 0.0,
                "avg_elapsed_ms": round(avg_time, 2),
            })
        
        return results

    def get_failed_queries(self, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """실패한 검색어 분석 (가장 자주 실패한 쿼리들)
        
        Args:
            days: 분석 기간
            limit: 조회 제한
            
        Returns:
            List: 실패한 쿼리, 실패 횟수, 마지막 시도
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        results = self.db.query(
            SearchLog.query_name,
            func.count(SearchLog.id).label("fail_count"),
            func.max(SearchLog.created_at).label("last_attempt"),
        ).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.status.in_(["FAIL", "ERROR"])
            )
        ).group_by(
            SearchLog.query_name
        ).order_by(
            func.count(SearchLog.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "query": query,
                "fail_count": count,
                "last_attempt": last_attempt.isoformat() if last_attempt else None,
            }
            for query, count, last_attempt in results
        ]

    def get_trending_queries(self, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """인기 검색어 (가장 많이 검색된 쿼리들)
        
        Args:
            days: 분석 기간
            limit: 조회 제한
            
        Returns:
            List: 검색어, 검색 횟수, 성공 횟수, 성공률
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        results = self.db.query(
            SearchLog.query_name,
            func.count(SearchLog.id).label("total_count"),
            func.sum(func.cast(SearchLog.status == "SUCCESS", type_=int)).label("success_count"),
        ).filter(
            SearchLog.created_at >= cutoff_date
        ).group_by(
            SearchLog.query_name
        ).order_by(
            func.count(SearchLog.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "query": query,
                "total_count": total,
                "success_count": success or 0,
                "success_rate": round((success or 0) / total * 100, 2) if total > 0 else 0.0,
            }
            for query, total, success in results
        ]

    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """성능 메트릭
        
        Args:
            days: 분석 기간
            
        Returns:
            Dict: 평균/최소/최대 응답시간, 50/95/99 percentile
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        results = self.db.query(SearchLog.elapsed_ms).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.elapsed_ms.isnot(None)
            )
        ).all()
        
        if not results:
            return {
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }
        
        times = sorted([r[0] for r in results])
        n = len(times)
        
        return {
            "avg_ms": round(sum(times) / n, 2),
            "min_ms": round(times[0], 2),
            "max_ms": round(times[-1], 2),
            "p50_ms": round(times[int(n * 0.5)], 2),
            "p95_ms": round(times[int(n * 0.95)], 2),
            "p99_ms": round(times[int(n * 0.99)], 2),
        }

    def get_price_diff_analysis(self, days: int = 7) -> Dict[str, Any]:
        """가격 차이 분석 (현재가 vs 최저가)
        
        Args:
            days: 분석 기간
            
        Returns:
            Dict: 평균 절감액, 절감율, 절감 건수
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        results = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.status == "SUCCESS",
                SearchLog.origin_price.isnot(None),
                SearchLog.found_price.isnot(None),
            )
        ).all()
        
        if not results:
            return {
                "total_saved": 0,
                "avg_saved_amount": 0.0,
                "avg_saved_rate": 0.0,
                "min_saved_amount": 0,
                "max_saved_amount": 0,
                "count": 0,
            }
        
        differences = [
            r.origin_price - r.found_price
            for r in results
            if r.origin_price and r.found_price and r.origin_price > 0
        ]
        
        if not differences:
            return {
                "total_saved": 0,
                "avg_saved_amount": 0.0,
                "avg_saved_rate": 0.0,
                "min_saved_amount": 0,
                "max_saved_amount": 0,
                "count": 0,
            }
        
        total_saved = sum(differences)
        avg_saved = total_saved / len(differences)
        
        # 절감율 계산
        saved_rates = [
            (r.origin_price - r.found_price) / r.origin_price * 100
            for r in results
            if r.origin_price and r.found_price and r.origin_price > 0
        ]
        avg_saved_rate = sum(saved_rates) / len(saved_rates) if saved_rates else 0.0
        
        return {
            "total_saved": int(total_saved),
            "avg_saved_amount": round(avg_saved, 2),
            "avg_saved_rate": round(avg_saved_rate, 2),
            "min_saved_amount": int(min(differences)),
            "max_saved_amount": int(max(differences)),
            "count": len(differences),
        }

    def get_problematic_product_ids(self, days: int = 7, limit: int = 15) -> List[Dict[str, Any]]:
        """문제가 되는 상품 ID (실패 빈도 높은)
        
        Args:
            days: 분석 기간
            limit: 조회 제한
            
        Returns:
            List: pcode, 실패 횟수, 마지막 시도, 최근 상품명
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        results = self.db.query(
            SearchLog.product_id,
            func.count(SearchLog.id).label("total_count"),
            func.sum(func.cast(SearchLog.status == "SUCCESS", type_=int)).label("success_count"),
            func.max(SearchLog.created_at).label("last_attempt"),
            func.max(SearchLog.query_name).label("recent_query"),
        ).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.product_id.isnot(None),
                SearchLog.product_id != ""
            )
        ).group_by(
            SearchLog.product_id
        ).order_by(
            func.count(SearchLog.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "product_id": pcode,
                "total_attempts": total,
                "success_count": success or 0,
                "failure_count": total - (success or 0),
                "failure_rate": round((total - (success or 0)) / total * 100, 2) if total > 0 else 0.0,
                "last_attempt": last_attempt.isoformat() if last_attempt else None,
                "recent_query": recent_query,
            }
            for pcode, total, success, last_attempt, recent_query in results
        ]

    def get_options_effectiveness(self, days: int = 7) -> Dict[str, Any]:
        """옵션 효율성 분석 (쿼리명에 옵션이 포함된 경우)
        
        Args:
            days: 분석 기간
            
        Returns:
            Dict: 옵션 포함 검색 성공률 vs 옵션 미포함 검색 성공률
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 옵션 포함 (query_name에 '[' 포함)
        with_options_total = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.query_name.contains("[")
            )
        ).count()
        
        with_options_success = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                SearchLog.query_name.contains("["),
                SearchLog.status == "SUCCESS"
            )
        ).count()
        
        # 옵션 미포함
        without_options_total = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                ~SearchLog.query_name.contains("[")
            )
        ).count()
        
        without_options_success = self.db.query(SearchLog).filter(
            and_(
                SearchLog.created_at >= cutoff_date,
                ~SearchLog.query_name.contains("["),
                SearchLog.status == "SUCCESS"
            )
        ).count()
        
        return {
            "with_options": {
                "total": with_options_total,
                "success": with_options_success,
                "success_rate": round(with_options_success / with_options_total * 100, 2) if with_options_total > 0 else 0.0,
            },
            "without_options": {
                "total": without_options_total,
                "success": without_options_success,
                "success_rate": round(without_options_success / without_options_total * 100, 2) if without_options_total > 0 else 0.0,
            },
            "improvement": round(
                (with_options_success / with_options_total * 100 if with_options_total > 0 else 0) -
                (without_options_success / without_options_total * 100 if without_options_total > 0 else 0),
                2
            ),
        }
