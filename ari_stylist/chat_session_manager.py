import datetime
import uuid
import re
import json
import logging
from typing import Dict, Any, Optional, Tuple, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat_session_manager")

class ChatSession:
    """
    Maintains the state and history of a continuous chat session with a user,
    using CAMEL's memory system.
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        stylist_agent = None,
        product_kg = None,
        product_retriever = None,
        memory = None
    ):
        # Generate session ID if not provided
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id
        self.stylist_agent = stylist_agent
        self.product_kg = product_kg
        self.product_retriever = product_retriever
        self.memory = memory
        
        # Track session state
        self.session_start_time = datetime.datetime.now()
        self.last_activity_time = self.session_start_time
        self.messages = []
        self.context = {}
        self.current_products_context = []
        
        logger.info(f"Created new chat session: {self.session_id}")
    
    def add_message(self, content: str, sender: str, related_products: List[str] = None) -> Dict[str, Any]:
        """
        Add a message to the chat session
        
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
        
        # Add to local state
        self.messages.append(message)
        self.last_activity_time = timestamp
        
        # Add to memory if available
        if self.memory:
            try:
                from camel.messages import BaseMessage
                from camel.memories import MemoryRecord
                from camel.types import OpenAIBackendRole
                
                if sender == "user":
                    record = MemoryRecord(
                        message=BaseMessage.make_user_message(
                            role_name="User",
                            content=content,
                        ),
                        role_at_backend=OpenAIBackendRole.USER,
                    )
                else:
                    record = MemoryRecord(
                        message=BaseMessage.make_assistant_message(
                            role_name="Stylist",
                            content=content,
                        ),
                        role_at_backend=OpenAIBackendRole.ASSISTANT,
                    )
                
                self.memory.write_records([record])
                logger.info(f"Added {sender} message to CAMEL memory")
            except Exception as e:
                logger.error(f"Error adding message to CAMEL memory: {e}")
        
        return message
    

    def get_memory_context(self) -> Tuple[List[Dict[str, str]], int]:
        """
        Get context from CAMEL memory with robust error handling for CAMEL 2.43
        
        Returns:
            Tuple of (context messages, token count)
        """
        if self.memory:
            try:
                # Import the get_memory_context function from memory_integration
                from memory_integration import get_memory_context
                
                # Use the enhanced version with better error handling
                return get_memory_context(self.memory)
                
            except Exception as e:
                logger.error(f"Error getting context from CAMEL memory: {e}")
                
                # Fallback: Return recent chat history directly
                try:
                    # Format recent messages as context
                    recent_history = self.get_conversation_history(limit=5)
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
    
    def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the recent conversation history
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        if not self.messages:
            return []
            
        # Return the most recent messages, up to the limit
        return self.messages[-limit:]
    
    def update_product_context(self, products: List[Dict[str, Any]]):
        """
        Update the current products in context
        
        Args:
            products: List of product dictionaries
        """
        self.current_products_context = products
        logger.info(f"Updated product context with {len(products)} products")
        
    def get_or_fetch_user_preferences(self) -> Dict[str, Any]:
        """
        Get the user's preferences or fetch from knowledge graph if needed
        
        Returns:
            Dictionary of user preferences
        """
        if "user_preferences" in self.context:
            return self.context["user_preferences"]
            
        # If we have a user ID and product knowledge graph, try to fetch preferences
        if self.user_id and self.product_kg:
            try:
                preferences = self.product_kg.get_user_preferences(self.user_id)
                self.context["user_preferences"] = preferences
                return preferences
            except Exception as e:
                logger.error(f"Error fetching user preferences: {e}")
        
        # Return empty preferences if nothing found
        return {
            "preferred_categories": [], 
            "preferred_collections": [],
            "preferred_tags": [], 
            "budget_range": None
        }
    
    def add_interaction_context(self, key: str, value: Any):
        """
        Add contextual information to the chat session
        
        Args:
            key: Context key
            value: Context value
        """
        self.context[key] = value
        logger.info(f"Added interaction context: {key}")


