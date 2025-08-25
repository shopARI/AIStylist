"""
ARI Fashion AI System - Complete Main Application
Full end-to-end implementation with all ML systems registered
"""

import os
import sys
import logging
import asyncio
import uuid
import time
import secrets
from typing import Optional, Dict, Any, List, Tuple
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import bleach

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

# Import settings and DI container
from config.settings import get_settings, Settings
from di_container import DIContainer

# Battle System Components
from services.battle.orchestrator import BattleOrchestrator
from agents.cypher_bot import CypherBotAgent
from agents.vibe_bot import VibeBotAgent
from agents.judge import JudgeAriAgent

# Chat Components
from services.conversation_handler import ConversationHandler
from services.nlp.parameter_extractor import ParameterExtractor
from services.nlp.intent_detector import IntentDetector

# ML Intelligence - Import ALL systems
from services.ml.intelligence.coordinator import IntelligenceCoordinator
from services.ml.intelligence.behavioral import BehavioralIntelligence
from services.ml.intelligence.clustering import ClusteringIntelligence
from services.ml.intelligence.visual_pytorch import VisualIntelligence
from services.ml.intelligence.memory_rag import MemoryRAGIntelligence

# Connection Management
from services.connection.manager import (
    ConnectionManager,
    create_neo4j_connection_manager,
    create_qdrant_connection_manager
)

# Agent Factory
from agents.factory import get_agent_factory

# Memory Management
from services.memory.fallback_manager import FallbackMemoryManager

# Data Store
from services.data.hybrid_store import HybridDataStore

# User and Product Services
from services.user.knowledge_graph import UserKnowledgeGraphService
from services.product.retriever import ProductRetrieverService

# Cache Service
from services.cache.battle_cache import BattleCache

# ============= API Models =============

class ChatMessage(BaseModel):
    """Chat message request"""
    message: str = Field(..., description="User message", max_length=1000)
    session_id: Optional[str] = Field(None, description="Session ID")
    user_id: Optional[str] = Field(None, description="User ID")

    @validator('message')
    def sanitize_message(cls, v):
        """Sanitize user input"""
        return bleach.clean(v, strip=True)[:1000]  # Also enforce length limit

class ChatResponse(BaseModel):
    """Chat response with products"""
    response: str = Field(..., description="Ari's response")
    products: List[Dict[str, Any]] = Field(default_factory=list)
    session_id: str = Field(..., description="Session ID")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SystemStatus(BaseModel):
    """System status response"""
    status: str
    timestamp: str
    components: Dict[str, str]
    ml_systems: Dict[str, bool]
    stats: Dict[str, Any]

# ============= Enhanced AI Stylist App =============

