"""
Asynchronous Stylist Service

Provides a FastAPI service for the AI Stylist system with full async support.
Handles message processing, session management, and provides a REST API.

MIGRATED: Updated for CAMEL-AI 0.2.64 compatibility.
Uses AgentFactory and MemoryManager for all operations.
"""

import os
import time
import logging
import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from functools import lru_cache

import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from aiolimiter import AsyncLimiter

# MIGRATED: Import updated components
from ai_stylist_app_async import EnhancedAIStylistApp
from memory_integration_async import MemoryManager
from agent_factory import get_agent_factory
from camel_imports import CAMEL_AVAILABLE, LongtermAgentMemory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('stylist_service.log')
    ]
)

logger = logging.getLogger("stylist_service_async")

# Rate limiter for OpenAI API calls (20 requests per minute by default)
rate_limiter = AsyncLimiter(20, 60)

# Memory pool for optimization
class MemoryPool:
    """Optimized memory pool for better performance"""
    
    def __init__(self, max_size=100):
        self.pool = {}
        self.max_size = max_size
        self.lock = asyncio.Lock()
    
    async def get_memory(self, user_id: str, neo4j_client=None):
        """Get memory from pool or create new one"""
        async with self.lock:
            if user_id in self.pool:
                return self.pool[user_id]
            
            # Create new memory using MemoryManager
            manager = MemoryManager(neo4j_client)
            memory = await manager.create_memory(
                user_id=user_id,
                enable_mcp=True
            )
            
            # Add to pool if space available
            if len(self.pool) < self.max_size:
                self.pool[user_id] = memory
                logger.info(f"Added memory to pool for user {user_id}")
            
            return memory
    
    async def cleanup_inactive(self, inactive_users: List[str]):
        """Remove memories for inactive users"""
        async with self.lock:
            for user_id in inactive_users:
                if user_id in self.pool:
                    del self.pool[user_id]
                    logger.info(f"Removed memory from pool for inactive user {user_id}")

# Global memory pool
memory_pool = MemoryPool()

# Pydantic models for API
class MessageRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    message_id: Optional[str] = None

class MessageResponse(BaseModel):
    message_id: str
    session_id: str
    response: str
    data: Optional[Dict[str, Any]] = None
    processing_time: float
    success: bool
    camel_version: str = "0.2.64"  # MIGRATED: Track version

class SessionInfo(BaseModel):
    session_id: str
    exists: bool
    user_id: Optional[str] = None
    start_time: Optional[str] = None
    last_activity: Optional[float] = None
    time_since_activity: Optional[float] = None
    message_count: Optional[int] = None
    last_messages: Optional[List[Dict[str, Any]]] = []
    error: Optional[str] = None
    memory_status: Optional[str] = None  # MIGRATED: Track memory status

class ServiceStats(BaseModel):
    active_sessions: int
    queue_size: int
    worker_count: int
    uptime_seconds: float
    messages_processed: int
    errors: int
    sessions_created: int
    sessions_expired: int
    camel_version: str = "0.2.64"  # MIGRATED: Track version
    migration_status: str = "complete"  # MIGRATED: Track migration status
    memory_pool_size: int = 0  # MIGRATED: Track memory pool

