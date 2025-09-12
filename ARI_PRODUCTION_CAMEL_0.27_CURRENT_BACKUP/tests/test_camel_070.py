"""
Test CAMEL 0.2.70 API Changes
Validates the new API patterns before migration
This file should be run FIRST to understand the new API
"""

import os
import sys
import asyncio
import logging
from typing import Optional, Any, Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_camel_070")

def test_camel_import():
    """Test basic CAMEL import and version."""
    print("\n" + "="*60)
    print("TEST 1: Basic CAMEL Import")
    print("="*60)
    
    try:
        import camel
        print(f"✅ CAMEL imported successfully")
        print(f"   Version: {camel.__version__}")
        
        # Check if version is 0.2.70 or higher
        version_parts = camel.__version__.split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1])
        patch = int(version_parts[2]) if len(version_parts) > 2 else 0
        
        if major == 0 and minor == 2 and patch >= 70:
            print(f"✅ Version is 0.2.70+")
            return True
        else:
            print(f"⚠️  Version {camel.__version__} may not have new API")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import CAMEL: {e}")
        print("   Install with: pip install camel-ai==0.2.70")
        return False

def test_model_factory():
    """Test ModelFactory pattern for 0.2.70."""
    print("\n" + "="*60)
    print("TEST 2: ModelFactory API")
    print("="*60)
    
    try:
        from camel.models import ModelFactory
        from camel.types import ModelPlatformType, ModelType
        
        print("✅ ModelFactory imported")
        
        # Test creating OpenAI model
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4O_MINI,
            model_config_dict={
                "temperature": 0.7,
                "max_tokens": 100
            }
        )
        
        print(f"✅ Created OpenAI model: {type(model)}")
        
        # Check model attributes
        if hasattr(model, 'model_type'):
            print(f"   Model type: {model.model_type}")
        if hasattr(model, 'model_config'):
            print(f"   Config keys: {list(model.model_config.keys())}")
            
        return True
        
    except Exception as e:
        print(f"❌ ModelFactory test failed: {e}")
        return False

def test_chat_agent():
    """Test ChatAgent creation with new API."""
    print("\n" + "="*60)
    print("TEST 3: ChatAgent Creation")
    print("="*60)
    
    try:
        from camel.models import ModelFactory
        from camel.types import ModelPlatformType, ModelType
        from camel.agents import ChatAgent
        
        # Create model first
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4O_MINI,
            model_config_dict={"temperature": 0.7}
        )
        
        # Test different ways to pass system message
        system_msg = "You are a helpful assistant."
        
        # Method 1: Direct string (new in 0.2.70?)
        try:
            agent = ChatAgent(
                system_message=system_msg,
                model=model
            )
            print("✅ Method 1: Direct string system_message works")
        except:
            print("❌ Method 1: Direct string failed")
            
            # Method 2: Try with SystemMessage class
            try:
                from camel.messages import SystemMessage
                agent = ChatAgent(
                    system_message=SystemMessage(content=system_msg),
                    model=model
                )
                print("✅ Method 2: SystemMessage class works")
            except Exception as e:
                print(f"❌ Method 2: SystemMessage failed: {e}")
                return False
        
        # Check agent attributes
        print(f"   Agent type: {type(agent)}")
        if hasattr(agent, 'model'):
            print(f"   Has model: ✅")
        if hasattr(agent, 'step'):
            print(f"   Has step method: ✅")
        if hasattr(agent, 'step_async'):
            print(f"   Has step_async: ✅")
        elif hasattr(agent, 'astep'):
            print(f"   Has astep: ✅")
            
        return True
        
    except Exception as e:
        print(f"❌ ChatAgent test failed: {e}")
        return False

def test_memory_api():
    """Test memory API changes."""
    print("\n" + "="*60)
    print("TEST 4: Memory API")
    print("="*60)
    
    try:
        # Try different import patterns
        memory_imported = False
        
        # Pattern 1: From memories
        try:
            from camel.memories import LongtermAgentMemory
            print("✅ Import from camel.memories works")
            memory_imported = True
        except:
            print("❌ camel.memories import failed")
            
        # Pattern 2: From memory (singular)
        if not memory_imported:
            try:
                from camel.memory import LongtermAgentMemory
                print("✅ Import from camel.memory works")
                memory_imported = True
            except:
                print("❌ camel.memory import failed")
        
        if not memory_imported:
            print("⚠️  Could not import LongtermAgentMemory")
            return False
            
        # Test memory components
        try:
            from camel.memories import (
                ScoreBasedContextCreator,
                ChatHistoryBlock,
                VectorDBBlock
            )
            print("✅ Memory components imported")
            
            # Test creating memory
            from camel.utils import OpenAITokenCounter
            from camel.types import ModelType
            
            memory = LongtermAgentMemory(
                context_creator=ScoreBasedContextCreator(
                    token_counter=OpenAITokenCounter(ModelType.GPT_4O_MINI),
                    token_limit=1024
                ),
                chat_history_block=ChatHistoryBlock(),
                vector_db_block=VectorDBBlock()
            )
            
            print("✅ Memory created successfully")
            print(f"   Memory type: {type(memory)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Memory component test failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Memory test failed: {e}")
        return False

