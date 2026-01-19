# ARI Navigation Intelligence - Pseudocode Specification V3

**Date:** 2025-12-29  



## North Star & Philosophy

**North Star:** Find the best product for each individual.

**How:** By representing style as a multi-dimensional space, alongside tangential spaces (demographics, psychometrics, psychology, life context), and using the LLM to traverse all of these simultaneously.

The LLM receives historical data, personalization metrics, and behavioral patterns across all these spaces. It synthesizes them to determine the path.

**Three Pillars provide the knowledge:**
1. **Pillar 1: Personalization** - Raw user data from Neo4j User Graph (body, interactions, conversations, social media)
2. **Pillar 2: Stylist Knowledge** - RAG over fashion literature (color theory, body types, occasions)
3. **Pillar 3: User Activity** - Behavioral patterns computed from interaction history

**Key Principles:**
- Store raw data, not fixed inferences
- Compute position and trajectory from behavior (deterministic)
- Users have style REPERTOIRES, not one style (context-aware positions)
- LLM synthesizes pillars and outputs descriptors (not coordinates)
- Destination grounded in real product space via exemplar retrieval
- All other calculations are deterministic (fast, consistent, reproducible)
- Feedback loop enables continuous learning
- Re-interpret profile when behavior diverges from onboarding (people change)
---

