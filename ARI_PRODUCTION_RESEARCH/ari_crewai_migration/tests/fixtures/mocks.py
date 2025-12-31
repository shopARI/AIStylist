"""
Mock Utilities for Testing
Provides mock objects for testing without API calls
"""

from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, Optional
from models.types import SearchIntent


class MockIntentResult:
    """Mock intent detection result"""

    def __init__(
        self,
        primary_intent: SearchIntent,
        confidence: float = 0.95,
        extracted_parameters: Optional[Dict[str, Any]] = None,
        detection_method: str = "crewai",
        fallback_used: bool = False,
        processing_time: float = 0.234
    ):
        self.primary_intent = primary_intent
        self.confidence = confidence
        self.extracted_parameters = extracted_parameters or {}
        self.detection_method = detection_method
        self.fallback_used = fallback_used
        self.processing_time = processing_time
        self.crewai_result = None


class MockIntentDetector:
    """Mock intent detector for testing"""

    def __init__(self, default_intent: SearchIntent = SearchIntent.SPECIFIC_ITEM):
        self.default_intent = default_intent
        self.call_count = 0
        self.queries = []

    async def detect_intent_and_extract(self, query: str):
        """Mock detect_intent_and_extract"""
        self.call_count += 1
        self.queries.append(query)

        return MockIntentResult(
            primary_intent=self.default_intent,
            confidence=0.95,
            extracted_parameters=self._extract_mock_parameters(query),
        )

    def _extract_mock_parameters(self, query: str) -> Dict[str, Any]:
        """Extract mock parameters from query"""
        params = {}

        # Mock color extraction
        colors = ["black", "red", "blue", "white", "green"]
        for color in colors:
            if color in query.lower():
                params["colors"] = [color]
                break

        # Mock category extraction
        categories = ["shirt", "dress", "jeans", "jacket", "shoes"]
        for category in categories:
            if category in query.lower():
                params["categories"] = [category]
                break

        return params


class MockProductCrew:
    """Mock product search crew"""

    def __init__(self, mock_results: Optional[Dict[str, Any]] = None):
        self.mock_results = mock_results or {
            "products": [],
            "reasoning": "Mock crew execution",
            "execution_time": 1.0,
        }
        self.call_count = 0
        self.last_query = None
        self.last_filters = None

    async def execute(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
    ):
        """Mock crew execution"""
        self.call_count += 1
        self.last_query = query
        self.last_filters = filters

        return self.mock_results.copy()


class MockIntelligenceCoordinator:
    """Mock ML intelligence coordinator"""

    def __init__(self):
        self.call_count = 0
        self.last_query = None

    async def gather_intelligence(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Mock intelligence gathering"""
        self.call_count += 1
        self.last_query = query

        return {
            "cypher_intel": {
                "behavioral_patterns": {"mock": True},
                "clustering": {"mock": True},
            },
            "vibe_intel": {
                "visual_analysis": {"mock": True},
                "style_patterns": {"mock": True},
            },
            "shared_intel": {
                "memory": {"mock": True},
                "user_preferences": {"mock": True},
            },
        }


class MockCacheService:
    """Mock cache service"""

    def __init__(self):
        self.cache = {}
        self.get_count = 0
        self.set_count = 0

    async def get(self, key: str):
        """Mock cache get"""
        self.get_count += 1
        return self.cache.get(key)

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Mock cache set"""
        self.set_count += 1
        self.cache[key] = value


class MockMetricsService:
    """Mock metrics service"""

    def __init__(self):
        self.metrics = []

    async def record(self, metric_name: str, value: Any, tags: Optional[Dict] = None):
        """Mock metric recording"""
        self.metrics.append({
            "name": metric_name,
            "value": value,
            "tags": tags or {},
        })


def create_mock_orchestrator(
    intent_detector: Optional[MockIntentDetector] = None,
    product_crew: Optional[MockProductCrew] = None,
    intelligence_coordinator: Optional[MockIntelligenceCoordinator] = None,
):
    """Create mock orchestrator with injected dependencies"""
    from crews.crewai_orchestrator import CrewAIOrchestrator

    orchestrator = CrewAIOrchestrator(
        crew=product_crew or MockProductCrew(),
        cache_service=MockCacheService(),
        metrics_service=MockMetricsService(),
    )

    # Inject mock intent detector if provided
    if intent_detector:
        orchestrator.intent_detector = intent_detector

    # Inject mock intelligence coordinator if provided
    if intelligence_coordinator:
        orchestrator.intelligence_coordinator = intelligence_coordinator
        orchestrator.enable_ml_intelligence = True

    return orchestrator


def create_mock_intent_result_for_query(query: str) -> MockIntentResult:
    """Create appropriate mock intent result based on query"""

    # Simple keyword-based detection for mocking
    query_lower = query.lower()

    if "gift" in query_lower:
        intent = SearchIntent.GIFT
    elif "sale" in query_lower:
        intent = SearchIntent.SALE
    elif any(word in query_lower for word in ["what", "how", "who"]):
        if "wear" in query_lower:
            intent = SearchIntent.INSPIRATION
        elif "remember" in query_lower or "size" in query_lower:
            intent = SearchIntent.MEMORY_QUERY
        elif "ask" in query_lower or "history" in query_lower:
            intent = SearchIntent.CONVERSATION_HISTORY
        else:
            intent = SearchIntent.CLARIFICATION
    elif any(word in query_lower for word in ["show", "browse", "view"]):
        intent = SearchIntent.BROWSE
    elif "outfit" in query_lower:
        intent = SearchIntent.OUTFIT
    elif "compare" in query_lower:
        intent = SearchIntent.COMPARISON
    else:
        intent = SearchIntent.SPECIFIC_ITEM

    # Extract mock parameters
    params = {}

    colors = ["black", "red", "blue", "white", "green", "navy", "pink", "gray"]
    for color in colors:
        if color in query_lower:
            params["colors"] = [color]
            break

    categories = ["shirt", "dress", "jeans", "jacket", "shoes", "pants", "sweater"]
    for category in categories:
        if category in query_lower:
            params["categories"] = [category]
            break

    return MockIntentResult(
        primary_intent=intent,
        confidence=0.95,
        extracted_parameters=params,
    )
