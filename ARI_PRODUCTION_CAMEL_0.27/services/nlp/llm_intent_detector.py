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

from lib.camel.v070 import (
    create_agent,
    create_user_message,
    BaseMessage,
    ModelType,
    ModelPlatformType,
    CAMEL_AVAILABLE,
    OpenAIEmbedding,
    EMBEDDINGS_AVAILABLE
)

from models.types import SearchIntent
from services.nlp.fashion_knowledge import FASHION_KNOWLEDGE_BASE, get_relevant_knowledge

logger = logging.getLogger("services.nlm.llm_intent_detector")

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
        
        system_message = """You are a fashion intent detection specialist. Your job is to understand customer queries and extract structured information for a fashion recommendation system.

AVAILABLE INTENTS:
- BROWSE: Customer wants to explore options without specific requirements
- SPECIFIC_ITEM: Customer is looking for a particular type of item
- INSPIRATION: Customer wants styling ideas and suggestions  
- COMPARISON: Customer wants to compare different options
- GIFT: Customer is shopping for someone else
- OUTFIT: Customer wants coordinated pieces/complete looks
- BRAND: Customer is interested in specific brands
- SALE: Customer is looking for deals and discounts

EXTRACTION TASKS:
1. Identify the PRIMARY INTENT from the options above
2. Extract specific parameters:
   - categories: clothing/accessory types mentioned
   - occasions: events or situations mentioned
   - style_preferences: style descriptors (casual, formal, trendy, etc.)
   - colors: any colors mentioned
   - size_preferences: any sizes mentioned  
   - price_range: budget information (min/max)
   - brand_preferences: specific brands mentioned
   - materials: fabric types mentioned

RESPONSE FORMAT:
Always respond with valid JSON in this exact format:
{
  "intent": "SPECIFIC_ITEM",
  "confidence": 0.9,
  "parameters": {
    "categories": ["dress", "shoes"],
    "occasions": ["wedding"], 
    "style_preferences": ["elegant", "formal"],
    "colors": ["blue", "navy"],
    "size_preferences": ["medium"],
    "price_range": {"min": 100, "max": 300},
    "brand_preferences": ["gucci"],
    "materials": ["silk"]
  },
  "reasoning": "Customer is looking for a specific dress for a wedding, mentions elegant style and blue color preference"
}

IMPORTANT RULES:
- Use semantic understanding, not just keyword matching
- Understand synonyms and variations (e.g., "flowy" = loose/flowing, "comfy" = comfortable)
- Handle typos naturally
- Consider context and implied needs
- Only include parameters that are clearly mentioned or strongly implied
- Use empty arrays/objects for missing information
- Confidence should reflect how certain you are about the intent (0.0-1.0)"""

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
            
            # Use compatibility bridge to handle different async method names
            from lib.camel.v070 import CompatibilityBridge
            async_method = CompatibilityBridge.check_async_method(self.agent)
            
            if async_method == 'step_async':
                response = await self.agent.step_async(user_message)
            elif async_method == 'astep':
                response = await self.agent.astep(user_message)
            else:
                # Fallback to synchronous step
                response = self.agent.step(user_message)
            
            # Step 4: Parse LLM response
            # Handle different response formats in CAMEL 0.2.7
            if hasattr(response, 'content'):
                response_content = response.content
            elif hasattr(response, 'msg'):
                response_content = response.msg.content if hasattr(response.msg, 'content') else str(response.msg)
            elif hasattr(response, 'message'):
                response_content = response.message.content if hasattr(response.message, 'content') else str(response.message)
            else:
                response_content = str(response)
            
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