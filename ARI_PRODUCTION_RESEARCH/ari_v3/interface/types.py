"""
ARI V3 - Interface Types

Type definitions for the conversational interface layer.
Based on Section 0.5 of the pseudocode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SearchIntent(str, Enum):
    """
    User intent classifications for routing.

    Based on pseudocode Section 0.5.1
    """
    # Product-related intents -> Route to Navigation Intelligence
    PRODUCT_SEARCH = "product_search"       # "Find me a blue dress"
    PRODUCT_COMPARISON = "product_comparison"  # "Compare these two jackets"
    STYLE_ADVICE = "style_advice"           # "What would go with this?"
    OUTFIT_BUILDING = "outfit_building"     # "Help me build an outfit for..."
    BROWSE = "browse"                       # "Show me what you have"
    SPECIFIC_ITEM = "specific_item"         # "Need black shoes"
    INSPIRATION = "inspiration"             # "Outfit ideas for interview"
    GIFT = "gift"                           # "Gift for my mom"
    BRAND = "brand"                         # "Show me Nike products"
    SALE = "sale"                           # "What's on sale?"

    # Conversation intents -> Route to Conversation Handler
    GENERAL_CONVERSATION = "general_conversation"  # "Talk a little?", "How are you?"
    MEMORY_QUERY = "memory_query"           # "What did I look at yesterday?"
    CONVERSATION_HISTORY = "conversation_history"  # "What were we discussing?"
    CLARIFICATION = "clarification"         # "Why did you recommend that?"
    SYSTEM_STATUS = "system_status"         # "What can you do?"

    # Special intents
    ONBOARDING = "onboarding"               # User in onboarding flow
    FEEDBACK = "feedback"                   # "I liked that one" / "Not my style"
    GREETING = "greeting"                   # "Hi", "Hello"
    GOODBYE = "goodbye"                     # "Bye", "Thanks"


class QueryType(str, Enum):
    """Types of user queries for additional classification."""
    SEARCH = "search"
    CONVERSATION = "conversation"
    RECOMMENDATION = "recommendation"
    QUESTION = "question"
    COMMAND = "command"
    GREETING = "greeting"
    FEEDBACK = "feedback"


class ResponseType(str, Enum):
    """Type of response from ARI."""
    PRODUCTS = "products"                   # Product recommendations
    CONVERSATION = "conversation"           # Natural language response
    GREETING = "greeting"                   # Greeting response
    GOODBYE = "goodbye"                     # Goodbye response
    ERROR = "error"                         # Error response


@dataclass
class Exclusion:
    """A single exclusion criterion with reasoning."""
    field: str  # "brand", "color", "category", "price", "style", "material", etc.
    value: str  # The value to exclude
    reason: Optional[str] = None  # Why it should be excluded


@dataclass
class ExtractedParameters:
    """
    Parameters extracted from user query.

    Based on pseudocode Section 0.5.1 IntentResult.extracted_parameters
    """
    categories: List[str] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    occasions: List[str] = field(default_factory=list)
    price_range: Optional[Dict[str, float]] = None
    brand_preferences: List[str] = field(default_factory=list)
    style_modifiers: List[str] = field(default_factory=list)
    sizes: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)

    # General exclusions - can be any field type (brand, color, category, style, etc.)
    exclusions: List[Exclusion] = field(default_factory=list)

    # For memory/clarification intents
    time_reference: Optional[str] = None
    entity_reference: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None and empty values."""
        result = {}
        if self.categories:
            result["categories"] = self.categories
        if self.colors:
            result["colors"] = self.colors
        if self.occasions:
            result["occasions"] = self.occasions
        if self.price_range:
            result["price_range"] = self.price_range
        if self.brand_preferences:
            result["brand_preferences"] = self.brand_preferences
        if self.exclusions:
            result["exclusions"] = [
                {"field": e.field, "value": e.value, "reason": e.reason}
                for e in self.exclusions
            ]
        if self.style_modifiers:
            result["style_modifiers"] = self.style_modifiers
        if self.sizes:
            result["sizes"] = self.sizes
        if self.materials:
            result["materials"] = self.materials
        if self.time_reference:
            result["time_reference"] = self.time_reference
        if self.entity_reference:
            result["entity_reference"] = self.entity_reference
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExtractedParameters:
        """Create from dictionary."""
        return cls(
            categories=data.get("categories", []),
            colors=data.get("colors", []),
            occasions=data.get("occasions", []),
            price_range=data.get("price_range"),
            brand_preferences=data.get("brand_preferences", []),
            style_modifiers=data.get("style_modifiers", []),
            sizes=data.get("sizes", []),
            materials=data.get("materials", []),
            time_reference=data.get("time_reference"),
            entity_reference=data.get("entity_reference"),
        )


