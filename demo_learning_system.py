"""
검색 실패 학습 시스템 데모
실제 동작하는 예제를 보여줍니다
"""
from sqlalchemy.orm import Session
from src.core.database import SessionLocal, engine, Base
from src.repositories.search_failure_repository import SearchFailureRepository
from src.services.search_failure_analyzer import SearchFailureAnalyzer
import json


def demo_record_failures():
    """예제 1: 실패 기록 저장"""
    print("\n" + "="*70)
    print("📝 예제 1: 검색 실패 기록 저장")
    print("="*70)
    
    db = SessionLocal()
    
    # 시뮬레이션: 실제 실패 패턴들
    test_cases = [
        {
            "original": "Apple 2024 에어팟 4 액티브 노이즈 캔슬링 블루투스 이어폰",
            "normalized": "에어팟 4 이어폰",
            "category": "earphone",
            "brand": "Apple",
            "model": "에어팟 4",
            "error": "No products found"
        },
        {
            "original": "베이직스 2024 베이직북 14 N-시리즈BasicWhite · 256GB · 8GB · WIN11 Home",
            "normalized": "베이직스 베이직북 14",
            "category": "laptop",
            "brand": "베이직스",
            "model": "베이직북 14",
            "error": "No products found"
        },
        {
            "original": "LG UltraFine OLED Pro 32UP550-W 프로페셔널 모니터",
            "normalized": "LG UltraFine OLED Pro 32UP550",
            "category": "monitor",
            "brand": "LG",
            "model": "UltraFine 32UP550",
            "error": "No products found"
        }
    ]
    
    for case in test_cases:
        failure = SearchFailureRepository.record_failure(
            db=db,
            original_query=case["original"],
            normalized_query=case["normalized"],
            candidates=[
                case["normalized"],
                f"{case['brand']} {case['model']}",
                case["model"],
                case["brand"]
            ],
            error_message=case["error"],
            category_detected=case["category"],
            brand=case["brand"],
            model=case["model"]
        )
        print(f"✅ 저장됨: {case['original'][:40]}...")
    
    db.close()
    print(f"\n📊 총 {len(test_cases)}개 실패 기록 저장 완료")


def demo_analyze_failures():
    """예제 2: 실패 분석"""
    print("\n" + "="*70)
    print("📊 예제 2: 실패 패턴 분석")
    print("="*70)
    
    db = SessionLocal()
    
    # 같은 패턴으로 여러 번 실패 기록
    print("\n🔄 같은 패턴으로 반복되는 실패 시뮬레이션...")
    for i in range(3):
        SearchFailureRepository.record_failure(
            db=db,
            original_query="Apple 2024 에어팟 4 액티브 노이즈 캔슬링 블루투스 이어폰",
            normalized_query="에어팟 4 이어폰",
            candidates=["에어팟 4 이어폰", "Apple 에어팟 4"],
            error_message="No products found"
        )
    
    # 대시보드 조회
    dashboard = SearchFailureAnalyzer.get_analytics_dashboard(db)
    
    print("\n📈 대시보드 통계:")
    print(f"  • 총 실패: {dashboard['stats']['total']}건")
    print(f"  • 미해결: {dashboard['stats']['pending']}건")
    print(f"  • 해결됨: {dashboard['stats']['resolved']}건")
    print(f"  • 해결율: {dashboard['resolution_rate']:.1f}%")
    
    print("\n📌 카테고리별 분석:")
    for cat in dashboard['stats']['by_category']:
        print(f"  • {cat['category']}: {cat['count']}건")
    
    db.close()


def demo_common_patterns():
    """예제 3: 반복되는 실패 패턴 발견"""
    print("\n" + "="*70)
    print("🔍 예제 3: 반복되는 실패 패턴")
    print("="*70)
    
    db = SessionLocal()
    
    common = SearchFailureRepository.get_common_failures(db, limit=5)
    
    if common:
        print("\n🔴 가장 많은 실패 케이스 (PRIORITY: HIGH):")
        for i, failure in enumerate(common, 1):
            print(f"\n  {i}. 원본: {failure['original_query'][:50]}...")
            print(f"     정규화: {failure['normalized_query']}")
            print(f"     카테고리: {failure['category']}")
            print(f"     반복 횟수: {failure['failure_count']}회")
    
    db.close()


