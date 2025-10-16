# Migration Plan: CAMEL-AI to AutoGen

## Executive Summary

This document outlines a technical migration strategy for transitioning the ARI Production fashion recommendation system from CAMEL-AI (v0.2.7) to Microsoft AutoGen framework. The migration transforms custom battle orchestration into conversation-driven multi-agent collaboration while preserving agent intelligence and integrating with existing Redis-based production infrastructure.

**Current System**: Multi-agent battle orchestration using CAMEL-AI primitives with custom coordination logic, parallel agent execution, and Redis state management for specialized fashion recommendation agents.

**Target System**: AutoGen framework leveraging multi-agent conversation patterns, group chat coordination, flexible agent communication, function calling for tool integration, and extensible architecture while maintaining Redis, Neo4j, and Qdrant integrations.

**Migration Approach**: Transform battle pattern into conversational group chat, convert agents to ConversableAgent instances, implement function calling for backend integration, and adopt AutoGen conversation patterns for coordination.

**Note**: AutoGen v0.4 (2025) represents a major architectural evolution. Microsoft now recommends Microsoft Agent Framework for new projects, though AutoGen continues receiving maintenance and critical updates. This migration plan considers AutoGen as a transitional or alternative path.

---

## Current Architecture Analysis

### System Overview

**Agent Layer**
- CypherBot: Graph database specialist executing LLM-powered semantic Cypher queries against Neo4j product graph
- VibeBot: Vector search specialist using Qdrant for semantic similarity and visual aesthetic matching
- VisionBot: Visual similarity specialist using FashionSigLIP embeddings for image-based product discovery
- JudgeAri: Product evaluator implementing quality control, conscious rejection, consensus detection, and learning from judgment history

**CAMEL-AI Integration Patterns**
- ModelFactory for model instantiation with platform and type specification
- ChatAgent wrapping with BaseMessage system for structured communication
- ChatHistoryMemory with ScoreBasedContextCreator for token-based context management
- RolePlaying society for collaborative judgment between Fashion Judge and Battle Evaluator
- Agent step execution pattern with response extraction from nested attributes
- Memory integration through explicit context loading and storage

**Orchestration Pattern**
- BattleOrchestrator coordinates agent lifecycle, caching, and optimization
- BattleExecutor runs agents in parallel using asyncio.gather for concurrent execution
- Results aggregated after all agents complete
- JudgeAri evaluates aggregated results and selects winning products
- Fixed parallel execution without dynamic conversation flow

**Current Workflow**
1. Intelligence generation creates ML context for agents
2. CypherBot, VibeBot, VisionBot execute in parallel
3. JudgeAri evaluates all results simultaneously
4. Quality control filters and ranks products
5. Final products returned to user

### Architectural Strengths

**Sophisticated Agent Intelligence**
- Semantic query expansion with LLM-generated synonyms and context understanding
- Conscious quality control rejecting irrelevant products with detailed reasoning
- Learning system analyzing judgment history for strategy optimization
- Independent quality assessment ignoring agent biases

**Production Infrastructure**
- Redis-backed caching reducing database load
- Distributed state management enabling horizontal scaling
- Comprehensive metrics for observability
- Graceful degradation with fallback mechanisms

### Architectural Weaknesses

**Rigid Coordination**
- Fixed parallel execution pattern without conversation flow
- No dynamic interaction between agents during search
- Cannot implement iterative refinement through dialogue
- Adding new interaction patterns requires orchestrator modification

**One-Way Communication**
- Search agents cannot communicate with each other
- Judge receives results but cannot request clarification
- No negotiation or collaborative problem-solving
- Results merged only at final stage without iteration

---

## AutoGen Architecture Overview

### Core Architectural Components

**Agent Hierarchy**

ConversableAgent Base Class:
- Foundation for all AutoGen agents
- Message sending and receiving capabilities
- Conversation initiation and termination logic
- Reply function registration for custom behaviors
- Human-in-the-loop integration support

AssistantAgent:
- LLM-powered agent for task execution
- System message configuration for role definition
- Tool/function calling capabilities
- Code generation and reasoning
- Extends ConversableAgent

UserProxyAgent:
- Represents user or executes code
- Code execution in isolated environments
- Human input solicitation
- Function execution coordination
- Safety and validation

**Multi-Agent Conversation Patterns**

Two-Agent Chat:
- Direct conversation between two agents
- Sequential message exchange
- Simple coordination pattern
- Clear termination conditions

Group Chat:
- Multiple agents in shared conversation
- GroupChatManager coordinates speakers
- Dynamic speaker selection strategies
- Flexible participation rules

Nested Chat:
- Agents initiate sub-conversations
- Hierarchical problem decomposition
- Context preservation across levels
- Parallel nested conversations

Sequential Chat:
- Agents converse in sequence
- Output chaining from one to next
- Pipeline processing pattern
- Explicit handoff points

**Function Calling and Tools**

Function Registration:
- Agents register callable functions
- LLM generates function call requests
- Agent executes function and returns result
- Automatic parameter extraction from conversation

Tool Definition:
- Decorator-based function registration
- Schema generation for function signatures
- Type hints for parameter validation
- Return value formatting

Code Execution:
- UserProxyAgent executes generated code
- Isolated execution environments (Docker, local)
- Code validation and safety checks
- Output capture and formatting

**Conversation Control**

Max Consecutive Auto Reply:
- Limit autonomous conversation length
- Prevent infinite loops
- Force human intervention at thresholds
- Configurable per agent

Termination Conditions:
- Message content matching patterns
- Max turns reached
- Explicit termination signals
- Custom termination functions

Speaker Selection:
- Round robin for equal participation
- Random selection for diversity
- LLM-based selection for intelligence
- Custom selection functions
- State machine constraints

**Memory and State**

Conversation History:
- Automatic message history tracking
- Context window management
- History pruning strategies
- Shared context across agents

Agent State:
- Stateful agents with memory
- State persistence across conversations
- State sharing mechanisms
- Reset and initialization

### AutoGen v0.4 Architecture (2025)

