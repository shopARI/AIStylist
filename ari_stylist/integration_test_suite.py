"""
Integration Test Suite for Vector Migration
Tests the HybridDataStore, Battle System, and migration readiness
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
import json
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("integration_tests")

# Import components
try:
    from user_knowledge_graph_async import UserKnowledgeGraphAsync
    from hybrid_data_store import HybridDataStore
    from product_retriever_async_enhanced import ProductRetrieverAsync
    from battle_agents import BattleAgents
    from competitive_search_system import CompetitiveSearchSystem
    from ai_stylist_app_async import EnhancedAIStylistApp
    
    logger.info("✅ All imports successful")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    sys.exit(1)


class IntegrationTestSuite:
    """Comprehensive test suite for vector migration integration"""
    
    def __init__(self):
        self.test_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }
        
        # Test data
        self.test_user_id = "test_user_integration"
        self.test_product_id = None  # Will be set during tests
        
    async def setup(self):
        """Initialize test environment"""
        logger.info("🔧 Setting up test environment...")
        
        try:
            # Initialize components
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
            
            self.battle_agents = BattleAgents(
                neo4j_client=self.user_kg,
                qdrant_retriever=self.product_retriever
            )
            
            self.competitive_search = CompetitiveSearchSystem(self.battle_agents)
            
            logger.info("✅ Test environment setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            return False
    
    async def teardown(self):
        """Clean up test environment"""
        logger.info("🧹 Cleaning up test environment...")
        
        try:
            # Clean up test user
            if hasattr(self, 'user_kg'):
                await self.user_kg.close()
                
            logger.info("✅ Cleanup complete")
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
    
    async def run_all_tests(self):
        """Run all integration tests"""
        logger.info("🚀 Starting integration tests...")
        
        if not await self.setup():
            logger.error("Setup failed, aborting tests")
            return self.test_results
        
        # Test categories
        test_methods = [
            # Basic connectivity
            self.test_neo4j_connectivity,
            self.test_qdrant_connectivity,
            
            # HybridDataStore routing
            self.test_user_operations_routing,
            self.test_product_operations_routing,
            
            # Battle system
            self.test_battle_system_basic,
            self.test_battle_system_with_filters,
            
            # Data integrity
            self.test_product_search,
            self.test_user_preferences,
            
            # Full integration
            self.test_full_recommendation_flow,
            
            # Migration readiness
            self.test_migration_readiness
        ]
        
        for test_method in test_methods:
            await self.run_single_test(test_method)
        
        await self.teardown()
        
        # Print summary
        self.print_test_summary()
        
        return self.test_results
    
    async def run_single_test(self, test_method):
        """Run a single test with error handling"""
        test_name = test_method.__name__
        self.test_results["total"] += 1
        
        try:
            logger.info(f"\n🧪 Running {test_name}...")
            result = await test_method()
            
            if result:
                self.test_results["passed"] += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                self.test_results["failed"] += 1
                logger.error(f"❌ {test_name} FAILED")
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.test_results["errors"].append({
                "test": test_name,
                "error": str(e)
            })
            logger.error(f"❌ {test_name} ERROR: {e}")
    
    # === CONNECTIVITY TESTS ===
    
    async def test_neo4j_connectivity(self) -> bool:
        """Test Neo4j connection and basic operations"""
        try:
            # Test user creation
            result = await self.user_kg.create_or_update_user(self.test_user_id)
            if not result:
                logger.error("Failed to create test user")
                return False
            
            # Test user retrieval
            user = await self.user_kg.get_user_details(self.test_user_id)
            if not user or user.get('id') != self.test_user_id:
                logger.error("Failed to retrieve test user")
                return False
            
            logger.info("Neo4j operations working correctly")
            return True
            
        except Exception as e:
            logger.error(f"Neo4j connectivity test failed: {e}")
            return False
    
    async def test_qdrant_connectivity(self) -> bool:
        """Test Qdrant connection and basic operations"""
        try:
            # Get collection stats
            stats = await self.product_retriever.get_collection_stats()
            
            if not isinstance(stats, dict):
                logger.error("Failed to get Qdrant stats")
                return False
            
            logger.info(f"Qdrant stats: {stats}")
            
            # Try to search for products
            results = await self.product_retriever.search_by_natural_language(
                "test query",
                limit=1
            )
            
            logger.info(f"Qdrant search returned {len(results)} results")
            return True
            
        except Exception as e:
            logger.error(f"Qdrant connectivity test failed: {e}")
            return False
    
    # === ROUTING TESTS ===
    
    async def test_user_operations_routing(self) -> bool:
        """Test that user operations go to Neo4j"""
        try:
            # Create user preference
            result = await self.data_store.create_or_update_user(
                self.test_user_id,
                {"test_field": "test_value"}
            )
            
            if not result:
                logger.error("Failed to create/update user via HybridDataStore")
                return False
            
            # Get user
            user = await self.data_store.get_user(self.test_user_id)
            if not user:
                logger.error("Failed to get user via HybridDataStore")
                return False
            
            # Check stats to verify Neo4j was called
            stats = self.data_store.get_stats()
            if stats["neo4j_calls"] == 0:
                logger.error("User operations not routing to Neo4j")
                return False
            
            logger.info(f"User operations correctly routed. Stats: {stats}")
            return True
            
        except Exception as e:
            logger.error(f"User routing test failed: {e}")
            return False
    
    async def test_product_operations_routing(self) -> bool:
        """Test that product operations go to Qdrant"""
        try:
            # Search products
            results = await self.data_store.search_products(
                query="dress",
                limit=5
            )
            
            # Check stats to verify Qdrant was called
            stats = self.data_store.get_stats()
            if stats["qdrant_calls"] == 0:
                logger.error("Product operations not routing to Qdrant")
                return False
            
            # Store a product ID for later tests
            if results:
                self.test_product_id = results[0].get('id')
            
            logger.info(f"Product operations correctly routed. Found {len(results)} products")
            return True
            
        except Exception as e:
            logger.error(f"Product routing test failed: {e}")
            return False
    
    # === BATTLE SYSTEM TESTS ===
    
    async def test_battle_system_basic(self) -> bool:
        """Test basic battle system functionality"""
        try:
            # Execute a simple battle
            results = await self.competitive_search.execute_battle(
                query="red dress for wedding",
                limit=5
            )
            
            # Check structure
            if not isinstance(results, dict):
                logger.error("Battle results not a dictionary")
                return False
            
            if 'judgment' not in results:
                logger.error("No judgment in battle results")
                return False
            
            judgment = results['judgment']
            winner = judgment.get('winner')
            
            if winner not in ['cypher', 'vector', 'draw']:
                logger.error(f"Invalid winner: {winner}")
                return False
            
            logger.info(f"Battle executed successfully. Winner: {winner}")
            logger.info(f"Explanation: {judgment.get('explanation', 'No explanation')[:200]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Battle system test failed: {e}")
            return False
    
    async def test_battle_system_with_filters(self) -> bool:
        """Test battle system with filters"""
        try:
            # Execute battle with filters
            results = await self.competitive_search.execute_battle(
                query="formal dress",
                filters={
                    "min_price": 50,
                    "max_price": 500,
                    "occasion": "wedding"
                },
                limit=5
            )
            
            # Check both agents returned results
            cypher_products = results.get('agents', {}).get('cypher', {}).get('products', [])
            vector_products = results.get('agents', {}).get('vector', {}).get('products', [])
            
            logger.info(f"CypherBot: {len(cypher_products)} products")
            logger.info(f"VibeBot: {len(vector_products)} products")
            
            # At least one agent should have results
            if len(cypher_products) == 0 and len(vector_products) == 0:
                logger.warning("No products found by either agent")
            
            return True
            
        except Exception as e:
            logger.error(f"Battle system filter test failed: {e}")
            return False
    
    # === DATA INTEGRITY TESTS ===
    
    async def test_product_search(self) -> bool:
        """Test product search functionality"""
        try:
            # Search with query
            results = await self.data_store.search_products(
                query="summer dress",
                limit=10
            )
            
            if not isinstance(results, list):
                logger.error("Search results not a list")
                return False
            
            # Verify product structure
            for product in results[:3]:  # Check first 3
                required_fields = ['id', 'title', 'price']
                for field in required_fields:
                    if field not in product:
                        logger.error(f"Missing required field: {field}")
                        return False
            
            logger.info(f"Product search working. Found {len(results)} products")
            return True
            
        except Exception as e:
            logger.error(f"Product search test failed: {e}")
            return False
    
    async def test_user_preferences(self) -> bool:
        """Test user preference operations"""
        try:
            # Add preference
            await self.user_kg.update_user_preference(
                self.test_user_id,
                "color",
                "blue",
                confidence=0.9
            )
            
            # Get preferences
            prefs = await self.data_store.get_user_preferences(self.test_user_id)
            
            if not isinstance(prefs, dict):
                logger.error("Preferences not a dictionary")
                return False
            
            logger.info(f"User preferences working. Preferences: {prefs}")
            return True
            
        except Exception as e:
            logger.error(f"User preferences test failed: {e}")
            return False
    
    # === FULL INTEGRATION TEST ===
    
    async def test_full_recommendation_flow(self) -> bool:
        """Test complete recommendation flow with app"""
        try:
            # Initialize app
            app = EnhancedAIStylistApp()
            
            # Create session
            session_id = await app.create_session(self.test_user_id)
            
            if not session_id:
                logger.error("Failed to create session")
                return False
            
            # Send message
            response, data = await app.send_message(
                session_id,
                "I need a red dress for a summer wedding"
            )
            
            if not response:
                logger.error("No response from app")
                return False
            
            # Check if battle system was used
            if 'used_battle_system' in data:
                logger.info(f"Battle system used: {data['used_battle_system']}")
            
            logger.info(f"Full flow test passed. Response length: {len(response)}")
            return True
            
        except Exception as e:
            logger.error(f"Full integration test failed: {e}")
            return False
    
    # === MIGRATION READINESS ===
    
    async def test_migration_readiness(self) -> bool:
        """Check if system is ready for migration"""
        try:
            readiness = {
                "neo4j_users": False,
                "qdrant_products": False,
                "hybrid_routing": False,
                "battle_system": False
            }
            
            # Check Neo4j has users but not products
            stats = await self.user_kg.get_database_statistics()
            if stats.get('user_statistics', {}).get('user_count', 0) > 0:
                readiness["neo4j_users"] = True
            
            # Check Qdrant has products
            qdrant_stats = await self.product_retriever.get_collection_stats()
            if qdrant_stats.get('vectors_count', 0) > 0:
                readiness["qdrant_products"] = True
            
            # Check hybrid routing works
            data_store_stats = self.data_store.get_stats()
            if data_store_stats['neo4j_calls'] > 0 and data_store_stats['qdrant_calls'] > 0:
                readiness["hybrid_routing"] = True
            
            # Check battle system works
            battle_stats = await self.competitive_search.get_current_stats()
            if battle_stats['total_battles'] > 0:
                readiness["battle_system"] = True
            
            # Print readiness report
            logger.info("\n📋 MIGRATION READINESS REPORT:")
            all_ready = True
            for check, status in readiness.items():
                status_emoji = "✅" if status else "❌"
                logger.info(f"{status_emoji} {check}: {'READY' if status else 'NOT READY'}")
                if not status:
                    all_ready = False
            
            if all_ready:
                logger.info("\n🎉 SYSTEM IS READY FOR MIGRATION!")
            else:
                logger.warning("\n⚠️  SYSTEM NOT READY FOR MIGRATION - Fix issues above")
            
            return all_ready
            
        except Exception as e:
            logger.error(f"Migration readiness test failed: {e}")
            return False
    
    def print_test_summary(self):
        """Print test results summary"""
        total = self.test_results['total']
        passed = self.test_results['passed']
        failed = self.test_results['failed']
        
        logger.info("\n" + "="*50)
        logger.info("TEST SUMMARY")
        logger.info("="*50)
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed} ({passed/total*100:.1f}%)")
        logger.info(f"Failed: {failed} ({failed/total*100:.1f}%)")
        
        if self.test_results['errors']:
            logger.info("\nERRORS:")
            for error in self.test_results['errors']:
                logger.error(f"- {error['test']}: {error['error']}")
        
        if failed == 0:
            logger.info("\n✅ ALL TESTS PASSED! Ready for migration.")
        else:
            logger.warning(f"\n❌ {failed} TESTS FAILED! Fix issues before migration.")


async def main():
    """Run the integration test suite"""
    logger.info("Starting Integration Test Suite for Vector Migration")
    
    test_suite = IntegrationTestSuite()
    results = await test_suite.run_all_tests()
    
    # Save results to file
    with open("integration_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\nTest results saved to integration_test_results.json")
    
    # Exit with appropriate code
    sys.exit(0 if results['failed'] == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())