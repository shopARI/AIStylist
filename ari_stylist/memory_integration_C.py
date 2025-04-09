import logging
from typing import Tuple, List, Dict, Any, Optional

# Import required modules for memory integration from CAMEL
from camel.memories import (
    ChatHistoryBlock,
    LongtermAgentMemory,
    MemoryRecord,
    ScoreBasedContextCreator,
    VectorDBBlock,
)
from camel.messages import BaseMessage
from camel.types import ModelType, OpenAIBackendRole
from camel.utils import OpenAITokenCounter

# For custom embedding configuration
from camel.embeddings import OpenAIEmbedding
from camel.types import EmbeddingModelType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory_integration")

def setup_stylist_memory(model_type: ModelType = ModelType.GPT_4O, token_limit: int = 2048) -> LongtermAgentMemory:
    """
    Initialize the memory system for the AI stylist using CAMEL's LongtermAgentMemory.
    Properly configures OpenAI embeddings for CAMEL 2.43 compatibility.
    
    Args:
        model_type: Type of model to use for token counting
        token_limit: Maximum token limit for context window
    
    Returns:
        LongtermAgentMemory: Configured memory system for the stylist agent
    """
    logger.info(f"Setting up stylist memory with model type {model_type} and token limit {token_limit}")
    
    try:
        # Set up token counter for the appropriate model
        token_counter = OpenAITokenCounter(model_type)
        
        # Create custom configured OpenAI embedding instance
        # The key is to properly configure this for the current OpenAI API format
        embedding_model = OpenAIEmbedding(
            model_type=EmbeddingModelType.TEXT_EMBEDDING_ADA_2,
            # Explicitly set parameters to ensure compatibility
            request_timeout=60,
            dimensions=1536,  # Standard for ada-002
            encoding_format="float",  # Explicitly set format
            # Additional parameters to help compatibility
            config_list=None,  # Let CAMEL use its default configuration
            embedding_ctx_size=8191,  # Maximum context size
            api_key=None  # Will use environment variable
        )
        
        logger.info("Created properly configured OpenAI embedding model")
        
        # Initialize the memory with appropriate context creator and blocks
        try:
            # Create VectorDBBlock with the properly configured embedding model
            vector_block = VectorDBBlock()
            # Set the embedding model explicitly
            vector_block.embedding_model = embedding_model
            
            memory = LongtermAgentMemory(
                context_creator=ScoreBasedContextCreator(
                    token_counter=token_counter,
                    token_limit=token_limit,
                ),
                chat_history_block=ChatHistoryBlock(),
                vector_db_block=vector_block,
            )
            logger.info("Stylist memory setup with vector capabilities")
        except Exception as e:
            logger.error(f"Error setting up VectorDBBlock: {e}")
            # Try without vector block
            memory = LongtermAgentMemory(
                context_creator=ScoreBasedContextCreator(
                    token_counter=token_counter,
                    token_limit=token_limit,
                ),
                chat_history_block=ChatHistoryBlock(),
            )
            logger.info("Stylist memory setup with chat history only (no vector capabilities)")
        
        logger.info("Stylist memory setup successful")
        return memory
    
    except Exception as e:
        logger.error(f"Error setting up stylist memory: {e}")
        # Create a minimal fallback memory if the full setup fails
        try:
            # Simple memory without vector DB block to avoid embedding issues
            fallback_memory = LongtermAgentMemory(
                context_creator=ScoreBasedContextCreator(
                    token_counter=OpenAITokenCounter(ModelType.GPT_3_5_TURBO),
                    token_limit=1024,
                ),
                chat_history_block=ChatHistoryBlock(),
            )
            logger.info("Created fallback memory due to error (chat history only)")
            return fallback_memory
        except Exception as e2:
            logger.error(f"Failed to create fallback memory: {e2}")
            # Last resort: return a very basic memory system
            try:
                minimal_memory = LongtermAgentMemory(
                    context_creator=ScoreBasedContextCreator(
                        token_counter=OpenAITokenCounter(ModelType.GPT_3_5_TURBO),
                        token_limit=512,
                    )
                )
                logger.info("Created minimal memory system")
                return minimal_memory
            except Exception as e3:
                logger.error(f"Failed to create even minimal memory: {e3}")
                raise RuntimeError("Unable to create any memory system")

