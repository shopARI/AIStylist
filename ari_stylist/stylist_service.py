import os
import time
import logging
import threading
import queue
import signal
import sys
import json
from typing import Dict, Any, Optional, Callable, List, Union

from ai_stylist_app import AIStylistApp
from memory_integration import setup_stylist_memory
from neo4j_integration import ProductKnowledgeGraph
from product_retriever import ProductRetriever

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('stylist_service.log')
    ]
)

logger = logging.getLogger("stylist_service")

class StylistService:
    """
    Continuous service for the AI Stylist system.
    Handles incoming message processing and maintains sessions.
    """
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None):
        """Initialize the stylist service with all required components"""
        logger.info("Initializing Stylist Service...")
        
        # Connect to Neo4j
        self.neo4j_url = neo4j_url or os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
        self.neo4j_username = neo4j_username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "shopari1234")
        
        logger.info(f"Connecting to Neo4j at {self.neo4j_url}")
        
        # Create AI Stylist app with all components
        try:
            self.app = AIStylistApp(
                neo4j_url=self.neo4j_url,
                neo4j_username=self.neo4j_username,
                neo4j_password=self.neo4j_password
            )
            logger.info("AI Stylist app initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing AI Stylist app: {e}")
            raise RuntimeError(f"Failed to initialize AI Stylist app: {e}")
        
        # Active sessions tracking with thread safety
        self.active_sessions = {}
        self.session_timestamps = {}
        self.session_lock = threading.RLock()  # Reentrant lock for nested lock acquisition
        
        # Message queue for processing
        self.message_queue = queue.Queue()
        self.shutdown_flag = threading.Event()
        
        # Session cleanup settings
        self.session_timeout_seconds = 3600  # 1 hour
        
        # Worker threads
        self.workers = []
        self.cleanup_thread = None
        
        # Statistics tracking
        self.stats = {
            "messages_processed": 0,
            "errors": 0,
            "sessions_created": 0,
            "sessions_expired": 0
        }
        self.stats_lock = threading.Lock()
        
        logger.info("Stylist Service initialized successfully")
    
    def start(self, num_workers=None):
        """
        Start the service with worker threads
        
        Args:
            num_workers: Number of worker threads (default: use environment variable or 4)
        """
        logger.info("Starting Stylist Service...")
        
        # Start worker threads for message processing
        if num_workers is None:
            num_workers = int(os.environ.get("NUM_WORKER_THREADS", "4"))
        
        self.workers = []
        
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._message_worker,
                name=f"StylistWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            logger.info(f"Started worker thread {i}")
        
        # Start session cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._session_cleanup_worker,
            name="SessionCleanup",
            daemon=True
        )
        self.cleanup_thread.start()
        logger.info("Started session cleanup thread")
        
        # Setup signal handlers for clean shutdown
        self._setup_signal_handlers()
        
        logger.info(f"Stylist Service started with {num_workers} worker threads")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        try:
            # Handle termination signals
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            logger.info("Signal handlers registered")
        except (AttributeError, ValueError) as e:
            # This can happen in environments where signal isn't fully supported
            logger.warning(f"Failed to register signal handlers: {e}")
    
    def shutdown(self):
        """Gracefully shut down the service"""
        logger.info("Shutting down Stylist Service...")
        
        # Set shutdown flag to stop worker threads
        self.shutdown_flag.set()
        
        # Wait for workers to complete
        for worker in self.workers:
            try:
                worker.join(timeout=5)
                if worker.is_alive():
                    logger.warning(f"Worker thread {worker.name} did not complete in time")
            except Exception as e:
                logger.error(f"Error waiting for worker {worker.name}: {e}")
        
        # Wait for cleanup thread
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            try:
                self.cleanup_thread.join(timeout=5)
                if self.cleanup_thread.is_alive():
                    logger.warning("Cleanup thread did not complete in time")
            except Exception as e:
                logger.error(f"Error waiting for cleanup thread: {e}")
        
        # Close the app resources
        try:
            self.app.close()
            logger.info("Closed AI Stylist app resources")
        except Exception as e:
            logger.error(f"Error closing AI Stylist app: {e}")
        
        logger.info("Stylist Service shutdown complete")
    
    def _signal_handler(self, sig, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {sig}")
        self.shutdown()
        sys.exit(0)
    
    def _message_worker(self):
        """Worker thread to process messages from the queue"""
        logger.info(f"Message worker {threading.current_thread().name} started")
        
        while not self.shutdown_flag.is_set():
            try:
                # Get a message from the queue with timeout
                try:
                    task = self.message_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Process the message
                try:
                    self._process_message_task(task)
                    
                    # Update statistics
                    with self.stats_lock:
                        self.stats["messages_processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    
                    # Update error statistics
                    with self.stats_lock:
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
                            callback(result)
                        except Exception as e:
                            logger.error(f"Error in callback: {e}")
                
                # Mark task as done
                self.message_queue.task_done()
                
            except Exception as e:
                logger.error(f"Unexpected error in message worker: {e}", exc_info=True)
    
    def _session_cleanup_worker(self):
        """Worker thread to clean up inactive sessions"""
        logger.info("Session cleanup worker started")
        
        while not self.shutdown_flag.is_set():
            try:
                # Sleep for a while between cleanup runs
                time.sleep(60)  # Check every minute
                
                current_time = time.time()
                sessions_to_remove = []
                
                # Check for expired sessions
                with self.session_lock:
                    for session_id, last_timestamp in self.session_timestamps.items():
                        if current_time - last_timestamp > self.session_timeout_seconds:
                            sessions_to_remove.append(session_id)
                
                # Remove expired sessions
                if sessions_to_remove:
                    with self.session_lock:
                        for session_id in sessions_to_remove:
                            if session_id in self.active_sessions:
                                del self.active_sessions[session_id]
                            if session_id in self.session_timestamps:
                                del self.session_timestamps[session_id]
                    
                    # Update statistics
                    with self.stats_lock:
                        self.stats["sessions_expired"] += len(sessions_to_remove)
                    
                    logger.info(f"Cleaned up {len(sessions_to_remove)} inactive sessions")
                
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}", exc_info=True)
    
    def _process_message_task(self, task):
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
            session_id = self.app.create_session(user_id=user_id)
            
            with self.session_lock:
                self.active_sessions[session_id] = True
                self.session_timestamps[session_id] = time.time()
            
            # Update statistics
            with self.stats_lock:
                self.stats["sessions_created"] += 1
            
            logger.info(f"Created new session {session_id} for user {user_id}")
        else:
            # Update session timestamp
            with self.session_lock:
                self.session_timestamps[session_id] = time.time()
        
        # Process the message
        start_time = time.time()
        response, data = self.app.send_message(session_id, message)
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
                callback(result)
            except Exception as e:
                logger.error(f"Error in callback for message {message_id}: {e}")
        
        # Store result in task for synchronous mode
        task["result"] = result
    
    def process_message(self, message: str, user_id: Optional[str] = None, 
                      session_id: Optional[str] = None, message_id: Optional[str] = None,
                      callback: Optional[Callable] = None, sync: bool = False) -> Union[str, Dict]:
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
                self._process_message_task(task)
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
            self.message_queue.put(task)
            return message_id
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about a session
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with session information
        """
        if not session_id:
            return {"error": "No session ID provided"}
            
        with self.session_lock:
            if session_id not in self.active_sessions:
                return {"error": f"Session not found: {session_id}"}
                
            # Get session timestamp
            last_activity = self.session_timestamps.get(session_id)
            time_since_activity = time.time() - last_activity if last_activity else None
            
        # Get session from app
        session = self.app.get_session(session_id)
        if not session:
            return {
                "session_id": session_id,
                "exists": False,
                "error": "Session exists in service but not in app"
            }
            
        # Get session history
        try:
            history = session.get_conversation_history(limit=10)
            
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
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        Get service statistics
        
        Returns:
            Dictionary with service statistics
        """
        with self.session_lock:
            active_session_count = len(self.active_sessions)
            
        with self.stats_lock:
            stats = self.stats.copy()
            
        return {
            "active_sessions": active_session_count,
            "queue_size": self.message_queue.qsize(),
            "worker_count": len(self.workers),
            "uptime_seconds": time.time() - self.stats.get("start_time", time.time()),
            "messages_processed": stats.get("messages_processed", 0),
            "errors": stats.get("errors", 0),
            "sessions_created": stats.get("sessions_created", 0),
            "sessions_expired": stats.get("sessions_expired", 0)
        }

# REST API server for the stylist service
class StylistServiceAPI:
    """
    Simple REST API wrapper for the stylist service
    """
    
    def __init__(self, service=None):
        """
        Initialize the API with a stylist service
        
        Args:
            service: StylistService instance (creates a new one if None)
        """
        self.service = service or StylistService()
    
    def start_api_server(self, host='0.0.0.0', port=5000):
        """
        Start the Flask API server
        
        Args:
            host: Host to bind the server to
            port: Port to bind the server to
        """
        try:
            from flask import Flask, request, jsonify
            
            # Start the service
            self.service.start()
            
            # Create Flask app
            app = Flask("AI_Stylist_API")
            
            @app.route('/health', methods=['GET'])
            def health_check():
                """Health check endpoint"""
                return jsonify({
                    "status": "healthy",
                    "service": "ai_stylist",
                    "version": "1.0.0",
                    "stats": self.service.get_service_stats()
                })
            
            @app.route('/chat', methods=['POST'])
            def chat():
                """Chat endpoint to process messages"""
                try:
                    data = request.json
                    
                    if not data or 'message' not in data:
                        return jsonify({
                            "error": "Message is required"
                        }), 400
                    
                    # Extract parameters
                    message = data['message']
                    user_id = data.get('user_id')
                    session_id = data.get('session_id')
                    
                    # Process message synchronously
                    result = self.service.process_message(
                        message=message,
                        user_id=user_id,
                        session_id=session_id,
                        sync=True
                    )
                    
                    return jsonify(result)
                except Exception as e:
                    logger.error(f"Error in chat endpoint: {e}", exc_info=True)
                    return jsonify({
                        "error": f"Server error: {str(e)}"
                    }), 500
            
            @app.route('/session/<session_id>', methods=['GET'])
            def get_session(session_id):
                """Get session information"""
                return jsonify(self.service.get_session_info(session_id))
            
            @app.route('/stats', methods=['GET'])
            def get_stats():
                """Get service statistics"""
                return jsonify(self.service.get_service_stats())
            
            # Run the Flask app
            logger.info(f"Starting API server on {host}:{port}")
            app.run(host=host, port=port)
            
        except Exception as e:
            logger.error(f"Error starting API server: {e}", exc_info=True)
            self.service.shutdown()
            raise

# Main entry point when run as a script
if __name__ == "__main__":
    try:
        # Create and start service with API
        api = StylistServiceAPI()
        
        # Get port from environment or use default
        port = int(os.environ.get("API_PORT", "5000"))
        
        # Start API server (this will start the service as well)
        api.start_api_server(port=port)
        
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
