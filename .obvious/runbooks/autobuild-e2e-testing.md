<!-- obvious-install: skill-version=1.3.1, template-version=1 -->
<!-- validation-summary:v1
runbook: autobuild-e2e-testing
last-validated: 2026-04-21T20:15:00Z
result: partial
blockers encountered:
  - type: missing_dependency
    detail: "fastapi, camel-ai, neo4j, qdrant-client, redis not installed in this sandbox — pip install required before E2E tests can run"
  - type: service_unreachable
    detail: "Neo4j, Qdrant, and Redis are external cloud services; E2E tests require live connections. Cannot validate without credentials."
  - type: auth_required_by_user
    detail: "OpenAI API key required for agent battle tests. Session-level API costs will accrue."
verified commands:
  - "python3 --version" → Python 3.13.13 (available)
  - "python -m pytest --collect-only" → pending (deps not installed)
screenshots: []
notes: "Scan-only mode: E2E test structure documented from codebase scan. All execution steps marked pending/blocked until services available."
-->

# Autobuild E2E Testing — AIStylist / ARI Fashion AI

> This runbook covers local and API-level E2E testing for the ARI multi-agent fashion recommendation system. Browser-based E2E is not applicable (no frontend SPA — API + WebSocket interface only).

---

## Architecture Under Test

```
Test Client
     │
     ▼
FastAPI /chat  ←→  ApplicationService
     │
     ▼
Battle System Orchestrator
  ├── CypherBot (Neo4j graph queries)
  ├── VibeBot   (Qdrant vector search)
  └── JudgeAri  (CAMEL-AI final ranker)
     │
     ▼
HybridDataStore
  ├── Neo4j  (user knowledge graph)
  ├── Qdrant (product embeddings)
  └── Redis  (session cache/state)
```

---

## Prerequisites

- `.env` with Neo4j, Qdrant, Redis, and OpenAI credentials (see `local-dev-onboarding.md`)
- Dependencies installed: `pip install -r requirements.txt`
- External services reachable (Neo4j, Qdrant, Redis)

---

## Step 1 — Unit tests (no services needed)

```bash
cd ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/
python -m pytest tests/ -v -m "not integration" --tb=short

# CrewAI research branch:
cd ARI_PRODUCTION_RESEARCH/ari_crewai_migration/
python -m pytest tests/unit/ -v --tb=short
```

> ⚠️ **BLOCKED** (`missing_dependency`): pytest available but camel-ai and other deps not installed.

---

## Step 2 — Integration tests (services required)

```bash
cd ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/
python -m pytest tests/ -v -m integration --tb=short

# CAMEL-0.27 migration tests:
python -m pytest tests/test_camel_070.py tests/test_camel_migration.py -v
```

> ⚠️ **BLOCKED** (`service_unreachable`): Requires live Neo4j, Qdrant, and Redis.

---

## Step 3 — API smoke E2E

Start the server, then run API-level tests:

```bash
# Start in background
cd ARI_PRODUCTION_CAMEL_0.27_FINAL/
uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 5

# Basic health check
curl -s http://localhost:8000/ | python3 -m json.tool

# Create a chat session
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need a casual summer outfit for a beach vacation",
    "session_id": "e2e-test-001"
  }' | python3 -m json.tool

# Continue conversation
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What about shoes to go with that?",
    "session_id": "e2e-test-001"
  }' | python3 -m json.tool
```

> ⚠️ **BLOCKED** (`missing_dependency` + `service_unreachable`): Server cannot start without deps and live services.

---

## Step 4 — WebSocket E2E (if applicable)

The CAMEL_0.27_BACKUP variant exposes a WebSocket at `/ws/{session_id}`:

```python
import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws/e2e-test-ws-001"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"message": "Show me red dresses under $200"}))
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(test_ws())
```

> ⚠️ **BLOCKED** (`missing_dependency`): `websockets` package may not be installed.

---

## Step 5 — Agent battle validation

The battle system (CypherBot vs VibeBot) can be tested in isolation:

```bash
cd ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/

# Test agent factory
python3 -c "
from agents.factory import AgentFactory
from config.settings import settings
# TODO(confirm): Initialize factory with valid config
factory = AgentFactory(settings)
print('Factory OK')
"

# Integration test suite (ari_stylist variant)
cd ari_stylist/
python migration_test_script.py
```

> ⚠️ **BLOCKED** (`auth_required_by_user`): OpenAI API key required; battle tests will incur API costs.

---

## Step 6 — ML recommendation system validation

```bash
cd ari_stylist/
python3 -c "
# Verify ML components load without external deps
from ensemble_recommender import EnsembleRecommender
print('EnsembleRecommender: OK')
"

# Run full integration test if available
python integration_test_suite.py
```

> ⚠️ **BLOCKED** (`missing_dependency` + `service_unreachable`): Requires torch, scikit-learn, and live DB connections.

---

## Step 7 — Data pipeline validation (neo4j graph)

```bash
cd ari_stylist/
# Verify graph analysis
python neo4j_graph_analyzer.py  # Read-only analysis

# Check production schema
python production_schema_init.py
```

> ⚠️ **BLOCKED** (`service_unreachable`): Neo4j host required.

---

## Autobuild Agent Test Loop

When an autobuild agent runs E2E validation:

1. Start the FastAPI server (`python main.py` or `uvicorn main:app`)
2. POST a test conversation to `/chat` with a known fashion query
3. Assert response contains `recommendations` or `products` array
4. Assert `session_id` round-trips correctly
5. POST a follow-up message to same session — verify context memory
6. Shut down server

**Definition of pass:** API responds with structured product recommendations for a conversational fashion query without 500 errors.

---

## TODO

- [ ] `TODO(confirm):` Which sub-project is the current primary? `ari_stylist/` or `ARI_PRODUCTION_CAMEL_0.27_FINAL/`?
- [ ] `TODO(confirm):` Are there fixture datasets for Neo4j/Qdrant seeding in CI?
- [ ] `TODO(confirm):` Is there a CI/CD pipeline that runs E2E against staging services?
- [ ] `TODO(confirm):` Redis is required for which variants? (BACKUP and redis variants confirmed; FINAL unclear)

---

## Known Constraints

- **No browser UI to test**: The primary interface is REST API + optional WebSocket; no Playwright/Selenium tests needed.
- **External service dependency**: All meaningful E2E requires live Neo4j/Qdrant/Redis — no local mock provided.
- **OpenAI cost**: Battle system calls GPT-4/GPT-3.5 on each recommendation cycle; E2E tests will incur API costs.
- **Multiple entry points**: Each sub-directory has its own `main.py` / app entrypoint; specify which one to test.
