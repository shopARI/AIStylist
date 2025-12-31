#!/bin/bash
# Comprehensive Test Runner Script
# Runs all tests with coverage and generates reports

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "ARI CrewAI Migration - Test Suite"
echo "========================================"

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source ../crewai_env/bin/activate
fi

# Parse command line arguments
TEST_TYPE=${1:-all}
COVERAGE=${2:-true}

echo -e "\nTest Type: $TEST_TYPE"
echo -e "Coverage: $COVERAGE\n"

# Function to run tests
run_tests() {
    local test_path=$1
    local test_name=$2

    echo -e "${GREEN}Running $test_name...${NC}"

    if [ "$COVERAGE" = "true" ]; then
        python -m pytest $test_path -v --tb=short \
            --cov=nlp --cov=crews \
            --cov-report=term-missing \
            --cov-report=html:htmlcov/$test_name
    else
        python -m pytest $test_path -v --tb=short
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}$test_name PASSED${NC}\n"
    else
        echo -e "${RED}$test_name FAILED${NC}\n"
        return 1
    fi
}

# Run tests based on type
case $TEST_TYPE in
    unit)
        echo "========================================"
        echo "Running Unit Tests Only"
        echo "========================================"
        run_tests "tests/unit/" "Unit Tests"
        ;;

    integration)
        echo "========================================"
        echo "Running Integration Tests Only"
        echo "========================================"
        run_tests "tests/integration/test_intent_detection_comprehensive.py" "Integration Tests (Pattern-Based)"
        ;;

    crewai)
        echo "========================================"
        echo "Running CrewAI Agent Tests"
        echo "========================================"
        echo -e "${YELLOW}Note: Requires OpenAI API key${NC}\n"
        run_tests "tests/integration/test_crewai_agent_detection.py" "CrewAI Agent Tests"
        ;;

    e2e)
        echo "========================================"
        echo "Running E2E Tests"
        echo "========================================"
        run_tests "tests/e2e/" "E2E Tests"
        ;;

    all)
        echo "========================================"
        echo "Running All Tests"
        echo "========================================"

        # Run unit tests
        run_tests "tests/unit/" "Unit Tests" || true

        # Run integration tests (pattern-based)
        run_tests "tests/integration/test_intent_detection_comprehensive.py" "Integration Tests" || true

        # Summary
        echo "========================================"
        echo "Test Summary"
        echo "========================================"
        python -m pytest tests/unit/ tests/integration/test_intent_detection_comprehensive.py --tb=no -q
        ;;

    quick)
        echo "========================================"
        echo "Quick Test Run (Unit Tests Only)"
        echo "========================================"
        python -m pytest tests/unit/ -q --tb=line
        ;;

    *)
        echo -e "${RED}Unknown test type: $TEST_TYPE${NC}"
        echo "Usage: ./run_tests.sh [unit|integration|crewai|e2e|all|quick] [true|false]"
        exit 1
        ;;
esac

# Generate coverage report if enabled
if [ "$COVERAGE" = "true" ] && [ "$TEST_TYPE" != "quick" ]; then
    echo "========================================"
    echo "Coverage Report"
    echo "========================================"

    # Generate XML for CI/CD
    python -m pytest tests/unit/ --cov=nlp --cov=crews --cov-report=xml --cov-report=term -q

    echo -e "\n${GREEN}Coverage reports generated:${NC}"
    echo "  - Terminal: (above)"
    echo "  - HTML: htmlcov/index.html"
    echo "  - XML: coverage.xml"
fi

echo -e "\n${GREEN}Test run complete!${NC}"
