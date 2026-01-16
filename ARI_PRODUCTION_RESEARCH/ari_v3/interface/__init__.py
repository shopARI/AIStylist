"""
ARI V3 - Conversational Interface Layer

This module implements Section 0.5 of the pseudocode:
- Intent Detection (LLM #0)
- Conversation Handler (LLM #5)
- Main Orchestrator (ARIOrchestrator)
- Memory Provider (Mem0 integration)

The interface layer routes user input to either:
- Product search (V3 Navigation Intelligence pipeline)
- Conversation handling (natural language responses)
"""

from .types import (
    SearchIntent,
    QueryType,
    IntentResult,
    ConversationResponse,
    ARIResponse,
    ResponseType,
)
from .intent_detector import (
    IntentDetector,
    HybridIntentDetector,
    DetectionStrategy,
    get_intent_detector,
)
from .parameter_extractor import (
    ParameterExtractor,
    get_parameter_extractor,
)
from .conversation_handler import (
    ConversationHandler,
    Message,
    MessageRole,
)
from .orchestrator import (
    ARIOrchestrator,
    create_orchestrator,
)

__all__ = [
    # Types
    "SearchIntent",
    "QueryType",
    "IntentResult",
    "ConversationResponse",
    "ARIResponse",
    "ResponseType",
    # Intent Detection
    "IntentDetector",
    "HybridIntentDetector",
    "DetectionStrategy",
    "get_intent_detector",
    # Parameter Extraction
    "ParameterExtractor",
    "get_parameter_extractor",
    # Conversation
    "ConversationHandler",
    "Message",
    "MessageRole",
    # Orchestrator
    "ARIOrchestrator",
    "create_orchestrator",
]