# The rest of the file remains the same as in the previous version
def add_message_to_memory(memory: LongtermAgentMemory, content: str, sender: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Add a message to the agent's memory.
    
    Args:
        memory: LongtermAgentMemory instance
        content: Message content
        sender: Message sender ('user' or 'agent')
        metadata: Optional metadata for the message
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory:
        logger.warning("Cannot add message to memory: memory is None")
        return False
    
    try:
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
        
        memory.write_records([record])
        logger.info(f"Added {sender} message to memory: {content[:50]}...")
        return True
    
    except Exception as e:
        logger.error(f"Error adding message to memory: {e}")
        return False

def get_memory_context(memory: LongtermAgentMemory) -> Tuple[List[Dict[str, str]], int]:
    """
    Get context from the agent's memory with robust fallback options.
    
    Args:
        memory: LongtermAgentMemory instance
        
    Returns:
        Tuple of (context messages, token count)
    """
    if not memory:
        logger.warning("Cannot get context from memory: memory is None")
        return [], 0
    
    try:
        # Try getting context - this may use embeddings which could fail with API changes
        try:
            context, tokens = memory.get_context()
            logger.info(f"Retrieved memory context with {len(context)} messages and {tokens} tokens")
            return context, tokens
        except Exception as e:
            logger.warning(f"Error getting full context from memory: {e}")
            
            # Fallback: Try to access memory records directly
            try:
                # Access the memory records directly if available
                if hasattr(memory, 'chat_history_block') and hasattr(memory.chat_history_block, 'memory'):
                    history_records = list(memory.chat_history_block.memory.values())
                    # Format the history records into context messages
                    context = []
                    
                    for record in history_records[-5:]:  # Get last 5 messages
                        if hasattr(record, 'role_at_backend') and hasattr(record, 'message'):
                            role = "user" if record.role_at_backend == OpenAIBackendRole.USER else "assistant"
                            content = record.message.content if hasattr(record.message, 'content') else ""
                            context.append({
                                "role": role,
                                "content": content
                            })
                    
                    logger.info(f"Retrieved fallback chat history with {len(context)} messages")
                    return context, 0  # Token count unknown in fallback mode
                else:
                    logger.warning("No direct access to chat history block memory")
                    return [], 0
            except Exception as e2:
                logger.error(f"Error getting chat history fallback: {e2}")
                return [], 0
    
    except Exception as e:
        logger.error(f"Error getting context from memory: {e}")
        return [], 0

def save_memory_to_disk(memory: LongtermAgentMemory, path: str) -> bool:
    """
    Save the memory state to disk for persistence.
    
    Args:
        memory: LongtermAgentMemory instance
        path: Path to save the memory
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory:
        logger.warning("Cannot save memory: memory is None")
        return False
    
    try:
        memory.save(path)
        logger.info(f"Memory saved to {path}")
        return True
    except Exception as e:
        logger.error(f"Error saving memory to {path}: {e}")
        return False

def load_memory_from_disk(path: str) -> Optional[LongtermAgentMemory]:
    """
    Load memory state from disk.
    
    Args:
        path: Path to load the memory from
        
    Returns:
        LongtermAgentMemory if successful, None otherwise
    """
    try:
        memory = LongtermAgentMemory.load(path)
        logger.info(f"Memory loaded from {path}")
        return memory
    except Exception as e:
        logger.error(f"Error loading memory from {path}: {e}")
        return None

def add_product_to_memory(memory: LongtermAgentMemory, product: Dict[str, Any], 
                         interaction_type: str = "recommendation") -> bool:
    """
    Add product interaction information to memory.
    
    Args:
        memory: LongtermAgentMemory instance
        product: Product information dictionary
        interaction_type: Type of interaction with the product
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory or not product:
        logger.warning("Cannot add product to memory: invalid input")
        return False
        
    try:
        # Create a product reference message
        product_id = product.get("id", "unknown")
        product_title = product.get("title", "Untitled Product")
        
        # Build message content based on interaction type
        if interaction_type == "recommendation":
            content = f"I recommended {product_title} (ID: {product_id})."
        elif interaction_type == "viewed":
            content = f"User viewed {product_title} (ID: {product_id})."
        elif interaction_type == "liked":
            content = f"User liked {product_title} (ID: {product_id})."
        else:
            content = f"Product interaction: {product_title} (ID: {product_id})."
            
        # Add product categories if available
        if product.get("categories"):
            categories = ", ".join(product.get("categories"))
            content += f" Categories: {categories}."
            
        # Add product collections if available
        if product.get("collections"):
            collections = ", ".join(product.get("collections"))
            content += f" Collections: {collections}."
            
        # Create a memory record with product metadata
        metadata = {
            "type": "product_interaction",
            "interaction_type": interaction_type,
            "product_id": product_id,
            "product_title": product_title,
            "product_price": product.get("price", 0),
        }
        
        # Add to memory as system message
        record = MemoryRecord(
            message=BaseMessage.make_system_message(
                role_name="System",
                content=content,
            ),
            role_at_backend=OpenAIBackendRole.SYSTEM,
            metadata=metadata,
        )
        
        memory.write_records([record])
        logger.info(f"Added product interaction to memory: {product_title}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding product to memory: {e}")
        return False

def add_user_preference_to_memory(memory: LongtermAgentMemory, preference_type: str, 
                                preference_value: Any) -> bool:
    """
    Add user preference information to memory.
    
    Args:
        memory: LongtermAgentMemory instance
        preference_type: Type of preference (e.g., "color", "style", "budget")
        preference_value: Value of the preference
        
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
        }
        
        # Add to memory as system message
        record = MemoryRecord(
            message=BaseMessage.make_system_message(
                role_name="System",
                content=content,
            ),
            role_at_backend=OpenAIBackendRole.SYSTEM,
            metadata=metadata,
        )
        
        memory.write_records([record])
        logger.info(f"Added user preference to memory: {preference_type} = {value_str}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding user preference to memory: {e}")
        return False

def clear_memory(memory: LongtermAgentMemory) -> bool:
    """
    Clear all memory records.
    
    Args:
        memory: LongtermAgentMemory instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory:
        logger.warning("Cannot clear memory: memory is None")
        return False
        
    try:
        # Add a memory reset marker
        reset_record = MemoryRecord(
            message=BaseMessage.make_system_message(
                role_name="System",
                content="Memory has been reset.",
            ),
            role_at_backend=OpenAIBackendRole.SYSTEM,
        )
        
        # Clear existing records and add the reset marker
        memory.clear()
        memory.write_records([reset_record])
        
        logger.info("Memory has been cleared")
        return True
        
    except Exception as e:
        logger.error(f"Error clearing memory: {e}")
        return False

def optimize_memory(memory: LongtermAgentMemory) -> bool:
    """
    Optimize memory by removing redundant information.
    
    Args:
        memory: LongtermAgentMemory instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not memory:
        logger.warning("Cannot optimize memory: memory is None")
        return False
        
    try:
        # Get current context
        context, _ = get_memory_context(memory)
        
        if not context:
            logger.info("No context to optimize")
            return True
            
        logger.info(f"Optimizing memory with {len(context)} context items")
        
        # Currently a placeholder for future optimization implementations
        # CAMEL does not yet provide direct memory optimization functions
        
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing memory: {e}")
        return False