class ChatManager:
    """
    Manages multiple chat sessions and provides the interface for chat functionality
    using CAMEL's memory and retrieval systems.
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
        
        logger.info("Chat Manager initialized")
    
    def get_or_create_session(self, session_id: Optional[str] = None, user_id: Optional[str] = None) -> ChatSession:
        """
        Get an existing session or create a new one
        
        Args:
            session_id: Optional session ID
            user_id: Optional user ID
            
        Returns:
            Chat session object
        """
        # If session ID provided and exists, return it
        if session_id and session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # Create new memory for this session
        memory = None
        if self.memory_setup_func:
            try:
                memory = self.memory_setup_func()
                logger.info("Created new memory for session")
            except Exception as e:
                logger.error(f"Failed to create memory: {e}")
        
        # Create new session
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            stylist_agent=self.stylist_agent,
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory=memory
        )
        
        # Store in active sessions
        self.active_sessions[session.session_id] = session
        
        # If user ID provided, load user preferences
        if user_id:
            session.get_or_fetch_user_preferences()
        
        return session
    

    def _handle_meta_question(self, session: ChatSession, message: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Handle follow-up responses and meta-questions using CAMEL memory
        Compatible with CAMEL 2.43
        
        Args:
            session: Chat session
            message: User message
            
        Returns:
            Tuple of (response message, additional data) or None if not a meta-question
        """
        # Get CAMEL memory context with improved error handling
        try:
            memory_context, token_count = session.get_memory_context()
            
            if not memory_context or len(memory_context) < 2:  # Need at least previous Q&A
                logger.info("Insufficient context in memory for meta-question handling")
                return None
                
            # Format memory context for agent
            context_text = ""
            for msg in memory_context:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context_text += f"{role.upper()}: {content}\n\n"
            
            # Create a meta-question detection prompt
            meta_question_prompt = f"""
            Based on our conversation history, I need to address your follow-up question:
            
            CONVERSATION HISTORY:
            {context_text}
            
            LATEST QUESTION: {message}
            
            I'll think about how this question relates to our previous discussion about style and fashion.
            """
            
            # Send to stylist agent
            try:
                from camel.messages import BaseMessage
                
                # Add user message to session first
                session.add_message(message, "user")
                
                meta_message = BaseMessage.make_user_message(
                    role_name="User",
                    content=meta_question_prompt
                )
                
                agent_response = session.stylist_agent.step(meta_message)
                response_text = agent_response.msg.content
                
                # Add agent message to session
                session.add_message(response_text, "agent")
                
                logger.info("Handled meta-question successfully")
                
                return response_text, {
                    "result_type": "meta_response",
                    "is_follow_up": True
                }
            except Exception as e:
                logger.error(f"Error handling meta-question with agent: {e}")
                return None
                
        except Exception as e:
            logger.warning(f"Error in meta-question handling: {e}")
            return None
    
    def _extract_parameters(self, message: str) -> Dict[str, Any]:
        """
        Extract query parameters from a user message
        
        Args:
            message: User message
            
        Returns:
            Dictionary of extracted parameters
        """
        import re
        
        # Initialize params with default values
        params = {
            "category": None,
            "collection": None,  # Changed from 'brand' to match actual schema
            "tag": None,         # Added for tag search
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
    
    def _handle_product_search(self, session: ChatSession, message: str) -> Tuple[str, Dict[str, Any]]:
        """
        Handle product search requests
        
        Args:
            session: Chat session
            message: User message
            
        Returns:
            Tuple of (response message, additional data)
        """
        # Add user message to session
        session.add_message(message, "user")
        
        # Extract parameters from the message
        params = self._extract_parameters(message)
        
        # Get user preferences to augment the search
        user_preferences = session.get_or_fetch_user_preferences()
        
        # Combine explicit parameters with user preferences when appropriate
        if not params.get("collection") and user_preferences.get("preferred_collections"):
            # Only use preferred collection if the user didn't specify one
            params["collection"] = user_preferences["preferred_collections"][0] if user_preferences["preferred_collections"] else None
        
        # Transform materials into tags for proper database search
        if params.get("materials") and not params.get("tag"):
            params["tag"] = params["materials"][0]
        
        # Same for colors - treat them as tags
        if params.get("colors") and not params.get("tag"):
            params["tag"] = params["colors"][0]
        
        # Perform search using knowledge graph
        search_results = []
        if session.product_kg:
            try:
                # Use the updated schema-compatible method
                search_results = session.product_kg.get_product_by_filter(
                    category=params.get("category"),
                    collection=params.get("collection"),
                    tag=params.get("tag"),
                    min_price=params.get("min_price"),
                    max_price=params.get("max_price"),
                    limit=5
                )
                
                logger.info(f"Found {len(search_results)} products from knowledge graph")
                
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
                retriever_results = session.product_retriever.search_by_natural_language(nl_query, limit=5)
                
                if retriever_results:
                    logger.info(f"Found {len(retriever_results)} additional products from retriever")
                    search_results.extend(retriever_results)
                    
                    # Deduplicate results by ID
                    seen_ids = set()
                    unique_results = []
                    
                    for product in search_results:
                        if product.get("id") not in seen_ids:
                            seen_ids.add(product.get("id"))
                            unique_results.append(product)
                    
                    search_results = unique_results[:5]  # Limit to 5 products
                
            except Exception as e:
                logger.error(f"Error augmenting search with retriever: {e}")
        
        # Update session with current products context
        if search_results:
            session.update_product_context(search_results)
        
        # Prepare data for the agent context
        conversation_context = ""
        recent_history = session.get_conversation_history(limit=5)
        for msg in recent_history:
            sender = "User" if msg["sender"] == "user" else "Stylist"
            conversation_context += f"{sender}: {msg['content']}\n\n"
        
        # Prepare product IDs for tracking
        product_ids = [product.get("id", "") for product in search_results if product.get("id")]
        
        # Create product descriptions in a more natural, conversational format
        product_descriptions = []
        for product in search_results:
            # Extract key information
            title = product.get("title", "Stylish item")
            price = product.get("price", 0)
            categories = ", ".join(product.get("categories", []))
            features = ", ".join(product.get("features", []) or product.get("tags", []))
            description = product.get("description", "")
            
            # Create a natural description
            desc = (f"A {title} that would be perfect for you. "
                   f"It's priced at ${price} ")
            
            if categories:
                desc += f"and is great for {categories}. "
            else:
                desc += "and is very versatile. "
                
            if features:
                desc += f"What makes it special is {features}. "
                
            if description and len(description) > 10:  # Only add if meaningful description exists
                # Truncate long descriptions
                short_desc = description[:100] + "..." if len(description) > 100 else description
                desc += f"The product details mention: {short_desc}"
                
            product_descriptions.append(desc)
        
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

        Here are the products I've found:

        {' '.join(product_descriptions)}

        Respond as if you're having a friendly styling consultation in person, making the client feel understood and excited about these options.
        """
        
        # Send context to the agent
        try:
            from camel.messages import BaseMessage
            user_message = BaseMessage.make_user_message(
                role_name="User",
                content=agent_context
            )
            
            agent_response = session.stylist_agent.step(user_message)
            response_text = agent_response.msg.content
            
            # Apply post-processing to ensure natural conversation
            response_text = self._naturalize_response(response_text)
            
            # Add agent message to session
            agent_message = session.add_message(response_text, "agent", related_products=product_ids)
            
            # Return the response and result data
            result_data = {
                "result_type": "product_search",
                "products": search_results,
                "parameters": params
            }
            
            logger.info("Product search handled successfully")
            return response_text, result_data
            
        except Exception as e:
            logger.error(f"Error getting response from agent: {e}")
            fallback_response = "I'm sorry, I'm having trouble finding products that match your request right now. Could you try describing what you're looking for in a different way, or perhaps be more specific about the type of item you need?"
            
            # Add fallback response to session
            session.add_message(fallback_response, "agent")
            
            return fallback_response, {
                "result_type": "error",
                "error": str(e)
            }
    
    def _naturalize_response(self, response_text: str) -> str:
        """
        Post-process agent responses to remove robotic formatting elements
        and enhance natural conversational flow.
        
        Args:
            response_text: Original response from the agent
            
        Returns:
            Naturalized response text
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
        
        # Remove headers
        response_text = re.sub(r'^#{1,6}\s+(.*)$', r'\1', response_text, flags=re.MULTILINE)
        
        # Replace categorical headers with conversational transitions
        transitions = {
            "For Men:": "For a more masculine look, ",
            "For Women:": "For a more feminine style, ",
            "Accessories:": "To complete the look, ",
            "Dress Shirt:": "When it comes to shirts, ",
            "Blazer and Chinos:": "For a smart-casual option, ",
            "Cocktail Dress:": "If you're considering a dress, "
        }
        
        for header, transition in transitions.items():
            response_text = response_text.replace(header, transition)
        
        # Add more personal language
        personal_phrases = [
            "I think ", "I'd recommend ", "In my experience, ", 
            "You might love ", "I'm picturing ", "I could see you in "
        ]
        
        # Check for short paragraphs that might be item introductions and add personal phrases
        lines = response_text.split('\n')
        for i in range(len(lines)):
            # If line starts a new paragraph and is relatively short
            if lines[i].strip() and (i == 0 or not lines[i-1].strip()):
                if 20 < len(lines[i]) < 100 and not any(phrase in lines[i] for phrase in personal_phrases):
                    # Add a personal phrase to the beginning
                    random_phrase = random.choice(personal_phrases)
                    # Make sure first character after phrase is lowercase
                    if len(lines[i]) > 0:
                        lines[i] = random_phrase + lines[i][0].lower() + lines[i][1:]
        
        response_text = '\n'.join(lines)
        
        return response_text
    
    def process_message(self, session_id: Optional[str], user_id: Optional[str], message: str) -> Tuple[str, Dict[str, Any]]:
        """
        Process a user message and generate a response
        
        Args:
            session_id: Optional session ID
            user_id: Optional user ID
            message: User message
            
        Returns:
            Tuple of (response message, additional data)
        """
        logger.info(f"Processing message for session {session_id}: {message[:50]}...")
        
        # Get or create session
        session = self.get_or_create_session(session_id, user_id)
        
        # Check if this is a follow-up or meta-question
        meta_response = self._handle_meta_question(session, message)
        if meta_response:
            logger.info("Handled as meta-question")
            return meta_response
        
        # Handle as a product search if no meta-response
        logger.info("Handling as product search")
        return self._handle_product_search(session, message)
