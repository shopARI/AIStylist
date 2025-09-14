"""
CAMEL VectorDB Integration - Long-term semantic memory
Leverages CAMEL 0.2.7 vector memory capabilities for intelligent context retrieval
"""

import logging
import time
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger("services.memory.camel_vector_memory")

try:
    # CAMEL 0.2.7 vector memory imports
    from camel.memories import VectorDBMemory
    from camel.memories.records import MemoryRecord
    from camel.embeddings import OpenAIEmbedding
    from camel.types import EmbeddingModelType
    CAMEL_AVAILABLE = True
    logger.info("CAMEL vector memory components imported successfully")
except ImportError as e:
    CAMEL_AVAILABLE = False
    logger.warning(f"CAMEL vector memory not available: {e}")

@dataclass
class ConversationContext:
    """Rich conversation context for vector storage"""
    session_id: str
    user_id: str
    query: str
    intent: str
    extracted_params: Dict[str, Any]
    products_found: int
    user_satisfaction: Optional[float]  # If available from feedback
    timestamp: float
    metadata: Dict[str, Any]

class CAMELVectorMemory:
    """
    Semantic long-term memory using CAMEL's VectorDB capabilities.
    Stores and retrieves conversation contexts based on semantic similarity.
    """
    
    def __init__(
        self,
        redis_client,
        embedding_model: str = "text-embedding-3-small",
        max_contexts_per_query: int = 5,
        similarity_threshold: float = 0.7,
        enable_vector_storage: bool = True
    ):
        self.redis = redis_client
        self.embedding_model = embedding_model
        self.max_contexts = max_contexts_per_query
        self.similarity_threshold = similarity_threshold
        
        # Initialize CAMEL components if available
        self.vector_memory = None
        self.embedding_model_instance = None
        
        if CAMEL_AVAILABLE and enable_vector_storage:
            self._initialize_camel_vector_memory()
        else:
            logger.warning("CAMEL vector memory disabled - falling back to Redis-only storage")
    
    def _initialize_camel_vector_memory(self):
        """Initialize CAMEL VectorDB memory components"""
        try:
            # Initialize embedding model
            self.embedding_model_instance = OpenAIEmbedding(
                model_type=EmbeddingModelType.TEXT_EMBEDDING_3_SMALL
            )
            
            # Initialize VectorDB memory
            # Note: This may require additional configuration for the vector store backend
            # You might need to configure the specific vector store (e.g., Pinecone, Weaviate, etc.)
            self.vector_memory = VectorDBMemory(
                embedding_model=self.embedding_model_instance,
                dimensions=1536,  # text-embedding-3-small dimensions
                top_k=self.max_contexts
            )
            
            logger.info("CAMEL VectorDB memory initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CAMEL vector memory: {e}")
            self.vector_memory = None
            self.embedding_model_instance = None
    
    async def store_conversation_context(
        self,
        context: ConversationContext
    ) -> bool:
        """
        Store conversation context in both vector memory and Redis.
        Vector memory enables semantic retrieval, Redis provides fast access.
        """
        try:
            # Create searchable text representation
            searchable_text = self._create_searchable_text(context)
            
            # Store in CAMEL VectorDB if available
            vector_stored = False
            if self.vector_memory:
                try:
                    # Create memory record for CAMEL
                    record = MemoryRecord(
                        message=searchable_text,
                        embedding=None,  # Will be generated automatically
                        metadata={
                            'session_id': context.session_id,
                            'user_id': context.user_id,
                            'intent': context.intent,
                            'timestamp': context.timestamp,
                            'products_found': context.products_found,
                            'params': json.dumps(context.extracted_params),
                            'satisfaction': context.user_satisfaction
                        }
                    )
                    
                    # Store in vector memory
                    await self.vector_memory.write_records([record])
                    vector_stored = True
                    logger.debug(f"Stored context in CAMEL VectorDB for session {context.session_id}")
                    
                except Exception as e:
                    logger.warning(f"Failed to store in CAMEL VectorDB: {e}")
            
            # Always store in Redis as backup/fast access
            context_key = f"vector_context:{context.session_id}:{time.time()}"
            await self.redis.set_json(
                context_key,
                asdict(context),
                ttl=90 * 24 * 3600  # 90 days
            )
            
            # Add to user's context index
            user_index_key = f"user_contexts:{context.user_id}"
            await self.redis.client.zadd(
                user_index_key,
                {context_key: context.timestamp}
            )
            await self.redis.client.expire(user_index_key, 90 * 24 * 3600)
            
            logger.info(f"Stored conversation context (vector: {vector_stored}, redis: True)")
            return True
            
        except Exception as e:
            logger.error(f"Error storing conversation context: {e}")
            return False
    
    async def retrieve_relevant_contexts(
        self,
        query: str,
        user_id: str,
        intent: Optional[str] = None,
        limit: int = None
    ) -> List[ConversationContext]:
        """
        Retrieve semantically similar conversation contexts.
        Uses CAMEL VectorDB for semantic search, falls back to Redis keyword search.
        """
        limit = limit or self.max_contexts
        contexts = []
        
        try:
            # Try CAMEL VectorDB semantic search first
            if self.vector_memory:
                try:
                    # Search for similar contexts
                    similar_records = await self.vector_memory.query(
                        query=query,
                        top_k=limit,
                        score_threshold=self.similarity_threshold
                    )
                    
                    for record in similar_records:
                        # Reconstruct context from metadata
                        metadata = record.metadata
                        if metadata.get('user_id') == user_id:  # Only return user's own contexts
                            try:
                                context = ConversationContext(
                                    session_id=metadata['session_id'],
                                    user_id=metadata['user_id'],
                                    query=record.message.split('|')[0] if '|' in record.message else record.message,
                                    intent=metadata['intent'],
                                    extracted_params=json.loads(metadata.get('params', '{}')),
                                    products_found=metadata.get('products_found', 0),
                                    user_satisfaction=metadata.get('satisfaction'),
                                    timestamp=metadata['timestamp'],
                                    metadata={'similarity_score': record.score}
                                )
                                contexts.append(context)
                            except Exception as e:
                                logger.warning(f"Failed to reconstruct context from vector record: {e}")
                    
                    if contexts:
                        logger.info(f"Retrieved {len(contexts)} contexts from CAMEL VectorDB")
                        return contexts[:limit]
                        
                except Exception as e:
                    logger.warning(f"CAMEL VectorDB search failed: {e}")
            
            # Fallback to Redis-based search
            contexts = await self._redis_context_search(query, user_id, intent, limit)
            logger.info(f"Retrieved {len(contexts)} contexts from Redis fallback")
            return contexts
            
        except Exception as e:
            logger.error(f"Error retrieving contexts: {e}")
            return []
    
    async def get_user_conversation_patterns(
        self,
        user_id: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze user conversation patterns from stored contexts.
        Useful for understanding user behavior and preferences.
        """
        try:
            cutoff_time = time.time() - (days_back * 24 * 3600)
            user_index_key = f"user_contexts:{user_id}"
            
            # Get recent context keys from Redis
            context_keys = await self.redis.client.zrangebyscore(
                user_index_key,
                cutoff_time,
                '+inf',
                withscores=True
            )
            
            if not context_keys:
                return {}
            
            patterns = {
                'total_conversations': len(context_keys),
                'intent_distribution': {},
                'avg_products_per_query': 0,
                'parameter_patterns': {},
                'satisfaction_trend': [],
                'query_topics': []
            }
            
            total_products = 0
            satisfactions = []
            
            # Analyze each context
            for context_key, timestamp in context_keys:
                try:
                    context_data = await self.redis.get_json(context_key)
                    if not context_data:
                        continue
                    
                    context = ConversationContext(**context_data)
                    
                    # Intent distribution
                    intent = context.intent
                    patterns['intent_distribution'][intent] = patterns['intent_distribution'].get(intent, 0) + 1
                    
                    # Products found
                    total_products += context.products_found
                    
                    # User satisfaction
                    if context.user_satisfaction is not None:
                        satisfactions.append({
                            'timestamp': context.timestamp,
                            'satisfaction': context.user_satisfaction
                        })
                    
                    # Parameter patterns
                    for param, values in context.extracted_params.items():
                        if param not in patterns['parameter_patterns']:
                            patterns['parameter_patterns'][param] = {}
                        
                        if isinstance(values, list):
                            for value in values:
                                if isinstance(value, str):
                                    patterns['parameter_patterns'][param][value] = \
                                        patterns['parameter_patterns'][param].get(value, 0) + 1
                        elif isinstance(values, str):
                            patterns['parameter_patterns'][param][values] = \
                                patterns['parameter_patterns'][param].get(values, 0) + 1
                    
                    # Query topics (simple keyword extraction)
                    query_words = context.query.lower().split()
                    for word in query_words:
                        if len(word) > 3:  # Skip short words
                            patterns['query_topics'].append(word)
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze context {context_key}: {e}")
            
            # Calculate averages and trends
            if patterns['total_conversations'] > 0:
                patterns['avg_products_per_query'] = total_products / patterns['total_conversations']
            
            patterns['satisfaction_trend'] = sorted(satisfactions, key=lambda x: x['timestamp'])
            
            # Get most common query topics
            from collections import Counter
            topic_counter = Counter(patterns['query_topics'])
            patterns['query_topics'] = dict(topic_counter.most_common(10))
            
            logger.info(f"Analyzed patterns for user {user_id}: {patterns['total_conversations']} conversations")
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing user patterns: {e}")
            return {}
    
    def _create_searchable_text(self, context: ConversationContext) -> str:
        """Create searchable text representation for vector embedding"""
        parts = [
            f"Query: {context.query}",
            f"Intent: {context.intent}",
        ]
        
        # Add parameters
        if context.extracted_params:
            param_parts = []
            for key, values in context.extracted_params.items():
                if isinstance(values, list):
                    param_parts.append(f"{key}: {', '.join(str(v) for v in values)}")
                else:
                    param_parts.append(f"{key}: {values}")
            
            if param_parts:
                parts.append(f"Parameters: {'; '.join(param_parts)}")
        
        # Add result context
        parts.append(f"Products found: {context.products_found}")
        
        # Add satisfaction if available
        if context.user_satisfaction is not None:
            parts.append(f"User satisfaction: {context.user_satisfaction}")
        
        return " | ".join(parts)
    
    async def _redis_context_search(
        self,
        query: str,
        user_id: str,
        intent: Optional[str],
        limit: int
    ) -> List[ConversationContext]:
        """Fallback Redis-based context search using keywords"""
        try:
            user_index_key = f"user_contexts:{user_id}"
            
            # Get recent context keys
            context_keys = await self.redis.client.zrevrange(user_index_key, 0, 50)  # Last 50 contexts
            
            contexts = []
            query_words = set(query.lower().split())
            
            for context_key in context_keys:
                try:
                    context_data = await self.redis.get_json(context_key)
                    if not context_data:
                        continue
                    
                    context = ConversationContext(**context_data)
                    
                    # Simple keyword matching score
                    score = 0
                    context_text = (context.query + " " + context.intent).lower()
                    context_words = set(context_text.split())
                    
                    # Calculate overlap
                    overlap = query_words.intersection(context_words)
                    if overlap:
                        score = len(overlap) / len(query_words)
                    
                    # Intent bonus
                    if intent and context.intent == intent:
                        score += 0.3
                    
                    # Add score to metadata and include if above threshold
                    if score >= 0.3:  # Minimum keyword overlap
                        context.metadata = context.metadata or {}
                        context.metadata['similarity_score'] = score
                        contexts.append(context)
                
                except Exception as e:
                    logger.warning(f"Failed to process context {context_key}: {e}")
            
            # Sort by similarity score and return top results
            contexts.sort(key=lambda x: x.metadata.get('similarity_score', 0), reverse=True)
            return contexts[:limit]
            
        except Exception as e:
            logger.error(f"Redis context search failed: {e}")
            return []

# Global instance
_vector_memory = None

def get_camel_vector_memory(redis_client) -> CAMELVectorMemory:
    """Get or create the global CAMEL vector memory instance"""
    global _vector_memory
    if _vector_memory is None:
        _vector_memory = CAMELVectorMemory(redis_client)
    return _vector_memory