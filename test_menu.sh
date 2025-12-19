#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_menu() {
    echo -e "\n${BLUE}=== importBack 테스트 메뉴 ===${NC}\n"
    echo "1. 📝 Unit Tests (API 기본 기능)"
    echo "2. 📦 Coverage Tests (전체 파이프라인)"
    echo "3. ⚡ Stress Tests (고부하 성능)"
    echo "4. 🎯 E2E Tests (실제 시나리오)"
    echo "5. ✅ 모든 테스트"
    echo "6. 📊 테스트 개요 (collect only)"
    echo "7. 🔧 특정 테스트 검색"
    echo "0. 종료"
    echo -e "\n선택 (0-7): "
}

run_unit_tests() {
    echo -e "\n${YELLOW}Unit Tests 실행 중...${NC}"
    pytest tests/unit/test_api_basic.py -v --tb=short
}

run_coverage_tests() {
    echo -e "\n${YELLOW}Coverage Tests 실행 중...${NC}"
    pytest tests/coverage/test_integration_full_pipeline.py -v --tb=short
}

run_stress_tests() {
    echo -e "\n${YELLOW}Stress Tests 실행 중...${NC}"
    pytest tests/stress/test_performance_stress.py -v --tb=short -s
}

run_e2e_tests() {
    echo -e "\n${YELLOW}E2E Tests 실행 중...${NC}"
    pytest tests/E2E/test_e2e_real_scenarios.py -v --tb=short -s
}

run_all_tests() {
    echo -e "\n${YELLOW}모든 테스트 실행 중...${NC}"
    pytest tests/ -v --tb=short
}

collect_tests() {
    echo -e "\n${BLUE}테스트 개요:${NC}\n"
    pytest tests/ --collect-only -q
}

search_test() {
    echo -e "\n${BLUE}검색 키워드 입력:${NC} "
    read keyword
    echo -e "\n${YELLOW}'$keyword' 검색 중...${NC}\n"
    pytest tests/ --collect-only -q | grep -i "$keyword"
    
    echo -e "\n${YELLOW}실행하시겠습니까? (y/n):${NC} "
    read confirm
    if [ "$confirm" = "y" ]; then
        pytest tests/ -k "$keyword" -v --tb=short
    fi
}

# 메인 루프
while true; do
    show_menu
    read choice
    
    case $choice in
        1) run_unit_tests ;;
        2) run_coverage_tests ;;
        3) run_stress_tests ;;
        4) run_e2e_tests ;;
        5) run_all_tests ;;
        6) collect_tests ;;
        7) search_test ;;
        0) 
            echo -e "\n${GREEN}종료합니다.${NC}"
            exit 0
            ;;
        *)
            echo -e "\n${RED}잘못된 선택입니다.${NC}"
            ;;
    esac
done
