"""
Redis Migration: Setup Key Structure and Policies
Configures Redis for optimal performance with the AIStylist application
"""

async def up(redis_client):
    """Apply migration - setup Redis key structure and policies."""
    
    # Set up key expiration policies and memory optimization
    
    # 1. Configure maxmemory policy for LRU eviction (if Redis admin allows)
    try:
        # This may require admin privileges
        await redis_client.client.config_set("maxmemory-policy", "allkeys-lru")
        print("✅ Set Redis maxmemory-policy to allkeys-lru")
    except Exception as e:
        print(f"⚠️ Could not set maxmemory-policy (may require admin): {e}")
    
    # 2. Set up default TTLs for different key types
    key_ttl_config = {
        "session:*": 86400,      # 24 hours for session data
        "embedding:*": 3600,     # 1 hour for embedding cache
        "battles:*": 300,        # 5 minutes for battle state
        "conversation:*": 604800, # 1 week for conversation history
        "user_preferences:*": 2592000,  # 30 days for user preferences
        "cache:*": 1800          # 30 minutes for general cache
    }
    
    # Store TTL configuration in Redis for application reference
    await redis_client.client.hset(
        "config:key_ttls", 
        mapping={k: str(v) for k, v in key_ttl_config.items()}
    )
    print("✅ Configured default TTL policies for key patterns")
    
    # 3. Set up Redis key naming conventions documentation
    key_conventions = {
        "session": "session:{session_id} - User session data",
        "embedding": "embedding:{hash} - Cached embeddings", 
        "battle": "battles:{type}:{id} - Battle state and counters",
        "conversation": "conversation:{session_id}:{user_id} - Chat history",
        "preferences": "user_preferences:{user_id} - User preferences",
        "cache": "cache:{type}:{key} - General application cache",
        "migration": "migration:{name} - Migration tracking"
    }
    
    await redis_client.client.hset(
        "config:key_conventions",
        mapping=key_conventions
    )
    print("✅ Documented key naming conventions")
    
    # 4. Initialize migration tracking
    await redis_client.client.set("migration:redis_setup", "applied")
    print("✅ Initialized migration tracking in Redis")
    
    # 5. Set up monitoring keys
    await redis_client.client.set("stats:redis_migration_date", str(int(__import__('time').time())))
    await redis_client.client.set("stats:redis_version", "initial")
    
    print("✅ Redis key structure and policies configured successfully")

async def down(redis_client):
    """Rollback migration - clean up Redis configuration."""
    
    # Remove configuration keys
    config_keys = [
        "config:key_ttls",
        "config:key_conventions", 
        "migration:redis_setup",
        "stats:redis_migration_date",
        "stats:redis_version"
    ]
    
    for key in config_keys:
        try:
            await redis_client.client.delete(key)
        except Exception as e:
            print(f"Warning: Could not delete key {key}: {e}")
    
    # Note: We don't reset maxmemory-policy as it might affect other applications
    
    print("✅ Redis configuration rollback completed")