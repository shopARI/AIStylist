# Lambda Migration Handoff Document

**Date:** January 5, 2026 (Updated)
**From:** GCloud VM (leo@gcloud)
**To:** Lambda Labs (ubuntu@192.18.143.49)
**Status:** ✅ MIGRATION COMPLETE

---

## Executive Summary

Lambda Labs is now **fully self-contained** with all services running locally:

| Service | Status | Data |
|---------|--------|------|
| **Neo4j** | ✅ Local Docker | 6.4M Products, 232K relationships |
| **Qdrant** | ✅ Local Docker | 17.4M vectors (3 collections) |
| **OpenAI** | Cloud API | Only external dependency |

No dependencies on GCloud VM - it can be shut down.

---

## 0. Quick Start (VSCode SSH)

### Connect via VSCode:
1. Open VSCode
2. `Cmd/Ctrl + Shift + P` → "Remote-SSH: Connect to Host"
3. Enter: `ubuntu@192.18.143.49` (or `lambda` if SSH config set up)
4. Open folder: `/home/ubuntu/AIStylist/ARI_PRODUCTION_RESEARCH`

### Verify everything works:
```bash
cd ~/AIStylist/ARI_PRODUCTION_RESEARCH
source venv/bin/activate

# Check services are running
sudo docker ps  # Should show: neo4j, qdrant

# Quick test
python3 -c "
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

# Qdrant
q = QdrantClient(url='http://localhost:6333')
print(f'Qdrant collections: {len(q.get_collections().collections)}')

# Neo4j
d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'shopari1234'))
with d.session() as s:
    r = s.run('MATCH (p:Product) RETURN count(p)').single()[0]
    print(f'Neo4j products: {r:,}')
d.close()
print('All systems operational!')
"
```

### If services aren't running:
```bash
sudo docker start qdrant neo4j
```

---

## 1. V3 Implementation Status

### Roadmap Document
See `ARI_V3_Implementation_Roadmap.md` for the full 10-step implementation plan.

### Current State
- **Onboarding System:** ~90% complete (6 conversation nodes, profile aggregation)
- **Embedding Pipeline:** Complete (SigLIP 1024d + OpenAI 1536d)
- **Three Pillars:** Framework exists, needs V3 refinement
- **Navigation Engine:** Core exists, needs InterpretableDimensions integration

### Key V3 Components to Build
1. `NavigationParameters` data structure
2. `InterpretableDimensions` (8 fashion dimensions)
3. 4-LLM orchestration (Navigator, Identifier, Describer, Presenter)
4. Enhanced feedback loop with preference learning

### Critical Files for V3
```
ARI_PRODUCTION_RESEARCH/
├── ari_crewai_migration/          # CrewAI agent implementation
│   ├── fashion_agents.py          # Agent definitions
│   ├── fashion_tasks.py           # Task definitions
│   └── navigation_crew.py         # Crew orchestration
├── onboarding/                    # User onboarding system
│   ├── onboarding_conversation.py # 6-node conversation flow
│   └── profile_aggregator.py      # Profile compilation
├── graph/phase1/                  # Embedding scripts
│   ├── run_openai_embeddings.py   # OpenAI text embeddings
│   └── balanced_enhanced_embeddings.py
└── run_fashionsig_multimodal_multi_image.py  # SigLIP visual embeddings
```

---

## 2. Lambda Labs Access

### SSH Connection
```bash
ssh lambda
# or explicitly:
ssh ubuntu@192.18.143.49 -i ~/.ssh/google_compute_engine
```

### Hardware
- **GPU:** NVIDIA A10 (23GB VRAM)
- **Storage:** 1.4TB SSD (~956GB available)
- **RAM:** 64GB+

---

## 3. Directory Structure on Lambda

```
/home/ubuntu/
├── AIStylist/
│   └── ARI_PRODUCTION_RESEARCH/    # Main project directory
│       ├── .env                     # Environment variables
│       ├── venv/                    # Python virtual environment
│       ├── ari_crewai_migration/
│       │   └── .env                 # CrewAI specific env
│       └── [all project files]
├── qdrant_storage/                  # Qdrant persistent data
├── qdrant_backup/                   # Backup JSON files (346GB)
├── restore_qdrant.py                # Restore script
├── fashionsig.env                   # FashionSigLIP config
└── ari-prod.pem                     # AWS key (chmod 600)
```

