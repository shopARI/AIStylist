# save as full_debug.py
import asyncio
import os
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("full_debug")

async def test_full_pipeline():
    print("="*60)
    print("FULL PIPELINE DEBUG TEST")
    print("="*60)
    
    # 1. TEST INTENT DETECTION
    print("\n1. TESTING INTENT DETECTION...")
    print("-"*40)
    from services.nlp.intent_detector import IntentDetector
    from services.nlp.parameter_extractor import ParameterExtractor
    
    detector = IntentDetector()
    extractor = ParameterExtractor()
    
    test_queries = [
        "show me something to wear for a wedding",
        "wedding dress",
        "blue shirt"
    ]
    
    for query in test_queries:
        try:
            intent = await detector.detect_intent(query)
            params = await extractor.extract_parameters(query)
            print(f"Query: '{query}'")
            print(f"  Intent: {intent}")
            print(f"  Params: {params}")
        except Exception as e:
            print(f"  ERROR: {e}")
    
    # 2. TEST INDIVIDUAL AGENTS
    print("\n2. TESTING INDIVIDUAL AGENTS...")
    print("-"*40)
    
    from services.product.retriever import ProductRetrieverService
    from services.user.knowledge_graph import UserKnowledgeGraphService
    from agents.cypher_bot import CypherBotAgent
    from agents.vibe_bot import VibeBotAgent
    
    # Initialize services
    retriever = ProductRetrieverService()
    await retriever.initialize()
    
    neo4j = UserKnowledgeGraphService(
        url="bolt://34.135.40.119:7687",
        username="neo4j",
        password=os.getenv("NEO4J_PASSWORD", "shopari1234")
    )
    await neo4j.initialize()
    
    # Test CypherBot
    print("\nTesting CypherBot...")
    try:
        cypher = CypherBotAgent(neo4j)
        cypher_results = await cypher.search(
            query="wedding",
            filters={"category": "dress"},
            limit=5
        )
        print(f"  CypherBot found: {len(cypher_results)} products")
        if cypher_results:
            print(f"    Sample: {cypher_results[0].get('title', 'NO TITLE')[:50]}")
    except Exception as e:
        print(f"  CypherBot ERROR: {e}")
    
    # Test VibeBot
    print("\nTesting VibeBot...")
    try:
        vibe = VibeBotAgent(retriever)
        vibe_results = await vibe.search(
            query="wedding dress",
            limit=5
        )
        print(f"  VibeBot found: {len(vibe_results)} products")
        if vibe_results:
            print(f"    Sample: {vibe_results[0].get('title', 'NO TITLE')[:50]}")
    except Exception as e:
        print(f"  VibeBot ERROR: {e}")
    
    # 3. TEST BATTLE EXECUTOR
    print("\n3. TESTING BATTLE EXECUTION...")
    print("-"*40)
    
    from services.battle.executor import BattleExecutor
    from agents.judge import JudgeAriAgent
    
    try:
        judge = JudgeAriAgent()
        executor = BattleExecutor(
            cypher_bot=cypher,
            vibe_bot=vibe,
            judge=judge
        )
        
        result = await executor.execute(
            query="wedding dress",
            limit=10
        )
        
        print(f"  Battle Winner: {result.get('winner')}")
        print(f"  Products: {len(result.get('products', []))}")
        print(f"  Cypher found: {result.get('cypher_count', 0)}")
        print(f"  Vibe found: {result.get('vibe_count', 0)}")
        print(f"  Consensus: {result.get('consensus_count', 0)}")
    except Exception as e:
        print(f"  Battle ERROR: {e}")
    
    # 4. TEST APPLICATION SERVICE
    print("\n4. TESTING APPLICATION SERVICE...")
    print("-"*40)
    
    from services.application import ApplicationService
    from services.conversation_handler import ConversationHandler
    from services.battle.orchestrator import BattleOrchestrator
    from services.memory.fallback_manager import MemoryFallbackManager
    from services.battle.metrics import BattleMetrics
    from services.battle.optimizer import BattleOptimizer
    from services.cache.battle_cache import BattleCache
    
    try:
        # Create components
        memory_manager = MemoryFallbackManager()
        conversation_handler = ConversationHandler(
            neo4j_service=neo4j,
            qdrant_service=retriever,
            memory_manager=memory_manager
        )
        
        cache = BattleCache()
        optimizer = BattleOptimizer()
        metrics = BattleMetrics()
        
        orchestrator = BattleOrchestrator(
            executor=executor,
            cache=cache,
            optimizer=optimizer,
            metrics=metrics
        )
        
        app_service = ApplicationService(
            conversation_handler=conversation_handler,
            battle_orchestrator=orchestrator,
            user_kg_service=neo4j
        )
        
        # Test processing a message
        response = await app_service.process_message(
            session_id="test-session",
            message="show me a wedding dress"
        )
        
        print(f"  Response: {response.response[:100]}...")
        print(f"  Products: {len(response.products)}")
        print(f"  Intent: {response.metadata.get('intent')}")
    except Exception as e:
        print(f"  Application ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # FINAL RECOMMENDATIONS
    print("\n="*60)
    print("DIAGNOSIS:")
    print("="*60)
    
    print("\nCheck which component failed above and fix:")
    print("1. If VibeBot timeout: increase timeout in retriever.py")
    print("2. If no products: check filters and score thresholds")
    print("3. If battle fails: check agent results")
    print("4. If app service fails: check the error trace")
    
    await retriever.close()
    await neo4j.close()

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
