"""
API Integration Tests for ARI Fashion AI System
Tests main API endpoints, security, and functionality
"""

import pytest
import asyncio
import time
from httpx import AsyncClient
from fastapi.testclient import TestClient
import json
from unittest.mock import AsyncMock, MagicMock, patch

# Import the app
from main import app

@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)

@pytest.fixture
async def async_client():
    """Async test client fixture."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns correct message."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "ARI Fashion AI System is operational."
    
    def test_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "memory_healthy" in data
        assert "version" in data
        assert data["version"] == "4.0.0"
    
    def test_detailed_health_check(self, client):
        """Test detailed health check endpoint."""
        response = client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "memory_stats" in data
        assert "system_stats" in data
        assert "health_checks" in data
    
    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        content = response.text
        assert "ari_memory_usage_mb" in content
        assert "ari_tracked_objects" in content

class TestInputValidation:
    """Test input validation and security."""
    
    def test_chat_valid_input(self, client):
        """Test chat endpoint with valid input."""
        valid_payload = {
            "message": "Hello, I'm looking for a dress",
            "session_id": "test_session_123",
            "user_id": "test_user_123"
        }
        
        # Mock the application service
        with patch('main.app.state.container.application_service') as mock_service:
            mock_response = MagicMock()
            mock_response.response = "Hello! I'd love to help you find a dress."
            mock_response.products = []
            mock_response.session_id = "test_session_123"
            mock_response.metadata = {}
            
            mock_service.return_value.process_message = AsyncMock(return_value=mock_response)
            
            response = client.post("/chat", json=valid_payload)
            assert response.status_code == 200
    
    def test_chat_empty_message(self, client):
        """Test chat endpoint rejects empty message."""
        invalid_payload = {
            "message": "",
            "session_id": "test_session_123",
            "user_id": "test_user_123"
        }
        
        response = client.post("/chat", json=invalid_payload)
        assert response.status_code == 422  # Validation error
    
    def test_chat_long_message(self, client):
        """Test chat endpoint rejects overly long message."""
        invalid_payload = {
            "message": "x" * 2001,  # Exceeds MAX_MESSAGE_LENGTH
            "session_id": "test_session_123",
            "user_id": "test_user_123"
        }
        
        response = client.post("/chat", json=invalid_payload)
        assert response.status_code == 422
    
    def test_chat_xss_attempt(self, client):
        """Test chat endpoint rejects XSS attempts."""
        xss_payload = {
            "message": "<script>alert('xss')</script>",
            "session_id": "test_session_123",
            "user_id": "test_user_123"
        }
        
        response = client.post("/chat", json=xss_payload)
        assert response.status_code == 422
    
    def test_chat_invalid_session_id(self, client):
        """Test chat endpoint rejects invalid session ID."""
        invalid_payload = {
            "message": "Hello",
            "session_id": "test_session_123!@#",  # Invalid characters
            "user_id": "test_user_123"
        }
        
        response = client.post("/chat", json=invalid_payload)
        assert response.status_code == 422
    
    def test_chat_missing_fields(self, client):
        """Test chat endpoint requires all fields."""
        incomplete_payload = {
            "message": "Hello"
            # Missing session_id and user_id
        }
        
        response = client.post("/chat", json=incomplete_payload)
        assert response.status_code == 422

class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_chat_rate_limit(self, client):
        """Test chat endpoint rate limiting."""
        payload = {
            "message": "Hello",
            "session_id": "test_session_rate",
            "user_id": "test_user_rate"
        }
        
        # Mock the application service
        with patch('main.app.state.container.application_service') as mock_service:
            mock_response = MagicMock()
            mock_response.response = "Hello!"
            mock_response.products = []
            mock_response.session_id = "test_session_rate"
            mock_response.metadata = {}
            
            mock_service.return_value.process_message = AsyncMock(return_value=mock_response)
            
            # Make requests up to the limit (10/minute)
            responses = []
            for i in range(12):  # Try to exceed limit
                response = client.post("/chat", json=payload)
                responses.append(response.status_code)
                time.sleep(0.1)  # Small delay
            
            # Some requests should be rate limited
            assert 429 in responses  # Rate limited status
    
    def test_health_detailed_rate_limit(self, client):
        """Test detailed health check rate limiting."""
        # Make requests up to the limit (5/minute)
        responses = []
        for i in range(7):  # Try to exceed limit
            response = client.get("/health/detailed")
            responses.append(response.status_code)
        
        # Some requests should be rate limited
        assert 429 in responses

class TestCORSHeaders:
    """Test CORS configuration."""
    
    def test_cors_headers_present(self, client):
        """Test CORS headers are present in responses."""
        response = client.options("/", headers={"Origin": "http://localhost:3000"})
        
        # Check that CORS headers might be present (depends on middleware setup)
        # This is a basic check - exact headers depend on configuration
        assert response.status_code in [200, 405]  # OPTIONS might not be allowed
    
    def test_cors_allowed_origin(self, client):
        """Test requests from allowed origins."""
        response = client.get("/", headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 200

class TestWebSocketSecurity:
    """Test WebSocket security and validation."""
    
    @pytest.mark.asyncio
    async def test_websocket_invalid_session_id(self):
        """Test WebSocket rejects invalid session ID."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with pytest.raises(Exception):
                # This should fail due to invalid session ID
                async with client.websocket_connect("/ws/invalid!@#session"):
                    pass
    
    @pytest.mark.asyncio
    async def test_websocket_long_session_id(self):
        """Test WebSocket rejects overly long session ID."""
        long_session_id = "x" * 101  # Exceeds MAX_SESSION_ID_LENGTH
        async with AsyncClient(app=app, base_url="http://test") as client:
            with pytest.raises(Exception):
                async with client.websocket_connect(f"/ws/{long_session_id}"):
                    pass

