#!/usr/bin/env python3
"""
Resilient Fashion Product Embeddings Pipeline
Features:
- Automatic local backup on Qdrant failures
- Retry logic with exponential backoff
- Health monitoring and auto-recovery
- Rate limiting and batch size adaptation
- Comprehensive error handling
"""

import os
import json
import asyncio
import gzip
import pickle
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
from qdrant_client.http.exceptions import UnexpectedResponse
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

# Resilient Configuration
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
        'batch_size': 50,  # Reduced for resilience
        'cost_per_1m_tokens': 0.020,
        'max_retries': 3,
        'retry_delay': 1
    },
    'qdrant': {
        'url': os.getenv('QDRANT_URL', 'https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io'),
        'api_key': os.getenv('QDRANT_API_KEY'),
        'collection': os.getenv('QDRANT_COLLECTION', 'fashion_products'),
        'batch_size': 20,  # Small batches for resilience
        'timeout': 120,
        'max_retries': 5,
        'retry_delay': 30,
        'health_check_interval': 5000,  # Check health every 5k products
        'sub_batch_size': 5  # For fallback processing
    },
    'pipeline': {
        'neo4j_batch_size': 500,  # Reduced for stability
        'checkpoint_interval': 1000,  # Frequent checkpoints
        'output_dir': './embeddings_pipeline',
        'local_backup_dir': './embeddings_backup',
        'resume_enabled': True,
        'dry_run': False,
        'skip_neighborhood': True,
        'rate_limit_delay': 1,  # seconds between Qdrant operations
        'enable_local_backup': True,
        'adaptive_batch_size': True,  # Automatically reduce batch size on failures
        'min_batch_size': 1,
        'max_consecutive_failures': 10
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
    
    # Enriched attributes
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


class LocalEmbeddingStorage:
    """Store embeddings locally when Qdrant is unavailable"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.current_batch = []
        self.batch_size = 1000
        self.batch_count = self._get_existing_batch_count()
        
    def _get_existing_batch_count(self) -> int:
        """Get the count of existing batches"""
        existing_batches = list(self.base_dir.glob("embeddings_batch_*.pkl.gz"))
        if existing_batches:
            # Extract batch numbers and find the highest
            batch_numbers = []
            for batch_file in existing_batches:
                try:
                    batch_num = int(batch_file.stem.split('_')[-1])
                    batch_numbers.append(batch_num)
                except:
                    pass
            return max(batch_numbers) + 1 if batch_numbers else 0
        return 0
    
    def add_embedding(self, product_id: str, embedding_id: str, 
                     embedding: List[float], metadata: Dict[str, Any]) -> bool:
        """Add an embedding to the current batch"""
        try:
            self.current_batch.append({
                'product_id': product_id,
                'embedding_id': embedding_id,
                'embedding': embedding,
                'metadata': metadata,
                'timestamp': datetime.now().isoformat()
            })
            
            # Save batch when it reaches batch_size
            if len(self.current_batch) >= self.batch_size:
                self.save_batch()
            
            return True
        except Exception as e:
            logger.error(f"Failed to add embedding to local storage: {e}")
            return False
    
    def save_batch(self):
        """Save current batch to compressed file"""
        if not self.current_batch:
            return
            
        filename = self.base_dir / f"embeddings_batch_{self.batch_count:06d}.pkl.gz"
        
        try:
            with gzip.open(filename, 'wb') as f:
                pickle.dump(self.current_batch, f)
            
            logger.info(f"💾 Saved batch {self.batch_count} with {len(self.current_batch)} embeddings to {filename}")
            
            self.batch_count += 1
            self.current_batch = []
        except Exception as e:
            logger.error(f"Failed to save batch: {e}")
    
    def finalize(self):
        """Save any remaining embeddings and create manifest"""
        if self.current_batch:
            self.save_batch()
        
        # Create/update manifest file
        manifest_path = self.base_dir / 'manifest.json'
        manifest = {
            'total_batches': self.batch_count,
            'batch_size': self.batch_size,
            'created_at': datetime.now().isoformat(),
            'embedding_model': CONFIG['openai']['embedding_model'],
            'dimensions': CONFIG['openai']['embedding_dimensions']
        }
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"✅ Local storage finalized: {self.batch_count} batches saved")


class ResilientFashionEmbeddingsPipeline:
    """Resilient pipeline for creating fashion product embeddings"""
    
    def __init__(self):
        logger.info("Initializing Resilient Fashion Embeddings Pipeline")
        
        # Initialize clients
        self.openai_client = openai.OpenAI(api_key=CONFIG['openai']['api_key'])
        
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
        
        # Tokenizer
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
        
        # Local backup storage
        if CONFIG['pipeline']['enable_local_backup']:
            self.local_storage = LocalEmbeddingStorage(CONFIG['pipeline']['local_backup_dir'])
        else:
            self.local_storage = None
        
        # Statistics and monitoring
        self.stats = defaultdict(int)
        self.cost_tracker = {
            'tokens_used': 0,
            'embeddings_created': 0,
            'estimated_cost': 0.0
        }
        
        # Performance tracking
        self.batch_times = []
        self.start_time = None
        self.consecutive_failures = 0
        self.qdrant_healthy = True
        self.current_batch_size = CONFIG['qdrant']['batch_size']
        
        # Track products that failed after all retries
        self.permanently_failed = set(self.state.get('permanently_failed', []))
    
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
            'permanently_failed': [],
            'total_products': 0,
            'embedded_products': 0,
            'failed_products': [],
            'local_backup_count': 0,
            'start_time': datetime.now().isoformat()
        }
    
    def _save_state(self):
        """Save pipeline state"""
        self.state['processed_products'] = list(self.processed_products)
        self.state['permanently_failed'] = list(self.permanently_failed)
        self.state['embedded_products'] = len(self.processed_products)
        self.state['last_updated'] = datetime.now().isoformat()
        
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    async def run(self):
        """Main pipeline execution with resilience"""
        logger.info("="*60)
        logger.info("Starting Resilient Fashion Embeddings Pipeline")
        logger.info(f"Run ID: {self.state['run_id']}")
        logger.info(f"Embedding Model: {CONFIG['openai']['embedding_model']}")
        logger.info(f"Dimensions: {CONFIG['openai']['embedding_dimensions']}")
        logger.info(f"Resilience Features: ENABLED")
        logger.info(f"Local Backup: {'ENABLED' if CONFIG['pipeline']['enable_local_backup'] else 'DISABLED'}")
        logger.info("="*60)
        
        self.start_time = time.time()
        
        try:
            # Phase 1: Setup and validation
            collection_ready = await self._setup_qdrant_collection()
            if not collection_ready:
                logger.warning("Qdrant collection setup failed - will use local backup")
                self.qdrant_healthy = False
            
            product_count = await self._validate_and_count()
            
            if product_count == 0:
                logger.info("No products to embed!")
                return
            
            # Estimate costs
            est_cost = self._estimate_total_cost(product_count)
            logger.info(f"Estimated API cost: ${est_cost:.2f}")
            
            if CONFIG['pipeline']['dry_run']:
                logger.info("DRY RUN mode - no API calls will be made")
            
            # Phase 2: Process products with resilience
            await self._process_all_products_resilient(product_count)
            
            # Phase 3: Finalize and report
            if self.local_storage:
                self.local_storage.finalize()
            
            await self._verify_embeddings()
            self._generate_report()
            
            # Phase 4: Attempt to upload any local backups
            if self.state.get('local_backup_count', 0) > 0:
                logger.info(f"\n📤 Attempting to upload {self.state['local_backup_count']} locally backed up embeddings...")
                await self._upload_local_backups()
            
            logger.info("\n✅ Embedding pipeline completed successfully!")
            
        except KeyboardInterrupt:
            logger.warning("\nPipeline interrupted by user")
            self._save_state()
            if self.local_storage:
                self.local_storage.finalize()
            self._generate_report()
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            self._save_state()
            raise
        finally:
            self.neo4j_driver.close()
    
    async def _setup_qdrant_collection(self) -> bool:
        """Setup or verify Qdrant collection with error handling"""
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
                        default_segment_number=2  # Use 2 shards instead of 3
                    )
                )
                logger.info(f"Created Qdrant collection: {CONFIG['qdrant']['collection']}")
            else:
                count = self.qdrant.count(collection_name=CONFIG['qdrant']['collection'])
                logger.info(f"Using existing collection: {CONFIG['qdrant']['collection']} (current vectors: {count.count:,})")
            
            return True
            
        except Exception as e:
            logger.error(f"Qdrant setup failed: {e}")
            return False
    
    async def _check_qdrant_health(self) -> bool:
        """Check Qdrant cluster health"""
        try:
            # Simple health check - try to get collection info
            self.qdrant.get_collection(CONFIG['qdrant']['collection'])
            if not self.qdrant_healthy:
                logger.info("✅ Qdrant health restored!")
            self.qdrant_healthy = True
            self.consecutive_failures = 0
            return True
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            self.qdrant_healthy = False
            return False
    
    async def _validate_and_count(self) -> int:
        """Validate and count products ready for embedding"""
        with self.neo4j_driver.session() as session:
            # Get products needing embeddings
            result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.ready_for_embedding = true
                  AND p.embedding_id IS NULL
                  AND p.duplicate_of IS NULL
                RETURN count(p) as count
            """).single()
            
            total_to_embed = result['count']
            
            # Subtract already processed (excluding permanently failed)
            need_embedding = total_to_embed - len(self.processed_products - self.permanently_failed)
            
            logger.info(f"Products ready for embedding: {total_to_embed:,}")
            logger.info(f"Already processed this run: {len(self.processed_products):,}")
            logger.info(f"Permanently failed: {len(self.permanently_failed):,}")
            logger.info(f"Need embedding: {need_embedding:,}")
            
            self.state['total_products'] = need_embedding
            
            return max(0, need_embedding)
    
    def _estimate_total_cost(self, product_count: int) -> float:
        """Estimate total API cost"""
        avg_tokens_per_product = 400
        total_tokens = product_count * avg_tokens_per_product
        cost = (total_tokens / 1_000_000) * CONFIG['openai']['cost_per_1m_tokens']
        return cost
    
    async def _process_all_products_resilient(self, total_count: int):
        """Process all products with resilience features"""
        processed = 0
        
        with tqdm(total=total_count, desc="Creating embeddings") as pbar:
            while processed < total_count:
                # Periodic health check
                if processed > 0 and processed % CONFIG['qdrant']['health_check_interval'] == 0:
                    await self._check_qdrant_health()
                
                batch_start_time = time.time()
                
                # Get batch of products
                products = await self._get_product_batch_optimized(
                    skip=processed,
                    limit=CONFIG['pipeline']['neo4j_batch_size']
                )
                
                if not products:
                    break
                
                # Filter out already processed and permanently failed
                new_products = [
                    p for p in products 
                    if p.id not in self.processed_products 
                    and p.id not in self.permanently_failed
                ]
                
                if not new_products:
                    processed += len(products)
                    continue
                
                # Create embedding texts
                for product in new_products:
                    product.embedding_text = self._create_embedding_text(product)
                    product.embedding_tokens = len(self.tokenizer.encode(product.embedding_text))
                
                # Process with resilience
                successfully_processed = await self._embed_products_batch_resilient(new_products)
                
                processed += len(products)
                pbar.update(successfully_processed)
                
                # Performance tracking
                batch_time = time.time() - batch_start_time
                self.batch_times.append(batch_time)
                
                if successfully_processed > 0:
                    products_per_second = successfully_processed / batch_time
                    
                    # Log performance every 10 batches
                    if len(self.batch_times) % 10 == 0:
                        avg_rate = len(self.processed_products) / (time.time() - self.start_time)
                        eta_hours = (total_count - processed) / avg_rate / 3600 if avg_rate > 0 else 0
                        logger.info(
                            f"Rate: {products_per_second:.1f} p/s (avg: {avg_rate:.1f} p/s), "
                            f"ETA: {eta_hours:.1f} hours, "
                            f"Batch size: {self.current_batch_size}"
                        )
                
                # Save checkpoint
                if len(self.processed_products) % CONFIG['pipeline']['checkpoint_interval'] == 0:
                    self._save_checkpoint()
                
                # Check if we should stop due to too many failures
                if self.consecutive_failures >= CONFIG['pipeline']['max_consecutive_failures']:
                    logger.error(f"Stopping due to {self.consecutive_failures} consecutive failures")
                    break
    
    async def _get_product_batch_optimized(self, skip: int, limit: int) -> List[ProductContext]:
        """Get batch of products with optimized queries"""
        products = []
        
        with self.neo4j_driver.session() as session:
            result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.ready_for_embedding = true
                  AND p.embedding_id IS NULL
                  AND p.duplicate_of IS NULL
                WITH p
                ORDER BY p.visited_num DESC
                SKIP $skip LIMIT $limit
                
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
                # Skip if already processed or permanently failed
                product_id = record['p']['id']
                if product_id in self.processed_products or product_id in self.permanently_failed:
                    continue
                
                product_data = dict(record['p'])
                
                context = ProductContext(
                    id=product_data['id'],
                    title=product_data.get('title', ''),
                    description=product_data.get('description'),
                    price=product_data.get('price'),
                    visited_num=product_data.get('visited_num', 0),
                    active=product_data.get('active', True),
                    inventory=product_data.get('inventory'),
                    is_fashion=product_data.get('is_fashion', True),
                    fashion_confidence=product_data.get('fashion_confidence'),
                    fashion_category=product_data.get('fashion_category'),
                    classification_reasoning=product_data.get('classification_reasoning'),
                    product_type=product_data.get('product_type'),
                    primary_color=product_data.get('primary_color'),
                    color_list=product_data.get('color_list', []),
                    price_tier=product_data.get('price_tier'),
                    formality_level=product_data.get('formality_level'),
                    season_tags=product_data.get('season_tags', []),
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
        
        # Product Identity
        identity_parts = [f"[PRODUCT] {context.title}"]
        
        if context.product_type:
            identity_parts.append(f"Type: {context.product_type}")
        elif context.categories:
            cat_names = [c.get('name', '') for c in context.categories]
            identity_parts.append(f"Category: {', '.join(cat_names)}")
        
        if context.brand:
            identity_parts.append(f"Brand: {context.brand.get('name', '')}")
        
        if context.price:
            identity_parts.append(f"Price: ${context.price:.2f}")
            if context.price_tier:
                identity_parts.append(f"Tier: {context.price_tier}")
        
        parts.append(" | ".join(identity_parts))
        
        # Description
        if context.description:
            parts.append(f"\n[DESCRIPTION] {context.description}")
        
        # Attributes
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
        
        # Graph Context
        graph_parts = []
        
        if context.categories:
            cat_names = [c.get('name', '') for c in context.categories]
            if cat_names:
                graph_parts.append(f"Categories: {', '.join(cat_names)}")
        
        if context.collections:
            graph_parts.append(f"Collections: {', '.join(context.collections)}")
        
        if context.price_range:
            graph_parts.append(f"Price Range: {context.price_range}")
        
        if context.status:
            graph_parts.append(f"Status: {context.status}")
        
        if graph_parts:
            parts.append(f"\n[GRAPH CONTEXT]\n" + "\n".join(graph_parts))
        
        # Signals
        signals = []
        
        if context.visited_num and context.visited_num > 100:
            if context.visited_num > 1000:
                signals.append("High demand item")
            else:
                signals.append("Popular item")
        
        if context.inventory is not None:
            if context.inventory == 0:
                signals.append("Currently out of stock")
            elif context.inventory < 10:
                signals.append("Limited availability")
        
        if context.fashion_confidence and context.fashion_confidence > 0.9:
            signals.append("Highly fashion-relevant")
        
        if signals:
            parts.append(f"\n[SIGNALS] {', '.join(signals)}")
        
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
        
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)
    
    async def _embed_products_batch_resilient(self, products: List[ProductContext]) -> int:
        """Create embeddings with full resilience features"""
        successfully_processed = 0
        
        # Adaptive batch size based on recent failures
        batch_size = min(self.current_batch_size, CONFIG['openai']['batch_size'])
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            # Extract texts and track tokens
            texts = [p.embedding_text for p in batch]
            total_tokens = sum(p.embedding_tokens for p in batch)
            
            self.cost_tracker['tokens_used'] += total_tokens
            
            # Get embeddings from OpenAI
            if CONFIG['pipeline']['dry_run']:
                embeddings = [[0.1] * CONFIG['openai']['embedding_dimensions'] for _ in batch]
            else:
                embeddings = await self._get_embeddings_with_retry(texts)
            
            if not embeddings:
                logger.error(f"Failed to get embeddings for batch of {len(batch)} products")
                continue
            
            # Prepare points for Qdrant
            points = []
            point_to_product = {}
            
            for product, embedding in zip(batch, embeddings):
                embedding_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, product.id))
                
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
                
                point = PointStruct(
                    id=embedding_id,
                    vector=embedding,
                    payload=metadata
                )
                points.append(point)
                point_to_product[embedding_id] = product
            
            # Try to upload to Qdrant with resilience
            upload_success = await self._upload_to_qdrant_resilient(points, point_to_product)
            
            if upload_success:
                successfully_processed += len(batch)
                # Update Neo4j for successful uploads
                successful_products = [point_to_product[p.id] for p in points]
                await self._update_neo4j_embedding_status(successful_products)
            else:
                # Handle complete batch failure
                logger.warning(f"Batch upload failed completely for {len(batch)} products")
                
                # If local backup is enabled, save embeddings locally
                if self.local_storage and CONFIG['pipeline']['enable_local_backup']:
                    for point, product in zip(points, batch):
                        if self.local_storage.add_embedding(
                            product_id=product.id,
                            embedding_id=str(point.id),
                            embedding=point.vector,
                            metadata=point.payload
                        ):
                            self.processed_products.add(product.id)
                            self.state['local_backup_count'] = self.state.get('local_backup_count', 0) + 1
                            successfully_processed += 1
                
                # Add to permanently failed if max retries exceeded
                if self.consecutive_failures >= CONFIG['pipeline']['max_consecutive_failures']:
                    for product in batch:
                        self.permanently_failed.add(product.id)
            
            # Rate limiting
            await asyncio.sleep(CONFIG['pipeline']['rate_limit_delay'])
        
        return successfully_processed
    
    async def _upload_to_qdrant_resilient(self, points: List[PointStruct], 
                                         point_to_product: Dict[str, ProductContext]) -> bool:
        """Upload points to Qdrant with full resilience"""
        # First, check if Qdrant is healthy
        if not self.qdrant_healthy:
            if not await self._check_qdrant_health():
                return False
        
        # Try batch upload with retries
        for attempt in range(CONFIG['qdrant']['max_retries']):
            try:
                if not CONFIG['pipeline']['dry_run']:
                    self.qdrant.upsert(
                        collection_name=CONFIG['qdrant']['collection'],
                        points=points,
                        wait=True
                    )
                
                # Success - update tracking
                for point in points:
                    product = point_to_product[str(point.id)]
                    self.processed_products.add(product.id)
                    self.stats['embeddings_created'] += 1
                
                # Reset failure tracking on success
                self.consecutive_failures = 0
                
                # Increase batch size on success (adaptive sizing)
                if CONFIG['pipeline']['adaptive_batch_size']:
                    self.current_batch_size = min(
                        self.current_batch_size + 5,
                        CONFIG['qdrant']['batch_size']
                    )
                
                return True
                
            except UnexpectedResponse as e:
                error_msg = str(e)
                logger.warning(f"Qdrant upsert attempt {attempt + 1}/{CONFIG['qdrant']['max_retries']} failed: {error_msg}")
                
                # Check if it's a shard failure
                if "shard failed" in error_msg or "500" in error_msg:
                    self.qdrant_healthy = False
                    self.consecutive_failures += 1
                    
                    if attempt < CONFIG['qdrant']['max_retries'] - 1:
                        # Exponential backoff
                        wait_time = CONFIG['qdrant']['retry_delay'] * (2 ** attempt)
                        logger.info(f"Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        
                        # Reduce batch size on failure (adaptive sizing)
                        if CONFIG['pipeline']['adaptive_batch_size']:
                            self.current_batch_size = max(
                                self.current_batch_size // 2,
                                CONFIG['pipeline']['min_batch_size']
                            )
                            logger.info(f"Reduced batch size to {self.current_batch_size}")
                    else:
                        # Last attempt - try sub-batches
                        logger.info("Attempting sub-batch upload...")
                        return await self._upload_in_sub_batches(points, point_to_product)
                else:
                    # Other error - don't retry
                    raise
            
            except Exception as e:
                logger.error(f"Unexpected error during Qdrant upload: {e}")
                self.consecutive_failures += 1
                return False
        
        return False
    
    async def _upload_in_sub_batches(self, points: List[PointStruct], 
                                     point_to_product: Dict[str, ProductContext]) -> bool:
        """Upload points in smaller sub-batches when main batch fails"""
        successful_count = 0
        sub_batch_size = CONFIG['qdrant']['sub_batch_size']
        
        for i in range(0, len(points), sub_batch_size):
            sub_points = points[i:i + sub_batch_size]
            
            for retry in range(3):  # Fewer retries for sub-batches
                try:
                    if not CONFIG['pipeline']['dry_run']:
                        self.qdrant.upsert(
                            collection_name=CONFIG['qdrant']['collection'],
                            points=sub_points,
                            wait=True
                        )
                    
                    # Update tracking for successful sub-batch
                    for point in sub_points:
                        product = point_to_product[str(point.id)]
                        self.processed_products.add(product.id)
                        self.stats['embeddings_created'] += 1
                        successful_count += 1
                    
                    # Small delay between sub-batches
                    await asyncio.sleep(2)
                    break
                    
                except Exception as e:
                    logger.error(f"Sub-batch failed (attempt {retry + 1}/3): {e}")
                    if retry < 2:
                        await asyncio.sleep(5 * (retry + 1))
                    else:
                        # Save to local backup if available
                        if self.local_storage and CONFIG['pipeline']['enable_local_backup']:
                            for point in sub_points:
                                product = point_to_product[str(point.id)]
                                self.local_storage.add_embedding(
                                    product_id=product.id,
                                    embedding_id=str(point.id),
                                    embedding=point.vector,
                                    metadata=point.payload
                                )
                                self.state['local_backup_count'] = self.state.get('local_backup_count', 0) + 1
        
        return successful_count > 0
    
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
                logger.warning(f"OpenAI embedding attempt {attempt + 1} failed: {e}")
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
            
            # Update in smaller batches to avoid query size limits
            batch_size = 500
            for i in range(0, len(product_data), batch_size):
                batch = product_data[i:i + batch_size]
                
                try:
                    session.run("""
                        UNWIND $products as item
                        MATCH (p:Product {id: item.id})
                        SET p.embedding_id = item.embedding_id,
                            p.embedding_created_at = datetime(),
                            p.embedding_model = $model,
                            p.embedding_tokens = item.tokens
                    """, products=batch, model=CONFIG['openai']['embedding_model'])
                except Exception as e:
                    logger.error(f"Failed to update Neo4j for batch: {e}")
    
    def _save_checkpoint(self):
        """Save checkpoint for recovery"""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'processed_count': len(self.processed_products),
            'permanently_failed_count': len(self.permanently_failed),
            'tokens_used': self.cost_tracker['tokens_used'],
            'embeddings_created': self.stats['embeddings_created'],
            'local_backup_count': self.state.get('local_backup_count', 0),
            'state': self.state,
            'performance_stats': {
                'avg_batch_time': np.mean(self.batch_times[-100:]) if self.batch_times else 0,
                'products_per_second': len(self.processed_products) / (time.time() - self.start_time) if self.start_time else 0,
                'current_batch_size': self.current_batch_size,
                'consecutive_failures': self.consecutive_failures,
                'qdrant_healthy': self.qdrant_healthy
            }
        }
        
        checkpoint_file = self.checkpoints_dir / f'checkpoint_{len(self.processed_products)}.json'
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        # Also save main state
        self._save_state()
        
        logger.info(f"Checkpoint saved: {len(self.processed_products):,} processed, {self.state.get('local_backup_count', 0):,} in local backup")
    
    async def _upload_local_backups(self):
        """Attempt to upload locally backed up embeddings to Qdrant"""
        backup_dir = Path(CONFIG['pipeline']['local_backup_dir'])
        manifest_path = backup_dir / 'manifest.json'
        
        if not manifest_path.exists():
            logger.warning("No local backup manifest found")
            return
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        logger.info(f"Found {manifest['total_batches']} backup batches to upload")
        
        uploaded_count = 0
        for batch_num in range(manifest['total_batches']):
            filename = backup_dir / f"embeddings_batch_{batch_num:06d}.pkl.gz"
            
            if not filename.exists():
                continue
            
            try:
                with gzip.open(filename, 'rb') as f:
                    batch_data = pickle.load(f)
                
                # Convert to Qdrant points
                points = []
                for item in batch_data:
                    point = PointStruct(
                        id=item['embedding_id'],
                        vector=item['embedding'],
                        payload=item['metadata']
                    )
                    points.append(point)
                
                # Try to upload
                if await self._upload_to_qdrant_resilient(points, {}):
                    uploaded_count += len(points)
                    logger.info(f"✅ Uploaded backup batch {batch_num} ({len(points)} vectors)")
                    
                    # Update Neo4j for these products
                    product_ids = [item['product_id'] for item in batch_data]
                    await self._mark_products_as_embedded(product_ids)
                    
                    # Delete the backup file after successful upload
                    filename.unlink()
                else:
                    logger.warning(f"Failed to upload backup batch {batch_num}")
                    
            except Exception as e:
                logger.error(f"Error processing backup batch {batch_num}: {e}")
        
        logger.info(f"Uploaded {uploaded_count:,} vectors from local backup")
        self.state['local_backup_count'] = max(0, self.state.get('local_backup_count', 0) - uploaded_count)
    
    async def _mark_products_as_embedded(self, product_ids: List[str]):
        """Mark products as having embeddings in Neo4j"""
        with self.neo4j_driver.session() as session:
            batch_size = 500
            for i in range(0, len(product_ids), batch_size):
                batch = product_ids[i:i + batch_size]
                
                try:
                    session.run("""
                        UNWIND $product_ids as pid
                        MATCH (p:Product {id: pid})
                        SET p.embedding_id = pid,
                            p.embedding_created_at = datetime(),
                            p.embedding_model = $model
                    """, product_ids=batch, model=CONFIG['openai']['embedding_model'])
                except Exception as e:
                    logger.error(f"Failed to mark products as embedded: {e}")
    
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
        
        # Check local backups
        if self.state.get('local_backup_count', 0) > 0:
            logger.info(f"⚠️  Products in local backup (not uploaded): {self.state['local_backup_count']:,}")
    
    def _generate_report(self):
        """Generate comprehensive pipeline report"""
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
            'permanently_failed': len(self.permanently_failed),
            'local_backup_count': self.state.get('local_backup_count', 0),
            'tokens_used': self.cost_tracker['tokens_used'],
            'estimated_cost_usd': round(total_cost, 2),
            'average_tokens_per_product': self.cost_tracker['tokens_used'] / max(self.stats['embeddings_created'], 1),
            'model': CONFIG['openai']['embedding_model'],
            'dimensions': CONFIG['openai']['embedding_dimensions'],
            'performance': {
                'total_time_seconds': total_time,
                'average_products_per_second': avg_rate,
                'total_time_hours': total_time / 3600,
                'final_batch_size': self.current_batch_size,
                'total_qdrant_failures': self.consecutive_failures
            },
            'configuration': {
                'neo4j_batch_size': CONFIG['pipeline']['neo4j_batch_size'],
                'qdrant_batch_size': CONFIG['qdrant']['batch_size'],
                'resilience_enabled': True,
                'local_backup_enabled': CONFIG['pipeline']['enable_local_backup']
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
        logger.info(f"Local backups: {self.state.get('local_backup_count', 0):,}")
        logger.info(f"Permanently failed: {len(self.permanently_failed):,}")
        logger.info(f"Total tokens used: {self.cost_tracker['tokens_used']:,}")
        logger.info(f"Estimated cost: ${total_cost:.2f}")
        logger.info(f"Average tokens/product: {report['average_tokens_per_product']:.0f}")
        logger.info(f"Processing rate: {avg_rate:.1f} products/second")
        logger.info(f"Total time: {total_time/3600:.1f} hours")
        logger.info(f"Qdrant health: {'Healthy' if self.qdrant_healthy else 'Unhealthy'}")
        logger.info(f"Report saved to: {report_file}")
        logger.info("="*60)


def main():
    """Main execution"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Resilient Fashion Embeddings Pipeline")
        print("=====================================")
        print("Features:")
        print("- Automatic retry with exponential backoff")
        print("- Local backup when Qdrant fails")
        print("- Adaptive batch sizing")
        print("- Health monitoring")
        print("- Checkpoint recovery")
        print("\nUsage: python resilient_embeddings_pipeline.py")
        print("\nEnvironment variables needed:")
        print("- OPENAI_API_KEY")
        print("- NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD")
        print("- QDRANT_URL, QDRANT_API_KEY")
        print("- QDRANT_COLLECTION (optional, defaults to 'fashion_products')")
        sys.exit(0)
    
    pipeline = ResilientFashionEmbeddingsPipeline()
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()