"""
Verify Mem0 semantic relationships in Neo4j graph.
"""
import asyncio
import os
import sys

sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration')
sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

from neo4j import GraphDatabase


async def check_neo4j_mem0_graph():
    """Check if Mem0 has created semantic relationships in Neo4j."""

    # Connect to Neo4j
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER')
    password = os.getenv('NEO4J_PASSWORD')

    if not all([uri, user, password]):
        print("ERROR: Neo4j credentials not set in environment")
        return

    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session(database="users") as session:
            print("\n" + "=" * 70)
            print("CHECKING MEM0 SEMANTIC RELATIONSHIPS IN NEO4J")
            print("=" * 70)

            # Check for Mem0-created nodes
            print("\n1. Checking for Mem0 memory nodes...")
            result = session.run("""
                MATCH (n)
                WHERE labels(n) <> []
                RETURN DISTINCT labels(n) as labels, count(*) as count
                ORDER BY count DESC
                LIMIT 20
            """)

            labels_found = list(result)
            if labels_found:
                print(f"   Found {len(labels_found)} different node types:")
                for record in labels_found:
                    print(f"     - {record['labels']}: {record['count']} nodes")
            else:
                print("   No nodes found in graph")

            # Check for relationships
            print("\n2. Checking for relationships...")
            result = session.run("""
                MATCH ()-[r]->()
                RETURN DISTINCT type(r) as rel_type, count(*) as count
                ORDER BY count DESC
                LIMIT 20
            """)

            rels_found = list(result)
            if rels_found:
                print(f"   Found {len(rels_found)} different relationship types:")
                for record in rels_found:
                    print(f"     - {record['rel_type']}: {record['count']} relationships")
            else:
                print("   No relationships found in graph")

            # Check for User nodes (from Mem0)
            print("\n3. Checking for User nodes...")
            result = session.run("""
                MATCH (u:User)
                RETURN count(u) as count
            """)
            user_count = result.single()['count']
            print(f"   Found {user_count} User nodes")

            # Sample semantic relationships
            if user_count > 0:
                print("\n4. Sample user semantic relationships...")
                result = session.run("""
                    MATCH (u:User)-[r]-(n)
                    RETURN u.id as user_id, type(r) as relationship, labels(n)[0] as target_type, n.name as target_name
                    LIMIT 10
                """)

                sample_rels = list(result)
                if sample_rels:
                    for record in sample_rels:
                        print(f"     User({record['user_id']}) -{record['relationship']}-> {record['target_type']}({record['target_name']})")
                else:
                    print("     No user relationships found")

            print("\n" + "=" * 70)
            print("VERIFICATION COMPLETE")
            print("=" * 70)

    finally:
        driver.close()


if __name__ == "__main__":
    asyncio.run(check_neo4j_mem0_graph())
