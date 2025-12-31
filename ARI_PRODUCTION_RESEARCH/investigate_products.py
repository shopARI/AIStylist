#!/usr/bin/env python3
"""
Investigate why wedding searches return 0 products despite 6M+ products in Qdrant
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def investigate_qdrant_products():
    """Investigate products in Qdrant to understand why wedding searches fail"""
    print("Investigating Qdrant Products...")
    
    try:
        from services.product.retriever import ProductRetrieverService
        
        qdrant = ProductRetrieverService(
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            collection_name=os.getenv("QDRANT_COLLECTION_NAME", "fashion_products")
        )
        
        await qdrant.initialize()
        
        # Test 1: Try searching with very low threshold
        print("\n Test 1: Wedding search with low threshold...")
        try:
            results = await qdrant.search_by_natural_language(
                query="dress for wedding",
                limit=5,
                score_threshold=0.0  # Very low threshold
            )
            print(f"   Results with threshold 0.0: {len(results)}")
            
            if results:
                for i, product in enumerate(results[:2]):
                    print(f"   {i+1}. {product.get('title', 'No Title')} (score: {product.get('score', 0):.4f})")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 2: Try basic searches to see what products exist
        print("\n Test 2: Basic product searches...")
        basic_queries = ["dress", "black", "formal", "women", "shirt"]
        
        for query in basic_queries:
            try:
                results = await qdrant.search_by_natural_language(
                    query=query,
                    limit=3,
                    score_threshold=0.0
                )
                print(f"   '{query}': {len(results)} results")
                if results:
                    sample = results[0]
                    print(f"     Sample: {sample.get('title', 'No Title')[:50]}...")
            except Exception as e:
                print(f"   '{query}' error: {e}")
        
        # Test 3: Try to get ANY products using metadata filters
        print("\n Test 3: Try metadata filtering...")
        try:
            # Try to get products by category
            results = await qdrant.get_products_by_filter(
                category="dress",
                limit=3
            )
            print(f"   Category='dress': {len(results)} results")
            
            if results:
                for i, product in enumerate(results):
                    print(f"   {i+1}. {product.get('title', 'No Title')}")
        except Exception as e:
            print(f"   Category filter error: {e}")
        
        # Test 4: Check if we can get popular products
        print("\n Test 4: Popular products...")
        try:
            results = await qdrant.get_popular_products(limit=3)
            print(f"   Popular products: {len(results)} results")
            
            if results:
                for i, product in enumerate(results):
                    title = product.get('title', 'No Title')
                    score = product.get('score', 0)
                    print(f"   {i+1}. {title[:50]}... (score: {score:.3f})")
        except Exception as e:
            print(f"   Popular products error: {e}")
        
        # Test 5: Try direct Qdrant scroll to see raw products
        print("\n Test 5: Raw product scroll...")
        try:
            # Use the qdrant client directly
            response = await asyncio.to_thread(
                qdrant.client.scroll,
                collection_name=qdrant.collection_name,
                limit=3,
                with_payload=True,
                with_vectors=False
            )
            
            products = response[0] if response else []
            print(f"   Raw scroll: {len(products)} products")
            
            for i, point in enumerate(products):
                if hasattr(point, 'payload'):
                    title = point.payload.get('title', 'No Title')
                    category = point.payload.get('category', 'No Category')
                    brand = point.payload.get('brand', 'No Brand')
                    print(f"   {i+1}. {title[:40]}... | {category} | {brand}")
                    
                    # Check if this product has wedding-related keywords
                    payload_text = str(point.payload).lower()
                    wedding_keywords = ['wedding', 'formal', 'elegant', 'dress', 'gown']
                    found_keywords = [kw for kw in wedding_keywords if kw in payload_text]
                    if found_keywords:
                        print(f"       Contains keywords: {found_keywords}")
        except Exception as e:
            print(f"   Raw scroll error: {e}")
        
        await qdrant.close()
        
    except Exception as e:
        print(f" Investigation failed: {e}")
        import traceback
        traceback.print_exc()

async def test_embedding_similarity():
    """Test if the embeddings are working correctly"""
    print("\n🧪 Testing Embedding Similarity...")
    
    try:
        from services.product.retriever import ProductRetrieverService
        
        qdrant = ProductRetrieverService(
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            collection_name=os.getenv("QDRANT_COLLECTION_NAME", "fashion_products")
        )
        
        await qdrant.initialize()
        
        # Test embedding generation
        test_queries = [
            "dress for wedding",
            "black dress",
            "formal attire",
            "casual shirt"
        ]
        
        for query in test_queries:
            embedding = await qdrant.get_embedding(query)
            if embedding:
                print(f"   '{query}': Embedding generated ({len(embedding)} dimensions)")
            else:
                print(f"   '{query}': No embedding generated")
        
        await qdrant.close()
        
    except Exception as e:
        print(f" Embedding test failed: {e}")

async def check_qdrant_collection_structure():
    """Check the structure and configuration of the Qdrant collection"""
    print("\nChecking Qdrant Collection Structure...")
    
    try:
        from services.product.retriever import ProductRetrieverService
        
        qdrant = ProductRetrieverService(
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            collection_name=os.getenv("QDRANT_COLLECTION_NAME", "fashion_products")
        )
        
        await qdrant.initialize()
        
        # Get detailed collection info
        try:
            collection_info = await asyncio.to_thread(
                qdrant.client.get_collection,
                collection_name=qdrant.collection_name
            )
            
            print(f"   Collection: {collection_info.name}")
            print(f"   Status: {collection_info.status}")
            print(f"   Points count: {collection_info.points_count}")
            print(f"   Vectors count: {collection_info.vectors_count}")
            print(f"   Indexed vectors: {collection_info.indexed_vectors_count}")
            print(f"   Config: {collection_info.config}")
            
        except Exception as e:
            print(f"   Could not get collection details: {e}")
        
        await qdrant.close()
        
    except Exception as e:
        print(f" Collection structure check failed: {e}")

async def main():
    """Run product investigation"""
    print("🕵️ Product Investigation - Why No Wedding Results?")
    print("=" * 60)
    
    await check_qdrant_collection_structure()
    await investigate_qdrant_products()
    await test_embedding_similarity()
    
    print("\n" + "=" * 60)
    print("Investigation Summary:")
    print("The issue might be:")
    print("1. Search threshold too high (default 0.3)")
    print("2. Products don't have wedding-related embeddings/text")
    print("3. Embedding model mismatch")
    print("4. Collection indexing issues")
    print("5. Products might be in different format than expected")

if __name__ == "__main__":
    asyncio.run(main())