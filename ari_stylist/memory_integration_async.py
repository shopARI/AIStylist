"""
Enhanced Asynchronous Memory Integration for AI Stylist.

This module provides advanced functions to set up and manage persistent memory 
for the AI Stylist, using CAMEL's memory system with Neo4j persistence.
Compatible with CAMEL-AI 0.2.43.
"""

import logging
import asyncio
import json
import uuid
import datetime
import traceback
from typing import Tuple, List, Dict, Any, Optional, Union

# Import adapter first to ensure OpenAI embedding compatibility
try:
    from openai_embedding_adapter import initialization_result
    if initialization_result:
        logging.info("OpenAI embedding adapter initialized successfully")
    else:
        logging.warning("OpenAI embedding adapter initialization failed")
except Exception as e:
    logging.warning(f"Failed to import OpenAI embedding adapter: {e}")

# Import required modules for memory integration from CAMEL
from camel.memories import (
    ChatHistoryBlock,
    LongtermAgentMemory,
    MemoryRecord,
    ScoreBasedContextCreator
)
from camel.messages import BaseMessage
from camel.types import ModelType, OpenAIBackendRole
from camel.utils import OpenAITokenCounter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory_integration_async")

async def setup_stylist_memory_async(
    model_type: ModelType = ModelType.GPT_4O, 
    token_limit: int = 2048,
    user_id: Optional[str] = None,
    neo4j_client = None
) -> LongtermAgentMemory:
    """
    Initialize the memory system for the AI stylist using CAMEL's LongtermAgentMemory.
    Enhanced with persistence capabilities and user-specific loading.
    
    Args:
        model_type: Type of model to use for token counting
        token_limit: Maximum token limit for context window
        user_id: Optional user ID for loading persistent memory
        neo4j_client: Neo4j client for persistence operations
        
    Returns:
        LongtermAgentMemory: Configured memory system for the stylist agent
    """
    logger.info(f"Setting up stylist memory with model type {model_type} and token limit {token_limit}")
    
    memory = None
    
    # Try to load existing memory if user_id is provided
    if user_id and neo4j_client:
        try:
            logger.info(f"Attempting to load memory for user {user_id}")
            memory = await load_memory_for_user_async(user_id, neo4j_client, model_type)
            
            if memory:
                logger.info(f"Successfully loaded memory for user {user_id}")
                return memory
            else:
                logger.info(f"No existing memory found for user {user_id}, creating new memory")
        except Exception as e:
            logger.error(f"Error loading memory for user {user_id}: {e}", exc_info=True)
            # Continue to create new memory
    
    # Define memory setup function
    async def _setup_memory():
        try:
            # Set up token counter for the appropriate model
            token_counter = OpenAITokenCounter(model_type)
            
            # Create memory
            memory = LongtermAgentMemory(
                context_creator=ScoreBasedContextCreator(
                    token_counter=token_counter,
                    token_limit=token_limit,
                ),
                chat_history_block=ChatHistoryBlock()
            )
            
            # Add user_id to metadata if provided
            if user_id:
                memory.metadata = {"user_id": user_id, "created_at": datetime.datetime.now().isoformat()}
                
            return memory
        except Exception as e:
            logger.error(f"Error in _setup_memory: {e}", exc_info=True)
            return None
    
    # Run memory setup in thread pool
    try:
        memory = await asyncio.to_thread(_setup_memory)
        
        if not memory:
            logger.error("Failed to create memory")
            raise RuntimeError("Failed to create memory")
            
        logger.info("Stylist memory setup successful")
        return memory
    except Exception as e:
        logger.error(f"Error setting up memory: {e}", exc_info=True)
        # Create a minimal fallback memory
        try:
            logger.info("Attempting to create minimal fallback memory")
            
            # Run in thread pool to avoid blocking
            minimal_memory = await asyncio.to_thread(
                lambda: LongtermAgentMemory(
                    context_creator=ScoreBasedContextCreator(
                        token_counter=OpenAITokenCounter(ModelType.GPT_3_5_TURBO),
                        token_limit=512,
                    )
                )
            )
            
            # Add user_id to metadata if provided
            if user_id and minimal_memory:
                minimal_memory.metadata = {"user_id": user_id, "created_at": datetime.datetime.now().isoformat()}
                
            logger.info("Created minimal memory system")
            return minimal_memory
        except Exception as e3:
            logger.error(f"Failed to create even minimal memory: {e3}", exc_info=True)
            raise RuntimeError("Unable to create any memory system")

