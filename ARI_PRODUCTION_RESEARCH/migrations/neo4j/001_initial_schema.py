"""
Neo4j Migration: Initial Schema Setup
Creates basic nodes, relationships, and indexes for the fashion recommendation system
"""

async def up(neo4j_client):
    """Apply migration - create initial schema."""
    
    # Create constraints and indexes for User nodes
    await neo4j_client.run_query("""
        CREATE CONSTRAINT user_id_unique IF NOT EXISTS 
        FOR (u:User) REQUIRE u.id IS UNIQUE
    """)
    
    await neo4j_client.run_query("""
        CREATE INDEX user_email_index IF NOT EXISTS 
        FOR (u:User) ON (u.email)
    """)
    
    # Create constraints for Product nodes
    await neo4j_client.run_query("""
        CREATE CONSTRAINT product_id_unique IF NOT EXISTS 
        FOR (p:Product) REQUIRE p.id IS UNIQUE
    """)
    
    await neo4j_client.run_query("""
        CREATE INDEX product_category_index IF NOT EXISTS 
        FOR (p:Product) ON (p.category)
    """)
    
    # Create indexes for search optimization
    await neo4j_client.run_query("""
        CREATE INDEX product_title_text_index IF NOT EXISTS 
        FOR (p:Product) ON (p.title)
    """)
    
    # Create constraints for Style nodes
    await neo4j_client.run_query("""
        CREATE CONSTRAINT style_name_unique IF NOT EXISTS 
        FOR (s:Style) REQUIRE s.name IS UNIQUE
    """)
    
    # Create constraints for Brand nodes  
    await neo4j_client.run_query("""
        CREATE CONSTRAINT brand_name_unique IF NOT EXISTS 
        FOR (b:Brand) REQUIRE b.name IS UNIQUE
    """)
    
    # Create constraints for Color nodes
    await neo4j_client.run_query("""
        CREATE CONSTRAINT color_name_unique IF NOT EXISTS 
        FOR (c:Color) REQUIRE c.name IS UNIQUE
    """)
    
    # Create relationship indexes for performance
    await neo4j_client.run_query("""
        CREATE INDEX purchase_timestamp_index IF NOT EXISTS 
        FOR ()-[r:PURCHASED]->() ON (r.timestamp)
    """)
    
    await neo4j_client.run_query("""
        CREATE INDEX viewed_timestamp_index IF NOT EXISTS 
        FOR ()-[r:VIEWED]->() ON (r.timestamp)
    """)
    
    print(" Initial Neo4j schema created successfully")

async def down(neo4j_client):
    """Rollback migration - remove schema elements."""
    
    # Note: In production, be very careful with dropping constraints/indexes
    # This is mainly for development/testing
    
    constraints = [
        "user_id_unique",
        "product_id_unique", 
        "style_name_unique",
        "brand_name_unique",
        "color_name_unique"
    ]
    
    indexes = [
        "user_email_index",
        "product_category_index",
        "product_title_text_index",
        "purchase_timestamp_index",
        "viewed_timestamp_index"
    ]
    
    for constraint in constraints:
        try:
            await neo4j_client.run_query(f"DROP CONSTRAINT {constraint} IF EXISTS")
        except Exception as e:
            print(f"Warning: Could not drop constraint {constraint}: {e}")
    
    for index in indexes:
        try:
            await neo4j_client.run_query(f"DROP INDEX {index} IF EXISTS")
        except Exception as e:
            print(f"Warning: Could not drop index {index}: {e}")
    
    print(" Initial Neo4j schema rollback completed")