**Layered Design**

Core API:
- Event-driven agent framework
- Message passing primitives
- Local and distributed runtime
- Flexible and powerful foundation

AgentChat API:
- Simplified conversation API
- Built on Core API
- Common multi-agent patterns
- Rapid prototyping focus

Extensions API:
- First-party and third-party extensions
- LLM client integrations
- Capability expansions
- Modular extensibility

**Key Improvements**

Modularity:
- Clear separation of concerns
- Pluggable components
- Independent versioning
- Easier testing and maintenance

Stability:
- Robust error handling
- Backward compatibility considerations
- Production-grade reliability
- Comprehensive testing

Flexibility:
- Multiple programming patterns
- Extensible architecture
- Custom agent implementations
- Integration capabilities

### AutoGen vs Microsoft Agent Framework

**Relationship**

Microsoft now recommends Microsoft Agent Framework for new projects while maintaining AutoGen for existing users and specific use cases. AutoGen receives bug fixes and critical security patches.

**AutoGen Strengths**
- Mature framework with extensive examples
- Rich conversation patterns proven in research
- Large community and extensive documentation
- Flexible agent communication models
- Strong code execution capabilities

**Migration Consideration**

This migration plan focuses on AutoGen but teams should evaluate Microsoft Agent Framework as well. AutoGen remains viable for:
- Projects requiring specific AutoGen patterns
- Teams with AutoGen expertise
- Use cases emphasizing conversation-driven coordination
- Research and experimentation scenarios

---

## Component Mapping Strategy

### Agent Migration

**CAMEL ChatAgent to AutoGen ConversableAgent**

Current CAMEL Pattern:
```python
model = ModelFactory.create(
    model_platform=ModelPlatformType.DEFAULT,
    model_type=ModelType.GPT_4O,
    model_config_dict={"temperature": 0.7, "max_tokens": 2000}
)
self.agent = ChatAgent(
    system_message=BaseMessage.make_assistant_message(
        role_name="Graph Database Specialist",
        content=CYPHER_BOT_PROMPT
    ),
    model=model
)
```

AutoGen Pattern:
```python
from autogen import AssistantAgent

cypher_bot = AssistantAgent(
    name="CypherBot",
    system_message=CYPHER_BOT_PROMPT,
    llm_config={
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 2000,
        "functions": [neo4j_query_function, semantic_expansion_function]
    },
    max_consecutive_auto_reply=10,
    human_input_mode="NEVER"
)
```

**Agent Migration Strategy for Each Agent**

CypherBot to AutoGen AssistantAgent:
- System message from CYPHER_BOT_PROMPT
- Function registration for Neo4j query execution
- Semantic expansion function for query enhancement
- LLM config matching current model parameters
- Conversation capabilities for coordination

VibeBot to AutoGen AssistantAgent:
- System message from VIBE_BOT_PROMPT
- Function registration for Qdrant search
- Embedding generation function
- Visual analysis capabilities
- Aesthetic reasoning in conversation

VisionBot to AutoGen AssistantAgent:
- System message from VISION_BOT_PROMPT
- Function registration for FashionSigLIP embedding
- Image preprocessing function
- Visual similarity search function
- Multi-image handling capability

JudgeAri to AutoGen AssistantAgent:
- System message from JUDGE_ARI_PROMPT
- Function registration for quality scoring
- Consensus detection function
- Learning analysis function
- Conversation-based judgment coordination

### Orchestration Migration

**BattleOrchestrator to GroupChat Pattern**

Current Pattern:
```python
battle_results = await asyncio.gather(
    cypher_bot.search(query, limit, filters, ml_intelligence),
    vibe_bot.search(query, limit, filters, ml_intelligence),
    vision_bot.search(query, limit, ml_intelligence)
)
judgment = await judge.evaluate(
    battle_results[0], battle_results[1], query, ml_context
)
```

AutoGen GroupChat Pattern:
```python
from autogen import GroupChat, GroupChatManager

group_chat = GroupChat(
    agents=[cypher_bot, vibe_bot, vision_bot, judge_ari],
    messages=[],
    max_round=10,
    speaker_selection_method="auto"
)

manager = GroupChatManager(
    groupchat=group_chat,
    llm_config={
        "model": "gpt-4o",
        "temperature": 0.6
    }
)

# Initiate group discussion
judge_ari.initiate_chat(
    manager,
    message=f"Find products for query: {query}. "
           f"CypherBot, VibeBot, VisionBot: search your databases. "
           f"Report findings and I will evaluate."
)
```

**Conversation Flow Options**

Option 1: Manager-Coordinated Group Chat
- GroupChatManager coordinates conversation
- Agents speak in turns about findings
- Judge requests clarification if needed
- Iterative refinement through dialogue

Option 2: Sequential Chat Chain
- CypherBot finds products and reports
- VibeBot searches based on CypherBot context
- VisionBot searches based on previous findings
- Judge evaluates complete context

Option 3: Nested Chat
- Judge initiates sub-conversations with each agent
- Parallel information gathering
- Context aggregation at judge level
- Final evaluation after all sub-conversations

**Recommended Approach**: Manager-Coordinated Group Chat for flexibility and dynamic interaction.

### Function Registration

**CAMEL Method Calls to AutoGen Functions**

Current Pattern:
```python
async def _execute_neo4j_query(self, cypher: str, parameters: dict):
    async with self.driver.session() as session:
        result = await session.run(cypher, parameters)
        return [record.data() for record in result]
```

AutoGen Function Pattern:
```python
def neo4j_query_function(cypher: str, parameters: dict = None) -> list:
    """
    Execute Cypher query against Neo4j product graph.

    Args:
        cypher: Cypher query string
        parameters: Optional query parameters

    Returns:
        List of product records from graph database
    """
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(cypher, parameters or {})
        return [record.data() for record in result]

# Register with agent
cypher_bot.register_function(
    function_map={
        "neo4j_query": neo4j_query_function
    }
)
```

**Function Library**

