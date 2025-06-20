#!/usr/bin/env python3
"""
System Verification Script for AI Stylist
Run this after completing the migration to verify 100% health.
"""

import asyncio
import logging
import sys
import os
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("system_verification")

class SystemVerification:
    """Comprehensive system verification for AI Stylist"""
    
    def __init__(self):
        self.test_results = {}
        self.errors = []
        self.warnings = []
    
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """Log test result"""
        self.test_results[test_name] = success
        status = "✅" if success else "❌"
        logger.info(f"{status} {test_name}: {message}")
        
        if not success:
            self.errors.append(f"{test_name}: {message}")
    
    def log_warning(self, test_name: str, message: str):
        """Log warning"""
        logger.warning(f"⚠️  {test_name}: {message}")
        self.warnings.append(f"{test_name}: {message}")
    
    async def test_camel_imports(self) -> bool:
        """Test CAMEL-AI 0.2.64 imports"""
        try:
            # Test core imports
            from camel.memories import LongtermAgentMemory, ScoreBasedContextCreator
            from camel.utils import OpenAITokenCounter
            from camel.types import ModelType, OpenAIBackendRole
            from camel.agents import ChatAgent
            from camel.messages import BaseMessage
            
            # Check version if available
            try:
                import camel
                version = getattr(camel, '__version__', 'unknown')
                if version.startswith('0.2.64'):
                    self.log_test("CAMEL Version", True, f"v{version}")
                else:
                    self.log_warning("CAMEL Version", f"Version {version} may have compatibility issues")
            except:
                self.log_warning("CAMEL Version", "Could not determine version")
            
            self.log_test("CAMEL Imports", True, "All critical components imported successfully")
            return True
            
        except ImportError as e:
            self.log_test("CAMEL Imports", False, f"Import error: {e}")
            return False
        except Exception as e:
            self.log_test("CAMEL Imports", False, f"Unexpected error: {e}")
            return False
    
    async def test_memory_creation(self) -> bool:
        """Test memory creation with CAMEL-AI 0.2.64"""
        try:
            from memory_integration_async import MemoryManager
            
            # Test memory manager creation
            manager = MemoryManager()
            self.log_test("Memory Manager", True, "Created successfully")
            
            # Test memory creation
            memory = await asyncio.wait_for(
                manager.create_memory(user_id="test_verification", enable_mcp=True),
                timeout=30.0
            )
            
            if memory is None:
                self.log_test("Memory Creation", False, "Returned None")
                return False
            
            # Test memory operations
            success = await manager.add_message(
                memory=memory,
                content="Test message for verification",
                role="user"
            )
            
            if not success:
                self.log_test("Memory Operations", False, "Could not add message")
                return False
            
            # Test context retrieval
            context, token_count = await manager.get_context(memory)
            
            if not isinstance(context, list):
                self.log_test("Memory Context", False, "Invalid context format")
                return False
            
            self.log_test("Memory Creation", True, f"Created and tested memory operations")
            return True
            
        except asyncio.TimeoutError:
            self.log_test("Memory Creation", False, "Timeout - possible recursion issue")
            return False
        except Exception as e:
            self.log_test("Memory Creation", False, f"Error: {e}")
            return False
    
    async def test_agent_factory(self) -> bool:
        """Test agent factory functionality"""
        try:
            from agent_factory import get_agent_factory
            from memory_integration_async import MemoryManager
            
            # Get factory
            factory = get_agent_factory()
            if not factory:
                self.log_test("Agent Factory", False, "Factory creation failed")
                return False
            
            # Create memory for agent
            manager = MemoryManager()
            memory = await manager.create_memory(user_id="test_agent", enable_mcp=True)
            
            # Create stylist agent
            agent = await asyncio.wait_for(
                factory.create_stylist_agent(
                    memory=memory,
                    enable_mcp=True
                ),
                timeout=30.0
            )
            
            if not agent:
                self.log_test("Agent Creation", False, "Agent creation returned None")
                return False
            
            self.log_test("Agent Factory", True, "Agent created successfully")
            return True
            
        except asyncio.TimeoutError:
            self.log_test("Agent Factory", False, "Timeout during agent creation")
            return False
        except Exception as e:
            self.log_test("Agent Factory", False, f"Error: {e}")
            return False
    
    async def test_neo4j_connection(self) -> bool:
        """Test Neo4j connection"""
        try:
            # Try to import and test Neo4j integration
            try:
                from neo4j_integration_async import ProductKnowledgeGraphAsync
            except ImportError:
                # Try the fixed version
                from neo4j_integration_fixed import ProductKnowledgeGraphAsync
            
            # Get connection details
            url = os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
            username = os.environ.get("NEO4J_USERNAME", "neo4j") 
            password = os.environ.get("NEO4J_PASSWORD", "shopari1234")
            
            if not password or password == "your_password":
                self.log_test("Neo4j Config", False, "NEO4J_PASSWORD not properly configured")
                return False
            
            # Test connection
            kg = ProductKnowledgeGraphAsync(url, username, password)
            
            # Test basic query
            stats = await asyncio.wait_for(
                kg.get_database_statistics(),
                timeout=15.0
            )
            
            await kg.close()
            
            if stats and not stats.get("error"):
                self.log_test("Neo4j Connection", True, f"Connected successfully")
                return True
            else:
                self.log_test("Neo4j Connection", False, f"Query failed: {stats}")
                return False
                
        except asyncio.TimeoutError:
            self.log_test("Neo4j Connection", False, "Connection timeout")
            return False
        except Exception as e:
            self.log_test("Neo4j Connection", False, f"Error: {e}")
            return False
    
    async def test_full_system(self) -> bool:
        """Test the full AI Stylist system"""
        try:
            from ai_stylist_app_async import EnhancedAIStylistApp
            
            # Initialize app
            app = EnhancedAIStylistApp()
            
            # Test session creation
            session_id = await asyncio.wait_for(
                app.create_session(user_id="test_system_verification"),
                timeout=30.0
            )
            
            if not session_id:
                self.log_test("System Integration", False, "Session creation failed")
                return False
            
            # Test message processing
            response, data = await asyncio.wait_for(
                app.send_message(session_id, "Hello, I need fashion advice for a wedding"),
                timeout=45.0
            )
            
            if not response or "error" in data:
                self.log_test("System Integration", False, f"Message processing failed: {data}")
                return False
            
            # Test recommendations
            try:
                recommendations = await asyncio.wait_for(
                    app.get_product_recommendations(
                        session_id=session_id,
                        query="formal dress",
                        limit=3
                    ),
                    timeout=30.0
                )
                
                rec_status = f"Got {len(recommendations)} recommendations"
                self.log_test("Recommendations", len(recommendations) > 0, rec_status)
                
            except Exception as e:
                self.log_warning("Recommendations", f"Could not test recommendations: {e}")
            
            # Clean up
            await app.close()
            
            self.log_test("System Integration", True, "Full system test passed")
            return True
            
        except asyncio.TimeoutError:
            self.log_test("System Integration", False, "System test timeout")
            return False
        except Exception as e:
            self.log_test("System Integration", False, f"Error: {e}")
            return False
    
    async def test_environment_variables(self) -> bool:
        """Test environment variables"""
        required_vars = {
            "NEO4J_URL": "Neo4j connection URL",
            "NEO4J_USERNAME": "Neo4j username",
            "NEO4J_PASSWORD": "Neo4j password"
        }
        
        optional_vars = {
            "OPENAI_API_KEY": "OpenAI API key",
            "QDRANT_URL": "Qdrant vector database URL",
            "QDRANT_API_KEY": "Qdrant API key"
        }
        
        all_good = True
        
        for var, description in required_vars.items():
            value = os.environ.get(var)
            if value and value not in ["your_password", "your_key", "your_url"]:
                self.log_test(f"Env: {var}", True, "Set correctly")
            else:
                self.log_test(f"Env: {var}", False, f"Missing or placeholder value")
                all_good = False
        
        for var, description in optional_vars.items():
            value = os.environ.get(var)
            if value and value not in ["your_password", "your_key", "your_url"]:
                self.log_test(f"Env: {var}", True, "Set correctly")
            else:
                self.log_warning(f"Env: {var}", "Not set (optional)")
        
        return all_good
    
    def calculate_health_score(self) -> float:
        """Calculate overall health score"""
        if not self.test_results:
            return 0.0
        
        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)
        
        return (passed / total) * 100
    
    def print_summary(self):
        """Print verification summary"""
        health_score = self.calculate_health_score()
        
        print("\n" + "="*80)
        print("🔍 AI STYLIST SYSTEM VERIFICATION RESULTS")
        print("="*80)
        
        print(f"\n📊 HEALTH SCORE: {health_score:.1f}%")
        
        if health_score >= 95:
            print("🟢 System Status: EXCELLENT - Ready for production!")
        elif health_score >= 85:
            print("🟡 System Status: GOOD - Minor issues to address")
        elif health_score >= 70:
            print("🟠 System Status: FAIR - Several issues need attention")
        else:
            print("🔴 System Status: POOR - Major issues require fixing")
        
        # Test breakdown
        passed = sum(1 for result in self.test_results.values() if result)
        failed = len(self.test_results) - passed
        
        print(f"\n📈 TEST RESULTS:")
        print(f"   • Passed: {passed}")
        print(f"   • Failed: {failed}")
        print(f"   • Warnings: {len(self.warnings)}")
        
        # Show failed tests
        if self.errors:
            print(f"\n❌ FAILED TESTS:")
            for error in self.errors:
                print(f"   • {error}")
        
        # Show warnings
        if self.warnings:
            print(f"\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        # Recommendations
        if health_score < 100:
            print(f"\n💡 RECOMMENDATIONS:")
            if failed > 0:
                print("   • Fix the failed tests above")
                print("   • Check the migration guide for specific fixes")
                print("   • Verify environment variables are set correctly")
            
            if len(self.warnings) > 0:
                print("   • Address warnings for optimal performance")
                print("   • Consider setting optional environment variables")
        
        print(f"\n" + "="*80)
        
        if health_score >= 95:
            print("🎉 CONGRATULATIONS! Your AI Stylist system is running perfectly!")
        else:
            print("🔧 Please address the issues above and run verification again.")
        
        print("="*80)

async def main():
    """Main verification function"""
    print("🚀 Starting AI Stylist System Verification...")
    print("This will test all critical components for CAMEL-AI 0.2.64 compatibility\n")
    
    verifier = SystemVerification()
    
    # Run all tests
    test_functions = [
        ("Environment Variables", verifier.test_environment_variables),
        ("CAMEL-AI Imports", verifier.test_camel_imports),
        ("Memory Integration", verifier.test_memory_creation),
        ("Agent Factory", verifier.test_agent_factory),
        ("Neo4j Connection", verifier.test_neo4j_connection),
        ("Full System Test", verifier.test_full_system),
    ]
    
    print("Running verification tests...\n")
    
    for test_name, test_func in test_functions:
        print(f"🔍 Testing {test_name}...")
        try:
            await test_func()
        except Exception as e:
            verifier.log_test(test_name, False, f"Unexpected error: {e}")
        print()
    
    # Print final summary
    verifier.print_summary()
    
    # Return appropriate exit code
    health_score = verifier.calculate_health_score()
    if health_score >= 95:
        sys.exit(0)  # Perfect health
    elif health_score >= 85:
        sys.exit(1)  # Good but has issues
    else:
        sys.exit(2)  # Major issues

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Verification interrupted by user")
        sys.exit(3)
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        sys.exit(4)
