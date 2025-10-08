#!/usr/bin/env python3
"""Check what fields exist on Neo4j Product nodes."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

async def check_fields():
    from di.container import initialize_container

    print("Checking Neo4j Product fields...")

    container = await initialize_container()
    neo4j = await container.neo4j_client()

    # Get one product
    result = await neo4j.query('MATCH (p:Product) RETURN p LIMIT 1')

    if not result:
        print("No products found in Neo4j!")
        return

    product = dict(result[0]['p'])

    print(f"\nFound product with {len(product)} fields:")
    print("="*60)

    for key in sorted(product.keys()):
        value = product[key]
        value_type = type(value).__name__

        # Show sample value
        if isinstance(value, str):
            sample = value[:50] + "..." if len(value) > 50 else value
        elif isinstance(value, list):
            sample = f"[{len(value)} items]"
        else:
            sample = str(value)

        print(f"  {key:20s} ({value_type:10s}): {sample}")

    print("="*60)

if __name__ == "__main__":
    asyncio.run(check_fields())