Neo4j Functions:
```python
def neo4j_query_function(cypher: str, parameters: dict = None) -> list:
    """Execute Cypher query against product graph"""
    # Implementation

def semantic_expansion_function(query: str) -> dict:
    """Generate semantic expansions for query"""
    # Implementation

def fulltext_search_function(query: str, limit: int = 10) -> list:
    """Search Neo4j fulltext indexes"""
    # Implementation
```

Qdrant Functions:
```python
def qdrant_search_function(
    query_embedding: list,
    filters: dict = None,
    limit: int = 10
) -> list:
    """Search Qdrant vector database"""
    # Implementation

def generate_text_embedding_function(text: str) -> list:
    """Generate embedding for text query"""
    # Implementation

def generate_fashionsig_embedding_function(image_path: str) -> list:
    """Generate FashionSigLIP visual embedding"""
    # Implementation
```

Quality Functions:
```python
def quality_score_function(product: dict, query: str) -> dict:
    """Score product quality independently"""
    # Implementation

def consensus_detection_function(
    cypher_products: list,
    vibe_products: list,
    vision_products: list
) -> list:
    """Detect consensus products across agents"""
    # Implementation

def learning_analysis_function(judgment_history: list) -> dict:
    """Analyze judgment history for patterns"""
    # Implementation
```

Cache Functions:
```python
def cache_lookup_function(cache_key: str) -> dict:
    """Lookup results in Redis cache"""
    # Implementation

def cache_store_function(
    cache_key: str,
    data: dict,
    ttl: int = 180
) -> bool:
    """Store results in Redis cache"""
    # Implementation
```

### Memory Integration

**CAMEL ChatHistoryMemory to AutoGen Conversation History**

Current CAMEL Pattern:
```python
from camel.memories import ChatHistoryMemory

self.memory = ChatHistoryMemory(
    context_creator=ScoreBasedContextCreator(
        token_counter=token_counter,
        token_limit=4000
    ),
    window_size=20
)
```

AutoGen Built-in Pattern:
```python
# AutoGen automatically maintains conversation history
# Access via agent.chat_messages

# For custom memory management:
class RedisConversationMemory:
    def __init__(self, redis_client, session_id):
        self.redis = redis_client
        self.session_id = session_id

    def save_messages(self, messages):
        key = f"session:{self.session_id}:messages"
        self.redis.lpush(key, *[json.dumps(m) for m in messages])
        self.redis.ltrim(key, 0, 19)  # Keep last 20
        self.redis.expire(key, 3600)

    def load_messages(self):
        key = f"session:{self.session_id}:messages"
        messages = self.redis.lrange(key, 0, -1)
        return [json.loads(m) for m in messages]

# Integrate with agent
memory = RedisConversationMemory(redis_client, session_id)

# Restore context before conversation
previous_messages = memory.load_messages()
# Initialize group chat with previous messages
group_chat.messages = previous_messages

# Save after conversation
memory.save_messages(group_chat.messages)
```

---

## Detailed Migration Plan

### Phase 1: Function Library Development

**Objective**: Create AutoGen-compatible functions wrapping existing backend services for agent use through function calling.

**Neo4j Functions**

Implementation:
```python
from typing import Dict, List, Any, Optional
import os
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

def neo4j_query_function(
    cypher: str,
    parameters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Execute Cypher query against Neo4j product graph.

    Args:
        cypher: Cypher query string
        parameters: Optional parameters for query binding

    Returns:
        List of product records with properties and relationships
    """
    with driver.session() as session:
        result = session.run(cypher, parameters or {})
        return [record.data() for record in result]

def semantic_expansion_function(query: str) -> Dict[str, Any]:
    """
    Generate semantic expansions for search query.

    Args:
        query: Natural language search query

    Returns:
        Dictionary with synonyms, related terms, and categories
    """
    # Use LLM to generate semantic expansions
    from services.nlp.hybrid_intent_detector import HybridIntentDetector

    detector = HybridIntentDetector()
    expansions = detector.extract_semantic_expansions(query)

    return {
        "original_query": query,
        "synonyms": expansions.get("synonyms", []),
        "related_terms": expansions.get("related", []),
        "categories": expansions.get("categories", [])
    }
```

**Qdrant Functions**

Implementation:
```python
from qdrant_client import QdrantClient
from typing import List, Dict, Any, Optional

qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))

def qdrant_search_function(
    query_embedding: List[float],
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search Qdrant vector database for similar products.

    Args:
        query_embedding: Query vector embedding
        filters: Optional filters (category, price range, etc.)
        limit: Maximum number of results

    Returns:
        List of products with similarity scores
    """
    results = qdrant_client.search(
        collection_name="products",
        query_vector=query_embedding,
        query_filter=filters,
        limit=limit,
        with_payload=True
    )

    return [
        {
            "id": r.id,
            "score": r.score,
            **r.payload
        }
        for r in results
    ]

def generate_text_embedding_function(text: str) -> List[float]:
    """
    Generate embedding vector for text.

    Args:
        text: Text to embed

    Returns:
        Embedding vector as list of floats
    """
    # Use OpenAI embedding or custom model
    import openai

    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )

    return response.data[0].embedding
```

**FashionSigLIP Functions**

Implementation:
```python
def generate_fashionsig_embedding_function(
    image_path: str
) -> List[float]:
    """
    Generate FashionSigLIP visual embedding for image.

    Args:
        image_path: Path to product image

    Returns:
        Visual embedding vector
    """
    from services.ml.fashionsig_encoder import FashionSigLIPEncoder

    encoder = FashionSigLIPEncoder()
    embedding = encoder.encode_image(image_path)

    return embedding.tolist()
```

**Quality and Judgment Functions**