class MemoryState:
    """Class for serializing and deserializing memory states"""
    
    @staticmethod
    async def serialize_memory(memory: LongtermAgentMemory) -> Dict[str, Any]:
        """
        Serialize a CAMEL memory instance for storage.
        
        Args:
            memory: LongtermAgentMemory instance
            
        Returns:
            Dictionary with serialized memory data
        """
        if not memory:
            logger.warning("Cannot serialize memory: memory is None")
            return {}
            
        try:
            # Extract chat history records
            chat_history = {}
            
            if hasattr(memory, 'chat_history_block') and hasattr(memory.chat_history_block, 'memory'):
                for record_id, record in memory.chat_history_block.memory.items():
                    if hasattr(record, 'message') and hasattr(record.message, 'content'):
                        role = "user" if record.role_at_backend == OpenAIBackendRole.USER else "assistant"
                        chat_history[record_id] = {
                            "role": role,
                            "content": record.message.content,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "metadata": record.metadata if hasattr(record, 'metadata') else {}
                        }
            
            # Extract vector records if available
            vector_records = []
            
            if hasattr(memory, 'vector_db_block') and hasattr(memory.vector_db_block, 'storage'):
                try:
                    # Note: This is a simplification as direct access to records might not be available
                    # In a production system, we would implement a more robust extraction method
                    pass
                except Exception as e:
                    logger.error(f"Error extracting vector records: {e}", exc_info=True)
            
            # Create the serialized memory structure
            serialized = {
                "chat_history": chat_history,
                "vector_records": vector_records,
                "serialized_at": datetime.datetime.now().isoformat(),
                "version": "1.0"
            }
            
            logger.info(f"Serialized memory with {len(chat_history)} chat history records")
            return serialized
        
        except Exception as e:
            logger.error(f"Error serializing memory: {e}", exc_info=True)
            return {}
    
    @staticmethod
    async def deserialize_memory(serialized_data: Dict[str, Any], model_type: ModelType = ModelType.GPT_4O) -> Optional[LongtermAgentMemory]:
        """
        Deserialize memory data into a CAMEL memory instance.
        
        Args:
            serialized_data: Dictionary with serialized memory data
            model_type: Type of model to use for token counting
            
        Returns:
            LongtermAgentMemory instance or None if deserialization fails
        """
        if not serialized_data:
            logger.warning("Cannot deserialize memory: no data provided")
            return None
            
        try:
            # Create a new memory instance
            memory = await setup_stylist_memory_async(model_type)
            
            if not memory:
                logger.error("Failed to create new memory instance for deserialization")
                return None
                
            # Restore chat history records
            chat_history = serialized_data.get("chat_history", {})
            
            for record_id, record_data in chat_history.items():
                role = record_data.get("role")
                content = record_data.get("content")
                metadata = record_data.get("metadata", {})
                
                if role and content:
                    # Create the appropriate message based on role
                    if role == "user":
                        message = BaseMessage.make_user_message(
                            role_name="User",
                            content=content
                        )
                        role_at_backend = OpenAIBackendRole.USER
                    else:
                        message = BaseMessage.make_assistant_message(
                            role_name="Stylist",
                            content=content
                        )
                        role_at_backend = OpenAIBackendRole.ASSISTANT
                    
                    # Create and add the memory record
                    record = MemoryRecord(
                        message=message,
                        role_at_backend=role_at_backend,
                        metadata=metadata
                    )
                    
                    # Add to memory - use to_thread for non-blocking operation
                    await asyncio.to_thread(memory.write_records, [record])
            
            # Restore vector records if available
            # This would be implemented based on the specific vectorization approach
            
            logger.info(f"Successfully deserialized memory with {len(chat_history)} chat records")
            return memory
            
        except Exception as e:
            logger.error(f"Error deserializing memory: {e}", exc_info=True)
            return None

