#!/usr/bin/env python3
"""
FashionSigLIP using OpenCLIP directly - Avoiding HuggingFace transformers issues
"""

import os
import sys
import asyncio
import logging
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import time
from datetime import datetime
import uuid
import hashlib

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("openclip_fashionsig")

def load_environment():
    """Load environment variables"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Success Environment loaded")
    except ImportError:
        logger.warning("Warning  python-dotenv not available, using OS environment")

async def test_neo4j_connection():
    """Test Neo4j connection and fetch products"""
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URL", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USERNAME", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "")
            )
        )

        # Test connection
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            result.single()

        logger.info("Success Neo4j connection successful")
        return driver

    except Exception as e:
        logger.error(f"Error Neo4j connection failed: {e}")
        return None

async def fetch_products(driver, limit: int = 5):
    """Fetch products with images from Neo4j"""
    query = """
    MATCH (p:Product)
    WHERE p.id IS NOT NULL AND p.images IS NOT NULL
    RETURN p.id as id, p.title as title, p.images as images,
           p.description as description
    ORDER BY p.id
    LIMIT $limit
    """

    try:
        with driver.session() as session:
            result = session.run(query, {"limit": limit})
            products = [record.data() for record in result]
            logger.info(f"📦 Fetched {len(products)} products")
            return products
    except Exception as e:
        logger.error(f"Error Failed to fetch products: {e}")
        return []

def setup_openclip_fashionsig():
    """Initialize FashionSigLIP using OpenCLIP"""
    try:
        import torch
        import open_clip
        from PIL import Image
        import numpy as np

        logger.info("Loading Loading OpenCLIP FashionSigLIP...")

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {device}")

        # Load FashionSigLIP model using OpenCLIP
        model_name = "hf-hub:Marqo/marqo-fashionSigLIP"

        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name,
            device=device,
            cache_dir="/home/leo/.cache/huggingface"
        )

        tokenizer = open_clip.get_tokenizer(model_name)

        model.eval()
        logger.info("Success OpenCLIP FashionSigLIP loaded successfully")

        return model, preprocess, tokenizer, device, torch, np

    except Exception as e:
        logger.error(f"Error OpenCLIP FashionSigLIP setup failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, None, None

def setup_qdrant():
    """Initialize Qdrant client"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        client = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY"),
            prefer_grpc=False
        )

        collections = client.get_collections().collections
        logger.info(f"Success Qdrant connected ({len(collections)} collections)")

        return client, VectorParams, Distance

    except Exception as e:
        logger.error(f"Error Qdrant setup failed: {e}")
        return None, None, None

