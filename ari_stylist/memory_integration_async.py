"""
COMPLETE Memory Integration for CAMEL-AI 0.2.64
Includes ALL backward compatibility functions needed by the system.
FIXED: Resolves memory creation issues and ensures proper API compatibility.
"""

import logging
import json
import datetime
import uuid
import asyncio
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("memory_integration_fixed")

# UPDATED: Use centralized imports from camel_imports.py
from camel_imports import (
    LongtermAgentMemory, ChatHistoryBlock, VectorDBBlock,
    MemoryRecord, ScoreBasedContextCreator, BaseMessage,
    OpenAITokenCounter, ModelType, OpenAIBackendRole,
    CAMEL_AVAILABLE
)

# Check if memory components are available
CAMEL_MEMORIES_AVAILABLE = CAMEL_AVAILABLE and LongtermAgentMemory is not None

if CAMEL_MEMORIES_AVAILABLE:
    logger.info("✅ CAMEL-AI 0.2.64 memories imported successfully")
else:
    logger.error("❌ CAMEL memories not available, using fallback implementations")


class MemoryManager:
    """
    FIXED Memory manager for CAMEL-AI 0.2.64 with proper API compatibility.
    """
    
    def __init__(self, neo4j_client=None):
        """Initialize memory manager with proper error handling."""
        self.neo4j_client = neo4j_client
        self._memory_cache = {}
        self._creation_lock = asyncio.Lock()
        self._creating_memory = set()
        
        # Verify CAMEL availability on init
        if CAMEL_MEMORIES_AVAILABLE:
            logger.info("✅ CAMEL-AI 0.2.64 memory components available")
        else:
            logger.warning("⚠️ CAMEL-AI 0.2.64 not available, using fallback implementations")
    
    async def create_memory(
        self,
        user_id: Optional[str] = None,
        token_limit: int = 1024,
        enable_vector_db: bool = False,
        enable_mcp: bool = True
    ) -> LongtermAgentMemory:
        """Create memory following CAMEL-AI 0.2.64 exact specifications."""
        
        # Prevent recursive memory creation
        memory_key = f"{user_id}_{token_limit}_{enable_vector_db}"
        
        async with self._creation_lock:
            # Check if already creating this memory
            if memory_key in self._creating_memory:
                logger.warning(f"Memory creation already in progress for {memory_key}, waiting...")
                await asyncio.sleep(0.1)
                if user_id and user_id in self._memory_cache:
                    return self._memory_cache[user_id]
                return self._create_minimal_memory_fixed()
            
            # Check cache first
            if user_id and user_id in self._memory_cache:
                logger.info(f"✅ Returning cached memory for user: {user_id}")
                return self._memory_cache[user_id]
            
            # Mark as being created
            self._creating_memory.add(memory_key)
        
        try:
            # Load existing memory if user_id provided
            if user_id and self.neo4j_client:
                try:
                    existing_memory = await self._load_memory_from_neo4j(user_id)
                    if existing_memory:
                        async with self._creation_lock:
                            self._memory_cache[user_id] = existing_memory
                            self._creating_memory.discard(memory_key)
                        logger.info(f"✅ Loaded existing memory for user: {user_id}")
                        return existing_memory
                except Exception as e:
                    logger.warning(f"Could not load existing memory: {e}")
            
            # Create new memory using EXACT CAMEL-AI 0.2.64 pattern
            memory = await self._create_memory_camel_064_fixed(token_limit, enable_vector_db)
            
            # Cache if user_id provided
            if user_id and memory:
                async with self._creation_lock:
                    self._memory_cache[user_id] = memory
            
            logger.info(f"✅ Created new CAMEL-AI 0.2.64 memory for user: {user_id}")
            return memory
            
        except Exception as e:
            logger.error(f"❌ Error creating memory: {e}")
            return self._create_minimal_memory_fixed()
        finally:
            # Always remove from creation tracking
            async with self._creation_lock:
                self._creating_memory.discard(memory_key)
    
    async def _create_memory_camel_064_fixed(self, token_limit: int, enable_vector_db: bool) -> LongtermAgentMemory:
        """Create memory using EXACT CAMEL-AI 0.2.64 pattern with proper error handling."""
        try:
            if not CAMEL_MEMORIES_AVAILABLE:
                return self._create_minimal_memory_fixed()
            
            # Step 1: Create token counter with proper fallback
            token_counter = None
            try:
                if OpenAITokenCounter and ModelType:
                    token_counter = OpenAITokenCounter(ModelType.GPT_4O_MINI)
                    logger.debug("✅ Created OpenAITokenCounter")
                else:
                    # Create fallback token counter
                    token_counter = OpenAITokenCounter("gpt-4o-mini")
                    logger.debug("✅ Created fallback OpenAITokenCounter")
            except Exception as e:
                logger.warning(f"Could not create OpenAITokenCounter: {e}")
                # Create minimal token counter
                class MinimalTokenCounter:
                    def __init__(self, model_type):
                        self.model_type = model_type
                    def count_tokens(self, text):
                        return len(str(text).split()) if text else 0
                token_counter = MinimalTokenCounter("gpt-4o-mini")
            
            # Step 2: Create context creator (REQUIRED for CAMEL 0.2.64)
            try:
                context_creator = ScoreBasedContextCreator(
                    token_counter=token_counter,
                    token_limit=token_limit,
                )
                logger.debug("✅ Created ScoreBasedContextCreator")
            except Exception as e:
                logger.error(f"Could not create ScoreBasedContextCreator: {e}")
                # This is critical for CAMEL 0.2.64, create minimal fallback
                class MinimalContextCreator:
                    def __init__(self, token_counter=None, token_limit=1024):
                        self.token_counter = token_counter
                        self.token_limit = token_limit
                    
                    def create_context(self, records):
                        """Create context from memory records - FIXED"""
                        try:
                            messages = []
                            total_tokens = 0
                            
                            if not records:
                                return messages, total_tokens
                                
                            # Process records into OpenAI format
                            for record in records[-10:]:  # Limit to last 10 records
                                try:
                                    if hasattr(record, 'message') and record.message:
                                        message = record.message
                                        
                                        # Determine role
                                        if hasattr(record, 'role_at_backend'):
                                            role = record.role_at_backend
                                            if role == "user":
                                                role = "user"
                                            else:
                                                role = "assistant"
                                        else:
                                            role = "assistant"
                                        
                                        # Get content
                                        content = ""
                                        if hasattr(message, 'content'):
                                            content = message.content
                                        elif isinstance(message, str):
                                            content = message
                                        else:
                                            content = str(message)
                                        
                                        if content and len(content.strip()) > 0:
                                            openai_message = {
                                                "role": role,
                                                "content": content.strip()
                                            }
                                            messages.append(openai_message)
                                            
                                            # Rough token estimation
                                            total_tokens += len(content.split()) * 1.3
                                            
                                            # Stop if we exceed token limit
                                            if total_tokens > self.token_limit:
                                                break
                                                
                                except Exception as e:
                                    logger.debug(f"Error processing record: {e}")
                                    continue
                            
                            return messages, int(total_tokens)
                            
                        except Exception as e:
                            logger.error(f"Error creating context: {e}")
                            return [], 0
                
                context_creator = MinimalContextCreator(token_counter, token_limit)
                logger.warning("Created minimal context creator fallback")
            
            # Step 3: Create chat history block
            try:
                chat_history_block = ChatHistoryBlock()
                logger.debug("✅ Created ChatHistoryBlock")
            except Exception as e:
                logger.warning(f"Could not create ChatHistoryBlock: {e}")
                chat_history_block = None
            
            # Step 4: Skip vector DB block to avoid embedding issues
            vector_db_block = None
            if enable_vector_db:
                try:
                    vector_db_block = VectorDBBlock()
                    logger.debug("✅ Created VectorDBBlock")
                except Exception as e:
                    logger.warning(f"Could not create VectorDBBlock: {e}")
                    vector_db_block = None
            
            # Step 5: Create LongtermAgentMemory with required context_creator
            memory = LongtermAgentMemory(
                context_creator=context_creator,  # This is REQUIRED
                chat_history_block=chat_history_block,
                vector_db_block=vector_db_block,
            )
            
            logger.info("✅ Created LongtermAgentMemory using CAMEL-AI 0.2.64 pattern")
            return memory
            
        except Exception as e:
            logger.error(f"❌ Error in CAMEL-AI 0.2.64 memory creation: {e}")
            return self._create_minimal_memory_fixed()
    
    def _create_minimal_memory_fixed(self) -> LongtermAgentMemory:
        """Create minimal fallback memory that properly satisfies CAMEL-AI 0.2.64 requirements."""
        try:
            # Create minimal components that satisfy the API requirements
            
            # Create minimal token counter
            class MinimalTokenCounter:
                def __init__(self, model_type="gpt-4o-mini"):
                    self.model_type = model_type
                
                def count_tokens(self, text):
                    return len(str(text).split()) if text else 0
            
            token_counter = MinimalTokenCounter()
            
            # Create minimal context creator (REQUIRED)
            class MinimalContextCreator:
                def __init__(self, token_counter=None, token_limit=1024):
                    self.token_counter = token_counter or MinimalTokenCounter()
                    self.token_limit = token_limit
                
                def create_context(self, records):
                    """Create context from memory records - FIXED"""
                    try:
                        messages = []
                        total_tokens = 0
                        
                        if not records:
                            return messages, total_tokens
                            
                        # Process records into OpenAI format
                        for record in records[-10:]:  # Limit to last 10 records
                            try:
                                if hasattr(record, 'message') and record.message:
                                    message = record.message
                                    
                                    # Determine role
                                    if hasattr(record, 'role_at_backend'):
                                        role = record.role_at_backend
                                        if role == "user":
                                            role = "user"
                                        else:
                                            role = "assistant"
                                    else:
                                        role = "assistant"
                                    
                                    # Get content
                                    content = ""
                                    if hasattr(message, 'content'):
                                        content = message.content
                                    elif isinstance(message, str):
                                        content = message
                                    else:
                                        content = str(message)
                                    
                                    if content and len(content.strip()) > 0:
                                        openai_message = {
                                            "role": role,
                                            "content": content.strip()
                                        }
                                        messages.append(openai_message)
                                        
                                        # Rough token estimation
                                        total_tokens += len(content.split()) * 1.3
                                        
                                        # Stop if we exceed token limit
                                        if total_tokens > self.token_limit:
                                            break
                                            
                            except Exception as e:
                                logger.debug(f"Error processing record: {e}")
                                continue
                        
                        return messages, int(total_tokens)
                        
                    except Exception as e:
                        logger.error(f"Error creating context: {e}")
                        return [], 0
            
            context_creator = MinimalContextCreator(token_counter, 1024)
            
            # Create minimal memory with required context_creator
            if CAMEL_MEMORIES_AVAILABLE:
                try:
                    memory = LongtermAgentMemory(context_creator=context_creator)
                    logger.info("✅ Created minimal CAMEL memory with required arguments")
                    return memory
                except Exception as e:
                    logger.warning(f"Minimal CAMEL memory failed: {e}")
            
            # Final fallback - create our own minimal implementation
            class MinimalMemory:
                def __init__(self):
                    self.records = []
                    self.context_creator = context_creator
                
                def write_records(self, records):
                    if isinstance(records, list):
                        self.records.extend(records)
                
                def get_context(self):
                    if self.context_creator and hasattr(self.context_creator, 'create_context'):
                        return self.context_creator.create_context(self.records)
                    
                    messages = []
                    for record in self.records:
                        if hasattr(record, 'message') and hasattr(record.message, 'content'):
                            role = "user" if hasattr(record, 'role_at_backend') and record.role_at_backend == "user" else "assistant"
                            messages.append({
                                "role": role,
                                "content": record.message.content
                            })
                    return messages, len(str(messages))
            
            memory = MinimalMemory()
            logger.info("✅ Created absolute minimal memory fallback")
            return memory
            
        except Exception as e:
            logger.error(f"❌ Even minimal memory creation failed: {e}")
            
            # Absolute last resort
            class EmptyMemory:
                def __init__(self):
                    self.records = []
                
                def write_records(self, records):
                    pass
                
                def get_context(self):
                    return [], 0
            
            return EmptyMemory()
    
    # EXACT FIX FROM PASTE.TXT - Replace add_message method
    async def add_message(
        self,
        memory: LongtermAgentMemory,
        content: str,
        role: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add message with FIXED validation and error handling."""
        try:
            # FIXED: Validate content before processing
            if not content or not isinstance(content, str):
                logger.warning(f"Invalid content for memory: {content}")
                return False
                
            content = content.strip()
            if len(content) == 0:
                logger.warning("Empty content after stripping, skipping")
                return False
            
            # FIXED: Validate memory state
            if not memory:
                logger.warning("Memory is None, cannot add message")
                return False
            
            # Create message using EXACT CAMEL-AI pattern
            if role.lower() == "user":
                message = BaseMessage.make_user_message(
                    role_name="User",
                    content=content,
                    meta_dict=metadata
                )
                backend_role = "user"
            else:
                message = BaseMessage.make_assistant_message(
                    role_name="Assistant", 
                    content=content,
                    meta_dict=metadata
                )
                backend_role = "assistant"
            
            # FIXED: Validate message creation
            if not message or not hasattr(message, 'content'):
                logger.error("Failed to create valid message object")
                return False
            
            # Create memory record
            record = MemoryRecord(
                message=message,
                role_at_backend=backend_role,
            )
            
            # FIXED: Validate memory has write_records method
            if not hasattr(memory, 'write_records'):
                logger.error("Memory object missing write_records method")
                return False
            
            # Write to memory with timeout protection
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(memory.write_records, [record]),
                    timeout=5.0
                )
                logger.debug(f"✅ Added {role} message to memory")
                return True
            except asyncio.TimeoutError:
                logger.warning("Memory write operation timed out")
                return False
            except Exception as write_error:
                logger.error(f"Error writing to memory: {write_error}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error adding message to memory: {e}")
            return False
    
    # EXACT FIX FROM PASTE.TXT - Add _create_fallback_product_response method
    def _create_fallback_product_response(self, products: List[Dict[str, Any]]) -> str:
        """Create a fallback response when agent fails"""
        if products:
            response_parts = ["Based on what you're looking for, I'd recommend these options:"]
            
            for idx, product in enumerate(products[:3], 1):  # Limit to 3 for readability
                title = product.get('title', 'Stylish item')
                price = product.get('price', 0)
                response_parts.append(f"• {title} - ${price:.2f}")
            
            response_parts.append("Would any of these work for you?")
            return "\n\n".join(response_parts)
        else:
            return ("I'd be happy to help you find the perfect outfit! "
                    "Could you tell me more about what style or occasion you're shopping for?")
    
    async def get_context(
        self,
        memory: LongtermAgentMemory,
        query: Optional[str] = None
    ) -> Tuple[List[Dict[str, str]], int]:
        """Get context using CAMEL-AI 0.2.64 exact API pattern."""
        try:
            # Use timeout to prevent hanging
            result = await asyncio.wait_for(
                asyncio.to_thread(self._get_context_safe, memory),
                timeout=10.0
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning("Memory context retrieval timed out")
            return [], 0
        except Exception as e:
            logger.error(f"❌ Error getting context: {e}")
            return [], 0
    
    def _get_context_safe(self, memory):
        """Safely get context from memory"""
        try:
            if hasattr(memory, 'get_context') and callable(memory.get_context):
                # Try the normal CAMEL way first
                context, token_count = memory.get_context()
                
                # Process context into expected format
                messages = []
                if context:
                    for msg in context:
                        if isinstance(msg, dict):
                            messages.append(msg)
                        else:
                            # Convert from CAMEL format
                            try:
                                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                                    messages.append({
                                        "role": msg.role,
                                        "content": msg.content
                                    })
                                elif hasattr(msg, 'role_name') and hasattr(msg, 'content'):
                                    role = msg.role_name.lower()
                                    if role not in ["user", "assistant", "system"]:
                                        role = "user" if "user" in role.lower() else "assistant"
                                    messages.append({
                                        "role": role,
                                        "content": msg.content
                                    })
                            except Exception as e:
                                logger.warning(f"Could not process message: {e}")
                
                return messages, token_count
            else:
                # Fallback to manual context creation
                if hasattr(memory, 'records') and memory.records:
                    context_creator = getattr(memory, 'context_creator', None)
                    if context_creator and hasattr(context_creator, 'create_context'):
                        return context_creator.create_context(memory.records)
                    else:
                        # Manual fallback
                        messages = []
                        for record in memory.records[-10:]:  # Last 10 records
                            if hasattr(record, 'message') and hasattr(record.message, 'content'):
                                role = "user" if hasattr(record, 'role_at_backend') and record.role_at_backend == "user" else "assistant"
                                messages.append({
                                    "role": role,
                                    "content": record.message.content
                                })
                        return messages, len(str(messages))
                
                return [], 0
                
        except Exception as e:
            logger.error(f"Error in _get_context_safe: {e}")
            return [], 0
    
    async def save_memory(self, memory: LongtermAgentMemory, user_id: str) -> bool:
        """Save memory with improved error handling."""
        if not self.neo4j_client:
            logger.debug("No Neo4j client available for persistence")
            return True
        
        try:
            memory_data = await asyncio.wait_for(
                self._serialize_memory(memory),
                timeout=10.0
            )
            
            query = """
            MERGE (u:User {id: $user_id})
            CREATE (m:MemoryState {
                id: $memory_id,
                type: 'camel_064_fixed',
                data: $data,
                created_at: $created_at,
                version: '0.2.64'
            })
            CREATE (u)-[:HAS_MEMORY]->(m)
            
            // Clean up old memory states (keep last 3)
            WITH u
            MATCH (u)-[:HAS_MEMORY]->(old:MemoryState)
            WITH old ORDER BY old.created_at DESC SKIP 3
            DETACH DELETE old
            """
            
            result = await asyncio.wait_for(
                self.neo4j_client.query(query, {
                    "user_id": user_id,
                    "memory_id": str(uuid.uuid4()),
                    "data": json.dumps(memory_data),
                    "created_at": datetime.datetime.now().isoformat()
                }),
                timeout=10.0
            )
            
            logger.debug(f"✅ Saved memory for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving memory: {e}")
            return False
    
    async def add_product_interaction(
        self,
        memory: LongtermAgentMemory,
        product: Dict[str, Any],
        interaction_type: str,
        user_id: Optional[str] = None
    ) -> bool:
        """Add product interaction using CAMEL-AI 0.2.64 pattern."""
        content = f"User {interaction_type} product {product.get('title')} (ID: {product.get('id')})."
        
        return await self.add_message(
            memory=memory,
            content=content,
            role="system",
            metadata={
                "type": "product_interaction",
                "interaction_type": interaction_type,
                "product_id": product.get("id"),
                "product_data": product,
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
    
    async def add_preference(
        self,
        memory: LongtermAgentMemory,
        preference_type: str,
        preference_value: Any,
        user_id: Optional[str] = None
    ) -> bool:
        """Add user preference using CAMEL-AI 0.2.64 pattern."""
        content = f"User preference: {preference_type} = {preference_value}"
        
        return await self.add_message(
            memory=memory,
            content=content,
            role="system",
            metadata={
                "type": "user_preference",
                "preference_type": preference_type,
                "preference_value": preference_value,
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
    
    async def _serialize_memory(self, memory: LongtermAgentMemory) -> Dict[str, Any]:
        """Serialize memory for storage."""
        try:
            context, token_count = await self.get_context(memory)
            
            return {
                "context": context,
                "token_count": token_count,
                "serialized_at": datetime.datetime.now().isoformat(),
                "version": "0.2.64-fixed"
            }
        except Exception as e:
            logger.error(f"❌ Error serializing memory: {e}")
            return {
                "context": [],
                "token_count": 0,
                "serialized_at": datetime.datetime.now().isoformat(),
                "version": "0.2.64-fixed",
                "error": str(e)
            }
    
    async def _load_memory_from_neo4j(self, user_id: str) -> Optional[LongtermAgentMemory]:
        """Load memory from Neo4j."""
        try:
            query = """
            MATCH (u:User {id: $user_id})-[:HAS_MEMORY]->(m:MemoryState)
            WHERE m.type = 'camel_064_fixed' OR m.type = 'camel_064_complete' OR m.type = 'camel_v2_fixed' OR m.type = 'camel_v2'
            RETURN m.data as data
            ORDER BY m.created_at DESC
            LIMIT 1
            """
            
            result = await asyncio.wait_for(
                self.neo4j_client.query(query, {"user_id": user_id}),
                timeout=10.0
            )
            
            if result and result[0].get("data"):
                memory_data = json.loads(result[0]["data"])
                return await self._deserialize_memory(memory_data, user_id)
                
        except Exception as e:
            logger.error(f"❌ Error loading memory from Neo4j: {e}")
            
        return None
    
    async def _deserialize_memory(self, data: Dict[str, Any], user_id: str) -> LongtermAgentMemory:
        """Deserialize memory from stored data."""
        try:
            memory = await self.create_memory(user_id=user_id)
            
            context = data.get("context", [])
            for msg_data in context[:10]:  # Limit to prevent overwhelming memory
                try:
                    role = msg_data.get("role", "user")
                    content = msg_data.get("content", "")
                    if content:
                        await asyncio.wait_for(
                            self.add_message(memory=memory, content=content, role=role),
                            timeout=2.0
                        )
                except Exception as e:
                    logger.warning(f"Could not restore message: {e}")
            
            return memory
            
        except Exception as e:
            logger.error(f"❌ Error deserializing memory: {e}")
            return await self.create_memory(user_id=user_id)


# ALL BACKWARD COMPATIBILITY FUNCTIONS - with fixed implementations

async def setup_stylist_memory_async(
    model_type=None,
    token_limit: int = 1024,
    user_id: Optional[str] = None,
    neo4j_client=None
) -> LongtermAgentMemory:
    """Backward compatible memory setup using CAMEL-AI 0.2.64."""
    manager = MemoryManager(neo4j_client)
    return await manager.create_memory(
        user_id=user_id,
        token_limit=token_limit,
        enable_mcp=True
    )

async def add_message_to_memory_async(
    memory: LongtermAgentMemory,
    content: str,
    sender: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Backward compatible message addition."""
    manager = MemoryManager()
    return await manager.add_message(
        memory=memory,
        content=content,
        role=sender,
        metadata=metadata
    )

async def get_memory_context_async(
    memory: LongtermAgentMemory
) -> Tuple[List[Dict[str, str]], int]:
    """Backward compatible context retrieval."""
    manager = MemoryManager()
    return await manager.get_context(memory)

async def save_memory_for_user_async(
    memory: LongtermAgentMemory,
    user_id: str,
    neo4j_client
) -> bool:
    """Backward compatible memory saving."""
    manager = MemoryManager(neo4j_client)
    return await manager.save_memory(memory, user_id)

async def add_product_interaction_to_memory_async(
    memory: LongtermAgentMemory,
    product: Dict[str, Any],
    interaction_type: str,
    user_id: Optional[str] = None
) -> bool:
    """Add product interaction using CAMEL-AI 0.2.64."""
    manager = MemoryManager()
    return await manager.add_product_interaction(
        memory=memory,
        product=product,
        interaction_type=interaction_type,
        user_id=user_id
    )

async def add_user_preference_to_memory_async(
    memory: LongtermAgentMemory,
    preference_type: str,
    preference_value: Any,
    user_id: Optional[str] = None
) -> bool:
    """Add user preference using CAMEL-AI 0.2.64."""
    manager = MemoryManager()
    return await manager.add_preference(
        memory=memory,
        preference_type=preference_type,
        preference_value=preference_value,
        user_id=user_id
    )

async def extract_preferences_from_memory_async(
    memory: LongtermAgentMemory
) -> Dict[str, Any]:
    """Extract preferences from memory using CAMEL-AI 0.2.64."""
    try:
        manager = MemoryManager()
        context, _ = await manager.get_context(memory)
        
        preferences = {}
        for msg in context:
            content = msg.get("content", "")
            if "preference:" in content.lower():
                try:
                    parts = content.split("preference: ")[1].split(" = ")
                    if len(parts) == 2:
                        pref_type = parts[0].strip()
                        pref_value = parts[1].strip()
                        preferences[pref_type] = pref_value
                except Exception as e:
                    logger.warning(f"Could not parse preference: {e}")
        
        return preferences
        
    except Exception as e:
        logger.error(f"❌ Error extracting preferences: {e}")
        return {}

async def optimize_memory_async(
    memory: LongtermAgentMemory,
    user_id: str,
    neo4j_client
) -> bool:
    """Optimize memory using CAMEL-AI 0.2.64."""
    try:
        manager = MemoryManager(neo4j_client)
        success = await manager.save_memory(memory, user_id)
        
        if success:
            logger.info(f"✅ Optimized memory for user {user_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error optimizing memory: {e}")
        return False


logger.info("✅ FIXED CAMEL-AI 0.2.64 Compatible Memory Integration loaded successfully")