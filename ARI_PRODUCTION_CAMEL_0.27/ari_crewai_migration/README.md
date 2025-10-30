# ARI CrewAI Migration

Migration from CAMEL-AI to CrewAI framework for the ARI Fashion Recommendation System.

## Overview

This folder contains the complete CrewAI implementation that replaces the CAMEL-AI battle orchestration pattern with CrewAI crew-based workflows.

### Key Improvements

- **Flexible Workflows**: Hierarchical or sequential process types
- **Task-Based Architecture**: Discrete tasks with clear dependencies
- **Simplified Orchestration**: CrewAI handles agent coordination
- **Built-in Memory**: Automatic memory management with Redis backend
- **Better Testability**: Independent task testing

## Architecture

### Directory Structure

```
ari_crewai_migration/
 tools/                  # CrewAI tools wrapping backend services
    neo4j_tools.py      # Graph database tools
    qdrant_tools.py     # Vector search tools
    fashionsig_tools.py # Visual similarity tools
    quality_tools.py    # Quality assessment tools
    cache_tools.py      # Redis caching tools

 agents/                 # Agent YAML configurations
    cypher_bot.yaml     # Graph search agent
    vibe_bot.yaml       # Vector search agent
    vision_bot.yaml     # Visual search agent
    judge_ari.yaml      # Judgment agent

 tasks/                  # Task YAML definitions
    intelligence_generation.yaml
    graph_search.yaml
    vector_search.yaml
    visual_search.yaml
    result_evaluation.yaml

 crews/                  # Crew assembly
    product_search_crew.py
    crewai_orchestrator.py

 memory/                 # Memory providers
    redis_memory_provider.py

 utils/                  # Utilities
    agent_loader.py
    task_loader.py

 config/                 # Configuration files
```

## Installation

### 1. Install Dependencies

```bash
cd ari_crewai_migration
pip install -r requirements.txt
```

### 2. Configure Environment

Copy environment variables from parent directory or create new:

```bash
# Neo4j Configuration
NEO4J_URL=bolt://your-neo4j-host:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Qdrant Configuration
QDRANT_URL=http://your-qdrant-host:6333
QDRANT_API_KEY=your_api_key
QDRANT_COLLECTION_NAME=fashion_products

# Redis Configuration
REDIS_URL=redis://your-redis-host:6379

# OpenAI Configuration
OPENAI_API_KEY=your_openai_key
```

## Usage

### Basic Usage

```python
from crews.crewai_orchestrator import create_crewai_orchestrator

# Create orchestrator
orchestrator = create_crewai_orchestrator(
    process_type="hierarchical"  # or "sequential"
)

# Execute search
result = await orchestrator.execute_search(
    query="black dress for wedding",
    filters={"category": "dress"},
    limit=5,
    user_context={},
    ml_intelligence={}
)

# Access results
products = result['products']
reasoning = result['reasoning']
metadata = result['metadata']
```

### Integration with ApplicationService

Replace BattleOrchestrator in existing ApplicationService:

```python
from crews.crewai_orchestrator import create_crewai_orchestrator

class ApplicationService:
    def __init__(self, cache, metrics, redis_client):
        # Replace BattleOrchestrator with CrewAIOrchestrator
        self.orchestrator = create_crewai_orchestrator(
            cache_service=cache,
            metrics_service=metrics,
            redis_client=redis_client,
            process_type="hierarchical"
        )
```

## Agent Configurations

### CypherBot (Graph Search)
- **Role**: Graph Database Specialist
- **Tools**: neo4j_query_tool, semantic_expansion_tool, neo4j_fulltext_search_tool
- **Focus**: Relationship patterns, semantic expansion

### VibeBot (Vector Search)
- **Role**: Aesthetic and Style Specialist
- **Tools**: qdrant_search_tool, embedding_generation_tool, qdrant_hybrid_search_tool
- **Focus**: Semantic similarity, style matching

### VisionBot (Visual Search)
- **Role**: Visual Similarity Specialist
- **Tools**: fashionsig_embedding_tool, visual_similarity_search_tool, multi_image_search_tool
- **Focus**: Visual features, image similarity

