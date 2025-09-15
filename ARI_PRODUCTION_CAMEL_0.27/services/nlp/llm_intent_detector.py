"""
LLM-based Intent Detector with RAG using CAMEL-AI 0.2.7
Replaces hardcoded pattern matching with semantic understanding
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import time

# Direct CAMEL 0.2.7 imports
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType
try:
    import camel
    CAMEL_AVAILABLE = True
    from camel.embeddings import OpenAIEmbedding
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    CAMEL_AVAILABLE = False
    EMBEDDINGS_AVAILABLE = False

from models.types import SearchIntent
from services.nlp.fashion_knowledge import FASHION_KNOWLEDGE_BASE, get_relevant_knowledge

logger = logging.getLogger("services.nlm.llm_intent_detector")

def create_agent(system_message: str, model_type=ModelType.GPT_4O_MINI, temperature=0.7, max_tokens=4000):
    '''Helper to create agents with CAMEL 0.2.7 API'''
    
    # Always create model first
    model = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=model_type,
        model_config_dict={
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    )
    
    # Create system message
    system_msg = BaseMessage.make_assistant_message(
        role_name="System",
        content=system_message
    )
    
    # Create agent with model
    agent = ChatAgent(
        system_message=system_msg,
        model=model
    )
    
    return agent

def create_user_message(content: str):
    '''Helper to create user messages with CAMEL 0.2.7 API'''
    return BaseMessage.make_user_message(
        role_name="User",
        content=content
    )

@dataclass
class LLMIntentResult:
    """Result from LLM intent detection"""
    primary_intent: SearchIntent
    confidence: float
    extracted_parameters: Dict[str, Any]
    reasoning: str
    processing_time: float
    used_knowledge: List[str]

class LLMIntentDetector:
    """
    LLM-powered intent detector with fashion domain RAG.
    Uses CAMEL-AI 0.2.7 for natural language understanding.
    """
    
    def __init__(
        self,
        model_type: ModelType = ModelType.GPT_4O_MINI,
        temperature: float = 0.3,  # Lower for more consistent structured output
        max_tokens: int = 2000
    ):
        """Initialize LLM intent detector with CAMEL agent"""
        
        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL-AI not available for LLM intent detection")
        
        self.model_type = model_type
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Create CAMEL agent for intent detection
        self.agent = self._create_intent_agent()
        
        # Fashion knowledge embeddings (for RAG)
        self.knowledge_embeddings = None
        self.embedding_model = None
        
        if EMBEDDINGS_AVAILABLE:
            try:
                self._initialize_embeddings()
                logger.info("Fashion knowledge embeddings initialized")
            except Exception as e:
                logger.warning(f"Could not initialize embeddings: {e}, using keyword matching")
        
        logger.info(f"LLM Intent Detector initialized with {model_type}")
    
    def _create_intent_agent(self):
        """Create CAMEL agent specialized for fashion intent detection"""
        
        system_message = """You understand customer queries for a fashion shopping system using common sense.

INTENTS:
- SPECIFIC_ITEM: Looking for specific clothing/accessories ("black shirt", "need shoes", "want a dress")
- BROWSE: Exploring options ("show me clothes", "what do you have")
- INSPIRATION: Style ideas ("outfit ideas", "what should I wear")
- CONVERSATION_HISTORY: About past conversation ("what did I ask earlier")
- MEMORY_QUERY: About remembered info ("do you remember my size")
- CLARIFICATION: Asking to explain ("what do you mean")
- GENERAL_CONVERSATION: Non-shopping chat

COMMON SENSE RULES:
- If someone mentions clothing items → SPECIFIC_ITEM
- If they ask about memory/history → Use memory intents  
- If they're just chatting → GENERAL_CONVERSATION

Extract: categories, colors, occasions, style_preferences, price_range, brand_preferences

ALWAYS respond with valid JSON:
{
  "intent": "SPECIFIC_ITEM",
  "confidence": 0.9,
  "parameters": {
    "categories": ["shirt"],
    "colors": ["black"]
  },
  "reasoning": "User wants a black shirt"
}"""

        return create_agent(
            system_message=system_message,
            model_type=self.model_type,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
    
    def _initialize_embeddings(self):
        """Initialize embeddings for fashion knowledge RAG"""
        if not EMBEDDINGS_AVAILABLE:
            return
            
        try:
            self.embedding_model = OpenAIEmbedding()
            
            # Create embeddings for fashion knowledge
            knowledge_texts = [entry["content"] for entry in FASHION_KNOWLEDGE_BASE]
            self.knowledge_embeddings = {
                i: knowledge_texts[i] 
                for i in range(len(knowledge_texts))
            }
            
            logger.debug(f"Initialized embeddings for {len(knowledge_texts)} knowledge entries")
            
        except Exception as e:
            logger.error(f"Embedding initialization failed: {e}")
            self.embedding_model = None
            self.knowledge_embeddings = None
    
    def _get_relevant_knowledge(self, query: str, top_k: int = 5) -> List[str]:
        """Get relevant fashion knowledge for RAG context"""
        
        # Simple keyword-based matching as fallback
        query_words = query.lower().split()
        relevant_knowledge = []
        
        for entry in FASHION_KNOWLEDGE_BASE:
            entry_keywords = entry.get("keywords", [])
            content = entry["content"]
            
            # Check for keyword overlap
            if any(keyword.lower() in query_words for keyword in entry_keywords):
                relevant_knowledge.append(content)
            
            # Also check direct word overlap in content
            elif any(word in content.lower() for word in query_words if len(word) > 3):
                relevant_knowledge.append(content)
        
        # Return top matches
        return relevant_knowledge[:top_k]
    
    async def detect_intent_and_extract(self, query: str) -> LLMIntentResult:
        """
        Main method: detect intent and extract parameters using LLM + RAG
        
        Args:
            query: User's natural language query
            
        Returns:
            LLMIntentResult with intent, parameters, and metadata
        """
        start_time = time.time()
        
        try:
            # Step 1: Get relevant fashion knowledge for context
            relevant_knowledge = self._get_relevant_knowledge(query)
            
            # Step 2: Build context-enhanced prompt
            knowledge_context = ""
            if relevant_knowledge:
                knowledge_context = "\\n\\nFASHION KNOWLEDGE CONTEXT:\\n" + "\\n".join(relevant_knowledge[:3])
            
            enhanced_query = f"""CUSTOMER QUERY: "{query}"{knowledge_context}

