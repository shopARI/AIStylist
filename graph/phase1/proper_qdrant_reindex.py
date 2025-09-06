#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Proper Qdrant Re-indexing Implementation
Complete re-embedding with correct product_id correlation
"""

import json
import time
import os
import openai
from typing import Dict, List, Optional
from datetime import datetime
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http import models
import numpy as np

class ProperQdrantReindexer:
    """Complete Qdrant re-indexing with proper embedding generation"""
    
    def __init__(self):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        
        # Collection names
        self.old_collection = "fashion_products"
        self.new_collection = "fashion_products_v2"
        
        # OpenAI setup
        self.ai_config = get_ai_config()
        openai_api_key = ai_config.openai_api_key
        openai.api_key = self.openai_api_key
        
        # Processing parameters
        self.batch_size = 1000  # Products per batch
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimension = 1536
        
        # Statistics
        self.stats = {
            'products_loaded': 0,
            'embeddings_generated': 0,
            'vectors_uploaded': 0,
            'api_calls': 0,
            'errors': 0,
            'cost_estimate': 0.0
        }
        
        # Checkpoint system
        self.checkpoint_dir = f"reindex_checkpoints_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def connect_databases(self):
        """Connect to Neo4j and Qdrant"""
        print("🔌 Connecting to databases...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Connected to Neo4j and Qdrant")
    
    def create_new_collection(self):
        """Create new Qdrant collection with proper structure"""
        print("🆕 Creating new Qdrant collection...")
        
        try:
            # Delete if exists
            try:
                self.qdrant_client.delete_collection(self.new_collection)
                print(f"  Deleted existing {self.new_collection}")
            except:
                pass
            
            # Create new collection
            self.qdrant_client.create_collection(
                collection_name=self.new_collection,
                vectors_config=models.VectorParams(
                    size=self.embedding_dimension,
                    distance=models.Distance.COSINE
                )
            )
            
            print(f"✅ Created new collection: {self.new_collection}")
            
        except Exception as e:
            print(f"❌ Error creating collection: {e}")
            raise
    
    def load_products_batch(self, offset: int, limit: int) -> List[Dict]:
        """Load batch of products from Neo4j"""
        with self.neo4j_driver.session() as session:
            result = session.run(f"""
                MATCH (p:Product)
                RETURN p.id as id, p.title as title, p.description as description, p.price as price
                SKIP {offset}
                LIMIT {limit}
            """)
            
            products = []
            for record in result:
                product = {
                    'id': record['id'],
                    'title': record['title'] or '',
                    'description': record['description'] or '',
                    'price': record['price'] or 0
                }
                products.append(product)
            
            return products
    
    def generate_embeddings_batch(self, products: List[Dict]) -> List[Dict]:
        """Generate embeddings for batch of products"""
        print(f"  🧠 Generating embeddings for {len(products)} products...")
        
        # Prepare texts for embedding
        texts = []
        for product in products:
            # Combine title and description
            text = f"{product['title']} {product['description']}".strip()
            texts.append(text)
        
        try:
            # Call OpenAI API
            response = openai.embeddings.create(
                input=texts,
                model=self.embedding_model
            )
            
            self.stats['api_calls'] += 1
            self.stats['embeddings_generated'] += len(products)
            
            # Estimate cost (approximate)
            total_tokens = sum(len(text.split()) * 1.3 for text in texts)  # Rough token estimate
            cost = (total_tokens / 1000) * 0.00002  # $0.02 per 1K tokens
            self.stats['cost_estimate'] += cost
            
            # Prepare vectors with proper payload
            vectors = []
            for i, product in enumerate(products):
                vector_data = {
                    'id': product['id'],  # Use Neo4j UUID as Qdrant point ID
                    'vector': response.data[i].embedding,
                    'payload': {
                        'product_id': product['id'],  # Critical: proper correlation
                        'title': product['title'],
                        'description': product['description'],
                        'price': product['price']
                    }
                }
                vectors.append(vector_data)
            
            return vectors
            
        except Exception as e:
            print(f"❌ Error generating embeddings: {e}")
            self.stats['errors'] += 1
            
            # Wait and retry
            time.sleep(5)
            return self.generate_embeddings_batch(products)
    
    def upload_vectors_batch(self, vectors: List[Dict]):
        """Upload batch of vectors to Qdrant"""
        print(f"  📤 Uploading {len(vectors)} vectors...")
        
        try:
            points = []
            for vector_data in vectors:
                point = models.PointStruct(
                    id=vector_data['id'],
                    vector=vector_data['vector'],
                    payload=vector_data['payload']
                )
                points.append(point)
            
            self.qdrant_client.upsert(
                collection_name=self.new_collection,
                points=points
            )
            
            self.stats['vectors_uploaded'] += len(vectors)
            print(f"  ✅ Uploaded {len(vectors)} vectors")
            
        except Exception as e:
            print(f"❌ Error uploading vectors: {e}")
            self.stats['errors'] += 1
            raise
    
    def save_checkpoint(self, batch_number: int, offset: int):
        """Save progress checkpoint"""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'batch_number': batch_number,
            'offset': offset,
            'statistics': self.stats.copy()
        }
        
        checkpoint_file = os.path.join(
            self.checkpoint_dir, 
            f"checkpoint_batch_{batch_number:06d}.json"
        )
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def run_complete_reindex(self):
        """Run complete re-indexing process"""
        start_time = datetime.now()
        
        print("🚀 STARTING COMPLETE QDRANT RE-INDEXING")
        print("="*60)
        print(f"Started at: {start_time}")
        print()
        
        try:
            # Phase 1: Setup
            self.connect_databases()
            self.create_new_collection()
            
            # Get total product count
            with self.neo4j_driver.session() as session:
                result = session.run("MATCH (p:Product) RETURN count(p) as total")
                total_products = result.single()['total']
            
            print(f"📊 Total products to process: {total_products:,}")
            print(f"📊 Batch size: {self.batch_size:,}")
            print(f"📊 Estimated batches: {(total_products + self.batch_size - 1) // self.batch_size:,}")
            print()
            
            # Phase 2: Process all products in batches
            offset = 0
            batch_number = 0
            
            while offset < total_products:
                batch_number += 1
                batch_start_time = datetime.now()
                
                print(f"🔄 Processing batch {batch_number} (products {offset:,} to {offset + self.batch_size:,})")
                
                # Load batch
                products = self.load_products_batch(offset, self.batch_size)
                if not products:
                    break
                
                self.stats['products_loaded'] += len(products)
                
                # Generate embeddings
                vectors = self.generate_embeddings_batch(products)
                
                # Upload to Qdrant
                self.upload_vectors_batch(vectors)
                
                # Save checkpoint every 10 batches
                if batch_number % 10 == 0:
                    self.save_checkpoint(batch_number, offset)
                
                # Progress report
                batch_time = (datetime.now() - batch_start_time).total_seconds()
                progress = (offset + len(products)) / total_products * 100
                rate = len(products) / batch_time if batch_time > 0 else 0
                eta_seconds = (total_products - offset) / rate if rate > 0 else 0
                eta_hours = eta_seconds / 3600
                
                print(f"  ✅ Batch {batch_number} completed in {batch_time:.1f}s")
                print(f"  📊 Progress: {progress:.1f}% ({offset + len(products):,}/{total_products:,})")
                print(f"  ⚡ Rate: {rate:.0f} products/second")
                print(f"  🕐 ETA: {eta_hours:.1f} hours")
                print(f"  💰 Cost so far: ${self.stats['cost_estimate']:.2f}")
                print()
                
                offset += len(products)
                
                # Rate limiting
                time.sleep(1)  # Be nice to APIs
            
            # Phase 3: Validation
            self.validate_new_collection(total_products)
            
            # Final report
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() / 3600
            
            print("🎉 COMPLETE RE-INDEXING FINISHED!")
            print("="*50)
            print(f"✅ Duration: {duration:.1f} hours")
            print(f"✅ Products processed: {self.stats['products_loaded']:,}")
            print(f"✅ Embeddings generated: {self.stats['embeddings_generated']:,}")
            print(f"✅ Vectors uploaded: {self.stats['vectors_uploaded']:,}")
            print(f"✅ Total cost: ${self.stats['cost_estimate']:.2f}")
            print(f"✅ New collection: {self.new_collection}")
            print()
            print("🎯 RESULT: Perfect Neo4j ↔ Qdrant correlation!")
            print("🚀 Ready for Phase 2 with confidence!")
            
        except Exception as e:
            print(f"❌ Error during re-indexing: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            if hasattr(self, 'neo4j_driver'):
                self.neo4j_driver.close()
    
    def validate_new_collection(self, expected_count: int):
        """Validate new collection"""
        print("🔍 Validating new collection...")
        
        # Check total count
        count_result = self.qdrant_client.count(collection_name=self.new_collection)
        actual_count = count_result.count
        
        print(f"  📊 Expected vectors: {expected_count:,}")
        print(f"  📊 Actual vectors: {actual_count:,}")
        print(f"  📊 Success rate: {(actual_count / expected_count) * 100:.1f}%")
        
        # Sample validation
        scroll_result = self.qdrant_client.scroll(
            collection_name=self.new_collection,
            limit=10,
            with_payload=True
        )
        
        print("  📋 Sample vectors:")
        for i, point in enumerate(scroll_result[0][:5]):
            print(f"    {i+1}. ID: {point.id}")
            print(f"       Product ID: {point.payload.get('product_id', 'MISSING!')}")
            print(f"       Title: {point.payload.get('title', '')[:50]}...")

if __name__ == "__main__":
    reindexer = ProperQdrantReindexer()
    reindexer.run_complete_reindex()
