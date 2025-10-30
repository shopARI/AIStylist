#!/bin/bash
cd /home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration
set -a
source .env
set +a
PYTHONPATH=/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration:/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27 ../crewai_env/bin/python scripts/migrate_to_mem0.py
