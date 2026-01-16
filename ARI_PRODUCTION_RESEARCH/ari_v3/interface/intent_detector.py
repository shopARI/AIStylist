"""
ARI V3 - Intent Detector

Hybrid intent detection using rules + LLM.
Based on Section 0.5.1 of the pseudocode.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from .types import (
    ExtractedParameters,
    IntentResult,
    QueryType,
    SearchIntent,
)
from .parameter_extractor import ParameterExtractor, get_parameter_extractor

logger = logging.getLogger(__name__)

# Thread lock for singleton
_detector_lock = threading.Lock()


class DetectionStrategy(str, Enum):
    """Strategy for combining rule-based and LLM detection."""
    RULE_FIRST = "rule_first"       # Try rules, fall back to LLM
    LLM_FIRST = "llm_first"         # Try LLM, fall back to rules
    HYBRID = "hybrid"               # Use both and combine


@dataclass
class RuleDetectionResult:
    """Result from rule-based detection."""
    intent: SearchIntent
    confidence: float
    matched_patterns: List[str]


class IntentDetector:
    """
    Rule-based intent detector.

    Uses pattern matching to classify user intent.
    Prioritizes conversation intents over product intents.
    """

    def __init__(self):
        """Initialize with intent patterns."""

        # Intent patterns - CONVERSATION INTENTS FIRST (higher priority)
        self.intent_patterns: Dict[SearchIntent, List[str]] = {
            # Conversation/Memory Intents - CHECK THESE FIRST
            SearchIntent.GREETING: [
                # Only match short greetings, not "hey what should I wear"
                r"^hi[!?,.\s]*$", r"^hello[!?,.\s]*$", r"^hey[!?,.\s]*$",
                r"^hi there[!?,.\s]*$", r"^hello there[!?,.\s]*$", r"^hey there[!?,.\s]*$",
                r"^good morning[!?,.\s]*$", r"^good afternoon[!?,.\s]*$", r"^good evening[!?,.\s]*$",
                r"^greetings[!?,.\s]*$", r"^howdy[!?,.\s]*$",
                r"^how are you", r"^what's up[!?,.\s]*$",
            ],
            SearchIntent.GOODBYE: [
                r"\bbye\b", r"\bgoodbye\b", r"\bsee you\b", r"\bthanks?\b$",
                r"\bthank you\b$", r"\bthat's all\b", r"\bdone\b$",
                r"\bexit\b$", r"\bquit\b$",
            ],
            SearchIntent.CONVERSATION_HISTORY: [
                r"what did i ask", r"what did i say", r"what did i tell you",
                r"my first question", r"earlier i asked", r"at the beginning",
                r"what were we talking about", r"before this",
                r"what was my original", r"remember what we discussed",
                r"what did i look for before", r"show my past searches",
                r"past searches", r"earlier searches", r"search history",
            ],
            SearchIntent.MEMORY_QUERY: [
                r"do you remember", r"you know i like", r"recall my",
                r"you mentioned earlier", r"i told you before",
                r"my favorite", r"my preferred", r"what's my favorite",
                r"what's my preferred", r"remember my preferences",
                r"what i like", r"my style.*remember",
                r"what did i (?:look at|see|view|browse)",
                r"(?:show|tell) me what i (?:looked at|saw|viewed)",
                r"what (?:was|were) i looking at",
                # Time references ONLY with look/view/search context
                r"(?:looked at|viewed|searched|browsed).*(?:yesterday|last time|before|earlier)",
                r"(?:yesterday|last time|earlier).*(?:looked at|viewed|searched|browsed)",
            ],
            SearchIntent.CLARIFICATION: [
                r"what do you mean", r"can you explain", r"i don't understand",
                r"tell me more about", r"elaborate on", r"what exactly",
                r"i'm confused", r"that doesn't make sense", r"can you clarify",
                r"why did you recommend", r"why this", r"how come",
            ],
            SearchIntent.SYSTEM_STATUS: [
                r"how do you find products", r"what's your process",
                r"how does this work", r"what can you do", r"how smart are you",
                r"what's your memory", r"tell me about yourself",
                r"what are you", r"who are you",
            ],
            SearchIntent.GENERAL_CONVERSATION: [
                r"nice weather", r"how are you doing", r"good morning",
                r"hello there", r"thanks for", r"that's interesting",
                r"cool story", r"talk a little", r"let's chat",
                r"tell me something", r"how's your day",
            ],
            # Product Search Intents - CHECK AFTER CONVERSATION INTENTS
            SearchIntent.BROWSE: [
                r"show me", r"browse", r"what do you have",
                r"explore", r"see what", r"looking around",
            ],
            SearchIntent.SPECIFIC_ITEM: [
                r"looking for (?:a |an )?(\w+)",
                r"need (?:a |an )?(\w+)",
                r"want (?:a |an )?(\w+)",
                r"find me (?:a |an )?(\w+)",
                r"search for (?:a |an )?(\w+)",
                r"where can i find",
                r"i'd like (?:a |an )?(\w+)",
                r"could you (?:help me )?find",
                r"recommend (?:some |a |an )?(\w+)",
                r"suggest (?:some |a |an )?(\w+)",
                # Color + item patterns
                r"\b(?:black|white|red|blue|green|navy|gray|grey)\s+(?:shirt|dress|pants|jacket|shoes)",
            ],
            SearchIntent.INSPIRATION: [
                r"inspire me", r"inspiration", r"ideas for",
                r"what should i wear", r"help me choose", r"not sure what",
                r"outfit ideas", r"what to wear", r"clothing recommendations",
                r"fashion advice", r"dress code", r"style suggestions",
            ],
            SearchIntent.PRODUCT_COMPARISON: [
                r"compare", r"difference between", r"versus", r"vs\.",
                r"better than", r"which is better", r"contrast",
            ],
            SearchIntent.GIFT: [
                r"gift", r"present", r"for my \w+", r"for someone",
                r"birthday", r"anniversary", r"special occasion",
            ],
            SearchIntent.OUTFIT_BUILDING: [
                r"outfit", r"complete look", r"goes with", r"match with",
                r"coordinate", r"style with", r"wear together",
                r"full look", r"entire ensemble", r"matching set",
            ],
            SearchIntent.BRAND: [
                r"from (\w+)", r"by (\w+)", r"(\w+) brand",
                r"\b(nike|adidas|gucci|zara|h&m|uniqlo)\b",
            ],
            SearchIntent.SALE: [
                r"sale", r"discount", r"deal", r"clearance",
                r"bargain", r"under \$\d+", r"cheap", r"affordable",
            ],
            SearchIntent.FEEDBACK: [
                r"i like", r"i love", r"i hate", r"don't like",
                r"perfect", r"terrible", r"not my style",
            ],
        }

        # Query type patterns
        self.query_type_patterns: Dict[QueryType, List[str]] = {
            QueryType.GREETING: [
                # Only match short greetings without product queries following
                r"^(hi|hello|hey|good morning|good afternoon|good evening)[!?,.\s]*$",
                r"^how are you[!?,.\s]*$", r"^what's up[!?,.\s]*$",
            ],
            QueryType.QUESTION: [
                r"^(what|when|where|who|why|how) ",
                r"\?$",
            ],
            QueryType.COMMAND: [
                r"^(show|find|get|search|look|give me|bring me)",
                r"^(filter|sort|order)",
            ],
            QueryType.FEEDBACK: [
                r"(like|love|hate|don't like)",
                r"(perfect|great|terrible|awful|amazing)",
            ],
            QueryType.CONVERSATION: [
                r"tell me", r"i think", r"in my opinion", r"what do you think",
            ],
        }

        logger.info("IntentDetector initialized with patterns")

    async def detect_intent(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        """
        Detect intent from user query using rules.

        Args:
            query: User query string
            conversation_history: Recent conversation (optional)

        Returns:
            IntentResult
        """
        start_time = time.time()
        query_lower = query.lower().strip()

        # Detect query type
        query_type = self._detect_query_type(query_lower)

        # Detect primary intent
        rule_result = self._detect_primary_intent(query_lower)

        # Extract parameters
        extractor = get_parameter_extractor()
        params = extractor.extract(query)

        processing_time = time.time() - start_time

        return IntentResult(
            primary_intent=rule_result.intent,
            confidence=rule_result.confidence,
            detection_method="rule",
            extracted_parameters=params,
            query_type=query_type,
            reasoning=f"Matched patterns: {rule_result.matched_patterns}",
            processing_time=processing_time,
        )

    def _detect_query_type(self, query: str) -> QueryType:
        """Detect the type of query."""
        for query_type, patterns in self.query_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return query_type

        # Default based on content
        if len(query.split()) > 15:
            return QueryType.CONVERSATION
        return QueryType.SEARCH

    def _detect_primary_intent(self, query: str) -> RuleDetectionResult:
        """Detect primary search intent using rules with improved scoring."""
        intent_scores: Dict[SearchIntent, float] = {}
        matched_patterns: Dict[SearchIntent, List[str]] = {}

        for intent, patterns in self.intent_patterns.items():
            matches = []
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    matches.append(pattern)

            if matches:
                # Improved scoring: base confidence + bonus for multiple matches
                # This doesn't penalize intents with more patterns
                base_confidence = 0.5  # Base confidence for any match
                match_bonus = min(len(matches) * 0.15, 0.4)  # Up to 0.4 bonus for multiple matches
                score = base_confidence + match_bonus
                intent_scores[intent] = score
                matched_patterns[intent] = matches

        # Boost conversation intents (they should take priority when matched)
        conversation_intents = [
            SearchIntent.GREETING,
            SearchIntent.GOODBYE,
            SearchIntent.CONVERSATION_HISTORY,
            SearchIntent.MEMORY_QUERY,
            SearchIntent.CLARIFICATION,
            SearchIntent.SYSTEM_STATUS,
            SearchIntent.GENERAL_CONVERSATION,
            SearchIntent.FEEDBACK,
        ]
        for intent in conversation_intents:
            if intent in intent_scores and intent_scores[intent] > 0:
                intent_scores[intent] += 0.2  # Absolute boost, not multiplicative

        # Get highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            return RuleDetectionResult(
                intent=best_intent[0],
                confidence=min(best_intent[1], 1.0),
                matched_patterns=matched_patterns.get(best_intent[0], []),
            )

        # Default to browse
        return RuleDetectionResult(
            intent=SearchIntent.BROWSE,
            confidence=0.3,
            matched_patterns=[],
        )


class HybridIntentDetector:
    """
    Hybrid intent detector combining rules and LLM.

    Based on pseudocode Section 0.5.1.
    Uses rule-based detection first, falls back to LLM for ambiguous cases.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        strategy: DetectionStrategy = DetectionStrategy.RULE_FIRST,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize hybrid detector.

        Args:
            openai_api_key: OpenAI API key (uses env var if not provided)
            model: LLM model to use
            strategy: Detection strategy
            confidence_threshold: Threshold for rule confidence before using LLM
        """
        self.rule_detector = IntentDetector()
        self.extractor = get_parameter_extractor()
        self.model = model
        self.strategy = strategy
        self.confidence_threshold = confidence_threshold

        # Initialize OpenAI client
        import os
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = AsyncOpenAI(api_key=api_key)
        else:
            self.openai_client = None
            logger.warning("No OpenAI API key provided, LLM detection disabled")

        logger.info(
            f"HybridIntentDetector initialized with strategy={strategy.value}, "
            f"model={model}, threshold={confidence_threshold}"
        )

    async def detect_intent(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        """
        Detect intent using hybrid approach.

        Args:
            query: User query string
            conversation_history: Recent conversation history

        Returns:
            IntentResult
        """
        start_time = time.time()

        if self.strategy == DetectionStrategy.RULE_FIRST:
            result = await self._detect_rule_first(query, conversation_history)
        elif self.strategy == DetectionStrategy.LLM_FIRST:
            result = await self._detect_llm_first(query, conversation_history)
        else:
            result = await self._detect_hybrid(query, conversation_history)

        result.processing_time = time.time() - start_time
        return result

    async def _detect_rule_first(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        """Try rules first, fall back to LLM if low confidence."""
        rule_result = await self.rule_detector.detect_intent(query, conversation_history)

        if rule_result.confidence >= self.confidence_threshold:
            return rule_result

        # Low confidence, try LLM
        if self.openai_client:
            try:
                llm_result = await self._detect_with_llm(query, conversation_history)
                if llm_result.confidence > rule_result.confidence:
                    return llm_result
            except Exception as e:
                logger.warning(f"LLM detection failed, using rule result: {e}")

        return rule_result

    async def _detect_llm_first(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        """Try LLM first, fall back to rules."""
        if self.openai_client:
            try:
                return await self._detect_with_llm(query, conversation_history)
            except Exception as e:
                logger.warning(f"LLM detection failed, using rules: {e}")

        return await self.rule_detector.detect_intent(query, conversation_history)

    async def _detect_hybrid(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        """Use both methods and combine results."""
        rule_result = await self.rule_detector.detect_intent(query, conversation_history)

        if not self.openai_client:
            return rule_result

        try:
            llm_result = await self._detect_with_llm(query, conversation_history)

            # If they agree, boost confidence
            if rule_result.primary_intent == llm_result.primary_intent:
                combined_confidence = min(
                    (rule_result.confidence + llm_result.confidence) / 2 + 0.1,
                    1.0
                )
                return IntentResult(
                    primary_intent=rule_result.primary_intent,
                    confidence=combined_confidence,
                    detection_method="hybrid",
                    extracted_parameters=llm_result.extracted_parameters,
                    query_type=rule_result.query_type,
                    reasoning=f"Rule and LLM agree: {llm_result.reasoning}",
                )

            # If they disagree, use higher confidence
            if llm_result.confidence > rule_result.confidence:
                return llm_result
            return rule_result

        except Exception as e:
            logger.warning(f"LLM detection failed in hybrid mode: {e}")
            return rule_result

    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Robustly extract JSON from LLM response.

        Handles various formats:
        - Plain JSON
        - Markdown code blocks (```json ... ``` or ``` ... ```)
        - JSON with surrounding text
        - Nested braces

        Args:
            response_text: Raw LLM response

        Returns:
            Extracted JSON string

        Raises:
            ValueError: If no valid JSON found
        """
        text = response_text.strip()

        # Strategy 1: Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.rfind("```")
            if end > start:
                candidate = text[start:end].strip()
                # Skip language identifier if present (e.g., "json\n{...")
                if candidate and not candidate.startswith("{"):
                    newline_pos = candidate.find("\n")
                    if newline_pos != -1:
                        candidate = candidate[newline_pos + 1:].strip()
                if candidate.startswith("{"):
                    return candidate

        # Strategy 2: Find JSON object by matching braces
        brace_start = text.find("{")
        if brace_start != -1:
            depth = 0
            in_string = False
            escape_next = False
            end_pos = -1

            for i, char in enumerate(text[brace_start:], start=brace_start):
                if escape_next:
                    escape_next = False
                    continue

                if char == "\\":
                    escape_next = True
                    continue

                if char == '"':
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            end_pos = i + 1
                            break

            if end_pos != -1:
                return text[brace_start:end_pos]

        # Strategy 3: If all else fails, return the text as-is for json.loads to handle
        raise ValueError(f"Could not extract valid JSON from response: {text[:200]}...")

    async def _detect_with_llm(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        """Detect intent using LLM."""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized")

        # Build conversation context
        conversation_context = ""
        if conversation_history:
            context_items = []
            for msg in conversation_history[-3:]:
                role = msg.get('role', 'user').upper()
                content = msg.get('content', '')[:150]
                context_items.append(f"{role}: {content}")
            if context_items:
                conversation_context = "\n\nRECENT CONVERSATION:\n" + "\n".join(context_items)

        # Build prompt
        prompt = f"""Classify this user message and extract relevant parameters.
{conversation_context}

CURRENT MESSAGE: "{query}"

INTENTS (choose the most appropriate):
- GREETING: User is greeting ("hi", "hello")
- GOODBYE: User is ending conversation
- PRODUCT_SEARCH: User wants to find/browse products
- SPECIFIC_ITEM: User wants a specific item ("black dress", "running shoes")
- STYLE_ADVICE: User wants styling help
- INSPIRATION: User wants outfit ideas
- OUTFIT_BUILDING: User wants to build a complete outfit
- GIFT: Shopping for someone else
- BRAND: Specific brand search
- SALE: Looking for deals
- GENERAL_CONVERSATION: User wants to chat, not shop
- MEMORY_QUERY: User asking about past interactions
- CONVERSATION_HISTORY: User asking about this conversation
- CLARIFICATION: User asking why/how about recommendations
- SYSTEM_STATUS: User asking about capabilities
- FEEDBACK: User giving feedback on items

Output JSON:
{{
    "intent": "<INTENT_NAME>",
    "confidence": <0.0-1.0>,
    "categories": ["list of clothing categories mentioned"],
    "colors": ["list of colors mentioned"],
    "occasions": ["list of occasions mentioned"],
    "reasoning": "<brief reasoning>"
}}"""

        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an intent classifier for a fashion shopping assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3,
        )

        response_text = response.choices[0].message.content.strip()

        # Parse JSON response with robust extraction
        try:
            json_str = self._extract_json_from_response(response_text)
            result = json.loads(json_str)

            # Map intent string to enum
            intent_str = result.get("intent", "BROWSE").upper()
            try:
                primary_intent = SearchIntent[intent_str]
            except KeyError:
                # Try mapping common variations
                intent_mapping = {
                    "SEARCH": SearchIntent.PRODUCT_SEARCH,
                    "CHAT": SearchIntent.GENERAL_CONVERSATION,
                    "CONVERSATION": SearchIntent.GENERAL_CONVERSATION,
                }
                primary_intent = intent_mapping.get(intent_str, SearchIntent.BROWSE)

            # Build extracted parameters
            params = ExtractedParameters(
                categories=result.get("categories", []),
                colors=result.get("colors", []),
                occasions=result.get("occasions", []),
            )

            return IntentResult(
                primary_intent=primary_intent,
                confidence=float(result.get("confidence", 0.5)),
                detection_method="llm",
                extracted_parameters=params,
                reasoning=result.get("reasoning", "LLM classification"),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise RuntimeError(f"Failed to parse LLM response: {e}")


# Singleton instance with strategy tracking
_detector_instance: Optional[HybridIntentDetector] = None
_detector_strategy: Optional[DetectionStrategy] = None


def get_intent_detector(
    strategy: DetectionStrategy = DetectionStrategy.RULE_FIRST,
    force_new: bool = False,
) -> HybridIntentDetector:
    """
    Get thread-safe singleton intent detector instance.

    If called with a different strategy than the existing instance,
    a new instance will be created with the new strategy.

    Args:
        strategy: Detection strategy to use
        force_new: Force creation of a new instance (useful for testing)

    Returns:
        HybridIntentDetector instance
    """
    global _detector_instance, _detector_strategy

    # Fast path: instance exists with same strategy
    if (
        not force_new
        and _detector_instance is not None
        and _detector_strategy == strategy
    ):
        return _detector_instance

    # Slow path: need to create or recreate
    with _detector_lock:
        # Double-check after acquiring lock
        if (
            not force_new
            and _detector_instance is not None
            and _detector_strategy == strategy
        ):
            return _detector_instance

        # Log if recreating due to strategy change
        if _detector_instance is not None and _detector_strategy != strategy:
            logger.info(
                f"Recreating IntentDetector: strategy changed from "
                f"{_detector_strategy.value if _detector_strategy else 'None'} to {strategy.value}"
            )

        _detector_instance = HybridIntentDetector(strategy=strategy)
        _detector_strategy = strategy
        return _detector_instance


def reset_intent_detector() -> None:
    """Reset the singleton instance. Useful for testing."""
    global _detector_instance, _detector_strategy
    with _detector_lock:
        _detector_instance = None
        _detector_strategy = None
