import logging
import time
from typing import Optional, Dict, Any, List, Tuple

from pydantic import BaseModel, Field

# Import NLP and other services
from services.nlp.intent_detector import IntentDetector
from services.nlp.parameter_extractor import ParameterExtractor
from services.conversation_handler import ConversationHandler
from services.battle.orchestrator import BattleOrchestrator
from services.user.knowledge_graph import UserKnowledgeGraphService

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
        user_kg_service: UserKnowledgeGraphService
    ):
        """
        Initializes the service with all its required dependencies,
        which are injected by the DI container.
        """
        self.conversation_handler = conversation_handler
        self.battle_orchestrator = battle_orchestrator
        self.user_kg_service = user_kg_service
        
        # NLP tools can be instantiated here as they are lightweight
        self.intent_detector = IntentDetector()
        self.parameter_extractor = ParameterExtractor()
        
        # In-memory session tracking
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def process_message(
        self,
        session_id: str,
        message: str,
        user_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Main entry point for processing a user's message.
        """
        start_time = time.time()
        
        # Ensure session exists
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {"history": []}
            
        try:
            # 1. Detect intent and extract parameters using the correct methods
            intent_result = await self.intent_detector.detect_intent(message)
            params = self.parameter_extractor.extract_parameters(message)
            
            intent = intent_result.primary_intent
            score = intent_result.confidence
            
            logger.info(f"Intent: {intent.name} (Score: {score:.2f}), Params: {params}")

            # 2. Get user context
            user_context = await self._get_user_context(user_id)

            # 3. Route based on intent
            # Note: The IntentResult returns an enum, not a string. We compare to the enum type.
            # Assuming your models.types.SearchIntent is the enum used.
            from models.types import SearchIntent
            if intent in [SearchIntent.BROWSE, SearchIntent.SPECIFIC_ITEM, SearchIntent.SALE, SearchIntent.BRAND]:
                response_text, metadata = await self._handle_product_search(
                    message, params, user_context
                )
            else:
                response_text, metadata = await self._handle_general_conversation(
                    message, session_id
                )

            processing_time = time.time() - start_time
            metadata["processing_time_seconds"] = round(processing_time, 2)

            return ChatResponse(
                response=response_text,
                products=metadata.get("products", []),
                session_id=session_id,
                metadata=metadata
            )

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
        user_context: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Orchestrates the battle system to find and recommend products.
        """
        logger.info(f"Handling product search for query: '{message}'")
        
        battle_results = await self.battle_orchestrator.execute_battle(
            query=message,
            filters=params,
            user_context=user_context
        )

        products = battle_results.get("final_products", [])
        response_text = self._generate_product_response(products, message)
        
        metadata = {
            "intent": "product_search",
            "parameters": params,
            "products": products,
            "battle_winner": battle_results.get("judgment", {}).get("winner", "unknown")
        }
        
        return response_text, metadata

    async def _handle_general_conversation(
        self,
        message: str,
        session_id: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handles non-product related conversational turns.
        """
        logger.info(f"Handling general conversation for session: {session_id}")
        
        response_text = await self.conversation_handler.get_response(session_id, message)
        metadata = {"intent": "conversation"}
        
        return response_text, metadata

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