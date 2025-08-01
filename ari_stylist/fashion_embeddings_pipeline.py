#!/usr/bin/env python3
"""
Fashion Product Embeddings Pipeline
Converts Neo4j graph structure into rich embeddings stored in Qdrant
Captures product information, graph relationships, and context
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
    OptimizersConfigDiff, CollectionInfo,
    Filter, FieldCondition, MatchValue
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
        'password': os.getenv('NEO4J_PASSWORD', 'shopari1234')
    },
    'openai': {
        'api_key': os.getenv('OPENAI_API_KEY'),
        'embedding_model': 'text-embedding-3-small',
        'embedding_dimensions': 1536,
        'max_tokens': 8191,
        'batch_size': 100,  # OpenAI allows up to 100 texts per request
        'cost_per_1m_tokens': 0.020,  # $0.020 per 1M tokens
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
        'neo4j_batch_size': 500,
        'max_related_items': 5,
        'max_text_length': 6000,  # Leave buffer for safety
        'checkpoint_interval': 1000,
        'output_dir': './embeddings_pipeline',
        'resume_enabled': True,
        'dry_run': False  # Set to True to test without API calls
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
    category_path: Optional[str] = None
    brand: Optional[Dict[str, Any]] = None
    collections: List[str] = field(default_factory=list)
    price_range: Optional[str] = None
    status: Optional[str] = None
    
    # Related products context
    related_products: List[Dict[str, Any]] = field(default_factory=list)
    sibling_products: List[str] = field(default_factory=list)
    brand_family: List[str] = field(default_factory=list)
    
    # Embedding data
    embedding_text: Optional[str] = None
    embedding_tokens: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class FashionEmbeddingsPipeline:
    """Pipeline to create rich embeddings from Neo4j graph"""
    
    def __init__(self):
        logger.info("Initializing Fashion Embeddings Pipeline")
        
        # Initialize clients
        self.openai_client = openai.OpenAI(api_key=CONFIG['openai']['api_key'])
        self.neo4j_driver = GraphDatabase.driver(
            CONFIG['neo4j']['url'],
            auth=(CONFIG['neo4j']['username'], CONFIG['neo4j']['password'])
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
    
    def _load_state(self) -> Dict[str, Any]:
        """Load pipeline state for resume capability"""
        if self.state_file.exists() and CONFIG['pipeline']['resume_enabled']:
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    logger.info(f"Resumed from previous state: {state.get('embedded_products', 0)} products processed")
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
        logger.info("Starting Fashion Embeddings Pipeline")
        logger.info(f"Run ID: {self.state['run_id']}")
        logger.info(f"Embedding Model: {CONFIG['openai']['embedding_model']}")
        logger.info(f"Dimensions: {CONFIG['openai']['embedding_dimensions']}")
        logger.info(f"Dry Run: {CONFIG['pipeline']['dry_run']}")
        logger.info("="*60)
        
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
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
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
                        indexing_threshold=10000,
                        default_segment_number=4
                    )
                )
                logger.info(f"Created Qdrant collection: {CONFIG['qdrant']['collection']}")
            else:
                # Verify dimensions
                info = self.qdrant.get_collection(CONFIG['qdrant']['collection'])
                if info.config.params.vectors.size != CONFIG['openai']['embedding_dimensions']:
                    raise ValueError(f"Collection exists with different dimensions: {info.config.params.vectors.size}")
                
                # Get current count
                count = self.qdrant.count(collection_name=CONFIG['qdrant']['collection'])
                logger.info(f"Using existing collection: {CONFIG['qdrant']['collection']} (current vectors: {count.count:,})")
                
        except Exception as e:
            logger.error(f"Qdrant setup failed: {e}")
            raise
    
    async def _validate_and_count(self) -> int:
        """Validate and count products ready for embedding"""
        with self.neo4j_driver.session() as session:
            # Count products
            result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.ready_for_embedding = true
                RETURN count(p) as total,
                       sum(CASE WHEN p.embedding_id IS NOT NULL THEN 1 ELSE 0 END) as already_embedded
            """).single()
            
            total = result['total']
            already_embedded = result['already_embedded']
            
            # Get products needing embedding
            need_embedding_query = """
                MATCH (p:Product:FashionProduct)
                WHERE p.ready_for_embedding = true
                AND p.embedding_id IS NULL
            """

            if self.processed_products:
                need_embedding_query += " AND NOT p.id IN $processed"
                need_embedding_query += " RETURN count(p) as count"  # ADD THIS LINE!
                need_result = session.run(need_embedding_query, processed=list(self.processed_products)).single()
            else:
                need_result = session.run(need_embedding_query + " RETURN count(p) as count").single()
            
            need_embedding = need_result['count']
            
            logger.info(f"Products ready for embedding: {total:,}")
            logger.info(f"Already have embedding_id: {already_embedded:,}")
            logger.info(f"Already processed this run: {len(self.processed_products):,}")
            logger.info(f"Need embedding: {need_embedding:,}")
            
            self.state['total_products'] = need_embedding
            
            return need_embedding
    
    def _estimate_total_cost(self, product_count: int) -> float:
        """Estimate total API cost"""
        # Assume average 500 tokens per product
        avg_tokens_per_product = 500
        total_tokens = product_count * avg_tokens_per_product
        cost = (total_tokens / 1_000_000) * CONFIG['openai']['cost_per_1m_tokens']
        return cost
    
    async def _process_all_products(self, total_count: int):
        """Process all products in batches"""
        processed = 0
        
        with tqdm(total=total_count, desc="Creating embeddings") as pbar:
            while processed < total_count:
                # Get batch of products with context
                products = await self._get_product_batch_with_context(
                    skip=processed,
                    limit=CONFIG['pipeline']['neo4j_batch_size']
                )
                # products = await self._get_product_batch_with_context(
                #     skip=processed,
                #     limit=10  # HARDCODE to 10!
