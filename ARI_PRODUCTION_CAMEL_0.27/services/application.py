import logging
import time
from typing import Optional, Dict, Any, List, Tuple, Union

from pydantic import BaseModel, Field
from fastapi import BackgroundTasks

# Import NLP and other services - USE LLM/HYBRID INTENT DETECTION
from services.nlp.hybrid_intent_detector import HybridIntentDetector, DetectionStrategy, get_hybrid_intent_detector
from services.nlp.parameter_extractor import ParameterExtractor
from services.conversation_handler import ConversationHandler
from services.battle.orchestrator import BattleOrchestrator
from services.user.knowledge_graph import UserKnowledgeGraphService
from services.ml.intelligence.coordinator import IntelligenceCoordinator
from services.memory import get_session_store
from services.cache.redis_client import RedisService, FallbackRedisService

logger = logging.getLogger("services.application")

# --- Data Models for API contract ---

class Product(BaseModel):
    id: str
    title: str
    price: float
    category: Optional[str] = None
    
class ChatResponse(BaseModel):
    response: str
    products: List[Product] = Field(default_factory=list)
    session_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ApplicationService:
    """
    The core application service that orchestrates the main business logic.
    """
    def __init__(
        self,
        conversation_handler: ConversationHandler,
        battle_orchestrator: BattleOrchestrator,
        user_kg_service: UserKnowledgeGraphService,
        intelligence_coordinator: IntelligenceCoordinator,
        redis_client: Union[RedisService, FallbackRedisService]
    ):
        """
        Initializes the service with all its required dependencies,
        which are injected by the DI container.
        """
        self.conversation_handler = conversation_handler
        self.battle_orchestrator = battle_orchestrator
        self.user_kg_service = user_kg_service
        self.intelligence_coordinator = intelligence_coordinator
        self.redis_client = redis_client
        
        # NLP tools - USE HYBRID LLM INTENT DETECTION
        self.intent_detector = get_hybrid_intent_detector(strategy=DetectionStrategy.LLM_FIRST)
        self.parameter_extractor = ParameterExtractor()

    async def process_message(
        self,
        session_id: str,
        message: str,
        user_id: Optional[str] = None,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> ChatResponse:
        """
        Main entry point for processing a user's message.
        """
        start_time = time.time()
        
        # Ensure session exists in Redis
        session_key = f"session:{session_id}"
        session_data = await self.redis_client.get_json(session_key)
        if session_data is None:
            session_data = {"history": [], "created_at": time.time(), "user_id": user_id}
            await self.redis_client.set_json(session_key, session_data, ttl=86400)  # 24 hour TTL
            
        try:
            # 1. Get session memory context
            session_store = get_session_store()
            session_context = session_store.get_session_context(session_id, user_id or "anonymous")
            conversation_summary = session_store.get_conversation_summary(session_id, user_id or "anonymous")
            
            # Enhance message with memory context if available
            enhanced_message = message
            if conversation_summary:
                enhanced_message = f"{conversation_summary} | Current request: {message}"
                logger.info(f"Enhanced message with memory context: {len(conversation_summary)} chars")
            
            # 2. Detect intent and extract parameters using LLM/HYBRID - enhanced message
            hybrid_result = await self.intent_detector.detect_intent_and_extract(enhanced_message)
            intent = hybrid_result.primary_intent
            score = hybrid_result.confidence
            params = hybrid_result.extracted_parameters
            
            # Merge with stored preferences
            stored_preferences = session_store.get_user_preferences(session_id, user_id or "anonymous")
            if stored_preferences:
                # Merge stored preferences with current extraction
                for key, value in stored_preferences.items():
                    if key not in params or not params[key]:
                        params[key] = value
                logger.info(f"Merged stored preferences: {stored_preferences}")
            
            logger.info(f"LLM Intent: {intent.name} (Score: {score:.2f}, Method: {hybrid_result.detection_method}), Params: {params}")

            # 2. Get user context
            user_context = await self._get_user_context(user_id)

            # 3. Route based on intent and conversation flow
            from models.types import SearchIntent
            
            # First check conversation handler for conversation flow
            conversation_response_type, conversation_metadata = await self.conversation_handler.handle_message(
                session_id, message, user_id
            )
            
            # SIMPLIFIED SMART ROUTING: LLM-first approach, only route to products when confident
            
            # Only search products when there's clear shopping intent
            # Default to conversation for everything else
            should_search_products = (
                conversation_response_type == "search" or 
                (intent in [SearchIntent.SPECIFIC_ITEM, SearchIntent.SALE, 
                           SearchIntent.BRAND, SearchIntent.OUTFIT, SearchIntent.BROWSE, SearchIntent.INSPIRATION] 
                 and score > 0.6) or  # Lower threshold for inspiration/analogical cases
                # Explicit product request phrases
                any(phrase in message.lower() for phrase in [
                    "i need", "recommend", "show me", "find me", "looking for",
                    "want to buy", "need to buy", "actual product", "what products"
                ])
            )
            
            if should_search_products:
                # Product search requested
                logger.info(f"Routing to product search - Intent: {intent.name}, Score: {score:.2f}")
                response_text, metadata = await self._handle_product_search(
                    message, params, user_context, background_tasks
                )
                # Update conversation context with products
                if metadata.get("products"):
                    self.conversation_handler.update_product_context(session_id, [p.get('id') for p in metadata["products"] if p.get('id')])
            else:
                # Use conversation handler response (now LLM-powered for general topics)
                logger.info(f"Routing to conversation - Response type: {conversation_response_type}")
                response_text = conversation_metadata.get("response", "I'm here to help you find amazing fashion pieces!")
                metadata = {
                    "intent": conversation_response_type,
                    "conversation_state": conversation_metadata.get("state"),
                    "conversation_metadata": conversation_metadata,
                    "llm_intent": intent.name,
                    "llm_confidence": score,
                    "llm_method": hybrid_result.detection_method
                }

            processing_time = time.time() - start_time
            metadata["processing_time_seconds"] = round(processing_time, 2)

            # Create response immediately for faster user experience
            chat_response = ChatResponse(
                response=response_text,
                products=metadata.get("products", []),
                session_id=session_id,
                metadata=metadata
            )

            # 4. Store conversation in memory for future context (background task)
            if background_tasks:
                background_tasks.add_task(
                    self._store_session_context,
                    session_id,
                    user_id or "anonymous",
                    message,
                    response_text,
                    metadata.get("products", []),
                    params
                )
            else:
                # Fallback for non-HTTP contexts (like WebSocket)
                session_store = get_session_store()
                session_store.update_session_context(
                    session_id=session_id,
                    user_id=user_id or "anonymous", 
                    message=message,
                    response=response_text,
                    products=metadata.get("products", []),
                    extracted_preferences=params
                )

            return chat_response

        except Exception as e:
            logger.error(f"Error processing message for session {session_id}: {e}", exc_info=True)
            return ChatResponse(
                response="I'm sorry, I encountered an issue while processing your request. Please try again.",
                session_id=session_id,
                metadata={"error": str(e)}
            )

    async def _handle_product_search(
        self,
        message: str,
        params: Dict[str, Any],
        user_context: Dict[str, Any],
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Orchestrates the battle system to find and recommend products.
        Enhanced with ML intelligence for better recommendations.
        """
        logger.info(f"Handling product search for query: '{message}'")
        
        # Generate ML intelligence for the battle agents
        ml_intelligence = None
        try:
            ml_intelligence = await self._generate_ml_intelligence(
                message, params, user_context
            )
            logger.info(f"Generated ML intelligence with {len(ml_intelligence)} intelligence packets")
        except Exception as e:
            logger.warning(f"ML intelligence generation failed: {e}, continuing without")
        
        battle_results = await self.battle_orchestrator.execute_battle(
            query=message,
            filters=params,
            user_context=user_context,
            ml_intelligence=ml_intelligence
        )

        products = battle_results.get("products", [])
        response_text = self._generate_product_response(products, message)
        
        metadata = {
            "intent": "product_search",
            "parameters": params,
            "products": products,
            "battle_winner": battle_results.get("judgment", {}).get("winner", "unknown")
        }
        
        return response_text, metadata

    async def _generate_ml_intelligence(
        self,
        message: str,
        params: Dict[str, Any], 
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate ML intelligence packets for the battle agents.
        
        Returns:
            Dictionary with intelligence for CypherBot and VibeBot
        """
        try:
            # Gather intelligence from ML coordinator
            intelligence_packets = await self.intelligence_coordinator.gather_intelligence(
                query=message,
                user_id=user_context.get('user_id'),
                context={
                    'occasion': params.get('occasion'),
                    'categories': params.get('categories', []),
                    'colors': params.get('colors', []),
                    'styles': params.get('styles', []),
                    'user_preferences': user_context.get('preferences', {}),
                    'user_segments': user_context.get('segments', [])
                }
            )
            
            # The coordinator already returns structured intelligence
            ml_intelligence = {
                'cypher_intel': intelligence_packets.get('cypher_intel', {}),
                'vibe_intel': intelligence_packets.get('vibe_intel', {}),
                'shared_intel': intelligence_packets.get('shared_intel', {})
            }
            
            logger.debug(f"ML Intelligence routing: CypherBot={len(ml_intelligence['cypher_intel']) if isinstance(ml_intelligence['cypher_intel'], dict) else 0}, "
                        f"VibeBot={len(ml_intelligence['vibe_intel']) if isinstance(ml_intelligence['vibe_intel'], dict) else 0}, "
                        f"Shared={len(ml_intelligence['shared_intel']) if isinstance(ml_intelligence['shared_intel'], dict) else 0}")
            
            return ml_intelligence
            
        except Exception as e:
            logger.error(f"Error generating ML intelligence: {e}", exc_info=True)
            return {}


    async def _get_user_context(self, user_id: Optional[str]) -> Dict[str, Any]:
        """
        Retrieves user details from the knowledge graph.
        """
        if not user_id:
            return {}
        try:
            return await self.user_kg_service.get_user_details(user_id) or {}
        except Exception as e:
            logger.warning(f"Could not retrieve context for user {user_id}: {e}")
            return {}

    def _generate_product_response(self, products: List[Dict], query: str) -> str:
        """
        Creates a natural, conversational response based on product results.
        """
        if not products:
            return "I couldn't find any items that matched your request. Perhaps you could describe it a bit differently for me?"

        count = len(products)
        if count == 1:
            response = f"I found one perfect item for you based on '{query}':"
        else:
            response = f"I found {count} great options for you based on '{query}':"

        for product in products[:3]:
            title = product.get("title", "an item")
            price = product.get("price", 0)
            response += f"\n- The {title} for ${price:.2f}"
            
        if count > 3:
            response += f"\n... and {count - 3} more."

        return response

    def _store_session_context(
        self,
        session_id: str,
        user_id: str,
        message: str,
        response: str,
        products: List[Dict],
        extracted_preferences: Dict[str, Any]
    ):
        """
        Background task to store session context without blocking response.
        """
        try:
            from services.memory import get_session_store
            session_store = get_session_store()
            session_store.update_session_context(
                session_id=session_id,
                user_id=user_id,
                message=message,
                response=response,
                products=products,
                extracted_preferences=extracted_preferences
            )
            logger.info(f"Stored conversation context for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to store session context for {session_id}: {e}")