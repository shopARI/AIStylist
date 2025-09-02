import logging
import asyncio
import uuid
import os
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dependency_injector.wiring import inject, Provide

from di.container import DIContainer, initialize_container, cleanup_container
from services.application import ApplicationService, ChatResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

# --- Application Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown.
    Initializes the DI container and cleans it up gracefully.
    """
    container = await initialize_container()
    app.state.container = container
    logger.info("Application startup complete.")
    yield
    await cleanup_container(container)
    logger.info("Application shutdown complete.")

# --- API Models ---
class ChatMessage(BaseModel):
    message: str = Field(..., max_length=2000)
    session_id: str = Field(..., description="Required session identifier for conversation continuity")
    user_id: str = Field(..., description="Required user identifier for personalization")

# --- FastAPI App ---
app = FastAPI(
    title="ARI Fashion AI System",
    description="AI-Powered Fashion Stylist with a Conversational Recommendation Engine.",
    version="4.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# --- API Endpoints ---
@app.get("/")
async def root():
    return {"message": "ARI Fashion AI System is operational."}

@app.post("/chat", response_model=ChatResponse)
@inject
async def chat_with_ari(
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
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            user_id = data.get("user_id")
            
            if not user_id:
                await websocket.send_json({"error": "user_id is required"})
                continue

            response = await app_service.process_message(
                session_id=session_id,
                message=message,
                user_id=user_id
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