class StylistServiceAsync:
    """
    Asynchronous service for the AI Stylist system.
    Handles incoming message processing and maintains sessions.
    
    MIGRATED: Now uses CAMEL-AI 0.2.64 patterns throughout.
    """
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None):
        """Initialize the stylist service with all required components"""
        logger.info("Initializing Async Stylist Service with CAMEL-AI 0.2.64...")
        
        # MIGRATED: Verify CAMEL availability
        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL-AI 0.2.64 is not available. Please install camel-ai>=0.2.64")
        
        # Connect to Neo4j
        self.neo4j_url = neo4j_url or os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
        self.neo4j_username = neo4j_username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "shopari1234")
        
        logger.info(f"Connecting to Neo4j at {self.neo4j_url}")
        
        # MIGRATED: Create AI Stylist app with enhanced error handling
        try:
            self.app = EnhancedAIStylistApp(
                neo4j_url=self.neo4j_url,
                neo4j_username=self.neo4j_username,
                neo4j_password=self.neo4j_password
            )
            logger.info("✅ AI Stylist app initialized successfully with CAMEL 0.2.64")
        except Exception as e:
            logger.error(f"❌ Error initializing AI Stylist app: {e}")
            raise RuntimeError(f"Failed to initialize AI Stylist app: {e}")
        
        # MIGRATED: Initialize AgentFactory and MemoryManager
        self.agent_factory = get_agent_factory()
        self.memory_manager = MemoryManager(self.app.product_kg)
        
        # Active sessions tracking
        self.active_sessions = {}
        self.session_timestamps = {}
        self.session_lock = asyncio.Lock()  # Async lock for session access
        
        # Message queue for processing
        self.message_queue = asyncio.Queue()
        self.shutdown_flag = asyncio.Event()
        
        # Session cleanup settings
        self.session_timeout_seconds = 3600  # 1 hour
        
        # Worker tasks
        self.workers = []
        self.cleanup_task = None
        
        # Statistics tracking
        self.stats = {
            "start_time": time.time(),
            "messages_processed": 0,
            "errors": 0,
            "sessions_created": 0,
            "sessions_expired": 0,
            "migration_verified": False
        }
        self.stats_lock = asyncio.Lock()
        
        logger.info("✅ Async Stylist Service initialized successfully with CAMEL 0.2.64")
    
    async def verify_migration_compatibility(self) -> bool:
        """
        Verify all components are using CAMEL 0.2.64 patterns.
        
        MIGRATED: New verification method for migration status.
        """
        try:
            # Test AgentFactory
            factory = get_agent_factory()
            if not factory:
                raise RuntimeError("AgentFactory not available")
            
            # Test MemoryManager
            manager = MemoryManager(self.app.product_kg)
            if not manager:
                raise RuntimeError("MemoryManager not available")
            
            # Test memory creation
            test_memory = await manager.create_memory(
                user_id="test_user",
                enable_mcp=True
            )
            if not isinstance(test_memory, LongtermAgentMemory):
                raise RuntimeError("Memory creation failed")
            
            # Test agent creation
            test_agent = await factory.create_stylist_agent(
                memory=test_memory,
                enable_mcp=True
            )
            if not test_agent:
                raise RuntimeError("Agent creation failed")
            
            # Update stats
            async with self.stats_lock:
                self.stats["migration_verified"] = True
            
            logger.info("✅ Migration verification successful - CAMEL 0.2.64 compatible")
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration verification failed: {e}")
            return False
    
    async def start(self, num_workers=None):
        """
        Start the service with worker tasks
        
        Args:
            num_workers: Number of worker tasks (default: use environment variable or 4)
        """
        logger.info("Starting Async Stylist Service with CAMEL 0.2.64...")
        
        # MIGRATED: Verify migration compatibility
        if not await self.verify_migration_compatibility():
            raise RuntimeError("Migration verification failed - cannot start service")
        
        # Start worker tasks for message processing
        if num_workers is None:
            num_workers = int(os.environ.get("NUM_WORKER_TASKS", "4"))
        
        self.workers = []
        
        for i in range(num_workers):
            worker = asyncio.create_task(
                self._message_worker(),
                name=f"StylistWorker-{i}"
            )
            self.workers.append(worker)
            logger.info(f"Started worker task {i}")
        
        # Start session cleanup task
        self.cleanup_task = asyncio.create_task(
            self._session_cleanup_worker(),
            name="SessionCleanup"
        )
        logger.info("Started session cleanup task")
        
        logger.info(f"✅ Async Stylist Service started with {num_workers} worker tasks")
    
    async def shutdown(self):
        """Gracefully shut down the service"""
        logger.info("Shutting down Async Stylist Service...")
        
        # Set shutdown flag to stop worker tasks
        self.shutdown_flag.set()
        
        # Cancel workers
        for worker in self.workers:
            try:
                worker.cancel()
            except Exception as e:
                logger.error(f"Error canceling worker task: {e}")
        
        # Cancel cleanup task
        if self.cleanup_task:
            try:
                self.cleanup_task.cancel()
            except Exception as e:
                logger.error(f"Error canceling cleanup task: {e}")
        
        # MIGRATED: Clean up AgentFactory resources
        try:
            await self.agent_factory.cleanup()
            logger.info("Cleaned up AgentFactory resources")
        except Exception as e:
            logger.error(f"Error cleaning up AgentFactory: {e}")
        
        # Close the app resources
        try:
            await self.app.close()
            logger.info("Closed AI Stylist app resources")
        except Exception as e:
            logger.error(f"Error closing AI Stylist app: {e}")
        
        logger.info("✅ Async Stylist Service shutdown complete")
    
    async def _message_worker(self):
        """Worker task to process messages from the queue"""
        logger.info(f"Message worker started with CAMEL 0.2.64")
        
        while not self.shutdown_flag.is_set():
            try:
                # Get a message from the queue with timeout
                try:
                    task = await asyncio.wait_for(self.message_queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    continue
                
                # Process the message
                try:
                    await self._process_message_task(task)
                    
                    # Update statistics
                    async with self.stats_lock:
                        self.stats["messages_processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    
                    # Update error statistics
                    async with self.stats_lock:
                        self.stats["errors"] += 1
                    
                    # Prepare error result
                    result = {
                        "message_id": task.get("message_id"),
                        "session_id": task.get("session_id"),
                        "error": str(e),
                        "success": False,
                        "camel_version": "0.2.64"
                    }
                    
                    # Call the callback if provided
                    callback = task.get("callback")
                    if callback:
                        try:
                            await callback(result)
                        except Exception as e:
                            logger.error(f"Error in callback: {e}")
                
                # Mark task as done
                self.message_queue.task_done()
                
            except asyncio.CancelledError:
                # Worker task was cancelled during shutdown
                break
            except Exception as e:
                logger.error(f"Unexpected error in message worker: {e}", exc_info=True)
    
    async def _session_cleanup_worker(self):
        """Worker task to clean up inactive sessions"""
        logger.info("Session cleanup worker started")
        
        while not self.shutdown_flag.is_set():
            try:
                # Sleep for a while between cleanup runs
                await asyncio.sleep(60)  # Check every minute
                
                current_time = time.time()
                sessions_to_remove = []
                inactive_users = []
                
                # Check for expired sessions
                async with self.session_lock:
                    for session_id, last_timestamp in self.session_timestamps.items():
                        if current_time - last_timestamp > self.session_timeout_seconds:
                            sessions_to_remove.append(session_id)
                            
                            # Track inactive users for memory cleanup
                            if session_id in self.active_sessions:
                                session = await self.app.get_session(session_id)
                                if session and hasattr(session, 'user_id') and session.user_id:
                                    inactive_users.append(session.user_id)
                
                # Remove expired sessions
                if sessions_to_remove:
                    async with self.session_lock:
                        for session_id in sessions_to_remove:
                            if session_id in self.active_sessions:
                                del self.active_sessions[session_id]
                            if session_id in self.session_timestamps:
                                del self.session_timestamps[session_id]
                    
                    # MIGRATED: Clean up memory pool for inactive users
                    if inactive_users:
                        await memory_pool.cleanup_inactive(inactive_users)
                    
                    # Update statistics
                    async with self.stats_lock:
                        self.stats["sessions_expired"] += len(sessions_to_remove)
                    
                    logger.info(f"Cleaned up {len(sessions_to_remove)} inactive sessions")
                
            except asyncio.CancelledError:
                # Cleanup task was cancelled during shutdown
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}", exc_info=True)
    
    async def _process_message_task(self, task):
        """
        Process a message task from the queue
        
        Args:
            task: Message task dictionary with message details
        """
        message_id = task.get("message_id")
        user_id = task.get("user_id")
        session_id = task.get("session_id")
        message = task.get("message")
        callback = task.get("callback")
        
        logger.info(f"Processing message {message_id} for session {session_id}")
        
        # Get or create session
        if not session_id or session_id not in self.active_sessions:
            session_id = await self.app.create_session(user_id=user_id)
            
            async with self.session_lock:
                self.active_sessions[session_id] = True
                self.session_timestamps[session_id] = time.time()
            
            # Update statistics
            async with self.stats_lock:
                self.stats["sessions_created"] += 1
            
            logger.info(f"Created new session {session_id} for user {user_id}")
        else:
            # Update session timestamp
            async with self.session_lock:
                self.session_timestamps[session_id] = time.time()
        
        # Process the message - using rate limiter for OpenAI API calls
        start_time = time.time()
        
        async with rate_limiter:
            response, data = await self.app.send_message(session_id, message)
            
        processing_time = time.time() - start_time
        
        logger.info(f"Message {message_id} processed in {processing_time:.2f} seconds")
        
        # Prepare result
        result = {
            "message_id": message_id,
            "session_id": session_id,
            "response": response,
            "data": data,
            "processing_time": processing_time,
            "success": True,
            "camel_version": "0.2.64"  # MIGRATED: Track version
        }
        
        # Call the callback if provided
        if callback:
            try:
                await callback(result)
            except Exception as e:
                logger.error(f"Error in callback for message {message_id}: {e}")
        
        # Store result in task for synchronous mode
        task["result"] = result
    
    async def process_message(
        self, 
        message: str, 
        user_id: Optional[str] = None, 
        session_id: Optional[str] = None, 
        message_id: Optional[str] = None,
        callback: Optional[callable] = None, 
        sync: bool = False
    ) -> Union[str, Dict]:
        """
        Process a user message
        
        Args:
            message: The user message
            user_id: Optional user ID for personalization
            session_id: Optional session ID for continuing conversations
            message_id: Optional message ID for tracking
            callback: Optional callback function for result delivery
            sync: If True, process synchronously; otherwise queue for async processing
            
        Returns:
            If sync is True, returns the result dictionary; otherwise returns message_id for tracking
        """
        # Generate message ID if not provided
        if not message_id:
            message_id = f"msg_{int(time.time())}_{hash(message) % 10000}"
        
        # Create the task
        task = {
            "message_id": message_id,
            "user_id": user_id,
            "session_id": session_id,
            "message": message,
            "callback": callback,
            "result": None
        }
        
        # Process synchronously or asynchronously
        if sync:
            try:
                await self._process_message_task(task)
                return task.get("result", {})
            except Exception as e:
                logger.error(f"Error in synchronous message processing: {e}", exc_info=True)
                return {
                    "message_id": message_id,
                    "session_id": session_id,
                    "error": str(e),
                    "success": False,
                    "camel_version": "0.2.64"
                }
        else:
            await self.message_queue.put(task)
            return message_id
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about a session
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with session information
        """
        if not session_id:
            return {"error": "No session ID provided"}
            
        async with self.session_lock:
            if session_id not in self.active_sessions:
                return {"error": f"Session not found: {session_id}"}
                
            # Get session timestamp
            last_activity = self.session_timestamps.get(session_id)
            time_since_activity = time.time() - last_activity if last_activity else None
            
        # Get session from app
        session = await self.app.get_session(session_id)
        if not session:
            return {
                "session_id": session_id,
                "exists": False,
                "error": "Session exists in service but not in app"
            }
            
        # MIGRATED: Check memory status
        memory_status = "unknown"
        if hasattr(session, 'memory') and session.memory:
            memory_status = "active"
        elif hasattr(session, 'user_id') and session.user_id:
            memory_status = "pooled" if session.user_id in memory_pool.pool else "not_loaded"
        
        # Get session history
        try:
            history = await session.get_conversation_history(limit=10)
            
            return {
                "session_id": session_id,
                "exists": True,
                "user_id": session.user_id,
                "start_time": session.session_start_time.isoformat(),
                "last_activity": last_activity,
                "time_since_activity": time_since_activity,
                "message_count": len(session.messages),
                "last_messages": history[-3:] if history else [],
                "memory_status": memory_status  # MIGRATED: Include memory status
            }
        except Exception as e:
            logger.error(f"Error getting session info: {e}")
            return {
                "session_id": session_id,
                "exists": True,
                "error": f"Failed to get session details: {e}",
                "memory_status": memory_status
            }
    
    async def get_service_stats(self) -> Dict[str, Any]:
        """
        Get service statistics
        
        Returns:
            Dictionary with service statistics
        """
        async with self.session_lock:
            active_session_count = len(self.active_sessions)
            
        async with self.stats_lock:
            stats = self.stats.copy()
        
        # MIGRATED: Include memory pool stats
        memory_pool_size = len(memory_pool.pool)
        
        return {
            "active_sessions": active_session_count,
            "queue_size": self.message_queue.qsize(),
            "worker_count": len(self.workers),
            "uptime_seconds": time.time() - stats.get("start_time", time.time()),
            "messages_processed": stats.get("messages_processed", 0),
            "errors": stats.get("errors", 0),
            "sessions_created": stats.get("sessions_created", 0),
            "sessions_expired": stats.get("sessions_expired", 0),
            "camel_version": "0.2.64",
            "migration_status": "complete" if stats.get("migration_verified", False) else "incomplete",
            "memory_pool_size": memory_pool_size
        }

# FastAPI application
app = FastAPI(
    title="AI Stylist API",
    description="Asynchronous API for AI Stylist - CAMEL-AI 0.2.64",
    version="2.0.0"  # MIGRATED: Updated version
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Customize this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store service instance
service_instance = None

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    global service_instance
    service_instance = StylistServiceAsync()
    await service_instance.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown service on app shutdown"""
    global service_instance
    if service_instance:
        await service_instance.shutdown()

# Dependency for getting the service instance
async def get_service():
    """Get the service instance"""
    return service_instance

@app.get("/health", response_model=Dict[str, Any])
async def health_check(service: StylistServiceAsync = Depends(get_service)):
    """Health check endpoint"""
    stats = await service.get_service_stats()
    return {
        "status": "healthy",
        "service": "ai_stylist",
        "version": "2.0.0",
        "camel_version": "0.2.64",  # MIGRATED: Include CAMEL version
        "migration_status": stats.get("migration_status", "unknown"),
        "stats": stats
    }

@app.post("/chat", response_model=MessageResponse)
async def chat(
    request: MessageRequest,
    background_tasks: BackgroundTasks,
    service: StylistServiceAsync = Depends(get_service)
):
    """Chat endpoint to process messages"""
    try:
        # Process message synchronously to return faster
        result = await service.process_message(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id,
            message_id=request.message_id,
            sync=True
        )
        
        return result
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/session/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    service: StylistServiceAsync = Depends(get_service)
):
    """Get session information"""
    return await service.get_session_info(session_id)

