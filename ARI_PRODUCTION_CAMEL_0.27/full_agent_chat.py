#!/usr/bin/env python3
"""
Full ARI Agent Collaboration Chat Interface
Uses the complete multi-agent architecture: CypherBot, VibeBot, Ari Stylist, ML Intelligence
"""

import asyncio
import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables FIRST
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s'
)

# Suppress noisy HTTP library logs
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

class FullAgentARIChat:
    """Complete ARI chat interface using the full multi-agent collaboration system."""
    
    def __init__(self):
        self.session_id = f"full_agent_{int(time.time())}"
        self.user_id = "chat_user"
        self.conversation_count = 0
        
        # Will hold the complete system
        self.container = None
        self.app_service = None
        self.system_ready = False
        
    async def initialize_system(self):
        """Initialize the COMPLETE ARI system with all agents and intelligence."""
        print("Initializing COMPLETE ARI Fashion Stylist System")
        print("   This includes: CypherBot, VibeBot, Ari Stylist, ML Intelligence")
        print()
        
        try:
            # Initialize the full dependency injection container
            from di.container import initialize_container
            print("Loading complete system architecture...")
            
            self.container = await initialize_container()
            print("Dependency injection container loaded")
            
            # Get the ApplicationService which orchestrates everything
            self.app_service = await self.container.application_service()
            print("Application service ready")
            
            print()
            print("COMPLETE MULTI-AGENT SYSTEM READY!")
            print("   CypherBot: Neo4j graph query specialist")
            print("   VibeBot: Vector similarity search expert") 
            print("   Ari Stylist: Intelligent result curator")
            print("   ML Intelligence: User profiling & personalization")
            print("   Session Memory: Redis-backed conversation context")
            print("   Intent Detection: LLM + hardcoded hybrid system")
            print("   Agent Orchestrator: Collaborative recommendation framework")
            print()
            
            self.system_ready = True
            return True
            
        except Exception as e:
            print(f"CRITICAL FAILURE: Could not initialize complete system")
            print(f"   Error: {e}")
            print("   Please check that all services are running:")
            print("   - Redis server")
            print("   - Neo4j database (productionbackup2)")
            print("   - Qdrant vector database")
            print("   - OpenAI API key")
            print()
            import traceback
            traceback.print_exc()
            self.system_ready = False
            return False
    
    async def process_message(self, message: str) -> tuple[str, Dict[str, Any]]:
        """Process message through the COMPLETE ARI system with detailed agent mind output."""
        if not self.app_service:
            return "Complete system not initialized", {}
        
        try:
            print(f"ENGAGING FULL AGENT COLLABORATION SYSTEM...")
            print(f"   Query: '{message}'")
            print()
            
            # The ApplicationService will automatically use VerboseExecutor via DI container
            
            # Use the ApplicationService which orchestrates EVERYTHING
            start_time = time.time()
            chat_response = await self.app_service.process_message(
                session_id=self.session_id,
                user_id=self.user_id,
                message=message
            )
            processing_time = time.time() - start_time
            
            print(f"   Processing completed in {processing_time:.2f}s")
            
            # Extract metadata
            metadata = chat_response.metadata
            metadata["processing_time"] = processing_time
            metadata["products_found"] = len(chat_response.products)
            
            return chat_response.response, metadata
            
        except Exception as e:
            print(f"Agent collaboration system error: {e}")
            import traceback
            traceback.print_exc()
            return f"The agent collaboration system encountered an issue processing: '{message}'. Please try again.", {}
    
    def display_response(self, user_message: str, ari_response: str, metadata: Dict[str, Any]):
        """Display the complete agent collaboration results."""
        print("\n" + "="*80)
        print(f"USER: {user_message}")
        print("="*80)
        print(f"ARI AGENTS: {ari_response}")
        print("="*80)
        
        # Show agent battle details
        if metadata:
            print("AGENT COLLABORATION DETAILS:")
            if "intent" in metadata:
                print(f"   Intent: {metadata['intent']}")
            if "confidence" in metadata:
                print(f"   Confidence: {metadata['confidence']:.2f}")
            if "method" in metadata:
                print(f"   Detection Method: {metadata['method']}")
            if "processing_time" in metadata:
                print(f"   Processing Time: {metadata['processing_time']:.2f}s")
            if "products_found" in metadata:
                print(f"   Products Found: {metadata['products_found']}")
            
            # Show collaboration metadata if available
            if "battle_metadata" in metadata:
                collaboration_data = metadata["battle_metadata"]
                print("   COLLABORATION RESULTS:")
                if "winner" in collaboration_data:
                    print(f"      Best Source: {collaboration_data['winner']}")
                if "cypher_count" in collaboration_data:
                    print(f"      CypherBot Results: {collaboration_data['cypher_count']}")
                if "vibe_count" in collaboration_data:
                    print(f"      VibeBot Results: {collaboration_data['vibe_count']}")
                if "battle_time" in collaboration_data:
                    print(f"      Collaboration Duration: {collaboration_data['battle_time']:.2f}s")
            
            # Show ML intelligence if available
            if "ml_enhanced" in metadata and metadata["ml_enhanced"]:
                print("   ML Intelligence: ACTIVE")
            if "personalized" in metadata and metadata["personalized"]:
                print("   Personalization: ENABLED")
        
        print("="*80)
        print()
    
    async def run_chat(self):
        """Run the complete agent collaboration chat interface."""
        print("="*80)
        print("ARI FASHION STYLIST - COMPLETE MULTI-AGENT SYSTEM")
        print(f"Session: {self.session_id}")
        print("="*80)
        
        # Initialize the complete system
        if not await self.initialize_system():
            print("Failed to initialize complete system. Exiting...")
            return
        
        print("Ready! Ask me anything about fashion and let the agents find the best results.")
        print()
        print("Examples:")
        print("- 'I need a black dress for a wedding'")
        print("- 'Show me trendy winter coats'")
        print("- 'What would look good with dark jeans?'")
        print()
        print("Commands: 'quit' to exit, 'status' for system status, 'memory' for session memory")
        print()
        
        # Chat loop
        while True:
            try:
                # Get user input
                message = input("You: ").strip()
                
                if not message:
                    continue
                
                if message.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                    print("\nThanks for testing the complete ARI agent system! Goodbye!\n")
                    break
                
                if message.lower() == 'status':
                    print("\nCOMPLETE SYSTEM STATUS:")
                    print(f"   System Ready: {'YES' if self.system_ready else 'NO'}")
                    print(f"   Session: {self.session_id}")
                    print(f"   Messages Processed: {self.conversation_count}")
                    print(f"   Application Service: {'Active' if self.app_service else 'Inactive'}")
                    print("   Multi-Agent Components:")
                    print("      CypherBot (Neo4j specialist)")
                    print("      VibeBot (Vector search expert)")
                    print("      Ari Stylist (Result curator)")
                    print("      ML Intelligence (Personalization)")
                    print("      Enhanced Session Memory (Persistent context)")
                    
                    # Show session memory stats
                    if self.app_service:
                        try:
                            stats = await self.app_service.session_memory.get_session_stats(self.session_id)
                            if stats.get("exists"):
                                print(f"   Session Memory Stats:")
                                print(f"      • Total conversations: {stats.get('total_turns', 0)}")
                                print(f"      • Has learning summary: {'Yes' if stats.get('has_summary') else 'No'}")
                                print(f"      • Recent activity: {stats.get('recent_activity', 0)} in last hour")
                                if stats.get('preferred_categories'):
                                    print(f"      • Learned preferences: {', '.join(stats['preferred_categories'])}")
                            else:
                                print(f"   Session Memory: Fresh session (no history)")
                        except Exception as e:
                            print(f"   Session Memory: Error checking stats - {e}")
                    print()
                    continue
                
                if message.lower() == 'memory':
                    print("\nSESSION MEMORY DETAILS:")
                    if self.app_service:
                        try:
                            context = await self.app_service.session_memory.get_session_context(self.session_id, context_turns=10)
                            preferences = await self.app_service.session_memory.get_user_preferences(self.session_id)
                            
                            if context:
                                print(f"   Recent Context ({len(context)} chars):")
                                print(f"   {context[:200]}...")
                            else:
                                print("   No conversation context yet")
                            
                            if preferences:
                                print(f"   Learned Preferences:")
                                for key, value in preferences.items():
                                    if value:
                                        print(f"      • {key.title()}: {', '.join(value[:3]) if isinstance(value, list) else value}")
                            else:
                                print("   No preferences learned yet")
                                
                        except Exception as e:
                            print(f"   Error accessing memory: {e}")
                    print()
                    continue
                
                # Process message through COMPLETE agent system
                print(f"\nLaunching agent collaboration for: '{message}'")
                ari_response, metadata = await self.process_message(message)
                
                # Increment conversation count
                self.conversation_count += 1
                
                # Display the complete results
                self.display_response(message, ari_response, metadata)
                
            except KeyboardInterrupt:
                print("\n\nAgent collaboration interrupted. Goodbye!\n")
                break
            except EOFError:
                print("\n\nInput stream ended. Goodbye!\n")
                break
            except Exception as e:
                print(f"\nUnexpected error: {e}")
                print("Continuing agent collaboration...\n")
                continue

async def main():
    """Main entry point for the complete ARI agent system."""
    try:
        chat = FullAgentARIChat()
        await chat.run_chat()
    except Exception as e:
        print(f"Fatal system error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting COMPLETE ARI Multi-Agent Fashion Stylist System...")
    asyncio.run(main())