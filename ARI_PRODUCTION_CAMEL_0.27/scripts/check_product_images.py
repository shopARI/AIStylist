#!/usr/bin/env python3
"""
Diagnostic script to check product image URLs in Neo4j
"""

import os
import sys
import asyncio
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.user.knowledge_graph import UserKnowledgeGraphService

async def check_product_images():
    """Check if products have valid, accessible image URLs"""

    # Initialize Neo4j service with correct parameters
    service = UserKnowledgeGraphService(
        url=os.getenv("NEO4J_URL", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "")
    )

    try:
        await service.initialize()
        print("Success Connected to Neo4j")

        # Get first 5 products with their images
        result = await service.query('''
            MATCH (p:Product)
            WHERE p.id IS NOT NULL AND p.images IS NOT NULL
            RETURN p.id as id, p.title as title, p.images as images, p.description as description
            ORDER BY p.id
            LIMIT 5
        ''')

        print(f"\nStats Found {len(result)} products to check:")
        print("=" * 60)

        for i, record in enumerate(result, 1):
            product_id = record.get("id")
            title = record.get("title", "No title")
            images = record.get("images", [])
            description = record.get("description", "No description")

            print(f"\n{i}. Product ID: {product_id}")
            print(f"   Title: {title[:50]}{'...' if len(title) > 50 else ''}")
            print(f"   Description: {description[:50] if description else 'None'}{'...' if description and len(description) > 50 else ''}")

            if not images:
                print("   Error No images found")
                continue

            if isinstance(images, str):
                # Handle case where images might be a string
                try:
                    import json
                    images = json.loads(images)
                except:
                    images = [images]

            print(f"   📸 Found {len(images)} image(s):")

            for j, img_url in enumerate(images[:3]):  # Check first 3 images
                print(f"      {j+1}. {img_url}")

                # Test if image URL is accessible
                try:
                    response = requests.head(img_url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '')
                        content_length = response.headers.get('content-length', 'Unknown')
                        print(f"         Success Accessible (Status: {response.status_code}, Type: {content_type}, Size: {content_length} bytes)")
                    else:
                        print(f"         Error HTTP {response.status_code}")
                except Exception as e:
                    print(f"         Error Error: {str(e)[:50]}...")

            if len(images) > 3:
                print(f"      ... and {len(images) - 3} more images")

        # Get summary statistics
        stats_result = await service.query('''
            MATCH (p:Product)
            WHERE p.id IS NOT NULL
            RETURN
                count(p) as total_products,
                count(p.images) as products_with_images,
                avg(size(p.images)) as avg_images_per_product
        ''')

        if stats_result:
            stats = stats_result[0]
            print(f"\nGrowth Summary Statistics:")
            print(f"   Total products: {stats.get('total_products', 0)}")
            print(f"   Products with images: {stats.get('products_with_images', 0)}")
            print(f"   Average images per product: {stats.get('avg_images_per_product', 0):.1f}")

    except Exception as e:
        print(f"Error Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await service.close()
        print("\n🔌 Disconnected from Neo4j")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(check_product_images())