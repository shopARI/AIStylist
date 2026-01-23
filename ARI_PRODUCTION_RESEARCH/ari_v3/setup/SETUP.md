# ARI V3 - Setup Guide

Complete setup instructions for the ARI V3 Style Navigation Interface.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
   - [Python Environment](#1-python-environment)
   - [Qdrant Vector Database](#2-qdrant-vector-database)
   - [Neo4j Graph Database](#3-neo4j-graph-database)
   - [Environment Variables](#4-environment-variables)
   - [OpenAI API Key](#5-openai-api-key)
4. [Running the Application](#running-the-application)
5. [Troubleshooting](#troubleshooting)
6. [Data Population](#data-population)

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.10 or higher** - Check with `python3 --version`
- **Docker** - Check with `docker --version`
- **Git** - Check with `git --version`
- **At least 8GB RAM** - Neo4j and Qdrant each need ~2-4GB
- **20GB free disk space** - For Docker images and data storage
- **OpenAI API key** - Get one at https://platform.openai.com/api-keys

---

## Quick Start

If you want to get running quickly, follow these steps in order:

```bash
# 1. Navigate to the setup directory
cd /path/to/ARI_PRODUCTION_RESEARCH/ari_v3/setup

# 2. Make scripts executable
chmod +x setup_qdrant.sh setup_neo4j.sh

# 3. Set up Qdrant (vector search)
./setup_qdrant.sh

# 4. Set up Neo4j (user profiles)
./setup_neo4j.sh

# 5. Create Python virtual environment
cd ..
python3 -m venv venv
source venv/bin/activate

# 6. Install dependencies
pip install -r setup/requirements.txt

# 7. Copy and configure environment file
cp ../.env.example .env
# Edit .env with your settings (see section 4 below)

# 8. Run the CLI demo
python demo_cli.py
```

---

## Detailed Setup

### 1. Python Environment

#### 1.1 Create a Virtual Environment

It is strongly recommended to use a virtual environment to avoid package conflicts:

```bash
# Navigate to the ari_v3 directory
cd /path/to/ARI_PRODUCTION_RESEARCH/ari_v3

# Create virtual environment
python3 -m venv venv

# Activate it (Linux/Mac)
source venv/bin/activate

# Activate it (Windows)
# venv\Scripts\activate
```

You should see `(venv)` at the beginning of your terminal prompt.

#### 1.2 Install Python Packages

```bash
# Install all required packages
pip install -r setup/requirements.txt
```

This will install:
- `openai` - For embeddings and LLM calls
- `qdrant-client` - Vector database client
- `neo4j` - Graph database client
- `streamlit` - Web interface
- `numpy`, `pydantic` - Data processing
- `torch`, `transformers` - For visual search (FashionSigLIP)

#### 1.3 PyTorch Installation (for Visual Search)

If you have a GPU and want faster visual search:

```bash
# For NVIDIA GPU with CUDA 11.8
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# For NVIDIA GPU with CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# For CPU only (default, slower)
pip install torch torchvision
```

To verify GPU is detected:
```bash
python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

---

### 2. Qdrant Vector Database

Qdrant stores product embeddings and enables fast similarity search for recommendations.

#### 2.1 Automatic Setup (Recommended)

```bash
cd /path/to/ARI_PRODUCTION_RESEARCH/ari_v3/setup
chmod +x setup_qdrant.sh
./setup_qdrant.sh
```

The script will:
- Check Docker is installed
- Pull the Qdrant Docker image
- Create a data directory at `~/qdrant_data`
- Start Qdrant on port 6333
- Verify the installation

#### 2.2 Manual Setup

If you prefer to set up Qdrant manually:

```bash
# Create data directory
mkdir -p ~/qdrant_data

# Pull and run Qdrant
docker run -d \
    --name ari-qdrant \
    --restart unless-stopped \
    -p 6333:6333 \
    -p 6334:6334 \
    -v ~/qdrant_data:/qdrant/storage \
    qdrant/qdrant:v1.12.1
```

#### 2.3 Verify Qdrant is Running

```bash
# Check container status
docker ps | grep qdrant

# Test the API
curl http://localhost:6333/collections

# Open the dashboard in your browser
# http://localhost:6333/dashboard
```

#### 2.4 Qdrant Management Commands

```bash
# Stop Qdrant
docker stop ari-qdrant

# Start Qdrant
docker start ari-qdrant

# View logs
docker logs ari-qdrant

# Remove completely (data is preserved in ~/qdrant_data)
docker rm -f ari-qdrant
```

---

### 3. Neo4j Graph Database

Neo4j stores user profiles, preferences, purchase history, and style relationships.

#### 3.1 Automatic Setup (Recommended)

```bash
cd /path/to/ARI_PRODUCTION_RESEARCH/ari_v3/setup
chmod +x setup_neo4j.sh
./setup_neo4j.sh
```

The script will:
- Check Docker is installed
- Pull the Neo4j Docker image
- Create data directories at `~/neo4j_data`
- Start Neo4j on ports 7474 (HTTP) and 7687 (Bolt)
- Set up initial password
- Verify the installation

Default credentials:
- Username: `neo4j`
- Password: `ari_secure_password_2024`

**IMPORTANT**: Change the password for production use.

#### 3.2 Manual Setup

If you prefer to set up Neo4j manually:

```bash
# Create data directories
mkdir -p ~/neo4j_data/{data,logs,import,plugins}

# Pull and run Neo4j
docker run -d \
    --name ari-neo4j \
    --restart unless-stopped \
    -p 7474:7474 \
    -p 7687:7687 \
    -v ~/neo4j_data/data:/data \
    -v ~/neo4j_data/logs:/logs \
    -v ~/neo4j_data/import:/var/lib/neo4j/import \
    -v ~/neo4j_data/plugins:/plugins \
    -e NEO4J_AUTH=neo4j/ari_secure_password_2024 \
    -e NEO4J_PLUGINS='["apoc"]' \
    -e NEO4J_dbms_memory_heap_max__size=2g \
    neo4j:5.26.0
```

#### 3.3 Verify Neo4j is Running

```bash
# Check container status
docker ps | grep neo4j

# Open the browser interface
# http://localhost:7474

# Test connection with cypher-shell
docker exec -it ari-neo4j cypher-shell -u neo4j -p ari_secure_password_2024 "RETURN 1"
```

#### 3.4 Neo4j Management Commands

```bash
# Stop Neo4j
docker stop ari-neo4j

# Start Neo4j
docker start ari-neo4j

# View logs
docker logs ari-neo4j

# Remove completely (data is preserved in ~/neo4j_data)
docker rm -f ari-neo4j
```

#### 3.5 Change Neo4j Password

Using the browser:
1. Open http://localhost:7474
2. Log in with neo4j / ari_secure_password_2024
3. Click the user icon and change password

Using command line:
```bash
docker exec ari-neo4j cypher-shell \
    -u neo4j \
    -p ari_secure_password_2024 \
    "ALTER CURRENT USER SET PASSWORD FROM 'ari_secure_password_2024' TO 'your_new_password'"
```

---

### 4. Environment Variables

Create a `.env` file in the `ari_v3` directory:

```bash
cd /path/to/ARI_PRODUCTION_RESEARCH/ari_v3
cp ../.env.example .env
```

Edit the `.env` file with your settings:

```bash
# =============================================================================
# REQUIRED SETTINGS
# =============================================================================

# OpenAI API Key (REQUIRED)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Neo4j Database
NEO4J_URI=bolt://localhost:7687
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=ari_secure_password_2024
NEO4J_DATABASE=neo4j

# Qdrant Vector Database
QDRANT_URL=http://localhost:6333
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=fashion_products
QDRANT_VISUAL_COLLECTION_NAME=fashion_multimodal_embeddings

# =============================================================================
# OPTIONAL SETTINGS
# =============================================================================

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO

# OpenAI Model Settings
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Feature Flags
ENABLE_VISUAL_INTELLIGENCE=true
ENABLE_SEMANTIC_SEARCH=true
```

---

### 5. OpenAI API Key

You need an OpenAI API key for embeddings and LLM calls.

#### 5.1 Get an API Key

1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (it starts with `sk-`)

#### 5.2 Add to Environment

Add your key to the `.env` file:

```bash
OPENAI_API_KEY=sk-your-key-here
```

Or export it in your terminal:

```bash
export OPENAI_API_KEY=sk-your-key-here
```

#### 5.3 Verify API Key Works

```bash
python3 -c "
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[{'role': 'user', 'content': 'Say hello'}],
    max_tokens=10
)
print('API key works:', response.choices[0].message.content)
"
```

---

## Running the Application

### Command Line Interface (CLI)

```bash
cd /path/to/ARI_PRODUCTION_RESEARCH/ari_v3

# Activate virtual environment
source venv/bin/activate

# Run CLI demo
python demo_cli.py
```

CLI Commands:
- Type a style query like "show me casual summer dresses under $100"
- `/debug 1` - Enable basic debug mode
- `/debug 2` - Enable verbose debug mode (shows all scores)
- `/profile` - View current user profile
- `/visual on` - Enable visual search
- `/visual off` - Disable visual search
- `/help` - Show all commands
- `/quit` - Exit

### Web Interface

```bash
cd /path/to/ARI_PRODUCTION_RESEARCH/ari_v3

# Activate virtual environment
source venv/bin/activate

# Run Streamlit web app
streamlit run web_app.py
```

The web interface will open at http://localhost:8501

---

## Troubleshooting

### Docker Permission Denied

If you get "permission denied" errors with Docker:

```bash
# Add your user to the docker group
sudo usermod -aG docker $USER

# Log out and log back in, or run:
newgrp docker
```

### Port Already in Use

If ports 6333, 7474, or 7687 are already in use:

```bash
# Find what's using the port
sudo lsof -i :6333

# Kill the process or use different ports
# For Qdrant:
QDRANT_PORT=16333 ./setup_qdrant.sh

# For Neo4j:
NEO4J_HTTP_PORT=17474 NEO4J_BOLT_PORT=17687 ./setup_neo4j.sh
```

### Neo4j Connection Refused

If you cannot connect to Neo4j:

```bash
# Check container is running
docker ps | grep neo4j

# Check logs for errors
docker logs ari-neo4j

# Neo4j takes 30-60 seconds to start, wait and retry
```

### Qdrant Connection Refused

```bash
# Check container is running
docker ps | grep qdrant

# Check logs
docker logs ari-qdrant

# Test API directly
curl http://localhost:6333/collections
```

### OpenAI API Errors

If you get authentication errors:

```bash
# Verify key is set
echo $OPENAI_API_KEY

# Check .env file has the key
grep OPENAI_API_KEY .env

# Make sure there are no extra spaces or quotes
```

### Import Errors

If you get Python import errors:

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall requirements
pip install -r setup/requirements.txt

# Check Python version
python3 --version  # Should be 3.10+
```

### Visual Search Not Working

If FashionSigLIP visual search fails:

```bash
# Check PyTorch is installed
python3 -c "import torch; print(torch.__version__)"

# Check transformers is installed
python3 -c "import transformers; print(transformers.__version__)"

# Install missing dependencies
pip install torch transformers sentencepiece pillow
```

---

## Data Population

### Qdrant Collections

The system expects two Qdrant collections:

1. `fashion_products` - Semantic search (1536-dim OpenAI embeddings)
2. `fashion_multimodal_embeddings` - Visual search (1024-dim FashionSigLIP embeddings)

If you need to create empty collections:

```bash
python3 -c "
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient('http://localhost:6333')

# Semantic collection
client.create_collection(
    collection_name='fashion_products',
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
)

# Visual collection
client.create_collection(
    collection_name='fashion_multimodal_embeddings',
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)
print('Collections created')
"
```

### Neo4j Schema

The system will create necessary indexes automatically. To verify:

```bash
docker exec ari-neo4j cypher-shell \
    -u neo4j \
    -p ari_secure_password_2024 \
    "SHOW INDEXES"
```

---

## Support

If you encounter issues not covered here:

1. Check the logs: `docker logs ari-qdrant` or `docker logs ari-neo4j`
2. Verify all services are running: `docker ps`
3. Ensure environment variables are set: `env | grep -E "OPENAI|NEO4J|QDRANT"`
4. Run with debug mode: `python demo_cli.py` then type `/debug 2`
