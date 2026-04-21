<!-- obvious-install: skill-version=1.3.1, template-version=1 -->
# Obvious Repo Guidance — AIStylist

## Purpose

AIStylist (a.k.a. **ARI — AI Recommendation Intelligence**) is a Python multi-agent AI fashion
recommendation system. It provides personalized product recommendations via conversational AI,
using a battle system (CypherBot vs VibeBot) scored by JudgeAri, backed by Neo4j (user graph),
Qdrant (vector search), and Redis (session state).

Code agents working on this repo should:
- Identify which sub-project is the active target before editing (see Codebase Map)
- Never modify `.env` files or commit credentials
- Use the DI container pattern (`di/container.py`) in production variants for service wiring
- Treat `ARI_PRODUCTION_RESEARCH/` as experimental — do not ship from it without confirmation

## Existing Guidance

| File | Use |
|---|---|
| `ari_stylist/readme_ai_stylist.md` | Component overview and quick start for ari_stylist variant |
| `ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/README.md` | Full architecture docs for CAMEL 0.27 production variant |
| `ARI_PRODUCTION_CAMEL_0.27_FINAL/README.md` | Final production variant overview |
| `ARI_PRODUCTION_RESEARCH/ari_crewai_migration/` | CrewAI migration experiment (has CI + tests) |
| `ari_stylist/ai-stylist-documentation.md` | Detailed component documentation |

## Repo Entry Points

| Area | Path | Notes |
|---|---|---|
| App (ari_stylist) | `ari_stylist/ai_stylist_app_async.py` | Port 5000, CAMEL-AI 0.2.64 |
| App (FINAL) | `ARI_PRODUCTION_CAMEL_0.27_FINAL/main.py` | Port 8000, DI container |
| App (BACKUP) | `ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/main.py` | Port 8000, Redis |
| Agent factory | `*/agents/factory.py` | Agent instantiation |
| DI wiring | `*/di/container.py` | Service dependency injection |
| Tests (BACKUP) | `ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/tests/` | pytest |
| Tests (crewai) | `ARI_PRODUCTION_RESEARCH/ari_crewai_migration/tests/` | pytest + asyncio |
| DB schema | `*/migrations/` | Migration runner |
| CI config | `ARI_PRODUCTION_RESEARCH/ari_crewai_migration/.github/workflows/test.yml` | Only CI in repo |

## Common Commands

| Purpose | Command | Verified? |
|---|---|---|
| Python version | `python3 --version` | yes |
| Install deps | `pip install -r requirements.txt` | pending |
| Run ari_stylist | `python ai_stylist_app_async.py` | pending |
| Run FINAL | `uvicorn main:app --host 0.0.0.0 --port 8000` | pending |
| Test BACKUP | `python -m pytest tests/ -v` | pending |
| Test crewai | `cd ARI_PRODUCTION_RESEARCH/ari_crewai_migration && python -m pytest tests/ -v` | pending |
| Lint | `flake8 . --max-line-length=127 --exit-zero` | pending |

## Runbooks

### Always-on
| Runbook | When to use |
|---|---|
| `.obvious/runbooks/local-dev-onboarding.md` | Fresh checkout, new dev environment setup |

### Opt-in (generated at this install)
| Runbook | When to use |
|---|---|
| `.obvious/runbooks/autobuild-e2e-testing.md` | Before shipping changes; API and agent battle smoke tests |
| `.obvious/runbooks/ci-runbook-generator.md` | Setting up or improving CI; addressing CI failures |

## Codebase Map

See `.obvious/codebase-map.md` for a directory guide, key entry points, and where to find agents,
services, models, and migrations across all sub-projects.

## Bibliography

0 sources scanned. 0 entries — the workspace bibliography is empty (no nodes registered yet). Bibliography tool was invoked and returned no results. Re-run install after bibliography nodes are added to the workspace.

## Known Constraints

- **External cloud services required**: Neo4j (bolt), Qdrant (cloud), Redis — no local-only mode without credentials.
- **Multiple parallel sub-projects**: `ari_stylist/`, `ARI_PRODUCTION_CAMEL_0.27_CURRENT_BACKUP/`, `ARI_PRODUCTION_CAMEL_0.27_FINAL/`, `ARI_PRODUCTION_CAMEL_0.27_redis/`, `ARI_PRODUCTION_RESEARCH/`, `graph/`. Confirm the active target before editing.
- **`.env` in git history**: `ari_stylist/.env` contains live credentials (Neo4j password, OpenAI API key, Qdrant key). These should be rotated and the `.env` file added to `.gitignore`.
- **No root-level CI**: Only `ARI_PRODUCTION_RESEARCH/ari_crewai_migration/` has a GitHub Actions workflow. No CI runs on `master` branch PRs.
- **OpenAI API cost**: Battle system (CypherBot vs VibeBot vs JudgeAri) calls GPT-4/GPT-3.5 per request. Tests will incur API costs.
- **torch / ML deps**: `torch` and `torchvision` are ~2GB. Use CPU-only wheels on dev machines without GPU.
- **Python 3.10+**: Required for all variants. Python 3.13 is available in sandbox and compatible.
- **Not an iOS repo**: Despite any tool context suggesting iOS/Xcode, this is a Python AI/ML backend repo. No Xcode toolchain required.
