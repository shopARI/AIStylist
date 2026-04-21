<!-- obvious-install: skill-version=1.3.1, template-version=1 -->
<!-- validation-summary:v1
runbook: local-dev-onboarding
last-validated: 2026-04-21T20:15:00Z
result: partial
blockers encountered:
  - type: missing_dependency
    detail: "fastapi, camel-ai, neo4j, qdrant-client, redis not installed in this sandbox — pip install required"
  - type: service_unreachable
    detail: "Neo4j, Qdrant, and Redis are external cloud services; connection requires .env credentials. Neo4j: bolt://34.135.40.119:7687, Qdrant: cloud.qdrant.io, Redis: external"
  - type: auth_required_by_user
    detail: "OpenAI API key, Neo4j credentials, Qdrant API key, Redis URL must be supplied in .env"
verified commands:
  - "python3 --version" → Python 3.13.13 (available in sandbox)
  - "git clone" → OK
  - "pip install pytest" → OK (pytest already present)
screenshots: []
notes: "Scan-only mode: all service-dependent steps are marked BLOCKED; Python runtime is available but dependencies not installed in this sandbox. External databases cannot be validated without credentials."
-->

# Local Dev Onboarding — AIStylist / ARI Fashion AI

> **AIStylist** is a multi-agent AI fashion recommendation system built in Python. The primary active module is `ari_stylist/`, with archived versions under `ARI_PRODUCTION_CAMEL_0.27_*` and a newer research branch at `ARI_PRODUCTION_RESEARCH/`.

---

## Prerequisites

| Tool | Required version | Check |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| pip | ≥ 22 | `pip3 --version` |
| Neo4j | 5.0+ (external cloud) | See `.env` |
| Qdrant | 1.1+ (external cloud) | See `.env` |
| Redis | ≥ 6 (external cloud) | See `.env` |
| OpenAI API key | Any valid key | `.env` file |

---

## Step 1 — Clone the repo

```bash
git clone https://github.com/shopARI/AIStylist.git
cd AIStylist
```

---

## Step 2 — Decide which sub-project to run

The repo contains several versions/branches of the ARI system:

| Directory | Status | Notes |
|---|---|---|
| `ari_stylist/` | Current active dev | CAMEL-AI 0.2.64 based |
| `ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/` | Production backup (0.27) | Redis + DI container |
| `ARI_PRODUCTION_CAMEL_0.27_FINAL/` | Production final (0.27) | Cleanest DI structure |
| `ARI_PRODUCTION_CAMEL_0.27_redis/` | Redis-enhanced (0.27) | Distributed state |
| `ARI_PRODUCTION_RESEARCH/` | Research & v3 experiments | CrewAI, multi-modal |
| `graph/` | Graph analysis phase | Neo4j graph experiments |

For a fresh local dev start, use **`ARI_PRODUCTION_CAMEL_0.27_FINAL/`** (cleanest structure) or **`ari_stylist/`** (latest iteration).

---

## Step 3 — Set up environment

```bash
# Navigate to your chosen sub-project, e.g.:
cd ari_stylist/
# OR
cd ARI_PRODUCTION_CAMEL_0.27_FINAL/

# Copy and edit .env
cp .env.example .env   # If .env.example exists
# OR edit .env directly (a template .env is present in ari_stylist/)
```

### Required environment variables

```env
# Neo4j Connection
NEO4J_URL=bolt://<host>:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<password>

# OpenAI
OPENAI_API_KEY=<your-openai-key>

# Qdrant (vector DB)
QDRANT_URL=https://<instance>.cloud.qdrant.io
QDRANT_API_KEY=<key>
QDRANT_COLLECTION_NAME=fashion_products

# Redis (for production backup / redis variants)
REDIS_URL=redis://<host>:6379

# Service config
NUM_WORKER_THREADS=4
API_PORT=5000   # or 8000 for FINAL
CAMEL_VERSION=0.2.64
MEMORY_TOKEN_LIMIT=1024
ENABLE_MCP=true
```

> ⚠️ **BLOCKED** (`auth_required_by_user`): Credentials for Neo4j, Qdrant, and OpenAI must be provided by the user. Do not commit `.env` to the repo.

---

## Step 4 — Install dependencies

