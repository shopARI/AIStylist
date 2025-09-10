#!/usr/bin/env python3
"""
Simple ARI Chat Interface - No External Dependencies
Works with refactored architecture without crashing.
"""

import asyncio
import os
import sys
import time
import json
from typing import Dict, Any, Optional

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables FIRST (before any imports)
from dotenv import load_dotenv
load_dotenv()

class SimpleARIChat:
    """Simple chat interface compatible with refactored architecture."""
    
    def __init__(self):
        self.session_id = f"simple_{int(time.time())}"
        self.user_id = "simple_user"
        self.conversation_count = 0
        
        # Services will be initialized later
        self.intent_detector = None
        self.conversation_handler = None
        self.agent_factory = None
        self.product_retriever = None
        self.battle_orchestrator = None
        self.ml_intelligence = None
        
        # Initialize status
        self.system_ready = False
        
    async def initialize_system(self):
        """Initialize the ARI system with graceful fallbacks."""
        print("\n🚀 Initializing ARI Fashion Stylist System...")
        
        try:
            # Try to import and initialize core services
            from services.nlp.hybrid_intent_detector import get_hybrid_intent_detector
            print("  ✓ Intent detector imported")
            
            self.intent_detector = get_hybrid_intent_detector()
            print("  ✓ Intent detector initialized")
            
            # Try agent factory
            try:
                from agents.factory import get_agent_factory
                self.agent_factory = await get_agent_factory()
                print("  ✓ Agent factory initialized")
            except Exception as e:
                print(f"  ⚠ Agent factory unavailable: {e}")
                self.agent_factory = None
            
            # Try conversation handler
            try:
                from services.conversation_handler import ConversationHandler
                self.conversation_handler = ConversationHandler()
                print("  ✓ Conversation handler initialized")
            except Exception as e:
                print(f"  ⚠ Conversation handler unavailable: {e}")
                self.conversation_handler = None
            
            # Try product retriever
            try:
                from services.product.retriever import ProductRetrieverService
                self.product_retriever = ProductRetrieverService(
                    qdrant_url=os.getenv("QDRANT_URL"),
                    qdrant_api_key=os.getenv("QDRANT_API_KEY"),
                    collection_name=os.getenv("QDRANT_COLLECTION_NAME", "fashion_products")
                )
                print("  ✓ Product retriever initialized")
            except Exception as e:
                print(f"  ⚠ Product retriever unavailable: {e}")
                self.product_retriever = None
            
            print("✅ Core services initialized!\n")
            self.system_ready = True
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            print("Running in minimal fallback mode...\n")
            self.system_ready = False
            return False
    
    async def process_message(self, message: str) -> tuple[str, Dict[str, Any]]:
        """Process message with error handling."""
        metadata = {
            "intent": "conversation",
            "confidence": 0.8,
            "method": "simple",
            "processing_time": 0.0,
            "system_ready": self.system_ready
        }
        
        start_time = time.time()
        
        try:
            # Detect intent if available
            if self.intent_detector:
                try:
                    intent_result = await self.intent_detector.detect_intent_and_extract(message)
                    metadata.update({
                        "intent": intent_result.primary_intent.value,  # Use .value to get the string value
                        "confidence": intent_result.confidence,
                        "method": intent_result.detection_method
                    })
                except Exception as e:
                    print(f"Intent detection error: {e}")
            
            # Process based on intent
            intent = metadata["intent"]
            
            # Shopping-related intents that should trigger agent battle
            shopping_intents = ["specific_item", "inspiration", "comparison", "gift", "outfit", "brand", "sale"]
            
            if intent in shopping_intents:
                # This is a shopping query - search for actual products
                if self.product_retriever:
                    try:
                        print(f"🔍 Searching for products: '{message}'")
                        products = await self.product_retriever.search_by_natural_language(
                            query=message,
                            top_k=5,
                            min_confidence=0.6
                        )
                        
                        if products:
                            product_list = "\n".join([
                                f"• {p.get('title', 'Unknown')} - ${p.get('price', 'N/A')}"
                                for p in products[:3]
                            ])
                            response = f"Great! I found some options for you:\n\n{product_list}\n\nWould you like to see more details about any of these, or should I search for something more specific?"
                            metadata["products"] = products
                        else:
                            response = f"I searched our database for '{message}' but didn't find exact matches. Let me help you refine your search - could you tell me more about the style, color, or occasion you're looking for?"
                    except Exception as e:
                        print(f"Product search error: {e}")
                        response = f"I'm having trouble accessing our product database right now, but I'd love to help you think through what you're looking for regarding '{message}'. What specific style or occasion did you have in mind?"
                else:
                    response = f"I understand you're looking for '{message}'. My product search is temporarily unavailable, but I can help you think through style options. What occasion is this for, or do you have any specific preferences?"
            
            elif intent == "browse":
                # Check if this is actually just a greeting that was misclassified
                greeting_words = ["hello", "hi", "hey", "how are you", "how's it going", "what's up", "good morning", "good afternoon", "good evening"]
                is_greeting = any(greeting in message.lower() for greeting in greeting_words)
                
                if is_greeting:
                    # Handle as conversation, not fashion browse
                    if "how are you" in message.lower() or "how's it going" in message.lower():
                        response = "I'm doing great, thank you! I'm here and ready to help you with any fashion questions or just chat. How can I assist you today?"
                    else:
                        response = "Hello! I'm ARI, your fashion stylist. I'm here to help you look amazing or just have a nice conversation. What's on your mind?"
                else:
                    # Low confidence browse or other topics - send to conversation handler
                    if self.conversation_handler:
                        try:
                            response = await self.conversation_handler.handle_conversation(
                                session_id=self.session_id,
                                user_id=self.user_id,
                                message=message
                            )
                        except Exception as e:
                            response = "I'd love to help you explore fashion! What style or type of items are you looking for today?"
                    else:
                        response = "I'd love to help you explore fashion! What style or type of items are you looking for today?"
            else:
                # Regular conversation
                if self.conversation_handler:
                    try:
                        response = await self.conversation_handler.handle_conversation(
                            session_id=self.session_id,
                            user_id=self.user_id,
                            message=message
                        )
                    except Exception as e:
                        response = f"Thanks for saying: '{message}'. I'm having some technical issues but I'm still here to chat about fashion and style!"
                else:
                    # Ultimate fallback - simple responses
                    if any(word in message.lower() for word in ["hello", "hi", "hey"]):
                        response = "Hello! I'm ARI, your fashion stylist. How can I help you look amazing today?"
                    elif any(word in message.lower() for word in ["how are you", "how's it going"]):
                        response = "I'm doing well, thank you! Ready to help you with any fashion questions you might have."
                    elif any(word in message.lower() for word in ["wedding", "dress", "outfit", "style", "fashion"]):
                        response = f"I love helping with fashion! About '{message}' - I'd suggest looking for something that makes you feel confident and comfortable. What's the occasion?"
                    else:
                        response = f"I heard you say: '{message}'. I'm ARI, your fashion assistant. Feel free to ask me about styles, outfits, or just chat!"
            
            # Update processing time
            metadata["processing_time"] = time.time() - start_time
            return response, metadata
            
        except Exception as e:
            metadata["processing_time"] = time.time() - start_time
            metadata["error"] = str(e)
            return f"I encountered an issue, but I heard: '{message}'. Can you try asking in a different way?", metadata
    
    def display_response(self, user_message: str, ari_response: str, metadata: Dict[str, Any]):
        """Display the chat interaction."""
        print("\n" + "="*60)
        print(f"YOU: {user_message}")
        print("="*60)
        print(f"ARI: {ari_response}")
        print("="*60)
        
        # Show metadata if debug mode
        if os.getenv("ARI_DEBUG"):
            print(f"METADATA: {json.dumps(metadata, indent=2, default=str)}")
            print("="*60)
        
        print()
    
    async def run_chat(self):
        """Run the interactive chat loop."""
        print("="*60)
        print("ARI Fashion Stylist - Simple Chat Interface")
        print(f"Session: {self.session_id}")
        print("="*60)
        
        # Initialize system
        await self.initialize_system()
        
        print("Welcome! I'm ARI, your fashion stylist.")
        print("Ask me about fashion, styles, or just chat!")
        print("Type 'quit' to exit, 'debug' to toggle debug mode, 'status' for system info")
        print()
        
        # Chat loop
        while True:
            try:
                # Get user input using simple input()
                message = input("You: ").strip()
                
                if not message:
                    continue
                
                if message.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                    print("\n👋 Thanks for chatting with ARI! Goodbye!\n")
                    break
                
                if message.lower() == 'debug':
                    current_debug = os.getenv("ARI_DEBUG", "")
                    if current_debug:
                        os.environ.pop("ARI_DEBUG", None)
                        print("🔍 Debug mode OFF")
                    else:
                        os.environ["ARI_DEBUG"] = "1"
                        print("🔍 Debug mode ON")
                    continue
                
                if message.lower() == 'status':
                    print("\n🔧 System Status:")
                    print(f"  Intent Detector: {'✅ Ready' if self.intent_detector else '❌ Unavailable'}")
                    print(f"  Agent Factory: {'✅ Ready' if self.agent_factory else '❌ Unavailable'}")
                    print(f"  Conversation Handler: {'✅ Ready' if self.conversation_handler else '❌ Unavailable'}")
                    print(f"  System Ready: {'✅ Yes' if self.system_ready else '❌ No'}")
                    print(f"  Messages: {self.conversation_count}")
                    continue
                
                # Process message
                print("🤖 ARI is thinking...")
                ari_response, metadata = await self.process_message(message)
                
                # Increment conversation count
                self.conversation_count += 1
                
                # Display the interaction
                self.display_response(message, ari_response, metadata)
                
            except KeyboardInterrupt:
                print("\n\n👋 Chat interrupted. Goodbye!\n")
                break
            except EOFError:
                print("\n\n👋 Input stream ended. Goodbye!\n")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                print("Continuing chat...\n")
                continue

async def main():
    """Main entry point."""
    try:
        chat = SimpleARIChat()
        await chat.run_chat()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())