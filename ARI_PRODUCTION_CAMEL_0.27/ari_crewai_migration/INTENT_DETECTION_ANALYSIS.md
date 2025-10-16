# Intent Detection Integration Analysis

## Executive Summary

The CAMEL system has a **sophisticated 3-tier intent detection system** that is **critical to the application's intelligence**. It determines whether queries are product searches vs conversations, extracts parameters, and routes requests to appropriate handlers.

**Status:** Missing from CrewAI migration - must be integrated.

---

## Current CAMEL Architecture

### SearchIntent Enum (13 Intents)

**Product Search Intents (8):**
- `BROWSE` - General exploration
- `SPECIFIC_ITEM` - Looking for specific item
- `INSPIRATION` - Seeking style ideas
- `COMPARISON` - Comparing options
- `GIFT` - Shopping for someone else
- `OUTFIT` - Complete outfit requests
- `BRAND` - Brand-specific search
- `SALE` - Deals and discounts

**Conversation Intents (5):**
- `CONVERSATION_HISTORY` - "what did I ask earlier?"
- `MEMORY_QUERY` - "do you remember my size?"
- `CLARIFICATION` - "how do you work?"
- `SYSTEM_STATUS` - "who are the agents?"
- `GENERAL_CONVERSATION` - Non-fashion topics

### 3-Tier Detection System

**1. Pattern-Based (IntentDetector)**
- Location: `services/nlp/intent_detector.py`
- Method: Regex pattern matching
- Fast and deterministic
- Extracts entities: colors, categories, price, size, brand, occasion
- Extracts modifiers: casual, formal, trendy, etc.

**2. LLM-Based (LLMIntentDetector)**
- Location: `services/nlp/llm_intent_detector.py`
- Method: CAMEL ChatAgent with GPT-4o-mini
- RAG with fashion knowledge base
- Semantic understanding for complex queries
- Structured JSON output

**3. Hybrid (HybridIntentDetector)**
- Location: `services/nlp/hybrid_intent_detector.py`
- Combines both approaches
- Multiple strategies:
  - `LLM_FIRST` - Try LLM, fallback to patterns
  - `HARDCODED_FIRST` - Try patterns, LLM for complex
  - `LLM_ONLY` - LLM only
  - `HARDCODED_ONLY` - Patterns only
  - `PARALLEL` - Run both, compare results

### Usage in ApplicationService

**ApplicationService.process_message():**

```python
# Line 72: Initialize intent detector
self.intent_detector = get_hybrid_intent_detector(strategy=DetectionStrategy.LLM_FIRST)

# Line 99: Detect intent
intent, score, params, method = await self._detect_intent_with_preferences(message, stored_preferences)

# Line 101-106: Handle conversation intents FIRST (priority)
if intent in [CONVERSATION_HISTORY, MEMORY_QUERY, CLARIFICATION, SYSTEM_STATUS, GENERAL_CONVERSATION]:
    return await self._handle_conversation_intents(...)

# Line 125-128: Determine if should search products
should_search_products = self._should_search_products(intent, score, ...)

# Line 131-149: Route to product search or conversation
if should_search_products:
    await self._handle_product_search(...)
else:
    await self._handle_conversation(...)
```

**Intent Handlers (ApplicationService):**

1. `_handle_conversation_history()` - Line 958
   - Retrieves conversation history from session memory
   - Filters based on query (beginning, earlier, etc.)

2. `_handle_memory_query()` - Line 981
   - Retrieves stored preferences
   - Returns user preferences formatted

3. `_handle_clarification()` - Line 1005
   - Explains system features
   - Keywords: agents, cypher, vibe, ari

4. `_handle_system_status()` - Line 1022
   - System capabilities info
   - Memory, agents, process

5. `_handle_general_conversation()` - Line 1033
   - LLM-powered natural conversation
   - Time/date queries
   - General topics

**Product Search Decision Logic:**

```python
# Line 1294: _should_search_products()
should_search = (
    intent in [SPECIFIC_ITEM, SALE, BRAND, OUTFIT, BROWSE] and score > 0.7
    or intent == INSPIRATION and score > 0.8
    or is_product_continuation
    or explicit_product_phrases and not non_shopping_patterns
)
```

**Parameter Extraction:**
- Colors, categories, occasions, styles
- Price ranges, brands, sizes
- Merged with stored preferences from memory

