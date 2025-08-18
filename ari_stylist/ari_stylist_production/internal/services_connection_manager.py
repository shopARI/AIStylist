"""
Connection Manager Service
Handles database connections with circuit breaker pattern and auto-recovery
Enhanced version of the old connection_manager.py with settings integration
"""

import asyncio
import logging
from typing import Any, Callable, Optional, Dict, Protocol
from datetime import datetime, timedelta
from enum import Enum
from contextlib import asynccontextmanager

from config.settings import get_settings, ConnectionConfig

logger = logging.getLogger("services.connection.manager")

# =============================================================================
# CONNECTION PROTOCOLS
# =============================================================================

class DatabaseClient(Protocol):
    """Protocol for database clients."""
    
    async def connect(self) -> None:
        """Establish connection."""
        ...
    
    async def close(self) -> None:
        """Close connection."""
        ...
    
    async def health_check(self) -> bool:
        """Check connection health."""
        ...

# =============================================================================
# CONNECTION STATES
# =============================================================================

class ConnectionState(Enum):
    """Connection states for circuit breaker pattern."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    DEGRADED = "degraded"

# =============================================================================
# CONNECTION MANAGER
# =============================================================================

class ConnectionManager:
    """
    Enhanced connection manager with circuit breaker and auto-recovery.
    Integrates with centralized settings for configuration.
    """
    
    def __init__(
        self,
        name: str,
        client: DatabaseClient,
        config: Optional[ConnectionConfig] = None,
        connect_func: Optional[Callable] = None,
        health_check_func: Optional[Callable] = None
    ):
        """
        Initialize connection manager.
        
        Args:
            name: Connection name for logging
            client: Database client instance
            config: Optional connection config (uses settings if None)
            connect_func: Optional custom connect function
            health_check_func: Optional custom health check function
        """
        self.name = name
        self.client = client
        self.config = config or get_settings().connection
        
        # Use custom functions if provided, otherwise use client methods
        self.connect_func = connect_func or self._default_connect
        self.health_check_func = health_check_func or self._default_health_check
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self._reconnect_lock = asyncio.Lock()
        
        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_breaker_opened_at: Optional[datetime] = None
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._auto_reconnect_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "health_checks": 0,
            "failed_health_checks": 0,
            "circuit_breaker_trips": 0,
            "last_error": None,
            "uptime_start": None,
            "total_downtime": 0.0,
            "last_disconnect": None
        }
        
        logger.info(f"ConnectionManager initialized for {name}")
    
    # =========================================================================
    # CONNECTION LIFECYCLE
    # =========================================================================
    
    async def connect(self) -> bool:
        """
        Establish connection with circuit breaker protection.
        
        Returns:
            True if connected successfully
        """
        # Check circuit breaker
        if self.state == ConnectionState.FAILED:
            if not self._should_attempt_recovery():
                logger.warning(f"Circuit breaker OPEN for {self.name}")
                return False
            else:
                logger.info(f"Circuit breaker recovery attempt for {self.name}")
                self.state = ConnectionState.DISCONNECTED
        
        # Attempt connection
        success = await self._reconnect()
        
        if success:
            # Start health check worker
            if not self._health_check_task or self._health_check_task.done():
                self._health_check_task = asyncio.create_task(
                    self._health_check_worker()
                )
        
        return success
    
    async def disconnect(self) -> None:
        """Gracefully disconnect and cleanup resources."""
        logger.info(f"Disconnecting {self.name}")
        
        # Cancel background tasks
        for task in [self._health_check_task, self._auto_reconnect_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close connection
        if self.client:
            try:
                await self.client.close()
            except Exception as e:
                logger.error(f"Error closing {self.name}: {e}")
        
        # Update state
        if self.state == ConnectionState.CONNECTED:
            self._record_disconnect()
        
        self.state = ConnectionState.DISCONNECTED
        logger.info(f"{self.name} disconnected")
    
    @asynccontextmanager
    async def get_connection(self):
        """
        Get connection as async context manager.
        Ensures connection is established and handles errors.
        """
        # Ensure connected
        if self.state != ConnectionState.CONNECTED:
            if not await self.connect():
                raise RuntimeError(f"Failed to connect to {self.name}")
        
        try:
            yield self.client
        except Exception as e:
            logger.error(f"Error during {self.name} operation: {e}")
            self.stats["last_error"] = str(e)
            
            # Mark as disconnected if connection error
            if "connection" in str(e).lower():
                self.state = ConnectionState.DISCONNECTED
            
            raise
    
    # =========================================================================
    # RECONNECTION LOGIC
    # =========================================================================
    
    async def _reconnect(self) -> bool:
        """
        Attempt to establish or reestablish connection with exponential backoff.
        
        Returns:
            True if connection established
        """
        async with self._reconnect_lock:
            # Check if already connected
            if self.state == ConnectionState.CONNECTED:
                return True
            
            # Prevent concurrent reconnection
            if self.state == ConnectionState.RECONNECTING:
                return False
            
            self.state = ConnectionState.RECONNECTING
            retry_count = 0
            current_delay = self.config.retry_delay
            
            while retry_count < self.config.max_retries:
                try:
                    logger.info(
                        f"Connection attempt {retry_count + 1}/{self.config.max_retries} "
                        f"for {self.name}"
                    )
                    self.stats["connection_attempts"] += 1
                    
                    # Attempt connection
                    await self.connect_func()
                    
                    # Verify with health check
                    if await self._is_healthy():
                        self.state = ConnectionState.CONNECTED
                        self.stats["successful_connections"] += 1
                        self._consecutive_failures = 0
                        
                        if not self.stats["uptime_start"]:
                            self.stats["uptime_start"] = datetime.now()
                        
                        logger.info(f"Successfully connected to {self.name}")
                        return True
                    else:
                        raise RuntimeError("Health check failed after connection")
                
                except Exception as e:
                    retry_count += 1
                    self.stats["failed_connections"] += 1
                    self.stats["last_error"] = str(e)
                    logger.error(
                        f"Connection attempt {retry_count} failed for {self.name}: {e}"
                    )
                    
                    if retry_count < self.config.max_retries:
                        logger.info(f"Retrying in {current_delay} seconds...")
                        await asyncio.sleep(current_delay)
                        current_delay = min(current_delay * 2, 60)  # Exponential backoff
            
            # Handle failure
            self._consecutive_failures += 1
            
            # Check if circuit breaker should trip
            if self._consecutive_failures >= self.config.circuit_breaker_threshold:
                self.state = ConnectionState.FAILED
                self._circuit_breaker_opened_at = datetime.now()
                self.stats["circuit_breaker_trips"] += 1
                logger.error(
                    f"Circuit breaker OPENED for {self.name} after "
                    f"{self._consecutive_failures} failures"
                )
            else:
                self.state = ConnectionState.DISCONNECTED
            
            return False
    
    # =========================================================================
    # HEALTH CHECKING
    # =========================================================================
    
    async def _health_check_worker(self) -> None:
        """Background task that performs periodic health checks."""
        await asyncio.sleep(10)  # Initial delay
        
        while self.state in [ConnectionState.CONNECTED, ConnectionState.DEGRADED]:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                if self.state == ConnectionState.CONNECTED:
                    self.stats["health_checks"] += 1
                    
                    if await self._is_healthy():
                        logger.debug(f"Health check passed for {self.name}")
                    else:
                        self.stats["failed_health_checks"] += 1
                        logger.warning(f"Health check failed for {self.name}")
                        self.state = ConnectionState.DEGRADED
                        
                        # Attempt recovery
                        if not self._auto_reconnect_task or self._auto_reconnect_task.done():
                            self._auto_reconnect_task = asyncio.create_task(
                                self._auto_recovery()
                            )
            
            except asyncio.CancelledError:
                logger.info(f"Health check worker cancelled for {self.name}")
                break
            except Exception as e:
                logger.error(f"Error in health check worker for {self.name}: {e}")
    
    async def _is_healthy(self) -> bool:
        """
        Check if the current connection is healthy.
        
        Returns:
            True if healthy
        """
        if not self.client:
            return False
        
        try:
            result = await asyncio.wait_for(
                self.health_check_func(self.client),
                timeout=5.0
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Health check timed out for {self.name}")
            return False
        except Exception as e:
            logger.error(f"Health check failed for {self.name}: {e}")
            return False
    
    # =========================================================================
    # AUTO-RECOVERY
    # =========================================================================
    
    async def _auto_recovery(self) -> None:
        """Attempt automatic recovery when connection is degraded."""
        logger.info(f"Starting auto-recovery for {self.name}")
        
        await asyncio.sleep(5)  # Brief delay before recovery
        
        if await self._reconnect():
            logger.info(f"Auto-recovery successful for {self.name}")
        else:
            logger.error(f"Auto-recovery failed for {self.name}")
    
    def _should_attempt_recovery(self) -> bool:
        """
        Check if enough time has passed for circuit breaker recovery.
        
        Returns:
            True if recovery should be attempted
        """
        if not self._circuit_breaker_opened_at:
            return True
        
        elapsed = (datetime.now() - self._circuit_breaker_opened_at).total_seconds()
        return elapsed >= self.config.circuit_breaker_timeout
    
    # =========================================================================
    # DEFAULT IMPLEMENTATIONS
    # =========================================================================
    
    async def _default_connect(self) -> None:
        """Default connection implementation."""
        if hasattr(self.client, 'connect'):
            await self.client.connect()
    
    async def _default_health_check(self, client: Any) -> bool:
        """Default health check implementation."""
        if hasattr(client, 'health_check'):
            return await client.health_check()
        return True
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def _record_disconnect(self) -> None:
        """Record disconnect time for statistics."""
        if self.stats["uptime_start"]:
            uptime = datetime.now() - self.stats["uptime_start"]
            self.stats["last_disconnect"] = datetime.now()
            self.stats["uptime_start"] = None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()
        
        # Calculate uptime
        if stats["uptime_start"]:
            uptime = datetime.now() - stats["uptime_start"]
            stats["uptime_seconds"] = uptime.total_seconds()
            stats["uptime_string"] = str(uptime).split('.')[0]
        
        # Add current state
        stats["current_state"] = self.state.value
        stats["circuit_breaker_open"] = self.state == ConnectionState.FAILED
        
        # Calculate success rate
        total_attempts = stats["connection_attempts"]
        if total_attempts > 0:
            stats["success_rate"] = (
                stats["successful_connections"] / total_attempts * 100
            )
        else:
            stats["success_rate"] = 0
        
        # Calculate health check success rate
        total_health = stats["health_checks"]
        if total_health > 0:
            stats["health_check_success_rate"] = (
                (total_health - stats["failed_health_checks"]) / total_health * 100
            )
        
        return stats

# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

async def create_neo4j_connection_manager(
    neo4j_client: Any,
    config: Optional[ConnectionConfig] = None
) -> ConnectionManager:
    """
    Create a connection manager for Neo4j.
    
    Args:
        neo4j_client: Neo4j client instance
        config: Optional connection config
        
    Returns:
        Configured ConnectionManager
    """
    async def health_check(client):
        """Neo4j-specific health check."""
        try:
            # Use simple query for health check
            result = await client.query(
                "RETURN 1 as health_check LIMIT 1",
                timeout=5.0
            )
            return len(result) > 0
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False
    
    return ConnectionManager(
        name="Neo4j",
        client=neo4j_client,
        config=config,
        health_check_func=health_check
    )

async def create_qdrant_connection_manager(
    qdrant_client: Any,
    config: Optional[ConnectionConfig] = None
) -> ConnectionManager:
    """
    Create a connection manager for Qdrant.
    
    Args:
        qdrant_client: Qdrant client instance
        config: Optional connection config
        
    Returns:
        Configured ConnectionManager
    """
    async def health_check(client):
        """Qdrant-specific health check."""
        try:
            # Check collections exist
            collections = await client.get_collections()
            return collections is not None
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False
    
    return ConnectionManager(
        name="Qdrant",
        client=qdrant_client,
        config=config,
        health_check_func=health_check
    )

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ConnectionManager',
    'ConnectionState',
    'DatabaseClient',
    'create_neo4j_connection_manager',
    'create_qdrant_connection_manager'
]
