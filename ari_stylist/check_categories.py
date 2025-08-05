from qdrant_client import QdrantClient
import os
from collections import Counter

client = QdrantClient(
    url=os.environ.get("QDRANT_URL"),
    api_key=os.environ.get("QDRANT_API_KEY")
)

# Sample some products to see categories
categories = []
offset = None

print("Sampling categories from fashion_products...")
for _ in range(10):  # Get 10 batches
    records, offset = client.scroll(
        collection_name="fashion_products",
        limit=100,
        offset=offset,
        with_payload=True,
        with_vectors=False
    )
    
    for record in records:
        if record.payload.get('categories'):
            cats = record.payload['categories']
            if isinstance(cats, list):
                categories.extend(cats)
            else:
                categories.append(cats)
    
    if offset is None:
        break

# Count categories
cat_counts = Counter(categories)
print(f"\nTop 20 categories:")
for cat, count in cat_counts.most_common(20):
    print(f"  {cat}: {count}")

# Check for dress-related categories
print(f"\nDress-related categories:")
for cat, count in cat_counts.items():
    if 'dress' in cat.lower() or 'gown' in cat.lower() or 'wedding' in cat.lower():
        print(f"  {cat}: {count}")