@app.get("/stats", response_model=ServiceStats)
async def get_stats(service: StylistServiceAsync = Depends(get_service)):
    """Get service statistics"""
    return await service.get_service_stats()

# MIGRATED: Enhanced recommendations endpoint with better error handling
@app.post("/recommendations", response_model=Dict[str, Any])
async def get_recommendations(
    session_id: str,
    product_id: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = Query(5, ge=1, le=20),
    service: StylistServiceAsync = Depends(get_service)
):
    """Get product recommendations with comprehensive fallback chain"""
    
    # Track which method succeeded for logging/analytics
    successful_method = None
    recommendations = []
    
    # Method 1: Try full personalized recommendations
    try:
        logger.info(f"Attempting personalized recommendations for session {session_id}")
        recommendations = await service.app.get_product_recommendations(
            session_id=session_id,
            product_id=product_id,
            query=query,
            limit=limit
        )
        
        if recommendations:
            successful_method = "personalized"
            logger.info(f"Got {len(recommendations)} personalized recommendations")
        
    except Exception as e:
        logger.warning(f"Personalized recommendations failed: {e}")
        recommendations = []
    
    # Method 2: Try recommendations without session (if session was the problem)
    if not recommendations and session_id:
        try:
            logger.info("Attempting non-personalized recommendations")
            # Try to get recommendations without session-specific data
            recommendations = await _get_non_personalized_recommendations(
                service, product_id, query, limit
            )
            
            if recommendations:
                successful_method = "non_personalized"
                logger.info(f"Got {len(recommendations)} non-personalized recommendations")
                
        except Exception as e:
            logger.warning(f"Non-personalized recommendations failed: {e}")
            recommendations = []
    
    # Method 3: Try direct database fallback (bypass app layer)
    if not recommendations:
        try:
            logger.info("Attempting direct database recommendations")
            recommendations = await _get_direct_database_recommendations(
                service, product_id, query, limit
            )
            
            if recommendations:
                successful_method = "direct_database"
                logger.info(f"Got {len(recommendations)} direct database recommendations")
                
        except Exception as e:
            logger.warning(f"Direct database recommendations failed: {e}")
            recommendations = []
    
    # Method 4: Try cached/static recommendations
    if not recommendations:
        try:
            logger.info("Attempting cached/static recommendations")
            recommendations = await _get_cached_recommendations(query, limit)
            
            if recommendations:
                successful_method = "cached"
                logger.info(f"Got {len(recommendations)} cached recommendations")
                
        except Exception as e:
            logger.warning(f"Cached recommendations failed: {e}")
            recommendations = []
    
    # Method 5: Final fallback - return minimal static data
    if not recommendations:
        logger.warning("All recommendation methods failed, using minimal fallback")
        recommendations = _get_minimal_fallback_recommendations(limit)
        successful_method = "minimal_fallback"
    
    # Return response with metadata about which method worked
    return {
        "session_id": session_id,
        "recommendations": recommendations,
        "count": len(recommendations),
        "method": successful_method,
        "personalized": successful_method == "personalized",
        "fallback_used": successful_method != "personalized",
        "camel_version": "0.2.64"  # MIGRATED: Include version
    }

