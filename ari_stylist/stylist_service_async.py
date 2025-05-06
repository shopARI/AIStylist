"""
Asynchronous Stylist Service

Provides a FastAPI service for the AI Stylist system with full async support.
Handles message processing, session management, and provides a REST API.
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

from ai_stylist_app_async import EnhancedAIStylistApp
from memory_integration_async import setup_stylist_memory_async

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

class ServiceStats(BaseModel):
    active_sessions: int
    queue_size: int
    worker_count: int
    uptime_seconds: float
    messages_processed: int
    errors: int
    sessions_created: int
    sessions_expired: int

class StylistServiceAsync:
    """
    Asynchronous service for the AI Stylist system.
    Handles incoming message processing and maintains sessions.
    """
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None):
        """Initialize the stylist service with all required components"""
        logger.info("Initializing Async Stylist Service...")
        
        # Connect to Neo4j
        self.neo4j_url = neo4j_url or os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
        self.neo4j_username = neo4j_username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "shopari1234")
        
        logger.info(f"Connecting to Neo4j at {self.neo4j_url}")
        
        # Create AI Stylist app with all components
        try:
            self.app = EnhancedAIStylistApp(
                neo4j_url=self.neo4j_url,
                neo4j_username=self.neo4j_username,
                neo4j_password=self.neo4j_password
            )
            logger.info("AI Stylist app initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing AI Stylist app: {e}")
            raise RuntimeError(f"Failed to initialize AI Stylist app: {e}")
        
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
            "sessions_expired": 0
        }
        self.stats_lock = asyncio.Lock()
        
        logger.info("Async Stylist Service initialized successfully")
    
    async def start(self, num_workers=None):
        """
        Start the service with worker tasks
        
        Args:
            num_workers: Number of worker tasks (default: use environment variable or 4)
        """
        logger.info("Starting Async Stylist Service...")
        
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
        
        logger.info(f"Async Stylist Service started with {num_workers} worker tasks")
    
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
        
        # Close the app resources
        try:
            await self.app.close()
            logger.info("Closed AI Stylist app resources")
        except Exception as e:
            logger.error(f"Error closing AI Stylist app: {e}")
        
        logger.info("Async Stylist Service shutdown complete")
    
    async def _message_worker(self):
        """Worker task to process messages from the queue"""
        logger.info(f"Message worker started")
        
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
                        "success": False
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
                
                # Check for expired sessions
                async with self.session_lock:
                    for session_id, last_timestamp in self.session_timestamps.items():
                        if current_time - last_timestamp > self.session_timeout_seconds:
                            sessions_to_remove.append(session_id)
                
                # Remove expired sessions
                if sessions_to_remove:
                    async with self.session_lock:
                        for session_id in sessions_to_remove:
                            if session_id in self.active_sessions:
                                del self.active_sessions[session_id]
                            if session_id in self.session_timestamps:
                                del self.session_timestamps[session_id]
                    
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
            "success": True
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
                    "success": False
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
                "last_messages": history[-3:] if history else []
            }
        except Exception as e:
            logger.error(f"Error getting session info: {e}")
            return {
                "session_id": session_id,
                "exists": True,
                "error": f"Failed to get session details: {e}"
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
            
        return {
            "active_sessions": active_session_count,
            "queue_size": self.message_queue.qsize(),
            "worker_count": len(self.workers),
            "uptime_seconds": time.time() - stats.get("start_time", time.time()),
            "messages_processed": stats.get("messages_processed", 0),
            "errors": stats.get("errors", 0),
            "sessions_created": stats.get("sessions_created", 0),
            "sessions_expired": stats.get("sessions_expired", 0)
        }

# FastAPI application
app = FastAPI(
    title="AI Stylist API",
    description="Asynchronous API for AI Stylist",
    version="1.0.0"
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
        "version": "1.0.0",
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

@app.post("/recommendations", response_model=Dict[str, Any])
async def get_recommendations(
    session_id: str,
    product_id: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = Query(5, ge=1, le=20),
    service: StylistServiceAsync = Depends(get_service)
):
    """Get product recommendations"""
    try:
        recommendations = await service.app.get_product_recommendations(
            session_id=session_id,
            product_id=product_id,
            query=query,
            limit=limit
        )
        
        return {
            "session_id": session_id,
            "recommendations": recommendations,
            "count": len(recommendations)
        }
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

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
            "success": success
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
            "success": success
        }
    except Exception as e:
        logger.error(f"Error adding preference: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    
    # Start the uvicorn server
    uvicorn.run("stylist_service_async:app", host=host, port=port, reload=False)