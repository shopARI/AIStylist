# ARI Fashion AI System (Production)

> **Enterprise-Ready AI Fashion Stylist with Conversational Recommendations**  
> Built with CAMEL-AI 0.2.7 | Neo4j | Qdrant | Redis | FastAPI

## 🚀 Overview

ARI (AI Recommendation Intelligence) is a production-ready fashion AI system that provides personalized product recommendations through intelligent conversation. The system scales to handle **20-30M product nodes** across multiple application instances with zero data loss and sub-second response times.

### Key Features

- 🎯 **Intelligent Agent Battles**: CypherBot (graph-based) vs VibeBot (vector-based) recommendations
- 🧠 **ML-Enhanced Intelligence**: Clustering, visual analysis, behavioral patterns, and memory-based RAG
- 💬 **Conversational Memory**: Persistent user context and preferences across sessions
- ⚡ **High Performance**: Redis-distributed caching with FastAPI background tasks
- 🔄 **Production Scalable**: Stateless architecture for multi-instance deployment
- 🛡️ **Enterprise Ready**: Database migrations, monitoring, and error handling

## 🏗️ Architecture

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI       │    │  Battle System   │    │  ML Intelligence│
│   Application   ├────┤  Orchestrator    ├────┤  Coordinator    │
│   Service       │    │  (CAMEL Agents)  │    │  (4 Systems)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      │                          │                           │
┌─────▼─────┐            ┌───────▼────────┐         ┌────────▼─────┐
│   Redis   │            │     Neo4j      │         │    Qdrant    │
│ (Sessions │            │ (User Graph &  │         │ (Product     │
│  Cache &  │            │  Preferences)  │         │  Embeddings) │
│  State)   │            │                │         │              │
└───────────┘            └────────────────┘         └──────────────┘
```

### Agent Architecture

- **CypherBot**: Neo4j graph-based recommendations using user behavior patterns
- **VibeBot**: Qdrant vector-based recommendations using semantic similarity  
- **JudgeAri**: CAMEL-AI judge that selects the best recommendations
- **ML Intelligence**: 4 systems providing behavioral, clustering, visual, and memory insights

## 📁 Project Structure

```
ARI_PRODUCTION_CAMEL_0.27/
├── main.py                     # FastAPI application entry point
├── requirements.txt            # Production dependencies
├── .env                        # Environment configuration
├── .gitignore                 # Git exclusions
│
├── agents/                     # CAMEL-AI agent implementations
│   ├── cypher_bot.py          # Neo4j graph-based agent
│   ├── vibe_bot.py            # Qdrant vector-based agent
│   ├── judge.py               # CAMEL judge agent
│   └── factory.py             # Agent factory pattern
│
├── services/                   # Core business logic
│   ├── application.py         # Main application service
│   ├── conversation_handler.py # Session and memory management
│   ├── battle/                # Agent battle orchestration
│   ├── cache/                 # Redis caching services
│   ├── ml/intelligence/       # ML intelligence systems
│   ├── nlp/                   # Intent detection & NLP
│   ├── product/               # Product retrieval services
│   └── user/                  # User knowledge graph
│
├── models/                     # Data models and types
│   ├── products.py            # Product data structures
│   └── types.py               # Application type definitions
│
├── config/                     # Configuration management
│   ├── settings.py            # Environment-based settings
│   └── prompts.py             # Agent prompts and templates
│
├── di/                        # Dependency injection
│   └── container.py           # DI container configuration
│
├── migrations/                 # Database migration system
│   ├── migration_runner.py    # Migration coordinator
│   ├── neo4j/                 # Neo4j schema migrations
│   ├── qdrant/                # Qdrant collection migrations
│   ├── redis/                 # Redis structure migrations
│   └── README.md              # Migration documentation
│
└── scripts/                   # Utility and maintenance scripts
```

## 🚦 Quick Start

### Prerequisites

- Python 3.10+
- Neo4j 5.0+ (with user data and graph schema)
- Qdrant 1.0+ (with fashion product embeddings)
- Redis 6.0+ (for distributed caching)
- OpenAI API key (for embeddings and LLM)

### Installation

```bash
# Clone and enter directory
cd ARI_PRODUCTION_CAMEL_0.27

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials
```

### Environment Configuration

```bash
# .env file
OPENAI_API_KEY=your_openai_api_key

# Neo4j Configuration
NEO4J_URL=bolt://your-neo4j-host:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Qdrant Configuration  
QDRANT_URL=http://your-qdrant-host:6333
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_COLLECTION_NAME=fashion_products

# Redis Configuration
REDIS_URL=redis://your-redis-host:6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
```

### Database Setup

```bash
# Run database migrations
python migrations/migration_runner.py
```

### Launch Application

```bash
# Start production server
python main.py

# The API will be available at:
# http://localhost:8000
# Documentation: http://localhost:8000/docs
```

## 📡 API Usage

### Chat Endpoint

```bash
POST /chat
Content-Type: application/json