Implementation:
```python
def quality_score_function(
    product: Dict[str, Any],
    query: str
) -> Dict[str, Any]:
    """
    Calculate independent quality score for product.

    Args:
        product: Product data
        query: Search query for relevance assessment

    Returns:
        Quality assessment with score and factors
    """
    # Independent quality calculation
    score = 0.0
    factors = []

    # Completeness
    if product.get("title"):
        score += 0.15
        factors.append("Has title")
    if product.get("price", 0) > 0:
        score += 0.1
        factors.append("Has price")
    if product.get("images"):
        score += 0.1
        factors.append("Has images")

    # Query relevance
    query_terms = set(query.lower().split())
    title_lower = product.get("title", "").lower()
    matches = sum(1 for term in query_terms if term in title_lower)
    relevance_score = min(0.3, matches * 0.1)
    score += relevance_score
    factors.append(f"{matches} query term matches")

    # Commercial viability
    price = product.get("price", 0)
    if 5 <= price <= 500:
        score += 0.1
        factors.append("Reasonable price")

    return {
        "quality_score": min(score, 1.0),
        "factors": factors
    }

def consensus_detection_function(
    cypher_products: List[Dict],
    vibe_products: List[Dict],
    vision_products: List[Dict]
) -> List[Dict]:
    """
    Identify products found by multiple agents.

    Args:
        cypher_products: Products from CypherBot
        vibe_products: Products from VibeBot
        vision_products: Products from VisionBot

    Returns:
        Consensus products with source tracking
    """
    # Build product maps
    def get_key(p):
        return p.get("id") or p.get("title", "").lower().strip()

    cypher_map = {get_key(p): p for p in cypher_products}
    vibe_map = {get_key(p): p for p in vibe_products}
    vision_map = {get_key(p): p for p in vision_products}

    # Find consensus
    consensus = []
    all_keys = set(cypher_map.keys()) | set(vibe_map.keys()) | set(vision_map.keys())

    for key in all_keys:
        sources = []
        product = None

        if key in cypher_map:
            sources.append("CypherBot")
            product = cypher_map[key]
        if key in vibe_map:
            sources.append("VibeBot")
            product = product or vibe_map[key]
        if key in vision_map:
            sources.append("VisionBot")
            product = product or vision_map[key]

        if len(sources) >= 2:  # Consensus threshold
            consensus.append({
                **product,
                "sources": sources,
                "consensus_count": len(sources)
            })

    return sorted(consensus, key=lambda x: x["consensus_count"], reverse=True)
```

**Cache Functions**

Implementation:
```python
import json
import hashlib

def cache_lookup_function(cache_key: str) -> Optional[Dict]:
    """
    Lookup cached results in Redis.

    Args:
        cache_key: Cache key to search

    Returns:
        Cached data or None
    """
    redis_client = get_redis_client()
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)
    return None

def cache_store_function(
    cache_key: str,
    data: Dict[str, Any],
    ttl: int = 180
) -> bool:
    """
    Store results in Redis cache.

    Args:
        cache_key: Cache key
        data: Data to cache
        ttl: Time to live in seconds

    Returns:
        Success boolean
    """
    redis_client = get_redis_client()
    redis_client.set(cache_key, json.dumps(data), ex=ttl)
    return True

def make_cache_key(query: str, filters: Dict, limit: int) -> str:
    """
    Generate cache key for query.

    Args:
        query: Search query
        filters: Filter parameters
        limit: Result limit

    Returns:
        SHA256 hash as cache key
    """
    key_data = {
        "query": query.lower().strip(),
        "filters": sorted(filters.items()),
        "limit": limit
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()
```

### Phase 2: Agent Definition

**Objective**: Define AutoGen agents matching CAMEL agent capabilities using AssistantAgent class with function registration.

**CypherBot Agent**

```python
from autogen import AssistantAgent

cypher_bot = AssistantAgent(
    name="CypherBot",
    system_message="""You are a Graph Database Specialist expert in Neo4j and Cypher queries.

Your role is to find fashion products using graph relationships and semantic query expansion.
You translate natural language queries into optimized Cypher queries that leverage:
- Fulltext indexes for efficient text search
- Relationship traversal for connected products
- Semantic expansion with synonyms and related terms

When given a search query, you:
1. Analyze the query for key concepts
2. Generate semantic expansions using the semantic_expansion_function
3. Construct an optimized Cypher query
4. Execute the query using neo4j_query_function
5. Report your findings with product details

Focus on product categories, brands, styles, occasions, and relationships.""",
    llm_config={
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 2000,
        "functions": [
            {
                "name": "neo4j_query_function",
                "description": "Execute Cypher query against Neo4j product graph",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cypher": {
                            "type": "string",
                            "description": "Cypher query string"
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Query parameters for binding"
                        }
                    },
                    "required": ["cypher"]
                }
            },
            {
                "name": "semantic_expansion_function",
                "description": "Generate semantic expansions for search query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to expand"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    },
    max_consecutive_auto_reply=10,
    human_input_mode="NEVER"
)

# Register function implementations
cypher_bot.register_function(
    function_map={
        "neo4j_query_function": neo4j_query_function,
        "semantic_expansion_function": semantic_expansion_function
    }
)
```

**VibeBot Agent**

```python
vibe_bot = AssistantAgent(
    name="VibeBot",
    system_message="""You are an Aesthetic and Style Specialist expert in fashion trends and visual similarity.

Your role is to find products using semantic similarity and visual aesthetic matching.
You understand fashion terminology, style categories, color palettes, and aesthetic movements.

When given a search query, you:
1. Generate text embedding for the query using generate_text_embedding_function
2. Search Qdrant vector database using qdrant_search_function
3. Analyze similarity scores and aesthetic matches
4. Report your findings with style reasoning

You help users discover products that match their personal style even when they
can't articulate it precisely.""",
    llm_config={
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 1500,
        "functions": [
            {
                "name": "generate_text_embedding_function",
                "description": "Generate embedding vector for text query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to embed"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "qdrant_search_function",
                "description": "Search Qdrant vector database for similar products",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_embedding": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Query embedding vector"
                        },
                        "filters": {
                            "type": "object",
                            "description": "Optional filters"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results"
                        }
                    },
                    "required": ["query_embedding"]
                }
            }
        ]
    },
    max_consecutive_auto_reply=10,
    human_input_mode="NEVER"
)

vibe_bot.register_function(
    function_map={
        "generate_text_embedding_function": generate_text_embedding_function,
        "qdrant_search_function": qdrant_search_function
    }
)
```

