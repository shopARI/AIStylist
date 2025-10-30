"""
CrewAI-Based Intent Detector with RAG
Uses CrewAI agents for common sense reasoning (no LangChain dependency)
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time
import os

# CrewAI imports
try:
    from crewai import Agent, Task, LLM
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False

# Import from parent directory
import sys
sys.path.append('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')
from models.types import SearchIntent

# Import fashion knowledge from local nlp module
try:
    from .fashion_knowledge import FASHION_KNOWLEDGE_BASE, get_relevant_knowledge
except ImportError:
    FASHION_KNOWLEDGE_BASE = []
    def get_relevant_knowledge(query: str) -> List[str]:
        return []

logger = logging.getLogger("ari_crewai.nlp.crewai_intent_detector")

@dataclass
class CrewAIIntentResult:
    """Result from CrewAI intent detection"""
    primary_intent: SearchIntent
    confidence: float
    extracted_parameters: Dict[str, Any]
    reasoning: str
    processing_time: float
    used_knowledge: List[str]

class CrewAIIntentDetector:
    """
    CrewAI-powered intent detector with fashion domain RAG and common sense reasoning.
    Uses CrewAI agents exclusively (no LangChain).
    """

    def __init__(
        self,
        model: str = "gpt-5"
    ):
        """Initialize CrewAI intent detector"""

        if not CREWAI_AVAILABLE:
            raise RuntimeError("CrewAI not available for intent detection")

        self.model = model

        # Create CrewAI LLM
        self.llm = self._create_llm()

        # Create intent detection agent
        self.intent_agent = self._create_intent_agent()

        # Fashion knowledge base
        self.knowledge_base = FASHION_KNOWLEDGE_BASE

        logger.info(f"CrewAI Intent Detector initialized with {model}")

    def _create_llm(self):
        """Create CrewAI LLM"""
        return LLM(
            model=self.model,
            temperature=1  # GPT-5 only supports temperature=1
        )

    def _create_intent_agent(self):
        """Create CrewAI agent for intent detection"""

        return Agent(
            role="Fashion Intent Analyst",
            goal="Understand user queries using common sense and classify their intent accurately",
            backstory="""You are an expert at understanding what customers want when they talk about fashion.
