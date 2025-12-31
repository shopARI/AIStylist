"""
Enhanced Application Service for Streamlit Interface
Captures and exposes detailed agent outputs for real-time monitoring
"""

import logging
import time
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import json

from services.application import ApplicationService, ChatResponse
from services.battle.orchestrator import BattleOrchestrator
from services.nlp.intent_detector import IntentDetector
from services.nlp.parameter_extractor import ParameterExtractor

logger = logging.getLogger("services.streamlit_service")

class AgentMonitor:
    """Captures and stores agent outputs for real-time monitoring"""
    
    def __init__(self):
        self.outputs: List[Dict[str, Any]] = []
        self.callbacks: List[Callable] = []
        
    def log_agent_output(self, agent_name: str, stage: str, content: str, metadata: Dict = None):
        """Log an agent output"""
        output = {
            "agent_name": agent_name,
            "stage": stage,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.outputs.append(output)
        
        # Trigger callbacks
        for callback in self.callbacks:
            try:
                callback(output)
            except Exception as e:
                logger.warning(f"Callback error: {e}")
    
    def get_outputs_by_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get outputs for specific agent"""
        return [output for output in self.outputs if output["agent_name"] == agent_name]
    
    def get_latest_outputs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get latest outputs across all agents"""
        return self.outputs[-limit:] if self.outputs else []
    
    def clear_outputs(self):
        """Clear all stored outputs"""
        self.outputs.clear()
    
    def add_callback(self, callback: Callable):
        """Add a callback for real-time updates"""
        self.callbacks.append(callback)

class StreamlitApplicationService(ApplicationService):
    """Enhanced ApplicationService with detailed agent monitoring"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_monitor = AgentMonitor()
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        user_id: Optional[str] = None
    ) -> ChatResponse:
        """Process message with detailed agent monitoring"""
        start_time = time.time()
        
        self.agent_monitor.log_agent_output(
            "System", "start", f"Processing message: {message[:100]}...",
            {"session_id": session_id, "user_id": user_id}
        )
        
        # Ensure session exists
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {"history": []}
        
        try:
            # 1. Intent Detection with monitoring
            self.agent_monitor.log_agent_output(
                "IntentDetector", "analyzing", "Detecting user intent from message"
            )
            
            intent_result = await self.intent_detector.detect_intent(message)
            
            self.agent_monitor.log_agent_output(
                "IntentDetector", "result", 
                f"Primary intent: {intent_result.primary_intent} (confidence: {intent_result.confidence:.2f})",
                {"intent": intent_result.primary_intent, "confidence": intent_result.confidence}
            )
            
            # 2. Parameter Extraction with monitoring
            self.agent_monitor.log_agent_output(
                "ParameterExtractor", "analyzing", "Extracting parameters from message"
            )
            
            params = self.parameter_extractor.extract_parameters(message)
            
            self.agent_monitor.log_agent_output(
                "ParameterExtractor", "result",
                f"Extracted parameters: {json.dumps(params, indent=2)}",
                {"parameters": params}
            )
            
            intent = intent_result.primary_intent
            
            # 3. Battle System with enhanced monitoring
            self.agent_monitor.log_agent_output(
                "BattleOrchestrator", "start", 
                f"Starting agent battle for intent: {intent}"
            )
            
            # Monkey patch the battle orchestrator to capture agent outputs
            original_battle_method = self.battle_orchestrator._run_battle_process
            
            async def monitored_battle_process(*args, **kwargs):
                """Wrapper to monitor battle process"""
                try:
                    self.agent_monitor.log_agent_output(
                        "BattleOrchestrator", "battle_start", 
                        "Initializing CypherBot and VibeBot agents"
                    )
                    
                    result = await original_battle_method(*args, **kwargs)
                    
                    # Log battle results
                    if result and result.get('products'):
                        self.agent_monitor.log_agent_output(
                            "BattleOrchestrator", "battle_complete",
                            f"Battle completed. Found {len(result['products'])} products",
                            {"product_count": len(result['products'])}
                        )
                    
                    return result
                    
                except Exception as e:
                    self.agent_monitor.log_agent_output(
                        "BattleOrchestrator", "error",
                        f"Battle process error: {str(e)}"
                    )
                    raise
            
            # Temporarily replace the method
            self.battle_orchestrator._run_battle_process = monitored_battle_process
            
            try:
                battle_result = await self.battle_orchestrator.run_battle(
                    query=message,
                    intent=intent,
                    parameters=params,
                    session_id=session_id
                )
            finally:
                # Restore original method
                self.battle_orchestrator._run_battle_process = original_battle_method
            
            # Log ML Intelligence phase
            self.agent_monitor.log_agent_output(
                "Intelligence", "analyzing", 
                "Processing with ML intelligence systems"
            )
            
            # Extract ML intelligence data
            ml_intelligence = battle_result.get('ml_intelligence', {})
            
            if ml_intelligence:
                for intel_type, intel_data in ml_intelligence.items():
                    if intel_data:
                        self.agent_monitor.log_agent_output(
                            "Intelligence", f"{intel_type}_result",
                            f"{intel_type}: {json.dumps(intel_data, indent=2)[:200]}...",
                            {intel_type: intel_data}
                        )
            
            # Log Judge decision
            products = battle_result.get('products', [])
            final_decision = battle_result.get('final_decision', {})
            
            self.agent_monitor.log_agent_output(
                "Judge", "decision",
                f"Final decision: Selected {len(products)} products. " +
                f"Decision reasoning: {final_decision.get('reasoning', 'No reasoning provided')[:150]}...",
                {"product_count": len(products), "decision": final_decision}
            )
            
            # 4. Generate conversational response
            self.agent_monitor.log_agent_output(
                "ConversationHandler", "generating", 
                "Generating natural language response"
            )
            
            conversation_result = await self.conversation_handler.generate_response(
                query=message,
                intent=intent,
                parameters=params,
                battle_result=battle_result,
                session_id=session_id
            )
            
            # Prepare response
            products_list = []
            if products:
                for product in products:
                    products_list.append({
                        "id": str(product.get('id', 'unknown')),
                        "title": str(product.get('title', 'Unknown Product')),
                        "price": float(product.get('price', 0.0)) if product.get('price') else 0.0,
                        "category": str(product.get('category', 'Unknown'))
                    })
            
            # Create response
            response = ChatResponse(
                response=conversation_result.get('response', 'I apologize, but I couldn\'t generate a proper response.'),
                products=products_list,
                session_id=session_id,
                metadata={
                    'intent': intent,
                    'parameters': params,
                    'processing_time': time.time() - start_time,
                    'ml_intelligence': ml_intelligence,
                    'agent_outputs_count': len(self.agent_monitor.outputs),
                    'battle_metadata': battle_result.get('metadata', {})
                }
            )
            
            # Log completion
            processing_time = time.time() - start_time
            self.agent_monitor.log_agent_output(
                "System", "complete",
                f"Message processing completed in {processing_time:.2f}s",
                {
                    "processing_time": processing_time,
                    "response_length": len(response.response),
                    "product_count": len(response.products)
                }
            )
            
            return response
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            self.agent_monitor.log_agent_output(
                "System", "error", error_msg
            )
            
            return ChatResponse(
                response="I apologize, but I encountered an error while processing your request. Please try again.",
                products=[],
                session_id=session_id,
                metadata={'error': str(e), 'processing_time': time.time() - start_time}
            )
    
    def get_agent_outputs(self, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get agent outputs for monitoring interface"""
        if agent_name:
            return self.agent_monitor.get_outputs_by_agent(agent_name)
        return self.agent_monitor.get_latest_outputs()
    
    def clear_agent_outputs(self):
        """Clear agent output history"""
        self.agent_monitor.clear_outputs()
    
    def add_output_callback(self, callback: Callable):
        """Add callback for real-time agent output updates"""
        self.agent_monitor.add_callback(callback)