## Section 0: System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              ARI FULL SYSTEM ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                      PHASE 0: CONVERSATIONAL INTERFACE (V3.1)                        │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                         USER INPUT                                            │   │
│  │   "Find me a dress" | "Talk a little?" | "What did I see yesterday?"         │   │
│  └───────────────────────────────────┬──────────────────────────────────────────┘   │
│                                      ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                    INTENT DETECTOR (LLM #0)                                   │   │
│  │   Classifies: PRODUCT_SEARCH | CONVERSATION | MEMORY_QUERY | CLARIFICATION   │   │
│  └───────────────────────────────────┬──────────────────────────────────────────┘   │
│                    ┌─────────────────┴─────────────────┐                            │
│                    ▼                                   ▼                            │
│  ┌────────────────────────────┐      ┌────────────────────────────────────────┐    │
│  │   PRODUCT INTENT           │      │   CONVERSATION INTENT                  │    │
│  │   → Phase 3 (Navigation)   │      │   → Conversation Handler (LLM #5)      │    │
│  │   → Returns: Products +    │      │   → Returns: Natural response +        │    │
│  │     Narrative              │      │     Follow-up suggestions              │    │
│  └────────────────────────────┘      └────────────────────────────────────────┘    │
│                                                                                      │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                              PHASE 1: USER ONBOARDING                                │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                        ONBOARDING AGENT (LLM #1)                              │   │
│  │                                                                               │   │
│  │   Conversational data collection - "coffee with a wise friend"               │   │
│  │                                                                               │   │
│  │   ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐          │   │
│  │   │  PERSONAL  │ → │   TASTE    │ → │  PROCESS   │ → │ PRACTICAL  │          │   │
│  │   │            │   │            │   │            │   │            │          │   │
│  │   │ • age      │   │ • gender   │   │ • motiva-  │   │ • budget   │          │   │
│  │   │ • location │   │   express  │   │   tions    │   │ • category │          │   │
│  │   │ • work     │   │ • brands   │   │ • creative │   │   budgets  │          │   │
│  │   │ • occasions│   │ • shapes   │   │   control  │   │            │          │   │
│  │   │ • gender   │   │ • fit      │   │ • goals    │   │            │          │   │
│  │   │   identity │   │ • loves    │   │ • loyalty  │   │            │          │   │
│  │   │ • ethnicity│   │ • wants    │   │ • adventur │   │            │          │   │
│  │   │ • relation │   │ • avoids   │   │ • validatn │   │            │          │   │
│  │   │ • parental │   │ • occasion │   │ • exploratn│   │            │          │   │
│  │   │            │   │   styles   │   │ • social   │   │            │          │   │
│  │   └────────────┘   └────────────┘   └────────────┘   └────────────┘          │   │
│  │         │               │                │               │                    │   │
│  │         └───────────────┴────────────────┴───────────────┘                    │   │
│  │                                   │                                           │   │
│  │                    ┌──────────────┴──────────────┐                            │   │
│  │                    │                             │                            │   │
│  │              ┌─────▼─────┐               ┌───────▼───────┐                    │   │
│  │              │   BODY    │               │   EXTERNAL    │                    │   │
│  │              │           │               │               │                    │   │
│  │              │ • face    │               │ • instagram   │                    │   │
│  │              │   photo   │               │ • pinterest   │                    │   │
│  │              │ • body    │               │ • tiktok      │                    │   │
│  │              │   photo   │               │               │                    │   │
│  │              └───────────┘               └───────────────┘                    │   │
│  │                                                                               │   │
│  └───────────────────────────────────┬──────────────────────────────────────────┘   │
│                                      │                                               │
│                                      ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                     INTERPRETATION LLM (#2)                                   │   │
│  │                                                                               │   │
│  │   Parses raw onboarding conversation → structured OnboardingProfile          │   │
│  │   Extracts: explicit preferences, implicit signals, root values              │   │
│  └───────────────────────────────────┬──────────────────────────────────────────┘   │
│                                      │                                               │
│                                      ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                     [TBD] CALIBRATION FLOW                                    │   │
│  │                                                                               │   │
│  │   Show 5-10 exemplar products based on onboarding                            │   │
│  │   Quick reactions: thumbs up/down to refine initial embeddings                │   │
│  └───────────────────────────────────┬──────────────────────────────────────────┘   │
│                                      │                                               │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                              PHASE 2: DATA PERSISTENCE                              │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                                      │                                               │
│                                      ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                         NEO4J USER GRAPH                                      │   │
│  │                                                                               │   │
│  │   ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │   │                         USER NODE                                    │    │   │
│  │   │                                                                      │    │   │
│  │   │  Attributes (evolve over time):                                      │    │   │
│  │   │  • onboarding_profile (structured)                                   │    │   │
│  │   │  • raw_conversations (full text)                                     │    │   │
│  │   │  • root_values (extracted motivations)                               │    │   │
│  │   │  • navigation_parameters (derived from onboarding)                   │    │   │
│  │   │  • social_taste_embeddings (from Instagram/Pinterest/TikTok)         │    │   │
│  │   │  • body_data (photos, coloring, measurements)                        │    │   │
│  │   │                                                                      │    │   │
│  │   └──────────────────────────────┬──────────────────────────────────────┘    │   │
│  │                                  │                                           │    │
│  │                    ┌─────────────┼─────────────┐                             │    │
│  │                    │             │             │                             │    │
│  │                    ▼             ▼             ▼                             │    │
│  │              [:VIEWED]     [:LIKED/ACTED]     [:PURCHASED]                        │    │
│  │                    │             │             │                             │    │
│  │                    └─────────────┼─────────────┘                             │    │
│  │                                  │                                           │    │
│  │                                  ▼                                           │    │
│  │   ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │   │                      PRODUCT NODES                                   │    │   │
│  │   │                                                                      │    │   │
│  │   │  Pre-computed:                                                       │    │   │
│  │   │  • SAM3 masks, 3D geometry, textures                                 │    │   │
│  │   │  • Embeddings (OpenAI, SigLIP, multimodal)                           │    │   │
│  │   │  • Deterministic features (color, silhouette, harmony)               │    │   │
│  │   │  • Style coordinates (derived from embeddings)                       │    │   │
│  │   │                                                                      │    │   │
│  │   └─────────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                               │   │
│  │   Products become part of user's style graph through interactions            │   │
│  │                                                                               │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                               │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                          PHASE 3: QUERY-TIME NAVIGATION                             │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                                      │                                               │
│                                      ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                    NAVIGATION INTELLIGENCE ENGINE                             │   │
│  │                                                                               │   │
│  │   ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │   │                      THREE PILLARS                                   │    │   │
│  │   │                                                                      │    │   │
│  │   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │    │   │
│  │   │  │   PILLAR 1   │  │   PILLAR 2   │  │   PILLAR 3   │               │    │   │
│  │   │  │ Personalizatn│  │   Stylist    │  │   Activity   │               │    │   │
│  │   │  │              │  │  Knowledge   │  │              │               │    │   │
│  │   │  │ • Onboarding │  │              │  │ • Interactns │               │    │   │
│  │   │  │   profile    │  │ • RAG over   │  │ • Purchases  │               │    │   │
│  │   │  │ • Social     │  │   textbooks  │  │ • Drift      │               │    │   │
│  │   │  │   embeddings │  │ • Multiple   │  │ • Patterns   │               │    │   │
│  │   │  │ • Root vals  │  │   perspectivs│  │              │               │    │   │
│  │   │  │ • Nav params │  │              │  │              │               │    │   │
│  │   │  └──────────────┘  └──────────────┘  └──────────────┘               │    │   │
│  │   │         │                 │                 │                        │    │   │
│  │   │         └─────────────────┼─────────────────┘                        │    │   │
│  │   │                           ▼                                          │    │   │
│  │   │              ┌────────────────────────┐                              │    │   │
│  │   │              │   SYNTHESIS LLM (#3)   │                              │    │   │
│  │   │              │                        │                              │    │   │
│  │   │              │  Outputs:              │                              │    │   │
│  │   │              │  • Style descriptors   │ ──┐                          │    │   │
│  │   │              │  • Exemplar terms      │   │                          │    │   │
│  │   │              │  • Budget interpret    │   │                          │    │   │
│  │   │              │  • Formality level     │   │                          │    │   │
│  │   │              └────────────────────────┘   │                          │    │   │
│  │   │                                           │                          │    │   │
│  │   │              ┌────────────────────────┐   │                          │    │   │
│  │   │              │  EXEMPLAR RETRIEVAL    │◄──┘                          │    │   │
│  │   │              │  (Deterministic)       │                              │    │   │
│  │   │              │                        │                              │    │   │
│  │   │              │  Style descriptors →   │                              │    │   │
│  │   │              │  Search products →     │                              │    │   │
│  │   │              │  Destination = centroid│                              │    │   │
│  │   │              └────────────────────────┘                              │    │   │
│  │   │                           │                                          │    │   │
│  │   └───────────────────────────┼──────────────────────────────────────────┘    │   │
│  │                               ▼                                               │   │
│  │   ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │   │                    PATH CALCULATION                                  │    │   │
│  │   │                    (Deterministic)                                   │    │   │
│  │   │                                                                      │    │   │
│  │   │  • Step size from nav_params.step_size_multiplier                    │    │   │
│  │   │  • Exploration from nav_params.exploration_appetite                  │    │   │
│  │   │  • Per-context trajectory consideration                              │    │   │
│  │   │                                                                      │    │   │
│  │   └──────────────────────────────┬──────────────────────────────────────┘    │   │
│  │                                  │                                           │    │
│  │                                  ▼                                           │    │
│  │   ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │   │                    AGENT COORDINATION                                │    │   │
│  │   │                                                                      │    │   │
│  │   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │    │   │
│  │   │  │   VibeBot    │  │  VisionBot   │  │  [CypherBot]  │               │    │   │
│  │   │  │  (Semantic)  │  │   (Visual)   │  │ (Attributes) │               │    │   │
│  │   │  │   PRIMARY    │  │   PRIMARY    │  │  Conditional │               │    │   │
│  │   │  └──────────────┘  └──────────────┘  └──────────────┘               │    │   │
│  │   │         │                 │                 │                        │    │   │
│  │   │         └─────────────────┼─────────────────┘                        │    │   │
│  │   │                           ▼                                          │    │   │
│  │   │              ┌────────────────────────┐                              │    │   │
│  │   │              │          Ari         │                              │    │   │
│  │   │              │                        │                              │    │   │
│  │   │              │  • Score products      │                              │    │   │
│  │   │              │  • MMR diversity       │              │    │   │
│  │   │              │  • Outlier injection   │                              │    │   │
│  │   │              │  • Rule compliance     │                              │    │   │
│  │   │              └────────────────────────┘                              │    │   │
│  │   │                           │                                          │    │   │
│  │   └───────────────────────────┼──────────────────────────────────────────┘    │   │
│  │                               ▼                                               │   │
│  │   ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │   │                    NARRATIVE LLM (#4)                                │    │   │
│  │   │                                                                      │    │   │
│  │   │  Generates journey story using:                                      │    │   │
│  │   │  • validation_sources (frame for audience)                           │    │   │
│  │   │  • style_motivations (connect to root values)                        │    │   │
│  │   │  • Product explanations (why each piece)                             │    │   │
│  │   │                                                                      │    │   │
│  │   └──────────────────────────────┬──────────────────────────────────────┘    │   │
│  │                                  │                                           │    │
│  └──────────────────────────────────┼───────────────────────────────────────────┘   │
│                                     │                                                │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                              PHASE 4: FEEDBACK LOOP                                 │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                                     │                                                │
│                                     ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                         OUTCOME TRACKING                                      │   │
│  │                                                                               │   │
│  │   For each recommendation session, track:                                     │   │
│  │   • Which products were clicked/liked/purchased                               │   │
│  │   • Time spent viewing each product                                           │   │
│  │   • Scroll depth, return visits                                               │   │
│  │   • Explicit feedback (thumbs up/down)                                        │   │
│  │                                                                               │   │
│  │   Use to improve:                                                             │   │
│  │   • User embeddings (products → user graph)                                   │   │
│  │   • Synthesis LLM prompts (which destinations led to conversions)             │   │
│  │   • RAG knowledge (which rules correlated with success)                       │   │
│  │   • Navigation parameters (trajectory, step size calibration)                 │   │
│  │                                                                               │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Section 0.5: Conversational Interface Layer (New in V3.1)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         CONVERSATIONAL INTERFACE LAYER                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                         USER INPUT                                            │   │
│  │                                                                               │   │
│  │   "Find me a dress for my sister's wedding"  ← Product Search Intent         │   │
│  │   "Talk a little?"                           ← Conversation Intent           │   │
│  │   "What did I look at yesterday?"            ← Memory Query Intent           │   │
│  │   "Why did you recommend that jacket?"       ← Clarification Intent          │   │
│  │                                                                               │   │
│  └───────────────────────────────────┬──────────────────────────────────────────┘   │
│                                      │                                               │
│                                      ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                    INTENT DETECTOR (LLM #0)                                   │   │
│  │                                                                               │   │
│  │   Classifies user input into:                                                │   │
│  │   • PRODUCT_SEARCH      - User wants product recommendations                 │   │
│  │   • GENERAL_CONVERSATION - User wants to chat/discuss                        │   │
│  │   • MEMORY_QUERY        - User asking about past interactions                │   │
│  │   • CLARIFICATION       - User asking why/how about recommendations          │   │
│  │   • SYSTEM_STATUS       - User asking about system capabilities              │   │
│  │   • ONBOARDING          - User in onboarding flow                            │   │
│  │                                                                               │   │
│  │   Also extracts:                                                             │   │
│  │   • Categories, colors, occasions (for product search)                       │   │
│  │   • Time references (for memory queries)                                     │   │
│  │   • Entity references (for clarifications)                                   │   │
│  │                                                                               │   │
│  └───────────────────────────────────┬──────────────────────────────────────────┘   │
│                                      │                                               │
│                    ┌─────────────────┴─────────────────┐                            │
│                    │                                   │                            │
│                    ▼                                   ▼                            │
│  ┌────────────────────────────────┐  ┌────────────────────────────────────────┐    │
│  │     PRODUCT SEARCH INTENT      │  │     CONVERSATION INTENT                │    │
│  │                                │  │                                        │    │
│  │   Route to:                    │  │   Route to:                            │    │
│  │   Navigation Intelligence      │  │   Conversation Handler (LLM #5)       │    │
│  │   (Section 4-6)                │  │                                        │    │
│  │                                │  │   Uses:                                │    │
│  │   Returns:                     │  │   • Conversation history               │    │
│  │   • Products                   │  │   • User profile context               │    │
│  │   • Narrative                  │  │   • Memory (Mem0)                      │    │
│  │   • Journey explanation        │  │                                        │    │
│  │                                │  │   Returns:                             │    │
│  └────────────────────────────────┘  │   • Natural language response          │    │
│                                      │   • Follow-up suggestions              │    │
│                                      └────────────────────────────────────────┘    │
│                                                                                      │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                              CONVERSATION MEMORY                                     │
│  ════════════════════════════════════════════════════════════════════════════════   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                         MEM0 MEMORY SYSTEM                                    │   │
│  │                                                                               │   │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                       │   │
│  │   │   EPISODIC   │  │   SEMANTIC   │  │   FACTUAL    │                       │   │
│  │   │              │  │              │  │              │                       │   │
│  │   │ • Session    │  │ • Style      │  │ • Budget:    │                       │   │
│  │   │   history    │  │   preferences│  │   $500/mo    │                       │   │
│  │   │ • "Searched  │  │ • Brand      │  │ • Size: M    │                       │   │
│  │   │   for red    │  │   affinities │  │ • Dislikes:  │                       │   │
│  │   │   dresses"   │  │ • "User      │  │   polyester  │                       │   │
│  │   │ • "Liked     │  │   prefers    │  │              │                       │   │
│  │   │   item #3"   │  │   minimalist"│  │              │                       │   │
│  │   └──────────────┘  └──────────────┘  └──────────────┘                       │   │
│  │                                                                               │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 0.5.1 Intent Detection

```
ENUM SearchIntent:
    """
    User intent classifications for routing.
    """
    # Product-related intents → Route to Navigation Intelligence
    PRODUCT_SEARCH           # "Find me a blue dress"
    PRODUCT_COMPARISON       # "Compare these two jackets"
    STYLE_ADVICE             # "What would go with this?"
    OUTFIT_BUILDING          # "Help me build an outfit for..."

    # Conversation intents → Route to Conversation Handler
    GENERAL_CONVERSATION     # "Talk a little?", "How are you?"
    MEMORY_QUERY             # "What did I look at yesterday?"
    CONVERSATION_HISTORY     # "What were we discussing?"
    CLARIFICATION            # "Why did you recommend that?"
    SYSTEM_STATUS            # "What can you do?"

    # Special intents
    ONBOARDING               # User in onboarding flow
    FEEDBACK                 # "I liked that one" / "Not my style"


STRUCTURE IntentResult:
    """
    Output from intent detection.
    """
    primary_intent: SearchIntent
    confidence: FLOAT                    # 0-1
    detection_method: STRING             # "llm", "rule", "hybrid"

    # Extracted parameters (for product intents)
    extracted_parameters: {
        categories: LIST[STRING],        # ["dress", "top"]
        colors: LIST[STRING],            # ["blue", "navy"]
        occasions: LIST[STRING],         # ["wedding", "casual"]
        price_range: {min: FLOAT, max: FLOAT},
        brand_preferences: LIST[STRING],
        style_modifiers: LIST[STRING],   # ["minimalist", "bold"]

        # V3.1: Real-time exclusions from user text
        exclusions: LIST[Exclusion]      # Things user explicitly doesn't want
    }

    # V3.1: Exclusion structure for filtering
    STRUCTURE Exclusion:
        field: STRING      # "brand", "color", "category", "style", "material", "price", "abstract"
        value: STRING      # The value to exclude (e.g., "Theory", "black", "formal")
        reason: STRING     # Why excluded (for debugging/transparency)

    # For memory/clarification intents
    time_reference: STRING               # "yesterday", "last week"
    entity_reference: STRING             # "that jacket", "item #3"


CLASS IntentDetector:
    """
    Hybrid intent detection using rules + LLM.
    LLM-first strategy for natural language understanding.
    """

    FUNCTION detect_intent(
        query: STRING,
        conversation_history: LIST[Message] = []
    ) → IntentResult:
        """
        Detect user intent from query.
        Uses conversation history for context continuity.
        """

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Quick rule-based check for obvious patterns
        # ═══════════════════════════════════════════════════════════════════

        rule_result = self._check_rules(query)
        IF rule_result.confidence > 0.9:
            RETURN rule_result

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: LLM-based intent detection
        # ═══════════════════════════════════════════════════════════════════

        prompt = f"""
        Classify this user message and extract relevant parameters.

        CONVERSATION HISTORY:
        {format_history(conversation_history[-5:])}

        CURRENT MESSAGE: "{query}"

        INTENTS:
        - PRODUCT_SEARCH: User wants to find/browse products
        - STYLE_ADVICE: User wants styling help
        - GENERAL_CONVERSATION: User wants to chat, not shop
        - MEMORY_QUERY: User asking about past interactions
        - CLARIFICATION: User asking why/how about recommendations
        - FEEDBACK: User giving feedback on shown items

        Output JSON:
        {{
            "intent": "<INTENT_NAME>",
            "confidence": <0.0-1.0>,
            "categories": [...],
            "colors": [...],
            "occasions": [...],
            "reasoning": "<why this intent>"
        }}
        """

        response = llm.complete(prompt, model="gpt-4o-mini")
        parsed = json.parse(response)

        RETURN IntentResult(
            primary_intent=SearchIntent[parsed.intent],
            confidence=parsed.confidence,
            detection_method="llm",
            extracted_parameters={
                categories=parsed.categories,
                colors=parsed.colors,
                occasions=parsed.occasions
            }
        )

    FUNCTION _check_rules(query: STRING) → IntentResult:
        """
        Fast rule-based detection for common patterns.
        """
        query_lower = query.lower().strip()

        # Greeting patterns → GENERAL_CONVERSATION
        IF query_lower IN ["hi", "hello", "hey", "talk a little", "chat"]:
            RETURN IntentResult(
                primary_intent=SearchIntent.GENERAL_CONVERSATION,
                confidence=0.95,
                detection_method="rule"
            )

        # Memory patterns → MEMORY_QUERY
        IF "yesterday" IN query_lower OR "last time" IN query_lower:
            IF "look" IN query_lower OR "show" IN query_lower OR "saw" IN query_lower:
                RETURN IntentResult(
                    primary_intent=SearchIntent.MEMORY_QUERY,
                    confidence=0.9,
                    detection_method="rule"
                )

        # Why/how patterns → CLARIFICATION
        IF query_lower.startswith("why") OR query_lower.startswith("how come"):
            RETURN IntentResult(
                primary_intent=SearchIntent.CLARIFICATION,
                confidence=0.85,
                detection_method="rule"
            )

        # Default: low confidence, let LLM decide
        RETURN IntentResult(
            primary_intent=SearchIntent.PRODUCT_SEARCH,
            confidence=0.3,
            detection_method="rule"
        )
```

### 0.5.1.1 Real-Time Exclusion Extraction (V3.1)

```
CLASS ExclusionExtractor:
    """
    V3.1: Extract exclusions from natural language in real-time.

    Complements historical exclusions (Neo4j rejected/returned products)
    with immediate exclusions from user text.

    Examples:
    - "I don't want Theory" → brand: Theory
    - "no black items" → color: black
    - "nothing too formal" → style: formal
    - "skip items my mom would wear" → abstract: mature styles
    """

    ASYNC FUNCTION extract_exclusions_with_llm(query: STRING) → LIST[Exclusion]:
        """
        Use LLM to understand nuanced exclusions that regex can't capture.
        """
        prompt = f"""
        Analyze the user's message and extract exclusions (things they DON'T want).

        User message: "{query}"

        Return JSON:
        {{
            "exclusions": [
                {{"field": "brand|color|category|style|material|price|abstract",
                  "value": "...",
                  "reason": "why excluded"}}
            ]
        }}

        Field types:
        - brand: Specific brands (Theory, Nike, etc.)
        - color: Colors (black, red, etc.)
        - category: Product types (dresses, pants, etc.)
        - style: Style descriptors (formal, casual, trendy, etc.)
        - material: Fabrics (silk, polyester, etc.)
        - price: Price-related (expensive, cheap, over $100)
        - abstract: Complex/subjective exclusions ("what my mom would wear")
        """

        response = await llm.complete(prompt, model="gpt-4o-mini")
        parsed = json.parse(response)

        RETURN [
            Exclusion(field=e.field, value=e.value, reason=e.reason)
            FOR e IN parsed.exclusions
        ]

    FUNCTION apply_exclusions(products: LIST[Product], exclusions: LIST[Exclusion]) → LIST[Product]:
        """
        Filter products based on exclusion criteria.
        """
        FUNCTION matches_exclusion(product, exclusion) → BOOL:
            value = exclusion.value.lower()

            IF exclusion.field == "brand":
                RETURN value IN product.brand.lower() OR value IN product.title.lower()
            ELIF exclusion.field == "color":
                RETURN value IN product.color.lower() OR value IN product.description.lower()
            ELIF exclusion.field == "category":
                RETURN value IN product.category.lower()
            ELIF exclusion.field == "style":
                RETURN value IN product.tags OR value IN product.description.lower()
            ELIF exclusion.field == "price":
                # Handle "expensive", "over $X", etc.
                RETURN evaluate_price_exclusion(product.price, value)
            ELIF exclusion.field == "abstract":
                # Broad search across all text fields
                RETURN value IN (product.title + product.description + product.tags).lower()
            ELSE:
                RETURN value IN product.title.lower()

        RETURN [p FOR p IN products IF NOT ANY(matches_exclusion(p, e) FOR e IN exclusions)]
```

### 0.5.1.2 Session Feedback Refinement (V3.1)

```
CLASS SessionFeedbackHandler:
    """
    V3.1: Handle immediate feedback within a session.

    Different from Section 8 (long-term feedback loop):
    - Section 8: Learn from outcomes over days/weeks, update user profile
    - This: Immediate refinement within a conversation session

    Flow:
    1. User searches: "show me luxury bags"
    2. ARI shows results (Theory, Coach, etc.)
    3. User says: "that's not Gucci"
    4. System understands: User wanted Gucci, refines and re-searches
    """

    # Store last search context per session
    last_search_context: MAP[session_id → SearchContext]

    STRUCTURE SearchContext:
        query: STRING
        params: ExtractedParameters
        products_shown: LIST[STRING]      # Product titles shown
        brands_shown: LIST[STRING]        # Brands in results
        timestamp: DATETIME

    ASYNC FUNCTION handle_feedback(
        session_id: STRING,
        user_id: STRING,
        feedback: STRING,
        intent: IntentResult
    ) → ARIResponse:
        """
        Handle feedback by refining previous search.
        """
        prev_context = self.last_search_context.get(session_id)

        IF prev_context IS NULL:
            # No previous search, handle as conversation
            RETURN conversation_handler.handle(feedback)

        # Use LLM to interpret feedback in context
        refined_query = await self._interpret_feedback(
            original_query=prev_context.query,
            feedback=feedback,
            brands_shown=prev_context.brands_shown
        )

        IF refined_query:
            # Re-run product search with refined understanding
            RETURN await product_search(
                query=refined_query,
                user_id=user_id,
                session_id=session_id
            )
        ELSE:
            # Couldn't interpret, ask for clarification
            RETURN conversation_handler.handle(feedback)

    ASYNC FUNCTION _interpret_feedback(
        original_query: STRING,
        feedback: STRING,
        brands_shown: LIST[STRING]
    ) → STRING OR NULL:
        """
        Use LLM to understand feedback and generate refined query.
        """
        prompt = f"""
        User searched for: "{original_query}"
        Results showed brands: {brands_shown}
        User feedback: "{feedback}"

        Interpret their feedback and generate a refined search query.
        - "that's not X" usually means they wanted X specifically
        - "too formal" means they want more casual
        - "not my style" needs clarification

        Return ONLY the refined query, or "UNCLEAR" if can't interpret.
        """

        response = await llm.complete(prompt, model="gpt-4o-mini")

        IF response != "UNCLEAR":
            RETURN response
        RETURN NULL
```

### 0.5.2 Conversation Handler

```
CLASS ConversationHandler:
    """
    Handles non-product conversational intents.
    Provides natural, GPT-like responses.
    """

    ASYNC FUNCTION handle_conversation(
        session_id: STRING,
        query: STRING,
        intent: IntentResult,
        user_context: UserContext
    ) → ConversationResponse:
        """
        Generate natural conversational response.
        """

        # Get conversation history from Mem0
        history = await mem0.get_episodic(session_id, limit=10)

        # Get user facts for personalization
        user_facts = await mem0.get_factual(user_context.user_id)

        # Build context-aware prompt
        prompt = f"""
        You are ARI, a friendly and knowledgeable personal stylist.
        You're having a conversation with {user_context.name or 'a user'}.

        USER PROFILE:
        {format_user_facts(user_facts)}

        CONVERSATION HISTORY:
        {format_history(history)}

        USER SAYS: "{query}"
        DETECTED INTENT: {intent.primary_intent.name}

        Respond naturally and helpfully. If the user seems to want to
        browse products, gently guide them. If they want to chat, engage
        warmly while staying relevant to fashion/style.

        Keep response concise (2-3 sentences max for casual chat).
        """

        response = await llm.complete(prompt, model="gpt-4o")

        # Store in episodic memory
        await mem0.add_episodic(
            session_id,
            f"User: {query}\nARI: {response}",
            metadata={"intent": intent.primary_intent.name}
        )

        RETURN ConversationResponse(
            text=response,
            intent=intent.primary_intent,
            suggestions=self._generate_suggestions(intent, user_context)
        )

    FUNCTION _generate_suggestions(
        intent: IntentResult,
        user_context: UserContext
    ) → LIST[STRING]:
        """
        Generate follow-up suggestions based on context.
        """
        IF intent.primary_intent == SearchIntent.GENERAL_CONVERSATION:
            RETURN [
                "Show me what's new",
                "Help me find something for work",
                "What's trending right now?"
            ]

        IF intent.primary_intent == SearchIntent.MEMORY_QUERY:
            RETURN [
                "Show me similar items",
                "Search for something new",
                "Tell me more about my style"
            ]

        RETURN []
```

### 0.5.3 Main Interface Orchestrator

```
CLASS ARIOrchestrator:
    """
    Main entry point for all user interactions.
    Routes to appropriate handler based on intent.
    """

    ASYNC FUNCTION process_input(
        session_id: STRING,
        user_id: STRING,
        query: STRING
    ) → ARIResponse:
        """
        Process any user input - conversation or product search.
        """

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Load user context
        # ═══════════════════════════════════════════════════════════════════

        user_context = await load_user_context(user_id)
        conversation_history = await mem0.get_episodic(session_id, limit=5)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Detect intent
        # ═══════════════════════════════════════════════════════════════════

        intent = await intent_detector.detect_intent(
            query=query,
            conversation_history=conversation_history
        )

        log.info(f"Intent: {intent.primary_intent.name} (confidence: {intent.confidence})")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Route to appropriate handler
        # ═══════════════════════════════════════════════════════════════════

        IF self._is_product_intent(intent.primary_intent):
            # Route to Navigation Intelligence (Section 4-6)
            result = await navigation_orchestrator.execute_search(
                user_id=user_id,
                query=query,
                occasion=intent.extracted_parameters.occasions[0] if intent.extracted_parameters.occasions else None,
                filters=intent.extracted_parameters
            )

            RETURN ARIResponse(
                type="products",
                products=result.products,
                narrative=result.narrative,
                metadata={
                    "intent": intent,
                    "session_id": session_id
                }
            )

        ELSE:
            # Route to Conversation Handler
            result = await conversation_handler.handle_conversation(
                session_id=session_id,
                query=query,
                intent=intent,
                user_context=user_context
            )

            RETURN ARIResponse(
                type="conversation",
                text=result.text,
                suggestions=result.suggestions,
                metadata={
                    "intent": intent,
                    "session_id": session_id
                }
            )

    FUNCTION _is_product_intent(intent: SearchIntent) → BOOL:
        """
        Determine if intent should route to product search.
        """
        product_intents = {
            SearchIntent.PRODUCT_SEARCH,
            SearchIntent.PRODUCT_COMPARISON,
            SearchIntent.STYLE_ADVICE,
            SearchIntent.OUTFIT_BUILDING
        }
        RETURN intent IN product_intents


STRUCTURE ARIResponse:
    """
    Unified response from ARI.
    """
    type: ENUM["products", "conversation", "error"]

    # For product responses
    products: LIST[Product] = []
    narrative: JourneyNarrative = None

    # For conversation responses
    text: STRING = None
    suggestions: LIST[STRING] = []

    # Always present
    metadata: {
        intent: IntentResult,
        session_id: STRING,
        execution_time: FLOAT
    }
```

### 0.5.4 LLM Usage Summary (Updated)

| LLM # | Name | When Used | Input | Output |
|-------|------|-----------|-------|--------|
| #0 | Intent Detector | Every user input | Query + history | Intent classification |
| #1 | Onboarding Agent | During onboarding | User responses | Conversational continuation |
| #2 | Interpretation | After onboarding | Raw conversations | OnboardingProfile |
| #3 | Synthesis | Product search | 3 Pillars + Query | Style descriptors |
| #4 | Narrative | After product selection | Products + Context | Journey story |
| #5 | Conversation | Non-product intents | Query + Context | Natural response |

---


## Section 1: Data Structures

### 1.1.a Core Enums

ENUM StyleContext:
    """
    Users don't have ONE style - they have a style repertoire.
    Different contexts activate different style modes.
    """
    PROFESSIONAL      # Work, meetings, interviews
    CASUAL            # Weekends, errands, relaxed
    EVENING           # Date night, dinner, events
    FORMAL            # Weddings, galas, ceremonies
    ACTIVE            # Gym, sports, outdoor activities
    CREATIVE          # Artistic events, self-expression
    TRAVEL            # Vacation, comfort + style
    DEFAULT           # When context is unclear

### 1.1 Onboarding Data Structures

```
STRUCTURE OnboardingProfile:
    """
    Structured output from the Interpretation LLM.
    Maps directly to onboarding nodes.
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # PERSONAL NODE
    # ═══════════════════════════════════════════════════════════════════════
    
    personal: {
        age: INT,
        life_stage: STRING,                    # "early_career", "established", "transitioning", etc.
        
        location: {
            city: STRING,
            region: STRING,
            urban_suburban_rural: ENUM["urban", "suburban", "rural"],
            climate: STRING                    # Derived or explicit
        },
        
        occupation: {
            title: STRING,
            industry: STRING,
            dress_code: ENUM["formal", "business_casual", "casual", "creative", "varies"],
            work_style_alignment: FLOAT        # 0-1: Does work wardrobe = authentic self?
        },
        
        occasions: LIST[{
            name: STRING,                      # User's exact words: "park with Max"
            frequency: ENUM["daily", "weekly", "monthly", "occasional"],
            importance: FLOAT,                 # 0-1: How much they care about this occasion
            style_context: StyleContext        # Mapped to enum
        }],
        
        gender_identity: STRING,               # User's own words, not forced categories
        ethnicity: STRING,
        cultural_background: STRING,
        
        relationship_status: STRING,
        parental_status: {
            has_kids: BOOL,
            kid_ages: LIST[INT],
            parenting_style_impact: STRING     # How it affects their style needs
        }
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # TASTE NODE
    # ═══════════════════════════════════════════════════════════════════════
    
    taste: {
        gender_expression: {
            spectrum_position: STRING,         # User's description, not forced scale
            fluidity: FLOAT,                   # 0-1: How much it varies
            fit_preferences: LIST[STRING],     # "structured", "fluid", "fitted", etc.
        },
        
        brand_preferences: LIST[{
            brand: STRING,
            why_love_it: STRING,               # Root value connection
            frequency: ENUM["always", "often", "sometimes", "exploring"]
        }],
        
        shape_preferences: LIST[STRING],       # Silhouettes they gravitate toward
        fit_preferences: LIST[STRING],         # Oversized, tailored, bodycon, etc.
        
        style_loves: STRING,                   # What's working now
        style_wants: STRING,                   # Direction they want to go
        style_avoids: STRING,                  # Hard boundaries
        
        occasion_styles: MAP[STRING → {
            # Keyed by their actual occasions from personal.occasions
            description: STRING,               # How they described dressing for this
            consistency_with_other_contexts: FLOAT  # 0-1: Same person or code-switching?
        }],
        
        style_icons: LIST[STRING]              # Who inspires them
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # PROCESS NODE - THESE DRIVE NAVIGATION PARAMETERS
    # ═══════════════════════════════════════════════════════════════════════
    
    process: {
        style_motivations: LIST[{
            motivation: STRING,                # "confidence", "self-expression", "fitting in", etc.
            importance: FLOAT,                 # 0-1
            root_value: STRING                 # Deeper "why" behind this motivation
        }],
        
        creative_control: INT,                 # 1-10: How much they want to steer vs be steered
        style_goals: STRING,                   # What success looks like
        
        brand_loyalty: INT,                    # 1-10: Stick with favorites vs explore
        adventurousness: INT,                  # 1-10: Subtle evolution vs bold moves
        
        validation_sources: LIST[{
            source: ENUM["self", "partner", "friends", "colleagues", "strangers", "society"],
            importance: FLOAT                  # 0-1
        }],
        
        exploration_preference: ENUM["long_explore", "quick_decide", "curated_options"],
        
        social_influences: {
            primary_sources: LIST[STRING],     # Where they get inspiration
            trend_relationship: STRING,        # Leader, follower, ignorer
            originality_importance: FLOAT      # 0-1
        }
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # PRACTICALITY NODE
    # ═══════════════════════════════════════════════════════════════════════
    
    practicality: {
        budget: {
            monthly: FLOAT,
            yearly: FLOAT,
            flexibility: ENUM["firm", "guideline", "flexible"],
            investment_mindset: STRING         # How they think about price vs value
        },
        
        category_budgets: MAP[STRING → {
            # e.g., "shoes", "tops", "outerwear"
            budget_level: ENUM["splurge", "moderate", "budget"],
            reasoning: STRING                  # Why this category gets this treatment
        }]
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # BODY NODE
    # ═══════════════════════════════════════════════════════════════════════
    
    body: {
        face_photo_id: STRING,                 # Reference to stored photo
        body_photo_id: STRING,                 # Reference to stored photo
        
        # Extracted from photos or verbal description
        coloring: {
            skin_tone: STRING,
            undertone: ENUM["warm", "cool", "neutral"],
            hair_color: STRING,
            eye_color: STRING,
            seasonal_palette: STRING           # "autumn", "winter", etc.
        },
        
        body_verbal: STRING,                   # Their own description
        
        favorite_features: LIST[STRING],       # What they want to highlight
        # Note: insecurities NOT stored explicitly - too sensitive
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # EXTERNAL NODE - SOCIAL MEDIA
    # ═══════════════════════════════════════════════════════════════════════
    
    external: {
        instagram: {
            handle: STRING,
            connected: BOOL,
            last_synced: DATETIME
        },
        pinterest: {
            handle: STRING,
            connected: BOOL,
            boards_analyzed: LIST[STRING],
            last_synced: DATETIME
        },
        tiktok: {
            handle: STRING,
            connected: BOOL,
            last_synced: DATETIME
        }
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # ROOT VALUES (extracted across all nodes)
    # ═══════════════════════════════════════════════════════════════════════
    
    root_values: {
        primary: STRING,                       # The deepest "why" - what style means to them
        secondary: LIST[STRING],               # Supporting values
        
        # Specific value dimensions (0-1 scales)
        authenticity_importance: FLOAT,        # Being true to self
        belonging_importance: FLOAT,           # Fitting in with community
        standing_out_importance: FLOAT,        # Being noticed/unique
        comfort_importance: FLOAT,             # Physical and psychological comfort
        competence_importance: FLOAT,          # Looking capable/professional
        
        value_tensions: LIST[STRING]           # Where their values conflict
    }


STRUCTURE NavigationParameters:
    """
    Deterministically derived from OnboardingProfile.
    These control the navigation algorithm behavior.
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # DERIVED FROM process.adventurousness + process.creative_control
    # ═══════════════════════════════════════════════════════════════════════
    
    exploration_appetite: FLOAT               # 0-1, controls outlier %
    # Formula: (adventurousness / 10) * 0.7 + (1 - creative_control / 10) * 0.3
    # High adventurousness + low creative_control = high exploration
    
    step_size_multiplier: FLOAT               # 0.5-1.5, scales default step size
    # Formula: 0.5 + (adventurousness / 10) * 1.0
    # High adventurousness = larger steps allowed
    
    # ═══════════════════════════════════════════════════════════════════════
    # DERIVED FROM process.brand_loyalty
    # ═══════════════════════════════════════════════════════════════════════
    
    brand_affinity_weight: FLOAT              # 0-1, how much to favor known brands
    # Formula: brand_loyalty / 10
    
    # ═══════════════════════════════════════════════════════════════════════
    # DERIVED FROM process.exploration_preference
    # ═══════════════════════════════════════════════════════════════════════
    
    result_set_size: INT                      # How many results to return
    # "long_explore" → 20, "curated_options" → 5, "quick_decide" → 10
    
    diversity_requirement: FLOAT              # 0-1, MMR lambda parameter
    # "long_explore" → 0.7 (more diverse), "curated_options" → 0.3 (more focused)
    
    # ═══════════════════════════════════════════════════════════════════════
    # DERIVED FROM process.creative_control
    # ═══════════════════════════════════════════════════════════════════════
    
    user_embedding_weight: FLOAT              # Base weight for user vs query
    # Formula: 0.3 + (creative_control / 10) * 0.4
    # High creative_control = user history matters more
    
    # ═══════════════════════════════════════════════════════════════════════
    # DERIVED FROM practicality.budget
    # ═══════════════════════════════════════════════════════════════════════
    
    default_budget: {
        min: FLOAT,
        max: FLOAT,
        flexibility: FLOAT                    # How much to allow over/under
    }
    
    category_budget_overrides: MAP[STRING → {min, max}]


FUNCTION derive_navigation_parameters(profile: OnboardingProfile) → NavigationParameters:
    """
    Deterministic derivation of navigation parameters from onboarding.
    No LLM needed - pure computation.
    """
    
    # Exploration appetite
    adventurousness = profile.process.adventurousness / 10.0
    creative_control = profile.process.creative_control / 10.0
    exploration_appetite = adventurousness * 0.7 + (1 - creative_control) * 0.3
    
    # Step size
    step_size_multiplier = 0.5 + adventurousness * 1.0
    
    # Brand affinity
    brand_affinity_weight = profile.process.brand_loyalty / 10.0
    
    # Result set configuration
    IF profile.process.exploration_preference == "long_explore":
        result_set_size = 20
        diversity_requirement = 0.7
    ELIF profile.process.exploration_preference == "curated_options":
        result_set_size = 5
        diversity_requirement = 0.3
    ELSE:  # quick_decide
        result_set_size = 10
        diversity_requirement = 0.5
    
    # User embedding weight
    user_embedding_weight = 0.3 + creative_control * 0.4
    
    # Budget
    monthly = profile.practicality.budget.monthly
    flexibility = 0.2 if profile.practicality.budget.flexibility == "firm" else \
                  0.4 if profile.practicality.budget.flexibility == "guideline" else 0.6
    
    default_budget = {
        min: monthly * 0.1,                   # Assume single item ~10% of monthly
        max: monthly * 0.5,                   # Up to 50% for investment piece
        flexibility: flexibility
    }
    
    # Category overrides
    category_budget_overrides = {}
    FOR category, pref IN profile.practicality.category_budgets:
        IF pref.budget_level == "splurge":
            category_budget_overrides[category] = {
                min: default_budget.min * 1.5,
                max: default_budget.max * 2.0
            }
        ELIF pref.budget_level == "budget":
            category_budget_overrides[category] = {
                min: default_budget.min * 0.3,
                max: default_budget.max * 0.5
            }
        # "moderate" uses default
    
    RETURN NavigationParameters(
        exploration_appetite=exploration_appetite,
        step_size_multiplier=step_size_multiplier,
        brand_affinity_weight=brand_affinity_weight,
        result_set_size=result_set_size,
        diversity_requirement=diversity_requirement,
        user_embedding_weight=user_embedding_weight,
        default_budget=default_budget,
        category_budget_overrides=category_budget_overrides
    )
```

### 1.2 Social Media Embeddings

```
STRUCTURE SocialTasteEmbeddings:
    """
    Embeddings derived from connected social media accounts.
    These provide rich taste signals beyond explicit preferences.
    """
    
    pinterest: {
        boards: MAP[STRING → {
            # Board name → embedding
            embedding: VECTOR[1536],           # Averaged from pins
            pin_count: INT,
            dominant_themes: LIST[STRING],
            style_coordinates: StyleCoordinate # Derived
        }],
        overall_embedding: VECTOR[1536],       # Weighted blend of boards
        last_synced: DATETIME
    },
    
    instagram: {
        saved_posts_embedding: VECTOR[1536],   # From saved posts
        liked_posts_embedding: VECTOR[1536],   # From likes (if available)
        following_style_embedding: VECTOR[1536], # From followed fashion accounts
        overall_embedding: VECTOR[1536],       # Weighted blend
        last_synced: DATETIME
    },
    
    tiktok: {
        liked_videos_embedding: VECTOR[1536],  # From likes
        saved_videos_embedding: VECTOR[1536],  # From saves
        overall_embedding: VECTOR[1536],
        last_synced: DATETIME
    },
    
    # Combined embedding across all platforms
    unified_social_embedding: VECTOR[1536]


CLASS SocialMediaProcessor:
    """
    Process connected social media to extract taste embeddings.
    """
    
    ASYNC FUNCTION process_pinterest(handle: STRING) → PinterestEmbeddings:
        """
        Analyze Pinterest boards for style signals.
        """
        boards = await pinterest_api.get_boards(handle)
        
        board_embeddings = {}
        FOR board IN boards:
            pins = await pinterest_api.get_pins(board.id, limit=100)
            
            # Filter to fashion-related pins
            fashion_pins = [p for p in pins if is_fashion_related(p)]
            
            IF len(fashion_pins) > 0:
                # Extract images and compute embeddings
                pin_embeddings = []
                FOR pin IN fashion_pins:
                    IF pin.image_url:
                        # Use SigLIP for visual embedding
                        img_embedding = siglip.encode_image(pin.image_url)
                        pin_embeddings.append(img_embedding)
                    
                    IF pin.description:
                        # Also capture text signal
                        text_embedding = openai.embed(pin.description)
                        pin_embeddings.append(text_embedding * 0.3)  # Lower weight
                
                # Average for board embedding
                board_embedding = normalize(mean(pin_embeddings))
                
                # Derive style coordinates from embedding
                style_coords = derive_style_from_embedding(board_embedding)
                
                board_embeddings[board.name] = {
                    embedding: board_embedding,
                    pin_count: len(fashion_pins),
                    dominant_themes: extract_themes(fashion_pins),
                    style_coordinates: style_coords
                }
        
        # Compute overall embedding (weight by pin count)
        overall = weighted_average([
            (data.embedding, data.pin_count) 
            for data in board_embeddings.values()
        ])
        
        RETURN PinterestEmbeddings(
            boards=board_embeddings,
            overall_embedding=overall,
            last_synced=now()
        )
    
    ASYNC FUNCTION process_instagram(handle: STRING) → InstagramEmbeddings:
        """
        Analyze Instagram for style signals.
        """
        # Get saved posts (requires user permission)
        saved = await instagram_api.get_saved_posts(handle, limit=200)
        fashion_saved = [p for p in saved if is_fashion_related(p)]
        
        saved_embedding = ZERO_VECTOR[1536]
        IF len(fashion_saved) > 0:
            embeddings = [siglip.encode_image(p.image_url) for p in fashion_saved]
            saved_embedding = normalize(mean(embeddings))
        
        # Get followed fashion accounts
        following = await instagram_api.get_following(handle)
        fashion_accounts = [f for f in following if is_fashion_account(f)]
        
        following_embedding = ZERO_VECTOR[1536]
        IF len(fashion_accounts) > 0:
            # Get recent posts from followed fashion accounts
            account_posts = []
            FOR account IN fashion_accounts[:20]:  # Limit API calls
                posts = await instagram_api.get_recent_posts(account.handle, limit=10)
                account_posts.extend(posts)
            
            embeddings = [siglip.encode_image(p.image_url) for p in account_posts]
            following_embedding = normalize(mean(embeddings))
        
        # Blend with weights
        overall = normalize(
            saved_embedding * 0.6 +      # Saves are strong signal
            following_embedding * 0.4    # Following is weaker signal
        )
        
        RETURN InstagramEmbeddings(
            saved_posts_embedding=saved_embedding,
            following_style_embedding=following_embedding,
            overall_embedding=overall,
            last_synced=now()
        )
    
    FUNCTION compute_unified_social_embedding(
        pinterest: PinterestEmbeddings,
        instagram: InstagramEmbeddings,
        tiktok: TikTokEmbeddings
    ) → VECTOR[1536]:
        """
        Blend all social signals into one embedding.
        Weight by data richness.
        """
        embeddings = []
        weights = []
        
        IF pinterest AND pinterest.overall_embedding:
            embeddings.append(pinterest.overall_embedding)
            # Weight by number of pins analyzed
            total_pins = sum(b.pin_count for b in pinterest.boards.values())
            weights.append(min(1.0, total_pins / 100))  # Saturates at 100 pins
        
        IF instagram AND instagram.overall_embedding:
            embeddings.append(instagram.overall_embedding)
            weights.append(0.8)  # Fixed weight for Instagram
        
        IF tiktok AND tiktok.overall_embedding:
            embeddings.append(tiktok.overall_embedding)
            weights.append(0.6)  # Lower weight - less curated
        
        IF len(embeddings) == 0:
            RETURN ZERO_VECTOR[1536]
        
        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]
        
        RETURN normalize(sum(e * w for e, w in zip(embeddings, weights)))
```

### 1.3 Core Navigation Structures (Updated from V2)

```
STRUCTURE StyleCoordinate:
    """
     Embeddings are canonical. Explicit dimensions are DERIVED for interpretability.
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # CANONICAL REPRESENTATION: Embeddings
    # ═══════════════════════════════════════════════════════════════════════
    
    embedding: VECTOR[1536]                   # Primary representation (OpenAI space)
    visual_embedding: VECTOR[1024]            # SigLIP visual (optional, for visual-heavy contexts)
    
    # ═══════════════════════════════════════════════════════════════════════
    # DERIVED DIMENSIONS: For interpretability and explanation
    # These are computed FROM embeddings, not stored separately
    # ═══════════════════════════════════════════════════════════════════════
    
    @property
    FUNCTION interpretable_dimensions() → InterpretableDimensions:
        """
        Project embedding onto interpretable axes.
        Used for explanations and UI, NOT for retrieval.
        """
        RETURN project_to_interpretable(self.embedding)


STRUCTURE InterpretableDimensions:
    """
    Human-readable style dimensions.
    Derived from embeddings via learned projections.
    """
    form: FLOAT           # structured ←→ fluid (0-1)
    color_warmth: FLOAT   # cool ←→ warm (0-1)
    color_saturation: FLOAT  # muted ←→ vibrant (0-1)
    formality: FLOAT      # casual ←→ formal (0-1)
    proportion: FLOAT     # fitted ←→ oversized (0-1)
    minimalism: FLOAT     # minimal ←→ maximalist (0-1)
    edge: FLOAT           # classic ←→ edgy (0-1)


FUNCTION project_to_interpretable(embedding: VECTOR[1536]) → InterpretableDimensions:
    """
    Use pre-trained projection matrices to extract interpretable dimensions.
    These projections are learned from labeled product data.
    """
    # Each dimension has a learned projection vector
    # (trained on products labeled with these dimensions)
    
    form = sigmoid(dot(embedding, FORM_PROJECTION_VECTOR))
    color_warmth = sigmoid(dot(embedding, WARMTH_PROJECTION_VECTOR))
    color_saturation = sigmoid(dot(embedding, SATURATION_PROJECTION_VECTOR))
    formality = sigmoid(dot(embedding, FORMALITY_PROJECTION_VECTOR))
    proportion = sigmoid(dot(embedding, PROPORTION_PROJECTION_VECTOR))
    minimalism = sigmoid(dot(embedding, MINIMALISM_PROJECTION_VECTOR))
    edge = sigmoid(dot(embedding, EDGE_PROJECTION_VECTOR))
    
    RETURN InterpretableDimensions(
        form=form,
        color_warmth=color_warmth,
        color_saturation=color_saturation,
        formality=formality,
        proportion=proportion,
        minimalism=minimalism,
        edge=edge
    )


STRUCTURE ContextualPosition:
    """
    V3: Full per-context state including trajectory.
    """
    context: StyleContext
    
    # Position in embedding space
    position: StyleCoordinate
    
    # Per-context trajectory (V3 fix: not single trajectory anymore)
    trajectory: {
        direction: VECTOR[1536],              # In embedding space
        velocity: FLOAT,                      # Rate of change
        consistency: FLOAT,                   # Stability of this trajectory
        last_computed: DATETIME
    },
    
    # Context-specific embeddings
    embeddings: UserEmbeddings
    
    # Data quality metrics
    interaction_count: INT
    confidence: FLOAT
    last_interaction: DATETIME


STRUCTURE ComputedUserState:
    """
    V3: Computed at query time with per-context trajectories.
    """
    
    # Context-aware positions (one per detected context)
    detected_contexts: LIST[StyleContext]
    positions_by_context: MAP[StyleContext → ContextualPosition]
    
    # Active context for current query
    active_context: StyleContext
    active_position: ContextualPosition
    
    # Cross-context patterns
    universal_preferences: {
        always_preferred: LIST[STRING],
        always_avoided: LIST[STRING],
        stable_dimensions: LIST[STRING]       # Interpretable dimensions that don't vary
    }
    
    # Unified embeddings (blends across contexts + social)
    embeddings: UserEmbeddings
    
    # Social taste signal
    social_embeddings: SocialTasteEmbeddings
    
    # Spending patterns
    spending_patterns: SpendingPatterns
    
    # Behavioral patterns
    behavioral_patterns: BehavioralPatterns
    
    # Navigation parameters (from onboarding)
    nav_params: NavigationParameters


STRUCTURE RawUserData:
    """
    V3: Extended to include all onboarding data.
    """
    user_id: STRING
    
    # ═══════════════════════════════════════════════════════════════════════
    # ONBOARDING DATA
    # ═══════════════════════════════════════════════════════════════════════
    
    # Structured profile (from Interpretation LLM)
    onboarding_profile: OnboardingProfile
    
    # Raw conversations (full text for re-interpretation)
    raw_onboarding_conversations: LIST[{
        node: STRING,                         # "personal", "taste", etc.
        messages: LIST[{role: STRING, content: STRING}],
        timestamp: DATETIME
    }]
    
    # Navigation parameters (derived from onboarding)
    navigation_parameters: NavigationParameters
    
    # ═══════════════════════════════════════════════════════════════════════
    # BODY DATA
    # ═══════════════════════════════════════════════════════════════════════
    
    body_type: STRING
    coloring: STRING
    body_photo_url: STRING
    face_photo_url: STRING
    
    # ═══════════════════════════════════════════════════════════════════════
    # SOCIAL MEDIA
    # ═══════════════════════════════════════════════════════════════════════
    
    social_embeddings: SocialTasteEmbeddings
    
    # ═══════════════════════════════════════════════════════════════════════
    # INTERACTION HISTORY (products connect to user node)
    # ═══════════════════════════════════════════════════════════════════════
    
    interactions: LIST[{
        product_id: STRING,
        type: ENUM["viewed", "liked", "purchased", "rejected", "saved"],
        timestamp: DATETIME,
        context: {
            occasion: STRING,
            query: STRING,
            session_id: STRING,
            style_context: StyleContext        # Mapped context
        },
        feedback: {
            explicit_rating: INT,              # If provided
            time_spent_seconds: INT,
            returned_to_view: BOOL
        }
    }]
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONVERSATION HISTORY
    # ═══════════════════════════════════════════════════════════════════════
    
    conversation_history: LIST[{
        timestamp: DATETIME,
        messages: LIST[{role: STRING, content: STRING}],
        session_context: JSON,
        products_discussed: LIST[STRING]
    }]
    
    # ═══════════════════════════════════════════════════════════════════════
    # METADATA
    # ═══════════════════════════════════════════════════════════════════════
    
    created_at: DATETIME
    last_active: DATETIME
    onboarding_completed: BOOL
    calibration_completed: BOOL               # TBD: Post-onboarding calibration
```

---

### 1.4 Neo4j Storage Schema (V3 Addition)

The following schema defines how V3 navigation structures are persisted in Neo4j. This enables session continuity, trajectory tracking, and preference learning.

```
# ═══════════════════════════════════════════════════════════════════════════════
# V3 NODE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

NODE NavigationState:
    """
    Persists the current navigation state for a user.
    One per user, updated each session.
    """
    id: STRING (UUID)
    user_id: STRING

    # Current position (embedding serialized as JSON array)
    current_embedding: LIST[FLOAT]           # OpenAI 1536d
    current_visual_embedding: LIST[FLOAT]    # SigLIP 1024d (optional)

    # Active context
    active_context: STRING                   # StyleContext name

    # Session metadata
    session_id: STRING
    last_updated: DATETIME
    created_at: DATETIME


NODE ContextPosition:
    """
    Per-context position in style space.
    Users have multiple positions (one per context they've interacted in).
    """
    id: STRING (UUID)
    context: STRING                          # "work_professional", "casual_weekend", etc.

    # Position embedding
    embedding: LIST[FLOAT]                   # OpenAI 1536d
    visual_embedding: LIST[FLOAT]            # SigLIP 1024d (optional)

    # Quality metrics
    interaction_count: INT
    confidence: FLOAT                        # 0-1, based on data quality

    # Temporal
    first_interaction: DATETIME
    last_interaction: DATETIME


NODE StyleTrajectory:
    """
    Tracks style evolution over time within a context.
    Enables "you're moving toward X" insights.
    """
    id: STRING (UUID)
    context: STRING                          # Context this trajectory belongs to

    # Direction in embedding space
    direction_embedding: LIST[FLOAT]         # Normalized direction vector

    # Trajectory metrics
    velocity: FLOAT                          # Rate of change (0-1)
    consistency: FLOAT                       # How stable is this direction (0-1)

    # Temporal
    computed_from_window: STRING             # e.g., "30_days", "90_days"
    last_computed: DATETIME


# ═══════════════════════════════════════════════════════════════════════════════
# V3 RELATIONSHIP DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Navigation State Relationships
RELATIONSHIP (User)-[:HAS_NAV_STATE]->(NavigationState)
RELATIONSHIP (User)-[:HAS_CONTEXT_POSITION]->(ContextPosition)
RELATIONSHIP (ContextPosition)-[:HAS_TRAJECTORY]->(StyleTrajectory)

# Positive Interaction Signals (existing)
RELATIONSHIP (User)-[:VIEWED]->(Product)
    properties: {
        timestamp: DATETIME,
        session_id: STRING,
        context: STRING,
        time_spent_ms: INT,
        source: STRING                       # "search", "recommendation", "browse"
    }

RELATIONSHIP (User)-[:SAVED]->(Product)
    properties: {
        timestamp: DATETIME,
        session_id: STRING,
        context: STRING,
        collection_id: STRING                # Optional: which collection
    }

RELATIONSHIP (User)-[:PURCHASED]->(Product)
    properties: {
        timestamp: DATETIME,
        session_id: STRING,
        context: STRING,
        order_id: STRING,
        price_paid: FLOAT
    }

# ═══════════════════════════════════════════════════════════════════════════════
# V3 NEGATIVE SIGNAL RELATIONSHIPS (NEW)
# ═══════════════════════════════════════════════════════════════════════════════

RELATIONSHIP (User)-[:PASSED]->(Product)
    """
    User saw product but explicitly chose not to engage.
    Weak negative signal - may indicate "not for this context" vs "dislike".
    """
    properties: {
        timestamp: DATETIME,
        session_id: STRING,
        context: STRING,
        exposure_time_ms: INT,               # How long was it visible
        position_in_results: INT             # Where in the list
    }

RELATIONSHIP (User)-[:REJECTED]->(Product)
    """
    User explicitly rejected (thumbs down, "not for me", removed from consideration).
    Strong negative signal - use for exclusion in future recommendations.
    """
    properties: {
        timestamp: DATETIME,
        session_id: STRING,
        context: STRING,
        rejection_reason: STRING,            # Optional: if user provided
        source: STRING                       # "carousel", "comparison", "detail_page"
    }

RELATIONSHIP (User)-[:RETURNED]->(Product)
    """
    User purchased but returned.
    Strongest negative signal - indicates mismatch between expectation and reality.
    """
    properties: {
        timestamp: DATETIME,
        order_id: STRING,
        return_reason: STRING,               # "fit", "quality", "color", "style", "other"
        days_kept: INT,                      # How long before return
        original_purchase_context: STRING
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CYPHER EXAMPLES FOR V3 PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════

# Save navigation state after session
QUERY save_navigation_state(user_id, state):
    """
    MERGE (u:User {id: $user_id})
    MERGE (u)-[:HAS_NAV_STATE]->(ns:NavigationState {user_id: $user_id})
    SET ns.current_embedding = $embedding,
        ns.active_context = $context,
        ns.session_id = $session_id,
        ns.last_updated = datetime()
    """

# Save context position after interactions
QUERY save_context_position(user_id, context, position):
    """
    MERGE (u:User {id: $user_id})
    MERGE (u)-[:HAS_CONTEXT_POSITION]->(cp:ContextPosition {
        user_id: $user_id,
        context: $context
    })
    SET cp.embedding = $embedding,
        cp.interaction_count = cp.interaction_count + 1,
        cp.confidence = $confidence,
        cp.last_interaction = datetime()
    """

# Record negative signal (rejection)
QUERY record_rejection(user_id, product_id, context, reason):
    """
    MATCH (u:User {id: $user_id})
    MATCH (p:Product {id: $product_id})
    CREATE (u)-[:REJECTED {
        timestamp: datetime(),
        context: $context,
        rejection_reason: $reason,
        session_id: $session_id
    }]->(p)
    """

# Compute trajectory from recent interactions
QUERY compute_trajectory(user_id, context, days):
    """
    MATCH (u:User {id: $user_id})-[r:PURCHASED|SAVED|VIEWED]->(p:Product)
    WHERE r.context = $context
      AND r.timestamp > datetime() - duration({days: $days})
    WITH p ORDER BY r.timestamp
    RETURN p.embedding AS embeddings
    // Process in application layer to compute direction vector
    """

# Get products to exclude (negative signals)
QUERY get_exclusions(user_id):
    """
    MATCH (u:User {id: $user_id})-[:REJECTED|RETURNED]->(p:Product)
    RETURN COLLECT(DISTINCT p.id) AS excluded_ids
    """
```

---

## Section 2: Three Pillars - Knowledge Sources

### 2.1 Pillar 1: Personalization (Updated)

```
CLASS Pillar1_Personalization:
    """
    V3: Integrated onboarding + social media + interactions.
    """
    
    FUNCTION load_raw_user_data(user_id) → RawUserData:
        """
        Load complete user data from Neo4j.
        """
        user_data = neo4j.query("""
            MATCH (u:User {id: $user_id})
            
            // Get onboarding data
            OPTIONAL MATCH (u)-[:HAS_ONBOARDING]->(ob:OnboardingProfile)
            
            // Get body data
            OPTIONAL MATCH (u)-[:HAS_BODY_DATA]->(bd:BodyData)
            
            // Get social embeddings
            OPTIONAL MATCH (u)-[:HAS_SOCIAL_TASTE]->(st:SocialTasteEmbeddings)
            
            // Get navigation parameters
            OPTIONAL MATCH (u)-[:HAS_NAV_PARAMS]->(np:NavigationParameters)
            
            // Get interactions (products connected to user)
            OPTIONAL MATCH (u)-[r:INTERACTED_WITH]->(p:Product)
            
            // Get conversations
            OPTIONAL MATCH (u)-[:HAD_CONVERSATION]->(c:Conversation)
            
            RETURN u, ob, bd, st, np, 
                   collect(DISTINCT {
                       product_id: p.id,
                       type: r.type,
                       timestamp: r.timestamp,
                       context: r.context,
                       feedback: r.feedback
                   }) as interactions,
                   collect(DISTINCT c) as conversations
        """, user_id=user_id)
        
        RETURN RawUserData(
            user_id=user_id,
            onboarding_profile=parse_onboarding_profile(user_data.ob),
            raw_onboarding_conversations=user_data.ob.raw_conversations if user_data.ob else [],
            navigation_parameters=parse_nav_params(user_data.np),
            body_type=user_data.bd.body_verbal if user_data.bd else None,
            coloring=user_data.bd.coloring_verbal if user_data.bd else None,
            body_photo_url=user_data.bd.body_photo_url if user_data.bd else None,
            face_photo_url=user_data.bd.face_photo_url if user_data.bd else None,
            social_embeddings=parse_social_embeddings(user_data.st),
            interactions=user_data.interactions,
            conversation_history=user_data.conversations,
            created_at=user_data.u.created_at,
            last_active=user_data.u.last_active,
            onboarding_completed=user_data.ob is not None,
            calibration_completed=user_data.u.calibration_completed
        )
    
    FUNCTION compute_user_state(
        raw_data: RawUserData, 
        query_context: QueryContext
    ) → ComputedUserState:
        """
        V3: Compute state with per-context trajectories and social signals.
        """
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Detect style contexts from interactions
        # ═══════════════════════════════════════════════════════════════════
        
        detected_contexts = detect_user_contexts(raw_data.interactions)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Compute position + TRAJECTORY for EACH context
        # V3 fix: Per-context trajectories, not single trajectory
        # ═══════════════════════════════════════════════════════════════════
        
        positions_by_context = {}
        FOR context IN detected_contexts:
            context_interactions = filter_interactions_by_context(
                raw_data.interactions,
                context
            )
            
            IF len(context_interactions) >= 5:  # V3: Increased threshold
                position = compute_position_from_interactions(context_interactions)
                
                # V3: Per-context trajectory
                trajectory = compute_context_trajectory(
                    context_interactions,
                    context
                )
                
                embeddings = compute_user_embeddings(
                    raw_data, 
                    context_interactions,
                    raw_data.social_embeddings  # V3: Include social
                )
                
                positions_by_context[context] = ContextualPosition(
                    context=context,
                    position=position,
                    trajectory=trajectory,
                    embeddings=embeddings,
                    interaction_count=len(context_interactions),
                    confidence=min(1.0, len(context_interactions) / 30),
                    last_interaction=max(i.timestamp for i in context_interactions)
                )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Select active context
        # ═══════════════════════════════════════════════════════════════════
        
        active_context = select_active_context(
            query_context,
            detected_contexts,
            raw_data.onboarding_profile  # V3: Use onboarding occasions
        )
        
        IF active_context IN positions_by_context:
            active_position = positions_by_context[active_context]
        ELSE:
            # Cold start for this context - use onboarding + social
            active_position = compute_cold_start_position(
                raw_data,
                active_context
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Detect universal preferences
        # ═══════════════════════════════════════════════════════════════════
        
        universal_preferences = detect_universal_preferences(
            positions_by_context,
            raw_data.onboarding_profile  # V3: Use onboarding avoids
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: Compute unified embeddings (interactions + social)
        # ═══════════════════════════════════════════════════════════════════
        
        unified_embeddings = compute_unified_embeddings(
            active_position.embeddings,
            raw_data.social_embeddings,
            raw_data.navigation_parameters.user_embedding_weight
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: Other patterns
        # ═══════════════════════════════════════════════════════════════════
        
        spending_patterns = analyze_spending_patterns(
            raw_data.interactions,
            raw_data.onboarding_profile.practicality  # V3: Use onboarding budget
        )
        
        behavioral_patterns = detect_behavioral_patterns(raw_data.interactions)
        
        RETURN ComputedUserState(
            detected_contexts=detected_contexts,
            positions_by_context=positions_by_context,
            active_context=active_context,
            active_position=active_position,
            universal_preferences=universal_preferences,
            embeddings=unified_embeddings,
            social_embeddings=raw_data.social_embeddings,
            spending_patterns=spending_patterns,
            behavioral_patterns=behavioral_patterns,
            nav_params=raw_data.navigation_parameters
        )
    
    FUNCTION compute_context_trajectory(
        interactions: LIST[Interaction],
        context: StyleContext
    ) → Trajectory:
        """
        V3: Per-context trajectory computation.
        A user might evolve differently in different contexts.
        """
        IF len(interactions) < 10:
            RETURN Trajectory(
                direction=ZERO_VECTOR[1536],
                velocity=0.05,
                consistency=0.5,
                last_computed=now()
            )
        
        # Split by time
        recent = [i for i in interactions if i.timestamp > now() - days(30)]
        historical = [i for i in interactions if i.timestamp < now() - days(30)]
        
        IF len(recent) < 5 OR len(historical) < 5:
            RETURN Trajectory(
                direction=ZERO_VECTOR[1536],
                velocity=0.05,
                consistency=0.5,
                last_computed=now()
            )
        
        recent_embedding = compute_embedding_from_interactions(recent)
        historical_embedding = compute_embedding_from_interactions(historical)
        
        # Direction in embedding space
        direction = recent_embedding - historical_embedding
        magnitude = norm(direction)
        
        IF magnitude > 0:
            direction = direction / magnitude
        
        velocity = magnitude / 4  # Per week
        
        # Consistency: how stable is the evolution direction?
        consistency = compute_trajectory_consistency(interactions, direction)
        
        RETURN Trajectory(
            direction=direction,
            velocity=velocity,
            consistency=consistency,
            last_computed=now()
        )
    
    FUNCTION compute_unified_embeddings(
        interaction_embeddings: UserEmbeddings,
        social_embeddings: SocialTasteEmbeddings,
        user_weight: FLOAT
    ) → UserEmbeddings:
        """
        V3: Blend interaction history with social media signals.
        """
        # Weight social signals based on data richness
        social_weight = 0.0
        IF social_embeddings AND social_embeddings.unified_social_embedding:
            # Social matters more when interaction history is thin
            interaction_confidence = interaction_embeddings.confidence
            social_weight = (1 - interaction_confidence) * 0.5  # Up to 50%
        
        interaction_weight = 1.0 - social_weight
        
        # Blend semantic embeddings
        semantic = normalize(
            interaction_embeddings.semantic * interaction_weight +
            social_embeddings.unified_social_embedding * social_weight
        ) if social_embeddings else interaction_embeddings.semantic
        
        # Visual embeddings primarily from social (richer visual data)
        visual = social_embeddings.pinterest.overall_embedding \
            if social_embeddings and social_embeddings.pinterest else \
            interaction_embeddings.visual
        
        RETURN UserEmbeddings(
            semantic=semantic,
            visual=visual,
            multimodal=concatenate(semantic[:768], visual[:768]),
            source_weights={
                interactions: interaction_weight,
                social: social_weight
            },
            confidence=max(
                interaction_embeddings.confidence,
                0.3 if social_embeddings else 0.0
            )
        )
    
    FUNCTION compute_cold_start_position(
        raw_data: RawUserData,
        context: StyleContext
    ) → ContextualPosition:
        """
        V3: Better cold start using onboarding + social.
        """
        # First, check if onboarding has occasion-specific style info
        occasion_style = None
        IF raw_data.onboarding_profile:
            FOR occasion, style IN raw_data.onboarding_profile.taste.occasion_styles:
                IF map_occasion_to_context(occasion) == context:
                    occasion_style = style
                    BREAK
        
        # Generate initial embedding from available signals
        signals = []
        weights = []
        
        # 1. Onboarding style description
        IF occasion_style:
            style_text = occasion_style.description
            signals.append(openai.embed(style_text))
            weights.append(0.4)
        ELIF raw_data.onboarding_profile:
            # Use general style preferences
            style_text = f"""
                Loves: {raw_data.onboarding_profile.taste.style_loves}
                Wants more: {raw_data.onboarding_profile.taste.style_wants}
                Brands: {[b.brand for b in raw_data.onboarding_profile.taste.brand_preferences]}
            """
            signals.append(openai.embed(style_text))
            weights.append(0.3)
        
        # 2. Social taste embedding
        IF raw_data.social_embeddings and raw_data.social_embeddings.unified_social_embedding:
            signals.append(raw_data.social_embeddings.unified_social_embedding)
            weights.append(0.5)
        
        # 3. Population prior for context
        signals.append(get_population_centroid(context))
        weights.append(0.2)
        
        # Normalize weights and blend
        total = sum(weights)
        weights = [w / total for w in weights]
        
        embedding = normalize(sum(s * w for s, w in zip(signals, weights)))
        
        position = StyleCoordinate(
            embedding=embedding,
            visual_embedding=raw_data.social_embeddings.pinterest.overall_embedding \
                if raw_data.social_embeddings and raw_data.social_embeddings.pinterest \
                else ZERO_VECTOR[1024]
        )
        
        RETURN ContextualPosition(
            context=context,
            position=position,
            trajectory=Trajectory(
                direction=ZERO_VECTOR[1536],
                velocity=0.05,
                consistency=0.5,
                last_computed=now()
            ),
            embeddings=UserEmbeddings(
                semantic=embedding,
                visual=position.visual_embedding,
                multimodal=concatenate(embedding[:768], position.visual_embedding[:768]),
                confidence=0.3  # Low confidence for cold start
            ),
            interaction_count=0,
            confidence=0.3,
            last_interaction=None
        )
```

### 2.2 Pillar 2: Stylist Knowledge (Unchanged from V2)

```
# RAG architecture unchanged - see V2 specification
# Key capabilities:
# - FashionKnowledgeBase with hybrid search
# - Multiple perspectives (traditional, body-neutral, cultural, practical)
# - 6 curation principles
# - retrieve_multiple_perspectives() for diversity
```

### 2.3 Pillar 3: User Activity (Unchanged from V2)

```
# Behavioral pattern analysis unchanged - see V2 specification
# Key capabilities:
# - get_interaction_patterns()
# - detect_preference_drift()
# - get_recommendation_feedback()
```

---

## Section 3: LLM Integration Points

### 3.1 LLM #1: Onboarding Agent (External - Prompts Already Defined)

```
# The onboarding agent uses the prompts defined in ONBOARDING_PROMPTS_V2.py
# It outputs raw conversations that are stored in Neo4j
# See that file for full prompt structure

STRUCTURE OnboardingAgentOutput:
    """
    Output from the onboarding conversation.
    """
    raw_conversations: LIST[{
        node: STRING,
        messages: LIST[{role, content}]
    }]
    
    # Direct extractions (when user gives explicit values)
    explicit_values: {
        age: INT,
        location: STRING,
        occupation: STRING,
        creative_control: INT,          # 1-10
        adventurousness: INT,           # 1-10
        brand_loyalty: INT,             # 1-10
        budget_monthly: FLOAT,
        # ... other directly stated values
    }
    
    # Photos captured
    face_photo_id: STRING
    body_photo_id: STRING
    
    # Social accounts connected
    instagram_handle: STRING
    pinterest_handle: STRING
    tiktok_handle: STRING
```

### 3.2 LLM #2: Interpretation (New in V3)

```
CLASS InterpretationLLM:
    """
    Parses raw onboarding conversations into structured profile.
    Runs once after onboarding completion.
    """
    
    FUNCTION interpret_onboarding(
        raw_conversations: LIST[Conversation],
        explicit_values: Dict
    ) → OnboardingProfile:
        """
        Extract structured profile from conversational data.
        """
        
        prompt = f"""
You are an expert at understanding people's style preferences from conversation.

You've just had a conversation with someone about their style. Your job is to extract
a structured profile that captures both what they explicitly said AND what you can
infer from how they said it.

RAW CONVERSATIONS:
{format_conversations(raw_conversations)}

EXPLICITLY STATED VALUES:
{explicit_values}

Extract a complete OnboardingProfile with the following sections:

1. PERSONAL
   - Demographics, life context, occasions they dress for
   - Look for: What life stage? What matters to them? What's their world like?

2. TASTE  
   - Aesthetic preferences, brands, shapes, fits
   - Look for: What words do they use to describe style? What resonates?
   
3. PROCESS
   - How they make decisions, what motivates them
   - Look for: Control vs guidance preference, risk tolerance, validation sources
   
4. PRACTICALITY
   - Budget, constraints
   - Look for: How they think about value, not just the numbers
   
5. ROOT VALUES
   - The deeper "why" behind their style choices
   - Look for: What does style MEAN to them? Confidence? Belonging? Expression?

Be specific. Use their actual words when relevant. Infer what they implied but didn't say.

Output as JSON matching the OnboardingProfile schema.
"""
        
        response = llm.complete(prompt, response_format="json")
        profile = parse_onboarding_profile(response)
        
        # Derive navigation parameters
        profile.navigation_parameters = derive_navigation_parameters(profile)
        
        RETURN profile
    
    FUNCTION extract_root_values(
        raw_conversations: LIST[Conversation],
        profile: OnboardingProfile
    ) → RootValues:
        """
        Deep extraction of root values and motivations.
        """
        
        prompt = f"""
You are a psychologist specializing in self-expression and identity.

Review this style conversation and the extracted profile. Your job is to understand
the DEEPER motivations - what style means to this person at a fundamental level.

CONVERSATIONS:
{format_conversations(raw_conversations)}

PROFILE SUMMARY:
{summarize_profile(profile)}

Extract:

1. PRIMARY ROOT VALUE
   What is the single deepest motivation? Examples:
   - "Being seen as competent and taken seriously"
   - "Expressing my authentic self without caring what others think"  
   - "Fitting in with my community while still being me"
   - "Feeling confident and attractive"
   
2. SECONDARY VALUES
   What other values support the primary?

3. VALUE DIMENSIONS (0-1 scales)
   - authenticity_importance: Being true to self
   - belonging_importance: Fitting in
   - standing_out_importance: Being unique/noticed
   - comfort_importance: Physical and psychological ease
   - competence_importance: Appearing capable

4. VALUE TENSIONS
   Where do their values conflict? Examples:
   - "Wants to stand out but fears judgment"
   - "Values comfort but feels pressure to dress up for work"

Be insightful. Read between the lines. What do they REALLY want?

Output as JSON.
"""
        
        response = llm.complete(prompt, response_format="json")
        RETURN parse_root_values(response)
```

### 3.3 LLM #3: Synthesis (Updated from V2)

```
CLASS SynthesisLLM:
    """
    V3: Outputs style DESCRIPTORS, not coordinates.
    Coordinates are then derived via exemplar retrieval.
    """
    
    FUNCTION synthesize_navigation(
        pillars: ThreePillarsInput,
        query: STRING,
        occasion: STRING
    ) → SynthesisOutput:
        """
        V3: No more coordinate hallucination.
        LLM outputs descriptors → we retrieve exemplars → centroid = destination.
        """
        
        prompt = f"""
You are ARI, a style navigator. You help users traverse style space.

You have THREE PILLARS of knowledge:

PILLAR 1 - PERSONALIZATION (who they are):
- Body type: {pillars.body_type}
- Coloring: {pillars.coloring}
- Root values: {pillars.root_values.primary}
- Current position: {describe_position(pillars.current_position)}
- Trajectory: Moving {describe_trajectory(pillars.trajectory)}
- Navigation params: exploration={pillars.nav_params.exploration_appetite:.2f}, step={pillars.nav_params.step_size_multiplier:.2f}
- Behavioral patterns: Consistent on {pillars.behavioral_patterns.consistent_dimensions}, varies on {pillars.behavioral_patterns.variable_dimensions}

PILLAR 2 - STYLIST KNOWLEDGE (fashion expertise):
- Body guidance: {pillars.body_guidance}
- Occasion guidance: {pillars.occasion_guidance}
- Color guidance: {pillars.color_guidance}

PILLAR 3 - ACTIVITY (what they've done):
- Recent drift: {pillars.drift_analysis}
- Category interests: {pillars.category_interests}
- Spending patterns: {pillars.spending_patterns}

QUERY: "{query}"
OCCASION: {occasion or "not specified"}
CATEGORY DETECTED: {infer_category(query)}

YOUR TASK:
Based on all this, determine WHERE they want to go stylistically.

DO NOT output coordinates. Instead, describe the destination in words that can be used to search for exemplar products.

Output:
1. style_descriptors: List of 3-5 specific style terms (e.g., "minimalist structured blazer", "warm earth tones", "relaxed tailored fit")
2. exemplar_search_terms: 2-3 search queries to find products that represent the destination
3. understood_intent: What you understand they're looking for (1-2 sentences)
4. budget_interpretation: {{min, max}} for THIS query based on their patterns and the category
5. formality_level: 0-1 for THIS occasion
6. relevant_context: Key factors influencing your interpretation

Output as JSON.
"""
        
        response = llm.complete(prompt, response_format="json")
        
        RETURN SynthesisOutput(
            style_descriptors=response.style_descriptors,
            exemplar_search_terms=response.exemplar_search_terms,
            understood_intent=response.understood_intent,
            budget_interpretation=response.budget_interpretation,
            formality_level=response.formality_level,
            relevant_context=response.relevant_context
        )


FUNCTION compute_destination_from_synthesis(
    synthesis: SynthesisOutput,
    vector_store: Qdrant
) → StyleCoordinate:
    """
    V3: Convert LLM descriptors to coordinates via exemplar retrieval.
    This grounds the destination in actual product space.
    """
    
    exemplar_embeddings = []
    
    FOR search_term IN synthesis.exemplar_search_terms:
        # Search for products matching the descriptor
        query_embedding = openai.embed(search_term)
        
        results = vector_store.search(
            collection="fashion_products",
            query_vector=query_embedding,
            limit=5
        )
        
        # Collect embeddings of top results
        FOR product IN results:
            exemplar_embeddings.append(product.embedding)
    
    # Destination = centroid of exemplars
    IF len(exemplar_embeddings) == 0:
        # Fallback: embed the descriptors directly
        descriptor_text = " ".join(synthesis.style_descriptors)
        destination_embedding = openai.embed(descriptor_text)
    ELSE:
        destination_embedding = normalize(mean(exemplar_embeddings))
    
    RETURN StyleCoordinate(
        embedding=destination_embedding,
        visual_embedding=ZERO_VECTOR[1024]  # Visual determined by actual search
    )
```

### 3.4 Query Agents (V3.2 Addition)

Two LLM-powered query agents enhance search quality by understanding natural language intent:

```
CLASS Text2CypherGenerator:
    """
    Converts natural language to Cypher queries for Neo4j.
    Works with ANY field: brand, color, price, style, material, etc.

    Neo4j has structured data (extracted_brand, extracted_colors, extracted_styles)
    that Qdrant embeddings cannot filter precisely.
    """

    FUNCTION generate_cypher(query: STRING) → CypherQuery:
        """
        Use LLM to generate appropriate Cypher from natural language.

        Example:
            Input:  "Show me Gucci bags under $500"
            Output: MATCH (p:Product)
                    WHERE toLower(p.extracted_brand) = 'gucci'
                    AND p.price < 500
                    RETURN p LIMIT 50
        """

        prompt = format_cypher_prompt(
            schema=NEO4J_PRODUCT_SCHEMA,  # id, title, extracted_brand, price, etc.
            query=query
        )

        response = llm.generate(prompt, response_format="json")

        RETURN CypherQuery(
            cypher=response.cypher,
            parameters=response.parameters,
            search_fields=response.fields_used
        )


CLASS SemanticQueryGenerator:
    """
    Expands queries with style understanding for Qdrant embedding search.
    Understands fashion aesthetics, vibes, and occasions.
    """

    FUNCTION expand_query(query: STRING) → SemanticQuery:
        """
        Use LLM to expand query with synonyms, style terms, and context.

        Example:
            Input:  "boho chic summer dress"
            Output: SemanticQuery(
                expanded="boho chic summer dress bohemian relaxed
                         flowy earthy natural free-spirited lightweight",
                style_terms=["boho", "chic", "relaxed", "flowy"],
                color_terms=["earth tones", "pastels"],
                occasion="summer",
                price_hint="mid-range"
            )
        """

        prompt = format_semantic_prompt(query)
        response = llm.generate(prompt, response_format="json")

        RETURN SemanticQuery(
            original_query=query,
            expanded_query=response.expanded,
            style_terms=response.styles,
            color_terms=response.colors,
            occasion=response.occasion,
            filters=build_qdrant_filters(response)
        )
```

**Query Routing Logic:**
```
FUNCTION route_query(query: STRING, params: ExtractedParameters) → SearchStrategy:
    """
    Determine whether to use Neo4j (structured) or Qdrant (semantic) search.
    """

    # Neo4j for structured field queries (brand, specific attributes)
    IF params.brand_preferences OR query_needs_structured_search(query):
        cypher = Text2CypherGenerator.generate_cypher(query)
        products = neo4j.execute(cypher)
        RETURN products

    # Qdrant for semantic/vibe queries (style, aesthetic, mood)
    ELSE:
        semantic = SemanticQueryGenerator.expand_query(query)
        embedding = openai.embed(semantic.expanded_query)
        products = qdrant.search(embedding, filters=semantic.filters)
        RETURN products
```

### 3.5 LLM #4: Narrative (V3)

```
CLASS NarrativeLLM:
    """
    Generates journey narrative using root values and validation sources.
    """
    
    FUNCTION generate_narrative(
        nav_context: NavigationContext,
        products: LIST[Product],
        user_profile: OnboardingProfile
    ) → JourneyNarrative:
        """
        V3: Personalized narrative using root values.
        """
        
        # Determine framing based on validation sources
        primary_validation = user_profile.process.validation_sources[0].source \
            if user_profile.process.validation_sources else "self"
        
        IF primary_validation == "self":
            framing = "how these pieces express who you are"
        ELIF primary_validation == "partner":
            framing = "pieces your partner would love seeing you in"
        ELIF primary_validation == "colleagues":
            framing = "how you'll be perceived professionally"
        ELIF primary_validation == "strangers":
            framing = "the impression you'll make"
        ELSE:
            framing = "your style journey"
        
        prompt = f"""
You are ARI, a style navigator with a warm, wise personality.

You've just helped someone find products. Now create a brief narrative that:
1. Connects to their ROOT VALUE: "{user_profile.root_values.primary}"
2. Frames recommendations around: {framing}
3. Explains WHY each piece works for them specifically

USER CONTEXT:
- Style motivation: {user_profile.process.style_motivations[0].motivation if user_profile.process.style_motivations else "self-expression"}
- They want MORE: {user_profile.taste.style_wants}
- They AVOID: {user_profile.taste.style_avoids}
- Occasion: {nav_context.occasion}

NAVIGATION:
- Current: {describe_interpretable(nav_context.current_position)}
- Destination: {describe_interpretable(nav_context.destination)}

PRODUCTS SELECTED:
{format_products_for_narrative(products)}

Write a brief (3-4 sentence) opening narrative, then 1 sentence per product explaining why it's right for THEM specifically.

Be warm but concise. Sound human, not robotic. Reference their actual words when relevant.
"""
        
        response = llm.complete(prompt)
        
        RETURN JourneyNarrative(
            opening=extract_opening(response),
            product_explanations=extract_product_explanations(response, products),
            closing=extract_closing(response)
        )
```

---

## Section 4: Navigation Intelligence Core (Updated)

```
CLASS NavigationIntelligence:
    """
     Updated flow with multiple LLM calls and exemplar-based destination.
    """
    
    FUNCTION generate_navigation_context(
        user_id: STRING,
        query: STRING,
        occasion: STRING
    ) → NavigationContext:
        """
        Main entry point.
        """
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Load raw user data
        # ═══════════════════════════════════════════════════════════════════
        
        raw_user_data = pillars.personalization.load_raw_user_data(user_id)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Compute user state (per-context positions + trajectories)
        # ═══════════════════════════════════════════════════════════════════
        
        query_context = QueryContext(query=query, occasion=occasion)
        computed_state = pillars.personalization.compute_user_state(
            raw_user_data, 
            query_context
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Get behavioral patterns (Pillar 3)
        # ═══════════════════════════════════════════════════════════════════
        
        PARALLEL:
            behavioral = pillars.activity.get_interaction_patterns(
                user_id, 
                context_filter=computed_state.active_context
            )
            drift = pillars.activity.detect_preference_drift(user_id)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Retrieve stylist knowledge (Pillar 2 - RAG)
        # ═══════════════════════════════════════════════════════════════════
        
        styling_context = build_styling_context(
            raw_user_data.onboarding_profile,
            computed_state,
            query,
            occasion
        )
        
        PARALLEL:
            styling_rules = pillars.knowledge.query_styling_rules(styling_context)
            body_guidance = pillars.knowledge.get_body_type_rules(
                raw_user_data.body_type,
                infer_category(query)
            )
            occasion_guidance = pillars.knowledge.get_occasion_rules(occasion)
            
            # V3: Multiple perspectives
            perspectives = pillars.knowledge.retrieve_multiple_perspectives(
                query=query,
                topic=infer_category(query),
                user_cultural_context=raw_user_data.onboarding_profile.personal.cultural_background
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: LLM SYNTHESIS (V3: outputs descriptors, not coordinates)
        # ═══════════════════════════════════════════════════════════════════
        
        pillars_input = ThreePillarsInput(
            # Pillar 1
            body_type=raw_user_data.body_type,
            coloring=raw_user_data.coloring,
            root_values=raw_user_data.onboarding_profile.root_values,
            current_position=computed_state.active_position.position,
            trajectory=computed_state.active_position.trajectory,
            nav_params=computed_state.nav_params,
            behavioral_patterns=computed_state.behavioral_patterns,
            
            # Pillar 2
            body_guidance=body_guidance,
            occasion_guidance=occasion_guidance,
            color_guidance=perspectives.get("traditional", {}).get("summary", ""),
            
            # Pillar 3
            drift_analysis=drift,
            category_interests=behavioral.category_interests,
            spending_patterns=computed_state.spending_patterns
        )
        
        synthesis = synthesis_llm.synthesize_navigation(
            pillars=pillars_input,
            query=query,
            occasion=occasion
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: COMPUTE DESTINATION FROM EXEMPLARS (V3 fix)
        # ═══════════════════════════════════════════════════════════════════
        
        destination = compute_destination_from_synthesis(
            synthesis=synthesis,
            vector_store=qdrant
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 7: Calculate navigation path (deterministic)
        # V3: Uses nav_params from onboarding
        # ═══════════════════════════════════════════════════════════════════
        
        path = calculate_navigation_path(
            current=computed_state.active_position.position,
            destination=destination,
            trajectory=computed_state.active_position.trajectory,
            nav_params=computed_state.nav_params  # V3: Use derived params
        )
        
        RETURN NavigationContext(
            current_position=computed_state.active_position.position,
            trajectory=computed_state.active_position.trajectory,
            destination=destination,
            path=path,
            raw_user_data=raw_user_data,
            computed_state=computed_state,
            styling_rules=styling_rules,
            body_guidance=body_guidance,
            occasion_guidance=occasion_guidance,
            behavioral_profile=behavioral,
            drift_analysis=drift,
            query=query,
            occasion=occasion,
            synthesis=synthesis,
            perspectives=perspectives
        )
    
    FUNCTION calculate_navigation_path(
        current: StyleCoordinate,
        destination: StyleCoordinate,
        trajectory: Trajectory,
        nav_params: NavigationParameters
    ) → NavigationPath:
        """
        V3: Uses navigation parameters from onboarding.
        """
        
        total_distance = cosine_distance(current.embedding, destination.embedding)
        
        # V3: Step size from nav_params
        base_step = 0.3
        max_step = base_step * nav_params.step_size_multiplier
        
        # Velocity adjustment
        IF trajectory.velocity < 0.03:
            max_step *= 0.7  # Conservative for slow movers
        ELIF trajectory.velocity > 0.06:
            max_step *= 1.2  # Aggressive for fast movers
        
        # Outlier percentage from nav_params
        outlier_percentage = nav_params.exploration_appetite * 0.20
        
        RETURN NavigationPath(
            current_position=current,
            destination=destination,
            max_step_size=max_step,
            outlier_percentage=outlier_percentage,
            diversity_requirement=nav_params.diversity_requirement,
            smoothness_score=1.0 if total_distance <= max_step else 0.7,
            coherence_score=compute_coherence(current, destination, trajectory.direction)
        )
```

---

## Section 5: Navigation-Aware Agents (Updated)

### 5.0 VibeBot and VisionBot (Unchanged from V2)

```
# VibeBot_Navigator and VisionBot_Navigator implementations remain unchanged from V2.
# See V2 specification for full implementation details.
#
# Key points:
# - VibeBot: Semantic search using user embedding + query embedding blend
# - VisionBot: Visual search using user visual embedding + deterministic filters
# - Both use adaptive weighting based on user confidence and query specificity
# - Both use nav_params.user_embedding_weight for user vs query balance
#
# The only change in V3 is that they receive NavigationContext with the new
# computed_state structure including per-context positions and social embeddings.
```

### 5.1 Ari with MMR Diversity (V3 Update)

```
CLASS Ari_PathEvaluator:
    """
    V3: Added MMR (Maximal Marginal Relevance) for result diversity.
    """
    
    FUNCTION evaluate_and_select(
        vibe_results: LIST[Product],
        vision_results: LIST[Product],
        graph_results: LIST[Product],
        nav_context: NavigationContext,
        limit: INT = None
    ) → LIST[Product]:
        
        # V3: Use nav_params for result count
        IF limit IS None:
            limit = nav_context.computed_state.nav_params.result_set_size
        
        all_products = deduplicate(vibe_results + vision_results + graph_results)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Score all products
        # ═══════════════════════════════════════════════════════════════════
        
        FOR product IN all_products:
            scores = {}
            
            # 1. SMOOTHNESS: Step distance
            step_distance = cosine_distance(
                nav_context.current_position.embedding,
                product.embedding
            )
            scores.smoothness = 1.0 if step_distance <= nav_context.path.max_step_size else \
                               max(0, 1.0 - step_distance)
            
            # 2. COHERENCE: Trajectory alignment
            direction_to_product = product.embedding - nav_context.current_position.embedding
            IF norm(direction_to_product) > 0:
                direction_to_product = direction_to_product / norm(direction_to_product)
            trajectory_dot = dot(nav_context.trajectory.direction, direction_to_product)
            scores.coherence = max(0, min(1, trajectory_dot + 0.5))
            
            # 3. BUDGET FIT
            budget = nav_context.synthesis.budget_interpretation
            IF product.price <= budget["max"]:
                IF product.price >= budget["min"]:
                    scores.budget_fit = 1.0
                ELSE:
                    scores.budget_fit = 0.8
            ELSE:
                scores.budget_fit = max(0, 1.0 - (product.price - budget["max"]) / budget["max"])
            
            # 4. BRAND AFFINITY (V3: from nav_params)
            brand_weight = nav_context.computed_state.nav_params.brand_affinity_weight
            IF product.brand IN user_preferred_brands:
                scores.brand_match = brand_weight
            ELSE:
                scores.brand_match = 0.0
            
            # 5. BEHAVIORAL CONSISTENCY
            scores.behavioral_consistency = compute_behavioral_consistency(
                product,
                nav_context.computed_state.behavioral_patterns
            )
            
            # 6. MULTI-AGENT CONFIDENCE
            in_vibe = product IN vibe_results
            in_vision = product IN vision_results
            in_graph = product IN graph_results
            agent_count = sum([in_vibe, in_vision, in_graph])
            scores.multi_agent = 0.6 + (agent_count - 1) * 0.2
            
            # 7. RULE COMPLIANCE
            scores.rule_compliance = evaluate_rule_compliance(
                product,
                nav_context.styling_rules,
                nav_context.body_guidance
            )
            
            # Weighted combination
            product.relevance_score = (
                scores.smoothness * 0.15 +
                scores.coherence * 0.10 +
                scores.budget_fit * 0.15 +
                scores.brand_match * 0.10 +
                scores.behavioral_consistency * 0.20 +
                scores.multi_agent * 0.10 +
                scores.rule_compliance * 0.20
            )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: MMR DIVERSITY SELECTION (V3)
        # ═══════════════════════════════════════════════════════════════════
        
        lambda_param = nav_context.computed_state.nav_params.diversity_requirement
        main_count = int(limit * (1 - nav_context.path.outlier_percentage))
        
        selected = mmr_select(
            candidates=all_products,
            limit=main_count,
            lambda_param=lambda_param
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: OUTLIER INJECTION (unchanged from V2)
        # ═══════════════════════════════════════════════════════════════════
        
        outlier_count = limit - main_count
        IF outlier_count > 0:
            remaining = [p for p in all_products if p not in selected]
            outlier_candidates = [p for p in remaining
                                 if cosine_distance(
                                     nav_context.current_position.embedding,
                                     p.embedding
                                 ) > 0.4]
            
            IF len(outlier_candidates) >= outlier_count:
                outliers = random.sample(outlier_candidates, outlier_count)
            ELSE:
                outliers = outlier_candidates
            
            selected.extend(outliers)
        
        RETURN selected
    
    FUNCTION mmr_select(
        candidates: LIST[Product],
        limit: INT,
        lambda_param: FLOAT
    ) → LIST[Product]:
        """
        Maximal Marginal Relevance selection.
        Balances relevance with diversity.
        
        lambda_param: 1.0 = pure relevance, 0.0 = pure diversity
        """
        
        IF len(candidates) == 0:
            RETURN []
        
        # Sort by relevance
        sorted_candidates = sorted(candidates, key=lambda p: p.relevance_score, reverse=TRUE)
        
        # Start with most relevant
        selected = [sorted_candidates[0]]
        remaining = sorted_candidates[1:]
        
        WHILE len(selected) < limit AND len(remaining) > 0:
            best_mmr = -inf
            best_idx = 0
            
            FOR i, candidate IN enumerate(remaining):
                # Relevance term
                relevance = candidate.relevance_score
                
                # Diversity term: max similarity to already selected
                max_sim = max(
                    cosine_similarity(candidate.embedding, s.embedding)
                    for s in selected
                )
                
                # MMR score
                mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
                
                IF mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i
            
            selected.append(remaining[best_idx])
            remaining.pop(best_idx)
        
        RETURN selected
```

---

## Section 6: Main Orchestration (Updated)

```
CLASS NavigationOrchestrator:
    """
    V3.1: Product search orchestration with narrative generation.

    NOTE: This is called by ARIOrchestrator (Section 0.5) ONLY when
    intent is detected as PRODUCT_SEARCH, STYLE_ADVICE, etc.
    For conversation intents, ARIOrchestrator routes to ConversationHandler instead.

    Flow:
    User Input → IntentDetector → ARIOrchestrator
                                      ├─→ [PRODUCT] → NavigationOrchestrator (this class)
                                      └─→ [CONVERSATION] → ConversationHandler
    """
    
    ASYNC FUNCTION execute_search(
        user_id: STRING,
        query: STRING,
        occasion: STRING = None
    ) → SearchResult:
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Generate Navigation Context
        # ═══════════════════════════════════════════════════════════════════
        
        nav_context = await navigation_intelligence.generate_navigation_context(
            user_id=user_id,
            query=query,
            occasion=occasion
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Agent Execution
        # ═══════════════════════════════════════════════════════════════════
        
        query_analysis = analyze_query(query)
        use_graph = config.should_enable_graph_agent(query_analysis)
        
        IF use_graph:
            PARALLEL:
                vibe_results = await agents.vibe.search(nav_context)
                vision_results = await agents.vision.search(nav_context)
                graph_results = await agents.graph.search(nav_context)
        ELSE:
            graph_results = []
            PARALLEL:
                vibe_results = await agents.vibe.search(nav_context)
                vision_results = await agents.vision.search(nav_context)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Ari Evaluation with MMR
        # ═══════════════════════════════════════════════════════════════════
        
        final_products = await agents.Ari.evaluate_and_select(
            vibe_results=vibe_results,
            vision_results=vision_results,
            graph_results=graph_results,
            nav_context=nav_context
            # limit comes from nav_params
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Generate Narrative (V3 - LLM #4)
        # ═══════════════════════════════════════════════════════════════════
        
        narrative = await narrative_llm.generate_narrative(
            nav_context=nav_context,
            products=final_products,
            user_profile=nav_context.raw_user_data.onboarding_profile
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: Track for Feedback Loop
        # ═══════════════════════════════════════════════════════════════════
        
        session_id = await track_recommendation_session(
            user_id=user_id,
            nav_context=nav_context,
            products_shown=final_products,
            agents_used=["vibe", "vision"] + (["graph"] if use_graph else []),
            narrative=narrative
        )
        
        RETURN SearchResult(
            products=final_products,
            narrative=narrative,
            path=nav_context.path,
            session_id=session_id,
            metadata={
                "current_position": describe_interpretable(nav_context.current_position),
                "destination": describe_interpretable(nav_context.destination),
                "synthesis": nav_context.synthesis,
                "nav_params": nav_context.computed_state.nav_params,
                "agents_used": ["vibe", "vision"] + (["graph"] if use_graph else [])
            }
        )
```

---

## Section 7: Cold Start Handling (Rewritten)

```
FUNCTION handle_cold_start(user_id) → ComputedUserState:
    """
    V3: Much improved cold start using onboarding + social.
    """
    
    raw_data = pillars.personalization.load_raw_user_data(user_id)
    
    # ═══════════════════════════════════════════════════════════════════════
    # CASE 1: Has onboarding profile
    # ═══════════════════════════════════════════════════════════════════════
    
    IF raw_data.onboarding_completed:
        profile = raw_data.onboarding_profile
        
        # Generate initial position from onboarding + social
        initial_position = compute_cold_start_position_from_profile(profile, raw_data.social_embeddings)
        
        # Navigation params from onboarding
        nav_params = raw_data.navigation_parameters
        
        # Create positions for each occasion mentioned
        positions_by_context = {}
        FOR occasion IN profile.personal.occasions:
            context = occasion.style_context
            
            occasion_style = profile.taste.occasion_styles.get(occasion.name, None)
            position = compute_occasion_position(
                occasion_style,
                initial_position,
                raw_data.social_embeddings
            )
            
            positions_by_context[context] = ContextualPosition(
                context=context,
                position=position,
                trajectory=Trajectory(
                    direction=ZERO_VECTOR[1536],
                    velocity=profile.process.adventurousness / 100,  # Scale to reasonable velocity
                    consistency=0.5,
                    last_computed=now()
                ),
                embeddings=UserEmbeddings(
                    semantic=position.embedding,
                    visual=position.visual_embedding,
                    multimodal=concatenate(position.embedding[:768], position.visual_embedding[:768]),
                    confidence=0.4
                ),
                interaction_count=0,
                confidence=0.4,
                last_interaction=None
            )
        
        RETURN ComputedUserState(
            detected_contexts=list(positions_by_context.keys()),
            positions_by_context=positions_by_context,
            active_context=StyleContext.DEFAULT,
            active_position=positions_by_context.get(StyleContext.DEFAULT, list(positions_by_context.values())[0]),
            universal_preferences={
                always_preferred=[],
                always_avoided=parse_avoids(profile.taste.style_avoids),
                stable_dimensions=[]
            },
            embeddings=initial_position.embeddings,
            social_embeddings=raw_data.social_embeddings,
            spending_patterns=SpendingPatterns(
                by_category={},
                by_occasion={},
                by_context={},
                overall=profile.practicality.budget
            ),
            behavioral_patterns=BehavioralPatterns(
                consistent_dimensions=[],
                variable_dimensions=ALL_DIMENSIONS,
                preferred_categories=[],
                avoided_categories=[]
            ),
            nav_params=nav_params
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # CASE 2: Has social but no onboarding (partial cold start)
    # ═══════════════════════════════════════════════════════════════════════
    
    ELIF raw_data.social_embeddings AND raw_data.social_embeddings.unified_social_embedding:
        position = StyleCoordinate(
            embedding=raw_data.social_embeddings.unified_social_embedding,
            visual_embedding=raw_data.social_embeddings.pinterest.overall_embedding \
                if raw_data.social_embeddings.pinterest else ZERO_VECTOR[1024]
        )
        
        # Default navigation params (middle of the road)
        nav_params = NavigationParameters(
            exploration_appetite=0.3,
            step_size_multiplier=1.0,
            brand_affinity_weight=0.5,
            result_set_size=10,
            diversity_requirement=0.5,
            user_embedding_weight=0.5,
            default_budget={min: 20, max: 200, flexibility: 0.4},
            category_budget_overrides={}
        )
        
        default_position = ContextualPosition(
            context=StyleContext.DEFAULT,
            position=position,
            trajectory=DEFAULT_TRAJECTORY,
            embeddings=UserEmbeddings(semantic=position.embedding, confidence=0.3),
            interaction_count=0,
            confidence=0.3
        )
        
        RETURN ComputedUserState(
            detected_contexts=[StyleContext.DEFAULT],
            positions_by_context={StyleContext.DEFAULT: default_position},
            active_context=StyleContext.DEFAULT,
            active_position=default_position,
            nav_params=nav_params
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # CASE 3: Truly new user (no onboarding, no social)
    # ═══════════════════════════════════════════════════════════════════════
    
    ELSE:
        position = StyleCoordinate(
            embedding=get_population_median_embedding(),
            visual_embedding=ZERO_VECTOR[1024]
        )
        
        nav_params = DEFAULT_NAVIGATION_PARAMETERS
        
        default_position = ContextualPosition(
            context=StyleContext.DEFAULT,
            position=position,
            trajectory=DEFAULT_TRAJECTORY,
            embeddings=UserEmbeddings(semantic=position.embedding, confidence=0.1),
            interaction_count=0,
            confidence=0.1
        )
        
        RETURN ComputedUserState(
            detected_contexts=[StyleContext.DEFAULT],
            positions_by_context={StyleContext.DEFAULT: default_position},
            active_context=StyleContext.DEFAULT,
            active_position=default_position,
            nav_params=nav_params
        )


FUNCTION compute_cold_start_position_from_profile(
    profile: OnboardingProfile,
    social_embeddings: SocialTasteEmbeddings
) → StyleCoordinate:
    """
    Generate initial position from onboarding profile.
    """
    
    signals = []
    weights = []
    
    # 1. Style description embedding
    style_text = f"""
        Style loves: {profile.taste.style_loves}
        Style wants: {profile.taste.style_wants}
        Fit preference: {profile.taste.fit_preferences}
        Brands: {[b.brand for b in profile.taste.brand_preferences]}
    """
    signals.append(openai.embed(style_text))
    weights.append(0.3)
    
    # 2. Social embedding (if available)
    IF social_embeddings AND social_embeddings.unified_social_embedding:
        signals.append(social_embeddings.unified_social_embedding)
        weights.append(0.5)
    
    # 3. Demographic prior
    demographic_text = f"""
        {profile.personal.age} year old
        {profile.personal.occupation.title} in {profile.personal.occupation.industry}
        {profile.personal.location.urban_suburban_rural} in {profile.personal.location.city}
    """
    demographic_embedding = get_demographic_prior(demographic_text)
    signals.append(demographic_embedding)
    weights.append(0.2)
    
    # Normalize and blend
    total = sum(weights)
    weights = [w / total for w in weights]
    
    embedding = normalize(sum(s * w for s, w in zip(signals, weights)))
    
    visual_embedding = social_embeddings.pinterest.overall_embedding \
        if social_embeddings and social_embeddings.pinterest else ZERO_VECTOR[1024]
    
    RETURN StyleCoordinate(
        embedding=embedding,
        visual_embedding=visual_embedding
    )
```

---

## Section 8: Feedback Loop (New in V3)

CLASS FeedbackLoop:
    """
    V3: Learn from recommendation outcomes.
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RE-INTERPRETATION TRIGGER
    # When behavior diverges significantly from onboarding, update the profile
    # ═══════════════════════════════════════════════════════════════════════════
    
    FUNCTION check_reinterpretation_trigger(user_id) → BOOL:
        """
        Detect when behavioral patterns diverge significantly from onboarding.
        If triggered, re-run LLM #2 to update root values and profile.
        """
        raw_data = load_raw_user_data(user_id)
        
        IF NOT raw_data.onboarding_completed:
            RETURN FALSE
        
        IF len(raw_data.interactions) < 30:
            RETURN FALSE  # Not enough data to detect divergence
        
        profile = raw_data.onboarding_profile
        behavioral = compute_behavioral_patterns(raw_data.interactions)
        
        divergence_signals = []
        
        # 1. Budget divergence: spending consistently outside stated range
        stated_budget = profile.practicality.budget
        actual_spending = compute_actual_spending(raw_data.interactions)
        IF actual_spending.median > stated_budget.monthly * 1.5:
            divergence_signals.append("spending_above_stated")
        IF actual_spending.median < stated_budget.monthly * 0.3:
            divergence_signals.append("spending_below_stated")
        
        # 2. Adventurousness divergence: behavior vs stated preference
        stated_adventurousness = profile.process.adventurousness / 10.0
        actual_exploration = compute_style_variance(raw_data.interactions)
        IF abs(actual_exploration - stated_adventurousness) > 0.4:
            divergence_signals.append("adventurousness_mismatch")
        
        # 3. Style avoidance violation: buying what they said they avoid
        stated_avoids = parse_avoids(profile.taste.style_avoids)
        purchased_styles = extract_styles(raw_data.interactions, type="purchased")
        overlap = intersection(stated_avoids, purchased_styles)
        IF len(overlap) >= 3:
            divergence_signals.append("buying_stated_avoids")
        
        # 4. Context divergence: occasions used vs stated occasions
        stated_contexts = [o.style_context for o in profile.personal.occasions]
        actual_contexts = detect_user_contexts(raw_data.interactions)
        new_contexts = [c for c in actual_contexts if c not in stated_contexts]
        IF len(new_contexts) >= 2:
            divergence_signals.append("new_life_contexts")
        
        # 5. Brand loyalty divergence
        stated_loyalty = profile.process.brand_loyalty / 10.0
        actual_loyalty = compute_brand_repeat_rate(raw_data.interactions)
        IF abs(actual_loyalty - stated_loyalty) > 0.4:
            divergence_signals.append("brand_loyalty_mismatch")
        
        # Trigger if 2+ divergence signals
        RETURN len(divergence_signals) >= 2
    
    ASYNC FUNCTION run_reinterpretation(user_id):
        """
        Re-run LLM #2 with both onboarding AND behavioral data.
        Updates profile and root values.
        """
        raw_data = load_raw_user_data(user_id)
        behavioral_summary = summarize_behavioral_patterns(raw_data.interactions)
        
        # LLM #2 with additional behavioral context
        updated_profile = interpretation_llm.reinterpret_with_behavior(
            original_conversations=raw_data.raw_onboarding_conversations,
            original_profile=raw_data.onboarding_profile,
            behavioral_summary=behavioral_summary,
            divergence_notes=get_divergence_notes(user_id)
        )
        
        # Update navigation parameters
        updated_nav_params = derive_navigation_parameters(updated_profile)
        
        # Persist updates
        await neo4j.query("""
            MATCH (u:User {id: $user_id})-[:HAS_ONBOARDING]->(ob)
            SET ob = $updated_profile,
                ob.reinterpreted_at = datetime(),
                ob.reinterpretation_count = coalesce(ob.reinterpretation_count, 0) + 1
            
            WITH u
            MATCH (u)-[:HAS_NAV_PARAMS]->(np)
            SET np = $updated_nav_params
        """, 
            user_id=user_id,
            updated_profile=updated_profile,
            updated_nav_params=updated_nav_params
        )
        
        log.info(f"Reinterpreted profile for user {user_id}")
    
    ASYNC FUNCTION on_interaction(user_id, interaction):
        """
        Called after each user interaction.
        Checks for re-interpretation trigger every 20 interactions.
        """
        await record_interaction(user_id, interaction)
        
        interaction_count = get_interaction_count(user_id)
        IF interaction_count % 20 == 0:
            IF check_reinterpretation_trigger(user_id):
                await run_reinterpretation(user_id)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SESSION TRACKING
    # ═══════════════════════════════════════════════════════════════════════════
    
    ASYNC FUNCTION track_recommendation_session(
        user_id: STRING,
        nav_context: NavigationContext,
        products_shown: LIST[Product],
        agents_used: LIST[STRING],
        narrative: JourneyNarrative
    ) → STRING:
        """
        Create tracking record for a recommendation session.
        """
        
        session_id = generate_uuid()
        
        await neo4j.query("""
            CREATE (s:RecommendationSession {
                id: $session_id,
                user_id: $user_id,
                timestamp: datetime(),
                
                // Navigation context
                query: $query,
                occasion: $occasion,
                active_context: $active_context,
                
                // Synthesis output
                style_descriptors: $style_descriptors,
                destination_embedding: $destination_embedding,
                
                // Configuration
                nav_params: $nav_params,
                agents_used: $agents_used,
                
                // Products shown
                product_ids: $product_ids,
                product_scores: $product_scores
            })
            
            // Link to user
            WITH s
            MATCH (u:User {id: $user_id})
            CREATE (u)-[:HAD_SESSION]->(s)
            
            // Link to products shown
            WITH s
            UNWIND $product_ids AS pid
            MATCH (p:Product {id: pid})
            CREATE (s)-[:SHOWED]->(p)
        """,
            session_id=session_id,
            user_id=user_id,
            query=nav_context.query,
            occasion=nav_context.occasion,
            active_context=str(nav_context.computed_state.active_context),
            style_descriptors=nav_context.synthesis.style_descriptors,
            destination_embedding=nav_context.destination.embedding.tolist(),
            nav_params=serialize_nav_params(nav_context.computed_state.nav_params),
            agents_used=agents_used,
            product_ids=[p.id for p in products_shown],
            product_scores=[p.relevance_score for p in products_shown]
        )
        
        RETURN session_id
    
    ASYNC FUNCTION record_outcome(
        session_id: STRING,
        product_id: STRING,
        outcome: ENUM["viewed", "clicked", "liked", "purchased", "rejected"],
        time_spent_seconds: INT = None,
        explicit_feedback: INT = None
    ):
        """
        Record user interaction with a recommended product.
        """
        
        await neo4j.query("""
            MATCH (s:RecommendationSession {id: $session_id})
            MATCH (p:Product {id: $product_id})
            
            CREATE (s)-[r:OUTCOME {
                type: $outcome,
                timestamp: datetime(),
                time_spent_seconds: $time_spent,
                explicit_feedback: $feedback
            }]->(p)
            
            // Also update user-product relationship
            WITH s, p
            MATCH (u:User)-[:HAD_SESSION]->(s)
            MERGE (u)-[i:INTERACTED_WITH]->(p)
            ON CREATE SET i.first_interaction = datetime()
            SET i.last_interaction = datetime(),
                i.interaction_count = coalesce(i.interaction_count, 0) + 1,
                i.type = $outcome
        """,
            session_id=session_id,
            product_id=product_id,
            outcome=outcome,
            time_spent=time_spent_seconds,
            feedback=explicit_feedback
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYTICS & LEARNING
    # ═══════════════════════════════════════════════════════════════════════════
    
    FUNCTION analyze_session_outcomes(days: INT = 30) → FeedbackAnalysis:
        """
        Analyze what's working and what's not.
        """
        
        sessions = neo4j.query("""
            MATCH (s:RecommendationSession)
            WHERE s.timestamp > datetime() - duration({days: $days})
            
            // Get outcomes
            OPTIONAL MATCH (s)-[o:OUTCOME]->(p:Product)
            
            RETURN s, collect({
                product_id: p.id,
                outcome: o.type,
                time_spent: o.time_spent_seconds,
                feedback: o.explicit_feedback
            }) as outcomes
        """, days=days)
        
        analysis = {
            # Conversion metrics
            "click_through_rate": calculate_ctr(sessions),
            "conversion_rate": calculate_conversion(sessions),
            
            # What destinations led to conversions
            "successful_destinations": extract_successful_destinations(sessions),
            "failed_destinations": extract_failed_destinations(sessions),
            
            # Which style descriptors correlate with success
            "effective_descriptors": analyze_descriptor_effectiveness(sessions),
            
            # Navigation parameter effectiveness
            "exploration_vs_conversion": analyze_exploration_outcomes(sessions),
            "diversity_vs_satisfaction": analyze_diversity_outcomes(sessions)
        }
        
        RETURN FeedbackAnalysis(analysis)
    
    FUNCTION update_synthesis_prompt_from_feedback(analysis: FeedbackAnalysis):
        """
        Use feedback to improve synthesis prompts.
        This is where learning happens.
        """
        
        # Find patterns in what works
        effective_patterns = analysis.effective_descriptors
        
        # Update synthesis prompt to emphasize what works
        # This could be:
        # 1. Adding examples of successful synthesis outputs
        # 2. Adjusting weights on different factors
        # 3. Adding/removing descriptor types
        
        # Implementation depends on prompt management system
        pass
---

## Section 9: Calibration Flow (TBD Placeholder)

```
# ═══════════════════════════════════════════════════════════════════════════════════
# TBD: POST-ONBOARDING CALIBRATION
# ═══════════════════════════════════════════════════════════════════════════════════
#
# The calibration flow will:
# 1. Run immediately after onboarding completion
# 2. Show 5-10 exemplar products based on initial position
# 3. Collect quick reactions (thumbs up/down or 1-5 rating)
# 4. Update user embeddings based on responses
# 5. Dramatically improve cold start quality
#
# UI FLOW:
# "Before we start recommending, let me quickly calibrate to your taste.
#  I'll show you a few pieces - just tell me if they're you or not."
#
# [Show product image]
# "Is this your style?"
# [Yes, definitely] [Maybe] [Not for me]
#
# After 5-10 responses:
# "Perfect! I've got a much better sense of your taste now."
#
# TECHNICAL IMPLEMENTATION:
# - Generate initial position from onboarding
# - Search for 20 diverse products near that position
# - Select 10 with maximum diversity (MMR)
# - Show one at a time, record responses
# - Update embedding: move toward liked, away from disliked
# - Set calibration_completed = TRUE
#
# IMPLEMENTATION STATUS: TBD
# ═══════════════════════════════════════════════════════════════════════════════════
```

---

## Appendix A: Onboarding → Navigation Parameter Mapping

| Onboarding Field | Navigation Parameter | Formula (using raw 1-10 values) |
|------------------|---------------------|---------|
| `process.adventurousness` (1-10) + `process.creative_control` (1-10) | `exploration_appetite` | `(adventurousness/10) * 0.7 + (1 - creative_control/10) * 0.3` |
| `process.adventurousness` (1-10) | `step_size_multiplier` | `0.5 + (adventurousness/10) * 1.0` |
| `process.creative_control` (1-10) | `user_embedding_weight` | `0.3 + (creative_control/10) * 0.4` |
| `process.brand_loyalty` (1-10) | `brand_affinity_weight` | `brand_loyalty / 10` |
| `process.exploration_preference` | `result_set_size` | long=20, curated=5, quick=10 |
| `process.exploration_preference` | `diversity_requirement` | long=0.7, curated=0.3, quick=0.5 |
| `practicality.budget.monthly` | `default_budget.max` | `monthly * 0.5` |
| `practicality.budget.flexibility` | `default_budget.flexibility` | firm=0.2, guideline=0.4, flexible=0.6 |
| `practicality.category_budgets[cat]` | `category_budget_overrides[cat]` | splurge=2x, budget=0.5x |

---

## Appendix B: LLM Call Summary


| LLM | When | Input | Output | Latency Concern |
|-----|------|-------|--------|-----------------|
| #1 Onboarding Agent | During onboarding | User responses | Conversational continuation | Real-time, but user-paced |
| #2 Interpretation | After onboarding complete | Raw conversations | OnboardingProfile + RootValues | One-time, can be async |
| #2 Re-interpretation | When behavior diverges from profile | Original profile + behavioral data | Updated profile + root values | Async, triggered periodically |
| #3 Synthesis | Every query | Three pillars + query | Style descriptors + search terms | Critical path - needs optimization |
| #4 Narrative | After products selected | Products + profile | Journey story | Can be async/streamed |

**Re-interpretation Triggers (2+ signals required):**
- Spending consistently outside stated budget range
- Actual style variance diverges from stated adventurousness
- Purchasing items they said they avoid
- New life contexts not mentioned in onboarding
- Brand repeat rate diverges from stated loyalty

**Latency Mitigation for #3 Synthesis:**
1. Cache by (user_id, query_hash, context) with 5-minute TTL
2. Precompute for common query patterns ("date night dress", "work blazer")
3. Use smaller/faster model (Claude Haiku or fine-tuned 7B)
4. Return fast initial results, refine async

---

## Appendix C: Data Flow Diagram

```
┌─────────────────┐
│  User Message   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Onboarding     │────►│  Interpretation │
│  Agent (#1)     │     │  LLM (#2)       │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │    ┌──────────────────┘
         │    │
         ▼    ▼
┌─────────────────┐
│    Neo4j        │
│  User Graph     │
└────────┬────────┘
         │
         │ (Query time)
         ▼
┌─────────────────────────────────────────────────────────┐
│                  Navigation Intelligence                 │
│                                                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐           │
│  │ Pillar 1  │  │ Pillar 2  │  │ Pillar 3  │           │
│  │ Personal  │  │ Stylist   │  │ Activity  │           │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘           │
│        │              │              │                  │
│        └──────────────┼──────────────┘                  │
│                       ▼                                 │
│              ┌───────────────┐                          │
│              │ Synthesis     │                          │
│              │ LLM (#3)      │                          │
│              └───────┬───────┘                          │
│                      │                                  │
│                      ▼                                  │
│              ┌───────────────┐                          │
│              │ Exemplar      │                          │
│              │ Retrieval     │                          │
│              └───────┬───────┘                          │
│                      │                                  │
│                      ▼                                  │
│              ┌───────────────┐                          │
│              │ Path          │                          │
│              │ Calculation   │                          │
│              └───────────────┘                          │
│                                                         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  Agent Coordination                      │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ VibeBot  │  │VisionBot │  │[CypherBot]│              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │             │             │                     │
│       └─────────────┼─────────────┘                     │
│                     ▼                                   │
│              ┌───────────────┐                          │
│              │   Ari    │                          │
│              │   + MMR       │                          │
│              └───────┬───────┘                          │
│                      │                                  │
└──────────────────────┼──────────────────────────────────┘
                       │
                       ▼
              ┌───────────────┐
              │ Narrative     │
              │ LLM (#4)      │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │   Response    │
              │   + Tracking  │
              └───────────────┘
```

