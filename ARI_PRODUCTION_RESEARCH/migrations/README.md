# Database Migrations for AIStylist

This directory contains database migration scripts for the AIStylist production system. These migrations ensure consistent schema changes across Neo4j, Qdrant, and Redis databases.

## Overview

The migration system supports three database types:
- **Neo4j**: Graph database schema (nodes, relationships, indexes, constraints)
- **Qdrant**: Vector database collections and configurations
- **Redis**: Key structures, TTL policies, and configuration

## Directory Structure

```
migrations/
├── migration_runner.py      # Main migration coordinator
├── README.md               # This file
├── neo4j/                  # Neo4j schema migrations
│   ├── 001_initial_schema.py
│   └── ...
├── qdrant/                 # Qdrant collection migrations  
│   ├── 001_create_fashion_collection.py
│   └── ...
└── redis/                  # Redis configuration migrations
    ├── 001_setup_key_structure.py
    └── ...
```

## Usage

### Running All Migrations

```bash
# From the project root
python migrations/migration_runner.py
```

### Migration File Format

Each migration file must have an `up()` function and optionally a `down()` function:

```python
async def up(client):
    """Apply the migration."""
    # Migration logic here
    pass

async def down(client):
    """Rollback the migration (optional)."""
    # Rollback logic here
    pass
```

### Naming Convention

Migration files should be named with a 3-digit prefix followed by a descriptive name:
- `001_initial_schema.py`
- `002_add_user_preferences.py`
- `003_optimize_product_indexes.py`

## Migration Tracking

- **Neo4j**: Migrations tracked in `Migration` nodes
- **Redis**: Migrations tracked with `migration:{name}` keys
- **Qdrant**: Currently no built-in tracking (migrations run every time)

## Safety Guidelines

1. **Test First**: Always test migrations on a copy of production data
2. **Backup**: Take database backups before running migrations
3. **Rollback Plan**: Ensure rollback procedures are documented
4. **Incremental**: Keep migrations small and focused
5. **Non-destructive**: Avoid dropping data in production migrations

## Production Deployment

1. Review all pending migrations
2. Backup databases
3. Run migrations during maintenance window
4. Verify schema changes
5. Monitor application health

## Example Migration Workflow

```bash
# 1. Create new migration file
touch migrations/neo4j/002_add_recommendation_scores.py

# 2. Implement up() and down() functions
# 3. Test on staging environment  
# 4. Deploy to production during maintenance window
python migrations/migration_runner.py
```

## Troubleshooting

### Connection Issues
- Verify database connection settings in `config/settings.py`
- Check that databases are running and accessible
- Ensure proper authentication credentials

### Migration Failures
- Check logs for specific error messages
- Verify migration syntax and dependencies
- Rollback failed migrations if possible
- Contact database administrators for constraint/permission issues

### Performance Considerations
- Large index creations may take significant time
- Consider running heavy migrations during low-traffic periods
- Monitor database performance during and after migrations

## Best Practices

1. **Version Control**: All migrations should be committed to git
2. **Code Review**: Have migrations reviewed before production deployment
3. **Documentation**: Include comments explaining complex migrations
4. **Dependencies**: Ensure migrations can run in any environment
5. **Monitoring**: Monitor application health after schema changes