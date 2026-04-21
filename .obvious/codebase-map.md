<!-- obvious-install: skill-version=1.3.1, template-version=1 -->
# Codebase Map — AIStylist

> Generated: 2026-04-21 | Repo: shopARI/AIStylist | Commit: fc9a1b46

---

## Repository Structure

```
AIStylist/
├── .gitignore                          # Minimal (only ignores "ari/*")
├── .gitignore~                         # Backup (ignores "ari/*")
│
├── ari_stylist/                        # 🟢 CURRENT ACTIVE DEV — CAMEL-AI 0.2.64
│   ├── ai_stylist_app_async.py         # Main app entry point (async FastAPI)
│   ├── chat_session_manager_async.py   # Conversation + memory management
│   ├── agent_factory.py                # Agent instantiation
│   ├── battle_agents.py                # CypherBot vs VibeBot battle system
│   ├── competitive_search_system.py    # JudgeAri decision engine
│   ├── hybrid_data_store.py            # Neo4j + Qdrant routing layer
│   ├── user_knowledge_graph_async.py   # Neo4j user graph operations
│   ├── ensemble_recommender.py         # Multi-system recommendation fusion
│   ├── hybrid_visual_recommender.py    # Visual/multimodal recommendations
│   ├── memory_rag_recommender.py       # Memory-augmented RAG recommender
│   ├── memory_integration_async.py     # Memory system integration
│   ├── rfm_apriori_recommender_async.py # RFM + Apriori ML recommender
│   ├── multi_cluster_recommender.py    # Clustering-based recommender
│   ├── product_retriever_async.py      # Product retrieval from DBs
│   ├── enhanced_recommender_manager_async.py # Recommender orchestrator
│   ├── stylist_service_async.py        # Stylist service layer
│   ├── stylist_agent_async.py          # CAMEL-based stylist agent
│   ├── camel_imports.py                # CAMEL-AI library compatibility shim
│   ├── neo4j_graph_analyzer.py         # Graph analysis utilities
│   ├── neo4j_adaptive_analyzer.py      # Adaptive Neo4j analysis
│   ├── neo4j_analyzer_importer.py      # Data import to Neo4j
│   ├── neo4j_graph_analyzer_new_graph.py # New graph schema analyzer
│   ├── production_schema_init.py       # Production DB schema setup
│   ├── migration_test_script.py        # Migration validation tests
│   ├── product_field_mapping.py        # Product schema mapping
│   ├── stylist_config.json             # Stylist configuration
│   ├── requirements.txt                # Python dependencies (CAMEL-AI 0.2.7)
│   ├── .env                            # ⚠️ Environment config (contains credentials!)
│   ├── ai-stylist-documentation.md     # Component documentation
│   ├── readme_ai_stylist.md            # Dev readme
│   ├── ari_stylist_production/         # Production deployment artifacts
│   └── exports/                        # Data export files
│
├── ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/  # 🔵 PRODUCTION BACKUP
│   ├── main.py                         # FastAPI app (port 8000), DI container
│   ├── requirements.txt                # Production dependencies (CAMEL-AI 0.27)
│   ├── dependency_analyzer.py          # Dependency analysis
│   ├── agents/                         # CAMEL agent implementations
│   │   ├── base.py                     # Agent base class
│   │   ├── cypher_bot.py               # Neo4j graph agent
│   │   ├── vibe_bot.py                 # Qdrant vector agent
│   │   ├── judge.py                    # JudgeAri final ranker
│   │   └── factory.py                  # Agent factory (DI)
│   ├── config/
│   │   ├── settings.py                 # Centralized config (env vars, dataclasses)
│   │   └── prompts.py                  # Agent system prompts
│   ├── di/                             # Dependency injection container
│   ├── services/                       # Business logic
│   │   ├── application.py              # ApplicationService (main orchestrator)
│   │   ├── battle/                     # Battle system (orchestrator, metrics, executor)
│   │   ├── cache/                      # Redis caching layer
│   │   ├── chat/                       # Chat session management
│   │   ├── connection/                 # DB connection pools
│   │   ├── data/                       # Data access layer
│   │   ├── memory/                     # Conversation memory
│   │   ├── ml/                         # ML intelligence (4 sub-systems)
│   │   ├── nlp/                        # NLP processing
│   │   ├── product/                    # Product retrieval
│   │   ├── user/                       # User management
│   │   └── streamlit_service.py        # Optional Streamlit interface
│   ├── models/
│   │   ├── products.py                 # Product data models (Pydantic)
│   │   └── types.py                    # Shared type definitions
│   ├── migrations/                     # Database migrations
│   │   └── migration_runner.py         # Migration executor
│   ├── tests/
│   │   ├── test_camel_070.py           # CAMEL 0.70 compatibility tests
│   │   └── test_camel_migration.py     # Migration tests
│   ├── lib/                            # Internal libraries
│   ├── web_interface_dev/              # Dev web interface (Streamlit)
│   └── README.md                       # Full architecture docs
│
├── ARI_PRODUCTION_CAMEL_0.27_FINAL/    # 🔵 PRODUCTION FINAL (cleanest)
│   ├── main.py                         # FastAPI app entry point
│   ├── requirements.txt
│   ├── agents/                         # Same structure as BACKUP
│   ├── di/                             # DI container
│   ├── migrations/                     # DB migrations
│   ├── models/
│   ├── scripts/                        # Utility scripts (Qdrant cleanup, migrations)
│   ├── services/                       # Same structure as BACKUP
│   └── README.md
│
├── ARI_PRODUCTION_CAMEL_0.27_redis/    # 🔵 REDIS-ENHANCED VARIANT
│   ├── main.py                         # Redis-distributed state variant
│   ├── requirements.txt
│   ├── agents/
│   ├── di/
│   ├── migrations/
│   ├── models/
│   ├── scripts/
│   └── services/
│
├── ARI_PRODUCTION_RESEARCH/            # 🔬 RESEARCH & EXPERIMENTS
│   ├── README.md                       # ARI V3 roadmap
│   ├── ari_v3/                         # V3 architecture experiments
│   │   ├── core/                       # Core V3 components
│   │   ├── interface/                  # Interface layer
│   │   ├── nlp/                        # Advanced NLP
│   │   ├── orchestrator/               # Agent orchestration
│   │   ├── pillars/                    # Architecture pillars
│   │   └── tests/                      # V3 tests
│   ├── ari_crewai_migration/           # CrewAI migration (has CI!)
│   │   ├── .github/workflows/test.yml  # ← Only CI config in repo
│   │   ├── agents/ tasks/              # CrewAI agents and tasks (YAML)
│   │   ├── nlp/ crews/                 # NLP + crew implementations
│   │   └── tests/unit/ tests/integration/
│   ├── agents/                         # Research agents (including VisionBot)
│   ├── services/                       # Research services
│   ├── run_fashionsig_*.py             # FashionSIG embedding generation scripts
│   ├── adaptive_llm_extract.py         # LLM-based feature extraction
│   └── [many analysis/doc files]       # Design docs, reviews, roadmaps
│
└── graph/                              # 🔬 GRAPH ANALYSIS
    └── phase1/                         # Phase 1 Neo4j graph work
        ├── README.md
        └── [analysis scripts, data]
```