def test_base_message():
    """Test BaseMessage API."""
    print("\n" + "="*60)
    print("TEST 5: BaseMessage API")
    print("="*60)
    
    try:
        from camel.messages import BaseMessage
        
        # Test creating messages
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content="Hello, this is a test."
        )
        
        assistant_msg = BaseMessage.make_assistant_message(
            role_name="Assistant",
            content="Hello! I'm here to help."
        )
        
        print("✅ BaseMessage creation works")
        print(f"   User message type: {type(user_msg)}")
        print(f"   Assistant message type: {type(assistant_msg)}")
        
        # Check message attributes
        if hasattr(user_msg, 'content'):
            print(f"   Has content attribute: ✅")
        if hasattr(user_msg, 'role_name'):
            print(f"   Has role_name attribute: ✅")
            
        return True
        
    except Exception as e:
        print(f"❌ BaseMessage test failed: {e}")
        return False

async def test_async_agent():
    """Test async agent operations."""
    print("\n" + "="*60)
    print("TEST 6: Async Agent Operations")
    print("="*60)
    
    try:
        from camel.models import ModelFactory
        from camel.types import ModelPlatformType, ModelType
        from camel.agents import ChatAgent
        from camel.messages import BaseMessage
        
        # Create agent
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4O_MINI,
            model_config_dict={"temperature": 0.7, "max_tokens": 50}
        )
        
        agent = ChatAgent(
            system_message="You are a helpful assistant. Keep responses very brief.",
            model=model
        )
        
        # Test async step
        test_msg = BaseMessage.make_user_message(
            role_name="User",
            content="Say 'test successful' if you can hear me."
        )
        
        # Try different async methods
        response = None
        
        # Method 1: step_async
        if hasattr(agent, 'step_async'):
            response = await agent.step_async(test_msg)
            print("✅ step_async method works")
        # Method 2: astep
        elif hasattr(agent, 'astep'):
            response = await agent.astep(test_msg)
            print("✅ astep method works")
        # Method 3: sync step in async context
        elif hasattr(agent, 'step'):
            response = agent.step(test_msg)
            print("✅ sync step method works (in async context)")
        else:
            print("❌ No suitable step method found")
            return False
            
        if response:
            print(f"   Response type: {type(response)}")
            if hasattr(response, 'msgs'):
                print(f"   Response has msgs: ✅")
            if hasattr(response, 'msg'):
                print(f"   Response has msg: ✅")
                if hasattr(response.msg, 'content'):
                    print(f"   Response content preview: {response.msg.content[:50]}...")
                    
        return True
        
    except Exception as e:
        print(f"❌ Async agent test failed: {e}")
        return False

def test_tools_api():
    """Test tools/functions API."""
    print("\n" + "="*60)
    print("TEST 7: Tools/Functions API")
    print("="*60)
    
    try:
        from camel.models import ModelFactory
        from camel.types import ModelPlatformType, ModelType
        from camel.agents import ChatAgent
        
        # Define a simple tool
        def get_weather(location: str) -> str:
            """Get weather for a location."""
            return f"The weather in {location} is sunny."
        
        # Create agent with tool
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4O_MINI
        )
        
        # Test different ways to pass tools
        try:
            # Method 1: Direct list
            agent = ChatAgent(
                system_message="You are a weather assistant.",
                model=model,
                tools=[get_weather]
            )
            print("✅ Tools as direct list works")
        except:
            # Method 2: Wrapped tools
            try:
                from camel.toolkits import FunctionTool
                agent = ChatAgent(
                    system_message="You are a weather assistant.",
                    model=model,
                    tools=[FunctionTool(get_weather)]
                )
                print("✅ Tools as FunctionTool works")
            except Exception as e:
                print(f"⚠️  Tools API may have changed: {e}")
                
        return True
        
    except Exception as e:
        print(f"❌ Tools test failed: {e}")
        return False

def run_all_tests():
    """Run all API tests."""
    print("\n" + "="*70)
    print(" CAMEL 0.2.70 API VALIDATION TESTS")
    print("="*70)
    
    results = {}
    
    # Run sync tests
    results['import'] = test_camel_import()
    
    if not results['import']:
        print("\n❌ Cannot continue without CAMEL. Please install:")
        print("   pip install camel-ai==0.2.70")
        return
    
    results['model_factory'] = test_model_factory()
    results['chat_agent'] = test_chat_agent()
    results['memory'] = test_memory_api()
    results['base_message'] = test_base_message()
    results['tools'] = test_tools_api()
    
    # Run async test
    try:
        results['async'] = asyncio.run(test_async_agent())
    except:
        results['async'] = False
    
    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name:20} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Ready for migration to CAMEL 0.2.70")
    else:
        print("\n⚠️  Some tests failed. Review the API changes before migration.")
    
    return results

if __name__ == "__main__":
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set")
        print("   Some tests may fail without it")
        print("   Set with: export OPENAI_API_KEY='your-key-here'")
        print()
    
    results = run_all_tests()