**VisionBot Agent**

```python
vision_bot = AssistantAgent(
    name="VisionBot",
    system_message="""You are a Visual Similarity Specialist expert in fashion image analysis.

Your role is to find products visually similar to reference images using FashionSigLIP
visual embeddings and computer vision.

You understand visual features like:
- Color, pattern, texture
- Silhouette and shape
- Style and aesthetic
- Visual composition

When given a search query with images, you:
1. Generate visual embeddings using generate_fashionsig_embedding_function
2. Search for similar products using qdrant_search_function
3. Analyze visual similarity scores
4. Report your findings with visual reasoning

You can handle multi-image queries and find similar or matching items.""",
    llm_config={
        "model": "gpt-4o",
        "temperature": 0.6,
        "max_tokens": 1500,
        "functions": [
            {
                "name": "generate_fashionsig_embedding_function",
                "description": "Generate FashionSigLIP visual embedding for image",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Path to product image"
                        }
                    },
                    "required": ["image_path"]
                }
            },
            {
                "name": "qdrant_search_function",
                "description": "Search Qdrant for visually similar products",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_embedding": {
                            "type": "array",
                            "items": {"type": "number"}
                        },
                        "filters": {"type": "object"},
                        "limit": {"type": "integer"}
                    },
                    "required": ["query_embedding"]
                }
            }
        ]
    },
    max_consecutive_auto_reply=10,
    human_input_mode="NEVER"
)

vision_bot.register_function(
    function_map={
        "generate_fashionsig_embedding_function": generate_fashionsig_embedding_function,
        "qdrant_search_function": qdrant_search_function
    }
)
```

**JudgeAri Agent**

```python
judge_ari = AssistantAgent(
    name="JudgeAri",
    system_message="""You are a Fashion Recommendation Judge expert in quality assessment and curation.

Your role is to evaluate products from multiple search agents and curate the best
recommendations based on quality, relevance, and user needs.

You assess products considering:
- Completeness (title, price, images, description)
- Relevance to the query
- Commercial viability
- Overall quality
- Consensus across agents

You can:
- Score product quality using quality_score_function
- Detect consensus products using consensus_detection_function
- Learn from judgment history using learning_analysis_function
- Consciously reject products that don't meet standards

Provide detailed reasoning for your decisions to ensure transparency and continuous
improvement. Prioritize consensus products found by multiple agents for high confidence.""",
    llm_config={
        "model": "gpt-4o",
        "temperature": 0.6,
        "max_tokens": 1500,
        "functions": [
            {
                "name": "quality_score_function",
                "description": "Calculate independent quality score for product",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product": {"type": "object"},
                        "query": {"type": "string"}
                    },
                    "required": ["product", "query"]
                }
            },
            {
                "name": "consensus_detection_function",
                "description": "Identify products found by multiple agents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cypher_products": {"type": "array"},
                        "vibe_products": {"type": "array"},
                        "vision_products": {"type": "array"}
                    },
                    "required": ["cypher_products", "vibe_products", "vision_products"]
                }
            }
        ]
    },
    max_consecutive_auto_reply=10,
    human_input_mode="NEVER"
)

judge_ari.register_function(
    function_map={
        "quality_score_function": quality_score_function,
        "consensus_detection_function": consensus_detection_function
    }
)
```

### Phase 3: Group Chat Configuration

**Objective**: Configure AutoGen group chat to coordinate multi-agent product search through conversation.

**Group Chat Setup**

```python
from autogen import GroupChat, GroupChatManager

# Create group chat
product_search_group = GroupChat(
    agents=[cypher_bot, vibe_bot, vision_bot, judge_ari],
    messages=[],
    max_round=15,
    speaker_selection_method="auto",  # LLM-based speaker selection
    allow_repeat_speaker=False  # Encourage participation from all agents
)

# Create manager
product_search_manager = GroupChatManager(
    groupchat=product_search_group,
    llm_config={
        "model": "gpt-4o",
        "temperature": 0.6,
        "max_tokens": 2000
    },
    system_message="""You are coordinating a fashion product search across multiple specialist agents.

Agents:
- CypherBot: Graph database specialist using Neo4j relationships
- VibeBot: Aesthetic specialist using vector similarity
- VisionBot: Visual similarity specialist using image analysis
- JudgeAri: Quality judge evaluating all findings

Coordinate the conversation to:
1. Have search agents report their findings
2. Ensure all agents participate
3. Guide JudgeAri to evaluate after agents report
4. Conclude when JudgeAri provides final recommendations

Keep the conversation focused and efficient."""
)
```

**Speaker Selection Strategies**

Auto Selection (LLM-based):
```python
speaker_selection_method="auto"  # Manager LLM selects next speaker
```

Round Robin:
```python
speaker_selection_method="round_robin"  # Equal participation
```

Random:
```python
speaker_selection_method="random"  # Random selection
```

Custom Function:
```python
def custom_speaker_selection(last_speaker, groupchat):
    """Custom speaker selection logic"""
    if last_speaker == cypher_bot:
        return vibe_bot
    elif last_speaker == vibe_bot:
        return vision_bot
    elif last_speaker == vision_bot:
        return judge_ari
    else:
        return None  # Conversation ends

speaker_selection_method=custom_speaker_selection
```

### Phase 4: Orchestrator Implementation

**Objective**: Implement AutoGen-based orchestrator replacing BattleOrchestrator while maintaining API compatibility.

**AutoGen Orchestrator**

