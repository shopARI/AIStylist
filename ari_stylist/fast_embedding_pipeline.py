#!/usr/bin/env python3
"""
Optimized Fashion Product Embeddings Pipeline
Keeps all product information and relationships except neighborhood traversals
Focuses on performance while maintaining embedding quality
"""

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from tqdm import tqdm
import openai
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, 
    OptimizersConfigDiff
)
from dotenv import load_dotenv
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import tiktoken
import time
import uuid

load_dotenv()

# Logging setup
log_dir = Path('./embeddings_pipeline/logs')
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f'embeddings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'neo4j': {
        'url': os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
        'username': os.getenv('NEO4J_USERNAME', 'neo4j'),
        'password': os.getenv('NEO4J_PASSWORD', 'shopari1234'),
        'max_connection_lifetime': 3600,
        'max_connection_pool_size': 50,
        'connection_acquisition_timeout': 60
    },
    'openai': {
        'api_key': os.getenv('OPENAI_API_KEY'),
        'embedding_model': 'text-embedding-3-small',
        'embedding_dimensions': 1536,
        'max_tokens': 8191,
        'batch_size': 100,  # OpenAI allows up to 100 texts per request
        'cost_per_1m_tokens': 0.020,
        'max_retries': 3,
        'retry_delay': 1
    },
    'qdrant': {
        'url': os.getenv('QDRANT_URL', 'https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io'),
        'api_key': os.getenv('QDRANT_API_KEY'),
        'collection': 'fashion_products',
        'batch_size': 100,
        'timeout': 60
    },
    'pipeline': {
        'neo4j_batch_size': 1000,  # Increased from 500
        'checkpoint_interval': 5000,  # Increased from 1000
        'output_dir': './embeddings_pipeline',
        'resume_enabled': True,
        'dry_run': False,
        'skip_neighborhood': True,  # Skip expensive neighborhood queries
        'parallel_workers': 1  # Can increase for parallel processing
    }
}

