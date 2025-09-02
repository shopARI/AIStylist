#!/usr/bin/env python3
"""
Database Migration Runner for AIStylist
Handles schema changes across Neo4j, Qdrant, and Redis
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import importlib.util

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.settings import Settings
from services.user.knowledge_graph import UserKnowledgeGraphService
from services.product.retriever import ProductRetrieverService
from services.cache.redis_client import create_redis_service

logger = logging.getLogger("migrations")

class MigrationRunner:
    """Coordinates migrations across all database systems."""
    
    def __init__(self):
        self.settings = Settings()
        self.migration_history = {}
        
    async def run_all_migrations(self):
        """Run all pending migrations in correct order."""
        logger.info("Starting database migrations...")
        
        # Run migrations in order: Redis -> Neo4j -> Qdrant
        await self._run_redis_migrations()
        await self._run_neo4j_migrations() 
        await self._run_qdrant_migrations()
        
        logger.info("All migrations completed successfully!")
    
    async def _run_redis_migrations(self):
        """Run Redis schema migrations."""
        logger.info("Running Redis migrations...")
        
        redis_client = create_redis_service(
            url=self.settings.redis.url,
            host=self.settings.redis.host,
            port=self.settings.redis.port,
            password=self.settings.redis.password,
            db=self.settings.redis.db
        )
        
        await redis_client.initialize()
        
        # Load and run Redis migrations
        migrations_dir = Path(__file__).parent / "redis"
        await self._run_migrations_in_dir(migrations_dir, "redis", redis_client)
        
        await redis_client.close()
    
    async def _run_neo4j_migrations(self):
        """Run Neo4j schema migrations."""
        logger.info("Running Neo4j migrations...")
        
        neo4j_service = UserKnowledgeGraphService(
            url=self.settings.neo4j.url,
            username=self.settings.neo4j.username,
            password=self.settings.neo4j.password
        )
        
        await neo4j_service.initialize()
        
        # Load and run Neo4j migrations
        migrations_dir = Path(__file__).parent / "neo4j"
        await self._run_migrations_in_dir(migrations_dir, "neo4j", neo4j_service)
        
        await neo4j_service.close()
    
    async def _run_qdrant_migrations(self):
        """Run Qdrant schema migrations."""
        logger.info("Running Qdrant migrations...")
        
        qdrant_service = ProductRetrieverService(
            collection_name=self.settings.qdrant.collection_name
        )
        
        await qdrant_service.initialize()
        
        # Load and run Qdrant migrations
        migrations_dir = Path(__file__).parent / "qdrant"
        await self._run_migrations_in_dir(migrations_dir, "qdrant", qdrant_service)
        
        await qdrant_service.close()
    
    async def _run_migrations_in_dir(self, migrations_dir: Path, db_type: str, client):
        """Run all migration files in a directory."""
        if not migrations_dir.exists():
            logger.warning(f"No migrations directory found for {db_type}")
            return
        
        # Get all migration files and sort them
        migration_files = sorted([
            f for f in migrations_dir.glob("*.py") 
            if f.name != "__init__.py"
        ])
        
        for migration_file in migration_files:
            await self._run_migration_file(migration_file, db_type, client)
    
    async def _run_migration_file(self, migration_file: Path, db_type: str, client):
        """Run a single migration file."""
        migration_name = migration_file.stem
        
        # Check if already applied
        if await self._is_migration_applied(migration_name, db_type, client):
            logger.info(f"Skipping already applied migration: {migration_name}")
            return
        
        logger.info(f"Applying migration: {migration_name}")
        
        # Load and execute migration
        spec = importlib.util.spec_from_file_location(migration_name, migration_file)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        
        # Execute migration
        if hasattr(migration_module, 'up'):
            await migration_module.up(client)
            await self._record_migration(migration_name, db_type, client)
            logger.info(f"Successfully applied migration: {migration_name}")
        else:
            logger.error(f"Migration {migration_name} missing 'up' function")
    
    async def _is_migration_applied(self, migration_name: str, db_type: str, client) -> bool:
        """Check if a migration has been applied."""
        try:
            if db_type == "redis":
                result = await client.get(f"migration:{migration_name}")
                return result is not None
            elif db_type == "neo4j":
                query = "MATCH (m:Migration {name: $name}) RETURN m"
                result = await client.run_query(query, {"name": migration_name})
                return len(result) > 0
            elif db_type == "qdrant":
                # Store migration info in collection metadata or separate tracking
                # For now, assume all Qdrant migrations need to run
                return False
        except Exception as e:
            logger.warning(f"Could not check migration status for {migration_name}: {e}")
            return False
    
    async def _record_migration(self, migration_name: str, db_type: str, client):
        """Record that a migration has been applied."""
        try:
            if db_type == "redis":
                await client.set(f"migration:{migration_name}", "applied")
            elif db_type == "neo4j":
                query = """
                CREATE (m:Migration {
                    name: $name,
                    applied_at: datetime(),
                    db_type: $db_type
                })
                """
                await client.run_query(query, {
                    "name": migration_name,
                    "db_type": db_type
                })
        except Exception as e:
            logger.error(f"Could not record migration {migration_name}: {e}")

async def main():
    """Main entry point for migration runner."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    runner = MigrationRunner()
    await runner.run_all_migrations()

if __name__ == "__main__":
    asyncio.run(main())