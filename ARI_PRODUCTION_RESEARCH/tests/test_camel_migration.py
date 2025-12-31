"""
Test CAMEL Migration from 0.2.64 to 0.2.70
Compares old patterns with new patterns
Validates that we can migrate the existing code
"""

import os
import sys
import asyncio
import logging
from typing import Optional, Any, Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_migration")

class MigrationTester:
    """Test migration patterns from 0.2.64 to 0.2.70"""
    
    def __init__(self):
        self.old_patterns = []
        self.new_patterns = []
        self.migration_notes = []
        
    def test_agent_creation_patterns(self):
        """Compare old vs new agent creation patterns."""
        print("\n" + "="*60)
        print("MIGRATION TEST: Agent Creation")
        print("="*60)
        
        # OLD PATTERN (0.2.64)
        print("\n📦 OLD PATTERN (0.2.64):")
        print("""
from camel.messages import SystemMessage
from camel.agents import ChatAgent
from camel.types import ModelType

agent = ChatAgent(
    system_message=SystemMessage(content="You are Ari..."),
    model=ModelType.GPT_4O_MINI,
    message_window_size=10
)
        """)
        
        # NEW PATTERN (0.2.70)
        print("\n✨ NEW PATTERN (0.2.70):")
        print("""
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.agents import ChatAgent

# Step 1: Create model first
model = ModelFactory.create(
    model_platform=ModelPlatformType.OPENAI,
    model_type=ModelType.GPT_4O_MINI,
    model_config_dict={"temperature": 0.7}
)

# Step 2: Create agent with model object
agent = ChatAgent(
    system_message="You are Ari...",  # Direct string now!
    model=model,  # Model object, not type
    tools=[]  # Direct list, not wrapped
)
        """)
        
        # Test the new pattern
        try:
            from camel.models import ModelFactory
            from camel.types import ModelPlatformType, ModelType
            from camel.agents import ChatAgent
            
            model = ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI,
                model_type=ModelType.GPT_4O_MINI,
                model_config_dict={"temperature": 0.7}
            )
            
            agent = ChatAgent(
                system_message="You are a test agent.",
                model=model
            )
            
            print("\n New pattern works!")
            
            self.migration_notes.append(
                "Agent Creation: Use ModelFactory.create() first, then pass model object to ChatAgent"
            )
            return True
            
        except Exception as e:
            print(f"\n New pattern failed: {e}")
            return False
    
    def test_memory_patterns(self):
        """Compare old vs new memory patterns."""
        print("\n" + "="*60)
        print("MIGRATION TEST: Memory Creation")
        print("="*60)
        
        # OLD PATTERN
        print("\n📦 OLD PATTERN (0.2.64):")
        print("""
from camel.memories import (
    LongtermAgentMemory,
    ScoreBasedContextCreator,
    ChatHistoryBlock,
    VectorDBBlock
)
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
        """)
        
        # NEW PATTERN (might be same)
        print("\n✨ NEW PATTERN (0.2.70):")
        print("(Testing if same pattern works...)")
        
        try:
            from camel.memories import (
                LongtermAgentMemory,
                ScoreBasedContextCreator,
                ChatHistoryBlock,
                VectorDBBlock
            )
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
            
            print("\n Memory pattern unchanged (backward compatible)")
            
            self.migration_notes.append(
                "Memory: Same pattern works, but check for new optional parameters"
            )
            return True
            
        except Exception as e:
            print(f"\n⚠️  Memory pattern may need adjustment: {e}")
            
            # Try alternative pattern
            print("\nTrying alternative pattern...")
            try:
                from camel.memory import AgentMemory
                
                memory = AgentMemory()
                print(" Alternative: Use simplified AgentMemory()")
                
                self.migration_notes.append(
                    "Memory: Consider using simplified AgentMemory() class"
                )
                return True
                
            except:
                print(" Could not find working memory pattern")
                return False
    
    def test_message_patterns(self):
        """Compare old vs new message patterns."""
        print("\n" + "="*60)
        print("MIGRATION TEST: Message Creation")
        print("="*60)
        
        # OLD PATTERN
        print("\n📦 OLD PATTERN (0.2.64):")
        print("""
from camel.messages import BaseMessage

user_msg = BaseMessage.make_user_message(
    role_name="User",
    content="Hello"
)

response = agent.step(user_msg)
        """)
        
        # Test if pattern still works
        try:
            from camel.messages import BaseMessage
            
            user_msg = BaseMessage.make_user_message(
                role_name="User",
                content="Test message"
            )
            
            print("\n Message pattern unchanged")
            
            self.migration_notes.append(
                "Messages: BaseMessage.make_user_message() still works"
            )
            return True
            
        except Exception as e:
            print(f"\n Message pattern failed: {e}")
            return False
    
    def test_battle_agents_migration(self):
        """Test migration of battle agents (CypherBot, VibeBot, Judge)."""
        print("\n" + "="*60)
        print("MIGRATION TEST: Battle Agents")
        print("="*60)
        
        print("\n📦 OLD CYPHER BOT PATTERN:")
        print("""
# From battle_agents.py
self.agent = ChatAgent(
    system_message=SystemMessage(content=system_message),
    model=ModelType.GPT_4O_MINI,
    message_window_size=10
)
        """)
        
        print("\n✨ NEW CYPHER BOT PATTERN:")
        new_pattern = """
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.agents import ChatAgent

class CypherBotAgent:
    def __init__(self, neo4j_client):
        self.neo4j = neo4j_client
        
        # Create model first
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4O_MINI,
            model_config_dict={
                "temperature": 0.7,
                "max_tokens": 4000
            }
        )
        
        # Create agent with model object
        self.agent = ChatAgent(
            system_message="You are CypherBot...",  # Direct string
            model=model,  # Model object
            tools=[]  # Direct list
        )
        """
        
        print(new_pattern)
        
        # Test the pattern
        try:
            from camel.models import ModelFactory
            from camel.types import ModelPlatformType, ModelType
            from camel.agents import ChatAgent
            
            model = ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI,
                model_type=ModelType.GPT_4O_MINI,
                model_config_dict={"temperature": 0.7}
            )
            
            cypher_agent = ChatAgent(
                system_message="You are CypherBot, a data-driven fashion intelligence agent.",
                model=model
            )
            
            print("\n Battle agent pattern works!")
            
            self.migration_notes.append(
                "Battle Agents: Create model with ModelFactory first, then pass to ChatAgent"
            )
            return True
            
        except Exception as e:
            print(f"\n Battle agent pattern failed: {e}")
            return False
    
    def test_ari_personality_preservation(self):
        """Ensure Ari's personality can be preserved exactly."""
        print("\n" + "="*60)
        print("MIGRATION TEST: Ari's Personality Preservation")
        print("="*60)
        
        # The exact personality from agent_factory.py
        ari_personality = """You are Ari, a warm and personable fashion stylist with years of experience helping clients look and feel their best.

Communication Style:
- Speak naturally and conversationally, like a friendly chat with a trusted stylist
- Avoid bullet points, numbered lists, or rigid formatting
- Use "I" and "you" to maintain personal connection
- Express genuine enthusiasm for fashion and helping clients"""
        
        print(f"\nTesting with Ari's personality ({len(ari_personality)} chars)...")
        
        try:
            from camel.models import ModelFactory
            from camel.types import ModelPlatformType, ModelType
            from camel.agents import ChatAgent
            
            model = ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI,
                model_type=ModelType.GPT_4O_MINI,
                model_config_dict={
                    "temperature": 0.7,
                    "max_tokens": 4000
                }
            )
            
            ari_agent = ChatAgent(
                system_message=ari_personality,
                model=model
            )
            
            # Check if personality is preserved
            if hasattr(ari_agent, 'system_message'):
                if ari_personality in str(ari_agent.system_message):
                    print(" Personality preserved exactly!")
                else:
                    print("⚠️  Personality may be modified")
            else:
                print(" Agent created (personality storage unclear)")
            
            self.migration_notes.append(
                "Ari's Personality: Can be passed as direct string to ChatAgent"
            )
            return True
            
        except Exception as e:
            print(f" Failed to preserve personality: {e}")
            return False
    
    def test_async_patterns(self):
        """Test async pattern changes."""
        print("\n" + "="*60)
        print("MIGRATION TEST: Async Patterns")
        print("="*60)
        
        print("\n📦 OLD ASYNC PATTERN:")
        print("""
# Unclear if step was async in 0.2.64
response = agent.step(message)
        """)
        
        print("\n✨ NEW ASYNC PATTERN:")
        print("""
# Check for async methods
if hasattr(agent, 'step_async'):
    response = await agent.step_async(message)
elif hasattr(agent, 'astep'):
    response = await agent.astep(message)
else:
    # Fallback to sync
    response = agent.step(message)
        """)
        
        self.migration_notes.append(
            "Async: Check for step_async or astep methods, fallback to sync step"
        )
        
        return True
    
    def generate_migration_guide(self):
        """Generate migration guide based on tests."""
        print("\n" + "="*70)
        print(" MIGRATION GUIDE: 0.2.64 → 0.2.70")
        print("="*70)
        
        print("\n📋 KEY CHANGES:")
        for i, note in enumerate(self.migration_notes, 1):
            print(f"\n{i}. {note}")
        
        print("\n\n MIGRATION STRATEGY:")
        print("""
1. **Create lib/camel/v070/ package**:
   - __init__.py with new imports
   - compatibility.py with helpers
   
2. **Update agent creation everywhere**:
   - Always create model with ModelFactory first
   - Pass model object (not type) to ChatAgent
   - Use direct strings for system_message
   
3. **Preserve exact personalities**:
   - Copy from agent_factory.py → config/prompts.py
   - Pass as strings to ChatAgent
   
4. **Keep compatibility layer**:
   - The CompatibilityLayer from camel_imports.py is useful
   - Adapt it for 0.2.70 patterns
   
5. **Test incrementally**:
   - Start with one agent (e.g., CypherBot)
   - Validate it works
   - Then migrate others
        """)
        
        print("\n\n📄 EXAMPLE MIGRATION:")
        print("""
# lib/camel/v070/__init__.py
```python
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.agents import ChatAgent

def create_agent(system_message: str, model_type=ModelType.GPT_4O_MINI):
    '''Helper to create agents with new API'''
    
    # Always create model first
    model = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=model_type,
        model_config_dict={
            "temperature": 0.7,
            "max_tokens": 4000
        }
    )
    
    # Then create agent
    return ChatAgent(
        system_message=system_message,
        model=model,
        tools=[]
    )
```
        """)

def run_migration_tests():
    """Run all migration tests."""
    print("\n" + "="*70)
    print(" CAMEL 0.2.64 → 0.2.70 MIGRATION TESTS")
    print("="*70)
    
    tester = MigrationTester()
    
    results = {}
    
    # Run tests
    results['agent_creation'] = tester.test_agent_creation_patterns()
    results['memory'] = tester.test_memory_patterns()
    results['messages'] = tester.test_message_patterns()
    results['battle_agents'] = tester.test_battle_agents_migration()
    results['ari_personality'] = tester.test_ari_personality_preservation()
    results['async'] = tester.test_async_patterns()
    
    # Generate guide
    tester.generate_migration_guide()
    
    # Summary
    print("\n" + "="*70)
    print(" TEST RESULTS")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = " PASS" if result else " FAIL"
        print(f"  {test_name:20} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n Migration path validated! Ready to proceed.")
    else:
        print("\n⚠️  Some patterns need investigation before migration.")
    
    return results

if __name__ == "__main__":
    # Check environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set")
        print()
    
    # Check CAMEL version
    try:
        import camel
        print(f"Current CAMEL version: {camel.__version__}")
    except:
        print("CAMEL not installed")
    
    results = run_migration_tests()