---

## 4. Environment Setup

### 4.1 Activate Python Environment
```bash
cd ~/AIStylist/ARI_PRODUCTION_RESEARCH
source venv/bin/activate
```

### 4.2 Verify Installation
```bash
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
print(f'GPU: {torch.cuda.get_device_name(0)}')

from qdrant_client import QdrantClient
from neo4j import GraphDatabase
import openai
print('All imports OK')
"
```

### 4.3 Environment Variables (.env)
The `.env` file is already configured for local services:
```bash
# Neo4j Connection (LOCAL) - ALREADY SET
NEO4J_URL=bolt://localhost:7687
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=shopari1234

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Qdrant (LOCAL) - ALREADY SET
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=fashion_products

# Service Config
NUM_WORKER_THREADS=4
API_PORT=5000
```

**NOTE:** `.env.backup` contains the old remote URLs if ever needed.

---

## 5. Qdrant Vector Database

### 5.1 Collections
| Collection | Dimensions | Points | Description |
|------------|-----------|--------|-------------|
| fashion_products | 1536 | 6,414,404 | OpenAI text embeddings |
| fashion_fashionsig_neo4j_1024d | 1024 | 6,409,367 | SigLIP visual embeddings |
| fashion_fashionsig_multimodal_multi | 2048 | 4,563,324 | Multimodal embeddings |
| mem0_memories | 1536 | ~3,400 | Memory store |
| mem0migrations | 1536 | ~40 | Migrations |

### 5.2 Qdrant Service Management
```bash
# Check status
sudo docker ps | grep qdrant

# Start Qdrant
sudo docker start qdrant

# Or run fresh:
sudo docker run -d --name qdrant \
    -p 6333:6333 -p 6334:6334 \
    -v ~/qdrant_storage:/qdrant/storage:z \
    --restart unless-stopped \
    qdrant/qdrant

# Verify
curl http://localhost:6333/collections
```

### 5.3 Check Restore Progress
```bash
# Quick status
curl -s http://localhost:6333/collections | python3 -m json.tool

# Detailed counts
for coll in fashion_products fashion_fashionsig_neo4j_1024d fashion_fashionsig_multimodal_multi; do
    count=$(curl -s "http://localhost:6333/collections/$coll" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('points_count',0))")
    echo "$coll: $count points"
done
```

### 5.4 Manual Restore (if needed)
```bash
cd ~/AIStylist/ARI_PRODUCTION_RESEARCH
source venv/bin/activate
python ~/restore_qdrant.py [collection_name]  # optional: specific collection
```

---

## 6. Service Connections

### 6.1 Test All Connections
```bash
cd ~/AIStylist/ARI_PRODUCTION_RESEARCH
source venv/bin/activate
python -c "
from dotenv import load_dotenv
import os
load_dotenv()

# OpenAI
print('OpenAI:', 'OK' if os.getenv('OPENAI_API_KEY','').startswith('sk-') else 'MISSING')

# Qdrant
from qdrant_client import QdrantClient
client = QdrantClient(url='http://localhost:6333')
colls = [c.name for c in client.get_collections().collections]
print(f'Qdrant: {len(colls)} collections', colls)

# Neo4j
from neo4j import GraphDatabase
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URL'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)
with driver.session() as s:
    r = s.run('RETURN 1').single()[0]
print(f'Neo4j: Connected (test={r})')
driver.close()
"
```

### 6.2 Service URLs (Local Mode)
| Service | URL | Notes |
|---------|-----|-------|
| Qdrant | http://localhost:6333 | Local Docker |
| Neo4j | bolt://localhost:7687 | Local Docker |
| OpenAI | api.openai.com | Cloud API |

### 6.3 Neo4j Local Setup
Neo4j runs locally on Lambda via Docker with the same credentials as production.

