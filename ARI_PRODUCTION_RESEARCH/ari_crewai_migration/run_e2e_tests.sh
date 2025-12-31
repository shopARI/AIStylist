#!/bin/bash
# End-to-End Test Runner for Phase 5
# This script checks for available services and runs appropriate tests

set -e

echo "============================================================"
echo "Phase 5: End-to-End Testing with Real Databases"
echo "============================================================"
echo ""

# Load environment variables if available
if [ -f .env.e2e ]; then
    echo "Loading .env.e2e configuration..."
    export $(cat .env.e2e | grep -v '^#' | xargs)
else
    echo "WARNING: .env.e2e not found. Copy .env.e2e.template and configure."
    echo ""
fi

# Check service availability
echo "Checking service availability..."
echo "----------------------------------------"

# Neo4j
if [ -n "$NEO4J_URI" ] && [ -n "$NEO4J_USER" ] && [ -n "$NEO4J_PASSWORD" ]; then
    echo "Neo4j:        Configured"
    NEO4J_OK=true
else
    echo "Neo4j:        Not configured"
    NEO4J_OK=false
fi

# Qdrant
if [ -n "$QDRANT_URL" ] && [ -n "$QDRANT_API_KEY" ]; then
    echo "Qdrant:       Configured"
    QDRANT_OK=true
else
    echo "Qdrant:       Not configured"
    QDRANT_OK=false
fi

# OpenAI
if [ -n "$OPENAI_API_KEY" ]; then
    echo "OpenAI:       Configured"
    OPENAI_OK=true
else
    echo "OpenAI:       Not configured"
    OPENAI_OK=false
fi

# FashionSigLIP
if [ -n "$FASHIONSIG_MODEL_PATH" ] && [ -d "$FASHIONSIG_MODEL_PATH" ]; then
    echo "FashionSigLIP: Available"
    FASHIONSIG_OK=true
else
    echo "WARNING: FashionSigLIP: Not available (optional)"
    FASHIONSIG_OK=false
fi

echo "----------------------------------------"
echo ""

# Determine which tests can run
CAN_RUN_FULL=false
if [ "$NEO4J_OK" = true ] && [ "$QDRANT_OK" = true ] && [ "$OPENAI_OK" = true ]; then
    CAN_RUN_FULL=true
    echo "All required services available - Running full E2E tests"
else
    echo "WARNING: Some services unavailable - Running limited tests"
fi

echo ""
echo "============================================================"
echo "Running End-to-End Tests"
echo "============================================================"
echo ""

# Run tests with appropriate markers
if [ "$CAN_RUN_FULL" = true ]; then
    echo "Running complete E2E test suite..."
    python -m pytest tests/e2e/test_real_database_integration.py -v -s --tb=short
else
    echo "Running tests for available services only..."
    python -m pytest tests/e2e/test_real_database_integration.py -v -s --tb=short
fi

EXIT_CODE=$?

echo ""
echo "============================================================"
echo "E2E Test Summary"
echo "============================================================"

if [ $EXIT_CODE -eq 0 ]; then
    echo "All available tests passed!"
else
    echo "Some tests failed (exit code: $EXIT_CODE)"
fi

echo ""
echo "Next Steps:"
if [ "$CAN_RUN_FULL" = false ]; then
    echo "  1. Configure missing services in .env.e2e"
    echo "  2. Re-run this script to test with all services"
fi
echo "  3. Review PHASE_5_COMPLETION_REPORT.md for findings"
echo "  4. Proceed to Phase 6 (Production Deployment)"
echo ""

exit $EXIT_CODE
