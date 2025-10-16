"""
Pytest Configuration and Shared Fixtures
"""

import pytest
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/.env')

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')


# Pytest configuration hooks
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow tests")


# Shared fixtures
@pytest.fixture(scope="session")
def env_loaded():
    """Ensure environment is loaded"""
    return os.getenv('OPENAI_API_KEY') is not None


@pytest.fixture
def intent_detector():
    """Provide intent detector instance"""
    from nlp.hybrid_intent_detector import get_hybrid_intent_detector, DetectionStrategy
    return get_hybrid_intent_detector(strategy=DetectionStrategy.HARDCODED_ONLY)


@pytest.fixture
def parameter_extractor():
    """Provide parameter extractor instance"""
    from nlp.parameter_extractor import ParameterExtractor
    return ParameterExtractor()


@pytest.fixture
def mock_intent_detector():
    """Provide mock intent detector"""
    from tests.fixtures.mocks import MockIntentDetector
    return MockIntentDetector()


@pytest.fixture
def mock_product_crew():
    """Provide mock product crew"""
    from tests.fixtures.mocks import MockProductCrew
    return MockProductCrew()


@pytest.fixture
def mock_intelligence_coordinator():
    """Provide mock intelligence coordinator"""
    from tests.fixtures.mocks import MockIntelligenceCoordinator
    return MockIntelligenceCoordinator()


@pytest.fixture
def test_queries():
    """Provide standard test queries"""
    from tests.fixtures.test_data import get_all_test_queries
    return get_all_test_queries()


@pytest.fixture
def edge_case_queries():
    """Provide edge case queries"""
    from tests.fixtures.test_data import EDGE_CASE_QUERIES
    return EDGE_CASE_QUERIES


# Async fixtures
@pytest.fixture
def event_loop():
    """Provide event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Test data fixtures
@pytest.fixture
def sample_product_result():
    """Provide sample product search result"""
    return {
        "products": [
            {
                "id": "test_001",
                "name": "Test Product",
                "price": 49.99,
                "category": "shirts",
            }
        ],
        "reasoning": "Test result",
        "execution_time": 1.0,
    }


@pytest.fixture
def sample_conversation_result():
    """Provide sample conversation result"""
    return {
        "products": [],
        "response": "Test conversation response",
        "reasoning": "Conversation intent detected",
        "metadata": {
            "is_conversation": True,
        }
    }