```python
from autogen import GroupChat, GroupChatManager
from typing import Dict, List, Any, Optional
import logging
import asyncio

logger = logging.getLogger("services.autogen_orchestrator")

class AutoGenOrchestrator:
    """
    AutoGen-based orchestrator replacing BattleOrchestrator.
    Maintains API compatibility with existing ApplicationService.
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        cache_service,
        metrics_service,
        redis_client
    ):
        self.agents = agents
        self.cache = cache_service
        self.metrics = metrics_service
        self.redis = redis_client

        # Create group chat
        self.group_chat = GroupChat(
            agents=list(agents.values()),
            messages=[],
            max_round=15,
            speaker_selection_method="auto"
        )

        # Create manager
        self.manager = GroupChatManager(
            groupchat=self.group_chat,
            llm_config={
                "model": "gpt-4o",
                "temperature": 0.6
            }
        )

    async def execute_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Execute product search using AutoGen group chat.
        Maintains BattleOrchestrator API compatibility.
        """
        # Check cache
        if not bypass_cache:
            cache_key = self._make_cache_key(query, filters or {}, limit)
            cached = await self.cache.get(cache_key)
            if cached:
                logger.info(f"Cache hit for query: '{query[:30]}...'")
                self.metrics.record_cache_hit(query, cached)
                return cached

        # Prepare search message
        search_message = self._create_search_message(
            query, filters, limit, user_context, ml_intelligence
        )

        # Execute group chat
        logger.info(f"Initiating group chat for query: '{query[:50]}...'")

        # Reset group chat messages
        self.group_chat.messages = []

        # Initiate chat from JudgeAri to manager
        result = await asyncio.to_thread(
            self.agents["judge_ari"].initiate_chat,
            self.manager,
            message=search_message,
            clear_history=False
        )

        # Extract results from conversation
        response = self._extract_results_from_conversation(
            self.group_chat.messages,
            query
        )

        # Cache result
        if response.get("products"):
            await self.cache.set(cache_key, response, ttl=180)
            logger.info(f"Cached result: {len(response['products'])} products")

        # Record metrics
        self.metrics.record_search(query, response)

        return response

    def _create_search_message(
        self,
        query: str,
        filters: Optional[Dict],
        limit: int,
        user_context: Optional[Dict],
        ml_intelligence: Optional[Dict]
    ) -> str:
        """Create search initiation message for group chat"""
        message = f"""Product Search Request: {query}

Parameters:
- Limit: {limit} products
- Filters: {filters or "None"}

CypherBot: Search Neo4j graph database using Cypher queries with semantic expansion.
VibeBot: Search Qdrant vector database for semantically similar products.
VisionBot: Search for visually similar products using FashionSigLIP.

All agents: Report your findings with product details and reasoning.

JudgeAri: Once all agents report, evaluate the findings:
1. Use consensus_detection_function to find products multiple agents discovered
2. Use quality_score_function to assess each product
3. Select the best {limit} products
4. Provide detailed reasoning for your selections"""

        if ml_intelligence:
            message += f"\n\nML Intelligence Available:\n{ml_intelligence}"

        if user_context:
            message += f"\n\nUser Context:\n{user_context}"

        return message

    def _extract_results_from_conversation(
        self,
        messages: List[Dict],
        query: str
    ) -> Dict[str, Any]:
        """Extract structured results from group chat conversation"""
        # Find JudgeAri's final evaluation
        judge_messages = [
            m for m in messages
            if m.get("name") == "JudgeAri"
        ]

        if not judge_messages:
            logger.error("No judgment found in conversation")
            return {
                "products": [],
                "error": "No judgment provided",
                "conversation": messages
            }

        # Get last judgment message
        final_judgment = judge_messages[-1]["content"]

        # Extract products from judgment
        # Parse function calls and results
        products = self._parse_products_from_judgment(messages)

        # Count agent contributions
        cypher_count = len([m for m in messages if m.get("name") == "CypherBot"])
        vibe_count = len([m for m in messages if m.get("name") == "VibeBot"])
        vision_count = len([m for m in messages if m.get("name") == "VisionBot"])

        return {
            "products": products,
            "reasoning": final_judgment,
            "cypher_count": cypher_count,
            "vibe_count": vibe_count,
            "vision_count": vision_count,
            "winner": "consensus",  # AutoGen uses collaborative approach
            "quality_controlled": True,
            "conversation": messages  # Include full conversation for debugging
        }

    def _parse_products_from_judgment(
        self,
        messages: List[Dict]
    ) -> List[Dict]:
        """Parse products from conversation messages and function calls"""
        products = []

        # Look for function call results
        for message in messages:
            if "function_call" in message or "tool_calls" in message:
                # Extract function results
                # This depends on AutoGen's function call format
                pass

        # Parse from final judgment if products mentioned
        # Implementation depends on how JudgeAri structures response

        return products[:5]  # Limit to requested number

    def _make_cache_key(
        self,
        query: str,
        filters: Dict,
        limit: int
    ) -> str:
        """Create cache key matching BattleOrchestrator pattern"""
        import hashlib
        import json

        key_data = {
            "query": query.lower().strip(),
            "filters": sorted(filters.items()),
            "limit": limit
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
```

**Integration with ApplicationService**

```python
from services.autogen_orchestrator import AutoGenOrchestrator

class ApplicationService:
    def __init__(self, cache, metrics, redis_client):
        # Initialize AutoGen agents
        agents = {
            "cypher_bot": cypher_bot,
            "vibe_bot": vibe_bot,
            "vision_bot": vision_bot,
            "judge_ari": judge_ari
        }

        self.orchestrator = AutoGenOrchestrator(
            agents=agents,
            cache_service=cache,
            metrics_service=metrics,
            redis_client=redis_client
        )

    async def search_products(
        self,
        query: str,
        filters: dict = None,
        user_id: str = None,
        session_id: str = None
    ):
        # Existing ApplicationService logic
        user_context = await self._load_user_context(user_id)
        ml_intelligence = await self._generate_ml_intelligence(query, user_context)

        # Execute search via AutoGen
        results = await self.orchestrator.execute_search(
            query=query,
            filters=filters,
            user_context=user_context,
            ml_intelligence=ml_intelligence
        )

        return results
```

### Phase 5: Memory Integration

**Objective**: Integrate AutoGen conversation history with existing Redis-backed memory systems.

**Redis Memory Manager**

