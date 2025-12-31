"""
Memory Cleanup Service Tests
Tests for memory leak prevention and cleanup functionality
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from services.memory.cleanup import (
    MemoryCleanupService, 
    CleanupConfig, 
    get_memory_service,
    memory_cleanup
)

class TestMemoryCleanupService:
    """Test memory cleanup service functionality."""
    
    @pytest.fixture
    def config(self):
        """Test configuration."""
        return CleanupConfig(
            max_memory_mb=100,
            memory_threshold=0.8,
            cleanup_interval=1,  # 1 second for testing
            session_timeout=5,   # 5 seconds for testing
            cache_timeout=3,     # 3 seconds for testing
            max_tracked_objects=10
        )
    
    @pytest.fixture
    def service(self, config):
        """Memory cleanup service instance."""
        return MemoryCleanupService(config)
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service.config.max_memory_mb == 100
        assert service.is_running is False
        assert len(service.tracked_sessions) == 0
        assert len(service.cached_objects) == 0
    
    @pytest.mark.asyncio
    async def test_start_stop_service(self, service):
        """Test starting and stopping service."""
        # Start service
        await service.start()
        assert service.is_running is True
        assert service.cleanup_task is not None
        
        # Stop service
        await service.stop()
        assert service.is_running is False
    
    def test_track_session(self, service):
        """Test session tracking."""
        session_obj = {"data": "test_session"}
        service.track_session("session_1", session_obj)
        
        assert "session_1" in service.tracked_sessions
        assert "session_1" in service.session_timestamps
        assert service.stats.tracked_objects == 1
    
    def test_remove_session(self, service):
        """Test session removal."""
        session_obj = {"data": "test_session"}
        service.track_session("session_1", session_obj)
        service.remove_session("session_1")
        
        assert "session_1" not in service.tracked_sessions
        assert "session_1" not in service.session_timestamps
    
    def test_cache_object(self, service):
        """Test object caching."""
        test_obj = {"data": "cached_data"}
        service.cache_object("key_1", test_obj)
        
        assert "key_1" in service.cached_objects
        assert "key_1" in service.cache_timestamps
        assert service.cached_objects["key_1"] == test_obj
    
    def test_get_cached_object(self, service):
        """Test cached object retrieval."""
        test_obj = {"data": "cached_data"}
        service.cache_object("key_1", test_obj)
        
        retrieved = service.get_cached_object("key_1")
        assert retrieved == test_obj
        
        # Test non-existent key
        assert service.get_cached_object("non_existent") is None
    
    def test_remove_cached_object(self, service):
        """Test cached object removal."""
        test_obj = {"data": "cached_data"}
        service.cache_object("key_1", test_obj)
        service.remove_cached_object("key_1")
        
        assert "key_1" not in service.cached_objects
        assert "key_1" not in service.cache_timestamps
    
    @patch('services.memory.cleanup.psutil.Process')
    def test_memory_stats_update(self, mock_process, service):
        """Test memory statistics update."""
        # Mock process memory info
        mock_memory_info = MagicMock()
        mock_memory_info.rss = 100 * 1024 * 1024  # 100MB in bytes
        mock_process.return_value.memory_info.return_value = mock_memory_info
        
        with patch('services.memory.cleanup.psutil.virtual_memory') as mock_virtual_memory:
            mock_virtual_memory.return_value.percent = 75.0
            
            with patch('services.memory.cleanup.gc.get_counts') as mock_gc_counts:
                mock_gc_counts.return_value = [100, 10, 1]
                
                service._update_memory_stats()
                
                assert service.stats.process_memory_mb == 100.0
                assert service.stats.system_memory_percent == 75.0
                assert service.stats.gc_collections == [100, 10, 1]
    
    def test_should_cleanup_memory_threshold(self, service):
        """Test cleanup trigger based on memory threshold."""
        # Set high memory usage
        service.stats.process_memory_mb = 90.0  # 90MB > 80MB threshold
        assert service._should_cleanup() is True
        
        # Set low memory usage
        service.stats.process_memory_mb = 50.0  # 50MB < 80MB threshold
        service.stats.tracked_objects = 5  # Below threshold
        assert service._should_cleanup() is False
    
    def test_should_cleanup_object_threshold(self, service):
        """Test cleanup trigger based on object count."""
        service.stats.process_memory_mb = 50.0  # Below memory threshold
        service.stats.tracked_objects = 15  # Above max_tracked_objects (10)
        assert service._should_cleanup() is True
    
    def test_cleanup_expired_sessions(self, service):
        """Test cleanup of expired sessions."""
        # Add sessions with different timestamps
        current_time = datetime.now()
        old_time = current_time - timedelta(seconds=10)  # Older than 5s timeout
        recent_time = current_time - timedelta(seconds=2)  # Within timeout
        
        service.session_timestamps["old_session"] = old_time
        service.session_timestamps["recent_session"] = recent_time
        service.tracked_sessions["old_session"] = "dummy_ref"
        service.tracked_sessions["recent_session"] = "dummy_ref"
        
        expired_count = service._cleanup_expired_sessions()
        
        assert expired_count == 1
        assert "old_session" not in service.session_timestamps
        assert "recent_session" in service.session_timestamps
    
    def test_cleanup_expired_cache(self, service):
        """Test cleanup of expired cache entries."""
        # Add cache entries with different timestamps
        current_time = datetime.now()
        old_time = current_time - timedelta(seconds=5)  # Older than 3s timeout
        recent_time = current_time - timedelta(seconds=1)  # Within timeout
        
        service.cache_timestamps["old_cache"] = old_time
        service.cache_timestamps["recent_cache"] = recent_time
        service.cached_objects["old_cache"] = "old_data"
        service.cached_objects["recent_cache"] = "recent_data"
        
        expired_count = service._cleanup_expired_cache()
        
        assert expired_count == 1
        assert "old_cache" not in service.cache_timestamps
        assert "recent_cache" in service.cache_timestamps
    
    @patch('services.memory.cleanup.gc.collect')
    def test_force_garbage_collection(self, mock_gc_collect, service):
        """Test forced garbage collection."""
        mock_gc_collect.side_effect = [10, 5, 2]  # Return values for generations 0, 1, 2
        
        collected = service._force_garbage_collection()
        
        assert collected == 17  # 10 + 5 + 2
        assert mock_gc_collect.call_count == 3
    
    @pytest.mark.asyncio
    async def test_run_cleanup_cycle(self, service, config):
        """Test complete cleanup cycle."""
        # Setup some expired data
        old_time = datetime.now() - timedelta(seconds=10)
        service.session_timestamps["expired_session"] = old_time
        service.tracked_sessions["expired_session"] = "dummy_ref"
        service.cache_timestamps["expired_cache"] = old_time
        service.cached_objects["expired_cache"] = "expired_data"
        
        # Mock memory stats to trigger cleanup
        service.stats.process_memory_mb = 90.0
        
        with patch.object(service, '_update_memory_stats'):
            with patch.object(service, '_should_cleanup', return_value=True):
                await service.run_cleanup()
        
        # Check that cleanup ran
        assert service.stats.cleanup_runs > 0
        assert service.stats.last_cleanup is not None
    
    def test_memory_health_check(self, service):
        """Test memory health assessment."""
        # Healthy state
        service.stats.process_memory_mb = 50.0  # Below threshold
        service.stats.tracked_objects = 5  # Below threshold
        assert service.is_memory_healthy() is True
        
        # Unhealthy state - high memory
        service.stats.process_memory_mb = 90.0  # Above threshold
        assert service.is_memory_healthy() is False
        
        # Unhealthy state - too many objects
        service.stats.process_memory_mb = 50.0  # Reset to healthy
        service.stats.tracked_objects = 15  # Above threshold
        assert service.is_memory_healthy() is False
    
    def test_get_memory_stats(self, service):
        """Test memory statistics retrieval."""
        stats = service.get_memory_stats()
        
        assert isinstance(stats, dict)
        assert "process_memory_mb" in stats
        assert "tracked_objects" in stats
        assert "cleanup_runs" in stats
        assert "memory_threshold_mb" in stats
        assert "max_memory_mb" in stats
    
    def test_max_tracked_objects_limit(self, service):
        """Test that tracking is limited to prevent unbounded growth."""
        # Add more sessions than the limit
        for i in range(15):  # More than max_tracked_objects (10)
            service.track_session(f"session_{i}", f"data_{i}")
        
        # Should not exceed the limit significantly
        assert len(service.tracked_sessions) <= service.config.max_tracked_objects + 1

class TestGlobalMemoryService:
    """Test global memory service functions."""
    
    def test_get_memory_service_singleton(self):
        """Test that get_memory_service returns singleton."""
        service1 = get_memory_service()
        service2 = get_memory_service()
        
        assert service1 is service2  # Same instance
    
    @pytest.mark.asyncio
    async def test_start_stop_global_service(self):
        """Test starting and stopping global service."""
        from services.memory.cleanup import start_memory_service, stop_memory_service
        
        # Start service
        await start_memory_service()
        service = get_memory_service()
        assert service.is_running is True
        
        # Stop service
        await stop_memory_service()
        assert service.is_running is False

class TestMemoryCleanupDecorator:
    """Test memory cleanup decorator."""
    
    @memory_cleanup(session_timeout=10)
    async def mock_create_session(self, session_id: str):
        """Mock session creation function."""
        return {"session_id": session_id, "data": "test_data"}
    
    @pytest.mark.asyncio
    async def test_decorator_tracks_session(self):
        """Test that decorator automatically tracks sessions."""
        session_id = "test_session_decorated"
        
        # Call decorated function
        result = await self.mock_create_session(session_id)
        
        # Check that session was tracked
        service = get_memory_service()
        assert session_id in service.tracked_sessions
        assert session_id in service.session_timestamps
        
        # Cleanup
        service.remove_session(session_id)

class TestConfigValidation:
    """Test configuration validation."""
    
    def test_config_defaults(self):
        """Test default configuration values."""
        config = CleanupConfig()
        
        assert config.max_memory_mb == 2048
        assert config.memory_threshold == 0.8
        assert config.cleanup_interval == 300
        assert config.session_timeout == 3600
        assert config.cache_timeout == 1800
        assert config.max_tracked_objects == 10000
        assert config.enable_gc_debug is False
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = CleanupConfig(
            max_memory_mb=1000,
            memory_threshold=0.7,
            cleanup_interval=60,
            session_timeout=1800,
            enable_gc_debug=True
        )
        
        assert config.max_memory_mb == 1000
        assert config.memory_threshold == 0.7
        assert config.cleanup_interval == 60
        assert config.session_timeout == 1800
        assert config.enable_gc_debug is True

# Performance Tests
class TestMemoryServicePerformance:
    """Test memory service performance."""
    
    def test_large_session_tracking(self):
        """Test performance with large number of sessions."""
        config = CleanupConfig(max_tracked_objects=1000)
        service = MemoryCleanupService(config)
        
        start_time = time.time()
        
        # Track many sessions
        for i in range(500):
            service.track_session(f"session_{i}", f"data_{i}")
        
        end_time = time.time()
        
        assert (end_time - start_time) < 1.0  # Should complete within 1 second
        assert len(service.tracked_sessions) == 500
    
    def test_large_cache_operations(self):
        """Test performance with large cache operations."""
        service = MemoryCleanupService()
        
        start_time = time.time()
        
        # Cache many objects
        for i in range(1000):
            service.cache_object(f"key_{i}", {"data": f"value_{i}"})
        
        end_time = time.time()
        
        assert (end_time - start_time) < 2.0  # Should complete within 2 seconds
        assert len(service.cached_objects) == 1000

# Configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])