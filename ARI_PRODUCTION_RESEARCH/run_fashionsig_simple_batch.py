#!/usr/bin/env python3
"""
Simplified FashionSigLIP Batch Processing
Processes products with existing URL formats (tradeinn, shopify, etc.)
"""

import os
import sys
import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fashionsig_simple_batch")

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def test_product_urls():
    """Test what types of URLs we have in the database and their accessibility"""
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URL", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USERNAME", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "")
            )
        )

        logger.info("Testing product URL accessibility...")

        with driver.session() as session:
            # Get products with accessible URLs
            limit = int(os.getenv('TOTAL_PRODUCTS', '1000'))  # Default 1000, configurable
            result = session.run(f"""
                MATCH (p:Product)
                WHERE p.images IS NOT NULL
                RETURN p.id, p.title, p.images
                LIMIT {limit}
            """)

            successful_urls = []
            failed_urls = []

            async with __import__('aiohttp').ClientSession() as http_session:
                for record in result:
                    product_id = record['p.id']
                    title = record['p.title']
                    images_data = record['p.images']

                    if isinstance(images_data, str):
                        try:
                            images_data = json.loads(images_data)
                        except:
                            images_data = [images_data]

                    for img_url in images_data[:1]:  # Test first image only
                        try:
                            async with http_session.head(img_url, timeout=10) as response:
                                if response.status == 200:
                                    content_type = response.headers.get('content-type', '')
                                    if 'image/' in content_type:
                                        successful_urls.append({
                                            'product_id': product_id,
                                            'title': title[:50] + '...' if len(title) > 50 else title,
                                            'url': img_url,
                                            'content_type': content_type
                                        })
                                        logger.info(f"OK {img_url[:80]}... -> {content_type}")
                                    else:
                                        failed_urls.append({
                                            'product_id': product_id,
                                            'url': img_url,
                                            'reason': f'Not image: {content_type}'
                                        })
                                        logger.warning(f"FAILED {img_url[:80]}... -> {content_type} (not image)")
                                else:
                                    failed_urls.append({
                                        'product_id': product_id,
                                        'url': img_url,
                                        'reason': f'HTTP {response.status}'
                                    })
                                    logger.warning(f"FAILED {img_url[:80]}... -> HTTP {response.status}")
                        except Exception as e:
                            failed_urls.append({
                                'product_id': product_id,
                                'url': img_url,
                                'reason': str(e)
                            })
                            logger.warning(f"FAILED {img_url[:80]}... -> {e}")

                        # Small delay to be nice to servers
                        await asyncio.sleep(0.1)

            # Summary
            logger.info(f"URL Test Results:")
            logger.info(f"   Successful: {len(successful_urls)}")
            logger.info(f"   Failed: {len(failed_urls)}")

            if successful_urls:
                logger.info("Sample working URLs:")
                for url_info in successful_urls[:5]:
                    logger.info(f"   {url_info['product_id']}: {url_info['url'][:60]}...")

            return successful_urls, failed_urls

    except Exception as e:
        logger.error(f"URL test failed: {e}")
        return [], []

async def process_batch_with_accessible_urls():
    """Process a batch using only URLs that are actually accessible"""
    logger.info("Starting simple batch processing with accessible URLs...")

    # First test URLs to find what works
    successful_urls, failed_urls = await test_product_urls()

    if not successful_urls:
        logger.error("No accessible URLs found. Cannot proceed with batch processing.")
        return False

    logger.info(f"Found {len(successful_urls)} accessible URLs. Processing first batch...")

    # Use the working single-product script approach for now
    # This gives us a working baseline before scaling up
    try:
        sys.path.append('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

        # Import the working functionality from single product script
        from run_fashionsig_precomputation import (
            setup_fashionsig,
            setup_qdrant,
            process_products_fashionsig
        )

        # Load model and setup
        processor, model, device, torch, np = setup_fashionsig()
        if model is None:
            logger.error("Failed to load FashionSigLIP model")
            return False

        # Setup Qdrant
        qdrant_client, VectorParams, Distance = setup_qdrant()
        if qdrant_client is None:
            logger.error("Failed to setup Qdrant client")
            return False

        # Use the standard collection name
        collection_name = "fashion_fashionsig_768d"

        # Convert URL info to product format expected by the function
        batch_size = int(os.getenv('BATCH_SIZE', '512'))  # Default 512, configurable via env
        products_to_process = []
        for url_info in successful_urls[:batch_size]:  # Use configurable batch size
            product = {
                'id': url_info['product_id'],
                'title': url_info['title'],
                'description': '',  # No description available
                'images': [url_info['url']]  # Single image URL
            }
            products_to_process.append(product)

        logger.info(f"Processing batch of {len(products_to_process)} products...")

        # Use the original processing function
        results = await process_products_fashionsig(
            products=products_to_process,
            processor=processor,
            model=model,
            device=device,
            torch=torch,
            np=np,
            qdrant_client=qdrant_client,
            collection_name=collection_name
        )

        batch_results = [r for r in results if r.get('status') == 'success']
        logger.info(f"Batch Results: {len(batch_results)} successful out of {len(products_to_process)} attempted")

        return len(batch_results) > 0

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main function"""
    logger.info("Starting simplified FashionSigLIP batch processing")

    success = await process_batch_with_accessible_urls()

    if success:
        logger.info("Simple batch processing completed successfully!")
        logger.info("Next step: Scale up to larger batches with working URL formats")
    else:
        logger.error("Batch processing failed")

    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)