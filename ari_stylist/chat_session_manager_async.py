"""
Enhanced Asynchronous Chat Session Manager for AI Stylist.

This module provides an improved session manager with persistent memory
across sessions and enhanced conversation capabilities.
Compatible with CAMEL-AI 0.2.43.
"""

import datetime
import uuid
import re
import json
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enhanced_chat_session_manager_async")

# Import memory integration functions
from memory_integration_async import (
    setup_stylist_memory_async,
    save_memory_for_user_async,
    add_message_to_memory_async,
    get_memory_context_async,
    add_product_interaction_to_memory_async,
    add_user_preference_to_memory_async,
    extract_preferences_from_memory_async,
    optimize_memory_async
)

class EnhancedChatSessionAsync:
    """
    Enhanced chat session with persistent memory and cross-session capabilities.
    Uses CAMEL's memory system with Neo4j persistence.
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        stylist_agent = None,
        product_kg = None,
        product_retriever = None,
        memory = None,
        auto_persistence: bool = True
    ):
        # Generate session ID if not provided
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id
        self.stylist_agent = stylist_agent
        self.product_kg = product_kg
        self.product_retriever = product_retriever
        self.memory = memory
        
        # Auto-persistence settings
        self.auto_persistence = auto_persistence
        self.persistence_interval = 600  # 10 minutes
        self.last_persistence_time = datetime.datetime.now()
        self.persistence_task = None
        
        # Track session state
        self.session_start_time = datetime.datetime.now()
        self.last_activity_time = self.session_start_time
        self.messages = []
        self.context = {}
        self.current_products_context = []
        
        # Lock for concurrent access to messages
        self.messages_lock = asyncio.Lock()
        
        # User preferences extracted from memory
        self.user_preferences = {}
        self.preferences_up_to_date = False
        
        # Start persistence task if enabled
        if self.auto_persistence and user_id and product_kg:
            self.persistence_task = asyncio.create_task(self._persistence_worker())
        
        logger.info(f"Created enhanced chat session: {self.session_id} for user: {self.user_id}")
    
    async def add_message(self, content: str, sender: str, related_products: List[str] = None) -> Dict[str, Any]:
        """
        Add a message to the chat session with enhanced memory integration
        
        Args:
            content: Message content
            sender: Message sender ('user' or 'agent')
            related_products: List of product IDs related to this message
            
        Returns:
            The created message object
        """
        message_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now()
        
        message = {
            "id": message_id,
            "session_id": self.session_id,
            "content": content,
            "sender": sender,
            "timestamp": timestamp,
            "related_products": related_products or []
        }
        
        # Add to local state with lock to prevent concurrent modification
        async with self.messages_lock:
            self.messages.append(message)
            self.last_activity_time = timestamp
        
        # Add to memory if available
        if self.memory:
            try:
                # Enhanced metadata for better memory retrieval
                metadata = {
                    "message_id": message_id,
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "related_products": related_products or [],
                    "timestamp": timestamp.isoformat()
                }
                
                # Add to memory using enhanced memory integration
                await add_message_to_memory_async(
                    memory=self.memory, 
                    content=content, 
                    sender=sender, 
                    metadata=metadata
                )
                
                logger.info(f"Added {sender} message to enhanced memory")
                
                # Extract and update preferences from user messages
                if sender == "user" and not self.preferences_up_to_date:
                    await self._update_preferences_from_memory()
                
            except Exception as e:
                logger.error(f"Error adding message to memory: {e}")
        
        # Schedule memory persistence if enabled
        if self.auto_persistence and self.user_id and self.product_kg and self.memory:
            current_time = datetime.datetime.now()
            if (current_time - self.last_persistence_time).total_seconds() > self.persistence_interval:
                try:
                    logger.info(f"Persisting memory for user {self.user_id}")
                    await save_memory_for_user_async(self.memory, self.user_id, self.product_kg)
                    self.last_persistence_time = current_time
                except Exception as e:
                    logger.error(f"Error persisting memory: {e}")
        
        return message
    
    async def _persistence_worker(self):
        """Background task to periodically persist memory for this session"""
        try:
            while True:
                # Sleep for the persistence interval
                await asyncio.sleep(self.persistence_interval)
                
                # Check if persistence is still needed
                current_time = datetime.datetime.now()
                time_since_activity = (current_time - self.last_activity_time).total_seconds()
                
                if time_since_activity > 300:  # 5 minutes of inactivity
                    # Final persistence before ending task
                    if self.memory and self.user_id and self.product_kg:
                        try:
                            logger.info(f"Final memory persistence for inactive session {self.session_id}")
                            await save_memory_for_user_async(self.memory, self.user_id, self.product_kg)
                            # Optimize memory before ending
                            await optimize_memory_async(self.memory, self.user_id, self.product_kg)
                        except Exception as e:
                            logger.error(f"Error in final memory persistence: {e}")
                    break
                
                # Periodic persistence
                if self.memory and self.user_id and self.product_kg:
                    try:
                        logger.info(f"Periodic memory persistence for session {self.session_id}")
                        await save_memory_for_user_async(self.memory, self.user_id, self.product_kg)
                        self.last_persistence_time = current_time
                    except Exception as e:
                        logger.error(f"Error in periodic memory persistence: {e}")
        
        except asyncio.CancelledError:
            # Task was cancelled - perform final persistence
            if self.memory and self.user_id and self.product_kg:
                try:
                    logger.info(f"Final memory persistence on cancellation for session {self.session_id}")
                    await save_memory_for_user_async(self.memory, self.user_id, self.product_kg)
                except Exception as e:
                    logger.error(f"Error in final memory persistence on cancellation: {e}")
        
        except Exception as e:
            logger.error(f"Error in persistence worker: {e}")
    
    async def get_memory_context(self) -> Tuple[List[Dict[str, str]], int]:
        """
        Get context from CAMEL memory with enhanced error handling
        
        Returns:
            Tuple of (context messages, token count)
        """
        if self.memory:
            try:
                # Use enhanced memory integration
                return await get_memory_context_async(self.memory)
                
            except Exception as e:
                logger.error(f"Error getting context from memory: {e}")
                
                # Fallback: Return recent chat history directly
                try:
                    # Format recent messages as context
                    recent_history = await self.get_conversation_history(limit=10)  # Increased from 5
                    context = []
                    
                    for msg in recent_history:
                        role = "user" if msg["sender"] == "user" else "assistant"
                        context.append({
                            "role": role,
                            "content": msg["content"]
                        })
                    
                    logger.info(f"Using fallback chat history with {len(context)} messages")
                    return context, 0
                    
                except Exception as e2:
                    logger.error(f"Error creating fallback context: {e2}")
        
        return [], 0
    
    async def _update_preferences_from_memory(self):
        """Extract and update user preferences from memory content"""
        if not self.memory:
            return
            
        try:
            # Extract preferences from memory
            memory_preferences = await extract_preferences_from_memory_async(self.memory)
            
            # Merge with existing preferences
            for key, value in memory_preferences.items():
                if isinstance(value, list):
                    # For list values, combine and deduplicate
                    existing = self.user_preferences.get(key, [])
                    if isinstance(existing, list):
                        combined = existing + value
                        # Remove duplicates while preserving order
                        self.user_preferences[key] = list(dict.fromkeys(combined))
                    else:
                        self.user_preferences[key] = value
                else:
                    # For scalar values, prefer newer values
                    self.user_preferences[key] = value
            
            # Mark preferences as up to date
            self.preferences_up_to_date = True
            
            # Also store in context for backward compatibility
            self.context["user_preferences"] = self.user_preferences
            
            logger.info(f"Updated user preferences from memory: {len(self.user_preferences)} preference types")
            
        except Exception as e:
            logger.error(f"Error updating preferences from memory: {e}")
    
    async def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the recent conversation history
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        async with self.messages_lock:
            if not self.messages:
                return []
                
            # Return the most recent messages, up to the limit
            return self.messages[-limit:]
    
    async def update_product_context(self, products: List[Dict[str, Any]]):
        """
        Update the current products in context
        
        Args:
            products: List of product dictionaries
        """
        async with self.messages_lock:
            self.current_products_context = products
        
        logger.info(f"Updated product context with {len(products)} products")
        
        # Record product interactions if a user ID is available
        if self.user_id and self.memory and self.product_kg:
            for product in products:
                try:
                    await add_product_interaction_to_memory_async(
                        memory=self.memory,
                        product=product,
                        interaction_type="recommended",
                        persist_to_neo4j=True,
                        user_id=self.user_id,
                        neo4j_client=self.product_kg
                    )
                except Exception as e:
                    logger.error(f"Error recording product interaction: {e}")
    
    async def get_or_fetch_user_preferences(self) -> Dict[str, Any]:
        """
        Get the user's preferences from memory or fetch from knowledge graph if needed
        
        Returns:
            Dictionary of user preferences
        """
        # If we already have preferences and they're up to date, return them
        if self.preferences_up_to_date and self.user_preferences:
            return self.user_preferences
            
        # If we have preferences in context (backward compatibility), use them
        if "user_preferences" in self.context:
            self.user_preferences = self.context["user_preferences"]
            return self.user_preferences
            
        # If we have a user ID and product knowledge graph, try to fetch preferences
        if self.user_id and self.product_kg:
            try:
                # Get preferences from Neo4j
                preferences = await self.product_kg.get_user_preferences(self.user_id)
                
                if preferences:
                    self.user_preferences = preferences
                    self.context["user_preferences"] = preferences
                    self.preferences_up_to_date = True
                    return preferences
                    
                # If no preferences in Neo4j, try to extract from memory
                if self.memory:
                    await self._update_preferences_from_memory()
                    return self.user_preferences
                    
            except Exception as e:
                logger.error(f"Error fetching user preferences: {e}")
        
        # If memory extraction failed or no user ID, return empty preferences
        return {
            "preferred_categories": [], 
            "preferred_collections": [],
            "preferred_tags": [], 
            "budget_range": None
        }
    
    async def add_preference(self, preference_type: str, preference_value: Any) -> bool:
        """
        Add a user preference to memory and Neo4j
        
        Args:
            preference_type: Type of preference (e.g., "color", "style", "budget")
            preference_value: Value of the preference
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Update local preferences
        if isinstance(preference_value, list):
            # For list values, ensure we have a list in preferences
            if preference_type not in self.user_preferences:
                self.user_preferences[preference_type] = []
            
            # Add new values to the list
            if not isinstance(self.user_preferences[preference_type], list):
                self.user_preferences[preference_type] = [self.user_preferences[preference_type]]
                
            # Add new values and deduplicate
            self.user_preferences[preference_type].extend(preference_value)
            self.user_preferences[preference_type] = list(dict.fromkeys(self.user_preferences[preference_type]))
        else:
            # For scalar values, simply replace
            self.user_preferences[preference_type] = preference_value
        
        # Update context for backward compatibility
        self.context["user_preferences"] = self.user_preferences
        
        # Add to memory if available
        if self.memory:
            try:
                # Enhanced with persistence
                await add_user_preference_to_memory_async(
                    memory=self.memory,
                    preference_type=preference_type,
                    preference_value=preference_value,
                    persist_to_neo4j=True if self.user_id and self.product_kg else False,
                    user_id=self.user_id,
                    neo4j_client=self.product_kg
                )
                
                logger.info(f"Added preference to memory: {preference_type}")
                return True
                
            except Exception as e:
                logger.error(f"Error adding preference to memory: {e}")
                return False
        
        # If no memory available, just use local state
        return True
    
    async def add_interaction_context(self, key: str, value: Any):
        """
        Add contextual information to the chat session
        
        Args:
            key: Context key
            value: Context value
        """
        self.context[key] = value
        logger.info(f"Added interaction context: {key}")
    
    async def record_product_interaction(self, product_id: str, interaction_type: str = "viewed") -> bool:
        """
        Record a product interaction to memory and Neo4j
        
        Args:
            product_id: Product ID
            interaction_type: Type of interaction (e.g., "viewed", "liked", "purchased")
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not product_id:
            return False
            
        try:
            # Get product details
            product = await self.product_kg.get_product_details(product_id)
            
            if not product:
                logger.warning(f"Product not found: {product_id}")
                return False
                
            # Add to memory with persistence
            if self.memory:
                await add_product_interaction_to_memory_async(
                    memory=self.memory,
                    product=product,
                    interaction_type=interaction_type,
                    persist_to_neo4j=True if self.user_id and self.product_kg else False,
                    user_id=self.user_id,
                    neo4j_client=self.product_kg
                )
                
                logger.info(f"Recorded product interaction: {interaction_type} {product_id}")
                return True
            else:
                logger.warning(f"Cannot record interaction: memory not available")
                return False
                
        except Exception as e:
            logger.error(f"Error recording product interaction: {e}")
            return False
    
    async def close(self):
        """
        Close the session and perform final persistence
        """
        # Cancel persistence task if running
        if self.persistence_task:
            self.persistence_task.cancel()
            try:
                await self.persistence_task
            except asyncio.CancelledError:
                pass
            
        # Perform final persistence
        if self.memory and self.user_id and self.product_kg:
            try:
                logger.info(f"Final memory persistence for session {self.session_id}")
                await save_memory_for_user_async(self.memory, self.user_id, self.product_kg)
                # Optimize memory before closing
                await optimize_memory_async(self.memory, self.user_id, self.product_kg)
            except Exception as e:
                logger.error(f"Error in final memory persistence: {e}")
        
        logger.info(f"Closed session {self.session_id}")


class EnhancedChatManagerAsync:
    """
    Enhanced chat manager with persistent memory and cross-session capabilities.
    Uses CAMEL's memory system with Neo4j persistence.
    """
    
    def __init__(
        self,
        stylist_agent = None,
        product_kg = None,
        product_retriever = None,
        memory_setup_func = None,
    ):
        self.stylist_agent = stylist_agent
        self.product_kg = product_kg
        self.product_retriever = product_retriever
        self.memory_setup_func = memory_setup_func
        
        # Store active sessions
        self.active_sessions = {}
        self.sessions_lock = asyncio.Lock()
        
        # Create user registry for returning users
        self.registered_users = {}
        
        # Make sure schema is set up
        if product_kg:
            asyncio.create_task(self._ensure_schema())
        
        logger.info("Enhanced Chat Manager initialized")
    
    async def _ensure_schema(self):
        """Ensure the Neo4j schema is set up correctly"""
        if hasattr(self.product_kg, 'ensure_schema'):
            try:
                await self.product_kg.ensure_schema()
                logger.info("Neo4j schema verified")
            except Exception as e:
                logger.error(f"Error ensuring Neo4j schema: {e}")
    
    async def get_or_create_session(self, session_id: Optional[str] = None, user_id: Optional[str] = None) -> EnhancedChatSessionAsync:
        """
        Get an existing session or create a new one with persistent memory
        
        Args:
            session_id: Optional session ID
            user_id: Optional user ID
            
        Returns:
            Enhanced chat session object
        """
        # If session ID provided and exists, return it
        if session_id:
            async with self.sessions_lock:
                if session_id in self.active_sessions:
                    return self.active_sessions[session_id]
        
        # If user ID provided, check if a returning user
        memory = None
        if user_id and self.product_kg:
            try:
                # Create or update user in Neo4j
                await self.product_kg.create_or_update_user(user_id)
                
                # Try to load memory for returning user
                if self.memory_setup_func:
                    memory = await self.memory_setup_func(user_id=user_id, neo4j_client=self.product_kg)
                    
                    if memory:
                        logger.info(f"Loaded persistent memory for returning user {user_id}")
                    else:
                        logger.info(f"No existing memory found for user {user_id}, creating new memory")
            except Exception as e:
                logger.error(f"Error loading memory for user {user_id}: {e}")
        
        # If no memory loaded, create new memory
        if memory is None and self.memory_setup_func:
            try:
                memory = await self.memory_setup_func(user_id=user_id, neo4j_client=self.product_kg)
                logger.info("Created new memory for session")
            except Exception as e:
                logger.error(f"Failed to create memory: {e}")
        
        # Create new session
        session = EnhancedChatSessionAsync(
            session_id=session_id,
            user_id=user_id,
            stylist_agent=self.stylist_agent,
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory=memory,
            auto_persistence=True if user_id and self.product_kg else False
        )
        
        # Store in active sessions
        async with self.sessions_lock:
            self.active_sessions[session.session_id] = session
        
        # If user ID provided, associate with this user
        if user_id:
            self.registered_users[user_id] = session.session_id
            
            # Load user preferences
            await session.get_or_fetch_user_preferences()
        
        return session
    
    async def _handle_meta_question(self, session: EnhancedChatSessionAsync, message: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Handle follow-up responses and meta-questions using CAMEL memory
        Enhanced with improved detection of memory-related questions
        
        Args:
            session: Chat session
            message: User message
            
        Returns:
            Tuple of (response message, additional data) or None if not a meta-question
        """
        # First identify if this is a memory-related question
        memory_keywords = ["remember", "recall", "mentioned", "earlier", "previous", "before", 
                            "last time", "said", "asked", "told", "history", "conversation"]
        is_memory_question = any(keyword in message.lower() for keyword in memory_keywords)
        
        # If it's not a memory-related question, check if it's a follow-up question
        # that doesn't explicitly mention memory but requires context
        pronouns = ["it", "that", "this", "they", "them", "those", "these"]
        has_pronouns = any(f" {pronoun} " in f" {message.lower()} " for pronoun in pronouns)
        
        # Proceed if we have a memory question or a potential follow-up
        if is_memory_question or has_pronouns:
            logger.info(f"Detected potential memory-related question: '{message}'")
            
            try:
                # Get memory context with improved error handling
                memory_context, token_count = await session.get_memory_context()
                
                if not memory_context or len(memory_context) < 2:  # Need at least previous Q&A
                    logger.info("Insufficient context in memory for meta-question handling")
                    
                    if is_memory_question:
                        # If explicitly asking about memory but no context available
                        # Return an honest response about limited context
                        await session.add_message(message, "user")
                        
                        response_text = ("I can see you're asking about our previous conversation, "
                                        "but I don't have enough context from our earlier interaction. "
                                        "Could you help remind me what specifically you're referring to?")
                        
                        await session.add_message(response_text, "agent")
                        
                        return response_text, {
                            "result_type": "meta_response",
                            "is_follow_up": True,
                            "has_memory_context": False
                        }
                    return None
                
                # Format memory context for agent
                context_messages = []
                for idx, msg in enumerate(memory_context):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    # Format nicely with clear separation
                    context_messages.append(f"[Message {idx+1}] {role.upper()}: {content}")
                
                context_text = "\n\n".join(context_messages)
                
                # Get user preferences for enhanced context
                user_preferences = await session.get_or_fetch_user_preferences()
                
                # Create a meta-question detection prompt with clear instructions to use memory
                meta_question_prompt = f"""
                I need to respond to a question about our conversation history. I HAVE MEMORY and should use it to answer accurately.
                
                CONVERSATION HISTORY:
                {context_text}
                
                USER PREFERENCES:
                {json.dumps(user_preferences, indent=2)}
                
                LATEST QUESTION: {message}
                
                When responding, I should:
                1. Directly acknowledge what I remember from our previous conversation
                2. Reference specific details from our conversation history
                3. Use a natural, conversational tone as the stylist Ari
                4. Connect my response to any fashion advice or products I've previously mentioned
                
                I'll now respond with full awareness of our conversation history.
                """
                
                # Add user message to session first
                await session.add_message(message, "user")
                
                # Send to stylist agent
                try:
                    from camel.messages import BaseMessage
                    
                    meta_message = BaseMessage.make_user_message(
                        role_name="User",
                        content=meta_question_prompt
                    )
                    
                    # Note: CAMEL 0.2.43 doesn't have an async step method
                    # This will be a blocking call - in a real implementation, you would
                    # run this in a separate thread or use an async-compatible agent
                    agent_response = await asyncio.to_thread(session.stylist_agent.step, meta_message)
                    response_text = agent_response.msg.content
                    
                    # Process the response to ensure it actually uses memory
                    # If the response suggests it doesn't have memory, fix it
                    no_memory_phrases = [
                        "i don't have the ability to remember", 
                        "i cannot recall", 
                        "i don't have access to",
                        "i don't have memory",
                        "i can't remember"
                    ]
                    
                    if any(phrase in response_text.lower() for phrase in no_memory_phrases):
                        # Response incorrectly claims no memory - override it
                        logger.warning("Agent response incorrectly claims no memory capability - fixing")
                        
                        # Extract a relevant detail from the conversation history
                        relevant_detail = "our previous conversation"
                        for msg in reversed(memory_context):
                            if msg.get("role") == "user" and len(msg.get("content", "")) > 10:
                                # Found a substantive user message
                                content = msg.get("content", "")
                                if len(content) > 50:
                                    content = content[:50] + "..."
                                relevant_detail = f"when you asked about '{content}'"
                                break
                        
                        # Create fixed response that acknowledges memory
                        response_text = (
                            f"Yes, I remember {relevant_detail}. Looking at our conversation history, "
                            f"I can see we've been discussing fashion advice. Is there something specific "
                            f"from our previous conversation you'd like me to elaborate on?"
                        )
                    
                    # Add agent message to session
                    await session.add_message(response_text, "agent")
                    
                    logger.info("Handled meta-question successfully")
                    
                    return response_text, {
                        "result_type": "meta_response",
                        "is_follow_up": True,
                        "has_memory_context": True,
                        "memory_context_size": len(memory_context)
                    }
                except Exception as e:
                    logger.error(f"Error handling meta-question with agent: {e}")
                    
                    # Fallback response if agent fails
                    fallback_response = (
                        "I remember our conversation, but I'm having trouble processing your question. "
                        "Could you please rephrase it or provide more details about what you'd like me to recall?"
                    )
                    
                    await session.add_message(fallback_response, "agent")
                    
                    return fallback_response, {
                        "result_type": "meta_response",
                        "is_follow_up": True,
                        "has_memory_context": True,
                        "error": str(e)
                    }
                    
            except Exception as e:
                logger.warning(f"Error in meta-question handling: {e}")
                
                if is_memory_question:
                    # If explicitly asking about memory but handling failed
                    # Return a graceful response
                    await session.add_message(message, "user")
                    
                    response_text = ("I'm having trouble accessing our conversation history right now. "
                                    "Could you help remind me what you're referring to?")
                    
                    await session.add_message(response_text, "agent")
                    
                    return response_text, {
                        "result_type": "meta_response",
                        "is_follow_up": True,
                        "error": str(e)
                    }
                
                return None
        
        # Not a memory-related question
        return None
    
    def _extract_parameters(self, message: str) -> Dict[str, Any]:
        """
        Extract query parameters from a user message
        Enhanced with more robust extraction
        
        Args:
            message: User message
            
        Returns:
            Dictionary of extracted parameters
        """
        import re
        
        # Initialize params with default values
        params = {
            "category": None,
            "collection": None,
            "tag": None,
            "min_price": None,
            "max_price": None,
            "occasion": None,
            "colors": [],
            "materials": []
        }
        
        # Extract occasion
        occasion_patterns = [
            r'for\s+(?:a|an)\s+([a-zA-Z\s]+party)',
            r'to\s+(?:a|an)\s+([a-zA-Z\s]+party)',
            r'for\s+(?:a|an)\s+([a-zA-Z\s]+wedding)',
            r'to\s+(?:a|an)\s+([a-zA-Z\s]+wedding)',
            r'for\s+(?:a|an)\s+([a-zA-Z\s]+event)',
            r'to\s+(?:a|an)\s+([a-zA-Z\s]+event)',
            r'for\s+(?:a|an)\s+([a-zA-Z\s]+occasion)'
        ]
        
        for pattern in occasion_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params["occasion"] = match.group(1).strip()
                # Also set as a tag since that's how it would be stored in Neo4j
                params["tag"] = match.group(1).strip()
                break
        
        # Extract price range
        price_range_pattern = r'(?:under|less than|below)\s+\$(\d+)'
        match = re.search(price_range_pattern, message, re.IGNORECASE)
        if match:
            params["max_price"] = float(match.group(1))
        
        price_range_pattern = r'(?:around|about|approximately)\s+\$(\d+)'
        match = re.search(price_range_pattern, message, re.IGNORECASE)
        if match:
            price_value = float(match.group(1))
            params["min_price"] = price_value * 0.8  # 20% below
            params["max_price"] = price_value * 1.2  # 20% above
        
        price_range_pattern = r'(?:between|from)\s+\$(\d+)\s+(?:and|to)\s+\$(\d+)'
        match = re.search(price_range_pattern, message, re.IGNORECASE)
        if match:
            params["min_price"] = float(match.group(1))
            params["max_price"] = float(match.group(2))
        
        # Extract collection mentions (changed from brands to collections)
        collection_pattern = r'(?:from|by|collection like|collection such as|collection|)\s+([A-Z][A-Za-z\s&]+)'
        matches = re.finditer(collection_pattern, message)
        for match in matches:
            potential_collection = match.group(1).strip()
            # Simple heuristic - capitalized name that's not a common word
            if len(potential_collection) > 2 and potential_collection not in ["I", "me", "My", "The"]:
                params["collection"] = potential_collection
                break
        
        # Extract color mentions
        color_list = ["red", "blue", "green", "black", "white", "yellow", "purple", 
                      "orange", "pink", "brown", "gray", "grey", "navy", "teal", 
                      "maroon", "beige", "turquoise", "gold", "silver"]
        
        for color in color_list:
            if re.search(r'\b' + color + r'\b', message, re.IGNORECASE):
                params["colors"].append(color)
        
        # Extract material mentions  
        material_list = ["cotton", "silk", "wool", "polyester", "linen", "leather", 
                        "denim", "suede", "velvet", "cashmere", "satin", "nylon"]
        
        for material in material_list:
            if re.search(r'\b' + material + r'\b', message, re.IGNORECASE):
                params["materials"].append(material)
                
                # Also add as a tag for proper database search
                if not params["tag"]:
                    params["tag"] = material
        
        # Extract category mentions
        category_list = ["dress", "shirt", "pants", "jeans", "skirt", "blouse", 
                        "sweater", "jacket", "coat", "suit", "blazer", "t-shirt", 
                        "hoodie", "shorts", "swimwear", "activewear", "shoes", 
                        "boots", "sneakers", "accessories", "jewelry", "necklace",
                        "bracelet", "earrings", "ring", "watch", "scarf", "hat"]
        
        for category in category_list:
            if re.search(r'\b' + category + r'\b', message, re.IGNORECASE):
                params["category"] = category
                break
        
        logger.info(f"Extracted parameters: {params}")
        return params
    
    async def _handle_product_search(self, session: EnhancedChatSessionAsync, message: str) -> Tuple[str, Dict[str, Any]]:
        """
        Handle product search requests with enhanced personalization and memory
        
        Args:
            session: Enhanced chat session
            message: User message
            
        Returns:
            Tuple of (response text, result data)
        """
        # Add user message to session
        await session.add_message(message, "user")
        
        # Extract parameters from the message
        params = self._extract_parameters(message)
        
        # Get user preferences to augment the search
        user_preferences = await session.get_or_fetch_user_preferences()
        
        # Debug logging
        logger.info(f"Search parameters extracted: {params}")
        
        # Combine explicit parameters with user preferences when appropriate
        if not params.get("collection") and user_preferences.get("preferred_collections"):
            params["collection"] = user_preferences["preferred_collections"][0] if user_preferences["preferred_collections"] else None
        
        # Make sure occasion is also used as a tag for searching
        if params.get("occasion") and not params.get("tag"):
            params["tag"] = params.get("occasion")
            logger.info(f"Using occasion as tag: {params['tag']}")
        
        # Perform search using knowledge graph - DIRECT SEARCH FIRST
        search_results = []
        if session.product_kg:
            try:
                # Use the updated schema-compatible method - DIRECT SEARCH LIKE ORIGINAL
                search_results = await session.product_kg.get_product_by_filter(
                    category=params.get("category"),
                    collection=params.get("collection"),
                    tag=params.get("tag"),
                    min_price=params.get("min_price"),
                    max_price=params.get("max_price"),
                    limit=5
                )
                
                # Filter out test/untitled products and zero-priced items
                filtered_results = []
                for product in search_results:
                    if (product.get('price', 0) > 0 and 
                        product.get('title') and 
                        'test' not in product.get('title', '').lower() and
                        'untitled' not in product.get('title', '').lower()):
                        filtered_results.append(product)

                # Replace search_results with filtered_results
                search_results = filtered_results
                logger.info(f"Found {len(search_results)} products from knowledge graph")
                
                # If no results, try a more general search
                if not search_results and params.get("tag"):
                    logger.info(f"No results found, trying fallback search")
                    # Try searching with just the category
                    if params.get("category"):
                        search_results = await session.product_kg.get_product_by_filter(
                            category=params.get("category"),
                            limit=5
                        )
                        logger.info(f"Fallback search by category found {len(search_results)} products")
                    else:
                        # Get popular products as fallback
                        search_results = await session.product_kg.get_popular_products(limit=5)
                        logger.info(f"Fallback to popular products found {len(search_results)} products")
                
            except Exception as e:
                logger.error(f"Error searching products in knowledge graph: {e}")
        
        # If few results from knowledge graph, augment with retriever
        if session.product_retriever and len(search_results) < 3:
            try:
                # Construct a natural language query for the retriever
                nl_query = f"Find products that are "
                if params.get("category"):
                    nl_query += f"{params.get('category')} "
                if params.get("collection"):
                    nl_query += f"from {params.get('collection')} collection "
                if params.get("colors"):
                    nl_query += f"in {', '.join(params.get('colors'))} color "
                if params.get("tag"):
                    nl_query += f"tagged with {params.get('tag')} "
                if params.get("occasion"):
                    nl_query += f"suitable for {params.get('occasion')} "
                
                # Add price constraints if available
                if params.get("min_price") and params.get("max_price"):
                    nl_query += f"between ${params.get('min_price')} and ${params.get('max_price')} "
                elif params.get("max_price"):
                    nl_query += f"under ${params.get('max_price')} "
                
                # Use natural language search with the product retriever
                retriever_results = await session.product_retriever.search_by_natural_language(nl_query, limit=5)
                
                if retriever_results:
                    logger.info(f"Found {len(retriever_results)} additional products from retriever")
                    
                    # Add products not already in search_results
                    existing_ids = {p.get('id') for p in search_results}
                    for product in retriever_results:
                        if product.get('id') and product.get('id') not in existing_ids:
                            search_results.append(product)
                            existing_ids.add(product.get('id'))
                    
                    # Limit to 5 products
                    search_results = search_results[:5]
                
            except Exception as e:
                logger.error(f"Error augmenting search with retriever: {e}")
        
        # Update session with current products context
        if search_results:
            await session.update_product_context(search_results)
        
        # Prepare data for the agent context
        conversation_context = ""
        recent_history = await session.get_conversation_history(limit=5)
        for msg in recent_history:
            sender = "User" if msg["sender"] == "user" else "Stylist"
            conversation_context += f"{sender}: {msg['content']}\n\n"
        
        # Prepare product IDs for tracking
        product_ids = [product.get("id", "") for product in search_results if product.get("id")]
        
        # Create agent context with an emphasis on natural conversation
        agent_context = f"""
        {conversation_context}

        I've found some wonderful pieces that match what you're looking for. When sharing these with the client, please:

        - Speak conversationally as their personal stylist, Ari
        - Weave the product details naturally into your response without bullet points or lists
        - Connect each recommendation to their specific needs or the occasion they mentioned
        - Explain why you're suggesting each piece (fabric quality, versatility, current trends, etc.)
        - Express genuine enthusiasm for pieces you think would work particularly well
        - Use phrases like "I'd recommend" or "I think you'd look great in" rather than just listing options
        - Speak conversationally as their personal stylist, Ari
        - Be specific about product details including exact names and prices
        - Explain why each item would work well for their needs
        - If recommending multiple items, describe each one clearly
        Here are the products I've found:
        """

        # Add specific product details to the context
        for idx, product in enumerate(search_results, 1):
            title = product.get('title', 'Stylish item')
            price = product.get('price', 0)
            categories = ", ".join(product.get('categories', []))
            description = product.get('description', '')
            
            # Format each product with clear details
            agent_context += f"\nProduct {idx}: {title}\n"
            agent_context += f"- ID: {product.get('id', '')}\n"
            agent_context += f"- Price: ${price}\n"
            agent_context += f"- Categories: {categories}\n"
            
            if description and len(description) > 100:
                description = description[:100] + "..."
            if description:
                agent_context += f"- Description: {description}\n"

        # If no products were found, provide guidance
        if not search_results:
            agent_context += """
        I couldn't find exact product matches for their request. Please:
        - Acknowledge that we don't have the exact items they're looking for
        - Suggest general style advice based on their query
        - Ask follow-up questions to better understand their needs
        - Mention that we're constantly updating our inventory
        """

        agent_context += """
        IMPORTANT: Always mention specific product names and prices in your response.
        Respond as if you're having a friendly styling consultation, making the client feel understood and excited about these options.
        """
        
        # Send context to the agent
        try:
            from camel.messages import BaseMessage
            user_message = BaseMessage.make_user_message(
                role_name="User",
                content=agent_context
            )
            
            # Note: CAMEL 0.2.43 doesn't have an async step method
            # This will be a blocking call - in a real implementation, you would
            # run this in a separate thread or use an async-compatible agent
            agent_response = await asyncio.to_thread(session.stylist_agent.step, user_message)
            response_text = agent_response.msg.content
            
            # Apply post-processing to ensure natural conversation
            response_text = self._naturalize_response(response_text)
            
            # Add agent message to session
            agent_message = await session.add_message(response_text, "agent", related_products=product_ids)
            
            # Return the response and result data
            result_data = {
                "result_type": "product_search",
                "products": search_results,
                "parameters": params,
                "user_preferences": user_preferences
            }
            
            logger.info("Product search handled successfully")
            return response_text, result_data
            
        except Exception as e:
            logger.error(f"Error getting response from agent: {e}")
            fallback_response = "I'm sorry, I'm having trouble finding products that match your request right now. Could you try describing what you're looking for in a different way, or perhaps be more specific about the type of item you need?"
            
            # Add fallback response to session
            await session.add_message(fallback_response, "agent")
            
            return fallback_response, {
                "result_type": "error",
                "error": str(e)
            }
    
    def _naturalize_response(self, response_text: str) -> str:
        """
        Post-process agent responses to enhance natural conversational flow
        and improve product presentation.
        """
        import re
        import random
        
        # Remove numbered list formatting
        response_text = re.sub(r'^\d+\.\s', '', response_text, flags=re.MULTILINE)
        
        # Remove bullet points
        response_text = re.sub(r'^\s*[-•*]\s', '', response_text, flags=re.MULTILINE)
        
        # Remove markdown bold and italics
        response_text = re.sub(r'\*\*(.*?)\*\*', r'\1', response_text)
        response_text = re.sub(r'\*(.*?)\*', r'\1', response_text)
        
        # Ensure product prices are formatted consistently
        response_text = re.sub(r'(\$\d+)(?![\d.])', r'\1.00', response_text)
        
        # Add product highlighting phrases
        highlight_phrases = [
            "I'd particularly recommend the ",
            "You'll love the ",
            "One standout piece is the ",
            "My favorite pick is the ",
            "A perfect choice would be the "
        ]
        
        # Find product mentions without emphasis
        # This looks for capitalized product names followed by common apparel terms
        product_pattern = r'(?<!\w)((?:[A-Z][a-zA-Z]+\s)+(?:Dress|Top|Suit|Skirt|Blouse|Pants|Jacket|Gown))'
        
        # Use a counter to limit replacements (avoid over-repetition)
        replacement_count = 0
        max_replacements = 2
        
        def replace_with_highlight(match):
            nonlocal replacement_count
            if replacement_count < max_replacements:
                replacement_count += 1
                return random.choice(highlight_phrases) + match.group(1)
            return match.group(0)
        
        response_text = re.sub(product_pattern, replace_with_highlight, response_text)
        
        # Fix common grammatical errors from the replacements
        response_text = re.sub(r'the The ', 'the ', response_text, flags=re.IGNORECASE)
        response_text = re.sub(r'the An ', 'an ', response_text, flags=re.IGNORECASE)
        response_text = re.sub(r'the A ', 'a ', response_text, flags=re.IGNORECASE)
        
        # Replace categorical transitions with more natural ones
        transitions = {
            "For formal events:": "When dressing for formal events, ",
            "For casual wear:": "If you're looking for something more casual, ",
            "Accessories:": "To complete the look, ",
            "Styling tips:": "Here's how I'd style it: "
        }
        
        for formal, natural in transitions.items():
            response_text = response_text.replace(formal, natural)
        
        return response_text
    
    async def process_message(self, session_id: Optional[str], user_id: Optional[str], message: str) -> Tuple[str, Dict[str, Any]]:
        """
        Process a user message with enhanced memory and personalization
        
        Args:
            session_id: Optional session ID
            user_id: Optional user ID
            message: User message
            
        Returns:
            Tuple of (response message, additional data)
        """
        logger.info(f"Processing message for session {session_id}: {message[:50]}...")
        
        # Get or create session
        session = await self.get_or_create_session(session_id, user_id)
        
        # Check if user has a different active session
        if user_id and user_id in self.registered_users:
            registered_session_id = self.registered_users[user_id]
            if registered_session_id != session.session_id:
                logger.info(f"User {user_id} has a different active session, switching to {registered_session_id}")
                
                # Try to get the registered session
                async with self.sessions_lock:
                    if registered_session_id in self.active_sessions:
                        session = self.active_sessions[registered_session_id]
                        
                        # Update the session ID if it was provided
                        if session_id:
                            # Remove old mapping
                            del self.active_sessions[registered_session_id]
                            
                            # Update session ID
                            session.session_id = session_id
                            
                            # Add new mapping
                            self.active_sessions[session_id] = session
                            
                            # Update user registry
                            self.registered_users[user_id] = session_id
        
        # Check if this is a follow-up or meta-question
        meta_response = await self._handle_meta_question(session, message)
        if meta_response:
            logger.info("Handled as meta-question")
            return meta_response
        
        # Handle as a product search if no meta-response
        logger.info("Handling as product search")
        return await self._handle_product_search(session, message)