```bash
# Install from the relevant requirements.txt:
pip install -r requirements.txt

# For ari_stylist specifically:
pip install camel-ai==0.2.7 openai httpx asyncio aiolimiter
pip install neo4j qdrant-client fastapi uvicorn pydantic
pip install pandas numpy mlxtend scikit-learn torch torchvision pillow
pip install python-dotenv pytest pytest-asyncio
```

> ⚠️ **BLOCKED** (`missing_dependency`): Dependencies not pre-installed in sandbox. `pip install -r requirements.txt` required. Note: `torch` and `torchvision` may be large (~2GB); use `--no-deps` flags if needed for dev-only work.

---

## Step 5 — Verify services are reachable

```bash
# Test Neo4j connectivity
python3 -c "from neo4j import GraphDatabase; d = GraphDatabase.driver('bolt://<host>:7687', auth=('neo4j','<pw>')); d.verify_connectivity(); print('Neo4j OK')"

# Test Qdrant
python3 -c "from qdrant_client import QdrantClient; c = QdrantClient(url='<url>', api_key='<key>'); print(c.get_collections())"
```

> ⚠️ **BLOCKED** (`service_unreachable`): External cloud services (Neo4j, Qdrant, Redis) require credentials from `.env`. Cannot validate in sandbox without these.

---

## Step 6 — Run the application

### `ari_stylist/` variant

```bash
cd ari_stylist/
python ai_stylist_app_async.py
# Server starts on port 5000 (API_PORT in .env)
```

### `ARI_PRODUCTION_CAMEL_0.27_FINAL/` variant

```bash
cd ARI_PRODUCTION_CAMEL_0.27_FINAL/
python main.py
# OR for production:
uvicorn main:app --host 0.0.0.0 --port 8000
```

> ⚠️ **BLOCKED** (`missing_dependency` + `service_unreachable`): Requires dependencies installed (Step 4) and external services running (Step 5).

---

## Step 7 — Run tests

```bash
# For ari_stylist:
cd ari_stylist/
python integration_test_suite.py   # If it exists

# For FINAL variant:
cd ARI_PRODUCTION_CAMEL_0.27_FINAL/
python -m pytest tests/ -v

# For research/crewai branch:
cd ARI_PRODUCTION_RESEARCH/ari_crewai_migration/
pip install crewai chromadb pytest-asyncio
python -m pytest tests/ -v --tb=short
```

> ⚠️ **BLOCKED** (`missing_dependency`): Requires deps installed. Tests may also require running services.

---

## Step 8 — API smoke test

Once the server is running:

```bash
# Health check (if /health endpoint exists)
curl http://localhost:8000/health || curl http://localhost:5000/health

# Chat test
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a casual summer outfit", "session_id": "test-session-001"}'
```

> ⚠️ **BLOCKED** (`service_unreachable`): Cannot validate without services running.

---

## Known Constraints

- **Multiple sub-projects**: The repo has several parallel versions; each has its own `requirements.txt`. Work in one at a time.
- **External cloud services**: Neo4j and Qdrant are hosted externally. Local setup requires valid credentials.
- **Redis**: Required for the production/redis variants for distributed state. Not needed for `ari_stylist/` basic run.
- **Torch/ML**: `torch` is a large dependency; on CPU-only boxes, use `pip install torch --index-url https://download.pytorch.org/whl/cpu`.
- **No `.gitignore` for credentials**: Ensure `.env` files are never committed — they contain DB passwords and API keys.
- **No Xcode/iOS toolchain**: Despite the executable context mentioning iOS, this repo is a Python AI system. No iOS build toolchain is required.

---

## Common Commands

| Purpose | Command | Verified? |
|---|---|---|
| Python version | `python3 --version` | yes |
| Install deps | `pip install -r requirements.txt` | pending |
| Run (ari_stylist) | `python ai_stylist_app_async.py` | pending |
| Run (FINAL) | `uvicorn main:app --host 0.0.0.0 --port 8000` | pending |
| Test (FINAL) | `python -m pytest tests/ -v` | pending |
| Test (crewai) | `python -m pytest tests/ -v --tb=short` | pending |
| Lint | `flake8 . --max-line-length=127` | pending |
