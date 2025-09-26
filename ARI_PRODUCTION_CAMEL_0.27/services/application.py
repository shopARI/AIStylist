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

# CAMEL-AI imports for LLM styling advice
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType

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
        Refactored into smaller, focused methods for better maintainability.
        """
        start_time = time.time()

        try:
            # Step 1: Ensure session exists in Redis
            await self._ensure_session_exists(session_id, user_id)

            # Step 2: Get enhanced context and extract preferences
            enhanced_context = await self._get_enhanced_context(session_id, user_id, message)
            stored_preferences = self._extract_stored_preferences(enhanced_context)
            context_parts = self._build_context_parts(enhanced_context, stored_preferences, session_id, user_id)
            enhanced_message = self._build_enhanced_message(message, context_parts)

            # Step 3: Detect intent and extract parameters
            intent, score, params, method = await self._detect_intent_with_preferences(message, stored_preferences)

            # Step 4: Handle conversation intents first (they take priority)
            conversation_response = await self._handle_conversation_intents(
                intent, score, params, session_id, message, method, start_time
            )
            if conversation_response:
                return conversation_response

            # Step 5: Get user context for product search
            user_context = await self._get_user_context(user_id)

            # Step 6: Route based on intent and conversation flow
            conversation_response_type, conversation_metadata = await self.conversation_handler.handle_message(
                session_id, message, user_id
            )

            # Check if this is product continuation vs new search
            conversation_context = self.conversation_handler.get_or_create_session(session_id, user_id)
            has_current_products = bool(conversation_context.current_products)
            is_product_continuation = has_current_products and any(continuation_phrase in message.lower() for continuation_phrase in [
                "this", "that", "these", "those", "it", "them", "more about", "tell me about",
                "what about", "how about", "other colors", "different sizes", "similar to",
                "like this", "more like", "details on", "info on", "about this"
            ])

            # Determine if should search for products
            should_search_products = self._should_search_products(
                intent, score, conversation_response_type, is_product_continuation, message
            )

            # Step 7: Handle product search or general conversation
            if should_search_products:
                # Product search requested (new search or continuation)
                if is_product_continuation:
                    logger.info(f"Routing to product continuation - Current products: {len(conversation_context.current_products)}")
                    # For continuations, only use enhanced context if the query is vague/unclear
                    search_message = self._decide_context_inclusion(message, enhanced_message, is_continuation=True)
                    response_text, metadata = await self._handle_product_search(
                        search_message, params, user_context, background_tasks, session_id,
                        current_products=conversation_context.current_products,
                        original_message=message
                    )
                else:
                    logger.info(f"Routing to new product search - Intent: {intent.name}, Score: {score:.2f}")
                    # For new searches, only use enhanced context if query is vague and needs clarification
                    search_message = self._decide_context_inclusion(message, enhanced_message, is_continuation=False)
                    response_text, metadata = await self._handle_product_search(
                        search_message, params, user_context, background_tasks, session_id,
                        original_message=message
                    )

                # Add LLM intent metadata to product search results
                metadata.update({
                    "llm_intent": intent.name,
                    "llm_confidence": score,
                    "llm_method": method,
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
                    "llm_method": method
                }

            # Step 8: Create response and finalize
            chat_response = ChatResponse(
                response=response_text,
                products=metadata.get("products", []),
                session_id=session_id,
                metadata=metadata
            )

            # Step 9: Store conversation and add timing metadata
            await self._finalize_response(
                chat_response, session_id, user_id, message, intent, params, metadata, background_tasks, start_time
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
        search_message: str,
        params: Dict[str, Any],
        user_context: Dict[str, Any],
        background_tasks: Optional[BackgroundTasks] = None,
        session_id: Optional[str] = None,
        current_products: Optional[List[str]] = None,
        original_message: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Orchestrates the battle system to find and recommend products.
        Enhanced with ML intelligence for better recommendations.
        """
        if current_products:
            logger.info(f"Handling product continuation for query: '{search_message}' with {len(current_products)} current products")
        else:
            logger.info(f"Handling new product search for query: '{search_message}'")
        
        # Generate ML intelligence for the battle agents
        ml_intelligence = None
        try:
            ml_intelligence = await self._generate_ml_intelligence(
                search_message, params, user_context, session_id
            )
            logger.info(f"Generated ML intelligence with {len(ml_intelligence)} intelligence packets")
        except Exception as e:
            logger.warning(f"ML intelligence generation failed: {e}, continuing without")
        
        # Pass current products context to battle system for continuation scenarios
        conversation_context = {"current_products": current_products} if current_products else None
        
        battle_results = await self.battle_orchestrator.execute_battle(
            query=search_message,
            filters=params,
            user_context=user_context,
            ml_intelligence=ml_intelligence,
            conversation_context=conversation_context
        )

        products = battle_results.get("products", [])
        cypher_products = battle_results.get("cypher_products", [])
        vibe_products = battle_results.get("vibe_products", [])
        vision_products = battle_results.get("vision_products", [])

        # Generate response that shows all agent results for Ari's review
        # Use the original message for display, not the processed search_message
        display_message = original_message or search_message
        response_text = await self._generate_collaborative_response(
            products, cypher_products, vibe_products, display_message, battle_results, vision_products
        )
        
        # Extract detailed reasoning from judgment
        judgment = battle_results.get("judgment", {})
        detailed_reasoning = judgment.get("detailed_reasoning")
        
        metadata = {
            "intent": "product_search",
            "parameters": params,
            "products": products,
            "cypher_products": cypher_products,
            "vibe_products": vibe_products,
            "evaluation_method": judgment.get("evaluation_method", "unified_collaborative"),
            "detailed_reasoning": detailed_reasoning,
            "cypher_count": len(cypher_products),
            "vibe_count": len(vibe_products)
        }

        # Add VisionBot results if available
        if vision_products:
            metadata["vision_products"] = vision_products
            metadata["vision_count"] = len(vision_products)
        
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
            user_details = await self.user_kg_service.get_user_details(user_id)
            return user_details or {}
        except Exception as e:
            logger.warning(f"Could not retrieve context for user {user_id}: {e}")
            # Return empty context to avoid downstream errors
            return {
                "id": user_id,
                "preferences": {},
                "segments": [],
                "style_profile": "",
                "total_interactions": 0,
                "total_purchases": 0
            }

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

    def _decide_context_inclusion(self, original_message: str, enhanced_message: str, is_continuation: bool) -> str:
        """
        Intelligently decide whether to include conversation history based on intent inference.
        
        Rules:
        - Specific, clear queries (like "black shirt" or "interview outfit") → Use original message only
        - Vague queries (like "something similar", "that style") → Include context
        - Continuation queries referring to previous items → Include context
        - Professional/occasion queries with clear context → Use original message only
        """
        
        # If no enhanced context available, use original
        if not enhanced_message:
            return original_message
        
        # Check if query is specific and self-contained
        specific_indicators = [
            # Colors + items
            r'\b(black|white|red|blue|green|navy|gray|grey|brown|pink)\s+(shirt|dress|pants|jacket|shoes)',
            # Professional contexts
            r'\b(interview|job|work|professional|academic|business|formal)\b',
            # Specific items
            r'\b(blazer|suit|shirt|dress|pants|shoes|jacket|coat|blouse)\b',
            # Occasions with clear context
            r'\b(wedding|party|date|graduation|conference)\b',
            # Complete outfit requests
            r'what should i wear (for|to)',
        ]
        
        import re
        message_lower = original_message.lower()
        
        # If query is specific and self-contained, don't pollute with history
        for pattern in specific_indicators:
            if re.search(pattern, message_lower):
                logger.info(f"Query is specific and self-contained, using original message only")
                return original_message
        
        # Check for vague continuation indicators that need context
        vague_indicators = [
            r'\b(similar|like that|same style|matching|goes with)\b',
            r'\b(it|this|that|those|these)\b',
            r'\b(more|another|different)\b',
            r'\b(change|swap|replace)\b'
        ]
        
        # If query is vague and likely refers to previous context, include history
        for pattern in vague_indicators:
            if re.search(pattern, message_lower):
                logger.info(f"Query is vague and needs context, using enhanced message")
                return enhanced_message
        
        # Default: if continuation, include context; if new search, use original
        if is_continuation:
            logger.info(f"Continuation query, including context")
            return enhanced_message
        else:
            logger.info(f"New specific query, using original message only")
            return original_message

    async def _generate_collaborative_response(
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
        Enhanced with LLM-generated professional styling advice for interview/work contexts.
        """
        if not final_products and not cypher_products and not vibe_products:
            return "I couldn't find any items that matched your request. Perhaps you could describe it a bit differently for me?"

        # Add professional styling context if applicable
        styling_advice = await self._generate_styling_context(query, final_products)

        # Start with Ari's introduction
        response = f"I found several options for '{query}'. Here's what my team discovered:\n\n"

        # Add styling advice if relevant
        if styling_advice:
            response += styling_advice + "\n\n"
        
        # Show agent collaboration details - only if we have specific agent results
        if cypher_products or vibe_products:
            # Show CypherBot results
            if cypher_products:
                response += f"**CypherBot found {len(cypher_products)} items from graph search:**\n"
                for product in cypher_products[:3]:
                    title = product.get("title", "an item")
                    price = product.get("price", 0)
                    response += f"   • {title} - ${price:.2f}\n"
                if len(cypher_products) > 3:
                    response += f"   • ... and {len(cypher_products) - 3} more\n"
            else:
                response += "**CypherBot:** No matches found in graph search\n"

            response += "\n"

            # Show VibeBot results
            if vibe_products:
                response += f"**VibeBot found {len(vibe_products)} items from semantic search:**\n"
                for product in vibe_products[:3]:
                    title = product.get("title", "an item")
                    price = product.get("price", 0)
                    response += f"   • {title} - ${price:.2f}\n"
                if len(vibe_products) > 3:
                    response += f"   • ... and {len(vibe_products) - 3} more\n"
            else:
                response += "**VibeBot:** No matches found in semantic search\n"

            response += "\n"
        
        # Show Ari's final decisions
        if final_products:
            evaluation_method = battle_results.get("evaluation_method", "collaborative analysis")
            response += f"**My Final Recommendations ({len(final_products)} items):**\n"
            response += f"   *Based on {evaluation_method} and overall quality*\n\n"
            
            for product in final_products[:5]:
                title = product.get("title", "an item")
                price = product.get("price", 0)
                response += f"   • {title} - ${price:.2f}\n"
                
            if len(final_products) > 5:
                response += f"   ... and {len(final_products) - 5} more in your full results\n"
        else:
            response += "**My Assessment:** None of these quite meet our quality standards.\n"
            response += "Let me know if you'd like me to search with different criteria!"

        return response

    async def _generate_styling_context(self, query: str, final_products: List[Dict]) -> str:
        """
        Generate intelligent styling advice using LLM fashion expertise.
        Provides dynamic, personalized fashion advice for specific contexts.
        """
        query_lower = query.lower()

        # Check if styling advice is needed for professional/formal contexts
        # Use more precise matching to avoid false positives like "workout" matching "work"
        professional_patterns = [
            'interview', 'job', 'professional', ' work ', 'office', 'meeting',
            'professor', 'academic', 'university', 'college', 'teaching',
            'wedding', 'gala', 'formal', 'black tie', 'cocktail',
            'business casual', 'workplace', 'conference', 'presentation'
        ]

        # Check if any professional patterns match
        query_with_spaces = f" {query_lower} "

        has_professional_trigger = any(pattern in query_with_spaces for pattern in professional_patterns)

        # Also check for "formal" anywhere in the query since it's always professional
        has_formal = 'formal' in query_lower

        # Also check for outfit combination requests
        outfit_request = self._detect_outfit_combination_request(query)

        if has_professional_trigger or has_formal or outfit_request:
            try:
                return await self._generate_llm_styling_advice(query, final_products)
            except Exception as e:
                logger.error(f"Failed to generate LLM styling advice: {e}")
                # Fallback to basic professional advice
                return self._basic_professional_fallback()

        return ""  # No specific styling advice needed

    def _detect_outfit_combination_request(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Detect if the user is requesting outfit combinations with multiple pieces/colors.

        Returns:
            Dict with outfit request details or None if not a combination request
        """
        query_lower = query.lower()

        # Keywords that indicate combination requests
        combination_keywords = ['matching', 'match', 'coordinate', 'go with', 'pair with', 'combine']
        multiple_keywords = ['different colors', 'color variations', 'multiple colors', 'various colors']
        item_keywords = ['shirt', 'pants', 'blouse', 'skirt', 'jacket', 'dress', 'top', 'bottom']

        # Check for combination request patterns
        has_combination = any(keyword in query_lower for keyword in combination_keywords)
        has_multiple = any(keyword in query_lower for keyword in multiple_keywords)

        # Extract number requests (e.g., "4 different colors", "3 options")
        import re
        number_pattern = r'(\d+)\s*(?:different\s*)?(?:colors?|options?|variations?|pieces?)'
        number_match = re.search(number_pattern, query_lower)
        color_count = int(number_match.group(1)) if number_match else 4  # Default to 4

        # Detect base item and matching items
        base_item = None
        matching_items = []

        # Simple pattern matching for common requests
        if 'pants' in query_lower and ('shirt' in query_lower or 'top' in query_lower):
            base_item = 'pants'
            matching_items = ['shirts', 'tops']
        elif 'shirt' in query_lower and ('pants' in query_lower or 'skirt' in query_lower):
            base_item = 'shirt'
            matching_items = ['pants', 'skirts']
        elif 'dress' in query_lower and ('jacket' in query_lower or 'cardigan' in query_lower):
            base_item = 'dress'
            matching_items = ['jackets', 'cardigans']
        elif 'skirt' in query_lower and ('blouse' in query_lower or 'top' in query_lower):
            base_item = 'skirt'
            matching_items = ['blouses', 'tops']

        # If we detected combination intent or multiple colors/options
        if (has_combination or has_multiple or number_match) and (base_item or any(item in query_lower for item in item_keywords)):
            return {
                'base_item': base_item or 'foundation piece',
                'matching_items': matching_items if matching_items else ['coordinating pieces'],
                'color_count': min(color_count, 6),  # Cap at 6 for practicality
                'has_combination_intent': has_combination,
                'has_multiple_intent': has_multiple
            }

        return None

    async def _generate_llm_styling_advice(self, query: str, final_products: List[Dict]) -> str:
        """
        Generate dynamic styling advice using LLM expertise.
        Provides personalized fashion consultation based on context and products.
        """
        try:
            # Create LLM styling consultant
            model = ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI,
                model_type=ModelType.GPT_4O_MINI,
                model_config_dict={
                    "temperature": 0.7,
                    "max_tokens": 2000  # Increased for detailed explanations
                }
            )

            system_message = BaseMessage.make_assistant_message(
                role_name="System",
                content="""You are ARI, an elite fashion stylist and consultant with decades of experience in professional styling. You are known for your detailed explanations and ability to defend every styling choice with expert reasoning.

Your expertise includes:
- Professional interview styling for different industries
- Understanding dress codes and industry expectations
- Color theory and fabric knowledge
- Fit and proportion guidance
- Appropriate accessory selection
- Building versatile professional wardrobes
- Fashion psychology and confidence building
- Understanding body types and flattering cuts

CRITICAL: You must defend and explain WHY you recommend each piece. For every suggestion, provide:
1. The REASONING behind the choice
2. How it serves the specific context/occasion
3. Why this particular combination works
4. What psychological impact it creates
5. How it addresses practical considerations

Provide styling advice that is:
- Specific to the context and occasion
- Professional and authoritative with clear justifications
- Practical and actionable with detailed explanations
- Industry-appropriate with reasoning for each choice
- Confidence-building through expert knowledge

Format your response with clear sections. Always start with "**ARI'S EXPERT STYLING CONSULTATION:**" and defend every recommendation with professional reasoning."""
            )

            agent = ChatAgent(
                system_message=system_message,
                model=model
            )

            # Build context about the products found
            product_context = ""
            if final_products:
                product_context = f"\n\nProducts found in search: {len(final_products)} items including:"
                for i, product in enumerate(final_products[:3]):
                    title = product.get("title", "Item")
                    price = product.get("price", 0)
                    product_context += f"\n- {title} (${price:.2f})"
                if len(final_products) > 3:
                    product_context += f"\n- ... and {len(final_products) - 3} more items"
            else:
                product_context = "\n\nNote: No specific products were found in the current search, so provide general styling guidance for this context."

            # Create user query with context
            outfit_request = self._detect_outfit_combination_request(query)

            # ENHANCED WITH VISUAL INTELLIGENCE COORDINATION
            visual_coordination_context = ""
            if outfit_request:
                try:
                    # Use Visual Intelligence for outfit coordination analysis
                    visual_intel = await self.intelligence_coordinator.get_visual_intelligence()
                    if visual_intel and len(final_products) > 1:
                        print("VISUAL INTELLIGENCE: Analyzing outfit coordination for combination request...")

                        # Separate products into base items and coordinating items
                        base_products = []
                        coordinating_products = []

                        for product in final_products:
                            title_lower = product.get('title', '').lower()
                            categories = product.get('categories', [])
                            if isinstance(categories, str):
                                categories = [categories]
                            category_text = ' '.join(categories).lower()

                            # Classify products based on outfit request
                            is_base_item = False
                            is_coordinating_item = False

                            if outfit_request['base_item']:
                                base_item = outfit_request['base_item'].lower()
                                if base_item in title_lower or base_item in category_text:
                                    is_base_item = True

                            for matching_item in outfit_request['matching_items']:
                                matching_item_clean = matching_item.lower().rstrip('s')  # Remove plural
                                if matching_item_clean in title_lower or matching_item_clean in category_text:
                                    is_coordinating_item = True
                                    break

                            # Default assignment if classification unclear
                            if not is_base_item and not is_coordinating_item:
                                if len(base_products) <= len(coordinating_products):
                                    is_base_item = True
                                else:
                                    is_coordinating_item = True

                            if is_base_item:
                                base_products.append(product)
                            elif is_coordinating_item:
                                coordinating_products.append(product)

                        # Perform visual coordination analysis
                        if base_products and coordinating_products:
                            coordination_analysis = await visual_intel.analyze_outfit_coordination(
                                base_products=base_products,
                                coordinating_products=coordinating_products,
                                color_variations=outfit_request['color_count']
                            )

                            if coordination_analysis:
                                print(f"   Visual coordination analysis complete!")

                                # Extract insights for LLM prompt
                                color_harmony = coordination_analysis.get('color_harmony', {})
                                outfit_combinations = coordination_analysis.get('outfit_combinations', [])
                                color_variations = coordination_analysis.get('color_variations', [])
                                style_coherence = coordination_analysis.get('style_coherence', {})

                                visual_coordination_context = f"""

VISUAL INTELLIGENCE COORDINATION ANALYSIS:
Color Harmony Score: {color_harmony.get('overall_score', 0):.1%}
Best Color Combinations: {', '.join(color_harmony.get('base_colors', [])) + ' with ' + ', '.join(color_harmony.get('coordinating_colors', []))}
Style Coherence Score: {style_coherence.get('coherence_score', 0):.1%}
Dominant Styles: {', '.join(style_coherence.get('dominant_styles', [])[:3])}

TOP VISUAL COMBINATIONS IDENTIFIED:
"""
                                for i, combo in enumerate(outfit_combinations[:3], 1):
                                    base_item = combo.get('base_item', {})
                                    coord_item = combo.get('coordinating_item', {})
                                    visual_coordination_context += f"""
Combination {i}:
- Base: {base_item.get('colors', [])} | Coordinating: {coord_item.get('colors', [])}
- Compatibility: {combo.get('compatibility_score', 0):.1%}
- Color Harmony: {combo.get('color_harmony_score', 0):.1%}
- Style Coherence: {combo.get('style_coherence', 0):.1%}
"""

                                if color_variations:
                                    visual_coordination_context += f"""

RECOMMENDED COLOR PALETTE VARIATIONS:
"""
                                    for var in color_variations[:outfit_request['color_count']]:
                                        palette = var.get('palette_name', 'Custom')
                                        base_colors = ', '.join(var.get('base_item_colors', []))
                                        coord_colors = ', '.join(var.get('coordinating_item_colors', []))
                                        harmony_score = var.get('color_harmony_score', 0)
                                        visual_coordination_context += f"""
{palette.title()} Palette: {base_colors} + {coord_colors} (Harmony: {harmony_score:.1%})"""

                except Exception as e:
                    logger.error(f"Error in visual coordination analysis: {e}")
                    print(f"   Visual coordination analysis error: {e}")

            if outfit_request:
                user_prompt = f"""Please provide expert outfit coordination for: "{query}"

Context: The user wants complete outfit combinations with multiple options.{product_context}{visual_coordination_context}

OUTFIT COORDINATION REQUEST DETECTED:
Base Item: {outfit_request['base_item']}
Matching Items Needed: {outfit_request['matching_items']}
Color Variations Requested: {outfit_request['color_count']}

Please provide:
1. **Complete Outfit Sets** - Multiple coordinated combinations (use Visual Intelligence insights above if available)
2. **Color Coordination Strategy** - {outfit_request['color_count']} different color schemes that work together
3. **Styling Logic for Each Combination** - Why each color pairing works (reference visual analysis if provided)
4. **Mix & Match Guidance** - How pieces work together across combinations
5. **Versatility Analysis** - How to maximize wardrobe potential
6. **Occasion Adaptability** - How each combination suits different contexts

Format as: "OUTFIT COMBINATION 1: [Base] + [Top] + [Reasoning]" for each set.
Provide {outfit_request['color_count']} distinct, well-coordinated outfit combinations."""
            else:
                user_prompt = f"""Please provide expert styling advice for: "{query}"

Context: The user is seeking fashion guidance for this specific situation.{product_context}

IMPORTANT: For each recommendation, you must explain WHY you're suggesting it. Defend every choice with professional reasoning.

Please provide:
1. **Complete Outfit Recommendations** - Each piece with detailed justification
2. **Strategic Reasoning** - Why each piece serves the specific context
3. **Color Psychology** - Why specific colors work for this situation
4. **Fit & Silhouette Logic** - How each piece flatters and projects confidence
5. **Practical Considerations** - How recommendations address real-world needs
6. **What to Avoid & Why** - Specific pieces that would undermine the look
7. **Professional Success Strategy** - How this styling approach achieves goals

Be specific, authoritative, and defend every single choice with expert fashion knowledge. Think like a top-tier personal stylist explaining your decisions to a discerning client."""

            user_message = BaseMessage.make_user_message(
                role_name="User",
                content=user_prompt
            )

            # Get LLM response
            response = await agent.agenerate(user_message)

            return response.content if response and response.content else self._basic_professional_fallback()

        except Exception as e:
            logger.error(f"Error generating LLM styling advice: {e}")
            return self._basic_professional_fallback()

    def _basic_professional_fallback(self) -> str:
        """Fallback professional advice when LLM is unavailable."""
        return """**ARI'S EXPERT STYLING CONSULTATION:**

**The Universal Professional Formula with Expert Reasoning:**

• **Well-fitted blazer or jacket**
  *Why: Creates instant authority and professional presence. The structured shoulders communicate competence while providing a polished silhouette that works across all body types.*

• **Quality blouse or professional shirt**
  *Why: Serves as the foundation that bridges the blazer and bottom. Quality fabric drapes better, photographs well in professional settings, and maintains its appearance throughout long days.*

• **Tailored pants or appropriate skirt**
  *Why: Proper fit in the lower half projects attention to detail. Well-tailored pieces create clean lines that command respect while ensuring comfort for movement and sitting.*

• **Professional closed-toe shoes**
  *Why: Closed-toe maintains industry appropriateness while providing stability and confidence in your stride. The right heel height (1-3 inches) elongates the silhouette without compromising comfort.*

• **Structured bag and minimal accessories**
  *Why: A structured bag demonstrates organization and preparedness. Minimal accessories prevent distraction from your qualifications while adding subtle sophistication.*

**Strategic Color Psychology:**
- **Navy, black, charcoal:** Command authority and respect while being universally flattering
- **Cream, white:** Projects approachability and cleanliness, perfect for contrast and light reflection

**Professional Success Strategy:**
This formula works because it creates a cohesive, confident appearance that allows your expertise to be the focus while ensuring you're taken seriously in any professional context."""

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
        """Handle general conversation using LLM for natural, dynamic responses"""
        try:
            # Check for time/date queries first
            from datetime import datetime
            time_keywords = ['time', 'date', 'day', 'today', 'now', 'clock', 'current']
            message_lower = message.lower()

            if any(keyword in message_lower for keyword in time_keywords):
                current_time = datetime.now()
                time_str = current_time.strftime("%I:%M %p")
                date_str = current_time.strftime("%A, %B %d, %Y")

                if 'time' in message_lower:
                    return f"It's currently {time_str} on {date_str}. Perfect timing to think about what to wear for the rest of the day!"
                elif 'date' in message_lower or 'day' in message_lower or 'today' in message_lower:
                    return f"Today is {date_str}. What kind of day are you having? Are you dressing for work, leisure, or something special?"
                else:
                    return f"Right now it's {time_str} on {date_str}. Time flies when you're thinking about style!"

            # Use LLM to generate natural conversation response
            conversation_prompt = f"""You are ARI, a friendly AI fashion stylist who loves to chat about anything.
The user asked: "{message}"

Generate a natural, helpful response that:
1. Actually addresses their question/topic in a knowledgeable way
2. Shows genuine interest and engagement
3. Smoothly connects back to fashion/style if appropriate (but don't force it)
4. Keeps the conversation open and friendly

Be conversational, informative, and authentic. You're knowledgeable about many topics but fashion is your specialty."""

            # Create a quick LLM call for natural conversation
            from services.nlp.llm_intent_detector import create_agent
            from camel.types import ModelType

            agent = create_agent(
                system_message=conversation_prompt,
                model_type=ModelType.GPT_4O_MINI
            )

            response = agent.step(message)

            if hasattr(response, 'msgs') and response.msgs and len(response.msgs) > 0:
                return response.msgs[-1].content
            else:
                return self._fallback_conversation_response(message)

        except Exception as e:
            logger.warning(f"LLM conversation generation failed: {e}")
            return self._fallback_conversation_response(message)

    def _fallback_conversation_response(self, message: str) -> str:
        """Simple fallback for when LLM conversation fails"""
        message_lower = message.lower()

        # Just a few basic patterns as fallback
        if any(word in message_lower for word in ["time", "day", "date"]):
            import datetime
            today = datetime.date.today()
            return f"Today is {today.strftime('%A, %B %d, %Y')}! Is there anything special you're planning to wear today?"

        if any(word in message_lower for word in ["hello", "hi", "hey"]):
            return "Hello! I'm here to chat about anything on your mind. What would you like to talk about?"

        # Default friendly response
        return "That's interesting! I enjoy chatting about all kinds of topics. While fashion is my specialty, I'm always happy to have a good conversation. What else would you like to explore?"

    # ==================== REFACTORED HELPER METHODS ====================
    # These methods extract functionality from the overly complex process_message method

    async def _ensure_session_exists(self, session_id: str, user_id: Optional[str]) -> None:
        """
        Ensure session exists in Redis.
        Extracted from process_message for better maintainability.
        """
        session_key = f"session:{session_id}"
        session_data = await self.redis_client.get_json(session_key)
        if session_data is None:
            session_data = {"history": [], "created_at": time.time(), "user_id": user_id}
            await self.redis_client.set_json(session_key, session_data, ttl=86400)  # 24 hour TTL

    async def _get_enhanced_context(
        self,
        session_id: str,
        user_id: Optional[str],
        message: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive enhanced context from unified memory coordinator.
        Extracted from process_message for better maintainability.
        """
        return await self.memory_coordinator.get_enhanced_context(
            session_id=session_id,
            user_id=user_id,
            current_query=message,
            intent=None,  # Will be determined after intent detection
            include_similar_conversations=True,
            include_user_preferences=True,
            max_similar_contexts=3
        )

    def _extract_stored_preferences(self, enhanced_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract stored preferences from enhanced context.
        Extracted from process_message for better maintainability.
        """
        user_context_data = enhanced_context.get('user_context', {})
        stored_preferences = {}

        if user_context_data and user_context_data.get('active_preferences'):
            for category, prefs in user_context_data['active_preferences'].items():
                # Convert preference format for compatibility
                stored_preferences[category] = [p['value'] for p in prefs[:3] if p['confidence'] > 0.4]

        return stored_preferences

    def _build_context_parts(
        self,
        enhanced_context: Dict[str, Any],
        stored_preferences: Dict[str, Any],
        session_id: str,
        user_id: Optional[str]
    ) -> List[str]:
        """
        Build context parts for enhanced message.
        Extracted from process_message for better maintainability.
        """
        session_context = enhanced_context.get('session_context', '')
        similar_conversations = enhanced_context.get('similar_conversations', [])

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

        return context_parts

    def _build_enhanced_message(self, message: str, context_parts: List[str]) -> str:
        """
        Build enhanced message with memory context.
        Extracted from process_message for better maintainability.
        """
        enhanced_message = message
        if context_parts:
            memory_context = " | ".join(context_parts)
            enhanced_message = f"{memory_context} | Current request: {message}"
            logger.info(f"Enhanced message with comprehensive memory context: {len(memory_context)} chars")
        return enhanced_message

    async def _detect_intent_with_preferences(
        self,
        message: str,
        stored_preferences: Dict[str, Any]
    ) -> Tuple[Any, float, Dict[str, Any], str]:
        """
        Detect intent and merge with stored preferences.
        Extracted from process_message for better maintainability.
        """
        # Detect intent and extract parameters using LLM/HYBRID - use RAW message for intent detection
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
                    # Import colors from configuration
                    from config.fashion_vocabulary import COLORS
                    if key == "colors" and any(color in message.lower() for color in COLORS):
                        continue  # Skip merging stored color if current message has explicit color
                    params[key] = value
            logger.info(f"Merged stored preferences from session memory: {stored_preferences}")

        logger.info(f"LLM Intent: {intent.name} (Score: {score:.2f}, Method: {hybrid_result.detection_method}), Params: {params}")

        return intent, score, params, hybrid_result.detection_method

    async def _handle_conversation_intents(
        self,
        intent,
        score: float,
        params: Dict[str, Any],
        session_id: str,
        message: str,
        method: str,
        start_time: float
    ) -> Optional[ChatResponse]:
        """
        Handle conversation/memory intents.
        Extracted from process_message for better maintainability.
        Returns ChatResponse if handled, None if not a conversation intent.
        """
        from models.types import SearchIntent

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
                "method": method,
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

        return None  # Not a conversation intent

    def _should_search_products(
        self,
        intent,
        score: float,
        conversation_response_type: str,
        is_product_continuation: bool,
        message: str
    ) -> bool:
        """
        Determine if should search for products.
        Extracted from process_message for better maintainability.
        """
        from models.types import SearchIntent

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

        return should_search_products

    async def _finalize_response(
        self,
        chat_response: ChatResponse,
        session_id: str,
        user_id: Optional[str],
        message: str,
        intent,
        params: Dict[str, Any],
        metadata: Dict[str, Any],
        background_tasks: Optional[BackgroundTasks],
        start_time: float
    ) -> None:
        """
        Finalize response with timing and storage.
        Extracted from process_message for better maintainability.
        """
        processing_time = time.time() - start_time
        metadata["processing_time_seconds"] = round(processing_time, 2)
        chat_response.metadata.update(metadata)

        # Store conversation in comprehensive unified memory system (background task)
        if background_tasks:
            background_tasks.add_task(
                self._store_comprehensive_memory,
                session_id,
                user_id or "anonymous",
                message,
                chat_response.response,
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
                assistant_response=chat_response.response,
                intent=intent.name if hasattr(intent, 'name') else str(intent),
                extracted_params=params,
                products_found=len(metadata.get("products", [])),
                metadata=metadata
            )