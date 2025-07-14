"""
Product Migration Script from Neo4j to Qdrant
Migrates all product data from Neo4j to Qdrant for the vector migration project.
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("product_migration")

# Import required modules
from neo4j_integration_async import ProductKnowledgeGraphAsync
from product_retriever_async_enhanced import ProductRetrieverAsync


class ProductMigrator:
    """Handles migration of products from Neo4j to Qdrant"""
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None,
                 qdrant_url=None, qdrant_api_key=None, qdrant_collection=None):
        """Initialize the migrator with database connections"""
        
        # Neo4j configuration
        self.neo4j_url = neo4j_url or os.environ.get("NEO4J_URL", "bolt://localhost:7687")
        self.neo4j_username = neo4j_username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "password")
        
        # Qdrant configuration
        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")
        self.qdrant_collection = qdrant_collection or os.environ.get("QDRANT_COLLECTION", "products")
        
        # Initialize connections
        self.neo4j = None
        self.qdrant = None
        
        # Migration statistics
        self.stats = {
            "total_products": 0,
            "migrated": 0,
            "failed": 0,
            "start_time": None,
            "end_time": None,
            "errors": []
        }
    
    async def initialize(self):
        """Initialize database connections"""
        logger.info("Initializing database connections...")
        
        # Initialize Neo4j
        self.neo4j = ProductKnowledgeGraphAsync(
            url=self.neo4j_url,
            username=self.neo4j_username,
            password=self.neo4j_password
        )
        logger.info(f"Connected to Neo4j at {self.neo4j_url}")
        
        # Initialize Qdrant
        self.qdrant = ProductRetrieverAsync(
            qdrant_url=self.qdrant_url,
            qdrant_api_key=self.qdrant_api_key,
            collection_name=self.qdrant_collection
        )
        logger.info(f"Connected to Qdrant at {self.qdrant_url}")
    
    async def get_product_count(self) -> int:
        """Get total number of products in Neo4j"""
        try:
            query = "MATCH (p:Product) RETURN count(p) as count"
            result = await self.neo4j.query(query)
            
            if result:
                return result[0]["count"]
            return 0
            
        except Exception as e:
            logger.error(f"Error getting product count: {e}")
            return 0
    
    async def extract_products_batch(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Extract a batch of products from Neo4j"""
        try:
            query = """
            MATCH (p:Product)
            WITH p
            ORDER BY p.id
            SKIP $skip
            LIMIT $limit
            OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (p)-[:TAGGED_WITH]->(t:Tag)
            OPTIONAL MATCH (p)-[:IN_COLLECTION]->(col:Collection)
            WITH p, 
                 collect(DISTINCT c.title) as categories,
                 collect(DISTINCT t.title) as tags,
                 collect(DISTINCT col.title) as collections
            RETURN 
                p.id as id,
                p.title as title,
                p.description as description,
                p.price as price,
                p.images as images,
                p.created_at as created_at,
                p.updated_at as updated_at,
                p.visited_num as visited_num,
                p.brand as brand,
                p.materials as materials,
                p.sizes as sizes,
                p.colors as colors,
                p.in_stock as in_stock,
                p.return_rate as return_rate,
                p.popularity_score as popularity_score,
                categories,
                tags,
                collections
            """
            
            result = await self.neo4j.query(query, {"skip": skip, "limit": limit})
            
            # Process results
            products = []
            for record in result:
                product = {
                    "id": record.get("id", str(uuid.uuid4())),
                    "title": record.get("title", ""),
                    "description": record.get("description", ""),
                    "price": float(record.get("price", 0)),
                    "categories": record.get("categories", []),
                    "tags": record.get("tags", []),
                    "collections": record.get("collections", []),
                    "images": self._parse_images(record.get("images", "[]")),
                    "brand": record.get("brand", ""),
                    "materials": self._parse_list(record.get("materials", "[]")),
                    "sizes": self._parse_list(record.get("sizes", "[]")),
                    "colors": self._parse_list(record.get("colors", "[]")),
                    "created_at": record.get("created_at", datetime.now().isoformat()),
                    "updated_at": record.get("updated_at", datetime.now().isoformat()),
                    "visited_num": int(record.get("visited_num", 0)),
                    "in_stock": bool(record.get("in_stock", True)),
                    "return_rate": float(record.get("return_rate", 0)),
                    "popularity_score": float(record.get("popularity_score", 0))
                }
                products.append(product)
            
            logger.info(f"Extracted {len(products)} products (skip={skip}, limit={limit})")
            return products
            
        except Exception as e:
            logger.error(f"Error extracting products batch: {e}")
            return []
    
    def _parse_images(self, images_str: str) -> List[str]:
        """Parse images string to list"""
        if not images_str:
            return []
        
        try:
            if images_str.startswith('['):
                return json.loads(images_str.replace("'", '"'))
            return [images_str]
        except:
            return []
    
    def _parse_list(self, list_str: str) -> List[str]:
        """Parse list string to list"""
        if not list_str:
            return []
        
        try:
            if list_str.startswith('['):
                return json.loads(list_str.replace("'", '"'))
            return [list_str]
        except:
            return []
    
    async def migrate_batch(self, products: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Migrate a batch of products to Qdrant"""
        if not products:
            return 0, 0
        
        try:
            # Use bulk indexing
            successful, failed = await self.qdrant.bulk_index_products(products, batch_size=50)
            
            logger.info(f"Migrated batch: {successful} successful, {failed} failed")
            return successful, failed
            
        except Exception as e:
            logger.error(f"Error migrating batch: {e}")
            return 0, len(products)
    
    async def verify_migration(self, sample_size: int = 10) -> Dict[str, Any]:
        """Verify migration by checking random products"""
        verification = {
            "success": True,
            "checked": 0,
            "matched": 0,
            "mismatched": [],
            "missing": []
        }
        
        try:
            # Get random products from Neo4j
            query = """
            MATCH (p:Product)
            WITH p, rand() as r
            ORDER BY r
            LIMIT $limit
            RETURN p.id as id, p.title as title, p.price as price
            """
            
            neo4j_products = await self.neo4j.query(query, {"limit": sample_size})
            verification["checked"] = len(neo4j_products)
            
            # Check each product in Qdrant
            for product in neo4j_products:
                product_id = product["id"]
                
                # Get from Qdrant
                qdrant_product = await self.qdrant.get_product_details(product_id)
                
                if not qdrant_product:
                    verification["missing"].append(product_id)
                    verification["success"] = False
                else:
                    # Basic verification - check key fields
                    if (qdrant_product.get("title") == product["title"] and
                        abs(float(qdrant_product.get("price", 0)) - float(product["price"])) < 0.01):
                        verification["matched"] += 1
                    else:
                        verification["mismatched"].append({
                            "id": product_id,
                            "neo4j": product,
                            "qdrant": {
                                "title": qdrant_product.get("title"),
                                "price": qdrant_product.get("price")
                            }
                        })
                        verification["success"] = False
            
            logger.info(f"Verification: {verification['matched']}/{verification['checked']} matched")
            return verification
            
        except Exception as e:
            logger.error(f"Error verifying migration: {e}")
            verification["success"] = False
            verification["error"] = str(e)
            return verification
    
    async def cleanup_neo4j_products(self, dry_run: bool = True) -> int:
        """Remove product nodes from Neo4j after successful migration"""
        try:
            if dry_run:
                # Just count products that would be deleted
                query = "MATCH (p:Product) RETURN count(p) as count"
                result = await self.neo4j.query(query)
                count = result[0]["count"] if result else 0
                logger.info(f"DRY RUN: Would delete {count} products from Neo4j")
                return count
            else:
                # Actually delete products
                logger.warning("DELETING ALL PRODUCTS FROM NEO4J!")
                
                # Delete in batches to avoid memory issues
                deleted = 0
                batch_size = 1000
                
                while True:
                    query = """
                    MATCH (p:Product)
                    WITH p LIMIT $batch_size
                    DETACH DELETE p
                    RETURN count(p) as count
                    """
                    
                    result = await self.neo4j.query(query, {"batch_size": batch_size})
                    
                    if not result or result[0]["count"] == 0:
                        break
                    
                    deleted += result[0]["count"]
                    logger.info(f"Deleted {result[0]['count']} products (total: {deleted})")
                    
                    # Small delay between batches
                    await asyncio.sleep(0.1)
                
                logger.info(f"Cleanup complete: Deleted {deleted} products from Neo4j")
                return deleted
                
        except Exception as e:
            logger.error(f"Error cleaning up Neo4j products: {e}")
            return 0
    
    async def run_migration(self, batch_size: int = 100, verify: bool = True, cleanup: bool = False):
        """Run the complete migration process"""
        self.stats["start_time"] = datetime.now()
        logger.info("Starting product migration from Neo4j to Qdrant...")
        
        try:
            # Initialize connections
            await self.initialize()
            
            # Get total product count
            self.stats["total_products"] = await self.get_product_count()
            logger.info(f"Found {self.stats['total_products']} products to migrate")
            
            if self.stats["total_products"] == 0:
                logger.warning("No products found in Neo4j")
                return self.stats
            
            # Get Qdrant statistics before migration
            qdrant_stats_before = await self.qdrant.get_collection_stats()
            logger.info(f"Qdrant before migration: {qdrant_stats_before}")
            
            # Migrate in batches
            offset = 0
            
            while offset < self.stats["total_products"]:
                # Extract batch
                products = await self.extract_products_batch(offset, batch_size)
                
                if not products:
                    break
                
                # Migrate batch
                successful, failed = await self.migrate_batch(products)
                
                self.stats["migrated"] += successful
                self.stats["failed"] += failed
                
                # Log progress
                progress = (offset + len(products)) / self.stats["total_products"] * 100
                logger.info(f"Progress: {progress:.1f}% ({self.stats['migrated']} migrated, {self.stats['failed']} failed)")
                
                offset += batch_size
                
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.1)
            
            # Get Qdrant statistics after migration
            qdrant_stats_after = await self.qdrant.get_collection_stats()
            logger.info(f"Qdrant after migration: {qdrant_stats_after}")
            
            # Verify migration if requested
            if verify:
                logger.info("Verifying migration...")
                verification = await self.verify_migration(sample_size=20)
                self.stats["verification"] = verification
                
                if not verification["success"]:
                    logger.warning("Migration verification failed!")
                    logger.warning(f"Missing products: {verification['missing']}")
                    logger.warning(f"Mismatched products: {verification['mismatched']}")
            
            # Cleanup Neo4j if requested and verification passed
            if cleanup:
                if verify and not verification.get("success", False):
                    logger.error("Skipping cleanup due to failed verification")
                else:
                    logger.info("Starting Neo4j cleanup...")
                    deleted = await self.cleanup_neo4j_products(dry_run=False)
                    self.stats["neo4j_cleaned"] = deleted
            
            self.stats["end_time"] = datetime.now()
            self.stats["duration"] = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
            
            # Summary
            logger.info("=== MIGRATION SUMMARY ===")
            logger.info(f"Total products: {self.stats['total_products']}")
            logger.info(f"Successfully migrated: {self.stats['migrated']}")
            logger.info(f"Failed: {self.stats['failed']}")
            logger.info(f"Duration: {self.stats['duration']:.2f} seconds")
            
            if verify:
                logger.info(f"Verification: {'PASSED' if verification['success'] else 'FAILED'}")
            
            if cleanup and "neo4j_cleaned" in self.stats:
                logger.info(f"Neo4j products cleaned: {self.stats['neo4j_cleaned']}")
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.stats["error"] = str(e)
            self.stats["end_time"] = datetime.now()
            return self.stats
        
        finally:
            # Close connections
            if self.neo4j:
                await self.neo4j.close()
            # Qdrant client doesn't need explicit closing
            logger.info("Closed database connections")


async def main():
    """Main function to run the migration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate products from Neo4j to Qdrant")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for migration")
    parser.add_argument("--verify", action="store_true", help="Verify migration after completion")
    parser.add_argument("--cleanup", action="store_true", help="Remove products from Neo4j after migration")
    parser.add_argument("--dry-run", action="store_true", help="Run in simulation mode without actual migration")
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("=== DRY RUN MODE ===")
        
        # Just check counts
        migrator = ProductMigrator()
        await migrator.initialize()
        
        count = await migrator.get_product_count()
        logger.info(f"Would migrate {count} products")
        
        if args.cleanup:
            deleted = await migrator.cleanup_neo4j_products(dry_run=True)
        
        await migrator.neo4j.close()
    else:
        # Run actual migration
        migrator = ProductMigrator()
        stats = await migrator.run_migration(
            batch_size=args.batch_size,
            verify=args.verify,
            cleanup=args.cleanup
        )
        
        # Save stats to file
        with open("migration_stats.json", "w") as f:
            json.dump(stats, f, indent=2, default=str)
        
        logger.info(f"Migration stats saved to migration_stats.json")


if __name__ == "__main__":
    asyncio.run(main())