```python
import json
from typing import List, Dict, Any
from datetime import datetime

class AutoGenRedisMemory:
    """
    Manages AutoGen conversation persistence in Redis.
    Maintains compatibility with existing CAMEL memory structure.
    """

    def __init__(self, redis_client, session_id):
        self.redis = redis_client
        self.session_id = session_id
        self.messages_key = f"session:{session_id}:autogen_messages"
        self.summary_key = f"session:{session_id}:summary"

    def save_conversation(self, messages: List[Dict[str, Any]]):
        """Save AutoGen conversation messages to Redis"""
        # Store messages
        for message in messages:
            self.redis.lpush(
                self.messages_key,
                json.dumps({
                    "name": message.get("name"),
                    "role": message.get("role"),
                    "content": message.get("content"),
                    "timestamp": datetime.now().isoformat()
                })
            )

        # Keep last 50 messages
        self.redis.ltrim(self.messages_key, 0, 49)

        # Set TTL (1 hour)
        self.redis.expire(self.messages_key, 3600)

    def load_conversation(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Load conversation history from Redis"""
        messages = self.redis.lrange(self.messages_key, 0, limit - 1)
        return [json.loads(m) for m in messages]

    def save_summary(self, summary: str):
        """Save conversation summary"""
        self.redis.set(
            self.summary_key,
            summary,
            ex=3600
        )

    def load_summary(self) -> str:
        """Load conversation summary"""
        return self.redis.get(self.summary_key) or ""
```

**Memory Usage**

```python
# Before conversation
memory = AutoGenRedisMemory(redis_client, session_id)
previous_messages = memory.load_conversation()

# Initialize group chat with history
product_search_group.messages = previous_messages

# After conversation
memory.save_conversation(product_search_group.messages)
```

### Phase 6: Testing and Validation

**Objective**: Validate AutoGen implementation matches CAMEL behavior, performance, and quality.

**Unit Testing**

Test agents:
```python
async def test_cypher_bot_function_calls():
    # Test function registration
    assert "neo4j_query_function" in cypher_bot.function_map

    # Test agent can call function
    # Simulate conversation requiring function call
    pass

async def test_judge_ari_evaluation():
    # Test quality scoring
    product = {"title": "Black Blazer", "price": 120, "images": ["img1"]}
    score = quality_score_function(product, "black blazer")

    assert score["quality_score"] > 0
    assert "factors" in score
```

**Integration Testing**

Test group chat:
```python
async def test_group_chat_execution():
    # Create test group chat
    group_chat = GroupChat(
        agents=[cypher_bot, vibe_bot, vision_bot, judge_ari],
        messages=[],
        max_round=15
    )

    manager = GroupChatManager(groupchat=group_chat)

    # Initiate search
    result = await asyncio.to_thread(
        judge_ari.initiate_chat,
        manager,
        message="Find black blazers for wedding. Limit 5 products."
    )

    # Validate conversation occurred
    assert len(group_chat.messages) > 0

    # Validate all agents participated
    agent_names = {m.get("name") for m in group_chat.messages}
    assert "CypherBot" in agent_names
    assert "VibeBot" in agent_names
    assert "JudgeAri" in agent_names
```

**Comparison Testing**

Compare CAMEL vs AutoGen:
```python
async def test_result_comparison():
    query = "red evening dress"

    # CAMEL result
    camel_result = await battle_orchestrator.execute_battle(
        query=query,
        limit=5
    )

    # AutoGen result
    autogen_result = await autogen_orchestrator.execute_search(
        query=query,
        limit=5
    )

    # Compare product quality
    camel_products = camel_result["products"]
    autogen_products = autogen_result["products"]

    # Both should find products
    assert len(camel_products) > 0
    assert len(autogen_products) > 0

    # Products should have similar relevance
    # (exact match not expected due to conversation variability)
    assert measure_relevance_similarity(
        camel_products, autogen_products, query
    ) > 0.7
```

---

## Data Persistence and State Management

### Redis Integration

**Connection Management**

Use existing Redis client:
```python
import redis.asyncio as redis

redis_client = redis.from_url(
    os.getenv("REDIS_URL"),
    encoding="utf-8",
    decode_responses=True
)
```

**Key Structure**

Maintain existing patterns:
```
session:{session_id}:autogen_messages    # AutoGen conversation
session:{session_id}:summary              # Conversation summary
user:{user_id}:preferences                # User preferences
cache:{hash}                              # Query cache
```

### Neo4j and Qdrant Integration

Backend integration through function calling:
- Functions access existing drivers and clients
- Connection pooling maintained
- Query patterns unchanged
- Results returned to agents via function returns

---

## Risk Assessment and Mitigation

### Technical Risks

**Risk: Conversation Variability**

Description: AutoGen's conversation-based coordination introduces variability in agent interactions compared to deterministic CAMEL orchestration.

Impact: Non-deterministic product selection, inconsistent response times, unpredictable agent participation.

Mitigation:
- Clear agent system messages guiding behavior
- Speaker selection strategies for predictability
- Max rounds limit to prevent long conversations
- Termination conditions for conversation control
- Extensive testing of conversation patterns

**Risk: Function Calling Reliability**

Description: AutoGen function calling depends on LLM correctly generating function call requests, which may be unreliable.

Impact: Functions not called when needed, incorrect parameters, missing results.

Mitigation:
- Clear function descriptions and parameter schemas
- Agent system messages explicitly mentioning available functions
- Validation of function call parameters
- Fallback mechanisms for missing function calls
- Comprehensive function testing

**Risk: Group Chat Coordination**

Description: Group chat coordination more complex than parallel execution, may introduce coordination failures or inefficiencies.

Impact: Agents not participating, redundant work, inefficient conversations.

Mitigation:
- Speaker selection strategies optimized for use case
- Clear roles and responsibilities in system messages
- Conversation round limits
- Manager system message guiding efficient coordination
- Monitoring conversation patterns

**Risk: AutoGen Framework Status**

Description: Microsoft now recommends Microsoft Agent Framework over AutoGen, raising questions about AutoGen's future and support.

Impact: Framework may be deprecated, limited new features, migration pressure.

