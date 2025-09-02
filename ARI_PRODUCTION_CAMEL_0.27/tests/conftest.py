"""
Pytest configuration and fixtures for ARI Fashion AI System tests
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Set test environment
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LOG_LEVEL", "WARNING")  # Reduce logging noise in tests
os.environ.setdefault("NEO4J_PASSWORD", "test_password")
os.environ.setdefault("OPENAI_API_KEY", "test_api_key")

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies for all tests."""
    with pytest.MonkeyPatch.context() as m:
        # Mock Redis
        mock_redis_service = MagicMock()
        mock_redis_service.initialize = AsyncMock(return_value=True)
        mock_redis_service.close = AsyncMock()
        mock_redis_service.health_check = AsyncMock(return_value=True)
        mock_redis_service.get_stats.return_value = {
            "operations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "is_healthy": True
        }
        
        # Mock Neo4j
        mock_neo4j_service = MagicMock()
        mock_neo4j_service.initialize = AsyncMock(return_value=True)
        mock_neo4j_service.close = AsyncMock()
        mock_neo4j_service.run_query = AsyncMock(return_value=[])
        
        # Mock Qdrant
        mock_qdrant_service = MagicMock()
        mock_qdrant_service.initialize = AsyncMock(return_value=True)
        mock_qdrant_service.close = AsyncMock()
        
        # Mock Application Service
        mock_app_service = MagicMock()
        mock_response = MagicMock()
        mock_response.response = "Test response"
        mock_response.products = []
        mock_response.session_id = "test_session"
        mock_response.metadata = {}
        mock_response.model_dump.return_value = {
            "response": "Test response",
            "products": [],
            "session_id": "test_session",
            "metadata": {}
        }
        mock_app_service.process_message = AsyncMock(return_value=mock_response)
        
        # Apply mocks
        m.setattr("services.cache.redis_client.create_redis_service", lambda **kwargs: mock_redis_service)
        m.setattr("services.user.knowledge_graph.UserKnowledgeGraphService", mock_neo4j_service)
        m.setattr("services.product.retriever.ProductRetrieverService", mock_qdrant_service)
        
        yield {
            'redis': mock_redis_service,
            'neo4j': mock_neo4j_service,
            'qdrant': mock_qdrant_service,
            'app_service': mock_app_service
        }

@pytest.fixture
def mock_container():
    """Mock DI container for tests."""
    container = MagicMock()
    
    # Mock services
    container.redis_client.return_value = MagicMock()
    container.user_kg_service.return_value = MagicMock()
    container.product_retriever_service.return_value = MagicMock()
    container.application_service.return_value = MagicMock()
    
    return container

@pytest.fixture
def test_settings():
    """Test configuration settings."""
    from config.settings import Settings
    
    # Override with test values
    test_env = {
        "ENVIRONMENT": "testing",
        "NEO4J_URL": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "test_password",
        "OPENAI_API_KEY": "test_api_key",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "LOG_LEVEL": "WARNING"
    }
    
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    settings = Settings()
    
    yield settings
    
    # Restore original environment
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

@pytest.fixture
def sample_chat_message():
    """Sample chat message for testing."""
    return {
        "message": "I'm looking for a red dress for a party",
        "session_id": "test_session_123",
        "user_id": "test_user_456"
    }

@pytest.fixture
def sample_product():
    """Sample product data for testing."""
    return {
        "id": "prod_123",
        "title": "Red Party Dress",
        "description": "Beautiful red dress perfect for parties",
        "price": 89.99,
        "category": "Dresses",
        "brand": "Fashion Brand",
        "images": ["https://example.com/image1.jpg"],
        "colors": ["red"],
        "sizes": ["S", "M", "L"],
        "tags": ["party", "elegant"],
        "in_stock": True
    }

@pytest.fixture
def sample_user_profile():
    """Sample user profile for testing."""
    return {
        "id": "user_123",
        "created_at": "2024-01-01T00:00:00Z",
        "last_active": "2024-01-15T12:00:00Z",
        "email": "test@example.com",
        "name": "Test User",
        "preferences": {
            "preferred_categories": ["Dresses", "Tops"],
            "preferred_brands": ["Fashion Brand"],
            "preferred_colors": ["red", "blue"],
            "budget_range": {"min": 50, "max": 150}
        },
        "segments": ["New Customer"],
        "total_interactions": 5,
        "total_purchases": 1,
        "lifetime_value": 89.99
    }

@pytest.fixture
def mock_memory_service():
    """Mock memory service for testing."""
    service = MagicMock()
    service.is_memory_healthy.return_value = True
    service.get_memory_stats.return_value = {
        "process_memory_mb": 50.0,
        "system_memory_percent": 65.0,
        "tracked_objects": 100,
        "cleanup_runs": 5,
        "cached_objects": 50,
        "memory_threshold_mb": 80.0,
        "max_memory_mb": 100.0
    }
    service.track_session = MagicMock()
    service.remove_session = MagicMock()
    service.cache_object = MagicMock()
    service.get_cached_object = MagicMock(return_value=None)
    service.force_cleanup = MagicMock()
    
    return service

# Custom markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may be slow)"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast)"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security-related tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )

# Test data cleanup
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data after each test."""
    yield
    # Any cleanup logic here
    pass

# Async test helpers
@pytest.fixture
def async_mock():
    """Create async mock helper."""
    def _async_mock(*args, **kwargs):
        mock = MagicMock(*args, **kwargs)
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=None)
        return mock
    return _async_mock

# Performance test configuration
@pytest.fixture
def performance_config():
    """Configuration for performance tests."""
    return {
        "max_response_time": 1.0,  # seconds
        "max_memory_mb": 100,
        "max_cpu_percent": 80
    }

# Database test fixtures
@pytest.fixture
def mock_neo4j_data():
    """Mock Neo4j data for testing."""
    return {
        "users": [
            {"id": "user_1", "name": "Test User 1"},
            {"id": "user_2", "name": "Test User 2"}
        ],
        "interactions": [
            {"user_id": "user_1", "product_id": "prod_1", "type": "view"},
            {"user_id": "user_1", "product_id": "prod_2", "type": "purchase"}
        ]
    }

@pytest.fixture
def mock_qdrant_data():
    """Mock Qdrant data for testing."""
    return {
        "products": [
            {
                "id": "prod_1",
                "vector": [0.1, 0.2, 0.3],
                "metadata": {"title": "Product 1", "price": 50.0}
            },
            {
                "id": "prod_2", 
                "vector": [0.4, 0.5, 0.6],
                "metadata": {"title": "Product 2", "price": 75.0}
            }
        ]
    }

@pytest.fixture
def mock_redis_data():
    """Mock Redis data for testing."""
    return {
        "session:test_123": {
            "history": ["Hello", "Looking for dress"],
            "created_at": "2024-01-01T00:00:00Z",
            "user_id": "user_123"
        },
        "cache:product_123": {
            "id": "prod_123",
            "title": "Cached Product",
            "cached_at": "2024-01-01T00:00:00Z"
        }
    }