#!/usr/bin/env python3
"""
FashionSigLIP Vision Embedding Precomputation - Clean Environment Version
Use this in a separate environment with only the required dependencies
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
logger = logging.getLogger("fashionsig_precomputation")

# Required dependencies for separate environment:
"""
pip install torch torchvision transformers pillow requests python-dotenv
pip install qdrant-client
pip install neo4j
pip install numpy
"""

def load_environment():
    """Load environment variables"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Environment loaded")
    except ImportError:
        logger.warning("python-dotenv not available, using OS environment")

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

        logger.info("Neo4j connection successful")
        return driver

    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
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
            logger.info(f"Fetched {len(products)} products")
            return products
    except Exception as e:
        logger.error(f"Failed to fetch products: {e}")
        return []

def setup_fashionsig():
    """Initialize FashionSigLIP model"""
    try:
        import torch
        from transformers import AutoProcessor, AutoModel
        from PIL import Image
        import numpy as np

        logger.info("Loading FashionSigLIP dependencies...")

        # Use local model path instead of HuggingFace name
        local_model_path = "/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/marqo-fashionSigLIP"
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        logger.info(f"Loading FashionSigLIP from local path: {local_model_path}")
        logger.info(f"Device: {device}")

        # Load processor from local files
        processor = AutoProcessor.from_pretrained(
            local_model_path,
            trust_remote_code=True,
            local_files_only=True
        )
        logger.info("Processor loaded")

        # Load model from local files
        logger.info("Loading model from local files...")
        model = AutoModel.from_pretrained(
            local_model_path,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            device_map=None,
            low_cpu_mem_usage=False,  # This prevents meta tensor creation
            local_files_only=True  # Use local files only
        )

        logger.info("Moving model to device...")
        model = model.to(device)
        model.eval()
        logger.info("Model loaded successfully")

        return processor, model, device, torch, np

    except Exception as e:
        logger.error(f"FashionSigLIP setup failed: {e}")
        return None, None, None, None, None

