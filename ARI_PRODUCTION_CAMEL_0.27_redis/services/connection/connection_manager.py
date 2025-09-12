"""
Connection Manager for AI Stylist
Implements circuit breaker pattern for database connections
Production-ready with health checks and automatic recovery
"""

import asyncio
import logging
import time
from typing import Any, Callable, Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger("connection_manager")


class ConnectionState(Enum):
    """Connection states for circuit breaker pattern"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"  # Circuit breaker open


@dataclass
class ConnectionStats:
    """Statistics for connection monitoring"""
    connection_attempts: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    health_checks: int = 0
    failed_health_checks: int = 0
    circuit_breaker_trips: int = 0
    last_error: Optional[str] = None
    uptime_start: Optional[datetime] = None
    total_downtime: float = 0.0
    last_failure_time: Optional[datetime] = None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get statistics summary"""
        summary = {
            "connection_attempts": self.connection_attempts,
            "successful_connections": self.successful_connections,
            "failed_connections": self.failed_connections,
            "success_rate": (
                self.successful_connections / self.connection_attempts * 100
                if self.connection_attempts > 0 else 0
            ),
            "health_checks": self.health_checks,
            "failed_health_checks": self.failed_health_checks,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "last_error": self.last_error
        }
        
        if self.uptime_start:
            uptime = datetime.now() - self.uptime_start
            summary["uptime_seconds"] = uptime.total_seconds()
            summary["uptime_string"] = str(uptime).split('.')[0]
        
        summary["total_downtime_seconds"] = self.total_downtime
        
        return summary