Please analyze this fashion query and extract the structured information as JSON."""
            
            # Step 3: Send to LLM agent
            user_message = create_user_message(enhanced_query)
            
            # Use CAMEL 0.2.7 agent methods directly
            if hasattr(self.agent, 'step_async'):
                response = await self.agent.step_async(user_message)
            elif hasattr(self.agent, 'astep'):
                response = await self.agent.astep(user_message)
            else:
                # Fallback to synchronous step
                response = self.agent.step(user_message)
            
            # Step 4: Parse LLM response
            # Handle CAMEL 0.2.7 response format
            if hasattr(response, 'msgs') and response.msgs:
                # CAMEL 0.2.7 returns msgs list, get the last message
                last_msg = response.msgs[-1]
                if hasattr(last_msg, 'content'):
                    response_content = last_msg.content
                else:
                    response_content = str(last_msg)
            elif hasattr(response, 'content'):
                response_content = response.content
            elif hasattr(response, 'message'):
                response_content = response.message.content if hasattr(response.message, 'content') else str(response.message)
            else:
                response_content = str(response)
            
            # Debug logging
            logger.debug(f"LLM raw response type: {type(response)}")
            logger.debug(f"LLM response content length: {len(response_content)}")
            logger.debug(f"LLM response content: '{response_content[:200]}...' (truncated)")
            
            # Check for empty response
            if not response_content or len(response_content.strip()) == 0:
                logger.error("LLM returned empty response")
                return LLMIntentResult(
                    primary_intent=SearchIntent.BROWSE,
                    confidence=0.1,
                    extracted_parameters={},
                    reasoning="LLM returned empty response",
                    processing_time=time.time() - start_time,
                    used_knowledge=[]
                )
            
            result = self._parse_llm_response(response_content, query, relevant_knowledge)
            result.processing_time = time.time() - start_time
            
            logger.debug(f"LLM intent detection completed in {result.processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"LLM intent detection failed: {e}", exc_info=True)
            
            # Return fallback result
            return LLMIntentResult(
                primary_intent=SearchIntent.BROWSE,
                confidence=0.1,
                extracted_parameters={},
                reasoning=f"Error in LLM processing: {str(e)}",
                processing_time=time.time() - start_time,
                used_knowledge=[]
            )
    
    def _parse_llm_response(
        self, 
        response_content: str, 
        original_query: str,
        used_knowledge: List[str]
    ) -> LLMIntentResult:
        """Parse LLM JSON response into structured result"""
        
        try:
            # Extract JSON from response
            response_content = response_content.strip()
            
            # Handle potential markdown code blocks
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                json_str = response_content[start:end].strip()
            elif "```" in response_content:
                start = response_content.find("```") + 3
                end = response_content.rfind("```")
                json_str = response_content[start:end].strip()
            else:
                json_str = response_content
            
            # Parse JSON
            llm_result = json.loads(json_str)
            
            # Map intent string to enum
            intent_str = llm_result.get("intent", "BROWSE").upper()
            try:
                primary_intent = SearchIntent[intent_str]
            except KeyError:
                logger.warning(f"Unknown intent '{intent_str}', using BROWSE")
                primary_intent = SearchIntent.BROWSE
            
            return LLMIntentResult(
                primary_intent=primary_intent,
                confidence=float(llm_result.get("confidence", 0.5)),
                extracted_parameters=llm_result.get("parameters", {}),
                reasoning=llm_result.get("reasoning", "LLM analysis completed"),
                processing_time=0.0,  # Will be set by caller
                used_knowledge=[k[:100] + "..." for k in used_knowledge]  # Truncate for logging
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response: {response_content}")
            
            # Fallback result
            return LLMIntentResult(
                primary_intent=SearchIntent.BROWSE,
                confidence=0.2,
                extracted_parameters={},
                reasoning=f"Failed to parse LLM response: {str(e)}",
                processing_time=0.0,
                used_knowledge=[]
            )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            "model_type": self.model_type.name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "embeddings_available": EMBEDDINGS_AVAILABLE,
            "knowledge_entries": len(FASHION_KNOWLEDGE_BASE)
        }


# Global instance for hybrid usage
_llm_intent_detector: Optional[LLMIntentDetector] = None


def get_llm_intent_detector() -> LLMIntentDetector:
    """Get singleton LLM intent detector instance"""
    global _llm_intent_detector
    
    if _llm_intent_detector is None:
        _llm_intent_detector = LLMIntentDetector()
    
    return _llm_intent_detector


# Export for hybrid integration
__all__ = [
    'LLMIntentDetector',
    'LLMIntentResult', 
    'get_llm_intent_detector'
]