```bash
# Start Neo4j
sudo docker start neo4j

# Or run fresh:
sudo docker run -d --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -v ~/neo4j/data:/data \
    -v ~/neo4j/logs:/logs \
    -v ~/neo4j/import:/var/lib/neo4j/import \
    -e NEO4J_AUTH=neo4j/shopari1234 \
    --restart unless-stopped \
    neo4j:5.15.0

# Web UI: http://localhost:7474
# Bolt: bolt://localhost:7687
# Credentials: neo4j / shopari1234
```

### 6.4 Neo4j Data Import
To import the production database export:
```bash
cd ~/AIStylist/ARI_PRODUCTION_RESEARCH
source venv/bin/activate
pip install neo4j  # if not installed
python ~/import_neo4j.py --clear
```

The import includes:
- ~6.4M Product nodes
- Brand, Color, Style, Material nodes
- HAS_BRAND, HAS_COLOR, HAS_STYLE relationships

---

## 7. Running the System

### 7.1 Quick Start
```bash
ssh lambda
cd ~/AIStylist/ARI_PRODUCTION_RESEARCH
source venv/bin/activate

# Ensure Qdrant is running
sudo docker start qdrant

# Run your script
python your_script.py
```

### 7.2 Running Embedding Scripts
```bash
# OpenAI embeddings
python graph/phase1/run_openai_embeddings.py

# SigLIP visual embeddings (requires GPU)
python run_fashionsig_multimodal_multi_image.py
```

### 7.3 Running CrewAI Agents
```bash
cd ari_crewai_migration
source ../.env  # Load parent env
python navigation_crew.py
```

---

## 8. Migration Artifacts

### 8.1 Files Transferred
- `/home/ubuntu/qdrant_backup/` - 346GB Qdrant backup (JSON batches)
- `/home/ubuntu/restore_qdrant.py` - Restore script
- `/home/ubuntu/fashionsig.env` - FashionSigLIP configuration
- `/home/ubuntu/ari-prod.pem` - AWS credentials

### 8.2 SAM3 Folders (3D Object Generation)
| Folder | Size | Description |
|--------|------|-------------|
| `~/sam-3d-objects/` | 13GB | SAM 3D model checkpoints and code |
| `~/sam3/` | 130MB | SAM3 configuration and utilities |
| `~/sam3_product_outputs/` | 1.2GB | Generated 3D product outputs |

These folders contain the 3D object generation pipeline for product visualization.

### 8.3 Git Repository
The repo on Lambda may be behind. To update:
```bash
cd ~/AIStylist
git pull origin main
```

If authentication fails, the code is already present from previous clones.

---

## 9. Troubleshooting

### Qdrant not responding
```bash
sudo docker logs qdrant
sudo docker restart qdrant
```

### Python module not found
```bash
cd ~/AIStylist/ARI_PRODUCTION_RESEARCH
source venv/bin/activate
pip install <missing_module>
```

### GPU not detected
```bash
nvidia-smi  # Check GPU status
python -c "import torch; print(torch.cuda.is_available())"
```

### Neo4j connection timeout
- Check if GCloud firewall allows connection from Lambda IP
- Verify credentials in .env

---

## 10. Post-Migration Checklist

- [ ] Verify Qdrant restore completed (~17M total points)
- [ ] Update `.env` with `QDRANT_URL=http://localhost:6333`
- [ ] Test all service connections
- [ ] Pull latest git changes (if auth configured)
- [ ] Run a test query against each Qdrant collection
- [ ] Verify GPU is accessible for embedding generation
- [ ] Test CrewAI agent execution

---

## 11. Shutting Down GCloud

Once Lambda is verified working:

1. **Backup any remaining files** not in git
2. **Stop GCloud VM** from console
3. **Delete temp_qdrant_backup** on GCloud (346GB) if transfer confirmed
4. **Update DNS/firewall** if applicable

---

## Contact & Resources

- **V3 Roadmap:** `ARI_V3_Implementation_Roadmap.md`
- **GitHub:** https://github.com/LeoGondworworworworker/AIStylist
- **Lambda SSH:** `ssh lambda` (configured in ~/.ssh/config)

---

*Generated during GCloud → Lambda migration, January 2026*