class CircuitBreaker:
    """
    Circuit breaker implementation for connection management.
    Prevents cascading failures by temporarily blocking connections.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 3
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            half_open_requests: Test requests in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = ConnectionState.DISCONNECTED
        self.half_open_count = 0
        
        logger.info(f"Circuit breaker initialized (threshold={failure_threshold})")
    
    def call_succeeded(self):
        """Record successful call"""
        self.failure_count = 0
        self.half_open_count = 0
        
        if self.state == ConnectionState.FAILED:
            logger.info("Circuit breaker closed - connection recovered")
        
        self.state = ConnectionState.CONNECTED
    
    def call_failed(self):
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != ConnectionState.FAILED:
                logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
            self.state = ConnectionState.FAILED
    
    def should_attempt_call(self) -> bool:
        """Check if call should be attempted"""
        if self.state == ConnectionState.CONNECTED:
            return True
        
        if self.state == ConnectionState.DISCONNECTED:
            return True
        
        if self.state == ConnectionState.FAILED:
            if self.last_failure_time:
                time_since_failure = time.time() - self.last_failure_time
                
                if time_since_failure >= self.recovery_timeout:
                    # Try half-open state
                    if self.half_open_count < self.half_open_requests:
                        self.half_open_count += 1
                        logger.info(f"Circuit breaker half-open (attempt {self.half_open_count}/{self.half_open_requests})")
                        return True
                    else:
                        # Failed all half-open attempts
                        self.last_failure_time = time.time()
                        self.half_open_count = 0
                        return False
            
            return False
        
        return True
    
    def get_state(self) -> str:
        """Get current circuit breaker state"""
        return self.state.value


class ConnectionManager:
    """
    Manages database connections with automatic recovery and health checks.
    Implements circuit breaker pattern to prevent cascading failures.
    """
    
    def __init__(
        self,
        connect_func: Callable,
        health_check_func: Callable,
        name: str,
        retry_delay: int = 5,
        max_retries: int = 3,
        health_check_interval: int = 60,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 300,
        enable_auto_recovery: bool = True
    ):
        """
        Initialize connection manager.
        
        Args:
            connect_func: Async function to establish connection
            health_check_func: Async function to check connection health
            name: Connection name for logging
            retry_delay: Initial retry delay in seconds
            max_retries: Maximum connection retries
            health_check_interval: Seconds between health checks
            circuit_breaker_threshold: Failures before circuit opens
            circuit_breaker_timeout: Circuit breaker recovery timeout
            enable_auto_recovery: Enable automatic reconnection
        """
        self.connect_func = connect_func
        self.health_check_func = health_check_func
        self.name = name
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.health_check_interval = health_check_interval
        self.enable_auto_recovery = enable_auto_recovery
        
        self.connection = None
        self.state = ConnectionState.DISCONNECTED
        self._reconnect_lock = asyncio.Lock()
        self._health_check_task = None
        self._recovery_task = None
        self._last_health_check = None
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout
        )
        
        # Statistics
        self.stats = ConnectionStats()
        
        # Connection pool for high availability
        self.connection_pool: List[Any] = []
        self.max_pool_size = 3
        
        logger.info(f"ConnectionManager initialized for {name}")
        
        # Start health check worker
        self._health_check_task = asyncio.create_task(self._health_check_worker())
        
        # Start recovery worker if enabled
        if self.enable_auto_recovery:
            self._recovery_task = asyncio.create_task(self._auto_recovery_worker())
    
    async def get_connection(self) -> Optional[Any]:
        """
        Get connection, establishing or recovering if necessary.
        
        Returns:
            Active connection or None if circuit breaker is open
            
        Raises:
            RuntimeError: If connection cannot be established
        """
        # Check circuit breaker
        if not self.circuit_breaker.should_attempt_call():
            logger.warning(f"Circuit breaker OPEN for {self.name}, refusing connection")
            raise RuntimeError(f"Circuit breaker open for {self.name}")
        
        # Return existing healthy connection
        if self.state == ConnectionState.CONNECTED and self.connection:
            if await self._is_healthy():
                return self.connection
            else:
                logger.warning(f"Connection {self.name} failed health check")
                self.state = ConnectionState.DISCONNECTED
        
        # Try connection pool
        for conn in self.connection_pool:
            if await self._is_connection_healthy(conn):
                self.connection = conn
                self.state = ConnectionState.CONNECTED
                return self.connection
        
        # Attempt reconnection
        if self.state != ConnectionState.RECONNECTING:
            success = await self._reconnect()
            if not success:
                self.circuit_breaker.call_failed()
                raise RuntimeError(f"Failed to establish connection to {self.name}")
            else:
                self.circuit_breaker.call_succeeded()
        
        return self.connection
    
    async def _reconnect(self) -> bool:
        """
        Attempt to establish or reestablish connection with exponential backoff.
        
        Returns:
            True if connection established, False otherwise
        """
        # FIX: Add timeout to lock
        try:
            async with asyncio.timeout(30):
                async with self._reconnect_lock:
                    # Check if already connected
                    if self.state == ConnectionState.CONNECTED and self.connection:
                        return True
                    
                    if self.state == ConnectionState.RECONNECTING:
                        return False
                    
                    self.state = ConnectionState.RECONNECTING
                    retry_count = 0
                    current_delay = self.retry_delay
                    downtime_start = datetime.now()
                    
                    while retry_count < self.max_retries:
                        try:
                            logger.info(f"Attempting connection to {self.name} (attempt {retry_count + 1}/{self.max_retries})")
                            self.stats.connection_attempts += 1
                            
                            # Call connection function
                            self.connection = await asyncio.wait_for(
                                self.connect_func(),
                                timeout=30.0
                            )
                            
                            # Verify connection health
                            if await self._is_healthy():
                                self.state = ConnectionState.CONNECTED
                                self.stats.successful_connections += 1
                                
                                # Update uptime tracking
                                if not self.stats.uptime_start:
                                    self.stats.uptime_start = datetime.now()
                                
                                # Track downtime
                                if downtime_start:
                                    downtime = (datetime.now() - downtime_start).total_seconds()
                                    self.stats.total_downtime += downtime
                                
                                # Add to connection pool
                                # FIX: Rotate old connections
                                if len(self.connection_pool) >= self.max_pool_size:
                                    oldest = self.connection_pool.pop(0)
                                    if hasattr(oldest, 'close'):
                                        asyncio.create_task(oldest.close())
                                self.connection_pool.append(self.connection)
                                
                                logger.info(f"Successfully connected to {self.name}")
                                return True
                            else:
                                raise RuntimeError("Health check failed after connection")
                            
                        except asyncio.TimeoutError:
                            logger.error(f"Connection timeout for {self.name}")
                            self.stats.last_error = "Connection timeout"
                        except Exception as e:
                            logger.error(f"Connection attempt {retry_count + 1} failed for {self.name}: {e}")
                            self.stats.last_error = str(e)
                        
                        retry_count += 1
                        self.stats.failed_connections += 1
                        self.stats.last_failure_time = datetime.now()
                        
                        if retry_count < self.max_retries:
                            logger.info(f"Retrying in {current_delay} seconds...")
                            await asyncio.sleep(current_delay)
                            # Exponential backoff with jitter
                            current_delay = min(current_delay * 2 + (asyncio.get_event_loop().time() % 1), 60)
                    
                    # All retries failed
                    self.state = ConnectionState.FAILED
                    self.circuit_breaker.call_failed()
                    self.stats.circuit_breaker_trips += 1
                    
                    # Track downtime
                    if downtime_start:
                        downtime = (datetime.now() - downtime_start).total_seconds()
                        self.stats.total_downtime += downtime
                    
                    self.connection = None
                    self.connection_pool.clear()
                    
                    logger.error(f"Failed to connect to {self.name} after {self.max_retries} attempts")
                    return False
        except asyncio.TimeoutError:
            logger.error("Reconnect lock timeout")
            return False
    
    async def _is_healthy(self) -> bool:
        """Check if current connection is healthy"""
        return await self._is_connection_healthy(self.connection)
    
    async def _is_connection_healthy(self, connection: Any) -> bool:
        """Check if a specific connection is healthy"""
        if not connection:
            return False
        
        try:
            result = await asyncio.wait_for(
                self.health_check_func(connection),
                timeout=5.0
            )
            self._last_health_check = datetime.now()
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Health check timed out for {self.name}")
            return False
        except Exception as e:
            logger.error(f"Health check failed for {self.name}: {e}")
            return False
    
    async def _health_check_worker(self):
        """Background task that performs periodic health checks"""
        await asyncio.sleep(10)  # Initial delay
        
        while True:
            try:
                if self.state == ConnectionState.CONNECTED and self.connection:
                    self.stats.health_checks += 1
                    
                    if await self._is_healthy():
                        logger.debug(f"Health check passed for {self.name}")
                        self.circuit_breaker.call_succeeded()
                    else:
                        self.stats.failed_health_checks += 1
                        logger.warning(f"Health check failed for {self.name}")
                        self.state = ConnectionState.DISCONNECTED
                        self.circuit_breaker.call_failed()
                        
                        # Clean up failed connections from pool
                        healthy_pool = []
                        for conn in self.connection_pool:
                            if await self._is_connection_healthy(conn):
                                healthy_pool.append(conn)
                        self.connection_pool = healthy_pool
                
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                logger.info(f"Health check worker cancelled for {self.name}")
                raise
            except Exception as e:
                logger.error(f"Error in health check worker for {self.name}: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _auto_recovery_worker(self):
        """Background task that attempts automatic recovery"""
        await asyncio.sleep(30)  # Initial delay
        
        while True:
            try:
                if self.state in [ConnectionState.DISCONNECTED, ConnectionState.FAILED]:
                    if self.circuit_breaker.should_attempt_call():
                        logger.info(f"Attempting auto-recovery for {self.name}")
                        
                        success = await self._reconnect()
                        if success:
                            logger.info(f"Auto-recovery successful for {self.name}")
                            self.circuit_breaker.call_succeeded()
                        else:
                            logger.warning(f"Auto-recovery failed for {self.name}")
                            self.circuit_breaker.call_failed()
                
                # Adaptive sleep based on state
                if self.state == ConnectionState.CONNECTED:
                    await asyncio.sleep(300)  # 5 minutes when healthy
                elif self.state == ConnectionState.FAILED:
                    await asyncio.sleep(60)  # 1 minute when failed
                else:
                    await asyncio.sleep(30)  # 30 seconds otherwise
                
            except asyncio.CancelledError:
                logger.info(f"Auto-recovery worker cancelled for {self.name}")
                raise
            except Exception as e:
                logger.error(f"Error in auto-recovery worker for {self.name}: {e}")
                await asyncio.sleep(60)
    
    async def disconnect(self):
        """Gracefully disconnect and cleanup resources"""
        logger.info(f"Disconnecting {self.name}")
        
        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections in pool
        for conn in self.connection_pool:
            if hasattr(conn, 'close'):
                try:
                    await conn.close()
                except Exception as e:
                    logger.error(f"Error closing pooled connection: {e}")
        
        self.connection_pool.clear()
        
        # Close main connection
        if self.connection:
            if hasattr(self.connection, 'close'):
                try:
                    await self.connection.close()
                except Exception as e:
                    logger.error(f"Error closing connection for {self.name}: {e}")
            
            self.connection = None
        
        self.state = ConnectionState.DISCONNECTED
        logger.info(f"{self.name} disconnected")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        stats = self.stats.get_summary()
        stats["current_state"] = self.state.value
        stats["circuit_breaker_state"] = self.circuit_breaker.get_state()
        stats["connection_pool_size"] = len(self.connection_pool)
        stats["last_health_check"] = (
            self._last_health_check.isoformat() if self._last_health_check else None
        )
        return stats


# Factory functions for specific database connections

async def create_neo4j_connection_manager(neo4j_client) -> ConnectionManager:
    """
    Create a connection manager for Neo4j.
    
    Args:
        neo4j_client: Neo4j database client
        
    Returns:
        Configured ConnectionManager for Neo4j
    """
    async def connect():
        """Establish Neo4j connection"""
        if hasattr(neo4j_client, 'connect'):
            await neo4j_client.connect()
        return neo4j_client
    
    async def health_check(client) -> bool:
        """Check Neo4j health"""
        if hasattr(client, 'query'):
            try:
                result = await client.query("MATCH (n) RETURN n LIMIT 1")
                return True
            except Exception as e:
                logger.error(f"Neo4j health check failed: {e}")
                return False
        return True
    
    return ConnectionManager(
        connect_func=connect,
        health_check_func=health_check,
        name="Neo4j",
        health_check_interval=60,
        circuit_breaker_threshold=5,
        circuit_breaker_timeout=300
    )


async def create_qdrant_connection_manager(qdrant_client) -> ConnectionManager:
    """
    Create a connection manager for Qdrant.
    
    Args:
        qdrant_client: Qdrant database client
        
    Returns:
        Configured ConnectionManager for Qdrant
    """
    async def connect():
        """Establish Qdrant connection"""
        if hasattr(qdrant_client, 'init'):
            await qdrant_client.init()
        return qdrant_client
    
    async def health_check(client) -> bool:
        """Check Qdrant health"""
        if hasattr(client, 'get_collection_stats'):
            try:
                stats = await client.get_collection_stats()
                return bool(stats)
            except Exception as e:
                logger.error(f"Qdrant health check failed: {e}")
                return False
        return True
    
    return ConnectionManager(
        connect_func=connect,
        health_check_func=health_check,
        name="Qdrant",
        health_check_interval=60,
        circuit_breaker_threshold=5,
        circuit_breaker_timeout=300
    )


async def create_openai_connection_manager(openai_client) -> ConnectionManager:
    """
    Create a connection manager for OpenAI API.
    
    Args:
        openai_client: OpenAI client
        
    Returns:
        Configured ConnectionManager for OpenAI
    """
    async def connect():
        """Verify OpenAI connection"""
        return openai_client
    
    async def health_check(client) -> bool:
        """Check OpenAI API health"""
        try:
            # Simple model list check
            models = await asyncio.to_thread(client.models.list)
            return len(models.data) > 0
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False
    
    return ConnectionManager(
        connect_func=connect,
        health_check_func=health_check,
        name="OpenAI",
        health_check_interval=120,  # Less frequent for API
        circuit_breaker_threshold=3,  # More sensitive for API
        circuit_breaker_timeout=60  # Faster recovery attempts
    )
