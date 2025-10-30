#!/bin/bash
set -a
source .env
set +a
PYTHONPATH=/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration:/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27 ../crewai_env/bin/python test_mem0_integration.py
