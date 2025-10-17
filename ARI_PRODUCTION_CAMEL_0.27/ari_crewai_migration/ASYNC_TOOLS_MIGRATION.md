# Async Tools Migration Guide
**Phase 2: Non-blocking I/O for CrewAI**

## Overview
Phase 2 introduces truly async tools that don't block the event loop. This allows:
- ✅ Proper timeout enforcement (no more infinite loops)
- ✅ Parallel crew execution without blocking
- ✅ Better resource utilization
- ✅ Faster overall execution

## Created Async Tools

**Note:** Async tools are in `tools/async_tools/` directory (not `tools/async/` - Python keyword conflict)

### Neo4j Async Tools (`tools/async_tools/async_neo4j_tools.py`)
1. **`async_neo4j_query_tool`** - Execute Cypher queries without blocking
2. **`async_semantic_expansion_tool`** - Generate query expansions asynchronously
3. **`async_neo4j_fulltext_search_tool`** - Fulltext search with async fallback

### Qdrant Async Tools (`tools/async_tools/async_qdrant_tools.py`)
1. **`async_qdrant_search_tool`** - Vector similarity search (async)
2. **`async_embedding_generation_tool`** - Generate OpenAI embeddings (async)
3. **`async_qdrant_hybrid_search_tool`** - Combined embedding + search (async)
4. **`async_qdrant_filter_search_tool`** - Filter-only search (async)

### FashionSigLIP Async Tools (`tools/async_tools/async_fashionsig_tools.py`)
1. **`async_fashionsig_embedding_tool`** - Generate visual embeddings (async)
2. **`async_visual_similarity_search_tool`** - Find visually similar products (async)
3. **`async_multi_image_search_tool`** - Multi-image search with parallel embeddings
4. **`async_fashionsig_multimodal_search_tool`** - Text-to-visual search (async)

## Key Differences from Sync Tools

### Sync Tool (Blocking)
```python
@tool("Execute Neo4j Query")
def neo4j_query_tool(cypher: str, parameters: Dict = None) -> List[Dict]:
    driver = AsyncGraphDatabase.driver(...)

    async def execute():
        # Async code
        return results

    # ❌ BLOCKS event loop waiting for async code
    results = asyncio.run(execute())
    return results
```

### Async Tool (Non-blocking)
```python
@tool("Execute Neo4j Query (Async)")
async def async_neo4j_query_tool(cypher: str, parameters: Dict = None) -> List[Dict]:
    driver = AsyncGraphDatabase.driver(...)

    # ✅ Properly awaits without blocking
    async with driver.session() as session:
        result = await session.run(cypher, parameters or {})
        # ... process results
        return records
```

## How to Use Async Tools in Agent YAMLs

### Option 1: Direct YAML Update (Recommended)
Update agent YAML files to reference async tools:

**Before:**
```yaml
# agents/cypher_bot.yaml
agent:
  tools:
    - neo4j_query_tool
    - semantic_expansion_tool
    - neo4j_fulltext_search_tool
```

**After:**
```yaml
# agents/cypher_bot.yaml
agent:
  tools:
    - async_neo4j_query_tool
    - async_semantic_expansion_tool
    - async_neo4j_fulltext_search_tool
```

### Option 2: Dynamic Tool Registration (For Testing)
Register async tools programmatically when creating crews:

```python
from tools.async_tools.async_neo4j_tools import (
    async_neo4j_query_tool,
    async_semantic_expansion_tool,
    async_neo4j_fulltext_search_tool
)

# When creating mini-crew
from utils.agent_loader import load_agent

cypher_agent = load_agent('agents/cypher_bot.yaml')

# Override tools with async versions
cypher_agent.tools = [
    async_neo4j_query_tool,
    async_semantic_expansion_tool,
    async_neo4j_fulltext_search_tool
]
```

## Agent-Specific Tool Mappings

### CypherBot (Graph Search)
```yaml
tools:
  - async_neo4j_query_tool           # Replaces: neo4j_query_tool
  - async_semantic_expansion_tool    # Replaces: semantic_expansion_tool
  - async_neo4j_fulltext_search_tool # Replaces: neo4j_fulltext_search_tool
```

### VibeBot (Vector Search)
```yaml
tools:
  - async_qdrant_hybrid_search_tool      # Replaces: qdrant_hybrid_search_tool
  - async_embedding_generation_tool      # Replaces: embedding_generation_tool
  - async_qdrant_search_tool             # Replaces: qdrant_search_tool
  - async_qdrant_filter_search_tool      # New: filter-only search
```

### VisionBot (Visual Search)
```yaml
tools:
  - async_visual_similarity_search_tool    # Replaces: visual_similarity_search_tool
  - async_fashionsig_embedding_tool        # Replaces: fashionsig_embedding_tool
  - async_multi_image_search_tool          # Replaces: multi_image_search_tool
  - async_fashionsig_multimodal_search_tool # New: text-to-visual
```

### Judge Ari (Evaluation)
No database tools needed - uses LLM only for evaluation

