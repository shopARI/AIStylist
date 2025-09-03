import logging
import asyncio
import uuid
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import time
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dependency_injector.wiring import inject, Provide

from di.container import DIContainer, initialize_container, cleanup_container
from services.application import ApplicationService, ChatResponse
from services.memory.cleanup import start_memory_service, stop_memory_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)

# Security constants
MAX_MESSAGE_LENGTH = 2000
MAX_SESSION_ID_LENGTH = 100
MAX_USER_ID_LENGTH = 100
ALLOWED_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

# --- Application Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown.
    Initializes the DI container and cleans it up gracefully.
    """
    container = await initialize_container()
    app.state.container = container
    
    # Start memory cleanup service
    await start_memory_service()
    logger.info("Memory cleanup service started")
    
    logger.info("Application startup complete.")
    yield
    
    # Shutdown
    await stop_memory_service()
    logger.info("Memory cleanup service stopped")
    await cleanup_container(container)
    logger.info("Application shutdown complete.")

# --- API Models ---
def validate_safe_string(value: str) -> str:
    """Validate string contains only safe characters."""
    if not all(c in ALLOWED_CHARS for c in value):
        raise ValueError("Contains invalid characters")
    return value

class ChatMessage(BaseModel):
    message: str = Field(..., max_length=MAX_MESSAGE_LENGTH, description="Chat message content")
    session_id: str = Field(..., max_length=MAX_SESSION_ID_LENGTH, description="Required session identifier for conversation continuity")
    user_id: str = Field(..., max_length=MAX_USER_ID_LENGTH, description="Required user identifier for personalization")
    
    @validator('message')
    def validate_message_content(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty")
        # Basic XSS prevention
        dangerous_patterns = ['<script', 'javascript:', 'data:', 'vbscript:', 'onload=', 'onerror=']
        lower_msg = v.lower()
        if any(pattern in lower_msg for pattern in dangerous_patterns):
            raise ValueError("Message contains potentially dangerous content")
        return v.strip()
    
    @validator('session_id', 'user_id')
    def validate_ids(cls, v):
        if not v.strip():
            raise ValueError("ID cannot be empty")
        return validate_safe_string(v.strip())

# --- FastAPI App ---
app = FastAPI(
    title="ARI Fashion AI System",
    description="AI-Powered Fashion Stylist with a Conversational Recommendation Engine.",
    version="4.0.0",
    lifespan=lifespan
)

# Add rate limiting to FastAPI
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Development frontend
        "http://localhost:8080",  # Alternative dev port
        "https://aistylist.app",  # Production domain (replace with your actual domain)
        "https://api.aistylist.app"  # Production API domain
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- API Endpoints ---
@app.get("/")
async def root():
    return {"message": "ARI Fashion AI System is operational."}

async def check_redis_health(redis_client) -> bool:
    """Check if Redis is accessible."""
    try:
        if hasattr(redis_client, 'ping'):
            # Handle both sync and async ping methods
            ping_result = redis_client.ping()
            if asyncio.iscoroutine(ping_result):
                await ping_result
            return True
        else:
            # For FallbackRedisService, just return True
            return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False

async def check_neo4j_health(neo4j_service) -> bool:
    """Check if Neo4j is accessible."""
    try:
        if hasattr(neo4j_service, 'run_query'):
            # Simple test query
            await neo4j_service.run_query("RETURN 1 as test_connection")
            return True
        return False
    except Exception as e:
        logger.warning(f"Neo4j health check failed: {e}")
        return False

async def check_qdrant_health(qdrant_service) -> bool:
    """Check if Qdrant is accessible."""
    try:
        if hasattr(qdrant_service, 'client') and qdrant_service.client:
            # Try to get collections info
            collections = await asyncio.to_thread(qdrant_service.client.get_collections)
            return True
        return False
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")
        return False

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    from services.memory.cleanup import get_memory_service
    
    memory_service = get_memory_service()
    memory_healthy = memory_service.is_memory_healthy()
    
    return {
        "status": "healthy" if memory_healthy else "degraded",
        "timestamp": time.time(),
        "memory_healthy": memory_healthy,
        "version": "4.0.0"
    }

@app.get("/health/detailed")
@limiter.limit("5/minute")
async def detailed_health_check(request: Request):
    """Detailed health check with memory and system stats."""
    from services.memory.cleanup import get_memory_service
    import psutil
    
    memory_service = get_memory_service()
    memory_stats = memory_service.get_memory_stats()
    
    # System stats
    system_stats = {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
    }
    
    # Get services from DI container for health checks
    container = app.state.container
    try:
        redis_client = await container.redis_client()
        neo4j_service = await container.user_kg_service()
        qdrant_service = await container.product_retriever_service()
        
        # Run actual health checks
        redis_healthy = await check_redis_health(redis_client)
        neo4j_healthy = await check_neo4j_health(neo4j_service)
        qdrant_healthy = await check_qdrant_health(qdrant_service)
        
    except Exception as e:
        logger.error(f"Error accessing services for health check: {e}")
        redis_healthy = False
        neo4j_healthy = False
        qdrant_healthy = False
    
    # Service health checks
    health_checks = {
        "memory_service": memory_service.is_memory_healthy(),
        "redis_available": redis_healthy,
        "neo4j_available": neo4j_healthy,
        "qdrant_available": qdrant_healthy
    }
    
    overall_status = "healthy" if all(health_checks.values()) else "degraded"
    
    return {
        "status": overall_status,
        "timestamp": time.time(),
        "memory_stats": memory_stats,
        "system_stats": system_stats,
        "health_checks": health_checks,
        "version": "4.0.0"
    }

@app.get("/metrics")
@limiter.limit("10/minute") 
async def get_metrics(request: Request):
    """Prometheus-style metrics endpoint."""
    from services.memory.cleanup import get_memory_service
    
    memory_service = get_memory_service()
    stats = memory_service.get_memory_stats()
    
    # Generate Prometheus-style metrics
    metrics = [
        f'# HELP ari_memory_usage_mb Current memory usage in MB',
        f'# TYPE ari_memory_usage_mb gauge',
        f'ari_memory_usage_mb {stats["process_memory_mb"]}',
        f'',
        f'# HELP ari_tracked_objects Number of tracked objects',
        f'# TYPE ari_tracked_objects gauge', 
        f'ari_tracked_objects {stats["tracked_objects"]}',
        f'',
        f'# HELP ari_cleanup_runs_total Total number of cleanup runs',
        f'# TYPE ari_cleanup_runs_total counter',
        f'ari_cleanup_runs_total {stats["cleanup_runs"]}',
        f'',
        f'# HELP ari_cached_objects Number of cached objects',
        f'# TYPE ari_cached_objects gauge',
        f'ari_cached_objects {stats["cached_objects"]}',
        f''
    ]
    
    return Response(
        content='\n'.join(metrics),
        media_type='text/plain'
    )

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
@inject
async def chat_with_ari(
    request: Request,
    chat_message: ChatMessage,
    background_tasks: BackgroundTasks,
    app_service: ApplicationService = Depends(Provide[DIContainer.application_service])
):
    """
    Main chat endpoint to interact with Ari.
    The ApplicationService is automatically injected by the DI container.
    """
    try:
        response = await app_service.process_message(
            session_id=chat_message.session_id,
            message=chat_message.message,
            user_id=chat_message.user_id,
            background_tasks=background_tasks
        )
        return response
    except Exception as e:
        # Move detailed error logging to background to reduce response time
        background_tasks.add_task(
            logger.error,
            f"Chat endpoint error: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again."
        )

@app.websocket("/ws/{session_id}")
@inject
async def websocket_endpoint(
    websocket: WebSocket, 
    session_id: str,
    app_service: ApplicationService = Depends(Provide[DIContainer.application_service])
):
    """WebSocket endpoint for real-time chat with enhanced security."""
    # Validate session_id before accepting connection
    try:
        if len(session_id) > MAX_SESSION_ID_LENGTH:
            await websocket.close(code=4000, reason="Session ID too long")
            return
        validate_safe_string(session_id)
    except Exception:
        await websocket.close(code=4000, reason="Invalid session ID")
        return
        
    await websocket.accept()
    logger.info(f"WebSocket connection established for session: {session_id}")
    
    # Connection rate limiting (simple per-session)
    message_count = 0
    last_reset = time.time()
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Rate limiting: 30 messages per minute per connection
            current_time = time.time()
            if current_time - last_reset > 60:
                message_count = 0
                last_reset = current_time
            
            message_count += 1
            if message_count > 30:
                await websocket.send_json({
                    "error": "Rate limit exceeded. Please slow down.",
                    "code": "RATE_LIMITED"
                })
                continue
            
            message = data.get("message", "")
            user_id = data.get("user_id")
            
            # Validate required fields
            if not user_id:
                await websocket.send_json({"error": "user_id is required"})
                continue
                
            # Validate user_id
            try:
                if len(user_id) > MAX_USER_ID_LENGTH:
                    await websocket.send_json({"error": "user_id too long"})
                    continue
                validate_safe_string(user_id)
            except Exception:
                await websocket.send_json({"error": "Invalid user_id format"})
                continue
            
            # Validate message
            if len(message) > MAX_MESSAGE_LENGTH:
                await websocket.send_json({
                    "error": "Message too long",
                    "max_length": MAX_MESSAGE_LENGTH
                })
                continue
                
            if not message.strip():
                await websocket.send_json({"error": "Message cannot be empty"})
                continue
            
            # Basic XSS prevention
            dangerous_patterns = ['<script', 'javascript:', 'data:', 'vbscript:', 'onload=', 'onerror=']
            if any(pattern in message.lower() for pattern in dangerous_patterns):
                await websocket.send_json({"error": "Message contains potentially dangerous content"})
                continue

            response = await app_service.process_message(
                session_id=session_id,
                message=message.strip(),
                user_id=user_id.strip()
            )
            await websocket.send_json(response.model_dump())
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
        await websocket.close(code=1011)

# --- Main Entry Point for Running the Server ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )