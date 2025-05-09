# AI Stylist: Comprehensive Documentation

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Key Components](#key-components)
4. [Setup and Installation](#setup-and-installation)
5. [Configuration](#configuration)
6. [API Documentation](#api-documentation)
7. [Usage Examples](#usage-examples)
8. [Extending the System](#extending-the-system)
9. [Troubleshooting](#troubleshooting)

## Overview

AI Stylist is an intelligent fashion recommendation system built on the CAMEL-AI framework that provides personalized clothing recommendations, fashion advice, and natural conversational interactions. The system combines several advanced recommendation techniques including:

- Content-based filtering
- Collaborative filtering
- Visual similarity
- RFM (Recency, Frequency, Monetary) analysis
- Memory-based personalization
- Ensemble recommendations

The entire system is built with asynchronous processing at its core, enabling high throughput and responsiveness even under load.

## System Architecture

The system uses a combination of Neo4j for persistent storage and knowledge graphs, Qdrant for vector-based similarity search, and CAMEL-AI for large language model interactions. The architecture follows an asynchronous design pattern throughout, allowing for high concurrency and resource efficiency.

### Architecture Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌────────────────┐
│                 │     │                 │     │                │
│  FastAPI        │◄────┤  AI Stylist App │◄────┤  Neo4j        │
│  Service Layer  │     │  Core           │     │  Database      │
│                 │     │                 │     │                │
└────────┬────────┘     └────────┬────────┘     └────────────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌────────────────┐
│                 │     │                 │     │                │
│  Chat Session   │◄────┤  Recommender    │◄────┤  Qdrant Vector │
│  Manager        │     │  Manager        │     │  Database      │
│                 │     │                 │     │                │
└────────┬────────┘     └────────┬────────┘     └────────────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │
│  Memory         │◄────┤  Product        │
│  Integration    │     │  Retriever      │
│                 │     │                 │
└─────────────────┘     └─────────────────┘
```

## Key Components

### Core Components

1. **ai_stylist_app_async.py**
   - Main application entry point
   - Orchestrates all components
   - Manages cross-session memory

2. **async_camel_service.py**
   - Provides asynchronous interface to CAMEL-AI
   - Manages thread pools for CPU-intensive operations
   - Handles message processing and memory interactions

3. **chat_session_manager_async.py**
   - Manages user conversation sessions
   - Provides intent detection and context management
   - Routes messages to appropriate handlers

4. **stylist_agent_async.py**
   - Implements the stylist agent with LLM integration
   - Creates and manages agent prompts
   - Provides specialized agents for specific tasks

5. **stylist_service_async.py**
   - FastAPI service layer
   - Exposes RESTful API endpoints
   - Handles request routing and response formatting

### Recommendation Systems

1. **enhanced_recommender_manager_async.py**
   - Orchestrates multiple recommendation strategies
   - Manages the creation and initialization of recommenders
   - Routes recommendation requests to appropriate systems

2. **ensemble_recommender.py**
   - Combines recommendations from multiple sources
   - Applies weighted voting to select best recommendations
   - Provides explanation generation for recommendations

3. **hybrid_visual_recommender.py**
   - Uses image embeddings for visual similarity
   - Combines visual and semantic similarity
   - Provides fashion-specific visual recommendations

4. **memory_rag_recommender.py**
   - Uses Retrieval-Augmented Generation (RAG) with memory
   - Personalizes recommendations based on user history
   - Leverages conversational context for better recommendations

5. **multi_cluster_recommender.py**
   - Implements clustering-based recommendations
   - Groups similar products for better discovery
   - Matches users to product clusters

6. **rfm_apriori_recommender_async.py**
   - Implements RFM (Recency, Frequency, Monetary) analysis
   - Uses association rule mining with Apriori algorithm
   - Discovers purchase patterns and product affinities

### Data Integration

1. **neo4j_integration_async.py**
   - Provides asynchronous interface to Neo4j
   - Implements the product knowledge graph
   - Handles user data and preference persistence

2. **openai_embedding_adapter.py**
   - Ensures compatibility with OpenAI embeddings
   - Handles API version differences
   - Provides fallbacks for embedding generation

3. **product_retriever_async.py**
   - Implements vector-based product search
   - Integrates with Qdrant for similarity search
   - Provides natural language search capabilities

4. **memory_integration_async.py**
   - Manages persistent memory across sessions
   - Implements memory serialization and deserialization
   - Provides memory optimization and context retrieval

## Setup and Installation

### Prerequisites

- Python 3.9 or higher
- Neo4j database (v4.4+)
- Qdrant vector database (optional but recommended)
- OpenAI API key for embeddings

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-organization/ai-stylist.git
   cd ai-stylist
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables:**
   Create a `.env` file with the following variables:
   ```
   # OpenAI API
   OPENAI_API_KEY=your_openai_api_key
   
   # Neo4j Database
   NEO4J_URL=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   
   # Qdrant Vector Database
   QDRANT_URL=http://localhost:6333
   QDRANT_API_KEY=your_qdrant_api_key
   QDRANT_COLLECTION_NAME=products
   
   # Service Configuration
   HOST=0.0.0.0
   PORT=8000
   NUM_WORKER_TASKS=4
   ```

5. **Initialize Neo4j database:**
   Run the setup script to create the Neo4j schema:
   ```bash
   python scripts/setup_neo4j_schema.py
   ```

6. **Populate product data:**
   Add product data to the system:
   ```bash
   python scripts/import_products.py --file your_product_data.csv
   ```

7. **Start the service:**
   ```bash
   python stylist_service_async.py
   ```
   
   Alternatively, use uvicorn directly:
   ```bash
   uvicorn stylist_service_async:app --host 0.0.0.0 --port 8000
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings | None (Required) |
| `NEO4J_URL` | Neo4j database URL | bolt://localhost:7687 |
| `NEO4J_USERNAME` | Neo4j username | neo4j |
| `NEO4J_PASSWORD` | Neo4j password | None (Required) |
| `QDRANT_URL` | Qdrant vector DB URL | None (Optional) |
| `QDRANT_API_KEY` | Qdrant API key | None (Optional) |
| `QDRANT_COLLECTION_NAME` | Qdrant collection name | products |
| `HOST` | Service host | 0.0.0.0 |
| `PORT` | Service port | 8000 |
| `NUM_WORKER_TASKS` | Number of worker tasks | 4 |

### Product Data Format

The system expects product data with the following attributes:

- `id`: Unique product identifier
- `title`: Product title/name
- `description`: Product description
- `price`: Product price (numeric)
- `images`: List of image URLs
- `categories`: List of product categories
- `tags`: List of product tags
- `collections`: List of collections the product belongs to

Example CSV format:
```
id,title,description,price,images,categories,tags,collections
prod001,Summer Dress,"Light summer dress",49.99,"['http://example.com/img1.jpg']","['dress','women']","['summer','casual']","['Summer 2023']"
```

## API Documentation

### Chat API

#### POST /chat
Process a user message and get a stylist response.

**Request:**
```json
{
  "message": "Can you recommend a dress for a summer wedding?",
  "user_id": "user123",
  "session_id": "session456"
}
```

**Response:**
```json
{
  "message_id": "msg_12345",
  "session_id": "session456",
  "response": "For a summer wedding, I'd recommend a lightweight floral dress...",
  "data": {
    "products": [
      {
        "id": "prod123",
        "title": "Floral Maxi Dress",
        "price": 89.99,
        "images": ["http://example.com/img1.jpg"]
      }
    ]
  },
  "processing_time": 1.23,
  "success": true
}
```

### Session API

#### GET /session/{session_id}
Get information about a session.

**Response:**
```json
{
  "session_id": "session456",
  "exists": true,
  "user_id": "user123",
  "start_time": "2023-07-01T12:34:56",
  "last_activity": 1688213696.123,
  "time_since_activity": 120.5,
  "message_count": 10,
  "last_messages": [
    {
      "id": "msg_12345",
      "content": "Can you recommend a dress for a summer wedding?",
      "sender": "user",
      "timestamp": "2023-07-01T12:34:56"
    }
  ]
}
```

### Recommendations API

#### POST /recommendations
Get product recommendations.

**Request Parameters:**
- `session_id`: Session ID
- `product_id` (optional): Product ID for similar products
- `query` (optional): Search query
- `limit` (optional, default=5): Maximum number of recommendations

**Response:**
```json
{
  "session_id": "session456",
  "recommendations": [
    {
      "id": "prod123",
      "title": "Floral Maxi Dress",
      "price": 89.99,
      "images": ["http://example.com/img1.jpg"],
      "categories": ["dress", "women"],
      "tags": ["summer", "wedding"]
    }
  ],
  "count": 1
}
```

### Interaction API

#### POST /interaction
Record a product interaction.

**Request Parameters:**
- `session_id`: Session ID
- `product_id`: Product ID
- `interaction_type`: Type of interaction (viewed, liked, purchased)

**Response:**
```json
{
  "session_id": "session456",
  "product_id": "prod123",
  "interaction_type": "viewed",
  "success": true
}
```

### Preference API

#### POST /preference
Add a user preference.

**Request Parameters:**
- `session_id`: Session ID
- `preference_type`: Type of preference (color, style, budget)
- `preference_value`: Value of the preference

**Response:**
```json
{
  "session_id": "session456",
  "preference_type": "color",
  "success": true
}
```

## Usage Examples

### Basic Chat Interaction

```python
import requests

API_URL = "http://localhost:8000"

# Start a conversation
response = requests.post(f"{API_URL}/chat", json={
    "message": "I need a dress for a summer wedding",
    "user_id": "user123"
})

data = response.json()
session_id = data["session_id"]
print(f"Stylist: {data['response']}")

# Continue the conversation
response = requests.post(f"{API_URL}/chat", json={
    "message": "I prefer something in blue",
    "session_id": session_id
})

data = response.json()
print(f"Stylist: {data['response']}")

# Record an interaction with a product
if "products" in data["data"]:
    product_id = data["data"]["products"][0]["id"]
    requests.post(f"{API_URL}/interaction", json={
        "session_id": session_id,
        "product_id": product_id,
        "interaction_type": "viewed"
    })

# Add a preference
requests.post(f"{API_URL}/preference", json={
    "session_id": session_id,
    "preference_type": "color",
    "preference_value": "blue"
})
```

### Getting Recommendations

```python
import requests

API_URL = "http://localhost:8000"

# Get recommendations for a specific session
response = requests.post(f"{API_URL}/recommendations", json={
    "session_id": "session123",
    "query": "summer dress",
    "limit": 10
})

recommendations = response.json()["recommendations"]
for product in recommendations:
    print(f"{product['title']} - ${product['price']}")

# Get similar products
response = requests.post(f"{API_URL}/recommendations", json={
    "session_id": "session123",
    "product_id": "prod456",
    "limit": 5
})

similar_products = response.json()["recommendations"]
for product in similar_products:
    print(f"{product['title']} - ${product['price']}")
```

## Extending the System

### Adding a New Recommender

1. Create a new recommender class in a separate file:
   ```python
   # my_custom_recommender.py
   class MyCustomRecommender:
       def __init__(self, product_kg):
           self.product_kg = product_kg
           
       async def get_recommendations(self, user_id=None, product_id=None, limit=5):
           # Implementation
           return recommendations
   ```

2. Add the recommender to the enhanced recommender manager:
   ```python
   # enhanced_recommender_manager_async.py
   from my_custom_recommender import MyCustomRecommender
   
   def create_all_recommenders(self, initialize_data=False):
       # ... existing code ...
       
       # Create MyCustomRecommender
       custom = self.create_custom_recommender()
       if custom:
           self.recommenders['custom'] = custom
           
   def create_custom_recommender(self):
       try:
           recommender = MyCustomRecommender(
               product_kg=self.product_kg
           )
           
           logger.info("Created MyCustomRecommender")
           return recommender
           
       except Exception as e:
           logger.error(f"Error creating MyCustomRecommender: {e}")
           return None
   ```

3. Add the recommender to the ensemble:
   ```python
   # enhanced_recommender_manager_async.py
   def create_ensemble_recommender(self):
       # ... existing code ...
       
       # Add the custom recommender to the ensemble
       if 'custom' in self.recommenders:
           ensemble.add_recommender(self.recommenders['custom'], weight=1.0, name='custom')
   ```

### Adding a New API Endpoint

1. Add the endpoint in `stylist_service_async.py`:
   ```python
   @app.post("/custom_endpoint", response_model=Dict[str, Any])
   async def custom_endpoint(
       param1: str,
       param2: int = Query(10, ge=1, le=100),
       service: StylistServiceAsync = Depends(get_service)
   ):
       """Custom endpoint description"""
       try:
           result = await service.app.custom_method(param1, param2)
           return {
               "result": result,
               "success": True
           }
       except Exception as e:
           logger.error(f"Error in custom endpoint: {e}", exc_info=True)
           raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
   ```

2. Add the corresponding method in `ai_stylist_app_async.py`:
   ```python
   async def custom_method(self, param1: str, param2: int) -> Any:
       """
       Custom method implementation
       
       Args:
           param1: First parameter
           param2: Second parameter
           
       Returns:
           Custom result
       """
       # Implementation
       return result
   ```

## Troubleshooting

### Common Issues

1. **Neo4j Connection Errors**
   - **Symptom**: Error messages about Neo4j connection failures
   - **Solution**: 
     - Verify Neo4j server is running: `sudo systemctl status neo4j`
     - Check credentials in `.env` file
     - Ensure the Neo4j database allows remote connections if needed
     - Try connecting with Neo4j Browser to test connection

2. **Memory Issues**
   - **Symptom**: Service crashes with memory errors or high CPU
   - **Solution**:
     - Reduce `NUM_WORKER_TASKS` in configuration
     - Add memory limits to the service
     - Implement more aggressive context pruning in memory_integration_async.py

3. **Qdrant Vector Search Issues**
   - **Symptom**: Product search doesn't return expected results
   - **Solution**:
     - Ensure Qdrant is properly configured
     - Check if product data has been embedded correctly
     - Try manual search via Qdrant REST API to verify
     - Re-index product data with the `index_all_products` method

4. **LLM API Rate Limits**
   - **Symptom**: Errors related to OpenAI rate limits
   - **Solution**:
     - Adjust the `rate_limiter` configuration in `stylist_service_async.py`
     - Implement retry logic with exponential backoff
     - Consider upgrading OpenAI subscription tier

5. **Slow Response Times**
   - **Symptom**: API responses take longer than expected
   - **Solution**:
     - Implement caching for frequent queries
     - Pre-compute embeddings for popular products
     - Optimize database queries in Neo4j
     - Add request timeout handling

### Debugging

#### Enabling Debug Logging

```python
import logging

# Set logging level to DEBUG for more information
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug.log')
    ]
)
```

#### Testing the Recommendation Engine Directly

```python
# test_recommender.py
import asyncio
from ai_stylist_app_async import EnhancedAIStylistApp

async def test_recommendations():
    app = EnhancedAIStylistApp()
    
    # Create a session
    session_id = await app.create_session(user_id="test_user")
    
    # Get recommendations
    recommendations = await app.get_product_recommendations(
        session_id=session_id,
        query="summer dress",
        limit=5
    )
    
    print(f"Found {len(recommendations)} recommendations:")
    for rec in recommendations:
        print(f"- {rec.get('title', 'Unknown')} (${rec.get('price', 0.0)})")
    
    # Clean up
    await app.close()

if __name__ == "__main__":
    asyncio.run(test_recommendations())
```

#### Health Check Script

```python
# health_check.py
import asyncio
import httpx

async def check_service_health(url="http://localhost:8000"):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{url}/health")
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == "healthy":
                print("Service is healthy!")
                print(f"Active sessions: {data['stats']['active_sessions']}")
                print(f"Uptime: {data['stats']['uptime_seconds']:.2f} seconds")
                return True
            else:
                print(f"Service is not healthy! Status code: {response.status_code}")
                print(f"Response: {data}")
                return False
                
        except Exception as e:
            print(f"Error checking service health: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(check_service_health())
```