def demo_improvement_suggestions():
    """예제 4: 개선 제안"""
    print("\n" + "="*70)
    print("💡 예제 4: 개선 제안 생성")
    print("="*70)
    
    db = SessionLocal()
    
    # 5회 이상 반복되는 패턴 생성
    for i in range(5):
        SearchFailureRepository.record_failure(
            db=db,
            original_query="반복되는 실패 패턴",
            normalized_query="반복 패턴",
            candidates=["반복 패턴"]
        )
    
    suggestions = SearchFailureAnalyzer.get_improvement_suggestions(db)
    
    if suggestions:
        print("\n📋 개선 제안:")
        for suggestion in suggestions:
            print(f"\n  🎯 {suggestion['suggestion']}")
            print(f"     패턴: {suggestion['pattern']}")
            print(f"     발생 횟수: {suggestion['occurrences']}회")
            print(f"     우선순위: {suggestion['priority']}")
    
    db.close()


def demo_export_data():
    """예제 5: 학습 데이터 내보내기"""
    print("\n" + "="*70)
    print("💾 예제 5: 학습 데이터 내보내기")
    print("="*70)
    
    db = SessionLocal()
    
    # JSON 형식
    print("\n📄 JSON 형식 내보내기:")
    json_data = SearchFailureAnalyzer.export_learning_data(db, format="json")
    if json_data:
        data = json.loads(json_data)
        print(f"  ✓ {len(data)}개 기록 내보냄")
        if data:
            print(f"  첫 번째 레코드:")
            print(f"    - original: {data[0]['original'][:40]}...")
            print(f"    - normalized: {data[0]['normalized']}")
            print(f"    - category: {data[0]['category']}")
    
    # CSV 형식
    print("\n📊 CSV 형식 내보내기:")
    csv_data = SearchFailureAnalyzer.export_learning_data(db, format="csv")
    if csv_data:
        lines = csv_data.split('\n')
        print(f"  ✓ {len(lines)-2}개 기록 내보냄 (+ 헤더)")
        print(f"  첫 줄: {lines[0]}")
    
    db.close()


def demo_resolve_failure():
    """예제 6: 실패 기록 해결"""
    print("\n" + "="*70)
    print("✅ 예제 6: 실패 기록 해결 표시")
    print("="*70)
    
    db = SessionLocal()
    
    # 수동 수정 케이스
    failure = SearchFailureRepository.record_failure(
        db=db,
        original_query="테스트 상품",
        normalized_query="테스트",
        candidates=["테스트"]
    )
    
    print(f"\n원본 상태:")
    print(f"  • ID: {failure.id}")
    print(f"  • 상태: {failure.is_resolved}")
    
    # 수동 수정
    resolved = SearchFailureRepository.mark_resolved(
        db=db,
        failure_id=failure.id,
        status="manual_fixed",
        correct_product_name="올바른 상품명",
        correct_pcode="12345"
    )
    
    print(f"\n해결 후 상태:")
    print(f"  • ID: {resolved.id}")
    print(f"  • 상태: {resolved.is_resolved}")
    print(f"  • 올바른 상품명: {resolved.correct_product_name}")
    print(f"  • pcode: {resolved.correct_pcode}")
    
    db.close()


def main():
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "🎓 검색 실패 학습 시스템 - 데모" + " "*23 + "║")
    print("╚" + "="*68 + "╝")
    
    demo_record_failures()
    demo_analyze_failures()
    demo_common_patterns()
    demo_improvement_suggestions()
    demo_export_data()
    demo_resolve_failure()
    
    print("\n" + "="*70)
    print("✅ 모든 데모 완료!")
    print("="*70)
    print("\n💡 다음 단계:")
    print("  1. 서버 시작: python main.py")
    print("  2. API 호출:")
    print("     curl http://localhost:8000/api/analytics/dashboard")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
