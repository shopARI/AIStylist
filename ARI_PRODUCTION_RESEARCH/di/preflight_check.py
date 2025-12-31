"""
Pre-flight Database Connection Check
Ensures all critical databases are available before starting any services.
SWE Requirement: "If there are no neo4j connections then no graceful failure but rather immediate"
"""

import asyncio
import logging
from typing import Dict, Any
import sys

logger = logging.getLogger("di.preflight_check")

async def preflight_database_check(settings) -> None:
    """
    Pre-flight check for all critical database connections.
    Fails immediately if any critical database is unavailable.
    
    Raises:
        SystemExit: If any critical database connection fails
    """
    logger.info(" Starting pre-flight database connection checks...")
    
    checks = []
    
    # Critical database checks
    checks.append(("Neo4j", _check_neo4j_connection(settings)))
    checks.append(("Qdrant", _check_qdrant_connection(settings)))
    checks.append(("Redis", _check_redis_connection(settings)))
    
    # Run all checks concurrently
    results = await asyncio.gather(*[check[1] for check in checks], return_exceptions=True)
    
    # Process results
    failed_services = []
    for i, (service_name, result) in enumerate(zip([check[0] for check in checks], results)):
        if isinstance(result, Exception):
            logger.error(f" {service_name} connection failed: {result}")
            failed_services.append(service_name)
        else:
            logger.info(f" {service_name} connection verified")
    
    # Immediate failure if any critical service is down
    if failed_services:
        error_msg = f"🚨 CRITICAL: Cannot start application. Database connections failed: {', '.join(failed_services)}"
        logger.error(error_msg)
        logger.error("🚨 Application will NOT start with missing database connections.")
        sys.exit(1)  # Immediate exit - no graceful degradation
    
    logger.info(" All database connections verified. Application can start safely.")


async def _check_neo4j_connection(settings) -> None:
    """Check Neo4j connection with single quick attempt."""
    try:
        from neo4j import AsyncGraphDatabase
        
        # Single attempt with short timeout
        driver = AsyncGraphDatabase.driver(
            settings.neo4j.url,
            auth=(settings.neo4j.username, settings.neo4j.password),
            connection_timeout=5  # 5 second timeout
        )
        
        # Quick connectivity test
        async with driver.session() as session:
            await asyncio.wait_for(session.run("RETURN 1 AS test"), timeout=5.0)
        
        await driver.close()
        
    except Exception as e:
        raise ConnectionError(f"Neo4j unavailable at {settings.neo4j.url}: {e}")


async def _check_qdrant_connection(settings) -> None:
    """Check Qdrant connection with single quick attempt."""
    try:
        from qdrant_client import AsyncQdrantClient
        
        # Single attempt with short timeout
        client = AsyncQdrantClient(
            url=settings.qdrant.url,
            api_key=getattr(settings.qdrant, 'api_key', None),
            timeout=5  # 5 second timeout
        )
        
        # Quick connectivity test
        await asyncio.wait_for(client.get_collections(), timeout=5.0)
        await client.close()
        
    except Exception as e:
        raise ConnectionError(f"Qdrant unavailable at {settings.qdrant.url}: {e}")


async def _check_redis_connection(settings) -> None:
    """Check Redis connection with single quick attempt."""
    try:
        import redis.asyncio as aioredis
        
        # Single attempt with short timeout
        client = aioredis.Redis.from_url(
            settings.redis.url or f"redis://{settings.redis.host}:{settings.redis.port}",
            password=settings.redis.password,
            db=settings.redis.db,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Quick connectivity test
        await asyncio.wait_for(client.ping(), timeout=5.0)
        await client.aclose()
        
    except Exception as e:
        redis_url = settings.redis.url or f"{settings.redis.host}:{settings.redis.port}"
        raise ConnectionError(f"Redis unavailable at {redis_url}: {e}")