@dataclass
class ProductContext:
    """Complete product context from Neo4j"""
    # Core product data
    id: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    visited_num: Optional[int] = 0
    active: Optional[bool] = True
    inventory: Optional[int] = None
    
    # Classification data
    is_fashion: bool = True
    fashion_confidence: Optional[float] = None
    fashion_category: Optional[str] = None
    classification_reasoning: Optional[str] = None
    
    # Enriched attributes (if available)
    product_type: Optional[str] = None
    primary_color: Optional[str] = None
    color_list: Optional[List[str]] = field(default_factory=list)
    price_tier: Optional[str] = None
    formality_level: Optional[int] = None
    season_tags: Optional[List[str]] = field(default_factory=list)
    
    # Graph relationships
    categories: List[Dict[str, Any]] = field(default_factory=list)
    brand: Optional[Dict[str, Any]] = None
    collections: List[str] = field(default_factory=list)
    price_range: Optional[str] = None
    status: Optional[str] = None
    
    # Embedding data
    embedding_text: Optional[str] = None
    embedding_tokens: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OptimizedFashionEmbeddingsPipeline:
    """Optimized pipeline for creating fashion product embeddings"""
    
    def __init__(self):
        logger.info("Initializing Optimized Fashion Embeddings Pipeline")
        
        # Initialize clients with optimized settings
        self.openai_client = openai.OpenAI(api_key=CONFIG['openai']['api_key'])
        
        # Neo4j with connection pooling
        self.neo4j_driver = GraphDatabase.driver(
            CONFIG['neo4j']['url'],
            auth=(CONFIG['neo4j']['username'], CONFIG['neo4j']['password']),
            max_connection_lifetime=CONFIG['neo4j']['max_connection_lifetime'],
            max_connection_pool_size=CONFIG['neo4j']['max_connection_pool_size'],
            connection_acquisition_timeout=CONFIG['neo4j']['connection_acquisition_timeout']
        )
        
        self.qdrant = QdrantClient(
            url=CONFIG['qdrant']['url'],
            api_key=CONFIG['qdrant']['api_key'],
            timeout=CONFIG['qdrant']['timeout']
        )
        
        # Tokenizer for counting
        self.tokenizer = tiktoken.encoding_for_model(CONFIG['openai']['embedding_model'])
        
        # State management
        self.base_dir = Path(CONFIG['pipeline']['output_dir'])
        self.state_file = self.base_dir / 'embedding_pipeline_state.json'
        self.checkpoints_dir = self.base_dir / 'checkpoints'
        self.reports_dir = self.base_dir / 'reports'
        
        for dir in [self.base_dir, self.checkpoints_dir, self.reports_dir]:
            dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize state
        self.state = self._load_state()
        self.processed_products = set(self.state.get('processed_products', []))
        
        # Statistics
        self.stats = defaultdict(int)
        self.cost_tracker = {
            'tokens_used': 0,
            'embeddings_created': 0,
            'estimated_cost': 0.0
        }
        
        # Performance tracking
        self.batch_times = []
        self.start_time = None
    
    def _load_state(self) -> Dict[str, Any]:
        """Load pipeline state for resume capability"""
        if self.state_file.exists() and CONFIG['pipeline']['resume_enabled']:
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    logger.info(f"Resumed from previous state: {len(state.get('processed_products', [])):,} products processed")
                    return state
            except Exception as e:
                logger.warning(f"Could not load state: {e}")
        
        return {
            'run_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'status': 'initialized',
            'processed_products': [],
            'total_products': 0,
            'embedded_products': 0,
            'failed_products': [],
            'start_time': datetime.now().isoformat()
        }
    
    def _save_state(self):
        """Save pipeline state"""
        self.state['processed_products'] = list(self.processed_products)
        self.state['embedded_products'] = len(self.processed_products)
        self.state['last_updated'] = datetime.now().isoformat()
        
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    async def run(self):
        """Main pipeline execution"""
        logger.info("="*60)
        logger.info("Starting Optimized Fashion Embeddings Pipeline")
        logger.info(f"Run ID: {self.state['run_id']}")
        logger.info(f"Embedding Model: {CONFIG['openai']['embedding_model']}")
        logger.info(f"Dimensions: {CONFIG['openai']['embedding_dimensions']}")
        logger.info(f"Neo4j Batch Size: {CONFIG['pipeline']['neo4j_batch_size']}")
        logger.info(f"Skip Neighborhood: {CONFIG['pipeline']['skip_neighborhood']}")
        logger.info("="*60)
        
        self.start_time = time.time()
        
        try:
            # Phase 1: Setup and validation
            await self._setup_qdrant_collection()
            product_count = await self._validate_and_count()
            
            if product_count == 0:
                logger.info("No products to embed!")
                return
            
            # Estimate costs
            est_cost = self._estimate_total_cost(product_count)
            logger.info(f"Estimated API cost: ${est_cost:.2f}")
            
            if CONFIG['pipeline']['dry_run']:
                logger.info("DRY RUN mode - no API calls will be made")
            
            # Phase 2: Process products in batches
            await self._process_all_products(product_count)
            
            # Phase 3: Verify and report
            await self._verify_embeddings()
            self._generate_report()
            
            logger.info("\n✅ Embedding pipeline completed successfully!")
            
        except KeyboardInterrupt:
            logger.warning("\nPipeline interrupted by user")
            self._save_state()
            self._generate_report()
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            self._save_state()
            raise
        finally:
            self.neo4j_driver.close()
    
    async def _setup_qdrant_collection(self):
        """Setup or verify Qdrant collection"""
        try:
            collections = self.qdrant.get_collections()
            exists = any(c.name == CONFIG['qdrant']['collection'] for c in collections.collections)
            
            if not exists:
                self.qdrant.create_collection(
                    collection_name=CONFIG['qdrant']['collection'],
                    vectors_config=VectorParams(
                        size=CONFIG['openai']['embedding_dimensions'],
                        distance=Distance.COSINE
                    ),
                    optimizers_config=OptimizersConfigDiff(
                        indexing_threshold=20000,
                        default_segment_number=4
                    )
                )
                logger.info(f"Created Qdrant collection: {CONFIG['qdrant']['collection']}")
            else:
                count = self.qdrant.count(collection_name=CONFIG['qdrant']['collection'])
                logger.info(f"Using existing collection: {CONFIG['qdrant']['collection']} (current vectors: {count.count:,})")
                
        except Exception as e:
            logger.error(f"Qdrant setup failed: {e}")
            raise
    
    async def _validate_and_count(self) -> int:
        """Validate and count products ready for embedding"""
        with self.neo4j_driver.session() as session:
            # Count products - FIXED SYNTAX
            result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.ready_for_embedding = true
                  AND p.embedding_id IS NULL
                  AND p.duplicate_of IS NULL
                RETURN count(p) as count
            """).single()
            
            total_to_embed = result['count']
            
            # Subtract already processed
            need_embedding = total_to_embed - len(self.processed_products)
            
            logger.info(f"Products ready for embedding: {total_to_embed:,}")
            logger.info(f"Already processed this run: {len(self.processed_products):,}")
            logger.info(f"Need embedding: {need_embedding:,}")
            
            self.state['total_products'] = need_embedding
            
            return need_embedding
    
    def _estimate_total_cost(self, product_count: int) -> float:
        """Estimate total API cost"""
        avg_tokens_per_product = 400  # Conservative estimate
        total_tokens = product_count * avg_tokens_per_product
        cost = (total_tokens / 1_000_000) * CONFIG['openai']['cost_per_1m_tokens']
        return cost
    
    async def _process_all_products(self, total_count: int):
        """Process all products in batches"""
        processed = 0
        
        with tqdm(total=total_count, desc="Creating embeddings") as pbar:
            while processed < total_count:
                batch_start_time = time.time()
                
                # Get batch of products with context
                products = await self._get_product_batch_optimized(
                    skip=processed,
                    limit=CONFIG['pipeline']['neo4j_batch_size']
                )
                
                if not products:
                    break
                
                # Filter out already processed
                new_products = [p for p in products if p.id not in self.processed_products]
                
                if not new_products:
                    processed += len(products)
                    continue
                
                # Create embedding texts
                for product in new_products:
                    product.embedding_text = self._create_embedding_text(product)
                    product.embedding_tokens = len(self.tokenizer.encode(product.embedding_text))
                
                # Process in OpenAI batches
                await self._embed_products_batch(new_products)
                
                processed += len(products)
                pbar.update(len(new_products))
                
                # Performance tracking
                batch_time = time.time() - batch_start_time
                self.batch_times.append(batch_time)
                products_per_second = len(new_products) / batch_time
                
                # Log performance every 10 batches
                if len(self.batch_times) % 10 == 0:
                    avg_rate = processed / (time.time() - self.start_time)
                    eta_hours = (total_count - processed) / avg_rate / 3600
                    logger.info(f"Rate: {products_per_second:.1f} p/s (avg: {avg_rate:.1f} p/s), ETA: {eta_hours:.1f} hours")
                
                # Save checkpoint
                if len(self.processed_products) % CONFIG['pipeline']['checkpoint_interval'] == 0:
                    self._save_checkpoint()
    
    async def _get_product_batch_optimized(self, skip: int, limit: int) -> List[ProductContext]:
        """Get batch of products with optimized queries"""
        products = []
        
        with self.neo4j_driver.session() as session:
            # Optimized query - single pass with all direct relationships
            # NO neighborhood traversals (siblings, brand family)
            # FIXED SYNTAX
            result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.ready_for_embedding = true
                  AND p.embedding_id IS NULL
                  AND p.duplicate_of IS NULL
                WITH p
                ORDER BY p.visited_num DESC
                SKIP $skip LIMIT $limit
                
                // Get all direct relationships in one go
                OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
                OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                OPTIONAL MATCH (p)-[:IN_COLLECTION]->(col:Collection)
                OPTIONAL MATCH (p)-[:IN_PRICE_RANGE]->(pr:PriceRange)
                OPTIONAL MATCH (p)-[:HAS_STATUS]->(s:Status)
                
                RETURN p,
                       collect(DISTINCT c) as categories,
                       b as brand,
                       collect(DISTINCT col.name) as collections,
                       pr.name as price_range,
                       s.name as status
                ORDER BY p.visited_num DESC
            """, skip=skip, limit=limit)
            
            for record in result:
                # Skip if already processed
                if record['p']['id'] in self.processed_products:
                    continue
                
                product_data = dict(record['p'])
                
                # Create product context with all available data
                context = ProductContext(
                    # Core fields
                    id=product_data['id'],
                    title=product_data.get('title', ''),
                    description=product_data.get('description'),
                    price=product_data.get('price'),
                    visited_num=product_data.get('visited_num', 0),
                    active=product_data.get('active', True),
                    inventory=product_data.get('inventory'),
                    
                    # Classification data
                    is_fashion=product_data.get('is_fashion', True),
                    fashion_confidence=product_data.get('fashion_confidence'),
                    fashion_category=product_data.get('fashion_category'),
                    classification_reasoning=product_data.get('classification_reasoning'),
                    
                    # Enriched attributes (if they exist)
                    product_type=product_data.get('product_type'),
                    primary_color=product_data.get('primary_color'),
                    color_list=product_data.get('color_list', []),
                    price_tier=product_data.get('price_tier'),
                    formality_level=product_data.get('formality_level'),
                    season_tags=product_data.get('season_tags', []),
                    
                    # Graph relationships
                    categories=[dict(c) for c in record['categories']] if record['categories'] else [],
                    brand=dict(record['brand']) if record['brand'] else None,
                    collections=record['collections'] or [],
                    price_range=record['price_range'],
                    status=record['status']
                )
                
                products.append(context)
        
        return products
    
    def _create_embedding_text(self, context: ProductContext) -> str:
        """Create rich embedding text from product context"""
        parts = []
        
        # 1. Product Identity Section
        identity_parts = [f"[PRODUCT] {context.title}"]
        
        # Add enriched type if available
        if context.product_type:
            identity_parts.append(f"Type: {context.product_type}")
        elif context.categories:
            # Fallback to category
            cat_names = [c.get('name', '') for c in context.categories]
            identity_parts.append(f"Category: {', '.join(cat_names)}")
        
        # Add brand - VERY IMPORTANT
        if context.brand:
            identity_parts.append(f"Brand: {context.brand.get('name', '')}")
        
        # Add price
        if context.price:
            identity_parts.append(f"Price: ${context.price:.2f}")
            if context.price_tier:
                identity_parts.append(f"Tier: {context.price_tier}")
        
        parts.append(" | ".join(identity_parts))
        
        # 2. Description Section - FULL DESCRIPTION
        if context.description:
            parts.append(f"\n[DESCRIPTION] {context.description}")
        
        # 3. Attributes Section (if enriched)
        attributes = []
        
        if context.primary_color or context.color_list:
            colors = context.color_list if context.color_list else ([context.primary_color] if context.primary_color else [])
            if colors:
                attributes.append(f"Colors: {', '.join(colors)}")
        
        if context.formality_level:
            formality_map = {1: "casual", 2: "smart casual", 3: "business", 4: "formal", 5: "black tie"}
            attributes.append(f"Formality: {formality_map.get(context.formality_level, f'level {context.formality_level}')}")
        
        if context.season_tags:
            attributes.append(f"Seasons: {', '.join(context.season_tags)}")
        
        if attributes:
            parts.append(f"\n[ATTRIBUTES] {' | '.join(attributes)}")
        
        # 4. Graph Context Section
        graph_parts = []
        
        # Categories (all of them)
        if context.categories:
            cat_names = [c.get('name', '') for c in context.categories]
            if cat_names:
                graph_parts.append(f"Categories: {', '.join(cat_names)}")
        
        # Collections
        if context.collections:
            graph_parts.append(f"Collections: {', '.join(context.collections)}")
        
        # Price range
        if context.price_range:
            graph_parts.append(f"Price Range: {context.price_range}")
        
        # Status
        if context.status:
            graph_parts.append(f"Status: {context.status}")
        
        if graph_parts:
            parts.append(f"\n[GRAPH CONTEXT]\n" + "\n".join(graph_parts))
        
        # 5. Signals Section
        signals = []
        
        # Popularity signal
        if context.visited_num and context.visited_num > 100:
            if context.visited_num > 1000:
                signals.append("High demand item")
            else:
                signals.append("Popular item")
        
        # Inventory signal
        if context.inventory is not None:
            if context.inventory == 0:
                signals.append("Currently out of stock")
            elif context.inventory < 10:
                signals.append("Limited availability")
        
        # Fashion confidence
        if context.fashion_confidence and context.fashion_confidence > 0.9:
            signals.append("Highly fashion-relevant")
        
        if signals:
            parts.append(f"\n[SIGNALS] {', '.join(signals)}")
        
        # Combine all parts
        embedding_text = "\n".join(parts)
        
        # Ensure we don't exceed token limits
        if len(self.tokenizer.encode(embedding_text)) > CONFIG['openai']['max_tokens'] - 100:
            embedding_text = self._truncate_to_token_limit(embedding_text, CONFIG['openai']['max_tokens'] - 100)
        
        return embedding_text
    
    def _truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit"""
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        # Truncate and decode
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)
    
    async def _embed_products_batch(self, products: List[ProductContext]):
        """Create embeddings for a batch of products"""
        # Split into OpenAI API batches
        for i in range(0, len(products), CONFIG['openai']['batch_size']):
            batch = products[i:i + CONFIG['openai']['batch_size']]
            
            # Extract texts and track tokens
            texts = [p.embedding_text for p in batch]
            total_tokens = sum(p.embedding_tokens for p in batch)
            
            self.cost_tracker['tokens_used'] += total_tokens
            
            if CONFIG['pipeline']['dry_run']:
                # In dry run, create fake embeddings
                embeddings = [[0.1] * CONFIG['openai']['embedding_dimensions'] for _ in batch]
            else:
                # Get embeddings from OpenAI
                embeddings = await self._get_embeddings_with_retry(texts)
            
            if embeddings:
                # Prepare Qdrant points
                points = []
                for product, embedding in zip(batch, embeddings):
                    # Create comprehensive metadata
                    metadata = {
                        'product_id': product.id,
                        'title': product.title,
                        'brand': product.brand.get('name') if product.brand else None,
                        'price': product.price,
                        'price_tier': product.price_tier,
                        'product_type': product.product_type,
                        'primary_color': product.primary_color,
                        'categories': [c.get('name') for c in product.categories] if product.categories else [],
                        'collections': product.collections,
                        'visited_num': product.visited_num,
                        'fashion_confidence': product.fashion_confidence,
                        'embedding_model': CONFIG['openai']['embedding_model'],
                        'embedding_date': datetime.now().isoformat(),
                        'token_count': product.embedding_tokens
                    }
                    
                    # Create Qdrant point
                    point = PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, product.id)),
                        vector=embedding,
                        payload=metadata
                    )
                    points.append(point)
                    
                    # Track as processed
                    self.processed_products.add(product.id)
                    self.stats['embeddings_created'] += 1
                
                # Upload to Qdrant
                if not CONFIG['pipeline']['dry_run']:
                    self.qdrant.upsert(
                        collection_name=CONFIG['qdrant']['collection'],
                        points=points
                    )
                
                # Update Neo4j with embedding IDs
                await self._update_neo4j_embedding_status(batch)
    
    async def _get_embeddings_with_retry(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Get embeddings with retry logic"""
        for attempt in range(CONFIG['openai']['max_retries']):
            try:
                response = self.openai_client.embeddings.create(
                    model=CONFIG['openai']['embedding_model'],
                    input=texts,
                    dimensions=CONFIG['openai']['embedding_dimensions']
                )
                
                embeddings = [item.embedding for item in response.data]
                return embeddings
                
            except Exception as e:
                logger.warning(f"Embedding attempt {attempt + 1} failed: {e}")
                if attempt < CONFIG['openai']['max_retries'] - 1:
                    await asyncio.sleep(CONFIG['openai']['retry_delay'] * (attempt + 1))
                else:
                    logger.error(f"Failed to create embeddings after {CONFIG['openai']['max_retries']} attempts")
                    return None
    
    async def _update_neo4j_embedding_status(self, products: List[ProductContext]):
        """Update Neo4j to mark products as embedded"""
        with self.neo4j_driver.session() as session:
            product_data = [
                {
                    'id': p.id,
                    'embedding_id': str(uuid.uuid5(uuid.NAMESPACE_DNS, p.id)),
                    'tokens': p.embedding_tokens
                }
                for p in products
            ]
            
            # Update in batches to avoid query size limits
            batch_size = 1000
            for i in range(0, len(product_data), batch_size):
                batch = product_data[i:i + batch_size]
                
                session.run("""
                    UNWIND $products as item
                    MATCH (p:Product {id: item.id})
                    SET p.embedding_id = item.embedding_id,
                        p.embedding_created_at = datetime(),
                        p.embedding_model = $model,
                        p.embedding_tokens = item.tokens
                """, products=batch, model=CONFIG['openai']['embedding_model'])
    
    def _save_checkpoint(self):
        """Save checkpoint for recovery"""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'processed_count': len(self.processed_products),
            'tokens_used': self.cost_tracker['tokens_used'],
            'embeddings_created': self.stats['embeddings_created'],
            'state': self.state,
            'performance_stats': {
                'avg_batch_time': np.mean(self.batch_times[-100:]) if self.batch_times else 0,
                'products_per_second': len(self.processed_products) / (time.time() - self.start_time) if self.start_time else 0
            }
        }
        
        checkpoint_file = self.checkpoints_dir / f'checkpoint_{len(self.processed_products)}.json'
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        # Also save main state
        self._save_state()
        
        logger.info(f"Checkpoint saved: {len(self.processed_products):,} products processed")
    
    async def _verify_embeddings(self):
        """Verify embeddings were created successfully"""
        logger.info("\nVerifying embeddings...")
        
        # Check Qdrant
        try:
            count_result = self.qdrant.count(collection_name=CONFIG['qdrant']['collection'])
            vectors_count = count_result.count
            logger.info(f"Vectors in Qdrant: {vectors_count:,}")
        except Exception as e:
            logger.warning(f"Could not get Qdrant count: {e}")
            vectors_count = 0
        
        # Check Neo4j
        with self.neo4j_driver.session() as session:
            result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.embedding_id IS NOT NULL
                RETURN count(p) as embedded_count,
                       min(p.embedding_created_at) as earliest,
                       max(p.embedding_created_at) as latest
            """).single()
            
            logger.info(f"Products with embedding_id in Neo4j: {result['embedded_count']:,}")
            if result['earliest']:
                logger.info(f"Earliest embedding: {result['earliest']}")
                logger.info(f"Latest embedding: {result['latest']}")
        
        # Sample search test
        if vectors_count > 0 and not CONFIG['pipeline']['dry_run']:
            try:
                test_results = self.qdrant.query_points(
                    collection_name=CONFIG['qdrant']['collection'],
                    query=[0.1] * CONFIG['openai']['embedding_dimensions'],
                    limit=3
                )
                
                result_count = len(test_results.points) if hasattr(test_results, 'points') else len(test_results)
                logger.info(f"✓ Search test successful - found {result_count} results")
            except Exception as e:
                logger.warning(f"Search test failed: {e}")
    
    def _generate_report(self):
        """Generate final report"""
        # Calculate final cost
        total_cost = (self.cost_tracker['tokens_used'] / 1_000_000) * CONFIG['openai']['cost_per_1m_tokens']
        self.cost_tracker['estimated_cost'] = total_cost
        
        # Calculate performance metrics
        total_time = time.time() - self.start_time if self.start_time else 0
        avg_rate = len(self.processed_products) / total_time if total_time > 0 else 0
        
        report = {
            'run_id': self.state['run_id'],
            'start_time': self.state['start_time'],
            'end_time': datetime.now().isoformat(),
            'products_processed': len(self.processed_products),
            'embeddings_created': self.stats['embeddings_created'],
            'tokens_used': self.cost_tracker['tokens_used'],
            'estimated_cost_usd': round(total_cost, 2),
            'average_tokens_per_product': self.cost_tracker['tokens_used'] / max(self.stats['embeddings_created'], 1),
            'model': CONFIG['openai']['embedding_model'],
            'dimensions': CONFIG['openai']['embedding_dimensions'],
            'performance': {
                'total_time_seconds': total_time,
                'average_products_per_second': avg_rate,
                'total_time_hours': total_time / 3600
            },
            'configuration': {
                'neo4j_batch_size': CONFIG['pipeline']['neo4j_batch_size'],
                'skip_neighborhood': CONFIG['pipeline']['skip_neighborhood']
            }
        }
        
        report_file = self.reports_dir / f'embedding_report_{self.state["run_id"]}.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("EMBEDDING PIPELINE REPORT")
        logger.info("="*60)
        logger.info(f"Products processed: {len(self.processed_products):,}")
        logger.info(f"Embeddings created: {self.stats['embeddings_created']:,}")
        logger.info(f"Total tokens used: {self.cost_tracker['tokens_used']:,}")
        logger.info(f"Estimated cost: ${total_cost:.2f}")
        logger.info(f"Average tokens/product: {report['average_tokens_per_product']:.0f}")
        logger.info(f"Processing rate: {avg_rate:.1f} products/second")
        logger.info(f"Total time: {total_time/3600:.1f} hours")
        logger.info(f"Report saved to: {report_file}")
        logger.info("="*60)


def main():
    """Main execution with optional start position"""
    import sys
    
    # Check for start position argument
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Usage: python optimized_fashion_embeddings_pipeline.py [start_position]")
        print("  start_position: Skip to specific position (for parallel processing)")
        sys.exit(0)
    
    pipeline = OptimizedFashionEmbeddingsPipeline()
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()