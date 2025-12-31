"""
Crews package initialization.
Handles import path setup for production environment.
"""

# Ensure parent paths are available
import sys
import os

parent_path = '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27'
migration_path = '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration'

if parent_path not in sys.path:
    sys.path.insert(0, parent_path)
if migration_path not in sys.path:
    sys.path.insert(0, migration_path)