async def load_memory_for_user_async(
    user_id: str,
    neo4j_client,
    model_type: ModelType = ModelType.GPT_4O
) -> Optional[LongtermAgentMemory]:
    """
    Load memory for a specific user from Neo4j.
    
    Args:
        user_id: User ID
        neo4j_client: Neo4j client for persistence operations
        model_type: Type of model to use for token counting
        
    Returns:
        LongtermAgentMemory instance or None if not found
    """
    if not user_id or not neo4j_client:
        logger.warning("Cannot load memory: invalid user ID or Neo4j client")
        return None
        
    try:
        # Query Neo4j for the latest memory state for this user
        query = """
        MATCH (u:User {id: $user_id})-[:HAS_MEMORY]->(m:MemoryState)
        WHERE m.type = 'camel'
        RETURN m.memory_data as memory_data, m.created_at as created_at
        ORDER BY m.created_at DESC
        LIMIT 1
        """
        
        result = await neo4j_client.query(query, {"user_id": user_id})
        
        if not result or len(result) == 0:
            logger.info(f"No memory found for user {user_id}")
            return None
            
        # Extract memory data
        memory_data = result[0].get("memory_data")
        created_at = result[0].get("created_at")
        
        if not memory_data:
            logger.warning(f"Empty memory data for user {user_id}")
            return None
            
        # Deserialize the memory data
        try:
            memory_dict = json.loads(memory_data)
            memory = await MemoryState.deserialize_memory(memory_dict, model_type)
            
            if memory:
                logger.info(f"Loaded memory for user {user_id} created at {created_at}")
                
                # Add user_id to memory metadata
                memory.metadata = {"user_id": user_id, "loaded_at": datetime.datetime.now().isoformat()}
                
                return memory
            else:
                logger.warning(f"Failed to deserialize memory for user {user_id}")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding memory JSON for user {user_id}: {e}", exc_info=True)
            return None
            
    except Exception as e:
        logger.error(f"Error loading memory for user {user_id}: {e}", exc_info=True)
        return None

