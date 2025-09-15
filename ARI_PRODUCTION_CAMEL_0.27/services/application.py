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
from services.memory.session_memory import get_enhanced_session_memory
from services.memory.coordinator import get_unified_memory_coordinator
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
        
        # Enhanced session memory with persistence
        self.session_memory = get_enhanced_session_memory(redis_client)
        
        # Unified memory coordinator for comprehensive memory management
        self.memory_coordinator = get_unified_memory_coordinator(redis_client)
        
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
            # 1. Get comprehensive enhanced context from unified memory coordinator
            enhanced_context = await self.memory_coordinator.get_enhanced_context(
                session_id=session_id,
                user_id=user_id,
                current_query=message,
                intent=None,  # Will be determined after intent detection
                include_similar_conversations=True,
                include_user_preferences=True,
                max_similar_contexts=3
            )
            
            # Extract components for backward compatibility
            session_context = enhanced_context.get('session_context', '')
            user_context_data = enhanced_context.get('user_context', {})
            similar_conversations = enhanced_context.get('similar_conversations', [])
            memory_insights = enhanced_context.get('memory_insights', {})
            
            # Get user preferences from unified context (more comprehensive than session-only)
            stored_preferences = {}
            if user_context_data and user_context_data.get('active_preferences'):
                for category, prefs in user_context_data['active_preferences'].items():
                    # Convert preference format for compatibility
                    stored_preferences[category] = [p['value'] for p in prefs[:3] if p['confidence'] > 0.4]
            
            # Enhance message with comprehensive memory context
            enhanced_message = message
            context_parts = []
            
            # Add session context
            if session_context:
                context_parts.append(f"Recent conversation: {session_context}")
            
            # Add user preference context
            if stored_preferences:
                pref_summary = ", ".join([f"{k}: {', '.join(v[:2])}" for k, v in stored_preferences.items() if v])
                if pref_summary:
                    context_parts.append(f"User preferences: {pref_summary}")
            
            # Add similar conversation insights
            if similar_conversations:
                similar_summary = f"Similar past queries: {len(similar_conversations)} found"
                context_parts.append(similar_summary)
            
            # Get current conversation context for intent detection (critical fix)
            conversation_context = self.conversation_handler.get_or_create_session(session_id, user_id)
            if conversation_context.current_products:
                product_context = f"Currently viewing {len(conversation_context.current_products)} recommended products"
                context_parts.append(product_context)
                logger.info(f"Added product context for intent detection: {len(conversation_context.current_products)} products")
            
            # Add conversation state context for better intent detection
            if conversation_context.state.value != "new":
                state_context = f"Conversation state: {conversation_context.state.value}"
                context_parts.append(state_context)
            
            # Build enhanced message
            if context_parts:
                memory_context = " | ".join(context_parts)
                enhanced_message = f"{memory_context} | Current request: {message}"
                logger.info(f"Enhanced message with comprehensive memory context: {len(memory_context)} chars")
            
            # 2. Detect intent and extract parameters using LLM/HYBRID - use RAW message for intent detection
            # Enhanced context can bias intent detection, so use clean message for intent classification
            hybrid_result = await self.intent_detector.detect_intent_and_extract(message)
            intent = hybrid_result.primary_intent
            score = hybrid_result.confidence
            params = hybrid_result.extracted_parameters
            
            # Merge with stored preferences from enhanced session memory
            if stored_preferences:
                # Only merge stored preferences if current extraction is empty for that key
                # AND the current message doesn't explicitly mention conflicting values
                for key, value in stored_preferences.items():
                    if key not in params or not params[key]:
                        # Special handling for colors - don't merge if current message mentions any color
                        if key == "colors" and any(color in message.lower() for color in [
                            "red", "blue", "green", "yellow", "black", "white", "pink", "purple", 
                            "orange", "brown", "gray", "grey", "navy", "beige", "gold", "silver"
                        ]):
                            continue  # Skip merging stored color if current message has explicit color
                        params[key] = value
                logger.info(f"Merged stored preferences from session memory: {stored_preferences}")
            
            logger.info(f"LLM Intent: {intent.name} (Score: {score:.2f}, Method: {hybrid_result.detection_method}), Params: {params}")

            # 2. Get user context
            user_context = await self._get_user_context(user_id)

            # 3. Route based on intent and conversation flow
            from models.types import SearchIntent
            
            # First check conversation handler for conversation flow
            conversation_response_type, conversation_metadata = await self.conversation_handler.handle_message(
                session_id, message, user_id
            )
            
            # CONTEXT-AWARE SMART ROUTING: Consider conversation state and current products
            
            # Check if this is product continuation vs new search
            has_current_products = bool(conversation_context.current_products)
            is_product_continuation = has_current_products and any(continuation_phrase in message.lower() for continuation_phrase in [
                "this", "that", "these", "those", "it", "them", "more about", "tell me about", 
                "what about", "how about", "other colors", "different sizes", "similar to", 
                "like this", "more like", "details on", "info on", "about this"
            ])
            
            # CONVERSATION/MEMORY INTENT HANDLING - Take priority over product search
            if intent in [SearchIntent.CONVERSATION_HISTORY, SearchIntent.MEMORY_QUERY, 
                         SearchIntent.CLARIFICATION, SearchIntent.SYSTEM_STATUS, SearchIntent.GENERAL_CONVERSATION]:
                logger.info(f"Handling conversation intent: {intent.name} (confidence: {score:.2f})")
                
                if intent == SearchIntent.CONVERSATION_HISTORY:
                    response_text = await self._handle_conversation_history(session_id, message)
                elif intent == SearchIntent.MEMORY_QUERY:
                    response_text = await self._handle_memory_query(session_id, message, params)
                elif intent == SearchIntent.CLARIFICATION:
                    response_text = await self._handle_clarification(session_id, message)
                elif intent == SearchIntent.SYSTEM_STATUS:
                    response_text = await self._handle_system_status(message)
                else:  # GENERAL_CONVERSATION
                    response_text = await self._handle_general_conversation(message)
                
                metadata = {
                    "intent": intent.name,
                    "confidence": score,
                    "method": hybrid_result.detection_method,
                    "conversation_intent": True,
                    "products": []
                }
                
                processing_time = time.time() - start_time
                metadata["processing_time_seconds"] = round(processing_time, 2)
                
                return ChatResponse(
                    response=response_text,
                    products=[],
                    session_id=session_id,
                    metadata=metadata
                )
            
            # Only search products when there's clear shopping intent OR product continuation
            should_search_products = (
                conversation_response_type == "search" or 
                is_product_continuation or  # NEW: Handle product continuation scenarios
                (intent in [SearchIntent.SPECIFIC_ITEM, SearchIntent.SALE, 
                           SearchIntent.BRAND, SearchIntent.OUTFIT, SearchIntent.BROWSE] 
                 and score > 0.7) or  # Standard threshold for explicit product intents
                (intent == SearchIntent.INSPIRATION and score > 0.8) or  # RAISED threshold to reduce false positives
                # Only trigger on explicit product request phrases - exclude obvious non-shopping contexts
                (any(phrase in message.lower() for phrase in [
                    "i need a", "i need some", "recommend me", "show me some", "find me a", "looking for a",
                    "want to buy", "need to buy", "show me products", "what products", "actual product"
                ]) and not any(non_shopping_pattern in message.lower() for non_shopping_pattern in [
                    # News/Media patterns
                    "in the news", "breaking news", "headlines", "reporter said", "news report",
                    "media says", "press conference", "journalist", "broadcasting",
                    
                    # Question patterns about events/opinions  
                    "did you see", "did you hear", "what happened", "what do you think", "your opinion",
                    "do you believe", "what's your view", "how do you feel about", "thoughts on",
                    
                    # Academic/Professional contexts
                    "study shows", "research found", "according to", "scientist says", "doctor says",
                    "professor", "university", "academic", "clinical trial", "peer review",
                    
                    # Political context (general, not specific people)
                    "election results", "congress voted", "senate", "political party", "campaign", 
                    "government policy", "legislation", "ballot", "polling data", "voter",
                    
                    # Personal life/relationships
                    "my friend said", "my family", "relationship advice", "dating tips", "marriage",
                    "personal life", "life advice", "friendship", "social situation",
                    
                    # General conversation starters
                    "tell me about", "explain", "discuss", "talk about", "curious about",
                    "wondering", "question about", "help me understand"
                ]))
            )
            
            if should_search_products:
                # Product search requested (new search or continuation)
                if is_product_continuation:
                    logger.info(f"Routing to product continuation - Current products: {len(conversation_context.current_products)}")
                    # For continuations, pass current product context and enhanced message with conversation context
                    search_message = enhanced_message if enhanced_message else message
                    response_text, metadata = await self._handle_product_search(
                        search_message, params, user_context, background_tasks, session_id,
                        current_products=conversation_context.current_products
                    )
                else:
                    logger.info(f"Routing to new product search - Intent: {intent.name}, Score: {score:.2f}")
                    # For new searches, use enhanced message if available to provide context for vague queries
                    search_message = enhanced_message if enhanced_message else message
                    response_text, metadata = await self._handle_product_search(
                        search_message, params, user_context, background_tasks, session_id
                    )
                
                # Add LLM intent metadata to product search results
                metadata.update({
                    "llm_intent": intent.name,
                    "llm_confidence": score,
                    "llm_method": hybrid_result.detection_method,
                    "is_continuation": is_product_continuation
                })
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

            # 4. Store conversation in comprehensive unified memory system (background task)
            if background_tasks:
                background_tasks.add_task(
                    self._store_comprehensive_memory,
                    session_id,
                    user_id or "anonymous", 
                    message,
                    response_text,
                    intent.name if hasattr(intent, 'name') else str(intent),
                    params,
                    len(metadata.get("products", [])),
                    metadata
                )
            else:
                # Store immediately for non-HTTP contexts using comprehensive memory
                await self.memory_coordinator.store_conversation(
                    session_id=session_id,
                    user_id=user_id or "anonymous",
                    user_message=message,
                    assistant_response=response_text,
                    intent=intent.name if hasattr(intent, 'name') else str(intent),
                    extracted_params=params,
                    products_found=len(metadata.get("products", [])),
                    metadata=metadata
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
        background_tasks: Optional[BackgroundTasks] = None,
        session_id: Optional[str] = None,
        current_products: Optional[List[str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Orchestrates the battle system to find and recommend products.
        Enhanced with ML intelligence for better recommendations.
        """
        if current_products:
            logger.info(f"Handling product continuation for query: '{message}' with {len(current_products)} current products")
        else:
            logger.info(f"Handling new product search for query: '{message}'")
        
        # Generate ML intelligence for the battle agents
        ml_intelligence = None
        try:
            ml_intelligence = await self._generate_ml_intelligence(
                message, params, user_context, session_id
            )
            logger.info(f"Generated ML intelligence with {len(ml_intelligence)} intelligence packets")
        except Exception as e:
            logger.warning(f"ML intelligence generation failed: {e}, continuing without")
        
        # Pass current products context to battle system for continuation scenarios
        conversation_context = {"current_products": current_products} if current_products else None
        
        battle_results = await self.battle_orchestrator.execute_battle(
            query=message,
            filters=params,
            user_context=user_context,
            ml_intelligence=ml_intelligence,
            conversation_context=conversation_context
        )

        products = battle_results.get("products", [])
        cypher_products = battle_results.get("cypher_products", [])
        vibe_products = battle_results.get("vibe_products", [])
        
        # Generate response that shows both agent results for Ari's review
        response_text = self._generate_collaborative_response(
            products, cypher_products, vibe_products, message, battle_results
        )
        
        # Extract detailed reasoning from judgment
        judgment = battle_results.get("judgment", {})
        detailed_reasoning = judgment.get("detailed_reasoning")
        
        metadata = {
            "intent": "product_search",
            "parameters": params,
            "products": products,
            "cypher_products": cypher_products,  # Include raw CypherBot results
            "vibe_products": vibe_products,      # Include raw VibeBot results
            "battle_winner": judgment.get("winner", "unknown"),
            "detailed_reasoning": detailed_reasoning,
            "cypher_count": len(cypher_products),
            "vibe_count": len(vibe_products)
        }
        
        return response_text, metadata

    async def _generate_ml_intelligence(
        self,
        message: str,
        params: Dict[str, Any], 
        user_context: Dict[str, Any],
        session_id: Optional[str] = None
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
                session_id=session_id,
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

    def _generate_collaborative_response(
        self, 
        final_products: List[Dict], 
        cypher_products: List[Dict], 
        vibe_products: List[Dict], 
        query: str, 
        battle_results: Dict[str, Any]
    ) -> str:
        """
        Creates a collaborative response showing both agent findings for Ari's review.
        Presents what CypherBot and VibeBot found, then Ari's final decisions.
        """
        if not final_products and not cypher_products and not vibe_products:
            return "I couldn't find any items that matched your request. Perhaps you could describe it a bit differently for me?"

        # Start with Ari's introduction
        response = f"I found several options for '{query}'. Here's what my team discovered:\n\n"
        
        # Show CypherBot results
        if cypher_products:
            response += f"🔍 **CypherBot found {len(cypher_products)} items from graph search:**\n"
            for product in cypher_products[:3]:
                title = product.get("title", "an item")
                price = product.get("price", 0)
                response += f"   • {title} - ${price:.2f}\n"
            if len(cypher_products) > 3:
                response += f"   • ... and {len(cypher_products) - 3} more\n"
        else:
            response += "🔍 **CypherBot:** No matches found in graph search\n"
        
        response += "\n"
        
        # Show VibeBot results  
        if vibe_products:
            response += f"✨ **VibeBot found {len(vibe_products)} items from semantic search:**\n"
            for product in vibe_products[:3]:
                title = product.get("title", "an item")
                price = product.get("price", 0)
                response += f"   • {title} - ${price:.2f}\n"
            if len(vibe_products) > 3:
                response += f"   • ... and {len(vibe_products) - 3} more\n"
        else:
            response += "✨ **VibeBot:** No matches found in semantic search\n"
        
        response += "\n"
        
        # Show Ari's final decisions
        if final_products:
            winner = battle_results.get("winner", "unknown")
            response += f"👗 **My Final Recommendations ({len(final_products)} items):**\n"
            response += f"   *Based on {winner}'s expertise and overall quality*\n\n"
            
            for product in final_products[:5]:
                title = product.get("title", "an item")
                price = product.get("price", 0)
                response += f"   ⭐ {title} - ${price:.2f}\n"
                
            if len(final_products) > 5:
                response += f"   ... and {len(final_products) - 5} more in your full results\n"
        else:
            response += "👗 **My Assessment:** None of these quite meet our quality standards.\n"
            response += "Let me know if you'd like me to search with different criteria!"
        
        return response

    async def _store_comprehensive_memory(
        self,
        session_id: str,
        user_id: str,
        message: str,
        response: str,
        intent: str,
        extracted_params: Dict[str, Any],
        products_found: int,
        metadata: Dict[str, Any]
    ):
        """
        Background task to store conversation across all memory systems.
        Uses the unified memory coordinator for comprehensive storage.
        """
        try:
            success = await self.memory_coordinator.store_conversation(
                session_id=session_id,
                user_id=user_id,
                user_message=message,
                assistant_response=response,
                intent=intent,
                extracted_params=extracted_params,
                products_found=products_found,
                metadata=metadata
            )
            
            if success:
                logger.info(f"Stored comprehensive memory for session {session_id}")
            else:
                logger.warning(f"Partial failure storing memory for session {session_id}")
                
        except Exception as e:
            logger.error(f"Failed to store comprehensive memory for {session_id}: {e}")
    
    # CONVERSATION INTENT HANDLERS
    
    async def _handle_conversation_history(self, session_id: str, message: str) -> str:
        """Handle conversation history queries using CAMEL memory systems"""
        try:
            # Get conversation history from session memory
            context = await self.session_memory.get_session_context(session_id, context_turns=10)
            
            if not context:
                return "We just started our conversation! I don't have any previous conversation history to share."
            
            # Extract relevant parts based on the question
            if "beginning" in message.lower() or "first" in message.lower():
                # Get the first few exchanges
                first_context = context[:200] if len(context) > 200 else context
                return f"At the beginning of our conversation, you asked: {first_context}"
            elif "earlier" in message.lower() or "before" in message.lower():
                return f"Earlier in our conversation: {context[:300]}"
            else:
                return f"Here's what we've been discussing: {context[:400]}"
                
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return "I'm having trouble accessing our conversation history right now. Could you refresh my memory?"
    
    async def _handle_memory_query(self, session_id: str, message: str, params: dict) -> str:
        """Handle memory queries about stored preferences using CAMEL memory"""
        try:
            # Get user preferences from enhanced session memory
            preferences = await self.session_memory.get_user_preferences(session_id)
            
            if not preferences:
                return "I don't have any stored preferences for you yet. As we continue talking, I'll learn about your style!"
            
            # Format preferences in a friendly way
            pref_text = []
            for category, items in preferences.items():
                if items and isinstance(items, list) and len(items) > 0:
                    pref_text.append(f"- {category.title()}: {', '.join(items[:3])}")
            
            if pref_text:
                return f"Here's what I remember about your preferences:\n" + "\n".join(pref_text)
            else:
                return "I have some information stored but it's still building up. Keep sharing your preferences!"
                
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            return "I'm having trouble accessing my memory right now. Could you remind me what you're looking for?"
    
    async def _handle_clarification(self, session_id: str, message: str) -> str:
        """Handle clarification requests"""
        clarifications = {
            "agent collaboration": "My CypherBot (graph search) and VibeBot (vector search) work together to find the best products for you. Ari Stylist evaluates and combines their results!",
            "how this works": "I use multiple AI agents that search our product database in different ways, then collaborate to give you the best recommendations.",
            "cypher": "CypherBot is my graph database specialist - he's great at finding products based on specific criteria and relationships.",
            "vibe": "VibeBot is my aesthetic expert - he finds products based on style similarity and visual vibes.",
            "ari stylist": "Ari Stylist evaluates the results from both agents and curates the most relevant recommendations for you."
        }
        
        message_lower = message.lower()
        for keyword, explanation in clarifications.items():
            if keyword in message_lower:
                return explanation
        
        return "I'd be happy to clarify! Could you be more specific about what you'd like me to explain?"
    
    async def _handle_system_status(self, message: str) -> str:
        """Handle system status and capability questions"""
        if "agent" in message.lower():
            return "I have three main agents: CypherBot (graph search), VibeBot (vector search), and Ari Stylist (result curation). They work together to find you great fashion pieces!"
        elif "memory" in message.lower():
            return "I use CAMEL-AI's advanced memory system with conversation history, user preferences, and semantic long-term memory to remember our interactions."
        elif "work" in message.lower() or "process" in message.lower():
            return "I analyze your request, determine intent, then my agents collaborate to find the best products. Ari Stylist curates the results based on relevance and quality!"
        else:
            return "I'm an AI fashion stylist powered by multiple specialized agents and advanced memory systems. I can help you find products, remember your preferences, and provide personalized recommendations!"
    
    async def _handle_general_conversation(self, message: str) -> str:
        """Handle general conversation that's not fashion-related"""
        return "I enjoy chatting! While I'm primarily here to help with fashion and style, I'm happy to have a friendly conversation. Is there anything fashion-related I can help you with today?"