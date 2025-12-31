# Mem0 Integration Guide

Redis memory has been replaced with Mem0 for episodic, semantic, and factual memory.

## What Changed

**Before (Redis):**
- `memory/redis_memory_provider.py` - Session-based key-value storage
- Short-term memory (1 hour TTL)
- Long-term memory (30 days TTL)
- Entity memory (products, brands)

**After (Mem0):**
- `memory/mem0_memory_provider.py` - AI-powered memory with graph support
- Episodic memory (conversation history, interactions)
- Factual memory (user preferences, stable data)
- Semantic memory (concept relationships via Neo4j graph)

## Installation

```bash
pip install mem0ai
```

Already installed in `../crewai_env/`.

## Configuration

Mem0 uses your existing infrastructure:

**Neo4j Graph Store:**
- URL: `NEO4J_URI` (neo4j://34.135.40.119:7687)
- Database: `users`
- Stores relationship graphs (User → likes → Brand)

**Qdrant Vector Store:**
- URL: `QDRANT_URL`
- Collection: `mem0_memories`
- Stores embeddings for semantic search

**OpenAI LLM:**
- Model: `gpt-4o-mini`
- Used for entity extraction and memory summarization

All configured automatically from environment variables.

## Memory Types

### 1. Episodic Memory
**What:** Conversation turns, searches, product interactions
**TTL:** Session-based, can be cleared
**Example:**
```python
await mem0.add_episodic(
    "User searched for casual white t-shirts",
    metadata={"query": "white t-shirt", "products_shown": 5}
)
```

### 2. Factual Memory
**What:** User preferences, budget, style, account details
**TTL:** Permanent until updated
**Example:**
```python
await mem0.add_factual(
    "User prefers minimalist and casual style",
    category="style_preference"
)
```

### 3. Semantic Memory (Graph)
**What:** Relationships between concepts, entities
**TTL:** Permanent, stored in Neo4j graph
**Example:**
```python
await mem0.add_semantic(
    "User loves Brand X for minimalist aesthetic",
    metadata={"entity_type": "brand", "entity_value": "Brand X"}
)
```

Neo4j stores: `(User)-[:LOVES]->(Brand X)-[:HAS_AESTHETIC]->(Minimalist)`

## Usage

### Basic Usage

```python
from memory.mem0_memory_provider import create_mem0_memory_provider

# Create provider
mem0 = create_mem0_memory_provider(
    user_id="user_123",
    session_id="session_456"
)

# Add memories
await mem0.add_episodic("User asked about sustainable brands")
await mem0.add_factual("Monthly budget: $200-$500", category="budget")
await mem0.add_semantic("User prefers cotton materials for comfort")

# Retrieve memories
episodic = await mem0.get_episodic(limit=10)
factual = await mem0.get_factual(category="budget")
semantic = await mem0.get_semantic(query="materials", limit=5)

# Search all types
results = await mem0.search_all(query="sustainable shopping", limit=5)
```

### Backward Compatibility

Old Redis methods still work (mapped to new memory types):

```python
# OLD CODE (still works):
await mem0.save_short_term({"interaction": "User searched"})
await mem0.save_long_term("budget", "$200-500")
await mem0.save_entity("brand", "Brand X")

# Maps to:
# save_short_term → add_episodic
# save_long_term → add_factual
# save_entity → add_semantic
```

## Migration

Migrate existing Neo4j user data to Mem0:

```bash
cd scripts
PYTHONPATH=/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration:/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27 \
../crewai_env/bin/python migrate_to_mem0.py
```

This populates:
- Factual: Style preferences, budget, values
- Semantic: User-brand-style relationships
- Episodic: Search/purchase history summaries

## Examples

Run examples to see Mem0 in action:

```bash
cd examples
PYTHONPATH=/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration \
../crewai_env/bin/python mem0_usage_example.py
```

Shows:
1. Conversation flow tracking
2. User preference storage
3. Style relationship graphs
4. Contextual search across memory types
5. Integration with product search

## Integration Points

### 1. Chat Interface (`cli/chat_interface_v2.py`)

Track user conversations:

```python
from memory.mem0_memory_provider import create_mem0_memory_provider

# In chat loop
mem0 = create_mem0_memory_provider(user.id, session_id)

# Track each interaction
await mem0.add_episodic(f"User: {user_input}")
await mem0.add_episodic(f"ARI: {agent_response}")

# Get context for next response
context = await mem0.get_episodic(limit=5)
```

### 2. Onboarding Flow (`crews/onboarding_crew.py`)

Store onboarding data:

```python
# After collecting preferences
await mem0.add_factual(
    f"User prefers {style_adjectives}",
    category="style_preference"
)

await mem0.add_semantic(
    f"User associates {occasion} with {style}",
    metadata={"occasion": occasion, "style": style}
)
```

### 3. Product Search (`crews/crewai_orchestrator.py`)

Use memories for personalization:

```python
# Before search
budget = await mem0.get_factual(category="budget")
past_searches = await mem0.get_episodic(query="similar items", limit=3)
brand_prefs = await mem0.get_semantic(query="brand preferences")

# Apply to search filters
filters["max_price"] = extract_budget(budget)
filters["preferred_brands"] = extract_brands(brand_prefs)

# After showing results
await mem0.add_episodic(
    f"Showed {len(products)} {category} items to user"
)
```

### 4. Recommendation Tracking (`services/user_graph_manager.py`)

Track product interactions:

```python
# When user views product
await mem0.add_episodic(
    f"User viewed {product_title}",
    metadata={"product_id": product_id, "category": category}
)

# When user likes product
await mem0.add_semantic(
    f"User likes {brand} for {category}",
    metadata={"brand": brand, "category": category}
)
```

## Graph Memory Visualization

Mem0 creates knowledge graph in Neo4j:

```cypher
// View user's style graph
MATCH (u:User {id: 'user_123'})-[r]-(n)
RETURN u, r, n
LIMIT 20

// Example graph:
// (User)-[:PREFERS]->(Minimalist Style)
// (User)-[:LIKES]->(Brand X)
// (Brand X)-[:OFFERS]->(Casual Category)
// (User)-[:SHOPS_FOR]->(Weekend Occasion)
// (Minimalist Style)-[:SUITS]->(Weekend Occasion)
```

## Next Steps

1. **Update chat_interface_v2.py** to use Mem0 for conversation tracking
2. **Update onboarding_crew.py** to store preferences in Mem0
3. **Modify crewai_orchestrator.py** to use Mem0 context for personalization
4. **Run migration script** to populate Mem0 from existing user data
5. **Test conversation continuity** with episodic memory
6. **Monitor Neo4j graph** to verify semantic relationships

## Testing

```bash
# Test import
python -c "from memory.mem0_memory_provider import Mem0MemoryProvider; print('OK')"

# Run examples
cd examples
python mem0_usage_example.py

# Run migration
cd scripts
python migrate_to_mem0.py

# Test with chat interface
cd ..
./run_chat.sh
```

## Troubleshooting

**Neo4j Connection Error:**
Check `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in environment

**Qdrant Collection Missing:**
Mem0 auto-creates `mem0_memories` collection on first use

**OpenAI API Error:**
Verify `OPENAI_API_KEY` is set

**Import Error:**
Ensure `mem0ai` is installed: `pip install mem0ai`

## Benefits

**vs Redis:**
- Semantic search across memories (not just key lookup)
- AI-powered entity extraction and summarization
- Graph relationships for deep understanding
- No manual TTL management
- Unified search across memory types

**For ARI:**
- Better conversation continuity
- Richer user preference understanding
- Style relationship discovery
- Context-aware recommendations
- Learning from past interactions