---

## CrewAI Migration Requirements

### Phase 1: Copy Framework-Agnostic Components

**Files to Copy (No Changes):**
1. `services/nlp/intent_detector.py`  `ari_crewai_migration/nlp/intent_detector.py`
   - Pattern-based detection
   - Entity extraction
   - Modifier extraction
   - Framework-agnostic

2. `services/nlp/parameter_extractor.py`  `ari_crewai_migration/nlp/parameter_extractor.py`
   - Parameter extraction logic
   - Framework-agnostic

3. `services/nlp/fashion_knowledge.py`  `ari_crewai_migration/nlp/fashion_knowledge.py`
   - Fashion knowledge base for RAG
   - Framework-agnostic

4. `models/types.py` (SearchIntent enum)  Shared with CrewAI
   - Already defined, reference from parent

### Phase 2: Update CAMEL-Dependent Components

**File to Update:**
`services/nlp/llm_intent_detector.py`  `ari_crewai_migration/nlp/llm_intent_detector.py`

**Current Dependencies:**
```python
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType
```

**CrewAI Replacement:**
```python
from crewai import Agent
from langchain_openai import ChatOpenAI
```

**Changes Needed:**
- Replace `ChatAgent` with CrewAI `Agent`
- Remove CAMEL model factory
- Use LangChain LLM directly
- Keep same prompt engineering
- Keep same JSON parsing logic

**File to Update:**
`services/nlp/hybrid_intent_detector.py`  `ari_crewai_migration/nlp/hybrid_intent_detector.py`

**Changes Needed:**
- Import from new locations
- Update LLM detector import
- Keep same strategy logic
- Keep same fallback mechanisms

### Phase 3: Create Conversation Handler Crews

**New Files Needed:**

1. `ari_crewai_migration/crews/conversation_crew.py`
   - Handles conversation intents
   - Separate crew from product search
   - Memory access agents
   - System info agents

2. `ari_crewai_migration/agents/memory_agent.yaml`
   - Handles conversation history queries
   - Handles stored preference queries

3. `ari_crewai_migration/agents/system_agent.yaml`
   - System status and capabilities
   - Clarification requests

4. `ari_crewai_migration/agents/conversation_agent.yaml`
   - General conversation
   - Non-fashion topics
   - LLM-powered responses

**Tools Needed:**

1. `ari_crewai_migration/tools/memory_tools.py`
   - `conversation_history_tool` - Retrieve chat history
   - `preference_lookup_tool` - Get stored preferences
   - `session_context_tool` - Get session context

2. `ari_crewai_migration/tools/system_tools.py`
   - `system_info_tool` - System capabilities
   - `agent_info_tool` - Agent descriptions

### Phase 4: Update CrewAI Orchestrator

**File to Update:**
`ari_crewai_migration/crews/crewai_orchestrator.py`

**New Logic:**

```python
class CrewAIOrchestrator:
    def __init__(self, ...):
        # Add intent detector
        self.intent_detector = get_hybrid_intent_detector(strategy=DetectionStrategy.LLM_FIRST)

        # Add conversation crew
        self.conversation_crew = ConversationCrew(...)

        # Existing product search crew
        self.product_crew = ProductSearchCrew(...)

    async def execute_search(self, query, ...):
        # Step 1: Detect intent
        intent_result = await self.intent_detector.detect_intent_and_extract(query)
        intent = intent_result.primary_intent
        confidence = intent_result.confidence
        params = intent_result.extracted_parameters

        # Step 2: Route based on intent
        if intent in [CONVERSATION_HISTORY, MEMORY_QUERY, CLARIFICATION, SYSTEM_STATUS, GENERAL_CONVERSATION]:
            # Route to conversation crew
            return await self.conversation_crew.handle_conversation(
                intent=intent,
                query=query,
                params=params,
                session_id=session_id
            )

        # Step 3: Product search intents
        elif intent in [SPECIFIC_ITEM, BROWSE, INSPIRATION, OUTFIT, BRAND, SALE, GIFT, COMPARISON]:
            if confidence > 0.7:  # Confidence threshold
                # Route to product search crew
                return await self.product_crew.execute_search(
                    query=query,
                    filters=params,
                    intent=intent,
                    ...
                )

        # Step 4: Fallback to conversation
        return await self.conversation_crew.handle_conversation(...)
```