async def save_memory_for_user_async(
    memory: LongtermAgentMemory,
    user_id: str,
    neo4j_client
) -> bool:
    """
    Save memory for a specific user to Neo4j.
    
    Args:
        memory: LongtermAgentMemory instance
        user_id: User ID
        neo4j_client: Neo4j client for persistence operations
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory or not user_id or not neo4j_client:
        logger.warning("Cannot save memory: invalid memory, user ID, or Neo4j client")
        return False
        
    try:
        # Serialize the memory
        memory_dict = await MemoryState.serialize_memory(memory)
        
        if not memory_dict:
            logger.warning(f"Empty serialized memory for user {user_id}")
            return False
            
        # Convert to JSON
        memory_json = json.dumps(memory_dict)
        
        # Generate a unique ID for this memory state
        memory_id = str(uuid.uuid4())
        created_at = datetime.datetime.now().isoformat()
        
        # Save to Neo4j
        query = """
        // Ensure the user exists
        MERGE (u:User {id: $user_id})
        
        // Create the memory state
        CREATE (m:MemoryState {
            id: $memory_id,
            type: 'camel',
            memory_data: $memory_data,
            created_at: $created_at
        })
        
        // Connect the memory to the user
        CREATE (u)-[:HAS_MEMORY]->(m)
        
        RETURN m.id as memory_id
        """
        
        result = await neo4j_client.query(
            query, 
            {
                "user_id": user_id,
                "memory_id": memory_id,
                "memory_data": memory_json,
                "created_at": created_at
            }
        )
        
        if result and result[0].get("memory_id") == memory_id:
            logger.info(f"Saved memory state {memory_id} for user {user_id}")
            
            # Cleanup old memory states to avoid excessive storage
            await cleanup_old_memory_states_async(user_id, neo4j_client)
            
            return True
        else:
            logger.warning(f"Failed to save memory for user {user_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error saving memory for user {user_id}: {e}", exc_info=True)
        return False

async def cleanup_old_memory_states_async(
    user_id: str,
    neo4j_client,
    keep_latest: int = 3
) -> bool:
    """
    Clean up old memory states for a user to avoid excessive storage.
    
    Args:
        user_id: User ID
        neo4j_client: Neo4j client for persistence operations
        keep_latest: Number of latest memory states to keep
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not user_id or not neo4j_client:
        return False
        
    try:
        # Query to delete old memory states
        query = """
        MATCH (u:User {id: $user_id})-[:HAS_MEMORY]->(m:MemoryState)
        WITH m, u
        ORDER BY m.created_at DESC
        SKIP $keep_latest
        DETACH DELETE m
        """
        
        await neo4j_client.query(query, {"user_id": user_id, "keep_latest": keep_latest})
        
        logger.info(f"Cleaned up old memory states for user {user_id}, keeping {keep_latest} latest")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning up old memory states for user {user_id}: {e}", exc_info=True)
        return False

