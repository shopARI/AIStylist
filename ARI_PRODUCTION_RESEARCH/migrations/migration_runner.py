#!/usr/bin/env python3
"""
Database Migration Runner for AIStylist
Handles schema changes across Neo4j, Qdrant, and Redis
"""

import asyncio
import logging
import os
import sys
import time
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
        """Run a single migration file with rollback support."""
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
        
        # Validate migration has required functions
        if not hasattr(migration_module, 'up'):
            logger.error(f"Migration {migration_name} missing 'up' function")
            return
            
        # Check for rollback support
        has_rollback = hasattr(migration_module, 'down')
        if not has_rollback:
            logger.warning(f"Migration {migration_name} has no 'down' function - rollback not supported")
        
        try:
            # Execute migration
            await migration_module.up(client)
            await self._record_migration(migration_name, db_type, client, has_rollback)
            logger.info(f"Successfully applied migration: {migration_name}")
            
        except Exception as e:
            logger.error(f"Failed to apply migration {migration_name}: {e}")
            
            # Attempt automatic rollback if available
            if has_rollback:
                logger.info(f"Attempting rollback for failed migration: {migration_name}")
                try:
                    await migration_module.down(client)
                    logger.info(f"Successfully rolled back failed migration: {migration_name}")
                except Exception as rollback_error:
                    logger.error(f"Rollback failed for {migration_name}: {rollback_error}")
            
            raise
    
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
    
    async def _record_migration(self, migration_name: str, db_type: str, client, has_rollback: bool = False):
        """Record that a migration has been applied."""
        try:
            if db_type == "redis":
                migration_data = {
                    "status": "applied",
                    "applied_at": time.time(),
                    "has_rollback": has_rollback
                }
                await client.set_json(f"migration:{migration_name}", migration_data)
                
            elif db_type == "neo4j":
                query = """
                CREATE (m:Migration {
                    name: $name,
                    applied_at: datetime(),
                    db_type: $db_type,
                    has_rollback: $has_rollback,
                    status: 'applied'
                })
                """
                await client.run_query(query, {
                    "name": migration_name,
                    "db_type": db_type,
                    "has_rollback": has_rollback
                })
        except Exception as e:
            logger.error(f"Could not record migration {migration_name}: {e}")
    
    async def rollback_migration(self, migration_name: str):
        """Rollback a specific migration across all databases."""
        logger.info(f"Starting rollback for migration: {migration_name}")
        
        # Rollback in reverse order: Qdrant -> Neo4j -> Redis
        await self._rollback_qdrant_migration(migration_name)
        await self._rollback_neo4j_migration(migration_name)
        await self._rollback_redis_migration(migration_name)
        
        logger.info(f"Rollback completed for migration: {migration_name}")
    
    async def rollback_last_migration(self):
        """Rollback the most recently applied migration."""
        # Find the most recent migration from each database
        # This is a simplified implementation - you might want more sophisticated logic
        logger.info("Rolling back last migration from each database")
        
        # For now, this would need to be implemented based on your specific needs
        logger.warning("rollback_last_migration not fully implemented - manual rollback required")
    
    async def _rollback_redis_migration(self, migration_name: str):
        """Rollback a Redis migration."""
        logger.info(f"Rolling back Redis migration: {migration_name}")
        
        redis_client = create_redis_service(
            url=self.settings.redis.url,
            host=self.settings.redis.host,
            port=self.settings.redis.port,
            password=self.settings.redis.password,
            db=self.settings.redis.db
        )
        
        await redis_client.initialize()
        
        try:
            # Load migration module
            migrations_dir = Path(__file__).parent / "redis"
            migration_file = migrations_dir / f"{migration_name}.py"
            
            if not migration_file.exists():
                logger.error(f"Migration file not found: {migration_file}")
                return
            
            # Load and execute rollback
            spec = importlib.util.spec_from_file_location(migration_name, migration_file)
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            
            if hasattr(migration_module, 'down'):
                await migration_module.down(redis_client)
                await redis_client.delete(f"migration:{migration_name}")
                logger.info(f"Successfully rolled back Redis migration: {migration_name}")
            else:
                logger.warning(f"No rollback function found for Redis migration: {migration_name}")
                
        except Exception as e:
            logger.error(f"Failed to rollback Redis migration {migration_name}: {e}")
        finally:
            await redis_client.close()
    
    async def _rollback_neo4j_migration(self, migration_name: str):
        """Rollback a Neo4j migration."""
        logger.info(f"Rolling back Neo4j migration: {migration_name}")
        
        neo4j_service = UserKnowledgeGraphService(
            url=self.settings.neo4j.url,
            username=self.settings.neo4j.username,
            password=self.settings.neo4j.password
        )
        
        await neo4j_service.initialize()
        
        try:
            # Load migration module
            migrations_dir = Path(__file__).parent / "neo4j"
            migration_file = migrations_dir / f"{migration_name}.py"
            
            if not migration_file.exists():
                logger.error(f"Migration file not found: {migration_file}")
                return
            
            # Load and execute rollback
            spec = importlib.util.spec_from_file_location(migration_name, migration_file)
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            
            if hasattr(migration_module, 'down'):
                await migration_module.down(neo4j_service)
                # Remove migration record
                query = "MATCH (m:Migration {name: $name}) DELETE m"
                await neo4j_service.run_query(query, {"name": migration_name})
                logger.info(f"Successfully rolled back Neo4j migration: {migration_name}")
            else:
                logger.warning(f"No rollback function found for Neo4j migration: {migration_name}")
                
        except Exception as e:
            logger.error(f"Failed to rollback Neo4j migration {migration_name}: {e}")
        finally:
            await neo4j_service.close()
    
    async def _rollback_qdrant_migration(self, migration_name: str):
        """Rollback a Qdrant migration."""
        logger.info(f"Rolling back Qdrant migration: {migration_name}")
        
        qdrant_service = ProductRetrieverService(
            collection_name=self.settings.qdrant.collection_name
        )
        
        await qdrant_service.initialize()
        
        try:
            # Load migration module
            migrations_dir = Path(__file__).parent / "qdrant"
            migration_file = migrations_dir / f"{migration_name}.py"
            
            if not migration_file.exists():
                logger.error(f"Migration file not found: {migration_file}")
                return
            
            # Load and execute rollback
            spec = importlib.util.spec_from_file_location(migration_name, migration_file)
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            
            if hasattr(migration_module, 'down'):
                await migration_module.down(qdrant_service)
                logger.info(f"Successfully rolled back Qdrant migration: {migration_name}")
            else:
                logger.warning(f"No rollback function found for Qdrant migration: {migration_name}")
                
        except Exception as e:
            logger.error(f"Failed to rollback Qdrant migration {migration_name}: {e}")
        finally:
            await qdrant_service.close()

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