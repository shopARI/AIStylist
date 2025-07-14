## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# 3. Update recommender methods for compatibility
python method_updater.py

# 4. Run tests (optional)
python integration_test_suite.py

# 5. Run the application
python ai_stylist_app_async.py
```

## Requirements

- Python 3.8+
- CAMEL-AI 0.2.64
- Neo4j 5.0+
- Qdrant 1.7+
- See `requirements.txt` for complete list

## Architecture Overview

```
┌─────────────────┐
│   Frontend App  │
└────────┬────────┘
         │
┌────────▼────────┐
│  AI Stylist App │  Main Entry Point
└────────┬────────┘
         │
┌────────▼────────────────────────┐
│     Chat Session Manager         │
- Handles conversations
  - Manages memory
  - Routes to battle system
└────────┬───────────┬────────────┘
         │           │
┌────────▼─────┐ ┌──▼──────────────┐
│Battle System │ │  Recommenders   │
│ - CypherBot  │ │ - Multi-cluster │
│ - VibeBot    │ │ - Visual search │
│ - Judge Ari  │ │ - RFM analysis  │
└──────┬───────┘ │ - Memory RAG    │
       │         └────────┬────────┘
       │                  │
┌──────▼──────────────────▼────────┐
│      HybridDataStore             │
│  Routes operations intelligently  │
└──────┬──────────────┬────────────┘
       │              │
┌──────▼──────┐ ┌────▼────────────┐
│   Neo4j     │ │     Qdrant      │
│   (Users)   │ │   (Products)    │
└─────────────┘ └─────────────────┘
```

## Key Components

### Core Application
- **`ai_stylist_app_async.py`** - Main application class
- **`chat_session_manager_async.py`** - Manages chat sessions and memory
- **`frontend_app.py`** - FastAPI endpoints for frontend

### Battle System
- **`battle_agents.py`** - CypherBot (graph search) vs VibeBot (vector search)
- **`competitive_search_system.py`** - Judge Ari decides the winner
- Products compete in real-time for each query!

### Data Layer
- **`hybrid_data_store.py`** - Intelligent routing between databases
- **`user_knowledge_graph_async.py`** - Neo4j for user data
- **`product_retriever_async_enhanced.py`** - Qdrant for product vectors

### AI & Recommendations
- **`enhanced_recommender_manager_async.py`** - Orchestrates all recommendation algorithms
- **`stylist_agent_async.py`** - AI fashion stylist personality

### Recommendation Algorithms (All 5 Methods)
1. **`multi_cluster_recommender.py`** - K-means clustering for product grouping
2. **`hybrid_visual_recommender.py`** - Visual similarity using ResNet embeddings
3. **`rfm_apriori_recommender_async.py`** - RFM analysis + Apriori association rules
4. **`memory_rag_recommender.py`** - RAG-based recommendations from conversation memory
5. **`ensemble_recommender.py`** - Combines all methods with weighted voting

## Frontend Integration

### Initialize the App
```python
from ai_stylist_app_async import EnhancedAIStylistApp

app = EnhancedAIStylistApp()
```

### Create a Session
```python
# For new user
session_id = await app.create_session()

# For returning user
session_id = await app.create_session(user_id="user123")
```

### Send Messages
```python
response, data = await app.send_message(
    session_id=session_id,
    message="I need a red dress for a wedding"
)

# Response contains the AI stylist's message
# Data contains:
# - products: List of recommended products
# - used_battle_system: Whether battle search was used
# - battle_winner: Which agent won (if battle was used)
```

### Get Recommendations
```python
# Direct product recommendations (uses all 5 algorithms)
products = await app.get_product_recommendations(
    session_id=session_id,
    query="summer dresses",
    limit=5
)

# Similar products (emphasizes visual + cluster methods)
similar = await app.get_product_recommendations(
    session_id=session_id,
    product_id="prod_123",
    limit=5
)

# Personalized for user (emphasizes RFM + Memory RAG)
personalized = await app.get_product_recommendations(
    session_id=session_id,
    user_id="user_123",
    limit=5
)
```

## Recommendation System Explained

The system uses 5 advanced recommendation algorithms that work together:

### 1. Multi-Cluster Recommender
- Uses K-means clustering to group similar products
- Finds products in the same style cluster
- Great for "more like this" recommendations

### 2. Hybrid Visual Recommender  
- Analyzes product images using ResNet
- Finds visually similar items
- Perfect for "same look, different price" searches

### 3. RFM + Apriori Recommender
- **RFM Analysis**: Segments users by Recency, Frequency, Monetary value
- **Apriori Algorithm**: Finds products frequently bought together
- Creates "customers also bought" recommendations

### 4. Memory RAG Recommender
- Uses conversation history to understand preferences
- Retrieval-Augmented Generation from past interactions
- Provides highly personalized suggestions

### 5. Ensemble Recommender
- Combines all 4 methods with weighted voting
- Balances different recommendation strategies
- Delivers the best overall results

The `enhanced_recommender_manager_async.py` orchestrates all these methods based on the context:
- Similar product request? Visual + Cluster methods get higher weight
- User with history? RFM + Memory RAG get priority
- Cold start? Cluster + Visual methods take over

## Battle System Explained

When users search for products, two AI agents compete:

1. **CypherBot** - Uses Neo4j graph queries for precise matching
2. **VibeBot** - Uses Qdrant vector search for semantic understanding

**Judge Ari** evaluates both results and picks the winner based on:
- Relevance to query
- Product quality
- Price appropriateness
- Style matching

## Configuration

### Environment Variables (.env)
```bash
# Neo4j (User data)
NEO4J_URL=bolt://your-neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Qdrant (Product vectors)
QDRANT_URL=https://your-qdrant-instance
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION_NAME=products

