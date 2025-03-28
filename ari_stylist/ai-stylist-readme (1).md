# AI Stylist (Ari)

A conversational fashion advisor that provides personalized style recommendations using Neo4j knowledge graph, CAMEL framework, and OpenAI language models.

## Overview

The AI Stylist (named Ari) is a conversational agent designed to recommend fashion products based on user preferences. It uses:

- **Neo4j** knowledge graph for product data storage and retrieval
- **CAMEL framework** for agent capabilities and memory
- **OpenAI language models** for natural conversation

## System Requirements

- Python 3.8 or higher
- Neo4j database (accessible via Bolt protocol)
- OpenAI API key
- Sufficient RAM for concurrent sessions (recommended: 4GB+)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-stylist.git
cd ai-stylist
```

### 2. Set Up a Virtual Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages (for requirements.txt):

```
neo4j==4.4.10
openai==1.3.0
flask==2.3.3
python-dotenv==1.0.0
camel-ai==0.1.2
qdrant-client==1.6.3
numpy==1.24.3
requests==2.31.0
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```
# Neo4j Connection Settings
NEO4J_URL=bolt://your-neo4j-server:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# OpenAI API Key
OPENAI_API_KEY=your-openai-api-key

# Service Configuration
NUM_WORKER_THREADS=4
API_PORT=5000
```

## Database Setup

### Initialize the Database Schema

Run the schema initialization script to set up the required constraints and indexes:

```bash
python production_schema_init.py
```

This script creates constraints and indexes for the following node types:
- Product
- Category
- Collection
- Tag

And the following relationship types:
- IN_CATEGORY
- IN_COLLECTION
- TAGGED_WITH

### Expected Database Structure

The system expects products to be structured as follows:

```
(:Product {
    id: "product-id",
    title: "Product Title",
    price: 99.99,
    description: "Product description",
    images: "[\"https://example.com/image.jpg\"]",
    visited_num: 0
})
```

Connected to categories, collections, and tags:

```
(p:Product)-[:IN_CATEGORY]->(c:Category {title: "Category Name"})
(p:Product)-[:IN_COLLECTION]->(c:Collection {title: "Collection Name"})
(p:Product)-[:TAGGED_WITH]->(t:Tag {title: "Tag Name"})
```

## Running the System

### As a Service (Recommended)

Start the AI Stylist as a service with a REST API:

```bash
python stylist_service.py
```

This launches:
- A multi-threaded service for processing messages
- A Flask REST API on port 5000 (configurable in .env)

### API Endpoints

- `GET /health` - Health check and service statistics
- `POST /chat` - Process messages
- `GET /session/{session_id}` - Get session information
- `GET /stats` - Get service statistics

#### Chat Example

```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need something to wear to a summer wedding", "user_id": "user123"}'
```

### As a Library

Import and use the AI Stylist in your Python code:

```python
from ai_stylist_app import AIStylistApp

# Initialize the app
app = AIStylistApp()

# Create a session
session_id = app.create_session(user_id="user123")

# Send a message
response, data = app.send_message(
    session_id, 
    "I need a dress for a summer wedding"
)

print(f"Ari: {response}")

# Clean up when done
app.close()
```

## Module Structure

- `ai_stylist_app.py` - Main application entry point
- `chat_session_manager.py` - Session and conversation management
- `memory_integration.py` - CAMEL memory system integration
- `neo4j_integration.py` - Neo4j database integration
- `product_retriever.py` - Vector-based product retrieval
- `stylist_agent.py` - Conversational agent configuration
- `stylist_service.py` - Multi-threaded service with REST API
- `production_schema_init.py` - Database schema initialization

## Performance Considerations

- **Memory Usage**: Each active session consumes memory for the conversation history and agent state
- **API Rate Limits**: Be mindful of OpenAI API rate limits, especially with multiple concurrent users
- **Database Connection**: Ensure your Neo4j database can handle concurrent connections
- **Worker Threads**: Adjust `NUM_WORKER_THREADS` based on your server capabilities

## Troubleshooting

### Common Issues

1. **Neo4j Connection Errors**
   - Verify the Neo4j server is running
   - Check connection credentials in `.env`
   - Ensure the Bolt protocol is enabled

2. **OpenAI API Errors**
   - Verify the API key is correct
   - Check for API rate limits or quotas

3. **Missing Products in Responses**
   - Verify the database contains products with proper relationships
   - Check that products have required properties (id, title, price)
   - Run `python production_schema_init.py` to verify schema

4. **High Memory Usage**
   - Decrease the number of worker threads
   - Implement more aggressive session cleanup (modify session timeout)

5. **Slow Response Times**
   - Optimize Neo4j queries with appropriate indexes
   - Check Neo4j server performance
   - Consider upgrading to a more powerful OpenAI model

### Logs

Check the logs for detailed information:

- Console output
- `stylist_service.log` file

## License

[Specify your license here]

## Contributors

[List contributors here]

## Acknowledgements

- CAMEL AI framework
- Neo4j Graph Database
- OpenAI API
