"""
Migration Runner Script
Orchestrates the complete migration process with safety checks
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration_runner.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("migration_runner")

# Import migration script
try:
    from migrate_products_to_qdrant import ProductMigrator
    from integration_test_suite import IntegrationTestSuite
    from user_knowledge_graph_async import UserKnowledgeGraphAsync
    from product_retriever_async_enhanced import ProductRetrieverAsync
    from hybrid_data_store import HybridDataStore
    
    logger.info("✅ All imports successful")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    logger.error("Make sure all required files are in the same directory")
    sys.exit(1)


class MigrationRunner:
    """Orchestrates the complete migration process"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.migration_stats = {
            "start_time": None,
            "end_time": None,
            "pre_migration": {},
            "post_migration": {},
            "verification": {},
            "cleanup": {}
        }
        
    async def initialize_components(self):
        """Initialize all required components"""
        logger.info("Initializing components...")
        
        self.user_kg = UserKnowledgeGraphAsync(
            url=os.environ.get("NEO4J_URL", "bolt://localhost:7687"),
            username=os.environ.get("NEO4J_USERNAME", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", "password")
        )
        
        self.product_retriever = ProductRetrieverAsync(
            qdrant_url=os.environ.get("QDRANT_URL"),
            qdrant_api_key=os.environ.get("QDRANT_API_KEY"),
            collection_name=os.environ.get("QDRANT_COLLECTION_NAME", "products")
        )
        
        self.data_store = HybridDataStore(
            neo4j_client=self.user_kg,
            qdrant_client=self.product_retriever
        )
        
        self.migrator = ProductMigrator(
            neo4j_url=os.environ.get("NEO4J_URL"),
            neo4j_username=os.environ.get("NEO4J_USERNAME"),
            neo4j_password=os.environ.get("NEO4J_PASSWORD"),
            qdrant_url=os.environ.get("QDRANT_URL"),
            qdrant_api_key=os.environ.get("QDRANT_API_KEY"),
            qdrant_collection=os.environ.get("QDRANT_COLLECTION_NAME", "products")
        )
        
        logger.info("✅ Components initialized")
    
    async def run_pre_migration_checks(self) -> bool:
        """Run comprehensive pre-migration checks"""
        logger.info("\n" + "="*50)
        logger.info("PRE-MIGRATION CHECKS")
        logger.info("="*50)
        
        checks_passed = True
        
        # 1. Run integration tests
        logger.info("\n1️⃣ Running integration tests...")
        test_suite = IntegrationTestSuite()
        test_results = await test_suite.run_all_tests()
        
        if test_results['failed'] > 0:
            logger.error("❌ Integration tests failed")
            checks_passed = False
        else:
            logger.info("✅ Integration tests passed")
        
        # 2. Check Neo4j product count
        logger.info("\n2️⃣ Checking Neo4j product count...")
        neo4j_stats = await self.get_neo4j_stats()
        self.migration_stats["pre_migration"]["neo4j"] = neo4j_stats
        
        product_count = neo4j_stats.get('product_count', 0)
        logger.info(f"Found {product_count} products in Neo4j")
        
        if product_count == 0:
            logger.warning("⚠️  No products found in Neo4j - nothing to migrate")
            return False
        
        # 3. Check Qdrant status
        logger.info("\n3️⃣ Checking Qdrant status...")
        qdrant_stats = await self.product_retriever.get_collection_stats()
        self.migration_stats["pre_migration"]["qdrant"] = qdrant_stats
        
        existing_vectors = qdrant_stats.get('vectors_count', 0)
        logger.info(f"Found {existing_vectors} existing vectors in Qdrant")
        
        if existing_vectors > 0:
            logger.warning(f"⚠️  Qdrant already contains {existing_vectors} vectors")
            response = input("Continue and overwrite? (y/N): ")
            if response.lower() != 'y':
                logger.info("Migration cancelled by user")
                return False
        
        # 4. Test sample product operations
        logger.info("\n4️⃣ Testing sample product operations...")
        sample_products = await self.test_sample_operations()
        
        if not sample_products:
            logger.error("❌ Sample product operations failed")
            checks_passed = False
        else:
            logger.info("✅ Sample operations successful")
        
        # Summary
        if checks_passed:
            logger.info("\n✅ ALL PRE-MIGRATION CHECKS PASSED")
        else:
            logger.error("\n❌ PRE-MIGRATION CHECKS FAILED")
        
        return checks_passed
    
    async def get_neo4j_stats(self) -> Dict[str, Any]:
        """Get detailed Neo4j statistics"""
        try:
            # Get product count directly
            query = "MATCH (p:Product) RETURN count(p) as count"
            result = await self.migrator.neo4j.query(query)
            
            product_count = result[0]['count'] if result else 0
            
            # Get additional stats
            stats = await self.user_kg.get_database_statistics()
            stats['product_count'] = product_count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting Neo4j stats: {e}")
            return {"error": str(e)}
    
    async def test_sample_operations(self) -> bool:
        """Test operations on sample products"""
        try:
            # Get a sample product from Neo4j
            query = "MATCH (p:Product) RETURN p.id as id LIMIT 1"
            result = await self.migrator.neo4j.query(query)
            
            if not result:
                logger.warning("No products found for testing")
                return True
            
            product_id = result[0]['id']
            
            # Test getting product details
            product = await self.migrator.neo4j.get_product_details(product_id)
            
            if not product:
                logger.error(f"Failed to get product details for {product_id}")
                return False
            
            logger.info(f"Sample product: {product.get('title', 'Unknown')} - ${product.get('price', 0)}")
            return True
            
        except Exception as e:
            logger.error(f"Error in sample operations: {e}")
            return False
    
    async def run_migration(self) -> bool:
        """Run the actual migration"""
        logger.info("\n" + "="*50)
        logger.info("RUNNING MIGRATION")
        logger.info("="*50)
        
        self.migration_stats["start_time"] = datetime.now()
        
        try:
            # Initialize migrator
            await self.migrator.initialize()
            
            # Run migration
            stats = await self.migrator.run_migration(
                batch_size=100,
                verify=True,
                cleanup=False  # Don't cleanup yet
            )
            
            self.migration_stats["migration_result"] = stats
            
            if stats.get('failed', 0) > 0:
                logger.error(f"❌ Migration had {stats['failed']} failures")
                return False
            
            logger.info(f"✅ Successfully migrated {stats['migrated']} products")
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return False
        finally:
            self.migration_stats["end_time"] = datetime.now()
    
    async def run_post_migration_verification(self) -> bool:
        """Verify migration success"""
        logger.info("\n" + "="*50)
        logger.info("POST-MIGRATION VERIFICATION")
        logger.info("="*50)
        
        verification_passed = True
        
        # 1. Check Qdrant count matches Neo4j
        logger.info("\n1️⃣ Verifying product counts...")
        
        neo4j_count = self.migration_stats["pre_migration"]["neo4j"].get('product_count', 0)
        qdrant_stats = await self.product_retriever.get_collection_stats()
        qdrant_count = qdrant_stats.get('vectors_count', 0)
        
        self.migration_stats["post_migration"]["qdrant"] = qdrant_stats
        
        logger.info(f"Neo4j products: {neo4j_count}")
        logger.info(f"Qdrant vectors: {qdrant_count}")
        
        if qdrant_count < neo4j_count * 0.95:  # Allow 5% tolerance
            logger.error(f"❌ Product count mismatch! Missing {neo4j_count - qdrant_count} products")
            verification_passed = False
        else:
            logger.info("✅ Product counts match")
        
        # 2. Test random product lookups
        logger.info("\n2️⃣ Testing random product lookups...")
        
        sample_test_passed = await self.test_random_products()
        if not sample_test_passed:
            verification_passed = False
        
        # 3. Test search functionality
        logger.info("\n3️⃣ Testing search functionality...")
        
        search_test_passed = await self.test_search_functionality()
        if not search_test_passed:
            verification_passed = False
        
        # 4. Test battle system with migrated data
        logger.info("\n4️⃣ Testing battle system...")
        
        battle_test_passed = await self.test_battle_system()
        if not battle_test_passed:
            verification_passed = False
        
        # Summary
        if verification_passed:
            logger.info("\n✅ ALL POST-MIGRATION VERIFICATIONS PASSED")
        else:
            logger.error("\n❌ POST-MIGRATION VERIFICATION FAILED")
        
        return verification_passed
    
    async def test_random_products(self, sample_size: int = 10) -> bool:
        """Test random product lookups"""
        try:
            # Get random products from Neo4j
            query = """
            MATCH (p:Product)
            WITH p, rand() as r
            ORDER BY r
            LIMIT $limit
            RETURN p.id as id, p.title as title
            """
            
            neo4j_products = await self.migrator.neo4j.query(query, {"limit": sample_size})
            
            mismatches = 0
            for product in neo4j_products:
                product_id = product['id']
                
                # Get from Qdrant via HybridDataStore
                qdrant_product = await self.data_store.get_product(product_id)
                
                if not qdrant_product:
                    logger.error(f"Product {product_id} not found in Qdrant")
                    mismatches += 1
                elif qdrant_product.get('title') != product['title']:
                    logger.error(f"Title mismatch for {product_id}")
                    mismatches += 1
            
            if mismatches > 0:
                logger.error(f"❌ {mismatches}/{sample_size} products had issues")
                return False
            else:
                logger.info(f"✅ All {sample_size} sample products verified")
                return True
                
        except Exception as e:
            logger.error(f"Error testing random products: {e}")
            return False
    
    async def test_search_functionality(self) -> bool:
        """Test search works with migrated data"""
        try:
            test_queries = [
                "red dress",
                "summer clothing",
                "formal wear",
                "accessories"
            ]
            
            all_passed = True
            for query in test_queries:
                results = await self.data_store.search_products(query=query, limit=5)
                
                if not results:
                    logger.warning(f"No results for '{query}'")
                    all_passed = False
                else:
                    logger.info(f"✅ Found {len(results)} results for '{query}'")
            
            return all_passed
            
        except Exception as e:
            logger.error(f"Error testing search: {e}")
            return False
    
    async def test_battle_system(self) -> bool:
        """Test battle system with migrated data"""
        try:
            from competitive_search_system import CompetitiveSearchSystem
            from battle_agents import BattleAgents
            
            battle_agents = BattleAgents(
                neo4j_client=self.user_kg,
                qdrant_retriever=self.product_retriever
            )
            competitive_search = CompetitiveSearchSystem(battle_agents)
            
            # Run a test battle
            results = await competitive_search.execute_battle(
                query="elegant dress for special occasion",
                limit=5
            )
            
            if 'judgment' in results:
                winner = results['judgment'].get('winner')
                logger.info(f"✅ Battle executed. Winner: {winner}")
                return True
            else:
                logger.error("❌ Battle system test failed")
                return False
                
        except Exception as e:
            logger.error(f"Error testing battle system: {e}")
            return False
    
    async def cleanup_neo4j(self) -> bool:
        """Clean up Neo4j products after successful migration"""
        logger.info("\n" + "="*50)
        logger.info("NEO4J CLEANUP")
        logger.info("="*50)
        
        if self.dry_run:
            logger.info("🔍 DRY RUN - Simulating cleanup...")
            deleted = await self.migrator.cleanup_neo4j_products(dry_run=True)
            logger.info(f"Would delete {deleted} products from Neo4j")
            return True
        else:
            logger.warning("⚠️  ABOUT TO DELETE ALL PRODUCTS FROM NEO4J!")
            logger.warning("This action cannot be undone!")
            
            response = input("Are you SURE you want to proceed? Type 'DELETE' to confirm: ")
            if response != 'DELETE':
                logger.info("Cleanup cancelled")
                return False
            
            deleted = await self.migrator.cleanup_neo4j_products(dry_run=False)
            logger.info(f"✅ Deleted {deleted} products from Neo4j")
            
            self.migration_stats["cleanup"]["deleted_products"] = deleted
            return True
    
    async def run_complete_migration(self):
        """Run the complete migration process"""
        logger.info(f"\n{'='*60}")
        logger.info(f"VECTOR MIGRATION RUNNER - {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"{'='*60}\n")
        
        try:
            # Initialize
            await self.initialize_components()
            
            # Pre-migration checks
            if not await self.run_pre_migration_checks():
                logger.error("Pre-migration checks failed. Aborting.")
                return False
            
            # User confirmation
            if not self.dry_run:
                logger.warning("\n⚠️  READY TO START MIGRATION")
                logger.warning("This will copy all products from Neo4j to Qdrant")
                response = input("Continue? (y/N): ")
                if response.lower() != 'y':
                    logger.info("Migration cancelled by user")
                    return False
            
            # Run migration
            if not await self.run_migration():
                logger.error("Migration failed. Aborting.")
                return False
            
            # Post-migration verification
            if not await self.run_post_migration_verification():
                logger.error("Post-migration verification failed.")
                logger.warning("Products remain in both Neo4j and Qdrant")
                return False
            
            # Cleanup
            if await self.cleanup_neo4j():
                logger.info("\n✅ MIGRATION COMPLETED SUCCESSFULLY!")
            else:
                logger.warning("\n⚠️  Migration completed but cleanup was skipped")
            
            # Save final stats
            self.save_migration_report()
            
            return True
            
        except Exception as e:
            logger.error(f"Migration runner error: {e}")
            return False
        finally:
            # Cleanup connections
            if hasattr(self, 'user_kg'):
                await self.user_kg.close()
            if hasattr(self, 'migrator') and self.migrator.neo4j:
                await self.migrator.neo4j.close()
    
    def save_migration_report(self):
        """Save detailed migration report"""
        report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.migration_stats, f, indent=2, default=str)
        
        logger.info(f"\n📄 Migration report saved to: {report_file}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run the vector migration process")
    parser.add_argument(
        '--live',
        action='store_true',
        help='Run in LIVE mode (actually perform migration)'
    )
    parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='Skip integration tests (not recommended)'
    )
    
    args = parser.parse_args()
    
    # Create runner
    runner = MigrationRunner(dry_run=not args.live)
    
    # Run migration
    success = await runner.run_complete_migration()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())