# Helper functions for recommendations (unchanged from original)
async def _get_non_personalized_recommendations(service, product_id, query, limit):
    """Get recommendations without session-specific personalization"""
    try:
        # Create a temporary session or use generic logic
        if product_id and hasattr(service.app.product_kg, 'get_similar_products'):
            return await service.app.product_kg.get_similar_products(product_id, limit)
        
        elif query and hasattr(service.app.product_retriever, 'search_by_natural_language'):
            return await service.app.product_retriever.search_by_natural_language(query, limit)
        
        elif hasattr(service.app.product_kg, 'get_popular_products'):
            return await service.app.product_kg.get_popular_products(limit)
            
    except Exception as e:
        logger.error(f"Error in non-personalized recommendations: {e}")
        raise

async def _get_direct_database_recommendations(service, product_id, query, limit):
    """Get recommendations by directly querying the database"""
    try:
        # Try direct Neo4j queries bypassing the app layer
        if product_id:
            # Direct similar products query
            neo4j_query = """
            MATCH (p:Product {id: $product_id})-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(similar:Product)
            WHERE similar.id <> $product_id
            RETURN 
                similar.id as id,
                similar.title as title,
                similar.price as price,
                similar.description as description,
                similar.images as images
            ORDER BY similar.visited_num DESC
            LIMIT $limit
            """
            
            result = await service.app.product_kg.query(neo4j_query, {
                "product_id": product_id,
                "limit": limit
            })
            
            if result:
                return [_format_product_from_db_record(record) for record in result]
        
        # Direct popular products query
        popular_query = """
        MATCH (p:Product)
        WHERE p.price > 0 AND p.title IS NOT NULL
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await service.app.product_kg.query(popular_query, {"limit": limit})
        
        if result:
            return [_format_product_from_db_record(record) for record in result]
            
    except Exception as e:
        logger.error(f"Error in direct database recommendations: {e}")
        raise

async def _get_cached_recommendations(query, limit):
    """Get cached or pre-computed recommendations"""
    try:
        # This could be implemented with Redis, file cache, or static data
        # For now, return empty - let other fallbacks handle it
        return []
        
    except Exception as e:
        logger.error(f"Error in cached recommendations: {e}")
        raise

def _get_minimal_fallback_recommendations(limit):
    """Final fallback - return minimal generic data"""
    # This is the absolute last resort - return generic placeholder
    return [
        {
            "id": f"fallback_{i}",
            "title": f"Featured Item {i+1}",
            "price": 50.00,
            "description": "Popular choice",
            "images": [],
            "categories": [],
            "source": "minimal_fallback"
        }
        for i in range(min(limit, 3))  # Return up to 3 generic items
    ]

def _format_product_from_db_record(record):
    """Format a database record into a product dictionary"""
    return {
        "id": record.get("id", ""),
        "title": record.get("title", "Unknown Product"),
        "price": record.get("price", 0.0),
        "description": record.get("description", ""),
        "images": _parse_images_string(record.get("images", "[]")),
        "visited_num": record.get("visited_num", 0),
        "source": "direct_database"
    }

def _parse_images_string(images_str):
    """Parse images string from database"""
    if not images_str:
        return []
    try:
        import json
        return json.loads(images_str.replace("'", '"'))
    except:
        return []

@app.post("/interaction", response_model=Dict[str, Any])
async def record_interaction(
    session_id: str,
    product_id: str,
    interaction_type: str = "viewed",
    service: StylistServiceAsync = Depends(get_service)
):
    """Record a product interaction"""
    try:
        success = await service.app.record_product_interaction(
            session_id=session_id,
            product_id=product_id,
            interaction_type=interaction_type
        )
        
        return {
            "session_id": session_id,
            "product_id": product_id,
            "interaction_type": interaction_type,
            "success": success,
            "camel_version": "0.2.64"  # MIGRATED: Include version
        }
    except Exception as e:
        logger.error(f"Error recording interaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/preference", response_model=Dict[str, Any])
async def add_preference(
    session_id: str,
    preference_type: str,
    preference_value: Any,
    service: StylistServiceAsync = Depends(get_service)
):
    """Add a user preference"""
    try:
        success = await service.app.add_user_preference(
            session_id=session_id,
            preference_type=preference_type,
            preference_value=preference_value
        )
        
        return {
            "session_id": session_id,
            "preference_type": preference_type,
            "success": success,
            "camel_version": "0.2.64"  # MIGRATED: Include version
        }
    except Exception as e:
        logger.error(f"Error adding preference: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# MIGRATED: Add migration status endpoint
@app.get("/migration", response_model=Dict[str, Any])
async def get_migration_status(service: StylistServiceAsync = Depends(get_service)):
    """Get migration status and compatibility information"""
    try:
        stats = await service.get_service_stats()
        return {
            "migration_status": "complete",
            "camel_version": "0.2.64",
            "compatibility_verified": stats.get("migration_status") == "complete",
            "features": {
                "agent_factory": True,
                "memory_manager": True,
                "longterm_memory": True,
                "mcp_support": True,
                "memory_pooling": True
            },
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting migration status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    
    # Start the uvicorn server
    uvicorn.run("stylist_service_async:app", host=host, port=port, reload=False)