def setup_qdrant():
    """Initialize Qdrant client"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        client = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY"),
            prefer_grpc=False  # Force HTTP-only
        )

        # Test connection
        collections = client.get_collections().collections
        logger.info(f"Qdrant connected ({len(collections)} collections)")

        return client, VectorParams, Distance

    except Exception as e:
        logger.error(f"Qdrant setup failed: {e}")
        return None, None, None

def create_fashionsig_collection(client, VectorParams, Distance, embedding_dim, collection_name=None):
    """Create or verify FashionSigLIP collection"""
    if collection_name is None:
        collection_name = "fashion_multimodal_embeddings"

    try:
        collections = client.get_collections().collections
        collection_exists = any(c.name == collection_name for c in collections)

        if not collection_exists:
            logger.info(f"Creating FashionSigLIP collection: {collection_name}")
            client.create_collection(
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
            logger.info("FashionSigLIP collection created")
        else:
            # Check if existing collection has compatible dimensions
            try:
                collection_info = client.get_collection(collection_name)
                logger.info(f"Collection '{collection_name}' already exists")
                logger.info(f"   Will overwrite with FashionSigLIP embeddings")
            except Exception as check_error:
                logger.warning(f"Could not verify collection: {check_error}")
                # If there are issues, create with a safe name
                collection_name = f"fashion_multimodal_embeddings_fashionsig_{embedding_dim}d"
                logger.info(f"Creating safe collection: {collection_name}")
                client.create_collection(
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

        return collection_name

    except Exception as e:
        logger.error(f"Collection setup failed: {e}")
        return None

async def process_products_fashionsig(products, processor, model, device, torch, np, qdrant_client, collection_name):
    """Process products with FashionSigLIP"""
    results = []

    for i, product in enumerate(products, 1):
        logger.info(f"Processing product {i}/{len(products)}: {product['title'][:50]}...")

        try:
            # Prepare text
            text_content = []
            for field in ['title', 'description']:
                if product.get(field):
                    text_content.append(str(product[field]))

            full_text = " ".join(filter(None, text_content))
            # Truncate for token limits
            text_words = full_text.split()[:40]
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

            for j, img_path in enumerate(images_data[:3]):  # Max 3 images
                try:
                    # Format URL
                    if not img_path.startswith(('http://', 'https://')):
                        img_url = f"https://app.shopari.com/images/{img_path}"
                    else:
                        img_url = img_path

                    logger.info(f"   Downloading image {j+1}: {img_url}")

                    # Download image
                    response = requests.get(img_url, timeout=10)
                    response.raise_for_status()

                    # Process image
                    from io import BytesIO
                    from PIL import Image

                    img = Image.open(BytesIO(response.content)).convert('RGB')
                    logger.info(f"   Image loaded: {img.size}")

                    # Generate FashionSigLIP embeddings
                    try:
                        # Process both image and text together
                        inputs = processor(
                            text=[text],
                            images=[img],
                            return_tensors="pt",
                            padding=True,
                            truncation=True,
                            max_length=64  # SigLIP uses 64, not 77
                        )
                        # Remove attention_mask for MarqoFashionSigLIP compatibility
                        if 'attention_mask' in inputs:
                            del inputs['attention_mask']
                        inputs = {k: v.to(device) for k, v in inputs.items()}

                        with torch.no_grad():
                            outputs = model(**inputs)
                            # Handle MarqoFashionSigLIP output format
                            if isinstance(outputs, tuple) and len(outputs) == 4:
                                # FashionSigLIP returns (similarity1, similarity2, image_embeds, text_embeds)
                                image_embedding = outputs[2].cpu().numpy().flatten()  # Image embeddings (3rd tensor)
                                text_embedding = outputs[3].cpu().numpy().flatten()   # Text embeddings (4th tensor)
                            elif isinstance(outputs, tuple):
                                image_embedding = outputs[0].cpu().numpy().flatten()  # Fallback
                                text_embedding = outputs[1].cpu().numpy().flatten()   # Fallback
                            else:
                                image_embedding = outputs.image_embeds.cpu().numpy().flatten()
                                text_embedding = outputs.text_embeds.cpu().numpy().flatten()

                        # Create combined embedding
                        combined_embedding = np.concatenate([image_embedding, text_embedding])

                        logger.info(f"   FashionSigLIP embeddings created:")
                        logger.info(f"      Image: {len(image_embedding)} dims, {np.count_nonzero(image_embedding)} non-zero")
                        logger.info(f"      Text:  {len(text_embedding)} dims, {np.count_nonzero(text_embedding)} non-zero")
                        logger.info(f"      Combined: {len(combined_embedding)} dims")

                        # Upload to Qdrant if available
                        qdrant_uploaded = False
                        qdrant_point_id = None
                        qdrant_error = None

                        if qdrant_client and collection_name:
                            try:
                                from qdrant_client.models import PointStruct

                                # Create unique UUID
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
                                        "model_used": "fashionsig",
                                        "embedding_dims": {
                                            "image": len(image_embedding),
                                            "text": len(text_embedding),
                                            "combined": len(combined_embedding)
                                        },
                                        "timestamp": datetime.now().isoformat(),
                                        "approach": "fashionsig_multimodal"
                                    }
                                )

                                result = qdrant_client.upsert(
                                    collection_name=collection_name,
                                    points=[point]
                                )

                                logger.info(f"   Uploaded to Qdrant: {point_id}")
                                qdrant_uploaded = True
                                qdrant_point_id = point_id

                            except Exception as upload_error:
                                logger.error(f"   Qdrant upload failed: {upload_error}")
                                qdrant_error = str(upload_error)

                        embedding_result = {
                            "product_id": product['id'],
                            "image_index": j,
                            "image_url": img_url,
                            "image_size": img.size,
                            "text_content": text[:200],
                            "image_embedding_dim": len(image_embedding),
                            "text_embedding_dim": len(text_embedding),
                            "combined_embedding_dim": len(combined_embedding),
                            "non_zero_image": int(np.count_nonzero(image_embedding)),
                            "non_zero_text": int(np.count_nonzero(text_embedding)),
                            "qdrant_uploaded": qdrant_uploaded,
                            "qdrant_point_id": qdrant_point_id,
                            "qdrant_error": qdrant_error,
                            "timestamp": datetime.now().isoformat(),
                            "model_used": "Marqo/marqo-fashionSigLIP"
                        }

                        embeddings_created.append(embedding_result)

                    except Exception as model_error:
                        logger.error(f"   FashionSigLIP processing failed: {model_error}")
                        continue

                except Exception as e:
                    logger.error(f"   Image {j+1} processing failed: {e}")
                    continue

            # Store product result
            product_result = {
                "product_id": product['id'],
                "title": product['title'],
                "embeddings_created": len(embeddings_created),
                "embeddings": embeddings_created,
                "status": "success" if embeddings_created else "no_embeddings"
            }

            results.append(product_result)
            logger.info(f"   Product processed: {len(embeddings_created)} FashionSigLIP embeddings created")

        except Exception as e:
            logger.error(f"   Product processing failed: {e}")
            results.append({
                "product_id": product['id'],
                "title": product['title'],
                "status": "error",
                "error": str(e)
            })

    return results

async def main():
    """Main execution function"""
    # Workaround for TensorFlow conflicts
    import sys
    if 'tensorflow' in sys.modules:
        del sys.modules['tensorflow']

    import argparse

    parser = argparse.ArgumentParser(description='FashionSigLIP vision embedding precomputation')
    parser.add_argument('--limit', type=int, default=10000000, help='Number of products to process (default: all)')
    args = parser.parse_args()

    logger.info(f"Starting Starting FashionSigLIP precomputation (limit: {args.limit})")

    # Load environment
    load_environment()

    # Setup connections
    neo4j_driver = await test_neo4j_connection()
    if not neo4j_driver:
        logger.error("Error Cannot proceed without Neo4j")
        return

    # Fetch products
    products = await fetch_products(neo4j_driver, args.limit)
    if not products:
        logger.error("Error No products to process")
        return

    # Setup FashionSigLIP
    processor, model, device, torch, np = setup_fashionsig()
    if not model:
        logger.error("Error Cannot proceed without FashionSigLIP model")
        return

    # Setup Qdrant
    qdrant_client, VectorParams, Distance = setup_qdrant()
    collection_name = None

    if qdrant_client:
        # Determine embedding dimension
        from PIL import Image
        with torch.no_grad():
            dummy_inputs = processor(
                text=["test"],
                images=[Image.new('RGB', (224, 224))],
                return_tensors="pt"
            )
            # Remove attention_mask for MarqoFashionSigLIP compatibility
            if 'attention_mask' in dummy_inputs:
                del dummy_inputs['attention_mask']
            dummy_inputs = {k: v.to(device) for k, v in dummy_inputs.items()}
            dummy_outputs = model(**dummy_inputs)
            # Debug what the model returns
            logger.info(f"Model output type: {type(dummy_outputs)}")
            if isinstance(dummy_outputs, tuple):
                logger.info(f"Tuple length: {len(dummy_outputs)}")
                logger.info(f"Tensor shapes: {[x.shape if hasattr(x, 'shape') else type(x) for x in dummy_outputs]}")
                # FashionSigLIP returns (similarity1, similarity2, image_embeds, text_embeds)
                if len(dummy_outputs) == 4:
                    # Take the 768-dimensional embeddings (3rd and 4th tensors)
                    image_embeds = dummy_outputs[2]  # Image embeddings
                    text_embeds = dummy_outputs[3]   # Text embeddings
                else:
                    # Fallback: find largest embedding tensor
                    embedding_tensors = [x for x in dummy_outputs if hasattr(x, 'shape') and x.shape[-1] > 10]
                    image_embeds = embedding_tensors[0] if embedding_tensors else dummy_outputs[0]
            else:
                logger.info(f"Output attributes: {dir(dummy_outputs)}")
                image_embeds = dummy_outputs.image_embeds
            embedding_dim = image_embeds.shape[-1]

        logger.info(f"Search FashionSigLIP embedding dimension: {embedding_dim}")
        collection_name = f"fashion_fashionsig_{embedding_dim}d"
        collection_name = create_fashionsig_collection(qdrant_client, VectorParams, Distance, embedding_dim, collection_name)
    else:
        logger.warning("Warning  Continuing without Qdrant (embeddings will be saved to file only)")

    # Process products
    results = await process_products_fashionsig(
        products, processor, model, device, torch, np,
        qdrant_client, collection_name
    )

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"fashionsig_embeddings_{args.limit}_{timestamp}.json"

    # Calculate statistics
    total_uploaded = sum(
        len([e for e in r.get("embeddings", []) if e.get("qdrant_uploaded", False)])
        for r in results if r.get("status") == "success"
    )

    total_embeddings = sum(r.get("embeddings_created", 0) for r in results)
    successful_products = len([r for r in results if r.get("status") == "success"])

    summary = {
        "timestamp": timestamp,
        "model_used": "Marqo/marqo-fashionSigLIP",
        "total_products": len(products),
        "successful_products": successful_products,
        "total_embeddings": total_embeddings,
        "qdrant_uploaded": total_uploaded,
        "upload_success_rate": f"{total_uploaded/total_embeddings*100:.1f}%" if total_embeddings > 0 else "N/A",
        "qdrant_collection": collection_name or "N/A",
        "approach": "fashionsig_multimodal",
        "results": results
    }

    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)

    # Final summary
    logger.info(f"Directory Results saved to: {output_file}")
    logger.info(f"Stats Final Summary:")
    logger.info(f"   Model: {summary['model_used']}")
    logger.info(f"   Products: {summary['successful_products']}/{summary['total_products']}")
    logger.info(f"   Embeddings: {summary['total_embeddings']}")
    logger.info(f"   Starting Qdrant uploads: {summary['qdrant_uploaded']}")
    logger.info(f"   Growth Upload rate: {summary['upload_success_rate']}")
    logger.info(f"   📚 Collection: {summary['qdrant_collection']}")

    # Close Neo4j
    neo4j_driver.close()
    logger.info("Complete FashionSigLIP precomputation completed!")

if __name__ == "__main__":
    asyncio.run(main())