async def process_products_openclip(products, model, preprocess, tokenizer, device, torch, np, qdrant_client):
    """Process products with OpenCLIP FashionSigLIP"""

    # Setup collection
    collection_name = "fashion_multimodal_embeddings"

    if qdrant_client:
        try:
            from qdrant_client.models import VectorParams, Distance

            # Get embedding dimension with a test
            with torch.no_grad():
                test_image = Image.new('RGB', (224, 224))
                test_image_tensor = preprocess(test_image).unsqueeze(0).to(device)
                test_text_tokens = tokenizer(["test"]).to(device)

                image_features = model.encode_image(test_image_tensor)
                text_features = model.encode_text(test_text_tokens)

                embedding_dim = image_features.shape[-1]
                logger.info(f"Search Embedding dimension: {embedding_dim}")

            # Create or verify collection
            collections = qdrant_client.get_collections().collections
            collection_exists = any(c.name == collection_name for c in collections)

            if not collection_exists:
                logger.info(f"Creating OpenCLIP collection: {collection_name}")
                qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "image": VectorParams(
                            size=embedding_dim,
                            distance=Distance.COSINE
                        ),
                        "text": VectorParams(
                            size=embedding_dim,
                            distance=Distance.COSINE
                        ),
                        "combined": VectorParams(
                            size=embedding_dim * 2,
                            distance=Distance.COSINE
                        )
                    }
                )
                logger.info("Success Collection created successfully")
            else:
                logger.info(f"Success Collection '{collection_name}' exists")

        except Exception as e:
            logger.error(f"Error Collection setup failed: {e}")
            qdrant_client = None

    results = []

    for i, product in enumerate(products, 1):
        logger.info(f"Loading Processing product {i}/{len(products)}: {product['title'][:50]}...")

        try:
            # Prepare text
            text_content = []
            for field in ['title', 'description']:
                if product.get(field):
                    text_content.append(str(product[field]))

            full_text = " ".join(filter(None, text_content))
            text_words = full_text.split()[:40]  # Limit for token constraints
            text = " ".join(text_words)
            logger.info(f"   Text ({len(text_words)} words): {text[:100]}...")

            # Process images
            images_data = product.get('images', [])
            if isinstance(images_data, str):
                try:
                    images_data = json.loads(images_data)
                except:
                    images_data = [images_data]

            logger.info(f"   Found {len(images_data)} image(s)")

            embeddings_created = []

            for j, img_path in enumerate(images_data[:3]):
                try:
                    # Format URL
                    if not img_path.startswith(('http://', 'https://')):
                        img_url = f"https://app.shopari.com/images/{img_path}"
                    else:
                        img_url = img_path

                    logger.info(f"   📥 Downloading image {j+1}: {img_url}")

                    # Download and process image
                    response = requests.get(img_url, timeout=10)
                    response.raise_for_status()

                    from io import BytesIO
                    from PIL import Image

                    img = Image.open(BytesIO(response.content)).convert('RGB')
                    logger.info(f"   Image loaded: {img.size}")

                    # Generate embeddings with OpenCLIP
                    with torch.no_grad():
                        # Process image
                        image_tensor = preprocess(img).unsqueeze(0).to(device)
                        image_features = model.encode_image(image_tensor)
                        image_embedding = image_features.cpu().numpy().flatten()

                        # Process text
                        text_tokens = tokenizer([text]).to(device)
                        text_features = model.encode_text(text_tokens)
                        text_embedding = text_features.cpu().numpy().flatten()

                        # Normalize embeddings (OpenCLIP standard)
                        image_embedding = image_embedding / np.linalg.norm(image_embedding)
                        text_embedding = text_embedding / np.linalg.norm(text_embedding)

                        # Combined embedding
                        combined_embedding = np.concatenate([image_embedding, text_embedding])

                    logger.info(f"   Success OpenCLIP FashionSigLIP embeddings created:")
                    logger.info(f"      Image: {len(image_embedding)} dims, {np.count_nonzero(image_embedding)} non-zero")
                    logger.info(f"      Text:  {len(text_embedding)} dims, {np.count_nonzero(text_embedding)} non-zero")

                    # Upload to Qdrant
                    qdrant_uploaded = False
                    if qdrant_client:
                        try:
                            from qdrant_client.models import PointStruct

                            unique_string = f"{product['id']}_img_{j}"
                            hash_object = hashlib.md5(unique_string.encode())
                            point_id = str(uuid.UUID(hash_object.hexdigest()))

                            point = PointStruct(
                                id=point_id,
                                vector={
                                    "image": image_embedding.tolist(),
                                    "text": text_embedding.tolist(),
                                    "combined": combined_embedding.tolist()
                                },
                                payload={
                                    "product_id": product['id'],
                                    "title": product['title'][:200],
                                    "text_content": text[:200],
                                    "image_index": j,
                                    "image_url": img_url,
                                    "image_size": f"{img.size[0]}x{img.size[1]}",
                                    "model_used": "openclip_fashionsig",
                                    "embedding_dims": len(image_embedding),
                                    "timestamp": datetime.now().isoformat(),
                                    "approach": "openclip_fashionsig"
                                }
                            )

                            qdrant_client.upsert(
                                collection_name=collection_name,
                                points=[point]
                            )

                            logger.info(f"   Starting Uploaded to Qdrant: {point_id}")
                            qdrant_uploaded = True

                        except Exception as upload_error:
                            logger.error(f"   Error Qdrant upload failed: {upload_error}")

                    embedding_result = {
                        "product_id": product['id'],
                        "image_index": j,
                        "image_url": img_url,
                        "image_size": img.size,
                        "text_content": text[:200],
                        "embedding_dim": len(image_embedding),
                        "qdrant_uploaded": qdrant_uploaded,
                        "timestamp": datetime.now().isoformat(),
                        "model_used": "openclip_fashionsig"
                    }

                    embeddings_created.append(embedding_result)

                except Exception as e:
                    logger.error(f"   Error Image {j+1} processing failed: {e}")
                    continue

            product_result = {
                "product_id": product['id'],
                "title": product['title'],
                "embeddings_created": len(embeddings_created),
                "embeddings": embeddings_created,
                "status": "success" if embeddings_created else "no_embeddings"
            }

            results.append(product_result)
            logger.info(f"   Success Product processed: {len(embeddings_created)} embeddings")

        except Exception as e:
            logger.error(f"   Error Product processing failed: {e}")
            results.append({
                "product_id": product['id'],
                "title": product['title'],
                "status": "error",
                "error": str(e)
            })

    return results

async def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description='OpenCLIP FashionSigLIP precomputation')
    parser.add_argument('--limit', type=int, default=10000000, help='Number of products to process')
    args = parser.parse_args()

    logger.info(f"Starting Starting OpenCLIP FashionSigLIP precomputation (limit: {args.limit})")

    # Load environment
    load_environment()

    # Setup connections
    neo4j_driver = await test_neo4j_connection()
    if not neo4j_driver:
        return

    products = await fetch_products(neo4j_driver, args.limit)
    if not products:
        return

    # Setup OpenCLIP
    model, preprocess, tokenizer, device, torch, np = setup_openclip_fashionsig()
    if not model:
        return

    # Setup Qdrant
    qdrant_client, _, _ = setup_qdrant()

    # Process products
    results = await process_products_openclip(
        products, model, preprocess, tokenizer, device, torch, np, qdrant_client
    )

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"openclip_fashionsig_{args.limit}_{timestamp}.json"

    total_embeddings = sum(r.get("embeddings_created", 0) for r in results)
    successful_products = len([r for r in results if r.get("status") == "success"])

    summary = {
        "timestamp": timestamp,
        "model_used": "openclip_fashionsig",
        "total_products": len(products),
        "successful_products": successful_products,
        "total_embeddings": total_embeddings,
        "approach": "openclip_direct",
        "results": results
    }

    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Directory Results saved to: {output_file}")
    logger.info(f"Stats Summary: {successful_products}/{len(products)} products, {total_embeddings} embeddings")

    neo4j_driver.close()
    logger.info("Complete OpenCLIP FashionSigLIP precomputation completed!")

if __name__ == "__main__":
    asyncio.run(main())