async def add_message_to_memory_async(
    memory: LongtermAgentMemory, 
    content: str, 
    sender: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Add a message to the agent's memory asynchronously."""
    if not memory:
        logger.warning("Cannot add message to memory: memory is None")
        return False
    
    try:
        # Ensure memory is not a coroutine by awaiting it if needed
        if asyncio.iscoroutine(memory):
            logger.info("Memory is a coroutine, awaiting it before adding message")
            memory = await memory
            
        # Create the memory record based on sender
        if sender == "user":
            record = MemoryRecord(
                message=BaseMessage.make_user_message(
                    role_name="User",
                    content=content,
                ),
                role_at_backend=OpenAIBackendRole.USER,
                metadata=metadata or {},
            )
        else:
            record = MemoryRecord(
                message=BaseMessage.make_assistant_message(
                    role_name="Stylist",
                    content=content,
                ),
                role_at_backend=OpenAIBackendRole.ASSISTANT,
                metadata=metadata or {},
            )
        
        # Explicit function for thread pool to avoid capturing complex state
        def _write_to_memory(mem, rec):
            try:
                mem.write_records([rec])
                return True
            except Exception as e:
                logger.error(f"Error in _write_to_memory: {e}", exc_info=True)
                return False
                
        result = await asyncio.to_thread(_write_to_memory, memory, record)
        
        if result:
            logger.info(f"Added {sender} message to memory: {content[:50]}...")
        else:
            logger.error(f"Failed to add {sender} message to memory")
            
        return result
    
    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error adding message to memory: {e}\n{stack_trace}")
        return False

async def get_memory_context_async(memory: LongtermAgentMemory) -> Tuple[List[Dict[str, str]], int]:
    """
    Get context from the agent's memory with robust fallback options asynchronously.
    Enhanced for CAMEL-AI 0.2.43.
    
    Args:
        memory: LongtermAgentMemory instance
        
    Returns:
        Tuple of (context messages, token count)
    """
    if not memory:
        logger.warning("Cannot get context from memory: memory is None")
        return [], 0
    
    try:
        # Log the memory retrieval attempt
        logger.debug("Retrieving memory context...")
        
        # Try getting context using a separate function to avoid capturing complex state
        def _get_memory_context(mem):
            try:
                context, tokens = mem.get_context()
                return context, tokens, None
            except Exception as e:
                return None, 0, e
                
        # Use asyncio.to_thread to make this non-blocking
        context, tokens, error = await asyncio.to_thread(_get_memory_context, memory)
        
        if error:
            logger.warning(f"Error getting context from memory: {error}")
            
            # Access the memory records directly if available
            try:
                # Define explicit function for thread pool
                def _get_history_records(mem):
                    try:
                        if hasattr(mem, 'chat_history_block') and hasattr(mem.chat_history_block, 'memory'):
                            return list(mem.chat_history_block.memory.values())
                        return []
                    except Exception as e:
                        logger.error(f"Error in _get_history_records: {e}", exc_info=True)
                        return []
                        
                # Use to_thread to retrieve this in a non-blocking way
                history_records = await asyncio.to_thread(_get_history_records, memory)
                
                # Format the history records into context messages
                context = []
                
                for record in history_records[-10:]:  # Get last 10 messages
                    if hasattr(record, 'role_at_backend') and hasattr(record, 'message'):
                        role = "user" if record.role_at_backend == OpenAIBackendRole.USER else "assistant"
                        content = record.message.content if hasattr(record.message, 'content') else ""
                        context.append({
                            "role": role,
                            "content": content
                        })
                
                logger.info(f"Retrieved fallback chat history with {len(context)} messages")
                return context, 0  # Token count unknown in fallback mode
            except Exception as e2:
                logger.error(f"Error getting chat history fallback: {e2}", exc_info=True)
                return [], 0
        else:
            if context:
                logger.info(f"Retrieved memory context with {len(context)} messages and {tokens} tokens")
            else:
                logger.info("Retrieved empty memory context")
            return context, tokens
    
    except Exception as e:
        logger.error(f"Error getting context from memory: {e}", exc_info=True)
        return [], 0

async def extract_preferences_from_memory_async(
    memory: LongtermAgentMemory
) -> Dict[str, Any]:
    """
    Extract user preferences from memory content.
    
    Args:
        memory: LongtermAgentMemory instance
        
    Returns:
        Dictionary of extracted preferences
    """
    if not memory:
        logger.warning("Cannot extract preferences: memory is None")
        return {}
        
    try:
        # Get all memory records
        if not hasattr(memory, 'chat_history_block') or not hasattr(memory.chat_history_block, 'memory'):
            logger.warning("Memory does not have chat_history_block or memory attribute")
            return {}
            
        # Define explicit function for thread pool
        def _get_memory_records(mem):
            try:
                if hasattr(mem, 'chat_history_block') and hasattr(mem.chat_history_block, 'memory'):
                    return list(mem.chat_history_block.memory.values())
                return []
            except Exception as e:
                logger.error(f"Error in _get_memory_records: {e}", exc_info=True)
                return []
                
        # Use to_thread to retrieve this in a non-blocking way
        history_records = await asyncio.to_thread(_get_memory_records, memory)
        
        # Look for preference records with specific metadata
        preferences = {}
        
        for record in history_records:
            if hasattr(record, 'metadata'):
                metadata = record.metadata
                
                if metadata.get('type') == 'user_preference':
                    pref_type = metadata.get('preference_type')
                    pref_value = metadata.get('preference_value')
                    
                    if pref_type:
                        preferences[pref_type] = pref_value
        
        # If preferences were found in metadata, return them
        if preferences:
            logger.info(f"Extracted {len(preferences)} preferences from memory metadata")
            return preferences
            
        # Otherwise, try to extract preferences from message content
        extracted_prefs = {
            "preferred_categories": [],
            "preferred_collections": [],
            "preferred_tags": [],
            "budget_range": None,
            "style_preferences": [],
            "color_preferences": [],
            "occasion_preferences": []
        }
        
        # Create a simplified string representation of the memory for preference extraction
        memory_content = ""
        
        for record in history_records:
            if hasattr(record, 'message') and hasattr(record.message, 'content'):
                # Only use user messages to extract preferences
                if hasattr(record, 'role_at_backend') and record.role_at_backend == OpenAIBackendRole.USER:
                    memory_content += record.message.content + " "
        
        # Simple extraction based on keywords - in a real system, this would be more sophisticated
        
        # Extract color preferences
        color_keywords = ["red", "blue", "green", "black", "white", "pink", "purple", 
                        "orange", "yellow", "gray", "brown", "teal", "navy"]
                        
        for color in color_keywords:
            if f"like {color}" in memory_content.lower() or f"prefer {color}" in memory_content.lower():
                extracted_prefs["color_preferences"].append(color)
        
        # Extract style preferences
        style_keywords = ["casual", "formal", "elegant", "vintage", "modern", "classic",
                        "bohemian", "minimalist", "sporty", "preppy", "romantic"]
                        
        for style in style_keywords:
            if f"like {style}" in memory_content.lower() or f"prefer {style}" in memory_content.lower():
                extracted_prefs["style_preferences"].append(style)
        
        # Extract category preferences
        category_keywords = ["dress", "dresses", "pants", "jeans", "shirts", "t-shirts",
                           "skirts", "sweaters", "jackets", "coats", "shoes", "accessories"]
                           
        for category in category_keywords:
            if f"like {category}" in memory_content.lower() or f"prefer {category}" in memory_content.lower():
                extracted_prefs["preferred_categories"].append(category)
        
        # Extract occasion preferences
        occasion_keywords = ["wedding", "party", "work", "office", "casual", "formal",
                           "date", "evening", "outdoor", "vacation", "beach"]
                           
        for occasion in occasion_keywords:
            if f"for {occasion}" in memory_content.lower():
                extracted_prefs["occasion_preferences"].append(occasion)
        
        # Extract budget information - simplified
        if "budget" in memory_content.lower():
            if "low" in memory_content.lower():
                extracted_prefs["budget_range"] = {"min": 0, "max": 50}
            elif "high" in memory_content.lower():
                extracted_prefs["budget_range"] = {"min": 100, "max": 500}
            else:
                extracted_prefs["budget_range"] = {"min": 50, "max": 100}
        
        logger.info(f"Extracted preferences from memory content: {extracted_prefs}")
        return extracted_prefs
        
    except Exception as e:
        logger.error(f"Error extracting preferences from memory: {e}", exc_info=True)
        return {}

async def add_user_preference_to_memory_async(
    memory: LongtermAgentMemory, 
    preference_type: str, 
    preference_value: Any,
    persist_to_neo4j: bool = True,
    user_id: Optional[str] = None,
    neo4j_client = None
) -> bool:
    """
    Add user preference information to memory asynchronously.
    
    Args:
        memory: LongtermAgentMemory instance
        preference_type: Type of preference (e.g., "color", "style", "budget")
        preference_value: Value of the preference
        persist_to_neo4j: Whether to persist preference to Neo4j
        user_id: User ID (required if persist_to_neo4j is True)
        neo4j_client: Neo4j client (required if persist_to_neo4j is True)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory:
        logger.warning("Cannot add preference to memory: memory is None")
        return False
        
    try:
        # Create preference message content
        if isinstance(preference_value, list):
            value_str = ", ".join(str(v) for v in preference_value)
        else:
            value_str = str(preference_value)
            
        content = f"User preference: {preference_type} = {value_str}"
        
        # Create a memory record with preference metadata
        metadata = {
            "type": "user_preference",
            "preference_type": preference_type,
            "preference_value": preference_value,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add to memory as system message - FIXED for CAMEL-AI 0.2.43
        # Create an assistant message but override the role to system
        record = MemoryRecord(
            message=BaseMessage.make_assistant_message(
                role_name="System",  # Use "System" as role name
                content=content,
            ),
            role_at_backend=OpenAIBackendRole.SYSTEM,  # This ensures it's treated as a system message
            metadata=metadata,
        )
        
        # Define explicit function for thread pool
        def _write_preference_to_memory(mem, rec):
            try:
                mem.write_records([rec])
                return True
            except Exception as e:
                logger.error(f"Error in _write_preference_to_memory: {e}", exc_info=True)
                return False
        
        # Use asyncio.to_thread to make this non-blocking
        result = await asyncio.to_thread(_write_preference_to_memory, memory, record)
        
        if result:
            logger.info(f"Added user preference to memory: {preference_type} = {value_str}")
        else:
            logger.error(f"Failed to add preference to memory: {preference_type}")
            return False
        
        # Persist to Neo4j if requested
        if persist_to_neo4j and user_id and neo4j_client:
            try:
                # Convert preference value to JSON string for storage
                if isinstance(preference_value, (list, dict)):
                    value_json = json.dumps(preference_value)
                else:
                    value_json = json.dumps(str(preference_value))
                    
                # Create unique ID for preference
                preference_id = str(uuid.uuid4())
                
                # Save to Neo4j
                query = """
                // Ensure the user exists
                MERGE (u:User {id: $user_id})
                
                // Create preference
                CREATE (p:UserPreference {
                    id: $preference_id,
                    type: $preference_type,
                    value: $value,
                    created_at: $created_at
                })
                
                // Connect the preference to the user
                CREATE (u)-[:HAS_PREFERENCE]->(p)
                
                // Delete old preferences of the same type for this user
                OPTIONAL MATCH (u)-[:HAS_PREFERENCE]->(old:UserPreference)
                WHERE old.type = $preference_type AND old.id <> $preference_id
                DETACH DELETE old
                
                RETURN p.id as preference_id
                """
                
                neo4j_result = await neo4j_client.query(
                    query, 
                    {
                        "user_id": user_id,
                        "preference_id": preference_id,
                        "preference_type": preference_type,
                        "value": value_json,
                        "created_at": datetime.datetime.now().isoformat()
                    }
                )
                
                if neo4j_result and neo4j_result[0].get("preference_id") == preference_id:
                    logger.info(f"Persisted user preference to Neo4j: {preference_type}")
                else:
                    logger.warning(f"Failed to persist preference to Neo4j: {preference_type}")
            except Exception as e:
                logger.error(f"Error persisting preference to Neo4j: {e}", exc_info=True)
        
        return True
        
    except Exception as e:
        logger.error(f"Error adding user preference to memory: {e}", exc_info=True)
        return False

async def add_product_interaction_to_memory_async(
    memory: LongtermAgentMemory,
    product: Dict[str, Any],
    interaction_type: str = "viewed",
    persist_to_neo4j: bool = True,
    user_id: Optional[str] = None,
    neo4j_client = None
) -> bool:
    """
    Add product interaction to memory and optionally persist to Neo4j.
    
    Args:
        memory: LongtermAgentMemory instance
        product: Product dictionary
        interaction_type: Type of interaction (e.g., "viewed", "liked", "purchased")
        persist_to_neo4j: Whether to persist interaction to Neo4j
        user_id: User ID (required if persist_to_neo4j is True)
        neo4j_client: Neo4j client (required if persist_to_neo4j is True)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory or not product:
        logger.warning("Cannot add product interaction to memory: invalid input")
        return False
        
    try:
        # Extract product details
        product_id = product.get("id", "unknown")
        product_title = product.get("title", "Unknown Product")
        product_price = product.get("price", 0)
        
        # Create interaction message content
        content = f"User {interaction_type} product: {product_title} (ID: {product_id})"
        
        # Create metadata
        metadata = {
            "type": "product_interaction",
            "interaction_type": interaction_type,
            "product_id": product_id,
            "product_title": product_title,
            "product_price": product_price,
            "timestamp": datetime.datetime.now().isoformat(),
            "categories": product.get("categories", []),
            "tags": product.get("tags", [])
        }
        
        # Add to memory as system message - FIXED for CAMEL-AI 0.2.43
        # Create an assistant message but override the role to system
        record = MemoryRecord(
            message=BaseMessage.make_assistant_message(
                role_name="System",  # Use "System" as role name
                content=content,
            ),
            role_at_backend=OpenAIBackendRole.SYSTEM,  # This ensures it's treated as a system message
            metadata=metadata,
        )
        
        # Define explicit function for thread pool
        def _write_interaction_to_memory(mem, rec):
            try:
                mem.write_records([rec])
                return True
            except Exception as e:
                logger.error(f"Error in _write_interaction_to_memory: {e}", exc_info=True)
                return False
        
        # Use asyncio.to_thread to make this non-blocking
        result = await asyncio.to_thread(_write_interaction_to_memory, memory, record)
        
        if result:
            logger.info(f"Added product interaction to memory: {interaction_type} {product_id}")
        else:
            logger.error(f"Failed to add product interaction to memory: {product_id}")
            return False
        
        # Persist to Neo4j if requested
        if persist_to_neo4j and user_id and neo4j_client:
            try:
                # Create unique ID for interaction
                interaction_id = str(uuid.uuid4())
                timestamp = datetime.datetime.now().isoformat()
                
                # Save to Neo4j
                query = """
                // Ensure the user exists
                MERGE (u:User {id: $user_id})
                
                // Pass the user node to the next clause
                WITH u
                
                // Find the product
                MATCH (p:Product {id: $product_id})
                
                // Create interaction
                CREATE (i:ProductInteraction {
                    id: $interaction_id,
                    type: $interaction_type,
                    timestamp: $timestamp
                })
                
                // Connect the interaction to the user and product
                CREATE (u)-[:HAS_INTERACTION]->(i)-[:REFERS_TO]->(p)
                
                RETURN i.id as interaction_id
                """
                
                result = await neo4j_client.query(
                    query, 
                    {
                        "user_id": user_id,
                        "product_id": product_id,
                        "interaction_id": interaction_id,
                        "interaction_type": interaction_type,
                        "timestamp": timestamp
                    }
                )
                
                # If successful, increment product visit counter
                if result and result[0].get("interaction_id") == interaction_id:
                    # Query to increment visit counter
                    visit_query = """
                    MATCH (p:Product {id: $product_id})
                    SET p.visited_num = COALESCE(p.visited_num, 0) + 1
                    """
                    
                    await neo4j_client.query(visit_query, {"product_id": product_id})
                    
                    logger.info(f"Persisted product interaction to Neo4j: {interaction_type} {product_id}")
                else:
                    logger.warning(f"Failed to persist product interaction to Neo4j: {interaction_type} {product_id}")
            except Exception as e:
                logger.error(f"Error persisting product interaction to Neo4j: {e}", exc_info=True)
        
        return result
        
    except Exception as e:
        logger.error(f"Error adding product interaction to memory: {e}", exc_info=True)
        return False

async def optimize_memory_async(
    memory: LongtermAgentMemory, 
    user_id: Optional[str] = None,
    neo4j_client = None
) -> bool:
    """
    Optimize memory by summarizing and compressing memory records.
    
    Args:
        memory: LongtermAgentMemory instance
        user_id: Optional user ID for persistence
        neo4j_client: Neo4j client for persistence operations
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory:
        logger.warning("Cannot optimize memory: memory is None")
        return False
        
    try:
        # Get current memory state
        old_memory_size = 0
        
        if hasattr(memory, 'chat_history_block') and hasattr(memory.chat_history_block, 'memory'):
            old_memory_size = len(memory.chat_history_block.memory)
            
        # For a real implementation, we would:
        # 1. Identify important vs. unimportant memory records
        # 2. Summarize or compress less important records
        # 3. Keep important records (preferences, key interactions)
        
        # Since this is a placeholder, we'll just log the operation
        logger.info(f"Memory optimization performed (placeholder). Memory size: {old_memory_size}")
        
        # Save optimized memory if requested
        if user_id and neo4j_client:
            await save_memory_for_user_async(memory, user_id, neo4j_client)
        
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing memory: {e}", exc_info=True)
        return False