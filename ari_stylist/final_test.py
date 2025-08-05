import os
import asyncio
from product_retriever_async_enhanced import ProductRetrieverAsync

async def test_everything():
    print(f"Using collection: {os.environ.get('QDRANT_COLLECTION_NAME', 'fashion_products')}")
    
    retriever = ProductRetrieverAsync()
    
    # Get stats
    stats = await retriever.get_collection_stats()
    print(f"\nCollection stats: {stats}")
    
    # Test search
    results = await retriever.search_by_natural_language("elegant dress for wedding", limit=3)
    print(f"\nSearch found {len(results)} results")
    
    if results:
        product = results[0]
        print(f"\nFirst product:")
        print(f"  ID: {product.get('id')}")
        print(f"  Title: {product.get('title')}")
        print(f"  Category: {product.get('category')}")
        print(f"  Price: ${product.get('price')}")
        
asyncio.run(test_everything())
