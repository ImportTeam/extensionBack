#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   importBack - 프로덕션 급 테스트 실행${NC}"
echo -e "${BLUE}=================================================${NC}\n"

# 1. 환경 확인
echo -e "${YELLOW}[1/6] 환경 확인 중...${NC}"
python_version=$(python --version 2>&1)
echo -e "Python: ${GREEN}$python_version${NC}"

# pytest 확인
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest를 찾을 수 없습니다.${NC}"
    echo "설치: pip install pytest httpx psutil"
    exit 1
fi
echo -e "${GREEN}✓ pytest 확인 완료${NC}"

# 2. 서버 연결 확인
echo -e "\n${YELLOW}[2/6] 서버 연결 확인 중...${NC}"
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓ 서버 연결 성공 (http://localhost:8000)${NC}"
else
    echo -e "${RED}❌ 서버에 연결할 수 없습니다.${NC}"
    echo "실행: python main.py"
    exit 1
fi

# 3. Unit Tests
echo -e "\n${YELLOW}[3/6] Unit Tests 실행 중... (API 기본 기능)${NC}"
pytest tests/unit/test_api_basic.py -v --tb=short
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Unit Tests 완료${NC}"
else
    echo -e "${RED}✗ Unit Tests 실패${NC}"
fi

# 4. Coverage Tests
echo -e "\n${YELLOW}[4/6] Coverage Tests 실행 중... (전체 파이프라인)${NC}"
pytest tests/coverage/test_integration_full_pipeline.py -v --tb=short
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Coverage Tests 완료${NC}"
else
    echo -e "${RED}✗ Coverage Tests 실패${NC}"
fi

# 5. Stress Tests
echo -e "\n${YELLOW}[5/6] Stress Tests 실행 중... (고부하 성능)${NC}"
pytest tests/stress/test_performance_stress.py -v --tb=short -s
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Stress Tests 완료${NC}"
else
    echo -e "${RED}✗ Stress Tests 실패${NC}"
fi

# 6. E2E Tests
echo -e "\n${YELLOW}[6/6] E2E Tests 실행 중... (실제 시나리오)${NC}"
pytest tests/E2E/test_e2e_real_scenarios.py -v --tb=short -s
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ E2E Tests 완료${NC}"
else
    echo -e "${RED}✗ E2E Tests 실패${NC}"
fi

# 완료
echo -e "\n${BLUE}=================================================${NC}"
echo -e "${GREEN}✓ 모든 테스트 실행 완료!${NC}"
echo -e "${BLUE}=================================================${NC}\n"

# 최종 결과
total_tests=$(pytest tests/ --collect-only -q | tail -1 | awk '{print $1}')
echo -e "${BLUE}📊 결과:${NC}"
echo -e "  총 테스트: ${GREEN}$total_tests${NC}"
echo -e "  평가 시간: 20-40분"
echo -e "\n${BLUE}📖 상세 가이드: TESTING_GUIDE.md${NC}\n"