### Phase 5: Integration Points

**ApplicationService Integration:**

```python
from ari_crewai_migration.crews.crewai_orchestrator import CrewAIOrchestrator

class ApplicationService:
    def __init__(self, ...):
        self.orchestrator = CrewAIOrchestrator(...)
        # Intent detection now handled inside orchestrator

    async def process_message(self, session_id, message, user_id):
        # Orchestrator handles intent detection + routing
        result = await self.orchestrator.execute_search(
            query=message,
            session_id=session_id,
            user_id=user_id
        )
        return result
```

---

## Benefits of Intent-Based Routing

### 1. Intelligent Query Handling
- Conversation vs product search separation
- No wasted resources searching products for general chat
- Better user experience

### 2. Parameter Extraction
- Automatic extraction of colors, categories, occasions
- Merged with stored preferences
- Rich context for agents

### 3. Confidence-Based Decisions
- Low confidence  fallback to conversation
- High confidence  execute product search
- Prevents false positives

### 4. Conversation Memory
- Direct access to conversation history
- Stored preference queries
- Context-aware responses

### 5. System Transparency
- Users can ask about system capabilities
- Clarification requests handled properly
- Educational about how ARI works

---

## Migration Complexity Assessment

### Low Complexity (Copy As-Is)
-  `intent_detector.py` - Pattern-based
-  `parameter_extractor.py` - Pure Python
-  `fashion_knowledge.py` - Data file

### Medium Complexity (Update Imports)
-  `hybrid_intent_detector.py` - Update LLM detector import
-  `models/types.py` - Already compatible

### High Complexity (Refactor CAMELCrewAI)
-  `llm_intent_detector.py` - Replace CAMEL agents with CrewAI/LangChain
-  Create conversation crews and agents
-  Update orchestrator with routing logic
-  Create memory and system tools

---

## Implementation Plan

### Step 1: Copy Framework-Agnostic Files 
- Create `ari_crewai_migration/nlp/` directory
- Copy pattern-based detector
- Copy parameter extractor
- Copy fashion knowledge

### Step 2: Update LLM Intent Detector 
- Replace CAMEL ChatAgent with CrewAI Agent
- Use LangChain ChatOpenAI for LLM
- Keep prompt engineering
- Keep JSON parsing
- Test with sample queries

### Step 3: Update Hybrid Detector 
- Update imports from new locations
- Test all strategies
- Verify fallback mechanisms

### Step 4: Create Conversation Infrastructure 🆕
- Create conversation crew
- Create memory agent
- Create system agent
- Create general conversation agent
- Create memory tools
- Create system tools

### Step 5: Update Orchestrator 
- Add intent detector initialization
- Add intent-based routing logic
- Add conversation crew integration
- Add confidence thresholds
- Add fallback logic

### Step 6: Integration Testing 
- Test all 13 intent types
- Test confidence thresholds
- Test parameter extraction
- Test routing logic
- Test conversation handlers

---

## Success Criteria

### Functional Requirements
-  All 13 intents detected correctly
-  Confidence scores accurate
-  Parameters extracted properly
-  Conversation intents handled without product search
-  Product intents route to product crew
-  Fallback mechanisms work

### Performance Requirements
-  Intent detection < 500ms
-  No performance degradation vs CAMEL
-  LLM fallback works when needed

### Quality Requirements
-  Test coverage for all intents
-  Comparison tests vs CAMEL results
-  Error handling for edge cases

---

## Risk Mitigation

### Risk: LLM Agent Replacement Complexity
**Mitigation:** Keep prompt engineering identical, only change agent wrapper

### Risk: Different JSON Output Format
**Mitigation:** Extensive testing, same parsing logic

### Risk: Performance Degradation
**Mitigation:** Benchmark before/after, optimize if needed

### Risk: Missing Conversation Intents
**Mitigation:** Comprehensive test suite covering all intent types

---

## Next Steps

1. Create `nlp/` directory in CrewAI migration
2. Copy framework-agnostic files
3. Update `llm_intent_detector.py` for CrewAI
4. Create conversation crews
5. Update orchestrator with routing
6. Test end-to-end

**Priority:** HIGH - Intent detection is critical for application intelligence
**Estimated Effort:** 6-8 hours
**Blockers:** None - can start immediately