@dataclass
class IntentResult:
    """
    Output from intent detection.

    Based on pseudocode Section 0.5.1
    """
    primary_intent: SearchIntent
    confidence: float                       # 0-1, validated in __post_init__
    detection_method: str                   # "llm", "rule", "hybrid"
    extracted_parameters: ExtractedParameters = field(default_factory=ExtractedParameters)
    query_type: QueryType = QueryType.SEARCH
    reasoning: Optional[str] = None         # LLM's reasoning (if available)
    processing_time: float = 0.0

    def __post_init__(self):
        """Validate and clamp confidence to 0-1 range."""
        if self.confidence < 0:
            self.confidence = 0.0
        elif self.confidence > 1:
            self.confidence = 1.0

    def is_product_intent(self) -> bool:
        """Check if this intent should route to product search."""
        product_intents = {
            SearchIntent.PRODUCT_SEARCH,
            SearchIntent.PRODUCT_COMPARISON,
            SearchIntent.STYLE_ADVICE,
            SearchIntent.OUTFIT_BUILDING,
            SearchIntent.BROWSE,
            SearchIntent.SPECIFIC_ITEM,
            SearchIntent.INSPIRATION,
            SearchIntent.GIFT,
            SearchIntent.BRAND,
            SearchIntent.SALE,
        }
        return self.primary_intent in product_intents

    def is_conversation_intent(self) -> bool:
        """Check if this intent should route to conversation handler."""
        conversation_intents = {
            SearchIntent.GENERAL_CONVERSATION,
            SearchIntent.MEMORY_QUERY,
            SearchIntent.CONVERSATION_HISTORY,
            SearchIntent.CLARIFICATION,
            SearchIntent.SYSTEM_STATUS,
            SearchIntent.GREETING,
            SearchIntent.GOODBYE,
            SearchIntent.FEEDBACK,  # Feedback about recommendations is conversational
        }
        return self.primary_intent in conversation_intents

    def is_special_intent(self) -> bool:
        """Check if this intent requires special handling (e.g., onboarding flow)."""
        special_intents = {
            SearchIntent.ONBOARDING,
        }
        return self.primary_intent in special_intents

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "primary_intent": self.primary_intent.value,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
            "extracted_parameters": self.extracted_parameters.to_dict(),
            "query_type": self.query_type.value,
            "reasoning": self.reasoning,
            "processing_time": self.processing_time,
        }


@dataclass
class ConversationResponse:
    """
    Response from conversation handler.

    Based on pseudocode Section 0.5.2
    """
    text: str
    intent: SearchIntent
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "intent": self.intent.value,
            "suggestions": self.suggestions,
            "metadata": self.metadata,
        }


@dataclass
class ARIResponse:
    """
    Unified response from ARI.

    Based on pseudocode Section 0.5.3
    """
    response_type: ResponseType

    # For product responses
    products: List[Any] = field(default_factory=list)
    narrative: Optional[Any] = None

    # For conversation responses
    text: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)

    # Always present
    intent: Optional[IntentResult] = None
    session_id: Optional[str] = None
    execution_time: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "response_type": self.response_type.value,
            "execution_time": self.execution_time,
        }

        if self.products:
            result["products"] = self.products
        if self.narrative:
            result["narrative"] = (
                self.narrative.to_dict()
                if hasattr(self.narrative, "to_dict")
                else str(self.narrative)
            )
        if self.text:
            result["text"] = self.text
        if self.suggestions:
            result["suggestions"] = self.suggestions
        if self.intent:
            result["intent"] = self.intent.to_dict()
        if self.session_id:
            result["session_id"] = self.session_id
        if self.error:
            result["error"] = self.error

        return result


# Type aliases for clarity
ProductID = str
UserID = str
SessionID = str
QueryVector = List[float]
Embedding = List[float]
