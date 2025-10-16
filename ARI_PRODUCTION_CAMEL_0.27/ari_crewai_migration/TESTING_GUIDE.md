# Testing Guide for CrewAI Migration

## Test Files Created

### Unit Tests

1. **test_neo4j_tools.py**
   - Tests Neo4j connection
   - Tests semantic query expansion
   - Tests fulltext search
   - Validates actual database queries

2. **test_qdrant_tools.py**
   - Tests Qdrant connection
   - Tests embedding generation
   - Tests vector search
   - Tests hybrid search

3. **test_connections_simple.py**
   - Simple standalone connection tests
   - No CrewAI dependencies
   - Tests Neo4j, Qdrant, OpenAI

## Environment Configuration

From `.env` file:

### Neo4j
- URL: `neo4j://34.135.40.119:7687`
- Username: `neo4j`
- Password: `shopari1234`
- Database: `productionbackup2`
- Size: 6.4M+ products

### Qdrant
- URL: `https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io:6333`
- Collection: `fashion_products`
- Visual Collection: `fashion_multimodal_embeddings`

### OpenAI
- API key configured for embeddings
- Model: `text-embedding-3-small`

## Running Tests

### Option 1: Install Dependencies

```bash
cd ari_crewai_migration

# Install requirements
pip install -r requirements.txt

# Run specific test
python tests/test_neo4j_tools.py
python tests/test_qdrant_tools.py

# Or use pytest
pytest tests/
```

### Option 2: Simple Connection Test

```bash
cd ari_crewai_migration/tests

# Run without CrewAI dependencies
python test_connections_simple.py
```

### Option 3: Run All Tests

```bash
cd ari_crewai_migration/tests
python run_tests.py
```

## Test Coverage

### Neo4j Tool Tests

**TestNeo4jConnection**
- `test_environment_variables()` - Verify env vars set
- `test_simple_query()` - Basic MATCH query
- `test_product_count()` - Count total products
- `test_category_search()` - Search by category

**TestSemanticExpansion**
- `test_basic_expansion()` - Basic synonym expansion
- `test_occasion_expansion()` - Context-aware expansion
- `test_category_synonyms()` - Category mapping

**TestFulltextSearch**
- `test_simple_fulltext_search()` - Basic fulltext
- `test_fulltext_with_filters()` - With category filter
- `test_complex_search_string()` - AND/OR operators

### Qdrant Tool Tests

**TestQdrantConnection**
- `test_environment_variables()` - Verify env vars
- `test_collection_exists()` - Check collection access

**TestEmbeddingGeneration**
- `test_openai_key()` - Verify API key
- `test_generate_embedding()` - Generate embedding
- `test_embedding_consistency()` - Same text consistency

**TestQdrantSearch**
- `test_basic_search()` - Basic vector search
- `test_search_with_filters()` - Filtered search
- `test_hybrid_search()` - Text to search pipeline

## Expected Results

### Neo4j Tests

Should see:
```
Total products in database: 6,400,000+
Found products by category
Semantic expansion with synonyms
Fulltext search with scores
```

### Qdrant Tests

Should see:
```
Collection points: [count]
Vector dimension: 1536
Generated embeddings
Search results with scores
```

### OpenAI Tests

Should see:
```
Embedding dimension: 1536
Successful API calls
Consistent embeddings
```

## Troubleshooting

### Connection Timeouts

If tests timeout:
```bash
# Increase timeout in test
export NEO4J_CONNECTION_TIMEOUT=30
export QDRANT_TIMEOUT=90
```

### Import Errors

If crewai_tools not found:
```bash
pip install crewai crewai-tools
```

### Authentication Errors

Check `.env` file:
- Neo4j credentials correct
- Qdrant API key valid
- OpenAI API key active

### Network Issues

Verify connectivity:
```bash
# Test Neo4j
nc -zv 34.135.40.119 7687

# Test Qdrant (HTTPS)
curl -I https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io:6333
```

## Manual Testing

### Test Neo4j Connection

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "neo4j://34.135.40.119:7687",
    auth=("neo4j", "shopari1234")
)

with driver.session() as session:
    result = session.run("MATCH (p:Product) RETURN count(p)")
    print(result.single()['count(p)'])

driver.close()
```

### Test Qdrant Connection

```python
from qdrant_client import QdrantClient

client = QdrantClient(
    url="https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io:6333",
    api_key="[your-key]"
)

info = client.get_collection("fashion_products")
print(f"Points: {info.points_count}")
```

### Test OpenAI Embeddings

```python
import openai

openai.api_key = "[your-key]"

response = openai.embeddings.create(
    input="black dress",
    model="text-embedding-3-small"
)

embedding = response.data[0].embedding
print(f"Dimension: {len(embedding)}")
```

## Integration Testing

After unit tests pass, test full crew:

```python
from crews.crewai_orchestrator import create_crewai_orchestrator

# Create orchestrator
orchestrator = create_crewai_orchestrator(process_type="hierarchical")

# Execute search
result = await orchestrator.execute_search(
    query="black dress for wedding",
    filters={"category": "dress"},
    limit=5
)

print(f"Products found: {len(result['products'])}")
print(f"Reasoning: {result['reasoning']}")
```

## Performance Benchmarks

Compare with CAMEL implementation:

### Metrics to Compare
- Response time (target: < 3s)
- Cache hit rate (target: > 60%)
- Product relevance (manual review)
- Quality score distribution
- Memory usage
- Database query count

### Benchmark Script

```python
import time
import asyncio

async def benchmark_search(orchestrator, queries):
    results = []

    for query in queries:
        start = time.time()
        result = await orchestrator.execute_search(query=query, limit=5)
        elapsed = time.time() - start

        results.append({
            'query': query,
            'time': elapsed,
            'products': len(result['products']),
            'cached': result.get('metadata', {}).get('cached', False)
        })

    return results
```

## Next Steps

1. Run unit tests to validate tools
2. Fix any connection issues
3. Run integration tests with full crew
4. Performance benchmark against CAMEL
5. A/B testing in staging environment
