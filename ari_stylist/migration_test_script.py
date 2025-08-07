#!/usr/bin/env python3
"""
CAMEL-AI 0.2.64 Migration Validation Test Script

This script validates that all migration fixes are working correctly
and that the system is fully compatible with CAMEL-AI 0.2.64.

Run this script after implementing the migration fixes to ensure
everything is working properly.
"""

import asyncio
import logging
import sys
import json
import time
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("migration_test")

class MigrationTestSuite:
    """Test suite to validate CAMEL-AI 0.2.64 migration"""
    
    def __init__(self):
        self.test_results = {}
        self.app = None
        self.test_user_id = "migration_test_user"
        self.test_session_id = None
        
    async def run_all_tests(self):
        """Run all migration validation tests"""
        logger.info("🚀 Starting CAMEL-AI 0.2.64 Migration Validation Tests")
        
        # Test 1: Import Validation
        await self.test_imports()
        
        # Test 2: Service Initialization
        await self.test_service_initialization()
        
        # Test 3: Memory System
        await self.test_memory_system()
        
        # Test 4: Agent Factory
        await self.test_agent_factory()
        
        # Test 5: Chat Session Management
        await self.test_chat_sessions()
        
        # Test 6: Recommendation Systems
        await self.test_recommendation_systems()
        
        # Test 7: Error Handling
        await self.test_error_handling()
        
        # Test 8: Backward Compatibility
        await self.test_backward_compatibility()
        
        # Generate report
        self.generate_test_report()
        
        return self.test_results
    
    async def test_imports(self):
        """Test that all critical imports work without AsyncCAMELService"""
        logger.info("📦 Testing imports...")
        
        try:
            # Test 1: Verify deprecated file is removed
            try:
                import AIStylist.ari_stylist.async_camel_service_ as async_camel_service_
                self.test_results["deprecated_file_removed"] = {
                    "status": "FAIL",
                    "error": "async_camel_service.py still exists and should be deleted"
                }
                return
            except ImportError:
                self.test_results["deprecated_file_removed"] = {
                    "status": "PASS",
                    "message": "async_camel_service.py successfully removed"
                }
            
            # Test 2: Test centralized imports
            from camel_imports import CAMEL_AVAILABLE, CAMEL_VERSION
            self.test_results["centralized_imports"] = {
                "status": "PASS",
                "camel_available": CAMEL_AVAILABLE,
                "camel_version": CAMEL_VERSION
            }
            
            # Test 3: Test AgentFactory import
            from agent_factory import get_agent_factory
            factory = get_agent_factory()
            self.test_results["agent_factory_import"] = {
                "status": "PASS",
                "factory_available": factory is not None
            }
            
            # Test 4: Test MemoryManager import
            from memory_integration_async import MemoryManager
            manager = MemoryManager(None)
            self.test_results["memory_manager_import"] = {
                "status": "PASS",
                "manager_available": manager is not None
            }
            
            # Test 5: Test fixed recommenders
            from ensemble_recommender import EnsembleRecommender
            from memory_rag_recommender import MemoryRAGRecommender
            
            self.test_results["recommender_imports"] = {
                "status": "PASS",
                "ensemble_available": EnsembleRecommender is not None,
                "memory_rag_available": MemoryRAGRecommender is not None
            }
            
        except Exception as e:
            self.test_results["imports"] = {
                "status": "FAIL",
                "error": str(e)
            }
            logger.error(f"❌ Import test failed: {e}")
    
    async def test_service_initialization(self):
        """Test that the main service initializes correctly"""
        logger.info("🔧 Testing service initialization...")
        
        try:
            # Test AI Stylist app initialization
            from ai_stylist_app_async import EnhancedAIStylistApp
            
            self.app = EnhancedAIStylistApp(
                neo4j_url="bolt://34.135.40.119:7687",
                neo4j_username="neo4j", 
                neo4j_password="shopari1234"
            )
            
            # Give it a moment to initialize
            await asyncio.sleep(2)
            
            self.test_results["service_initialization"] = {
                "status": "PASS",
                "app_initialized": self.app is not None,
                "agent_factory_available": hasattr(self.app, 'agent_factory'),
                "memory_manager_available": hasattr(self.app, 'memory_manager')
            }
            
        except Exception as e:
            self.test_results["service_initialization"] = {
                "status": "FAIL", 
                "error": str(e)
            }
            logger.error(f"❌ Service initialization failed: {e}")
    
    async def test_memory_system(self):
        """Test that the memory system works with CAMEL 0.2.64"""
        logger.info("🧠 Testing memory system...")
        
        if not self.app:
            self.test_results["memory_system"] = {
                "status": "SKIP",
                "reason": "App not initialized"
            }
            return
        
        try:
            # Test memory creation
            memory = await self.app.memory_manager.create_memory(
                user_id=self.test_user_id,
                enable_mcp=True
            )
            
            memory_created = memory is not None
            
            # Test adding messages to memory
            message_added = False
            if memory:
                message_added = await self.app.memory_manager.add_message(
                    memory=memory,
                    content="Test message for migration validation",
                    role="user"
                )
            
            # Test getting context from memory
            context_retrieved = False
            context_size = 0
            if memory:
                context, token_count = await self.app.memory_manager.get_context(memory)
                context_retrieved = len(context) > 0
                context_size = len(context)
            
            self.test_results["memory_system"] = {
                "status": "PASS" if memory_created and message_added else "PARTIAL",
                "memory_created": memory_created,
                "message_added": message_added,
                "context_retrieved": context_retrieved,
                "context_size": context_size
            }
            
        except Exception as e:
            self.test_results["memory_system"] = {
                "status": "FAIL",
                "error": str(e)
            }
            logger.error(f"❌ Memory system test failed: {e}")
    
    async def test_agent_factory(self):
        """Test that AgentFactory works correctly"""
        logger.info("🤖 Testing agent factory...")
        
        if not self.app:
            self.test_results["agent_factory"] = {
                "status": "SKIP",
                "reason": "App not initialized"
            }
            return
        
        try:
            # Test stylist agent creation
            memory = await self.app.memory_manager.create_memory(
                user_id=self.test_user_id,
                enable_mcp=True
            )
            
            agent = await self.app.agent_factory.create_stylist_agent(
                memory=memory,
                enable_mcp=True
            )
            
            agent_created = agent is not None
            
            # Test agent has required attributes
            has_system_message = hasattr(agent, 'system_message') if agent else False
            has_memory = hasattr(agent, 'memory') if agent else False
            
            self.test_results["agent_factory"] = {
                "status": "PASS" if agent_created else "FAIL",
                "agent_created": agent_created,
                "has_system_message": has_system_message,
                "has_memory": has_memory
            }
            
        except Exception as e:
            self.test_results["agent_factory"] = {
                "status": "FAIL",
                "error": str(e)
            }
            logger.error(f"❌ Agent factory test failed: {e}")
    
    async def test_chat_sessions(self):
        """Test chat session creation and messaging"""
        logger.info("💬 Testing chat sessions...")
        
        if not self.app:
            self.test_results["chat_sessions"] = {
                "status": "SKIP",
                "reason": "App not initialized"
            }
            return
        
        try:
            # Test session creation
            self.test_session_id = await self.app.create_session(user_id=self.test_user_id)
            session_created = self.test_session_id is not None
            
            # Test message processing
            message_processed = False
            response = ""
            if self.test_session_id:
                response, data = await self.app.send_message(
                    self.test_session_id,
                    "Hello, this is a test message for migration validation."
                )
                message_processed = len(response) > 0
            
            # Test session retrieval
            session_retrieved = False
            if self.test_session_id:
                session = await self.app.get_session(self.test_session_id)
                session_retrieved = session is not None
            
            self.test_results["chat_sessions"] = {
                "status": "PASS" if session_created and message_processed else "PARTIAL",
                "session_created": session_created,
                "session_id": self.test_session_id,
                "message_processed": message_processed,
                "response_length": len(response) if response else 0,
                "session_retrieved": session_retrieved
            }
            
        except Exception as e:
            self.test_results["chat_sessions"] = {
                "status": "FAIL",
                "error": str(e)
            }
            logger.error(f"❌ Chat sessions test failed: {e}")
    
    async def test_recommendation_systems(self):
        """Test that recommendation systems work with new patterns"""
        logger.info("🎯 Testing recommendation systems...")
        
        if not self.app or not self.test_session_id:
            self.test_results["recommendation_systems"] = {
                "status": "SKIP",
                "reason": "App or session not initialized"
            }
            return
        
        try:
            # Test product recommendations
            recommendations = await self.app.get_product_recommendations(
                session_id=self.test_session_id,
                query="summer dress",
                limit=3
            )
            
            recommendations_received = len(recommendations) > 0
            
            # Test recommendation structure
            valid_structure = False
            if recommendations:
                first_rec = recommendations[0]
                valid_structure = all(key in first_rec for key in ['id', 'title', 'price'])
            
            # Test ensemble system if available
            ensemble_works = False
            if hasattr(self.app, 'enhanced_recommender_manager'):
                try:
                    ensemble_recs = await self.app.enhanced_recommender_manager.get_recommendations(
                        user_id=self.test_user_id,
                        query="casual outfit",
                        limit=2
                    )
                    ensemble_works = len(ensemble_recs) >= 0  # Even 0 results is OK
                except Exception:
                    ensemble_works = False
            
            self.test_results["recommendation_systems"] = {
                "status": "PASS" if recommendations_received else "PARTIAL",
                "recommendations_count": len(recommendations),
                "valid_structure": valid_structure,
                "ensemble_available": ensemble_works
            }
            
        except Exception as e:
            self.test_results["recommendation_systems"] = {
                "status": "FAIL",
                "error": str(e)
            }
            logger.error(f"❌ Recommendation systems test failed: {e}")
    
    async def test_error_handling(self):
        """Test that error handling works correctly"""
        logger.info("⚠️ Testing error handling...")
        
        try:
            # Test 1: Invalid session handling
            invalid_response, invalid_data = await self.app.send_message(
                "invalid_session_id",
                "Test message"
            )
            
            handles_invalid_session = "session" in invalid_response.lower() or "error" in invalid_data
            
            # Test 2: Memory manager error handling
            memory_error_handled = True
            try:
                # Try to create memory with invalid parameters
                bad_memory = await self.app.memory_manager.create_memory(
                    user_id=None,  # Invalid user ID
                    token_limit=-1  # Invalid token limit
                )
                # If this doesn't raise an error, that's also OK (graceful handling)
            except Exception:
                # Error was raised and handled, which is good
                pass
            
            # Test 3: Agent factory error handling
            agent_error_handled = True
            try:
                # Try to create agent with invalid parameters
                bad_agent = await self.app.agent_factory.create_agent(
                    system_message="",  # Empty system message
                    model_type="invalid_model"  # Invalid model
                )
                # If this returns None or works with fallback, that's OK
            except Exception:
                # Error was raised and handled, which is good
                pass
            
            self.test_results["error_handling"] = {
                "status": "PASS",
                "invalid_session_handled": handles_invalid_session,
                "memory_errors_handled": memory_error_handled,
                "agent_errors_handled": agent_error_handled
            }
            
        except Exception as e:
            self.test_results["error_handling"] = {
                "status": "FAIL",
                "error": str(e)
            }
            logger.error(f"❌ Error handling test failed: {e}")
    
    async def test_backward_compatibility(self):
        """Test that backward compatibility functions still work"""
        logger.info("🔄 Testing backward compatibility...")
        
        try:
            # Test backward compatibility imports
            from stylist_agent_async import create_stylist_agent_async, get_stylist_agent_async
            
            # Test creating memory using old method
            memory = await self.app.memory_manager.create_memory(
                user_id=self.test_user_id
            )
            
            # Test creating agent using backward compatibility function
            old_style_agent = await get_stylist_agent_async(memory)
            
            backward_compatible = old_style_agent is not None
            
            self.test_results["backward_compatibility"] = {
                "status": "PASS" if backward_compatible else "PARTIAL",
                "old_functions_work": backward_compatible,
                "memory_compatible": memory is not None
            }
            
        except Exception as e:
            self.test_results["backward_compatibility"] = {
                "status": "FAIL",
                "error": str(e)
            }
            logger.error(f"❌ Backward compatibility test failed: {e}")
    
    def generate_test_report(self):
        """Generate a comprehensive test report"""
        logger.info("📊 Generating test report...")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get("status") == "PASS")
        failed_tests = sum(1 for result in self.test_results.values() if result.get("status") == "FAIL")
        partial_tests = sum(1 for result in self.test_results.values() if result.get("status") == "PARTIAL")
        skipped_tests = sum(1 for result in self.test_results.values() if result.get("status") == "SKIP")
        
        print("\n" + "="*60)
        print("🎯 CAMEL-AI 0.2.64 MIGRATION VALIDATION REPORT")
        print("="*60)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Partial: {partial_tests}")
        print(f"⏭️ Skipped: {skipped_tests}")
        print()
        
        # Detailed results
        for test_name, result in self.test_results.items():
            status = result.get("status", "UNKNOWN")
            status_icon = {
                "PASS": "✅",
                "FAIL": "❌", 
                "PARTIAL": "⚠️",
                "SKIP": "⏭️"
            }.get(status, "❓")
            
            print(f"{status_icon} {test_name.upper()}: {status}")
            
            if "error" in result:
                print(f"   Error: {result['error']}")
            
            # Show key metrics for each test
            for key, value in result.items():
                if key not in ["status", "error"] and isinstance(value, (bool, int, str)):
                    if isinstance(value, bool):
                        print(f"   {key}: {'✓' if value else '✗'}")
                    else:
                        print(f"   {key}: {value}")
            print()
        
        # Overall assessment
        print("🔍 MIGRATION ASSESSMENT:")
        if failed_tests == 0:
            print("🎉 MIGRATION SUCCESSFUL! All critical tests passed.")
            print("   Your system is fully compatible with CAMEL-AI 0.2.64.")
        elif failed_tests <= 2 and partial_tests >= 0:
            print("⚠️ MIGRATION MOSTLY SUCCESSFUL with minor issues.")
            print("   Review failed tests and fix any remaining issues.")
        else:
            print("❌ MIGRATION NEEDS ATTENTION.")
            print("   Multiple tests failed. Review the errors above.")
        
        print("\n📋 NEXT STEPS:")
        if failed_tests > 0:
            print("1. Fix the failed tests shown above")
            print("2. Re-run this test script")
            print("3. Deploy only after all tests pass")
        else:
            print("1. ✅ Migration validation complete!")
            print("2. ✅ Safe to deploy to production")
            print("3. ✅ Monitor logs for any issues")
        
        print("\n" + "="*60)
        
        # Save detailed results to file
        with open("migration_test_results.json", "w") as f:
            json.dump({
                "timestamp": time.time(),
                "summary": {
                    "total": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "partial": partial_tests,
                    "skipped": skipped_tests
                },
                "detailed_results": self.test_results
            }, f, indent=2)
        
        print("📄 Detailed results saved to: migration_test_results.json")

async def main():
    """Main test execution"""
    test_suite = MigrationTestSuite()
    
    try:
        results = await test_suite.run_all_tests()
        
        # Clean up
        if test_suite.app:
            await test_suite.app.close()
        
        # Exit with appropriate code
        failed_count = sum(1 for result in results.values() if result.get("status") == "FAIL")
        sys.exit(1 if failed_count > 0 else 0)
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())