Mitigation:
- Evaluate Microsoft Agent Framework in parallel
- Design abstraction layer for potential future migration
- Monitor AutoGen community and Microsoft announcements
- Plan for eventual framework transition
- Document decision rationale

### Operational Risks

**Risk: Performance Degradation**

Description: Conversation overhead and LLM-based speaker selection may slow execution compared to parallel CAMEL approach.

Impact: Slower response times, reduced throughput, poor user experience.

Mitigation:
- Performance benchmarking against CAMEL baseline
- Optimization of conversation patterns
- Caching strategies to minimize overhead
- Speaker selection strategy tuning
- A/B testing with real traffic

**Risk: Production Stability**

Description: Conversation-based coordination introduces new failure modes compared to deterministic orchestration.

Impact: Service degradation, incorrect results, user dissatisfaction.

Mitigation:
- Parallel operation with CAMEL system
- Feature flags for rollback
- Comprehensive monitoring and alerting
- Clear incident response procedures
- Gradual traffic migration

---

## Technical Considerations

### Advantages of AutoGen

**Rich Conversation Patterns**
- Flexible multi-agent coordination through dialogue
- Dynamic interaction based on context
- Iterative refinement through conversation
- Natural information exchange between agents

**Research-Proven Patterns**
- Extensive research backing from Microsoft
- Proven multi-agent conversation approaches
- Academic validation and publications
- Large community experimentation

**Flexible Architecture**
- Multiple conversation patterns (group chat, sequential, nested)
- Customizable speaker selection
- Extensible agent capabilities
- Human-in-the-loop support

**Function Calling**
- Easy tool integration through functions
- Automatic parameter extraction
- LLM-driven function selection
- Clean separation of agent logic and backend access

**Code Execution**
- UserProxyAgent for code execution
- Isolated execution environments
- Useful for analytical tasks
- Safety and validation mechanisms

### Disadvantages and Limitations

**Conversation Variability**
- Non-deterministic agent interactions
- Unpredictable conversation length
- Variable response times
- Difficult to guarantee specific outcomes

**Framework Status Uncertainty**
- Microsoft recommending Microsoft Agent Framework instead
- Limited new feature development
- Potential future deprecation
- Maintenance-only mode

**LLM Dependency**
- Speaker selection relies on LLM
- Function calling depends on LLM accuracy
- Conversation quality varies with LLM performance
- Token usage and costs

**Debugging Complexity**
- Conversation flow harder to debug than linear orchestration
- Speaker selection logic opaque
- Function call failures subtle
- Multiple layers of abstraction

### Comparison with Other Frameworks

**AutoGen vs Microsoft Agent Framework**
- AutoGen: Conversation-focused, research-oriented, mature
- MAF: Enterprise-focused, graph workflows, newer, recommended by Microsoft

**AutoGen vs CrewAI**
- AutoGen: Flexible conversations, research-proven, complex
- CrewAI: Task-driven, simpler, production-ready, larger community

**When to Choose AutoGen**
- Conversation-driven coordination fits use case
- Research and experimentation important
- Team has AutoGen expertise
- Flexible agent interaction needed
- Code execution capability required

**When to Reconsider AutoGen**
- Deterministic orchestration preferred
- Framework longevity concern
- Simplicity prioritized
- Microsoft Agent Framework or CrewAI better fit

---

## Decision Factors

### When to Choose AutoGen

**Use Case Alignment**
- Product search benefits from conversational coordination
- Agents need to negotiate and refine together
- Iterative improvement through dialogue valuable
- Dynamic agent participation based on context

**Team Capabilities**
- Team comfortable with conversation-based patterns
- Research and experimentation culture
- Existing AutoGen knowledge
- Python expertise

**Technical Requirements**
- Rich multi-agent conversation patterns needed
- Function calling model works well
- Code execution capability useful
- Human-in-the-loop valuable

### When to Reconsider AutoGen

**Framework Concerns**
- Microsoft recommending alternative framework
- Long-term support uncertain
- Framework maturity declining
- Migration effort to newer framework likely

**Simplicity Preference**
- Deterministic orchestration simpler
- Conversation variability undesirable
- Predictable behavior critical
- Minimal abstraction preferred

**Alternative Frameworks**
- Microsoft Agent Framework better Microsoft integration
- CrewAI simpler and more production-ready
- CAMEL working well already
- Migration effort not justified

---

## Conclusion

Migration from CAMEL-AI to AutoGen represents an architectural shift to conversation-driven multi-agent coordination enabling:

**Enhanced Capabilities**
- Flexible agent coordination through natural dialogue
- Dynamic information exchange and negotiation
- Iterative refinement through conversation
- Rich multi-agent collaboration patterns

**Simplified Integration**
- Function calling for clean backend integration
- Easy tool registration and usage
- Agent-driven function selection
- Clear separation of concerns

**Research-Proven Patterns**
- Extensive Microsoft Research backing
- Validated multi-agent approaches
- Academic publication and community validation
- Proven conversation coordination

**Considerations**

Framework Status:
- Microsoft now recommends Microsoft Agent Framework
- AutoGen in maintenance mode with bug fixes only
- Future migration likely
- Evaluate alternatives carefully

Technical Trade-offs:
- Conversation variability vs deterministic orchestration
- Flexible coordination vs predictable execution
- Natural dialogue vs engineered workflows
- Research patterns vs production simplicity

**Migration Risk Management**
- Incremental migration with parallel operation
- Comprehensive testing of conversation patterns
- Feature flags for rollback
- Redis compatibility preservation
- Performance validation

The migration requires careful consideration of AutoGen's framework status and technical trade-offs. While AutoGen offers powerful conversation-driven coordination and research-proven patterns, Microsoft's recommendation of Microsoft Agent Framework suggests teams should evaluate all options. Success depends on conversation pattern design, function integration, comprehensive testing, and maintaining compatibility with existing Redis-backed infrastructure.

AutoGen remains viable for specific use cases requiring rich agent conversations, research experimentation, or teams with existing AutoGen expertise, but alternative frameworks may provide better long-term support and simpler production deployment.
