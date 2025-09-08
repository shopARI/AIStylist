#!/usr/bin/env python3
"""
Enhanced Qdrant Embedding Script - Simplified Version
Uses OpenAI embeddings with full metadata integration
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, 
    Match, PayloadSchemaType, CreateCollection
)
import openai
import numpy as np

@dataclass
class EnhancedProductData:
    """Enhanced product data structure with all extracted metadata"""
    uuid: str
    title: str
    description: str
    price: float
    
    # AI-extracted metadata
    colors: List[str]
    styles: List[str] 
    brand: Optional[str]
    
    # Computed metadata
    color_complements: List[str]
    style_compatible: List[str]
    price_tier: str
    occasions: List[str]
    
    # Search optimization
    text_for_embedding: str
    enhanced_payload: Dict[str, Any]

class SimpleEnhancedQdrantEmbedder:
    def __init__(self, collection_name: str = "fashion_products_enhanced"):
        """Initialize with enhanced embedding capabilities"""
        
        # Load environment variables
        self.load_environment()
        
        # Initialize clients
        self.neo4j_driver = GraphDatabase.driver(
            'bolt://34.135.40.119:7687',
            auth=('neo4j', 'shopari1234')
        )
        self.database = 'productionbackup2'
        
        self.qdrant_client = QdrantClient(
            host=self.qdrant_host,
            port=self.qdrant_port,
            api_key=self.qdrant_api_key
        )
        
        # Initialize OpenAI
        openai.api_key = self.openai_api_key
        self.embedding_model = "text-embedding-ada-002"
        self.embedding_dimension = 1536  # Ada-002 dimension
        
        self.collection_name = collection_name
        self.batch_size = 50  # Smaller batches for OpenAI API
        self.enhancement_stats = {
            'processed': 0,
            'enhanced_payloads': 0,
            'embedding_created': 0,
            'errors': 0
        }
    
    def load_environment(self):
        """Load environment variables"""
        # Try to load from .env file
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"\'')
        except FileNotFoundError:
            print("⚠️  No .env file found, using environment variables")
        
        # Set connection parameters
        self.qdrant_host = os.getenv('QDRANT_HOST', 'localhost')
        self.qdrant_port = int(os.getenv('QDRANT_PORT', 6333))
        self.qdrant_api_key = os.getenv('QDRANT_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for embeddings")
        
        print(f"🔗 Qdrant: {self.qdrant_host}:{self.qdrant_port}")
        print(f"🔗 OpenAI: Using {self.embedding_model}")
    
    def clear_existing_collection(self):
        """Clear existing collection and create enhanced version"""
        print(f"🗑️  Managing collection: {self.collection_name}")
        
        try:
            # Check if collection exists
            try:
                collection_info = self.qdrant_client.get_collection(self.collection_name)
                print(f"🗑️  Deleting existing collection with {collection_info.points_count} points")
                self.qdrant_client.delete_collection(self.collection_name)
            except:
                print("📝 Collection doesn't exist, will create new one")
            
            # Create new enhanced collection
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dimension,
                    distance=Distance.COSINE
                )
            )
            print(f"✅ Created enhanced collection: {self.collection_name}")
            
        except Exception as e:
            print(f"❌ Error managing collection: {e}")
            raise
    
    def get_enhanced_product_data(self, limit: Optional[int] = None) -> List[EnhancedProductData]:
        """Fetch products with all enhanced metadata from Neo4j"""
        print("📊 Fetching enhanced product data from Neo4j...")
        
        query = """
        MATCH (p:Product)
        OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)
        OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)
        OPTIONAL MATCH (p)-[:MADE_BY]->(b:Brand)
        
        WITH p, 
             collect(DISTINCT c.name) as colors,
             collect(DISTINCT s.name) as styles,
             b.name as brand
        
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
        
        with self.neo4j_driver.session(database=self.database) as session:
            result = session.run(query)
            
            for record in result:
                try:
                    # Get color complements
                    color_complements = self.get_color_complements(record['colors'])
                    
                    # Get style compatibility
                    style_compatible = self.get_style_compatibility(record['styles'])
                    
                    # Determine price tier
                    price_tier = self.determine_price_tier(record['price'])
                    
                    # Get appropriate occasions
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
                    
                    # Create enhanced payload
                    enhanced_payload = self.create_enhanced_payload(
                        record, color_complements, style_compatible, 
                        price_tier, occasions
                    )
                    
                    product = EnhancedProductData(
                        uuid=record['uuid'],
                        title=record['title'] or '',
                        description=record['description'] or '',
                        price=float(record['price'] or 0),
                        colors=record['colors'] or [],
                        styles=record['styles'] or [],
                        brand=record['brand'],
                        color_complements=color_complements,
                        style_compatible=style_compatible,
                        price_tier=price_tier,
                        occasions=occasions,
                        text_for_embedding=enhanced_text,
                        enhanced_payload=enhanced_payload
                    )
                    
                    enhanced_products.append(product)
                    
                except Exception as e:
                    print(f"⚠️  Error processing product {record.get('uuid', 'unknown')}: {e}")
                    self.enhancement_stats['errors'] += 1
                    continue
        
        print(f"📊 Fetched {len(enhanced_products)} enhanced products")
        return enhanced_products
    
    def get_color_complements(self, colors: List[str]) -> List[str]:
        """Get complementary colors from the knowledge graph"""
        if not colors:
            return []
        
        complements = []
        query = """
        MATCH (c1:Color)-[:COMPLEMENTS]->(c2:Color)
        WHERE c1.name IN $colors
        RETURN DISTINCT c2.name as complement
        """
        
        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(query, colors=colors)
                complements = [record['complement'] for record in result]
        except:
            pass
        
        return complements
    
    def get_style_compatibility(self, styles: List[str]) -> List[str]:
        """Get compatible styles from the knowledge graph"""
        if not styles:
            return []
        
        compatible = []
        query = """
        MATCH (s1:Style)-[:COMPATIBLE_WITH]->(s2:Style)
        WHERE s1.name IN $styles
        RETURN DISTINCT s2.name as compatible
        """
        
        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(query, styles=styles)
                compatible = [record['compatible'] for record in result]
        except:
            pass
        
        return compatible
    
    def determine_price_tier(self, price: float) -> str:
        """Determine price tier"""
        if price <= 30:
            return 'budget'
        elif price <= 105:
            return 'mid_range'
        else:
            return 'premium'
    
    def get_appropriate_occasions(self, styles: List[str]) -> List[str]:
        """Get appropriate occasions based on styles"""
        if not styles:
            return []
        
        occasions = []
        query = """
        MATCH (o:Occasion)-[:SUITABLE_FOR]->(s:Style)
        WHERE s.name IN $styles
        RETURN DISTINCT o.display_name as display_name
        """
        
        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(query, styles=styles)
                occasions = [record['display_name'] for record in result]
        except:
            pass
        
        return occasions
    
    def create_enhanced_text(self, title: str, description: str, colors: List[str], 
                           styles: List[str], brand: Optional[str], occasions: List[str]) -> str:
        """Create enhanced text for better embedding"""
        parts = []
        
        # Core product info
        if title:
            parts.append(title)
        if description:
            parts.append(description[:200])  # Limit description length
        
        # Enhanced metadata
        if brand:
            parts.append(f"Brand: {brand}")
        
        if colors:
            parts.append(f"Colors: {', '.join(colors)}")
        
        if styles:
            parts.append(f"Styles: {', '.join(styles)}")
        
        if occasions:
            parts.append(f"Occasions: {', '.join(occasions)}")
        
        return " | ".join(parts)
    
    def create_enhanced_payload(self, record: Dict, color_complements: List[str],
                               style_compatible: List[str], price_tier: str, 
                               occasions: List[str]) -> Dict[str, Any]:
        """Create comprehensive payload with all metadata"""
        
        payload = {
            # Original fields
            'uuid': record['uuid'],
            'title': record['title'] or '',
            'description': (record['description'] or '')[:500],  # Limit length
            'price': float(record['price'] or 0),
            
            # AI-extracted metadata
            'colors': record['colors'] or [],
            'styles': record['styles'] or [],
            'brand': record['brand'],
            
            # Enhanced semantic metadata
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
            'is_premium': price_tier == 'premium'
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
    
    def create_embeddings_batch(self, products: List[EnhancedProductData]) -> List[List[float]]:
        """Create embeddings for a batch of products using OpenAI"""
        texts = [product.text_for_embedding for product in products]
        
        try:
            response = openai.Embedding.create(
                input=texts,
                model=self.embedding_model
            )
            embeddings = [item['embedding'] for item in response['data']]
            return embeddings
        except Exception as e:
            print(f"❌ OpenAI embedding error: {e}")
            # Return zero vectors as fallback
            return [[0.0] * self.embedding_dimension for _ in texts]
    
    def upload_enhanced_embeddings(self, products: List[EnhancedProductData]):
        """Upload enhanced embeddings to Qdrant"""
        print(f"🚀 Uploading {len(products)} enhanced embeddings...")
        
        # Process in batches
        for i in range(0, len(products), self.batch_size):
            batch = products[i:i + self.batch_size]
            
            try:
                # Create embeddings for batch
                embeddings = self.create_embeddings_batch(batch)
                
                # Create points for upload
                points = []
                for product, embedding in zip(batch, embeddings):
                    point = PointStruct(
                        id=product.uuid,
                        vector=embedding,
                        payload=product.enhanced_payload
                    )
                    points.append(point)
                
                # Upload to Qdrant
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                
                self.enhancement_stats['processed'] += len(batch)
                self.enhancement_stats['embedding_created'] += len(batch)
                self.enhancement_stats['enhanced_payloads'] += len(batch)
                
                print(f"   ✅ Uploaded batch {i//self.batch_size + 1}: {len(batch)} products")
                time.sleep(1)  # Rate limiting for OpenAI
                
            except Exception as e:
                print(f"   ❌ Batch {i//self.batch_size + 1} failed: {e}")
                self.enhancement_stats['errors'] += len(batch)
    
    def validate_enhanced_embeddings(self):
        """Validate the enhanced embedding collection"""
        print("✅ Validating enhanced embeddings...")
        
        try:
            # Get collection info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            total_points = collection_info.points_count
            
            print(f"📊 Collection Status:")
            print(f"   Total points: {total_points:,}")
            print(f"   Vector size: {collection_info.config.params.vectors.size}")
            
            # Test sample point retrieval
            if total_points > 0:
                points = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    limit=3,
                    with_payload=True
                )[0]
                
                print(f"📊 Sample payload keys: {list(points[0].payload.keys()) if points else 'None'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            return False
    
    def run_complete_enhancement(self, limit: Optional[int] = None):
        """Run complete embedding enhancement process"""
        print("🚀 STARTING ENHANCED QDRANT EMBEDDING PROCESS")
        print("=" * 60)
        
        start_time = time.time()
        
        try:
            # Step 1: Clear existing collection and create enhanced version
            self.clear_existing_collection()
            
            # Step 2: Fetch enhanced product data from Neo4j
            enhanced_products = self.get_enhanced_product_data(limit)
            
            if not enhanced_products:
                print("❌ No products found to process!")
                return
            
            # Step 3: Create and upload enhanced embeddings
            self.upload_enhanced_embeddings(enhanced_products)
            
            # Step 4: Validate enhanced embeddings
            validation_success = self.validate_enhanced_embeddings()
            
            elapsed_time = time.time() - start_time
            
            print(f"\n🎉 ENHANCED QDRANT EMBEDDING PROCESS COMPLETE!")
            print(f"⏱️  Total execution time: {elapsed_time:.2f} seconds")
            print(f"📊 Processed: {self.enhancement_stats['processed']:,} products")
            print(f"🧠 Created: {self.enhancement_stats['embedding_created']:,} enhanced embeddings")
            print(f"❌ Errors: {self.enhancement_stats['errors']}")
            
            if validation_success:
                print(f"✅ Enhanced Qdrant collection ready for production!")
            else:
                print(f"⚠️  Validation had issues - check logs")
                
        except Exception as e:
            print(f"❌ Enhancement process failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.neo4j_driver.close()

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Qdrant Embedding with Fashion Metadata')
    parser.add_argument('--limit', type=int, help='Limit number of products to process (for testing)')
    parser.add_argument('--collection', default='fashion_products_enhanced', help='Qdrant collection name')
    
    args = parser.parse_args()
    
    embedder = SimpleEnhancedQdrantEmbedder(collection_name=args.collection)
    embedder.run_complete_enhancement(limit=args.limit)

if __name__ == "__main__":
    main()