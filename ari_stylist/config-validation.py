#!/usr/bin/env python3
"""
Quick validation script to ensure your environment is properly configured
"""
import os
import sys
import asyncio

def check_environment():
    """Check critical environment variables and dependencies"""
    issues = []
    
    # Check OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        issues.append("❌ OPENAI_API_KEY not set")
    else:
        print("✅ OpenAI API key found")
    
    # Check Neo4j credentials
    neo4j_vars = ["NEO4J_URL", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    for var in neo4j_vars:
        if not os.environ.get(var):
            issues.append(f"⚠️ {var} not set (using defaults)")
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append("❌ Python 3.8+ required")
    else:
        print(f"✅ Python {sys.version}")
    
    # Check critical imports
    try:
        import camel
        print(f"✅ CAMEL-AI {camel.__version__}")
        if not camel.__version__.startswith('0.2.64'):
            issues.append(f"⚠️ CAMEL version {camel.__version__} - expected 0.2.64")
    except ImportError:
        issues.append("❌ CAMEL-AI not installed")
    
    # Check for problematic file
    if os.path.exists("async_camel_service.py"):
        issues.append("❌ async_camel_service.py still exists - DELETE IT!")
    
    return issues

async def test_basic_functionality():
    """Test basic agent creation"""
    try:
        from agent_factory import get_agent_factory
        from memory_integration_async import MemoryManager
        
        print("\n🧪 Testing basic functionality...")
        
        # Test factory
        factory = get_agent_factory()
        assert factory is not None, "AgentFactory failed"
        print("✅ AgentFactory working")
        
        # Test memory manager
        manager = MemoryManager(None)
        memory = await manager.create_memory(enable_mcp=True)
        assert memory is not None, "Memory creation failed"
        print("✅ MemoryManager working")
        
        # Test agent creation
        agent = await factory.create_stylist_agent(memory=memory)
        assert agent is not None, "Agent creation failed"
        print("✅ Agent creation working")
        
        return True
    except Exception as e:
        print(f"❌ Functionality test failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 CAMEL-AI 0.2.64 Migration Validation\n")
    
    # Check environment
    issues = check_environment()
    
    if issues:
        print("\n⚠️ Issues found:")
        for issue in issues:
            print(f"  {issue}")
    
    # Run functionality test
    if not issues or all("⚠️" in i for i in issues):  # Only warnings
        asyncio.run(test_basic_functionality())
    else:
        print("\n❌ Fix critical issues before testing functionality")
        sys.exit(1)