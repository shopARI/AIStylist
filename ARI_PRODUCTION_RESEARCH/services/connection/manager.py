"""
Connection Manager with Circuit Breaker Pattern
Manages database connections with automatic recovery and health checks
Based on connection_manager.py patterns
"""

import logging
import asyncio
import time
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import traceback

logger = logging.getLogger("services.connection.manager")


class ConnectionState(Enum):
    """Connection states for circuit breaker."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures exceeded threshold
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ConnectionStats:
    """Statistics for a connection."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    total_response_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time / self.successful_requests


class CircuitBreaker:
    """
    Circuit breaker implementation for connection resilience.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name
            failure_threshold: Failures before opening
            recovery_timeout: Seconds before trying recovery
            success_threshold: Successes needed to close
            expected_exception: Exception type to catch
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.expected_exception = expected_exception
        
        self.state = ConnectionState.CLOSED
        self.stats = ConnectionStats()
        self.half_open_successes = 0
        self._lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker '{name}' initialized")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            # Check if circuit should transition to half-open
            if self.state == ConnectionState.OPEN:
                if self._should_attempt_reset():
                    self.state = ConnectionState.HALF_OPEN
                    self.half_open_successes = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                else:
                    raise ConnectionError(f"Circuit breaker '{self.name}' is OPEN")
        
        # Execute function
        start_time = time.time()
        
        try:
            # Execute function (handle both sync and async)
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            
            # Record success
            await self._on_success(time.time() - start_time)
            return result
            
        except self.expected_exception as e:
            # Record failure
            await self._on_failure()
            raise
    
    async def _on_success(self, response_time: float):
        """Handle successful call."""
        async with self._lock:
            self.stats.successful_requests += 1
            self.stats.total_requests += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = time.time()
            self.stats.total_response_time += response_time
            
            if self.state == ConnectionState.HALF_OPEN:
                self.half_open_successes += 1
                
                if self.half_open_successes >= self.success_threshold:
                    self.state = ConnectionState.CLOSED
                    logger.info(f"Circuit breaker '{self.name}' recovered to CLOSED")
    
    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.stats.failed_requests += 1
            self.stats.total_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.last_failure_time = time.time()
            
            if self.state == ConnectionState.HALF_OPEN:
                self.state = ConnectionState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' reopened due to failure in HALF_OPEN")
            
            elif self.state == ConnectionState.CLOSED:
                if self.stats.consecutive_failures >= self.failure_threshold:
                    self.state = ConnectionState.OPEN
                    logger.error(f"Circuit breaker '{self.name}' opened after {self.stats.consecutive_failures} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if should attempt reset from OPEN state."""
        if self.stats.last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self.stats.last_failure_time
        return time_since_failure >= self.recovery_timeout
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": {
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "consecutive_failures": self.stats.consecutive_failures,
                "success_rate": f"{self.stats.success_rate * 100:.1f}%",
                "avg_response_time": f"{self.stats.average_response_time:.3f}s"
            }
        }
    
    async def reset(self):
        """Reset circuit breaker to closed state."""
        async with self._lock:
            self.state = ConnectionState.CLOSED
            self.stats.consecutive_failures = 0
            self.half_open_successes = 0
            logger.info(f"Circuit breaker '{self.name}' manually reset")


class ConnectionPool:
    """
    Connection pool with health monitoring.
    """
    
    def __init__(
        self,
        name: str,
        create_connection: Callable,
        max_size: int = 10,
        min_size: int = 2,
        max_idle_time: int = 300
    ):
        """
        Initialize connection pool.
        
        Args:
            name: Pool name
            create_connection: Function to create connection
            max_size: Maximum pool size
            min_size: Minimum pool size
            max_idle_time: Maximum idle time before closing
        """
        self.name = name
        self.create_connection = create_connection
        self.max_size = max_size
        self.min_size = min_size
        self.max_idle_time = max_idle_time
        
        self._pool: List[Any] = []
        self._in_use: List[Any] = []
        self._lock = asyncio.Lock()
        self._created = 0
        
        logger.info(f"Connection pool '{name}' initialized (min={min_size}, max={max_size})")
    
    async def acquire(self) -> Any:
        """
        Acquire connection from pool.
        
        Returns:
            Connection instance
        """
        async with self._lock:
            # Try to get from pool
            if self._pool:
                conn = self._pool.pop()
                self._in_use.append(conn)
                return conn
            
            # Create new if under limit
            if self._created < self.max_size:
                conn = await self._create_new()
                self._in_use.append(conn)
                return conn
        
        # Wait for available connection
        while True:
            await asyncio.sleep(0.1)
            async with self._lock:
                if self._pool:
                    conn = self._pool.pop()
                    self._in_use.append(conn)
                    return conn
    
    async def release(self, connection: Any):
        """
        Release connection back to pool.
        
        Args:
            connection: Connection to release
        """
        async with self._lock:
            if connection in self._in_use:
                self._in_use.remove(connection)
                self._pool.append(connection)
    
    async def _create_new(self) -> Any:
        """Create new connection."""
        if asyncio.iscoroutinefunction(self.create_connection):
            conn = await self.create_connection()
        else:
            conn = await asyncio.to_thread(self.create_connection)
        
        self._created += 1
        logger.debug(f"Created new connection for pool '{self.name}' ({self._created}/{self.max_size})")
        return conn
    
    async def close_all(self):
        """Close all connections."""
        async with self._lock:
            all_connections = self._pool + self._in_use
            
            for conn in all_connections:
                try:
                    if hasattr(conn, 'close'):
                        if asyncio.iscoroutinefunction(conn.close):
                            await conn.close()
                        else:
                            await asyncio.to_thread(conn.close)
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")
            
            self._pool.clear()
            self._in_use.clear()
            self._created = 0
            
            logger.info(f"Connection pool '{self.name}' closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "name": self.name,
            "created": self._created,
            "available": len(self._pool),
            "in_use": len(self._in_use),
            "max_size": self.max_size,
            "utilization": f"{(len(self._in_use) / self.max_size * 100):.1f}%" if self.max_size > 0 else "0%"
        }