# OpenAI (For AI features)
OPENAI_API_KEY=your-openai-key
```

## Data Model

### Users (Neo4j)
- User profiles
- Preferences
- Interaction history
- Style profiles

### Products (Qdrant)
- Product details
- Vector embeddings
- Categories & tags
- Visual features

## System Architecture Notes

### Current State
- **Neo4j**: Contains only user-related data (users, preferences, interactions)
- **Qdrant**: Should contain all product data with vector embeddings
- **HybridDataStore**: Automatically routes operations to the correct database

### Data Flow
1. User operations → Neo4j (via `user_knowledge_graph_async.py`)
2. Product operations → Qdrant (via `product_retriever_async_enhanced.py`)
3. Battle system queries both and Judge Ari picks the winner
4. All recommenders now use HybridDataStore for data access

## Testing

```bash
# Run integration tests
python integration_test_suite.py

# Test battle system
python -c "from test_utils import test_battle; test_battle()"
```

## Important Notes

1. **Memory Persistence**: User conversations are saved and restored across sessions
2. **Scalability**: Designed for 6M+ products with efficient vector search
3. **Real-time Competition**: Every search triggers a battle between agents
4. **Personalization**: Learns user preferences through RFM analysis and memory
5. **Association Rules**: Uses Apriori algorithm to find product relationships
6. **Visual Intelligence**: ResNet-based image analysis for style matching

## Migration Limitations

The current `migrate_products_to_qdrant.py` script has a limitation:
- It expects to read products from Neo4j using `ProductKnowledgeGraphAsync`
- However, `user_knowledge_graph_async.py` only handles user operations
- To migrate existing products from Neo4j, you'll need the original `neo4j_integration_async.py`
- Alternatively, products can be directly imported into Qdrant from other sources

## Troubleshooting

### Common Issues

1. **"users_queries" error in tests**
   - This is a known test issue with HybridDataStore
   - Does not affect actual functionality

2. **Method compatibility errors**
   - Run `python method_updater.py` to update recommender files
   - Creates `.backup` files for all modified files

3. **Connection refused errors**
   - Check your `.env` file has correct database URLs
   - Ensure Neo4j and Qdrant services are running

4. **Empty messages array error**
   - This is a CAMEL agent initialization issue
   - The system has automatic retry logic to handle this

### Backup Files

The `method_updater.py` creates backup files:
- `*.py.backup` files are original versions before method updates
- To restore: `mv filename.py.backup filename.py`

## Support

For issues or questions about:
- Frontend integration: Check `frontend_app.py`
- Battle system: See `battle_agents.py` and `competitive_search_system.py`
- Database queries: Check `hybrid_data_store.py`

## API Endpoints (from frontend_app.py)

### Session Management
- `POST /api/session` - Create new session
- `GET /api/session/{session_id}` - Get session info

### Chat & Recommendations  
- `POST /api/chat` - Send message and get response
- `POST /api/recommendations` - Get product recommendations

### User Management
- `POST /api/user/preferences` - Update user preferences
- `POST /api/user/interaction` - Record product interaction

See `frontend_app.py` for complete API documentation.

## Features

- AI-powered fashion advice with personality
- Competitive product search (Battle System)
- Visual similarity matching using ResNet
- Personalized recommendations using 5 algorithms:
  - K-means clustering for style grouping
  - Visual embeddings for image similarity
  - RFM segmentation for user behavior
  - Apriori algorithm for purchase patterns
  - Memory RAG for conversation context
- Persistent conversation memory across sessions
- Multi-algorithm ensemble with weighted voting
- Real-time battle system between search strategies
- Scalable to 6M+ products

---

Built with CAMEL-AI, Neo4j, and Qdrant

## File Organization

### Essential Files (20 total)
- **Core (4)**: `ai_stylist_app_async.py`, `chat_session_manager_async.py`, `enhanced_recommender_manager_async.py`, `frontend_app.py`
- **Data Layer (3)**: `user_knowledge_graph_async.py`, `product_retriever_async_enhanced.py`, `hybrid_data_store.py`
- **Battle System (2)**: `battle_agents.py`, `competitive_search_system.py`
- **AI Agents (2)**: `agent_factory.py`, `stylist_agent_async.py`
- **Recommenders (5)**: All five recommendation algorithm files
- **Support (4)**: `memory_integration_async.py`, `camel_imports.py`, `requirements.txt`, `.env`

### Test & Migration Files (Optional)
- `integration_test_suite.py` - Test the system
- `migration_runner.py` - Migrate products
- `method_updater.py` - Fix compatibility issues