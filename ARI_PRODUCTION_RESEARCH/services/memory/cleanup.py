"""
Memory Leak Prevention and Cleanup Service
Handles automatic cleanup of memory-intensive resources
"""

import asyncio
import logging
import time
import weakref
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import gc
import psutil
import threading

logger = logging.getLogger("services.memory.cleanup")

@dataclass
class MemoryStats:
    """Memory statistics tracking."""
    process_memory_mb: float
    system_memory_percent: float
    gc_collections: List[int]
    tracked_objects: int
    cleanup_runs: int
    last_cleanup: Optional[datetime] = None

@dataclass 
class CleanupConfig:
    """Configuration for memory cleanup."""
    max_memory_mb: float = 2048  # 2GB limit
    memory_threshold: float = 0.8  # 80% of max before cleanup
    cleanup_interval: int = 300  # 5 minutes
    session_timeout: int = 3600  # 1 hour session timeout
    cache_timeout: int = 1800  # 30 min cache timeout
    max_tracked_objects: int = 10000
    enable_gc_debug: bool = False

class MemoryCleanupService:
    """
    Service for preventing memory leaks and managing memory usage.
    """
    
    def __init__(self, config: Optional[CleanupConfig] = None):
        self.config = config or CleanupConfig()
        self.is_running = False
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Object tracking
        self.tracked_sessions: Dict[str, weakref.ref] = {}
        self.session_timestamps: Dict[str, datetime] = {}
        self.cached_objects: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        
        # Statistics
        self.stats = MemoryStats(
            process_memory_mb=0.0,
            system_memory_percent=0.0,
            gc_collections=[0, 0, 0],
            tracked_objects=0,
            cleanup_runs=0
        )
        
        # Thread lock for statistics
        self._stats_lock = threading.Lock()
        
        logger.info("Memory cleanup service initialized")
    
    async def start(self):
        """Start the memory cleanup service."""
        if self.is_running:
            logger.warning("Memory cleanup service already running")
            return
            
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Memory cleanup service started")
    
    async def stop(self):
        """Stop the memory cleanup service."""
        self.is_running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Memory cleanup service stopped")
    
    async def _cleanup_loop(self):
        """Main cleanup loop."""
        while self.is_running:
            try:
                await self.run_cleanup()
                await asyncio.sleep(self.config.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(10)  # Short delay on error
    
    async def run_cleanup(self):
        """Run a complete memory cleanup cycle."""
        start_time = time.time()
        
        # Update memory statistics
        self._update_memory_stats()
        
        # Check if cleanup is needed
        if not self._should_cleanup():
            logger.debug("Memory cleanup not needed, skipping")
            return
        
        logger.info("Starting memory cleanup cycle")
        
        # Cleanup expired sessions
        expired_sessions = self._cleanup_expired_sessions()
        
        # Cleanup expired cache
        expired_cache = self._cleanup_expired_cache()
        
        # Force garbage collection if memory is high
        if self.stats.process_memory_mb > self.config.max_memory_mb * 0.9:
            collected = self._force_garbage_collection()
            logger.info(f"Forced garbage collection freed {collected} objects")
        
        # Update statistics
        with self._stats_lock:
            self.stats.cleanup_runs += 1
            self.stats.last_cleanup = datetime.now()
        
        duration = time.time() - start_time
        logger.info(
            f"Memory cleanup completed in {duration:.2f}s. "
            f"Sessions: {expired_sessions}, Cache: {expired_cache}"
        )
    
    def _update_memory_stats(self):
        """Update current memory statistics."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            with self._stats_lock:
                self.stats.process_memory_mb = memory_info.rss / 1024 / 1024
                self.stats.system_memory_percent = psutil.virtual_memory().percent
                self.stats.gc_collections = list(gc.get_counts())
                self.stats.tracked_objects = (
                    len(self.tracked_sessions) + 
                    len(self.cached_objects)
                )
        except Exception as e:
            logger.error(f"Error updating memory stats: {e}")
    
    def _should_cleanup(self) -> bool:
        """Check if cleanup should run."""
        return (
            self.stats.process_memory_mb > self.config.max_memory_mb * self.config.memory_threshold or
            self.stats.tracked_objects > self.config.max_tracked_objects or
            len(self.session_timestamps) > 1000 or
            len(self.cached_objects) > 5000
        )
    
    def _cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        now = datetime.now()
        timeout_threshold = now - timedelta(seconds=self.config.session_timeout)
        
        expired_sessions = []
        for session_id, timestamp in list(self.session_timestamps.items()):
            if timestamp < timeout_threshold:
                expired_sessions.append(session_id)
        
        # Remove expired sessions
        for session_id in expired_sessions:
            self.tracked_sessions.pop(session_id, None)
            self.session_timestamps.pop(session_id, None)
            logger.debug(f"Cleaned up expired session: {session_id}")
        
        return len(expired_sessions)
    
    def _cleanup_expired_cache(self) -> int:
        """Clean up expired cached objects."""
        now = datetime.now()
        timeout_threshold = now - timedelta(seconds=self.config.cache_timeout)
        
        expired_cache = []
        for cache_key, timestamp in list(self.cache_timestamps.items()):
            if timestamp < timeout_threshold:
                expired_cache.append(cache_key)
        
        # Remove expired cache entries
        for cache_key in expired_cache:
            self.cached_objects.pop(cache_key, None)
            self.cache_timestamps.pop(cache_key, None)
            logger.debug(f"Cleaned up expired cache: {cache_key}")
        
        return len(expired_cache)
    
    def _force_garbage_collection(self) -> int:
        """Force garbage collection and return number of objects collected."""
        logger.info("Forcing garbage collection due to high memory usage")
        
        # Enable GC debugging if configured
        if self.config.enable_gc_debug:
            gc.set_debug(gc.DEBUG_STATS)
        
        # Run full garbage collection
        collected = 0
        for generation in range(3):
            collected += gc.collect(generation)
        
        # Disable debugging
        if self.config.enable_gc_debug:
            gc.set_debug(0)
        
        return collected
    
    # ==================== PUBLIC API ====================
    
    def track_session(self, session_id: str, session_obj: Any):
        """Track a session object for cleanup."""
        self.tracked_sessions[session_id] = weakref.ref(session_obj)
        self.session_timestamps[session_id] = datetime.now()
        
        # Limit tracking to prevent unbounded growth
        if len(self.tracked_sessions) > self.config.max_tracked_objects:
            oldest_session = min(self.session_timestamps.items(), key=lambda x: x[1])
            self.remove_session(oldest_session[0])
    
    def remove_session(self, session_id: str):
        """Remove a session from tracking."""
        self.tracked_sessions.pop(session_id, None)
        self.session_timestamps.pop(session_id, None)
    
    def cache_object(self, key: str, obj: Any):
        """Cache an object with automatic expiration."""
        self.cached_objects[key] = obj
        self.cache_timestamps[key] = datetime.now()
        
        # Prevent cache from growing unbounded
        if len(self.cached_objects) > 5000:
            oldest_key = min(self.cache_timestamps.items(), key=lambda x: x[1])
            self.remove_cached_object(oldest_key[0])
    
    def remove_cached_object(self, key: str):
        """Remove a cached object."""
        self.cached_objects.pop(key, None)
        self.cache_timestamps.pop(key, None)
    
    def get_cached_object(self, key: str) -> Optional[Any]:
        """Get a cached object and update its timestamp."""
        obj = self.cached_objects.get(key)
        if obj is not None:
            self.cache_timestamps[key] = datetime.now()
        return obj
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics."""
        with self._stats_lock:
            stats_dict = {
                "process_memory_mb": self.stats.process_memory_mb,
                "system_memory_percent": self.stats.system_memory_percent,
                "gc_collections": self.stats.gc_collections,
                "tracked_objects": self.stats.tracked_objects,
                "cleanup_runs": self.stats.cleanup_runs,
                "last_cleanup": self.stats.last_cleanup.isoformat() if self.stats.last_cleanup else None,
                "tracked_sessions": len(self.tracked_sessions),
                "cached_objects": len(self.cached_objects),
                "memory_threshold_mb": self.config.max_memory_mb * self.config.memory_threshold,
                "max_memory_mb": self.config.max_memory_mb
            }
        
        return stats_dict
    
    def is_memory_healthy(self) -> bool:
        """Check if memory usage is within healthy limits."""
        return (
            self.stats.process_memory_mb < self.config.max_memory_mb * self.config.memory_threshold and
            self.stats.tracked_objects < self.config.max_tracked_objects
        )
    
    def force_cleanup(self):
        """Force an immediate cleanup cycle."""
        logger.info("Forcing immediate memory cleanup")
        asyncio.create_task(self.run_cleanup())


# ==================== GLOBAL INSTANCE ====================

_memory_service: Optional[MemoryCleanupService] = None

def get_memory_service() -> MemoryCleanupService:
    """Get the global memory cleanup service."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryCleanupService()
    return _memory_service

async def start_memory_service():
    """Start the global memory cleanup service."""
    service = get_memory_service()
    await service.start()

async def stop_memory_service():
    """Stop the global memory cleanup service."""
    if _memory_service:
        await _memory_service.stop()


# ==================== DECORATORS ====================

def memory_cleanup(session_timeout: int = 3600):
    """
    Decorator to automatically track objects for memory cleanup.
    
    Usage:
        @memory_cleanup(session_timeout=1800)
        async def create_session(session_id: str):
            session = Session(session_id)
            return session
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Try to extract session_id from arguments
            session_id = None
            if 'session_id' in kwargs:
                session_id = kwargs['session_id']
            elif args and hasattr(args[0], 'session_id'):
                session_id = args[0].session_id
            
            if session_id and result:
                service = get_memory_service()
                service.track_session(session_id, result)
            
            return result
        return wrapper
    return decorator