### JudgeAri (Quality Control)
- **Role**: Fashion Recommendation Judge
- **Tools**: quality_scoring_tool, consensus_detection_tool, learning_analysis_tool
- **Focus**: Quality assessment, curation

## Process Types

### Hierarchical Process (Recommended)

Manager agent coordinates subordinate agents dynamically:

```python
orchestrator = create_crewai_orchestrator(process_type="hierarchical")
```

Benefits:
- Dynamic task assignment
- Flexible workflow adaptation
- Manager ensures quality thresholds
- Better for complex queries

### Sequential Process

Tasks execute in fixed order:

```python
orchestrator = create_crewai_orchestrator(process_type="sequential")
```

Benefits:
- Simpler coordination
- Predictable execution
- Lower overhead
- Better for standard queries

## Memory System

Custom Redis memory provider integrates with existing infrastructure:

```python
from memory.redis_memory_provider import create_redis_memory_provider

# Create memory provider for session
memory = create_redis_memory_provider(session_id="user_123")

# Save short-term memory
await memory.save_short_term({"message": "user query", "response": "..."})

# Save long-term preferences
await memory.save_long_term("preferred_style", "casual")

# Save entities
await memory.save_entity("product", "dress_123", metadata={...})
```

## Testing

### Unit Tests

Test individual tools:

```python
from tools.neo4j_tools import neo4j_query_tool

products = neo4j_query_tool(
    cypher="MATCH (p:Product) RETURN p LIMIT 5",
    parameters={}
)

assert len(products) > 0
```

### Integration Tests

Test complete crew:

```python
from crews.product_search_crew import load_and_create_crew

crew = load_and_create_crew(process_type="hierarchical")
result = await crew.execute(
    query="red dress",
    limit=5
)

assert result['products']
assert result['metadata']
```

## Migration Checklist

- [x] Phase 1: Implement all CrewAI tools
- [x] Phase 2: Define agents in YAML
- [x] Phase 3: Define tasks in YAML
- [x] Phase 4: Implement crew assembly
- [x] Phase 5: Implement Redis memory provider
- [x] Phase 6: Implement CrewAI orchestrator
- [ ] Integration testing with existing system
- [ ] Performance benchmarking vs CAMEL
- [ ] Production deployment

## API Compatibility

CrewAIOrchestrator maintains full API compatibility with BattleOrchestrator:

```python
# Same method signature
await orchestrator.execute_search(
    query=query,
    filters=filters,
    limit=limit,
    user_context=user_context,
    ml_intelligence=ml_intelligence,
    conversation_context=conversation_context,
    bypass_cache=bypass_cache
)

# Same response format
{
    "products": [...],
    "reasoning": "...",
    "metadata": {
        "graph_count": 10,
        "vector_count": 8,
        "visual_count": 5,
        "execution_time": 1.23
    }
}
```

## Performance Considerations

### Caching

CrewAI orchestrator uses same caching strategy as BattleOrchestrator:
- 180-second TTL for search results
- SHA256 cache keys for deterministic lookups
- Compatible with existing Redis cache

### Optimization

- Parallel tool execution where possible
- Redis connection pooling
- Query result caching
- Efficient task dependencies

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure all dependencies installed
pip install -r requirements.txt
```

**Tool Execution Failures**
```python
# Check tool imports in agent_loader.py
# Verify database connections
```

**Memory Issues**
```python
# Verify Redis connection
# Check session_id format
```

### Logging

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Next Steps

1. Run integration tests with existing ARI system
2. Compare performance metrics with CAMEL implementation
3. Deploy to staging environment
4. Monitor production metrics
5. Gradual rollout with feature flags

## Documentation

- Migration Plan: `/MIGRATION_CAMEL_TO_CREWAI.md`
- CrewAI Docs: https://docs.crewai.com
- Original ARI README: `/README.md`

## Support

For issues or questions about the migration:
1. Check migration documentation
2. Review CrewAI documentation
3. Test with verbose logging enabled
