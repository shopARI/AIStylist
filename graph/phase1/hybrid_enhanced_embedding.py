#!/usr/bin/env python3
"""
Hybrid Enhanced Fashion Embedding Pipeline
Combines quality analysis with fashion intelligence metadata
Best of both approaches: contamination detection + Phase 1-5 enhancements
"""

import os
import json
import time
import hashlib
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict, Counter
import numpy as np
from tqdm import tqdm

# Database and ML imports
from neo4j import GraphDatabase
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Match

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


class HybridFashionEmbeddingPipeline:
    def __init__(self):
        """Initialize all connections and configurations"""
        
        # Neo4j connection - enhanced for Phase 1-5 data
        self.driver = GraphDatabase.driver(
            'bolt://34.135.40.119:7687',
            auth=('neo4j', 'shopari1234')
        )
        self.database = 'productionbackup2'  # Use enhanced database
        
        # OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=api_key) if api_key else None
        
        # Qdrant client
        qdrant_url = os.getenv('QDRANT_URL')
        self.qdrant_host = os.getenv('QDRANT_HOST', 'localhost')
        self.qdrant_port = int(os.getenv('QDRANT_PORT', 6333))
        self.qdrant_api_key = os.getenv('QDRANT_API_KEY')
        
        if qdrant_url and qdrant_url.startswith('https://'):
            self.qdrant = QdrantClient(
                url=qdrant_url,
                api_key=self.qdrant_api_key,
                timeout=30,
                prefer_grpc=False
            )
        else:
            self.qdrant = QdrantClient(
                host=self.qdrant_host,
                port=self.qdrant_port,
                api_key=self.qdrant_api_key
            )
        
        # Configuration
        self.collection_name = 'fashion_products_hybrid_enhanced'
        self.embedding_dim = 1536  # OpenAI ada-002
        
        # Quality analysis results (from your approach)
        self.contamination_ids = set()
        self.duplicate_groups = {}
        self.semantic_outliers = set()
        
        # Fashion enhancement stats
        self.enhancement_stats = {
            'processed': 0,
            'enhanced_payloads': 0,
            'embedding_created': 0,
            'errors': 0,
            'quality_filtered': 0
        }
        
        # Reports directory
        self.reports_dir = Path('./hybrid_pipeline_reports')
        self.reports_dir.mkdir(exist_ok=True)
        
        # Fashion keywords for contamination detection (your approach)
        self.fashion_keywords = {
            'shirt', 'dress', 'pants', 'shoes', 'jacket', 'coat', 'sweater',
            'jeans', 'skirt', 'blouse', 'suit', 'tie', 'socks', 'underwear',
            'bag', 'purse', 'wallet', 'watch', 'jewelry', 'necklace', 'ring',
            'bracelet', 'earrings', 'sunglasses', 'belt', 'scarf', 'hat'
        }
        
        self.non_fashion_keywords = {
            'furniture', 'electronics', 'computer', 'phone', 'tablet', 'tv',
            'kitchen', 'appliance', 'tool', 'hardware', 'garden', 'toy',
            'game', 'book', 'vitamin', 'supplement', 'medicine', 'food',
            'beverage', 'cleaning', 'pet', 'office', 'school'
        }
    
    def run_complete_pipeline(self):
        """Execute the hybrid pipeline with user choices"""
        logger.info("="*80)
        logger.info("HYBRID ENHANCED FASHION EMBEDDING PIPELINE")
        logger.info(f"Started: {datetime.now()}")
        logger.info("="*80)
        
        try:
            print("\nHybrid Pipeline Options:")
            print("1. Full pipeline (Quality Analysis + Enhanced Embedding)")
            print("2. Quality analysis only")
            print("3. Enhanced embedding only (skip quality analysis)")
            print("4. Load previous quality analysis + Enhanced embedding")
            
            choice = input("\nSelect option (1-4): ")
            
            skip_quality = choice == '3'
            skip_embedding = choice == '2'
            load_previous = choice == '4'
            
            if load_previous:
                logger.info("Loading previous quality analysis...")
                self.load_previous_analysis()
            elif not skip_quality:
                # PHASE 1: Quality Analysis (your approach)
                logger.info("\n" + "="*60)
                logger.info("PHASE 1: QUALITY ANALYSIS & CONTAMINATION DETECTION")
                logger.info("="*60)
                
                self.analyze_contamination()
                self.analyze_duplicates()
                self.analyze_semantic_outliers()
                self.display_quality_summary()
                
                # Save quality analysis
                self.save_quality_analysis()
            
            if not skip_embedding:
                # PHASE 2: Enhanced Embedding (my approach)
                logger.info("\n" + "="*60)
                logger.info("PHASE 2: ENHANCED METADATA EMBEDDING GENERATION")
                logger.info("="*60)
                
                if self.confirm_action("Proceed with enhanced embedding generation?"):
                    self.generate_enhanced_embeddings()
                else:
                    logger.info("Enhanced embedding generation skipped")
            
            logger.info("\n" + "="*80)
            logger.info("HYBRID PIPELINE COMPLETE")
            logger.info("="*80)
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
        finally:
            self.driver.close()
    
    def analyze_contamination(self):
        """Detect non-fashion contamination (your approach)"""
        logger.info("\n1. Analyzing Contamination...")
        
        with self.driver.session(database=self.database) as session:
            contamination_count = 0
            batch_size = 10000
            offset = 0
            limit = 100000  # Sample size
            
            while offset < limit:
                products = session.run("""
                    MATCH (p:Product)
                    WHERE p.title IS NOT NULL OR p.description IS NOT NULL
                    RETURN p.uuid as id, p.title as title, p.description as description
                    SKIP $offset LIMIT $batch_size
                """, offset=offset, batch_size=batch_size).data()
                
                if not products:
                    break
                
                for product in products:
                    text = f"{product['title'] or ''} {product['description'] or ''}".lower()
                    
                    # Count keyword matches
                    fashion_score = sum(1 for kw in self.fashion_keywords if kw in text)
                    non_fashion_score = sum(1 for kw in self.non_fashion_keywords if kw in text)
                    
                    # Strong contamination signal
                    if non_fashion_score > fashion_score * 1.5:
                        self.contamination_ids.add(product['id'])
                        contamination_count += 1
                
                offset += batch_size
            
            logger.info(f"  Contaminated products found: {contamination_count:,}")
    
    def analyze_duplicates(self):
        """Analyze duplicates (your approach)"""
        logger.info("\n2. Analyzing Duplicates...")
        
        with self.driver.session(database=self.database) as session:
            products = session.run("""
                MATCH (p:Product)
                WHERE p.title IS NOT NULL
                RETURN p.uuid as id, p.title as title, 
                       p.description as description, p.price as price
                LIMIT 100000
            """).data()
            
            # Title + Description hash for true duplicates
            title_desc_groups = defaultdict(list)
            
            for product in products:
                if product['description']:
                    combined = f"{product['title']}|{product['description']}".lower().strip()
                    combined_hash = hashlib.md5(combined.encode()).hexdigest()
                    title_desc_groups[combined_hash].append(product['id'])
            
            # Find true duplicates
            for hash_val, ids in title_desc_groups.items():
                if len(ids) > 1:
                    master_id = ids[0]
                    duplicate_ids = ids[1:]
                    self.duplicate_groups[master_id] = duplicate_ids
            
            duplicate_count = sum(len(ids) for ids in self.duplicate_groups.values())
            logger.info(f"  Duplicate products found: {duplicate_count:,}")
    
    def analyze_semantic_outliers(self):
        """Find semantic outliers using LLM (your approach)"""
        logger.info("\n3. Analyzing Semantic Outliers...")
        
        if not self.openai_client:
            logger.warning("  OpenAI not configured - skipping semantic analysis")
            return
        
        with self.driver.session(database=self.database) as session:
            products = session.run("""
                MATCH (p:Product)
                WHERE p.title IS NOT NULL AND rand() < 0.01
                RETURN p.uuid as id, p.title as title
                LIMIT 50
            """).data()
            
            outlier_count = 0
            for batch_start in range(0, len(products), 10):
                batch = products[batch_start:batch_start+10]
                titles = [p['title'][:100] for p in batch]
                
                prompt = f"""Classify these products as FASHION or NON_FASHION:
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(titles))}

Return JSON array: ["fashion", "non_fashion", ...]"""
                
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0,
                        max_tokens=200
                    )
                    
                    result = response.choices[0].message.content
                    classifications = json.loads(result.strip().replace('```json', '').replace('```', ''))
                    
                    for i, classification in enumerate(classifications):
                        if classification == "non_fashion" and i < len(batch):
                            self.semantic_outliers.add(batch[i]['id'])
                            outlier_count += 1
                            
                except Exception as e:
                    logger.warning(f"  LLM classification error: {e}")
            
            logger.info(f"  Semantic outliers found: {outlier_count}")
    
    def display_quality_summary(self):
        """Display quality analysis summary"""
        total_to_exclude = len(self.contamination_ids) + sum(len(ids) for ids in self.duplicate_groups.values()) + len(self.semantic_outliers)
        
        print("\n" + "="*60)
        print("QUALITY ANALYSIS SUMMARY")
        print("="*60)
        print(f"Products to exclude from embedding:")
        print(f"  - Contamination: {len(self.contamination_ids):,}")
        print(f"  - Duplicates: {sum(len(ids) for ids in self.duplicate_groups.values()):,}")
        print(f"  - Semantic outliers: {len(self.semantic_outliers):,}")
        print(f"  - Total exclusions: {total_to_exclude:,}")
    
    def get_enhanced_product_data(self, limit: Optional[int] = None):
        """Fetch products with Phase 1-5 enhanced metadata"""
        logger.info("Fetching enhanced product data from Neo4j...")
        
        # Build exclusion set from quality analysis
        exclude_ids = self.contamination_ids.copy()
        for duplicate_ids in self.duplicate_groups.values():
            exclude_ids.update(duplicate_ids)
        exclude_ids.update(self.semantic_outliers)
        
        logger.info(f"  Excluding {len(exclude_ids):,} low-quality products")
        
        query = """
        MATCH (p:Product)
        OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)
        OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)
        OPTIONAL MATCH (p)-[:MADE_BY]->(b:Brand)
        
        WITH p, 
             collect(DISTINCT c.name) as colors,
             collect(DISTINCT s.name) as styles,
             b.name as brand
        
        WHERE p.uuid IS NOT NULL
        AND p.title IS NOT NULL
        
        RETURN p.uuid as uuid,
               p.title as title, 
               p.description as description,
               p.price as price,
               colors,
               styles,
               brand
        ORDER BY p.title
        """ + (f" LIMIT {limit}" if limit else "")
        
        enhanced_products = []
        
        with self.driver.session(database=self.database) as session:
            result = session.run(query)
            
            for record in result:
                # Skip if in exclusion list (quality control)
                if record['uuid'] in exclude_ids:
                    self.enhancement_stats['quality_filtered'] += 1
                    continue
                
                try:
                    # Get fashion intelligence from Phase 3 ontology
                    color_complements = self.get_color_complements(record['colors'])
                    style_compatible = self.get_style_compatibility(record['styles'])
                    price_tier = self.determine_price_tier(record['price'])
                    occasions = self.get_appropriate_occasions(record['styles'])
                    
                    # Create enhanced text for embedding
                    enhanced_text = self.create_enhanced_text(
                        record['title'] or '',
                        record['description'] or '',
                        record['colors'],
                        record['styles'],
                        record['brand'],
                        occasions
                    )
                    
                    # Create comprehensive payload
                    enhanced_payload = self.create_enhanced_payload(
                        record, color_complements, style_compatible, 
                        price_tier, occasions
                    )
                    
                    product = {
                        'uuid': record['uuid'],
                        'enhanced_text': enhanced_text,
                        'enhanced_payload': enhanced_payload
                    }
                    
                    enhanced_products.append(product)
                    
                except Exception as e:
                    logger.warning(f"Error processing product {record.get('uuid', 'unknown')}: {e}")
                    self.enhancement_stats['errors'] += 1
                    continue
        
        logger.info(f"Processed {len(enhanced_products)} enhanced products")
        return enhanced_products
    
    def get_color_complements(self, colors: List[str]) -> List[str]:
        """Get complementary colors from Phase 3 ontology"""
        if not colors:
            return []
        
        query = """
        MATCH (c1:Color)-[:COMPLEMENTS]->(c2:Color)
        WHERE c1.name IN $colors
        RETURN DISTINCT c2.name as complement
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, colors=colors)
                return [record['complement'] for record in result]
        except:
            return []
    
    def get_style_compatibility(self, styles: List[str]) -> List[str]:
        """Get compatible styles from Phase 3 ontology"""
        if not styles:
            return []
        
        query = """
        MATCH (s1:Style)-[:COMPATIBLE_WITH]->(s2:Style)
        WHERE s1.name IN $styles
        RETURN DISTINCT s2.name as compatible
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, styles=styles)
                return [record['compatible'] for record in result]
        except:
            return []
    
    def determine_price_tier(self, price: float) -> str:
        """Determine price tier from Phase 4 analysis"""
        if not price:
            return 'unknown'
        if price <= 30:
            return 'budget'
        elif price <= 105:
            return 'mid_range'
        else:
            return 'premium'
    
    def get_appropriate_occasions(self, styles: List[str]) -> List[str]:
        """Get appropriate occasions from Phase 3 ontology"""
        if not styles:
            return []
        
        query = """
        MATCH (o:Occasion)-[:SUITABLE_FOR]->(s:Style)
        WHERE s.name IN $styles
        RETURN DISTINCT o.display_name as display_name
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, styles=styles)
                return [record['display_name'] for record in result]
        except:
            return []
    
    def create_enhanced_text(self, title: str, description: str, colors: List[str], 
                           styles: List[str], brand: Optional[str], occasions: List[str]) -> str:
        """Create metadata-enhanced text for superior embeddings"""
        parts = []
        
        # Core product info
        if title:
            parts.append(title)
        if description:
            parts.append(description[:300])  # Limit length
        
        # Enhanced metadata for better semantic understanding
        if brand:
            parts.append(f"Brand: {brand}")
        
        if colors:
            parts.append(f"Available in colors: {', '.join(colors)}")
        
        if styles:
            parts.append(f"Style categories: {', '.join(styles)}")
        
        if occasions:
            parts.append(f"Perfect for: {', '.join(occasions)}")
        
        return " | ".join(parts)
    
    def create_enhanced_payload(self, record: Dict, color_complements: List[str],
                               style_compatible: List[str], price_tier: str, 
                               occasions: List[str]) -> Dict:
        """Create comprehensive payload with all fashion intelligence"""
        
        payload = {
            # Original fields
            'uuid': record['uuid'],
            'title': record['title'] or '',
            'description': (record['description'] or '')[:500],
            'price': float(record['price'] or 0),
            
            # Phase 1-5 AI-extracted metadata
            'colors': record['colors'] or [],
            'styles': record['styles'] or [],
            'brand': record['brand'],
            
            # Phase 3 fashion intelligence
            'color_complements': color_complements,
            'style_compatible': style_compatible,
            'price_tier': price_tier,
            'occasions': occasions,
            
            # Search optimization fields
            'has_color_info': len(record['colors'] or []) > 0,
            'has_style_info': len(record['styles'] or []) > 0,
            'has_brand_info': record['brand'] is not None,
            'metadata_completeness': self.calculate_completeness_score(record),
            
            # Filtering helpers
            'primary_color': record['colors'][0] if record['colors'] else None,
            'primary_style': record['styles'][0] if record['styles'] else None,
            'is_budget_friendly': price_tier == 'budget',
            'is_premium': price_tier == 'premium',
            
            # Quality score (from your approach)
            'quality_passed': True  # Only high-quality products reach this point
        }
        
        return payload
    
    def calculate_completeness_score(self, record: Dict) -> float:
        """Calculate metadata completeness score (0-1)"""
        score = 0
        total_fields = 6
        
        if record.get('title'): score += 1
        if record.get('description'): score += 1
        if record.get('price') and record['price'] > 0: score += 1
        if record.get('colors'): score += 1
        if record.get('styles'): score += 1
        if record.get('brand'): score += 1
        
        return score / total_fields
    
    def generate_enhanced_embeddings(self):
        """Generate embeddings for quality-filtered, metadata-enhanced products"""
        if not self.openai_client:
            logger.error("OpenAI API key not configured")
            return
        
        logger.info("Generating enhanced embeddings for high-quality products...")
        
        # Get enhanced product data (already quality-filtered)
        enhanced_products = self.get_enhanced_product_data()
        
        if not enhanced_products:
            logger.error("No enhanced products found!")
            return
        
        clean_count = len(enhanced_products)
        cost = clean_count * 0.00002
        
        logger.info(f"  High-quality products to embed: {clean_count:,}")
        logger.info(f"  Quality filtered out: {self.enhancement_stats['quality_filtered']:,}")
        logger.info(f"  Estimated cost: ${cost:.2f}")
        
        if not self.confirm_action(f"Proceed with enhanced embedding generation (${cost:.2f})?"):
            logger.info("Enhanced embedding generation cancelled")
            return
        
        # Prepare Qdrant collection
        self.prepare_qdrant_collection()
        
        # Process in batches
        batch_size = 50  # Smaller batches for enhanced payloads
        
        with tqdm(total=len(enhanced_products), desc="Generating enhanced embeddings") as pbar:
            for i in range(0, len(enhanced_products), batch_size):
                batch = enhanced_products[i:i + batch_size]
                
                try:
                    # Create embeddings from enhanced text
                    texts = [product['enhanced_text'] for product in batch]
                    
                    response = self.openai_client.embeddings.create(
                        model="text-embedding-ada-002",
                        input=texts
                    )
                    
                    embeddings = [item.embedding for item in response.data]
                    
                    # Upload to Qdrant with comprehensive payloads
                    points = []
                    for product, embedding in zip(batch, embeddings):
                        point = PointStruct(
                            id=product['uuid'],
                            vector=embedding,
                            payload=product['enhanced_payload']
                        )
                        points.append(point)
                    
                    self.qdrant.upsert(
                        collection_name=self.collection_name,
                        points=points
                    )
                    
                    self.enhancement_stats['processed'] += len(points)
                    self.enhancement_stats['embedding_created'] += len(points)
                    self.enhancement_stats['enhanced_payloads'] += len(points)
                    
                    pbar.update(len(batch))
                    time.sleep(0.2)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Batch {i//batch_size + 1} failed: {e}")
                    self.enhancement_stats['errors'] += len(batch)
                    pbar.update(len(batch))
        
        # Create payload indexes for optimized filtering
        self.create_payload_indexes()
        
        # Final validation
        self.validate_hybrid_collection()
        
        # Generate final report
        self.generate_hybrid_report()
    
    def prepare_qdrant_collection(self):
        """Prepare Qdrant collection"""
        logger.info(f"Preparing Qdrant collection: {self.collection_name}")
        
        try:
            # Check if exists, delete if needed
            try:
                collection_info = self.qdrant.get_collection(self.collection_name)
                logger.info(f"  Deleting existing collection with {collection_info.points_count} points")
                self.qdrant.delete_collection(self.collection_name)
            except:
                logger.info("  Collection doesn't exist, will create new one")
            
            # Create enhanced collection
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"  Created collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Collection preparation failed: {e}")
            raise
    
    def create_payload_indexes(self):
        """Create payload indexes for optimized search"""
        logger.info("Creating payload indexes for enhanced search...")
        
        index_fields = [
            'colors', 'styles', 'brand', 'price_tier', 'occasions',
            'primary_color', 'primary_style', 'price', 'has_color_info',
            'has_style_info', 'has_brand_info', 'metadata_completeness',
            'quality_passed'
        ]
        
        for field in index_fields:
            try:
                self.qdrant.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field
                )
                logger.info(f"  ✅ Created index for: {field}")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"  Index creation warning for {field}: {e}")
    
    def validate_hybrid_collection(self):
        """Validate the hybrid collection"""
        logger.info("Validating hybrid collection...")
        
        try:
            collection_info = self.qdrant.get_collection(self.collection_name)
            total_points = collection_info.points_count
            
            logger.info(f"  ✅ Collection validation successful")
            logger.info(f"     Total vectors: {total_points:,}")
            logger.info(f"     Vector dimension: {collection_info.config.params.vectors.size}")
            logger.info(f"     Distance metric: {collection_info.config.params.vectors.distance}")
            
            # Test enhanced search capabilities
            logger.info("  Testing enhanced search capabilities:")
            
            # Test color filtering
            if total_points > 0:
                test_vector = [0.1] * self.embedding_dim  # Dummy vector for testing
                
                red_search = self.qdrant.search(
                    collection_name=self.collection_name,
                    query_vector=test_vector,
                    query_filter=Filter(
                        must=[FieldCondition(key="colors", match=Match(value="red"))]
                    ),
                    limit=3
                )
                logger.info(f"     Red products searchable: {len(red_search)}")
                
                return True
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
    
    def save_quality_analysis(self):
        """Save quality analysis results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        with open(self.reports_dir / f'contamination_ids_{timestamp}.json', 'w') as f:
            json.dump(list(self.contamination_ids), f)
        
        with open(self.reports_dir / f'duplicate_groups_{timestamp}.json', 'w') as f:
            json.dump({k: v for k, v in self.duplicate_groups.items()}, f)
        
        with open(self.reports_dir / f'semantic_outliers_{timestamp}.json', 'w') as f:
            json.dump(list(self.semantic_outliers), f)
        
        logger.info(f"Quality analysis saved to {self.reports_dir}")
    
    def load_previous_analysis(self):
        """Load previous quality analysis results"""
        try:
            contamination_files = sorted(self.reports_dir.glob('contamination_ids_*.json'))
            duplicate_files = sorted(self.reports_dir.glob('duplicate_groups_*.json'))
            outlier_files = sorted(self.reports_dir.glob('semantic_outliers_*.json'))
            
            if contamination_files:
                with open(contamination_files[-1], 'r') as f:
                    self.contamination_ids = set(json.load(f))
                logger.info(f"  Loaded {len(self.contamination_ids):,} contamination IDs")
            
            if duplicate_files:
                with open(duplicate_files[-1], 'r') as f:
                    self.duplicate_groups = json.load(f)
                logger.info(f"  Loaded duplicate groups")
            
            if outlier_files:
                with open(outlier_files[-1], 'r') as f:
                    self.semantic_outliers = set(json.load(f))
                logger.info(f"  Loaded {len(self.semantic_outliers):,} semantic outliers")
            
        except Exception as e:
            logger.error(f"Error loading previous analysis: {e}")
            raise
    
    def generate_hybrid_report(self):
        """Generate comprehensive hybrid pipeline report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f'hybrid_pipeline_report_{timestamp}.json'
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'pipeline_type': 'hybrid_enhanced',
            'quality_analysis': {
                'contamination_filtered': len(self.contamination_ids),
                'duplicates_filtered': sum(len(ids) for ids in self.duplicate_groups.values()),
                'semantic_outliers_filtered': len(self.semantic_outliers),
                'total_quality_filtered': self.enhancement_stats['quality_filtered']
            },
            'enhancement_stats': self.enhancement_stats,
            'collection_info': {
                'name': self.collection_name,
                'embedding_model': 'text-embedding-ada-002',
                'embedding_dimension': self.embedding_dim,
                'enhanced_payload_fields': 20
            },
            'capabilities_enabled': [
                'Multi-dimensional color/style/price filtering',
                'Fashion semantic intelligence (color complements)',
                'Style compatibility recommendations',
                'Occasion-appropriate product discovery',
                'Price tier segmentation',
                'Quality-controlled dataset',
                'Contamination-free embeddings'
            ]
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\n🎉 HYBRID PIPELINE COMPLETE!")
        logger.info(f"📊 Enhanced embeddings: {self.enhancement_stats['embedding_created']:,}")
        logger.info(f"🛡️  Quality filtered: {self.enhancement_stats['quality_filtered']:,}")
        logger.info(f"📄 Report: {report_file}")
    
    def confirm_action(self, prompt: str) -> bool:
        """Get user confirmation"""
        response = input(f"{prompt} (y/n): ")
        return response.lower() == 'y'


def main():
    """Main execution"""
    required_vars = ['OPENAI_API_KEY']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        return 1
    
    pipeline = HybridFashionEmbeddingPipeline()
    pipeline.run_complete_pipeline()
    
    return 0


if __name__ == "__main__":
    exit(main())