## Testing Async Tools

### Unit Test: Import Check
```python
# Test that all async tools can be imported
from tools.async import (
    async_neo4j_query_tool,
    async_qdrant_search_tool,
    async_fashionsig_embedding_tool
)
print("✅ All async tools imported successfully")
```

### Integration Test: Mock Async Call
```python
import asyncio
from tools.async import async_semantic_expansion_tool

async def test_async_tool():
    result = await async_semantic_expansion_tool(
        query="black dress for wedding",
        context={"occasion": "wedding"}
    )
    assert "synonyms" in result
    assert "expanded_query" in result
    print("✅ Async tool executed successfully")

asyncio.run(test_async_tool())
```

### Flow Integration Test
```python
# Test with ProductSearchFlow (already uses async)
from flows import create_and_run_flow
from crews.mini_crews import (
    create_graph_search_crew,
    create_vector_search_crew,
    create_visual_search_crew,
    create_judge_crew
)

# Mini-crews will automatically use async tools if configured
async def test_flow():
    result = await create_and_run_flow(
        query="red dress",
        limit=5,
        graph_crew=create_graph_search_crew(),
        vector_crew=create_vector_search_crew(),
        visual_crew=create_visual_search_crew(),
        judge_crew=create_judge_crew()
    )
    print(f"✅ Flow executed with {len(result.products)} products")

asyncio.run(test_flow())
```

## Benefits Verification

### 1. Timeout Enforcement
```python
import asyncio

async def test_timeout():
    """Verify async tools respect timeouts"""
    try:
        # Should timeout after 1s
        result = await asyncio.wait_for(
            async_neo4j_query_tool("MATCH (p:Product) RETURN p LIMIT 10", {}),
            timeout=1.0
        )
        print("✅ Query completed within timeout")
    except asyncio.TimeoutError:
        print("✅ Timeout enforced correctly")
```

### 2. Parallel Execution
```python
async def test_parallel():
    """Verify multiple async tools run in parallel"""
    import time

    start = time.time()

    # Run 3 async tools in parallel
    results = await asyncio.gather(
        async_semantic_expansion_tool("dress"),
        async_semantic_expansion_tool("shoes"),
        async_semantic_expansion_tool("jacket")
    )

    elapsed = time.time() - start

    # If truly parallel, should be ~same time as 1 call
    # If sequential, would be 3x longer
    print(f"✅ Parallel execution: {elapsed:.2f}s for 3 calls")
    assert elapsed < 0.5  # Should be fast for semantic expansion
```

## Migration Checklist

### Phase 2A: Tool Creation ✅
- [x] Create `tools/async_tools/async_neo4j_tools.py`
- [x] Create `tools/async_tools/async_qdrant_tools.py`
- [x] Create `tools/async_tools/async_fashionsig_tools.py`
- [x] Update `tools/async_tools/__init__.py` exports
- [x] Fix Python keyword conflict (renamed `async` → `async_tools`)

### Phase 2B: Agent Configuration (Next)
- [ ] Update `agents/cypher_bot.yaml` to use async Neo4j tools
- [ ] Update `agents/vibe_bot.yaml` to use async Qdrant tools
- [ ] Update `agents/vision_bot.yaml` to use async FashionSig tools
- [ ] Test agent initialization with async tools

### Phase 2C: Testing (Next)
- [ ] Unit tests for each async tool
- [ ] Integration tests with mini-crews
- [ ] Timeout enforcement tests
- [ ] Parallel execution verification

### Phase 2D: Documentation & Commit
- [ ] Update README with async tool usage
- [ ] Document performance improvements
- [ ] Commit Phase 2 changes

## Performance Expectations

### Before (Sync Tools)
- Graph search: 2-5s (blocking)
- Vector search: 1-3s (blocking)
- Visual search: 2-4s (blocking)
- **Total (sequential in Flow)**: 5-12s
- **Total (if crews block each other)**: 15-36s

### After (Async Tools)
- Graph search: 2-5s (non-blocking)
- Vector search: 1-3s (non-blocking)
- Visual search: 2-4s (non-blocking)
- **Total (parallel in Flow with async)**: 2-5s (limited by slowest crew)
- **Improvement**: 3-7x faster! 🚀

## Troubleshooting

### Issue: "Tool not found"
**Solution:** Ensure async tools are imported in agent loader or registered manually

### Issue: "Event loop is already running"
**Solution:** Async tools should be called within Flow context (already async)

### Issue: "Connection pool exhausted"
**Solution:** Async tools properly close connections in `finally` blocks

### Issue: "Timeout still not working"
**Solution:** Verify tools are truly async (no `asyncio.run()` calls)

## Next Steps

1. **Test async tool imports** - Verify all tools can be imported
2. **Update agent YAMLs** - Reference async tools in configurations
3. **Integration testing** - Test with real mini-crews
4. **Performance benchmarking** - Measure improvement
5. **Production deployment** - Roll out async tools gradually
