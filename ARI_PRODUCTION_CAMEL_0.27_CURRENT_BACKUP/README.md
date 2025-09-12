# 🎨 ARI Fashion AI System

> **Production-Ready AI-Powered Fashion Stylist with Conversational Recommendation Engine**

ARI (AI Recommendation Intelligence) is a sophisticated multi-agent fashion AI system that provides personalized style recommendations through natural language conversations. Built with production-grade architecture featuring Redis integration, distributed state management, and comprehensive agent orchestration.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Redis server
- Neo4j database
- Qdrant vector database
- OpenAI API access

### Installation & Setup

1. **Clone and navigate to the project**:
```bash
cd ARI_PRODUCTION_CAMEL_0.27
```

2. **Configure environment variables**:
```bash
cp .env.example .env  # Edit with your credentials
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Run the application**:
```bash
# Development server
python main.py

# Production server
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                  │
│                  (main.py - Port 8000)                 │
├─────────────────────┬───────────────────────────────────┤
│   REST API /chat    │      WebSocket /ws/{session}     │
├─────────────────────┴───────────────────────────────────┤
│                ApplicationService                       │
│            (services/application.py)                    │
├─────────────────────────────────────────────────────────┤
│                 Multi-Agent System                      │
│  ┌─────────────┬─────────────┬─────────────────────────┐ │
│  │  CypherBot  │   VibeBot   │    Intelligence ML      │ │
│  │ (Graph DB)  │  (Semantic) │    (Behavioral AI)     │ │
│  └─────────────┴─────────────┴─────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                  Data Layer                             │
│  ┌─────────────┬─────────────┬─────────────────────────┐ │
│  │    Neo4j    │   Qdrant    │        Redis           │ │
│  │ (Knowledge  │  (Vector    │    (Cache/State)       │ │
│  │   Graph)    │   Search)   │                        │ │
│  └─────────────┴─────────────┴─────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 🧠 AI Agent System

### Core Agents

#### 🤖 **CypherBot** (`agents/cypher_bot.py`)
- Generates and executes Neo4j Cypher queries
- Manages user knowledge graphs
- Handles complex product relationship queries

#### 🎯 **VibeBot** (`agents/vibe_bot.py`) 
- Semantic search using vector embeddings
- Style preference matching
- Context-aware product discovery

#### ⚖️ **Judge ARI** (`agents/judge.py`)
- Final decision orchestration
- Product ranking and selection
- Quality assurance filtering

### Battle System (`services/battle/`)
- **Orchestrator**: Coordinates agent competition
- **Metrics**: Performance tracking and optimization
- **Executor**: Parallel agent execution
- **Optimizer**: Dynamic strategy adjustment

## 🛠️ Key Features

### 💬 Conversational Interface
- Natural language processing
- Context-aware recommendations
- Session-based memory management
- Multi-turn conversation support

### 🎨 Fashion Intelligence
- Style preference learning
- Occasion-based recommendations
- Budget-conscious filtering
- Brand and category preferences

### 🔄 Real-time Capabilities
- WebSocket support for instant responses
- Live agent monitoring
- Dynamic product updates
- Performance metrics tracking

### 🏢 Production Features
- Dependency injection container
- Distributed state management
- Redis caching layer
- Comprehensive error handling
- Health monitoring endpoints

## 📁 Project Structure

```
ARI_PRODUCTION_CAMEL_0.27/
├── agents/                 # AI Agent implementations
│   ├── cypher_bot.py      # Neo4j graph database agent
│   ├── vibe_bot.py        # Semantic search agent
│   ├── judge.py           # Decision orchestration agent
│   └── base.py            # Base agent interface
├── services/              # Core business logic
│   ├── application.py     # Main application service
│   ├── battle/            # Agent competition system
│   ├── conversation_handler.py
│   ├── data/              # Data access layer
│   ├── memory/            # Memory management
│   ├── nlp/               # Natural language processing
│   ├── product/           # Product retrieval logic
│   └── user/              # User knowledge management
├── config/                # Configuration management
│   ├── settings.py        # Application settings
│   └── prompts.py         # AI prompt templates
├── models/                # Data models
│   ├── products.py        # Product data structures
│   └── types.py           # Common type definitions
├── di/                    # Dependency injection
│   └── container.py       # DI container setup
├── migrations/            # Database migrations
├── web_interface_dev/     # Streamlit development UI
├── tests/                 # Test suite
├── main.py               # FastAPI application entry point
└── .env                  # Environment configuration
```

## 🔧 Configuration

### Environment Variables

```bash
# Database Connections
NEO4J_URL=bolt://your-neo4j-host:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Vector Database
QDRANT_URL=https://your-qdrant-cluster.qdrant.io
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION_NAME=fashion_products

# AI Services
OPENAI_API_KEY=your-openai-key

# Performance Tuning
QDRANT_TIMEOUT=60.0
OPENAI_REQUEST_TIMEOUT=60
NEO4J_QUERY_TIMEOUT=60.0
BATTLE_TIMEOUT=60.0
NUM_WORKER_THREADS=4

# Application
API_PORT=8000
MEMORY_TOKEN_LIMIT=1024
ENABLE_MCP=true
```

## 🌐 API Endpoints

### REST API

#### `POST /chat`
Main chat endpoint for fashion recommendations.

**Request:**
```json
{
  "message": "I need a dress for a wedding",
  "session_id": "optional-session-id",
  "user_id": "optional-user-id"
}
```

**Response:**
```json
{
  "response": "I'd be happy to help you find the perfect wedding dress...",
  "products": [
    {
      "id": "prod-123",
      "title": "Elegant Wedding Dress",
      "price": 299.99,
      "category": "dresses"
    }
  ],
  "session_id": "session-uuid",
  "metadata": {
    "processing_time": 1.23,
    "agents_used": ["cypher_bot", "vibe_bot", "judge"]
  }
}
```

#### `GET /`
Health check endpoint.

### WebSocket API

#### `WS /ws/{session_id}`
Real-time chat interface for streaming responses.

## 🖥️ Development Interface

### Streamlit Web Interface
```bash
cd web_interface_dev
python run_streamlit.py
```

Features:
- Interactive chat interface
- Real-time agent monitoring
- Performance metrics
- Conversation history
- Product visualization

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test modules
python -m pytest tests/test_camel_070.py
python -m pytest tests/test_camel_migration.py
```

## 📊 Monitoring & Performance

### Metrics Available
- Agent response times
- Query processing performance  
- Cache hit rates
- Database connection health
- Memory usage patterns

### Logging
- Structured JSON logging
- Multiple log levels (INFO, ERROR, DEBUG)
- Agent-specific logging channels
- Request/response tracking

## 🔄 Deployment

### Production Checklist
- [ ] Environment variables configured
- [ ] Database connections established
- [ ] Redis cache operational
- [ ] API keys validated
- [ ] Health checks passing
- [ ] Performance metrics baseline established

### Docker Deployment (Recommended)
```bash
# Build image
docker build -t ari-fashion-ai .

# Run container
docker run -p 8000:8000 --env-file .env ari-fashion-ai
```

## 🤝 Contributing

1. Follow existing code patterns and architecture
2. Add tests for new features
3. Update documentation as needed
4. Ensure all agents maintain backward compatibility

## 📄 License

This project is proprietary software. All rights reserved.

## 🆘 Support

For technical issues or questions:
- Check the `/health` endpoint for system status
- Review logs in the application output
- Monitor agent performance metrics
- Verify database connectivity

---

**Built with**: FastAPI, Neo4j, Qdrant, OpenAI, Redis, CAMEL-AI Framework
**Version**: 4.0.0 (Production Ready)