{
    "message": "I need a summer dress for a wedding",
    "session_id": "user_123_session", 
    "user_id": "user_123"
}
```

### Response Format

```json
{
    "response": "I found 3 perfect dresses for a summer wedding...",
    "products": [
        {
            "id": "prod_456",
            "title": "Elegant Floral Summer Dress",
            "price": 89.99,
            "category": "Dresses"
        }
    ],
    "session_id": "user_123_session",
    "metadata": {
        "processing_time_seconds": 0.45,
        "battle_winner": "VibeBot",
        "intent": "product_search"
    }
}
```

## 🔧 Production Features

### Performance Optimizations

- **FastAPI BackgroundTasks**: Non-blocking session storage and logging
- **Redis Distributed Caching**: Shared state across multiple instances
- **Connection Pooling**: Optimized for 20-30M node Neo4j datasets
- **Async Architecture**: Full async/await implementation
- **ML Intelligence Caching**: 1-hour TTL for expensive ML computations

### Scalability Features

- **Stateless Design**: No in-memory state, fully Redis-backed
- **Horizontal Scaling**: Add instances without coordination issues
- **Database Connection Management**: Automatic pooling and health checks
- **Battle Concurrency**: 50 concurrent agent battles (up from 5)
- **Neo4j Query Optimization**: 100 concurrent queries (up from 10)

### Enterprise Features

- **Database Migrations**: Versioned schema change management
- **Health Monitoring**: Endpoint health checks and metrics
- **Error Handling**: Graceful degradation and fallback strategies
- **Request Validation**: Pydantic models with required user_id/session_id
- **Security**: No sensitive data logging, sanitized error messages

## 🗃️ Database Schema

### Neo4j Graph Schema

```cypher
// User nodes with preferences
(:User {id, email, created_at, preferences})

// Product and attribute nodes  
(:Product {id, title, category, price, description})
(:Brand {name}), (:Color {name}), (:Style {name})

// Relationships
(:User)-[:PURCHASED|VIEWED|LIKED]->(:Product)
(:Product)-[:HAS_BRAND|HAS_COLOR|HAS_STYLE]->(:Attribute)
```

### Qdrant Collection

```python
# Fashion products collection
{
    "collection_name": "fashion_products",
    "vector_size": 1536,  # OpenAI text-embedding-3-small
    "distance": "Cosine",
    "payload_schema": {
        "title": "str",
        "category": "str", 
        "brand": "str",
        "price": "float"
    }
}
```

### Redis Key Structure

```
session:{session_id}           # User session data (24h TTL)
embedding:{hash}               # Cached embeddings (1h TTL)
battles:active                 # Active battle tracking
battles:counter                # Battle ID counter
conversation:{session}:{user}  # Chat history (7d TTL)
```

## 🚀 Deployment

### Docker Deployment (Recommended)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
```

### Production Checklist

- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Redis connection tested
- [ ] OpenAI API key validated
- [ ] Load balancer configured
- [ ] Monitoring dashboards set up
- [ ] Backup strategies implemented

## 📊 Monitoring

### Health Endpoints

- `GET /` - Application health check
- `GET /docs` - API documentation
- Redis, Neo4j, Qdrant health checked on startup

### Key Metrics to Monitor

- Response time percentiles (P95, P99)
- Battle execution times
- Cache hit rates (Redis)
- Database connection pool utilization
- Active session counts

## 🛠️ Development

### Code Quality

- Type hints throughout codebase
- Pydantic data validation
- Async/await patterns
- Dependency injection with `dependency-injector`
- Comprehensive error handling

### Testing

```bash
# Run tests (when test suite is available)
pytest tests/

# Database connectivity tests
python scripts/verify_connections.py
```

### Adding New Features

1. Update data models in `models/`
2. Implement business logic in `services/`
3. Create database migration if needed
4. Add API endpoints in `main.py`
5. Update documentation

## 🔍 Troubleshooting

### Common Issues

**Connection Errors**
- Verify database credentials in `.env`
- Check network connectivity to databases
- Ensure databases are running and accessible

**Performance Issues**  
- Monitor Redis memory usage
- Check Neo4j query performance
- Verify connection pool settings

**Battle System Issues**
- Check agent factory configuration
- Verify CAMEL-AI dependency version
- Monitor battle timeout settings

### Logs and Debugging

- Application logs: Standard output with structured logging
- Database query logs: Enable in respective database configs
- Redis operations: Monitor with `redis-cli monitor`

## 🤝 Contributing

1. Follow existing code patterns and type hints
2. Add appropriate error handling
3. Update documentation for new features
4. Test with realistic data volumes
5. Consider multi-instance deployment impacts

## 📄 License

This is a production system for fashion AI recommendations. Please ensure appropriate licensing and data usage compliance.

---

**Built with ❤️ for scalable fashion AI at enterprise scale**