class TestErrorHandling:
    """Test error handling and responses."""
    
    def test_404_endpoint(self, client):
        """Test 404 handling for non-existent endpoints."""
        response = client.get("/non_existent_endpoint")
        assert response.status_code == 404
    
    def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON."""
        response = client.post(
            "/chat",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_missing_content_type(self, client):
        """Test handling of missing content type."""
        response = client.post("/chat", data='{"message": "test"}')
        assert response.status_code in [422, 415]

class TestDataValidation:
    """Test data validation and sanitization."""
    
    def test_message_trimming(self, client):
        """Test that messages are properly trimmed."""
        payload = {
            "message": "  Hello world  ",  # Extra whitespace
            "session_id": "test_session",
            "user_id": "test_user"
        }
        
        with patch('main.app.state.container.application_service') as mock_service:
            mock_response = MagicMock()
            mock_response.response = "Hello!"
            mock_response.products = []
            mock_response.session_id = "test_session"
            mock_response.metadata = {}
            
            mock_service.return_value.process_message = AsyncMock(return_value=mock_response)
            
            response = client.post("/chat", json=payload)
            assert response.status_code == 200
            
            # Check that the service was called with trimmed message
            call_args = mock_service.return_value.process_message.call_args
            assert call_args.kwargs['message'] == 'Hello world'  # Trimmed
    
    def test_dangerous_patterns_blocked(self, client):
        """Test that dangerous patterns are blocked."""
        dangerous_messages = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "onload=alert(1)",
            "onerror=alert(1)"
        ]
        
        for message in dangerous_messages:
            payload = {
                "message": message,
                "session_id": "test_session",
                "user_id": "test_user"
            }
            
            response = client.post("/chat", json=payload)
            assert response.status_code == 422

# Performance and Load Testing
class TestPerformance:
    """Basic performance tests."""
    
    def test_health_check_response_time(self, client):
        """Test health check responds quickly."""
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond within 1 second
    
    def test_metrics_response_time(self, client):
        """Test metrics endpoint responds quickly."""
        start_time = time.time()
        response = client.get("/metrics")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 2.0  # Should respond within 2 seconds

# Configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])