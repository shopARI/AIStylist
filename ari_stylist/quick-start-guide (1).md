# AI Stylist Quick Start Guide

This guide provides the quickest path to get the AI Stylist system up and running.

## Prerequisites

- Python 3.8+
- Access to a Neo4j database
- OpenAI API key

## 1. Installation

```bash
# Clone repository (replace with your actual repo)
git clone https://github.com/yourusername/ai-stylist.git
cd ai-stylist

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install neo4j openai flask python-dotenv camel-ai qdrant-client numpy requests
```

## 2. Configuration

Create a `.env` file in the project root:

```
NEO4J_URL=bolt://34.135.40.119:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=shopari1234
OPENAI_API_KEY=your-openai-api-key
```

## 3. Initialize Database Schema

```bash
python production_schema_init.py
```

## 4. Start the Service

```bash
python stylist_service.py
```

This will start the AI Stylist service and a Flask REST API on port 5000.

## 5. Test the Service

Send a test message using curl:

```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need an outfit for a summer wedding", "user_id": "test_user"}'
```

Or visit [http://localhost:5000/health](http://localhost:5000/health) in your browser to check the service status.

## 6. Common Commands

```bash
# Get service statistics
curl http://localhost:5000/stats

# Get information about a session
curl http://localhost:5000/session/{session_id}

# Send a follow-up message
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Do you have any accessories to match?", "session_id": "{session_id}"}'
```

## Troubleshooting

- **Connection issues**: Verify Neo4j credentials and OpenAI API key
- **No products found**: Ensure your Neo4j database contains products with the expected schema
- **High memory usage**: Reduce worker threads by setting `NUM_WORKER_THREADS=2` in `.env`
- **Slow responses**: Check Neo4j performance and connection speed

For more detailed information, refer to the complete README.md.