---

## Key Entry Points

| Entry Point | Path | Notes |
|---|---|---|
| Main app (ari_stylist) | `ari_stylist/ai_stylist_app_async.py` | Port 5000, async FastAPI |
| Main app (FINAL) | `ARI_PRODUCTION_CAMEL_0.27_FINAL/main.py` | Port 8000, DI container |
| Main app (BACKUP) | `ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/main.py` | Same as FINAL |
| Battle system | `ari_stylist/battle_agents.py` | CypherBot vs VibeBot |
| Agent factory | `*/agents/factory.py` | CAMEL agent instantiation |
| DI container | `*/di/container.py` | Dependency injection wiring |

---

## Data Layer

| Database | Role | Client |
|---|---|---|
| **Neo4j** | User knowledge graph, product relationships | `neo4j` Python driver |
| **Qdrant** | Product vector embeddings (semantic search) | `qdrant-client` |
| **Redis** | Session cache, distributed state (production variants) | `redis-py` (async) |

---

## Agent System

| Agent | File | Role |
|---|---|---|
| CypherBot | `agents/cypher_bot.py` | Graph-based recommendations via Cypher queries |
| VibeBot | `agents/vibe_bot.py` | Vector-based recommendations via Qdrant |
| JudgeAri | `agents/judge.py` | CAMEL-AI judge — selects best products |
| VisionBot | `ARI_PRODUCTION_RESEARCH/agents/vision_bot.py` | Multimodal/visual search (research) |

---

## ML Intelligence Sub-Systems (in `services/ml/`)

| System | Focus |
|---|---|
| Behavioral | User behavior patterns, RFM analysis |
| Clustering | K-means product clustering (scikit-learn) |
| Visual | Image embeddings, visual similarity (torch + CLIP) |
| Memory RAG | Retrieval-augmented generation with conversation memory |

---

## Where to Find Things

| Need | Look here |
|---|---|
| FastAPI routes | `main.py` (in each sub-project) |
| Agent logic | `agents/` (all sub-projects) |
| Business logic | `services/application.py` |
| Battle/ranking | `services/battle/` |
| DB schema/models | `models/`, `migrations/` |
| Config & env vars | `config/settings.py`, `.env` |
| Agent prompts | `config/prompts.py` |
| Tests | `tests/` (inside each sub-project) |
| ML systems | `services/ml/` |
| V3 research | `ARI_PRODUCTION_RESEARCH/ari_v3/` |
| CI config | `ARI_PRODUCTION_RESEARCH/ari_crewai_migration/.github/workflows/` |

---

## Structural Notes

- **No monorepo tooling**: Each sub-directory is a standalone Python project with its own `requirements.txt` and entry point. There is no `pyproject.toml`, `Pipfile`, or workspace management at the root level.
- **Active development uncertainty**: Multiple parallel versions exist. Consult Lior Cole (@lior@shopari.com) to confirm the primary/production-targeted variant.
- **Research vs production**: `ARI_PRODUCTION_RESEARCH/` contains experiments (CrewAI, V3, FashionSIG) not currently deployed. Production is one of the `ARI_PRODUCTION_CAMEL_0.27_*` variants.
- **Graph sub-project** (`graph/`): Phase 1 Neo4j graph analysis work, separate from main application.