class EnhancedAIStylistApp:
    """
    Main application class with full ML intelligence integration
    """
    
    def __init__(self, components: Dict[str, Any], settings: Settings):
        """Initialize with all components properly wired"""
        logger.info("="*60)
        logger.info("Constructing ARI Fashion AI System")
        logger.info("="*60)
        
        # Core components
        self.battle_system = components.get('battle_orchestrator')
        self.neo4j_client = components.get('neo4j')
        self.qdrant_client = components.get('qdrant')
        self.data_store = components.get('data_store')
        
        # Connection managers
        self.neo4j_conn_manager = components.get('neo4j_conn_manager')
        self.qdrant_conn_manager = components.get('qdrant_conn_manager')
        
        # Managers
        self.agent_factory = components.get('agent_factory')
        self.memory_manager = components.get('memory_manager')
        
        # Cache
        self.battle_cache = components.get('battle_cache')
        
        # NLP components
        self.parameter_extractor = ParameterExtractor()
        self.intent_detector = IntentDetector()
        
        # MODIFIED: ml_coordinator is now initialized in the async `initialize` method
        self.ml_coordinator: Optional[IntelligenceCoordinator] = None
        
        # Conversation handler
        self.conversation_handler = ConversationHandler(
            neo4j_service=self.neo4j_client,
            qdrant_service=self.qdrant_client,
            memory_manager=self.memory_manager,
            agent_factory=self.agent_factory
        )
        
        # Session management
        self.active_sessions = {}
        self.max_sessions = 100
        
        # Configuration
        self.settings = settings
        
        # Statistics
        self.request_count = 0
        self.startup_time = datetime.now()
        
        logger.info("✅ ARI Fashion AI System constructed. Awaiting async initialization.")

    # ADDED: New async initialize method
    async def initialize(self):
        """Asynchronously initialize long-running components like ML models."""
        logger.info("Starting asynchronous initialization of ARI application...")
        self.ml_coordinator = await self._initialize_ml_coordinator()
        logger.info("✅ ARI Fashion AI System initialized successfully")
        self._log_system_status()
    
    # MODIFIED: Method signature is now async
    async def _initialize_ml_coordinator(self) -> IntelligenceCoordinator:
        """Initialize ML coordinator with ALL REAL intelligence systems"""
        logger.info("Registering ML Intelligence Systems...")
        
        # Create coordinator
        coordinator = IntelligenceCoordinator(
            data_store=self.data_store,
            user_kg=self.neo4j_client,
            product_retriever=self.qdrant_client,
            memory_setup_func=self.memory_manager.create_memory if self.memory_manager else None
        )
        
        # Register REAL ML systems
        registered_count = 0
        
        # 1. Behavioral Intelligence (RFM + Apriori)
        if self.neo4j_client and self.data_store:
            try:
                behavioral = BehavioralIntelligence(
                    product_kg=self.data_store,
                    user_kg=self.neo4j_client,
                    memory_setup_func=self.memory_manager.create_memory if self.memory_manager else None,
                    min_support=0.01,
                    min_confidence=0.3,
                    min_lift=1.0
                )
                await behavioral.initialize()  # ADDED
                coordinator.register_intelligence_system("behavioral", behavioral, weight=1.1)
                logger.info("✅ Registered: Behavioral Intelligence (RFM + Apriori)")
                registered_count += 1
            except Exception as e:
                logger.error(f"Failed to register Behavioral Intelligence: {e}")
        
        # 2. Clustering Intelligence (KMeans)
        if self.data_store:
            try:
                clustering = ClusteringIntelligence(
                    product_kg=self.data_store,
                    n_clusters=8,
                    min_cluster_size=5,
                    use_minibatch=True
                )
                # MODIFIED: Await initialization directly instead of creating a background task
                await clustering.initialize_clusters() # Assuming this is the new initialize method
                coordinator.register_intelligence_system("clustering", clustering, weight=1.0)
                logger.info("✅ Registered: Clustering Intelligence (KMeans)")
                registered_count += 1
            except Exception as e:
                logger.error(f"Failed to register Clustering Intelligence: {e}")
        
        # 3. Visual Intelligence (PyTorch)
        if self.data_store:
            try:
                visual = VisualIntelligence(
                    product_kg=self.data_store,
                    model_name='resnet50',
                    device='auto',
                    enable_caching=True,
                    cache_size=1000
                )
                await visual.initialize()  # ADDED
                coordinator.register_intelligence_system("visual", visual, weight=1.2)
                logger.info("✅ Registered: Visual Intelligence (ResNet50)")
                registered_count += 1
            except Exception as e:
                logger.error(f"Failed to register Visual Intelligence: {e}")
        
        # 4. Memory RAG Intelligence
        if self.memory_manager and self.data_store:
            try:
                memory_rag = MemoryRAGIntelligence(
                    product_kg=self.data_store,
                    user_kg=self.neo4j_client,
                    memory_setup_func=self.memory_manager.create_memory,
                    token_limit=2048
                )
                await memory_rag.initialize()  # ADDED
                coordinator.register_intelligence_system("memory_rag", memory_rag, weight=1.3)
                logger.info("✅ Registered: Memory RAG Intelligence")
                registered_count += 1
            except Exception as e:
                logger.error(f"Failed to register Memory RAG Intelligence: {e}")
        
        logger.info(f"Registered {registered_count} ML intelligence systems")
        return coordinator
    
    # ... (the rest of EnhancedAIStylistApp is unchanged)
    
    async def _initialize_clusters(self, clustering: ClusteringIntelligence):
        """Initialize clustering in background"""
        try:
            logger.info("Starting background cluster initialization...")
            await clustering.initialize_clusters()
            logger.info("✅ Cluster initialization complete")
        except Exception as e:
            logger.error(f"Cluster initialization failed: {e}")
    
    def _log_system_status(self):
        """Log system configuration status"""
        logger.info("="*60)
        logger.info("System Configuration:")
        logger.info(f"  - Neo4j: {'✅' if self.neo4j_client else '❌'}")
        logger.info(f"  - Qdrant: {'✅' if self.qdrant_client else '❌'}")
        logger.info(f"  - Battle System: {'✅' if self.battle_system else '❌'}")
        logger.info(f"  - ML Coordinator: {'✅' if self.ml_coordinator else '❌'}")
        logger.info(f"  - Memory Manager: {'✅' if self.memory_manager else '❌'}")
        logger.info(f"  - Cache: {'✅' if self.battle_cache else '❌'}")
        logger.info("="*60)
    
    async def send_message(
        self, 
        session_id: str, 
        message: str, 
        user_id: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Process message through complete system with ML intelligence"""
        
        self.request_count += 1
        start_time = time.time()
        
        # Create session if needed WITH SIZE LIMIT
        if session_id not in self.active_sessions:
            # Check if we've hit the session limit
            if len(self.active_sessions) >= self.max_sessions:
                # Remove the oldest session
                oldest_session = min(
                    self.active_sessions.items(), 
                    key=lambda x: x[1]["created"]
                )
                del self.active_sessions[oldest_session[0]]
                logger.info(f"Evicted old session: {oldest_session[0][:8]}...")
            
            self.active_sessions[session_id] = {
                "created": datetime.now(),
                "messages": [],
                "user_id": user_id
            }
        
        # Add message to session
        self.active_sessions[session_id]["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now()
        })
        
        try:
            # 1. Extract parameters
            params = self.parameter_extractor.extract(message)
            logger.info(f"Parameters extracted: {params}")
            
            # 2. Detect intent
            intent = self.intent_detector.detect(message)
            logger.info(f"Intent detected: {intent}")
            
            # 3. Get user context
            user_context = await self._get_user_context(user_id)
            
            # 4. Route based on intent
            if intent in ["search", "product_search", "recommendation"]:
                response, metadata = await self._handle_product_search(
                    message, params, user_context, session_id, user_id
                )
            else:
                response, metadata = await self._handle_general_conversation(
                    message, session_id
                )
            
            # Add response to session
            self.active_sessions[session_id]["messages"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now(),
                "metadata": metadata
            })
            
            # Track performance
            processing_time = time.time() - start_time
            metadata["processing_time"] = processing_time
            
            logger.info(f"Message processed in {processing_time:.2f}s")
            return response, metadata
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return "I encountered an error processing your request. Please try again.", {
                "error": str(e),
                "intent": intent if 'intent' in locals() else "unknown"
            }
    
    async def _get_user_context(self, user_id: Optional[str]) -> Dict[str, Any]:
        """Get comprehensive user context"""
        if not user_id or not self.neo4j_client:
            return {}
        
        try:
            # Get user details from Neo4j
            user_details = await self.neo4j_client.get_user_details(user_id)
            
            if user_details:
                return {
                    "user_id": user_id,
                    "preferences": user_details.get("preferences", {}),
                    "segments": user_details.get("segments", []),
                    "style_profile": user_details.get("style_profile"),
                    "total_purchases": user_details.get("total_purchases", 0),
                    "lifetime_value": user_details.get("lifetime_value", 0),
                    "vip_status": user_details.get("lifetime_value", 0) > 1000
                }
            
            # Create new user if not exists
            await self.neo4j_client.create_or_update_user(user_id)
            return {"user_id": user_id, "new_user": True}
            
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return {"user_id": user_id}
    
    async def _handle_product_search(
        self,
        message: str,
        params: Dict[str, Any],
        user_context: Dict[str, Any],
        session_id: str,
        user_id: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle product search with full ML intelligence and battle system"""
        
        logger.info("="*40)
        logger.info(f"PRODUCT SEARCH: {message[:50]}...")
        logger.info("="*40)
        
        # Check cache first
        cache_key = f"{message}:{user_id}:{str(params)}"
        if self.battle_cache:
            cached = await self.battle_cache.get(cache_key)
            if cached:
                logger.info("Cache hit for product search")
                return cached["response"], cached["metadata"]
        
        # 1. Gather ML intelligence from ALL systems
        ml_intelligence = await self.ml_coordinator.gather_intelligence(
            query=message,
            user_id=user_id,
            session_id=session_id,
            context=user_context
        )
        
        # Log ML intelligence gathered
        if ml_intelligence["metadata"]["sources"]:
            logger.info(f"ML Intelligence gathered from: {', '.join(ml_intelligence['metadata']['sources'])}")
        else:
            logger.warning("No ML intelligence available")
        
        # 2. Build filters from parameters
        filters = self._build_filters(params)
        
        # 3. Execute BATTLE with ML intelligence
        logger.info("Executing battle system...")
        battle_results = await self.battle_system.execute_battle(
            query=message,
            filters=filters,
            limit=5,
            user_context=user_context,
            ml_intelligence=ml_intelligence
        )
        
        # Extract products from battle results
        products = battle_results.get("final_products", [])
        
        # 4. Generate Ari's response
        response = self._generate_product_response(products, message)
        
        # 5. Record interactions if products found
        if products and user_id:
            for product in products[:3]:  # Top 3
                asyncio.create_task(
                    self._record_interaction(user_id, product.get("id"), "recommended")
                )
        
        # Prepare metadata
        metadata = {
            "products": products,
            "parameters": params,
            "intent": "product_search",
            "ml_enhanced": bool(ml_intelligence["metadata"]["sources"]),
            "ml_sources": ml_intelligence["metadata"]["sources"],
            "battle_winner": battle_results.get("judgment", {}).get("winner"),
            "filters_applied": filters
        }
        
        # Cache the result
        if self.battle_cache and products:
            await self.battle_cache.set(cache_key, {
                "response": response,
                "metadata": metadata
            }, ttl=300)  # 5 minutes
        
        return response, metadata
    
    def _build_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build search filters from extracted parameters"""
        filters = {}
        
        if params.get("categories"):
            filters["category"] = params["categories"][0]
        
        if params.get("colors"):
            filters["colors"] = params["colors"]
        
        if params.get("price_range"):
            min_price, max_price = params["price_range"]
            if min_price is not None:
                filters["min_price"] = min_price
            if max_price is not None:
                filters["max_price"] = max_price
        
        if params.get("brands"):
            filters["brands"] = params["brands"]
        
        if params.get("occasions"):
            filters["occasions"] = params["occasions"]
        
        return filters
    
    def _generate_product_response(self, products: List[Dict], query: str) -> str:
        """Generate Ari's natural response about products"""
        if not products:
            return (
                "I couldn't find any products matching your criteria right now. "
                "Could you tell me more about what you're looking for? "
                "Maybe a different style, color, or price range?"
            )
        
        # Natural, conversational response
        count = len(products)
        response_parts = []
        
        # Opening based on count and query
        if count == 1:
            response_parts.append("I found the perfect item for you!")
        elif count <= 3:
            response_parts.append(f"I found {count} great options that match what you're looking for!")
        else:
            response_parts.append(f"Great news! I found {count} fantastic pieces for you!")
        
        # Describe top 3 products naturally
        for i, product in enumerate(products[:3], 1):
            title = product.get('title', 'Item')
            price = product.get('price', 0)
            category = product.get('category', '')
            
            if i == 1:
                response_parts.append(f"\n\nMy top pick is the {title} at ${price:.2f}.")
                if category:
                    response_parts.append(f"This {category.lower()} would be perfect for what you described.")
            elif i == 2:
                response_parts.append(f"\n\nAnother excellent choice is the {title} for ${price:.2f}.")
            elif i == 3:
                response_parts.append(f"\n\nYou might also love the {title} at ${price:.2f}.")
        
        # Closing
        if count > 3:
            response_parts.append(f"\n\nI have {count - 3} more options if you'd like to see them!")
        
        response_parts.append("\n\nWould you like more details about any of these, or should I keep looking?")
        
        return " ".join(response_parts)
    
    async def _handle_general_conversation(
        self, 
        message: str, 
        session_id: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle general conversation"""
        try:
            response = await self.conversation_handler.get_response(session_id, message)
            return response, {"intent": "conversation"}
        except Exception as e:
            logger.error(f"Conversation handler error: {e}")
            return "I'm here to help you find the perfect outfit! What are you looking for today?", {
                "intent": "conversation",
                "error": str(e)
            }
    
    async def _record_interaction(self, user_id: str, product_id: str, interaction_type: str):
        """Record user interaction in background"""
        try:
            if self.neo4j_client and product_id:
                await self.neo4j_client.record_product_interaction(
                    user_id, product_id, interaction_type
                )
                
                # Update ML systems
                await self.ml_coordinator.record_interaction(
                    user_id, product_id, interaction_type
                )
        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        status = {
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "uptime": str(datetime.now() - self.startup_time),
            "request_count": self.request_count,
            "active_sessions": len(self.active_sessions),
            "components": {},
            "ml_systems": {},
            "stats": {}
        }
        
        # Check components
        status["components"]["neo4j"] = "connected" if self.neo4j_client else "disconnected"
        status["components"]["qdrant"] = "connected" if self.qdrant_client else "disconnected"
        status["components"]["battle_system"] = "ready" if self.battle_system else "not_initialized"
        status["components"]["ml_coordinator"] = "ready" if self.ml_coordinator else "not_initialized"
        
        # Get ML system status
        if self.ml_coordinator:
            ml_stats = self.ml_coordinator.get_stats()
            status["ml_systems"] = ml_stats.get("ml_systems_active", [])
            status["stats"]["ml"] = ml_stats
        
        # Get battle stats
        if self.battle_system:
            battle_stats = await self.battle_system.get_stats()
            status["stats"]["battles"] = battle_stats
        
        # Database stats
        if self.neo4j_client:
            try:
                neo4j_stats = await self.neo4j_client.get_database_statistics()
                status["stats"]["neo4j"] = neo4j_stats
            except:
                pass
        
        if self.qdrant_client:
            try:
                qdrant_stats = await self.qdrant_client.get_collection_stats()
                status["stats"]["qdrant"] = qdrant_stats
            except:
                pass
        
        return status
    
    async def cleanup_sessions(self):
        """Clean up old sessions"""
        cutoff_time = datetime.now().timestamp() - 3600  # 1 hour
        to_remove = []
        
        for session_id, session in self.active_sessions.items():
            if session["created"].timestamp() < cutoff_time:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self.active_sessions[session_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old sessions")
    
    async def close(self):
        """Clean up resources"""
        logger.info("Shutting down ARI Fashion AI System...")
        
        # Cleanup ML systems
        if hasattr(self.ml_coordinator, 'ml_systems'):
            for name, system in self.ml_coordinator.ml_systems.items():
                if hasattr(system, 'cleanup'):
                    try:
                        await system.cleanup()
                        logger.info(f"Cleaned up {name}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {name}: {e}")
        
        logger.info("Shutdown complete")


# ============= Component Manager =============

class ComponentManager:
    """Manages all system components"""
    
    def __init__(self):
        self.components: Dict[str, Any] = {}
        self.app: Optional[EnhancedAIStylistApp] = None

    async def initialize_all(self, settings: Settings) -> None:
        """Initialize all components with proper error handling"""
        logger.info("="*60)
        logger.info("Starting component initialization...")
        logger.info("="*60)
        
        try:
            # 1. DI Container
            container = DIContainer(settings)
            await container.initialize()
            self.components['container'] = container
            logger.info("✅ DI Container initialized")
            
            # 2. Database services
            neo4j_client = await container.get("UserKnowledgeGraphService")
            qdrant_client = await container.get("ProductRetrieverService")
            
            # ADDED: Explicitly await initialization for each service
            if neo4j_client:
                await neo4j_client.initialize()
            if qdrant_client:
                await qdrant_client.initialize()
                
            logger.info("✅ Database services initialized")
            
            # 3. Connection managers with health checks
            if neo4j_client:
                self.components['neo4j_conn_manager'] = await create_neo4j_connection_manager(neo4j_client)
                
            if qdrant_client:
                self.components['qdrant_conn_manager'] = await create_qdrant_connection_manager(qdrant_client)
            
            # 4. HybridDataStore
            data_store = HybridDataStore(neo4j_client, qdrant_client)
            await data_store.initialize()
            logger.info("✅ HybridDataStore initialized")
            
            self.components['neo4j'] = neo4j_client
            self.components['qdrant'] = qdrant_client
            self.components['data_store'] = data_store
            
            # 5. Battle system
            battle_orchestrator = BattleOrchestrator(
                neo4j_client=neo4j_client,
                qdrant_client=qdrant_client,
                enable_cache=True
            )
            self.components['battle_orchestrator'] = battle_orchestrator
            logger.info("✅ Battle Orchestrator initialized")
            
            # 6. Cache
            self.components['battle_cache'] = BattleCache(ttl=300, max_size=1000)
            
            # 7. Memory manager
            memory_manager = FallbackMemoryManager(
                neo4j_client=neo4j_client
            )
            await memory_manager.initialize() # ADDED: Good practice to add for all services
            self.components['memory_manager'] = memory_manager
            logger.info("✅ Memory Manager initialized")
            
            # 8. Agent factory
            factory = await get_agent_factory()
            self.components['agent_factory'] = factory
            logger.info("✅ Agent Factory initialized")
            
            # 9. Create main application
            self.app = EnhancedAIStylistApp(self.components, settings)
            await self.app.initialize() # ADDED: Call the app's own async initializer
            
            logger.info("="*60)
            logger.info("✅ ALL COMPONENTS INITIALIZED SUCCESSFULLY")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Component initialization failed: {e}", exc_info=True)
            raise
    
    async def cleanup(self):
        """Clean up all components"""
        logger.info("Starting component cleanup...")
        
        if self.app:
            await self.app.close()
        
        # Close connection managers
        for key in ['neo4j_conn_manager', 'qdrant_conn_manager']:
            if key in self.components and hasattr(self.components[key], 'disconnect'):
                try:
                    await self.components[key].disconnect()
                except Exception as e:
                    logger.error(f"Error closing {key}: {e}")
        
        # Cleanup container
        if 'container' in self.components:
            await self.components['container'].cleanup()
        
        logger.info("Component cleanup complete")

# ============= FastAPI Application =============

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    component_manager = ComponentManager()
    
    try:
        settings = get_settings()
        await component_manager.initialize_all(settings)
        
        app.state.component_manager = component_manager
        app.state.stylist_app = component_manager.app
        app.state.settings = settings
        app.state.limiter = limiter
        
        # Start background tasks
        asyncio.create_task(periodic_cleanup(component_manager.app))
        
        logger.info("="*60)
        logger.info("🚀 ARI FASHION AI SYSTEM READY")
        logger.info("="*60)
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    finally:
        await component_manager.cleanup()
        logger.info("Shutdown complete")

async def periodic_cleanup(app: EnhancedAIStylistApp):
    """Periodic cleanup task"""
    while True:
        await asyncio.sleep(3600)  # Every hour
        try:
            await app.cleanup_sessions()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

app = FastAPI(
    title="ARI Fashion AI System",
    description="AI-Powered Fashion Stylist with Battle System and ML Intelligence",
    version="3.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )

# ============= API Endpoints =============

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ARI Fashion AI System",
        "version": "3.0.0",
        "status": "operational",
        "message": "Welcome to ARI, your AI fashion stylist!"
    }

@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/status", response_model=SystemStatus)
async def system_status():
    """Detailed system status"""
    stylist_app = app.state.stylist_app
    status = await stylist_app.get_system_status()
    
    return SystemStatus(
        status=status["status"],
        timestamp=status["timestamp"],
        components=status["components"],
        ml_systems={"active": status["ml_systems"]},
        stats=status["stats"]
    )

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat_with_ari(
    request: Request,
    chat_message: ChatMessage,
):
    """Main chat endpoint to interact with Ari"""
    stylist_app = app.state.stylist_app
    
    # Generate session ID if not provided
    session_id = chat_message.session_id or str(uuid.uuid4())
    
    try:
        response_text, metadata = await stylist_app.send_message(
            session_id=session_id,
            message=chat_message.message,
            user_id=chat_message.user_id
        )
        
        return ChatResponse(
            response=response_text,
            products=metadata.get("products", []),
            session_id=session_id,
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="I'm having trouble processing your request. Please try again."
        )

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    stylist_app = app.state.stylist_app
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            message = data.get("message", "")
            user_id = data.get("user_id")
            
            # Process message
            response_text, metadata = await stylist_app.send_message(
                session_id=session_id,
                message=message,
                user_id=user_id
            )
            
            # Send response
            await websocket.send_json({
                "response": response_text,
                "products": metadata.get("products", []),
                "metadata": metadata
            })
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()

# ============= Main Entry Point =============

if __name__ == "__main__":
    import uvicorn
    
    # Production configuration
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to False in production
        log_level="info",
        workers=1,  # Increase for production
        access_log=True
    )