class ConnectionManager:
    """
    Central connection manager for all database connections.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize connection manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.connection_pools: Dict[str, ConnectionPool] = {}
        self.health_check_tasks: Dict[str, asyncio.Task] = {}
        self._running = True
        
        # Initialize circuit breakers
        self._init_circuit_breakers()
        
        logger.info("Connection Manager initialized")
    
    def _init_circuit_breakers(self):
        """Initialize circuit breakers for each service."""
        # Neo4j circuit breaker
        self.circuit_breakers['neo4j'] = CircuitBreaker(
            name='neo4j',
            failure_threshold=self.config.get('circuit_breaker_threshold', 5),
            recovery_timeout=self.config.get('circuit_breaker_timeout', 60),
            success_threshold=2
        )
        
        # Qdrant circuit breaker
        self.circuit_breakers['qdrant'] = CircuitBreaker(
            name='qdrant',
            failure_threshold=self.config.get('circuit_breaker_threshold', 5),
            recovery_timeout=self.config.get('circuit_breaker_timeout', 60),
            success_threshold=2
        )
        
        # OpenAI circuit breaker
        self.circuit_breakers['openai'] = CircuitBreaker(
            name='openai',
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=1
        )
    
    async def execute_with_circuit_breaker(
        self,
        service: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            service: Service name
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        if service not in self.circuit_breakers:
            # Execute without circuit breaker
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return await asyncio.to_thread(func, *args, **kwargs)
        
        circuit_breaker = self.circuit_breakers[service]
        return await circuit_breaker.call(func, *args, **kwargs)
    
    async def create_connection_pool(
        self,
        name: str,
        create_func: Callable,
        max_size: int = 10
    ) -> ConnectionPool:
        """
        Create and register connection pool.
        
        Args:
            name: Pool name
            create_func: Connection creation function
            max_size: Maximum pool size
            
        Returns:
            ConnectionPool instance
        """
        pool = ConnectionPool(
            name=name,
            create_connection=create_func,
            max_size=max_size,
            min_size=max(1, max_size // 5)
        )
        
        self.connection_pools[name] = pool
        
        # Start health check task
        self.health_check_tasks[name] = asyncio.create_task(
            self._health_check_worker(name)
        )
        
        return pool
    
    async def _health_check_worker(self, pool_name: str):
        """
        Background health check for connection pool.
        
        Args:
            pool_name: Pool name to check
        """
        interval = self.config.get('health_check_interval', 60)
        
        while self._running:
            try:
                await asyncio.sleep(interval)
                
                if not self._running:
                    break
                
                pool = self.connection_pools.get(pool_name)
                if pool:
                    # Perform health check
                    try:
                        conn = await asyncio.wait_for(pool.acquire(), timeout=15.0)
                        await pool.release(conn)
                        logger.debug(f"Health check passed for pool '{pool_name}'")
                    except asyncio.TimeoutError:
                        logger.warning(f"Health check timeout for pool '{pool_name}'")
                    except Exception as e:
                        logger.error(f"Health check failed for pool '{pool_name}': {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check worker: {e}")
    
    async def retry_with_backoff(
        self,
        func: Callable,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ) -> Any:
        """
        Execute function with exponential backoff retry.
        
        Args:
            func: Function to execute
            max_attempts: Maximum retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Exponential backoff base
            
        Returns:
            Function result
        """
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func()
                else:
                    return await asyncio.to_thread(func)
                    
            except Exception as e:
                last_exception = e
                
                if attempt == max_attempts - 1:
                    logger.error(f"All retry attempts failed: {e}")
                    raise
                
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
                
                # Calculate next delay
                delay = min(delay * exponential_base, max_delay)
        
        raise last_exception
    
    def get_circuit_breaker_states(self) -> Dict[str, Any]:
        """Get all circuit breaker states."""
        states = {}
        for name, breaker in self.circuit_breakers.items():
            states[name] = breaker.get_state()
        return states
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get all connection pool statistics."""
        stats = {}
        for name, pool in self.connection_pools.items():
            stats[name] = pool.get_stats()
        return stats
    
    async def reset_circuit_breaker(self, service: str):
        """
        Reset circuit breaker for service.
        
        Args:
            service: Service name
        """
        if service in self.circuit_breakers:
            await self.circuit_breakers[service].reset()
            logger.info(f"Circuit breaker reset for service: {service}")
    
    async def shutdown(self):
        """Shutdown connection manager."""
        logger.info("Shutting down Connection Manager")
        
        self._running = False
        
        # Cancel health check tasks
        for task in self.health_check_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.health_check_tasks.values(), return_exceptions=True)
        
        # Close all connection pools
        for pool in self.connection_pools.values():
            await pool.close_all()
        
        logger.info("Connection Manager shutdown complete")


# Global instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager(config: Optional[Dict[str, Any]] = None) -> ConnectionManager:
    """
    Get global connection manager instance.
    
    Args:
        config: Optional configuration
        
    Returns:
        ConnectionManager instance
    """
    global _connection_manager
    
    if _connection_manager is None:
        if config is None:
            from config.settings import get_settings
            settings = get_settings()
            config = settings.connection.__dict__
        
        _connection_manager = ConnectionManager(config)
    
    return _connection_manager


# Exports
__all__ = [
    'ConnectionManager',
    'CircuitBreaker',
    'ConnectionPool',
    'ConnectionState',
    'ConnectionStats',
    'get_connection_manager'
]