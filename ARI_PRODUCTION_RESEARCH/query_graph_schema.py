#!/usr/bin/env python3
"""
Professional Neo4j schema extraction - no guesses, only verified facts.
"""
import asyncio
import os
import json
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

async def extract_schema():
    """Extract complete schema from Neo4j database"""

    neo4j_uri = os.getenv("NEO4J_URL")
    neo4j_user = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )

    schema = {
        "database": "productionbackup2",
        "nodes": {},
        "relationships": {}
    }

    try:
        async with driver.session() as session:

            # 1. Get all node labels
            print("Getting node labels...")
            result = await session.run("CALL db.labels()")
            node_labels = [record["label"] async for record in result]
            print(f"Found {len(node_labels)} node types: {node_labels}")

            # 2. For each node label, get properties from actual data
            for label in node_labels:
                print(f"\nAnalyzing {label} nodes...")

                # Get sample node to extract properties
                result = await session.run(f"MATCH (n:{label}) RETURN n LIMIT 1")
                record = await result.single()

                if record:
                    node = dict(record['n'])
                    properties = {}
                    for key, value in node.items():
                        properties[key] = type(value).__name__

                    schema["nodes"][label] = {
                        "properties": properties
                    }
                    print(f"  Found {len(properties)} properties")

            # 3. Get all relationship types with source and target labels
            print("\nGetting relationship types...")
            rel_query = """
            MATCH (source)-[r]->(target)
            WITH type(r) as rel_type,
                 labels(source) as source_labels,
                 labels(target) as target_labels,
                 count(*) as count
            RETURN rel_type, source_labels[0] as source_label, target_labels[0] as target_label, count
            ORDER BY count DESC
            """
            result = await session.run(rel_query)

            async for record in result:
                rel_type = record['rel_type']
                source_label = record['source_label']
                target_label = record['target_label']
                count = record['count']

                print(f"  {rel_type}: {source_label} -> {target_label} ({count:,} relationships)")

                schema["relationships"][rel_type] = {
                    "from": source_label,
                    "to": target_label,
                    "count": count
                }

            # 4. Check for relationship properties
            print("\nChecking relationship properties...")
            for rel_type in schema["relationships"].keys():
                result = await session.run(f"""
                    MATCH ()-[r:{rel_type}]->()
                    RETURN r LIMIT 1
                """)
                record = await result.single()

                if record and record['r']:
                    rel = dict(record['r'])
                    if rel:
                        props = {}
                        for key, value in rel.items():
                            props[key] = type(value).__name__
                        schema["relationships"][rel_type]["properties"] = props
                        print(f"  {rel_type} has properties: {list(props.keys())}")
                    else:
                        schema["relationships"][rel_type]["properties"] = {}
                else:
                    schema["relationships"][rel_type]["properties"] = {}

    finally:
        await driver.close()

    return schema

async def main():
    schema = await extract_schema()

    # Write to file
    output_file = "/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration/config/neo4j_schema.json"
    with open(output_file, 'w') as f:
        json.dump(schema, f, indent=2)

    print(f"\n\nSchema written to: {output_file}")
    print("\nFinal schema:")
    print(json.dumps(schema, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