You use common sense to distinguish between:
- Fashion shopping queries (they want products)
- Memory questions (they're asking about past conversations or preferences)
- System questions (they're asking how you work)
- General conversation (they're just chatting)

You're great at extracting details like colors, categories, occasions, and styles from natural language.""",
            llm=self.llm,
            verbose=False,
            allow_delegation=False
        )

    def _get_relevant_knowledge(self, query: str, top_k: int = 5) -> List[str]:
        """Get relevant fashion knowledge for RAG context"""

        # Simple keyword-based matching
        query_words = query.lower().split()
        relevant_knowledge = []

        for entry in self.knowledge_base:
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

    async def detect_intent_and_extract(self, query: str) -> CrewAIIntentResult:
        """
        Main method: detect intent and extract parameters using CrewAI agent + common sense

        Args:
            query: User's natural language query

        Returns:
            CrewAIIntentResult with intent, parameters, and metadata
        """
        start_time = time.time()

        try:
            # Step 1: Get relevant fashion knowledge for context
            relevant_knowledge = self._get_relevant_knowledge(query)

            # Step 2: Build context-enhanced prompt with common sense reasoning
            knowledge_context = ""
            if relevant_knowledge:
                knowledge_context = "\n\nFASHION KNOWLEDGE CONTEXT:\n" + "\n".join(relevant_knowledge[:3])

            # Step 3: Create task for intent detection
            task_description = self._build_task_description(query, knowledge_context)

            task = Task(
                description=task_description,
                agent=self.intent_agent,
                expected_output="JSON object with intent, confidence, parameters, and reasoning"
            )

            # Step 4: Execute task
            result = await asyncio.to_thread(task.execute_sync)

            # Step 5: Parse result
            parsed_result = self._parse_agent_response(result, query, relevant_knowledge)
            parsed_result.processing_time = time.time() - start_time

            logger.debug(f"CrewAI intent detection completed in {parsed_result.processing_time:.2f}s")
            return parsed_result

        except Exception as e:
            logger.error(f"CrewAI intent detection failed: {e}", exc_info=True)
            return self._fallback_result(start_time)

    def _build_task_description(self, query: str, knowledge_context: str) -> str:
        """Build task description with common sense instructions"""

        return f"""Analyze this customer query using COMMON SENSE and classify the intent.

CUSTOMER QUERY: "{query}"{knowledge_context}

INTENTS (choose the most appropriate):
- SPECIFIC_ITEM: User wants specific clothing/accessories ("black shirt", "need shoes", "dress for wedding")
- BROWSE: User wants to explore options ("show me clothes", "what do you have")
- INSPIRATION: User needs outfit ideas/advice ("what should I wear for", "outfit for interview")
- CONVERSATION_HISTORY: User asks about past conversation ("what did I ask", "earlier you said")
- MEMORY_QUERY: User asks about remembered preferences ("do you remember my size", "my favorite color")
- CLARIFICATION: User asks ME to explain MY fashion system/features ("how do you work", "explain your agents")
- GENERAL_CONVERSATION: Clearly non-fashion topics (weather, physics, current events, casual chat)
- GIFT: Shopping for someone else ("gift for my mom", "birthday present")
- OUTFIT: Complete outfit request ("outfit for interview", "what goes with this")
- BRAND: Brand-specific search ("show me Nike", "anything from Zara")
- SALE: Looking for deals ("on sale", "discount", "cheap")
- COMPARISON: Comparing options ("which is better", "compare these")

COMMON SENSE DECISION MAKING:
1. Is this about fashion, clothing, or shopping?  Use fashion intents (SPECIFIC_ITEM, BROWSE, INSPIRATION)
2. Is this asking about our past conversation?  CONVERSATION_HISTORY
3. Is this asking about their stored preferences?  MEMORY_QUERY
4. Is this asking me to explain how I work?  CLARIFICATION
5. Is this completely unrelated to fashion?  GENERAL_CONVERSATION

EXAMPLES:
- "what day is it"  GENERAL_CONVERSATION (not fashion related)
- "explain quantum physics"  GENERAL_CONVERSATION (not fashion related)
- "how do you work"  CLARIFICATION (asking about my system)
- "do you remember my size"  MEMORY_QUERY (asking about stored info)
- "what did I ask earlier"  CONVERSATION_HISTORY (about past conversation)
- "need a black shirt"  SPECIFIC_ITEM (fashion item)
- "outfit for interview"  INSPIRATION (fashion advice)
- "gift for mom"  GIFT (shopping for someone)
- "anything on sale"  SALE (looking for deals)

For fashion queries, extract FROM THE CUSTOMER QUERY ONLY: categories, colors, occasions, style_preferences, price_range, brand_preferences
**IMPORTANT:** DO NOT extract parameters from the FASHION KNOWLEDGE CONTEXT - only from the CUSTOMER QUERY!
For non-fashion queries, leave parameters empty.

RESPOND WITH VALID JSON:
{{
  "intent": "SPECIFIC_ITEM",
  "confidence": 0.95,
  "parameters": {{
    "categories": ["shirts"],
    "colors": ["black"],
    "occasions": ["interview"]
  }},
  "reasoning": "User needs specific black shirt for professional interview setting"
}}"""

    def _parse_agent_response(
        self,
        response: str,
        original_query: str,
        used_knowledge: List[str]
    ) -> CrewAIIntentResult:
        """Parse CrewAI agent response into structured result"""

        try:
            # Extract JSON from response
            response_str = str(response).strip()

            # Handle potential markdown code blocks
            if "```json" in response_str:
                start = response_str.find("```json") + 7
                end = response_str.find("```", start)
                json_str = response_str[start:end].strip()
            elif "```" in response_str:
                start = response_str.find("```") + 3
                end = response_str.rfind("```")
                json_str = response_str[start:end].strip()
            else:
                json_str = response_str

            # Parse JSON
            result = json.loads(json_str)

            # Map intent string to enum
            intent_str = result.get("intent", "BROWSE").upper()
            try:
                primary_intent = SearchIntent[intent_str]
            except KeyError:
                logger.warning(f"Unknown intent '{intent_str}', using BROWSE")
                primary_intent = SearchIntent.BROWSE

            return CrewAIIntentResult(
                primary_intent=primary_intent,
                confidence=float(result.get("confidence", 0.5)),
                extracted_parameters=result.get("parameters", {}),
                reasoning=result.get("reasoning", "CrewAI agent analysis completed"),
                processing_time=0.0,  # Will be set by caller
                used_knowledge=[k[:100] + "..." for k in used_knowledge]  # Truncate for logging
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse CrewAI response: {e}")
            logger.debug(f"Raw response: {response}")

            # Fallback result
            return CrewAIIntentResult(
                primary_intent=SearchIntent.BROWSE,
                confidence=0.2,
                extracted_parameters={},
                reasoning=f"Failed to parse agent response: {str(e)}",
                processing_time=0.0,
                used_knowledge=[]
            )

    def _fallback_result(self, start_time: float) -> CrewAIIntentResult:
        """Fallback result when CrewAI fails"""
        return CrewAIIntentResult(
            primary_intent=SearchIntent.BROWSE,
            confidence=0.1,
            extracted_parameters={},
            reasoning="CrewAI processing error, using fallback",
            processing_time=time.time() - start_time,
            used_knowledge=[]
        )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            "model": self.model,
            "knowledge_entries": len(self.knowledge_base),
            "framework": "CrewAI"
        }


# Global instance
_crewai_intent_detector: Optional[CrewAIIntentDetector] = None


def get_crewai_intent_detector() -> CrewAIIntentDetector:
    """Get singleton CrewAI intent detector instance"""
    global _crewai_intent_detector

    if _crewai_intent_detector is None:
        _crewai_intent_detector = CrewAIIntentDetector()

    return _crewai_intent_detector


# Export
__all__ = [
    'CrewAIIntentDetector',
    'CrewAIIntentResult',
    'get_crewai_intent_detector'
]