#)
                
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
                
                # Save checkpoint
                if len(self.processed_products) % CONFIG['pipeline']['checkpoint_interval'] == 0:
                    self._save_checkpoint()
    
    async def _get_product_batch_with_context(self, skip: int, limit: int) -> List[ProductContext]:
        """Get batch of products with full graph context"""
        products = []
        
        with self.neo4j_driver.session() as session:
            # Main query with all relationships
            result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.ready_for_embedding = true
                  AND p.embedding_id IS NULL
                WITH p SKIP $skip LIMIT $limit
                
                // Get all relationships
                OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
                OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                OPTIONAL MATCH (p)-[:IN_COLLECTION]->(col:Collection)
                OPTIONAL MATCH (p)-[:IN_PRICE_RANGE]->(pr:PriceRange)
                OPTIONAL MATCH (p)-[:HAS_STATUS]->(s:Status)
                
                /*
                // Get category hierarchy
                OPTIONAL MATCH cat_path = (c)-[:SUBCATEGORY_OF*0..]->(root:Category)
                WHERE NOT (root)-[:SUBCATEGORY_OF]->()
                
                // Get sibling products (same category)
                OPTIONAL MATCH (c)<-[:IN_CATEGORY]-(sibling:Product:FashionProduct)
                WHERE sibling.id <> p.id
                WITH p, c, b, col, pr, s, cat_path,
                     collect(DISTINCT sibling.title)[..5] as siblings
                
                // Get brand family
                OPTIONAL MATCH (b)<-[:BY_BRAND]-(brand_product:Product:FashionProduct)
                WHERE brand_product.id <> p.id
                WITH p, c, b, col, pr, s, cat_path, siblings,
                     collect(DISTINCT brand_product.title)[..5] as brand_family
                
                                 
                RETURN p,
                       collect(DISTINCT c) as categories,
                       b as brand,
                       collect(DISTINCT col.name) as collections,
                       pr.name as price_range,
                       s.name as status,
                       [node in nodes(cat_path) | node.name] as category_path,
                       siblings,
                       brand_family
                ORDER BY p.visited_num DESC
                */
                RETURN p,
                       collect(DISTINCT c) as categories,
                       b as brand,
                       collect(DISTINCT col.name) as collections,
                       pr.name as price_range,
                       s.name as status,
                       [] as category_path,  // Empty array instead of nodes(cat_path)
                       [] as siblings,       // Empty array
                       [] as brand_family    // Empty array
                ORDER BY p.visited_num DESC
            """, skip=skip, limit=limit)
            
            for record in result:
                # Skip if already processed
                if record['p']['id'] in self.processed_products:
                    continue
                
                product_data = dict(record['p'])
                
                # Build category path string
                category_path = None
                if record['category_path']:
                    # Create proper hierarchy (root -> leaf)
                    category_path = ' > '.join(record['category_path'])
                
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
                    category_path=category_path,
                    brand=dict(record['brand']) if record['brand'] else None,
                    collections=record['collections'] or [],
                    price_range=record['price_range'],
                    status=record['status'],
                    
                    # Related products
                    sibling_products=record['siblings'] or [],
                    brand_family=record['brand_family'] or []
                )
                
                # Get additional related products
                if len(context.sibling_products) < CONFIG['pipeline']['max_related_items']:
                    related = await self._get_related_products(session, context.id)
                    context.related_products = related
                
                products.append(context)
        
        return products
    
    async def _get_related_products(self, session, product_id: str) -> List[Dict[str, Any]]:
        """Get related products for additional context"""
        result = session.run("""
            MATCH (p:Product {id: $product_id})-[:IN_CATEGORY]->(c:Category)
            MATCH (related:Product:FashionProduct)-[:IN_CATEGORY]->(c)
            WHERE related.id <> $product_id
              AND related.is_fashion = true
            WITH related, p,
                 CASE 
                   WHEN p.price IS NOT NULL AND related.price IS NOT NULL 
                   THEN abs(p.price - related.price) / p.price
                   ELSE 1.0
                 END as price_diff
            WHERE price_diff < 0.3  // Within 30% price range
            RETURN related.id as id, 
                   related.title as title,
                   related.price as price
            ORDER BY related.visited_num DESC
            LIMIT $limit
        """, product_id=product_id, limit=CONFIG['pipeline']['max_related_items'])
        
        return [dict(record) for record in result]
    
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
        
        # Add brand
        if context.brand:
            identity_parts.append(f"Brand: {context.brand.get('name', '')}")
        
        # Add price
        if context.price:
            identity_parts.append(f"Price: ${context.price:.2f}")
            if context.price_tier:
                identity_parts.append(f"Tier: {context.price_tier}")
        
        parts.append(" | ".join(identity_parts))
        
        # 2. Description Section
        if context.description:
            # Smart truncation to fit token limits
            desc = self._smart_truncate(context.description, 2000)
            parts.append(f"\n[DESCRIPTION] {desc}")
        
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
        
        # Category hierarchy
        if context.category_path:
            graph_parts.append(f"Category Path: {context.category_path}")
        
        # Collections
        if context.collections:
            graph_parts.append(f"Collections: {', '.join(context.collections[:3])}")
        
        # Price range
        if context.price_range:
            graph_parts.append(f"Price Range: {context.price_range}")
        
        # Status
        if context.status:
            graph_parts.append(f"Status: {context.status}")
        
        if graph_parts:
            parts.append(f"\n[GRAPH CONTEXT]\n" + "\n".join(graph_parts))
        
        # 5. Related Products Context
        related_parts = []
        
        if context.sibling_products:
            related_parts.append(f"Similar products in category: {', '.join(context.sibling_products[:3])}")
        
        if context.brand_family:
            brand_name = context.brand.get('name', 'this brand') if context.brand else 'this brand'
            related_parts.append(f"Other {brand_name} products: {', '.join(context.brand_family[:3])}")
        
        if context.related_products:
            related_titles = [r['title'] for r in context.related_products[:3]]
            related_parts.append(f"Related items: {', '.join(related_titles)}")
        
        if related_parts:
            parts.append(f"\n[RELATED CONTEXT]\n" + "\n".join(related_parts))
        
        # 6. Signals Section
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
        if len(self.tokenizer.encode(embedding_text)) > CONFIG['pipeline']['max_text_length']:
            embedding_text = self._truncate_to_token_limit(embedding_text, CONFIG['pipeline']['max_text_length'])
        
        return embedding_text
    
    def _smart_truncate(self, text: str, max_length: int) -> str:
        """Intelligently truncate text preserving key information"""
        if not text or len(text) <= max_length:
            return text
        
        # Try to break at sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        if last_period > max_length * 0.8:
            return truncated[:last_period + 1]
        
        # Break at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.9:
            return truncated[:last_space] + '...'
        
        return truncated + '...'
    
    def _truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit"""
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        # Binary search for the right length
        left, right = 0, len(text)
        while left < right:
            mid = (left + right + 1) // 2
            if len(self.tokenizer.encode(text[:mid])) <= max_tokens:
                left = mid
            else:
                right = mid - 1
        
        return text[:left].rstrip() + '...'
    
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
                    # Create metadata
                    metadata = {
                        'product_id': product.id,
                        'title': product.title,
                        'brand': product.brand.get('name') if product.brand else None,
                        'price': product.price,
                        'price_tier': product.price_tier,
                        'product_type': product.product_type,
                        'primary_color': product.primary_color,
                        'category_path': product.category_path,
                        'collections': product.collections,
                        'visited_num': product.visited_num,
                        'fashion_confidence': product.fashion_confidence,
                        'embedding_model': CONFIG['openai']['embedding_model'],
                        'embedding_date': datetime.now().isoformat(),
                        'token_count': product.embedding_tokens
                    }
                    
                    # Create Qdrant point
                    point = PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, product.id)),  # Deterministic UUID
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
            query = """
            UNWIND $products as item
            MATCH (p:Product {id: item.id})
            SET p.embedding_id = item.embedding_id,
                p.embedding_created_at = datetime(),
                p.embedding_model = $model,
                p.embedding_tokens = item.tokens
            RETURN count(p) as updated
            """
            
            product_data = [
                {
                    'id': p.id,
                    'embedding_id': str(uuid.uuid5(uuid.NAMESPACE_DNS, p.id)),
                    'tokens': p.embedding_tokens
                }
                for p in products
            ]
            
            result = session.run(
                query,
                products=product_data,
                model=CONFIG['openai']['embedding_model']
            )
            
            updated = result.single()['updated']
            logger.debug(f"Updated {updated} products with embedding status")
    
    def _save_checkpoint(self):
        """Save checkpoint for recovery"""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'processed_count': len(self.processed_products),
            'tokens_used': self.cost_tracker['tokens_used'],
            'embeddings_created': self.stats['embeddings_created'],
            'state': self.state
        }
        
        checkpoint_file = self.checkpoints_dir / f'checkpoint_{len(self.processed_products)}.json'
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        # Also save main state
        self._save_state()
        
        logger.info(f"Checkpoint saved: {len(self.processed_products)} products processed")
    
    async def _verify_embeddings(self):
        """Verify embeddings were created successfully"""
        logger.info("\nVerifying embeddings...")
        
        # Check Qdrant
        collection_info = self.qdrant.get_collection(CONFIG['qdrant']['collection'])
        vectors_count = collection_info.vectors_count
        
        logger.info(f"Vectors in Qdrant: {vectors_count:,}")
        
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
                test_results = self.qdrant.search(
                    collection_name=CONFIG['qdrant']['collection'],
                    query_vector=[0.1] * CONFIG['openai']['embedding_dimensions'],
                    limit=3
                )
                logger.info(f"✓ Search test successful - found {len(test_results)} results")
            except Exception as e:
                logger.warning(f"Search test failed: {e}")
    
    def _generate_report(self):
        """Generate final report"""
        # Calculate final cost
        total_cost = (self.cost_tracker['tokens_used'] / 1_000_000) * CONFIG['openai']['cost_per_1m_tokens']
        self.cost_tracker['estimated_cost'] = total_cost
        
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
            'dry_run': CONFIG['pipeline']['dry_run']
        }
        
        report_file = self.reports_dir / f'embedding_report_{self.state["run_id"]}.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("EMBEDDING PIPELINE COMPLETE - SUMMARY")
        logger.info("="*60)
        logger.info(f"Products processed: {len(self.processed_products):,}")
        logger.info(f"Embeddings created: {self.stats['embeddings_created']:,}")
        logger.info(f"Total tokens used: {self.cost_tracker['tokens_used']:,}")
        logger.info(f"Estimated cost: ${total_cost:.2f}")
        logger.info(f"Average tokens/product: {report['average_tokens_per_product']:.0f}")
        logger.info(f"Report saved to: {report_file}")
        logger.info("="*60)


def main():
    """Main execution"""
    pipeline = FashionEmbeddingsPipeline()
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()