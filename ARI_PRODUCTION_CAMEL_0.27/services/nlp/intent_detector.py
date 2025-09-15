"""
Intent Detection Service
Detects user intent from queries for better routing
Based on intent_detector.py patterns
"""

import logging
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import json

logger = logging.getLogger("services.intent.detector")

from models.types import SearchIntent


class QueryType(Enum):
    """Types of user queries."""
    SEARCH = "search"
    CONVERSATION = "conversation"
    RECOMMENDATION = "recommendation"
    QUESTION = "question"
    COMMAND = "command"
    GREETING = "greeting"
    FEEDBACK = "feedback"


@dataclass
class IntentResult:
    """Intent detection result."""
    primary_intent: SearchIntent
    query_type: QueryType
    confidence: float
    keywords: List[str]
    entities: Dict[str, Any]
    modifiers: List[str]
    metadata: Dict[str, Any]


class IntentDetector:
    """
    Detects user intent from natural language queries.
    """
    
    def __init__(self):
        """Initialize intent detector with patterns."""
        
        # Intent patterns - CONVERSATION INTENTS FIRST (higher priority)
        self.intent_patterns = {
            # Conversation/Memory Intents - CHECK THESE FIRST
            SearchIntent.CONVERSATION_HISTORY: [
                r"what did i ask",
                r"what did i say",
                r"what did i tell you",
                r"my first question",
                r"earlier i asked",
                r"at the beginning", 
                r"what were we talking about",
                r"before this",
                r"what was my original",
                r"remember what we discussed",
                r".*what did i say.*",
                r".*what did i tell.*",
                r".*what was i asking.*",
                r".*said to you.*",
                r".*told you.*"
            ],
            SearchIntent.MEMORY_QUERY: [
                r"do you remember",
                r"you know i like",
                r"recall my",
                r"you mentioned earlier",
                r"i told you before",
                r"my favorite.*that i mentioned",
                r"the.*i said i prefer"
            ],
            SearchIntent.CLARIFICATION: [
                r"what do you mean by",
                r"what do you mean",
                r"can you explain",
                r"i don't understand",
                r"tell me more about",
                r"elaborate on",
                r"what exactly",
                r"i'm confused",
                r"that doesn't make sense",
                r"can you clarify",
                r"what.*mean by",
                r"explain.*agents"
            ],
            SearchIntent.SYSTEM_STATUS: [
                r"how do you find products",
                r"what's your process",
                r"how does this work",
                r"who are the agents",
                r"what's cypher bot",
                r"how do agents compete",
                r"what can you do",
                r"how smart are you",
                r"what's your memory"
            ],
            SearchIntent.GENERAL_CONVERSATION: [
                r"nice weather",
                r"how are you",
                r"good morning",
                r"hello there",
                r"thanks for",
                r"that's interesting",
                r"cool story"
            ],
            # Product Search Intents - CHECK THESE AFTER CONVERSATION INTENTS
            SearchIntent.BROWSE: [
                r"show me",
                r"browse",
                r"what do you have",
                r"explore",
                r"see what",
                r"looking around"
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
                # Direct product mentions - CRITICAL FIX
                r"\b(?:black|white|red|blue|green|navy|gray|grey)\s+(?:shirt|t-?shirt|tee|blouse|top)",
                r"\b(?:shirt|t-?shirt|tee|blouse|top|dress|pants|jeans|jacket|coat|shoes|boots)\b",
                r"\b(?:any|some)\s+(?:black|white|red|blue)\s+(?:shirt|t-?shirt|tee)"
            ],
            SearchIntent.INSPIRATION: [
                r"inspire me",
                r"inspiration",
                r"ideas for",
                r"suggest",
                r"what should i wear",
                r"help me choose",
                r"not sure what"
            ],
            SearchIntent.COMPARISON: [
                r"compare",
                r"difference between",
                r"versus",
                r"vs\.",
                r"better than",
                r"which is better",
                r"or"
            ],
            SearchIntent.GIFT: [
                r"gift",
                r"present",
                r"for my \w+",
                r"for someone",
                r"birthday",
                r"anniversary",
                r"special occasion"
            ],
            SearchIntent.OUTFIT: [
                r"outfit",
                r"complete look",
                r"goes with",
                r"match with",
                r"coordinate",
                r"style with",
                r"wear together"
            ],
            SearchIntent.BRAND: [
                r"from (\w+)",
                r"by (\w+)",
                r"(\w+) brand",
                r"anything from (\w+)",
                r"show me (\w+)"
            ],
            SearchIntent.SALE: [
                r"sale",
                r"discount",
                r"deal",
                r"clearance",
                r"bargain",
                r"under \$\d+",
                r"cheap",
                r"affordable"
            ]
        }
        
        # Query type patterns
        self.query_type_patterns = {
            QueryType.GREETING: [
                r"^(hi|hello|hey|good morning|good afternoon|good evening)",
                r"^how are you",
                r"^what'?s up",
                r"^hey\s+how'?s?\s+your\s+day",
                r"^how'?s?\s+(your|the)\s+day",
                r"^how'?s?\s+it\s+going",
                r"^what'?s?\s+happening",
                r"^how\s+have\s+you\s+been"
            ],
            QueryType.QUESTION: [
                r"^(what|when|where|who|why|how) (?!.*(?:find|show|recommend|suggest|have|do you have))",
                r"^(can you|do you) (?!.*(?:find|show|recommend|suggest|have))",
                r"\?$"
            ],
            QueryType.COMMAND: [
                r"^(show|find|get|search|look|give me|bring me)",
                r"^(filter|sort|order)"
            ],
            QueryType.FEEDBACK: [
                r"(like|love|hate|don't like)",
                r"(perfect|great|terrible|awful|amazing)",
                r"(yes|no|maybe|not really)$"
            ],
            QueryType.CONVERSATION: [
                r"tell me",
                r"i think",
                r"in my opinion",
                r"what do you think"
            ]
        }
        
        # Category keywords
        self.category_keywords = {
            "tops": ["shirt", "blouse", "top", "tee", "tank", "sweater", "hoodie"],
            "bottoms": ["pants", "jeans", "shorts", "skirt", "trousers", "leggings"],
            "dresses": ["dress", "gown", "maxi", "midi", "mini"],
            "outerwear": ["jacket", "coat", "blazer", "cardigan", "vest"],
            "shoes": ["shoes", "boots", "sneakers", "heels", "sandals", "flats"],
            "accessories": ["bag", "purse", "wallet", "belt", "scarf", "hat", "jewelry"],
            "activewear": ["athletic", "gym", "workout", "yoga", "sports", "running"]
        }
        
        # Style modifiers
        self.style_modifiers = {
            "casual": ["casual", "relaxed", "comfortable", "everyday", "laid-back"],
            "formal": ["formal", "business", "professional", "elegant", "sophisticated"],
            "trendy": ["trendy", "fashionable", "stylish", "chic", "modern"],
            "vintage": ["vintage", "retro", "classic", "timeless", "antique"],
            "sporty": ["sporty", "athletic", "active", "performance"],
            "bohemian": ["boho", "bohemian", "hippie", "free-spirited"],
            "minimalist": ["minimal", "simple", "clean", "basic", "understated"],
            "edgy": ["edgy", "punk", "rock", "alternative", "bold"]
        }
        
        # Color patterns
        self.color_pattern = r"\b(red|blue|green|yellow|orange|purple|pink|black|white|gray|grey|brown|beige|navy|teal|turquoise|burgundy|maroon|olive|coral|gold|silver)\b"
        
        # Price patterns
        self.price_patterns = {
            "under": r"under \$?(\d+)",
            "over": r"over \$?(\d+)",
            "between": r"between \$?(\d+) (?:and|to) \$?(\d+)",
            "around": r"around \$?(\d+)"
        }
        
        # Size patterns
        self.size_pattern = r"\b(xs|extra small|s|small|m|medium|l|large|xl|extra large|xxl|2xl|3xl|size \d+)\b"
        
        logger.info("Intent detector initialized with patterns")
    
    async def detect_intent(self, query: str) -> IntentResult:
        """
        Detect intent from user query.
        
        Args:
            query: User query string
            
        Returns:
            Intent detection result
        """
        query_lower = query.lower().strip()
        
        # Detect query type
        query_type = self._detect_query_type(query_lower)
        
        # Detect primary intent
        primary_intent, intent_confidence = self._detect_primary_intent(query_lower)
        
        # Extract entities
        entities = await self._extract_entities(query_lower)
        
        # Extract keywords
        keywords = self._extract_keywords(query_lower)
        
        # Extract modifiers
        modifiers = self._extract_modifiers(query_lower)
        
        # Build metadata
        metadata = {
            "query_length": len(query),
            "word_count": len(query.split()),
            "has_question": "?" in query,
            "has_price": bool(entities.get("price")),
            "has_color": bool(entities.get("colors")),
            "has_size": bool(entities.get("size")),
            "has_category": bool(entities.get("category"))
        }
        
        return IntentResult(
            primary_intent=primary_intent,
            query_type=query_type,
            confidence=intent_confidence,
            keywords=keywords,
            entities=entities,
            modifiers=modifiers,
            metadata=metadata
        )
    
    def _detect_query_type(self, query: str) -> QueryType:
        """Detect the type of query."""
        for query_type, patterns in self.query_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return query_type
        
        # Default based on content with better detection
        product_indicators = ["find", "search", "looking", "need", "want", "show", "recommend", "suggest", "help me find"]
        conversational_indicators = ["how are you", "tell me about", "what do you think", "i think", "in my opinion"]
        
        if any(word in query for word in product_indicators):
            return QueryType.SEARCH
        elif any(phrase in query for phrase in conversational_indicators):
            return QueryType.CONVERSATION
        elif len(query.split()) > 15:  # Very long queries are likely conversational
            return QueryType.CONVERSATION
        elif any(category in query for categories in self.category_keywords.values() for category in categories):
            return QueryType.SEARCH  # Mentions clothing categories
        else:
            return QueryType.RECOMMENDATION
    
    def _detect_primary_intent(self, query: str) -> Tuple[SearchIntent, float]:
        """Detect primary search intent."""
        intent_scores = {}
        
        for intent, patterns in self.intent_patterns.items():
            score = 0
            matches = 0
            
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    matches += 1
                    score += 1
            
            if matches > 0:
                # Normalize score
                intent_scores[intent] = score / len(patterns)
        
        # Check for specific indicators
        if re.search(self.price_patterns["under"], query) or re.search(self.price_patterns["between"], query):
            intent_scores[SearchIntent.SALE] = intent_scores.get(SearchIntent.SALE, 0) + 0.5
        
        if " or " in query or " vs " in query:
            intent_scores[SearchIntent.COMPARISON] = intent_scores.get(SearchIntent.COMPARISON, 0) + 0.5
        
        if "outfit" in query or "complete look" in query:
            intent_scores[SearchIntent.OUTFIT] = intent_scores.get(SearchIntent.OUTFIT, 0) + 0.5
        
        # Get highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            return best_intent[0], min(best_intent[1], 1.0)
        
        # Default to browse
        return SearchIntent.BROWSE, 0.5
    
    async def _extract_entities(self, query: str) -> Dict[str, Any]:
        """Extract entities from query."""
        entities = {}
        
        # Extract categories
        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    entities["category"] = category
                    entities["category_keyword"] = keyword
                    break
        
        # Extract colors
        colors = re.findall(self.color_pattern, query)
        if colors:
            entities["colors"] = list(set(colors))
        
        # Extract price
        for price_type, pattern in self.price_patterns.items():
            match = re.search(pattern, query)
            if match:
                if price_type == "under":
                    entities["price"] = {"max": float(match.group(1))}
                elif price_type == "over":
                    entities["price"] = {"min": float(match.group(1))}
                elif price_type == "between":
                    entities["price"] = {
                        "min": float(match.group(1)),
                        "max": float(match.group(2))
                    }
                elif price_type == "around":
                    amount = float(match.group(1))
                    entities["price"] = {
                        "min": amount * 0.8,
                        "max": amount * 1.2
                    }
                break
        
        # Extract size
        size_match = re.search(self.size_pattern, query, re.IGNORECASE)
        if size_match:
            entities["size"] = size_match.group(1).upper()
        
        # Extract brand mentions
        brand_patterns = [
            r"\b(nike|adidas|gucci|prada|zara|h&m|gap|levi'?s?|calvin klein|tommy hilfiger)\b",
            r"from (\w+)",
            r"by (\w+)"
        ]
        
        for pattern in brand_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                entities["brand"] = match.group(1) if match.group(1) else match.group(0)
                break
        
        # Extract occasion
        occasions = ["wedding", "party", "work", "gym", "beach", "date", "interview", "vacation"]
        for occasion in occasions:
            if occasion in query:
                entities["occasion"] = occasion
                break
        
        return entities
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract significant keywords from query."""
        # Remove common words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were",
            "i", "me", "my", "you", "your", "we", "our", "can", "could",
            "would", "should", "may", "might", "must", "shall", "will"
        }
        
        words = query.split()
        keywords = []
        
        for word in words:
            word_clean = re.sub(r'[^\w\s]', '', word.lower())
            if word_clean and word_clean not in stop_words and len(word_clean) > 2:
                keywords.append(word_clean)
        
        return keywords
    
    def _extract_modifiers(self, query: str) -> List[str]:
        """Extract style modifiers from query."""
        modifiers = []
        
        for style, keywords in self.style_modifiers.items():
            for keyword in keywords:
                if keyword in query:
                    modifiers.append(style)
                    break
        
        # Check for other modifiers
        quality_modifiers = ["high quality", "premium", "luxury", "designer", "budget", "affordable"]
        for modifier in quality_modifiers:
            if modifier in query:
                modifiers.append(modifier.replace(" ", "_"))
        
        return list(set(modifiers))
    
    def analyze_conversation_context(
        self,
        current_query: str,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Analyze query in context of conversation.
        
        Args:
            current_query: Current user query
            conversation_history: Previous messages
            
        Returns:
            Context analysis
        """
        context = {
            "is_followup": False,
            "references_previous": False,
            "topic_shift": False,
            "clarification": False,
            "sentiment_change": False
        }
        
        if not conversation_history:
            return context
        
        current_lower = current_query.lower()
        
        # Check for follow-up indicators
        followup_indicators = ["that", "those", "it", "them", "this", "these", "the same", "similar"]
        context["is_followup"] = any(indicator in current_lower for indicator in followup_indicators)
        
        # Check for references to previous
        reference_patterns = ["like i said", "as mentioned", "earlier", "before", "last", "previous"]
        context["references_previous"] = any(pattern in current_lower for pattern in reference_patterns)
        
        # Check for clarification
        clarification_patterns = ["i mean", "actually", "no not", "yes but", "sorry i meant"]
        context["clarification"] = any(pattern in current_lower for pattern in clarification_patterns)
        
        # Analyze topic shift
        if conversation_history:
            last_message = conversation_history[-1].get("content", "").lower()
            last_keywords = set(self._extract_keywords(last_message))
            current_keywords = set(self._extract_keywords(current_lower))
            
            overlap = len(last_keywords & current_keywords)
            context["topic_shift"] = overlap < len(current_keywords) * 0.3
        
        return context
    
    def get_intent_explanation(self, intent: SearchIntent) -> str:
        """
        Get human-readable explanation of intent.
        
        Args:
            intent: Search intent
            
        Returns:
            Explanation string
        """
        explanations = {
            SearchIntent.BROWSE: "Looking to explore and discover options",
            SearchIntent.SPECIFIC_ITEM: "Searching for a particular item",
            SearchIntent.INSPIRATION: "Seeking style inspiration and ideas",
            SearchIntent.COMPARISON: "Comparing different options",
            SearchIntent.GIFT: "Shopping for someone else",
            SearchIntent.OUTFIT: "Building a complete outfit",
            SearchIntent.BRAND: "Interested in specific brands",
            SearchIntent.SALE: "Looking for deals and discounts"
        }
        
        return explanations.get(intent, "General search")
    
    def suggest_refinements(self, intent_result: IntentResult) -> List[str]:
        """
        Suggest query refinements based on intent.
        
        Args:
            intent_result: Intent detection result
            
        Returns:
            List of refinement suggestions
        """
        suggestions = []
        
        # Suggest based on missing entities
        if not intent_result.entities.get("category"):
            suggestions.append("What type of item are you looking for?")
        
        if not intent_result.entities.get("price"):
            suggestions.append("Do you have a budget in mind?")
        
        if not intent_result.entities.get("size"):
            suggestions.append("What size do you need?")
        
        if not intent_result.entities.get("colors"):
            suggestions.append("Any color preferences?")
        
        # Suggest based on intent
        if intent_result.primary_intent == SearchIntent.GIFT:
            if not intent_result.entities.get("occasion"):
                suggestions.append("What's the occasion?")
            suggestions.append("Tell me more about who this is for")
        
        elif intent_result.primary_intent == SearchIntent.OUTFIT:
            suggestions.append("What occasion is this outfit for?")
            suggestions.append("What pieces do you already have?")
        
        elif intent_result.primary_intent == SearchIntent.COMPARISON:
            suggestions.append("What features are most important to you?")
        
        return suggestions[:3]  # Limit to 3 suggestions


# Global instance
_intent_detector: Optional[IntentDetector] = None


def get_intent_detector() -> IntentDetector:
    """
    Get global intent detector instance.
    
    Returns:
        IntentDetector instance
    """
    global _intent_detector
    
    if _intent_detector is None:
        _intent_detector = IntentDetector()
    
    return _intent_detector


# Exports
__all__ = [
    'IntentDetector',
    'IntentResult',
    'QueryType',
    'get_intent_detector'
]