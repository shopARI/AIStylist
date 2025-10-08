#!/usr/bin/env python3
"""Check what keywords are in product descriptions."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

async def check_descriptions():
    from di.container import initialize_container

    print("Checking product descriptions for black dresses...")

    container = await initialize_container()
    app_service = await container.application_service()

    # Get CypherBot directly
    cypher_bot = app_service.battle_orchestrator.cypher_bot

    # Search for black dresses without formality filter
    query = """
    MATCH (p:Product)
    WHERE (p.title CONTAINS 'dress' OR p.description CONTAINS 'dress')
      AND (p.title CONTAINS 'black' OR p.description CONTAINS 'black')
    RETURN p
    LIMIT 20
    """

    results = await cypher_bot.neo4j.query(query, {})

    print(f"\nFound {len(results)} black dresses")
    print("="*80)

    for i, record in enumerate(results[:10], 1):
        product = dict(record['p'])
        title = product.get('title', 'NO TITLE')
        desc = product.get('description', 'NO DESCRIPTION')

        print(f"\n{i}. {title[:70]}")
        print(f"   Description: {desc[:150]}...")

        # Check for formality keywords
        desc_lower = desc.lower()
        formality_found = []
        for kw in ['professional', 'formal', 'business', 'polished', 'structured',
                   'sophisticated', 'tailored', 'classic', 'elegant', 'blazer',
                   'refined', 'chic', 'sleek']:
            if kw in desc_lower:
                formality_found.append(kw)

        if formality_found:
            print(f"   Formality keywords: {', '.join(formality_found)}")
        else:
            print(f"   Formality keywords: NONE")

    print("="*80)

if __name__ == "__main__":
    asyncio.run(check_descriptions())
