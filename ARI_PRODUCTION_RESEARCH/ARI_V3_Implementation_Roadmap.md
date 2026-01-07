# ARI V3 Implementation Roadmap

Version: 1.1
Date: 2026-01-07
Status: Steps 1-2 COMPLETE, Ready for Step 3

---

## Overview

This document outlines the implementation plan for ARI Navigation Intelligence V3. The roadmap is organized into 10 sequential steps with clear dependencies. Steps 1-9 constitute the MVP. Step 10 (Social Media Integration) is a parallel track that can be deferred.

---

## Step 1: V3 Data Structures [COMPLETE]

Foundation that everything else depends on.

1.1 Create ari_v3/core/data_structures.py [DONE]
    - StyleContext enum (8 contexts: professional, casual, evening, formal, active, creative, travel, default)
    - OnboardingProfile (V3 aligned with 6 nodes + root_values + metadata)
    - NavigationParameters (exploration_appetite, step_size_multiplier, etc.)
    - StyleCoordinate, ContextualPosition, ComputedUserState
    - UserEmbeddings, SocialTasteEmbeddings
    - InterpretableDimensions - DEFER to post-MVP

1.2 Create ari_v3/core/navigation_params.py [DONE]
    - derive_navigation_parameters(profile) returns NavigationParameters
    - Pure function, no LLM, deterministic formulas:
        exploration_appetite = (adventurousness/10) * 0.7 + (1 - creative_control/10) * 0.3
        step_size_multiplier = 0.5 + (adventurousness/10) * 1.0
        user_embedding_weight = 0.3 + (creative_control/10) * 0.4
        brand_affinity_weight = brand_loyalty / 10
    - Helper functions: calculate_max_step_size, calculate_velocity_adjustment, etc.

1.3 V3 module structure created [DONE]
    - ari_v3/core/ - data structures and navigation params
    - ari_v3/services/ - user_graph_manager with V3 storage
    - ari_v3/tools/ - neo4j_tools, qdrant_tools (async)
    - All configured for productionbackup2 database (6.4M products)

1.4 Verification [DONE]
    - 32 unit tests for core structures
    - 11 integration tests for Neo4j/Qdrant
    - All tests passing

Dependencies: None
Unlocks: Steps 2, 3, 4

---

## Step 2: LLM #2 Interpretation Upgrade [COMPLETE]

Formalize existing extraction to output V3 structures.

**Design Decision:** LLM #2 is implemented as deterministic conversion from OnboardingCrewV2's
extracted data to V3 structures. The crew already performs LLM extraction with root_value_connection
prompts, so we convert rather than re-extract. This is efficient and aligns with "formalize existing."

2.1 Update crews/onboarding_crew_v2.py [DONE]
    - Added finalize_v3_onboarding(user_id) method - calls V3 service after onboarding completes
    - root_values extraction already in prompts (root_value_connection fields)
    - All 6 nodes mapped: Personal, Taste, Process, Practicality, Body, External

2.2 Create ari_v3/interpretation/interpretation_llm.py [DONE]
    - interpret_onboarding(extracted_data) returns (OnboardingProfile, NavigationParameters)
    - convert_extracted_to_v3_profile() - deterministic conversion from crew output
    - extract_root_values() - async LLM call for deeper psychological inference (optional)
    - Safe type conversion with bounds validation (_safe_int, _safe_float)

2.3 Create ari_v3/services/onboarding_service_v3.py [DONE]
    - OnboardingServiceV3 class with full Neo4j integration
    - process_completed_onboarding() calls derive_navigation_parameters()
    - Stores both OnboardingProfile and NavigationParameters in Neo4j
    - reinterpret_profile() for behavioral drift re-interpretation

2.4 Update Neo4j schema (in ari_v3/services/user_graph_manager.py) [DONE]
    - Added [:HAS_NAV_PARAMS] relationship
    - Added NavigationParameters node type
    - Added to OnboardingProfile node:
        - reinterpreted_at: DATETIME
        - reinterpretation_count: INT
    - RecommendationSession, [:HAD_SESSION], [:OUTCOME] deferred to Step 9

2.5 Verification [DONE]
    - 112 tests in ari_v3/tests/ (unit + integration)
    - test_step2_comprehensive.py: 54 tests covering edge cases
    - Neo4j store/retrieve roundtrip tests
    - All tests passing

Dependencies: Step 1 [COMPLETE]
Unlocks: Steps 3, 4, 5

---

## Step 3: Pillar 1 - Personalization Engine

Compute user state with per-context trajectories.

3.1 Create pillars/personalization.py
    - load_raw_user_data(user_id) returns RawUserData
    - Pull from existing Neo4j V2 ontology
    - Include OnboardingProfile, NavigationParameters, interactions

3.2 Implement compute_user_state()
    - detect_user_contexts() from interactions
    - compute_position_from_interactions() per context
    - compute_context_trajectory() per context (V3 per-context trajectories)
    - select_active_context() based on query/occasion

3.3 Implement compute_cold_start_position()
    - Use onboarding occasion_styles
    - Fall back to general style preferences
    - Population prior for unknown contexts
    - Confidence = 0.4 for onboarding-based, 0.1 for population prior

3.4 Implement compute_unified_embeddings()
    - Blend interaction embeddings with social (when available)
    - Weight by data richness:
        social_weight = (1 - interaction_confidence) * 0.5
        interaction_weight = 1.0 - social_weight

3.5 Verification
    - User state computation for existing test users
    - Verify per-context trajectories computed correctly

Dependencies: Steps 1, 2
Unlocks: Step 5

---

## Step 4: Pillar 2 - Stylist Knowledge RAG

Vectorize existing fashion knowledge.

4.1 Expand nlp/fashion_knowledge.py
    - Add multi-perspective content (traditional, body-neutral, cultural, practical)
    - Structure by topic (color theory, body types, occasions, silhouettes)
    - Include the 6 curation principles

4.2 Create pillars/stylist_knowledge.py
    - FashionKnowledgeBase class
    - Ingest knowledge into Qdrant collection (fashion_knowledge)
    - Chunk and embed all content

4.3 Implement RAG retrieval
    - retrieve_styling_rules(query, body_type, occasion)
    - retrieve_multiple_perspectives(topic) for diversity
    - Hybrid search (semantic + keyword + metadata filtering)

4.4 Verification
    - RAG retrieval returns relevant multi-perspective results
    - Test with various body types, occasions, style queries

Dependencies: Step 1.1 (StyleContext enum only)
Unlocks: Step 5
Note: Can run parallel to Steps 2-3

---

## Step 5: LLM #3 Synthesis

Three pillars to style descriptors to destination.

5.1 Create navigation/synthesis_llm.py
    - synthesize(pillar1, pillar2, pillar3, query) returns SynthesisOutput
    - Outputs: style_descriptors, exemplar_terms, budget_interpretation, formality_level, relevant_context
    - No coordinate output - descriptors only (prevents hallucination)

    Pillar 3 Input: Uses existing code from:
    - user_graph_manager.py:get_user_interactions() - interaction history
    - user_graph_manager.py:calculate_preference_drift() - drift detection
    - user_graph_manager.py:calculate_observed_preferences() - behavioral patterns
    - user_service.py:track_search(), track_product_view() - tracking
    No new implementation needed - wire existing methods into Synthesis input.

5.2 Implement exemplar retrieval
    - Style descriptors to Qdrant search to top products
    - Search each exemplar_search_term, collect top 5 per term
    - Destination = centroid of exemplar embeddings (normalized mean)
    - Grounding in real product space (no coordinate hallucination)

5.3 Implement path calculation (deterministic)
    - max_step_size = 0.3 * nav_params.step_size_multiplier
    - Velocity adjustment: slow movers get 0.7x, fast movers get 1.2x
    - outlier_percentage = nav_params.exploration_appetite * 0.20

5.4 Create navigation/navigation_context.py
    - NavigationContext dataclass
    - Combines: computed_state, synthesis, destination, path, styling_rules

5.5 Agent Input Formatting
    - The orchestrator (Step 8) formats NavigationContext into existing agent input structure:
    
    agent_context = {
        "query": nav_context.query,
        "user_context": nav_context.computed_state.to_dict(),
        "destination_embedding": nav_context.destination.embedding,
        "max_step_size": nav_context.path.max_step_size,
        "styling_rules": nav_context.styling_rules
    }
    
    Agents unchanged - orchestrator adapts the interface.

5.6 Verification
    - Full synthesis flow produces valid NavigationContext
    - Destination embeddings are grounded in real product space

Dependencies: Steps 3, 4
Unlocks: Steps 6, 7

---

## Step 6: Judge Upgrade - MMR + Outliers

Diversity selection and exploration injection.

6.1 Create judge/mmr_selector.py
    - mmr_select(candidates, limit, lambda_param) returns selected list
    - Balances relevance with diversity
    - Uses nav_params.diversity_requirement as lambda_param
    - Algorithm:
        1. Start with highest relevance product
        2. Iteratively add product with best MMR score
        3. MMR = lambda * relevance - (1 - lambda) * max_similarity_to_selected

6.2 Create judge/outlier_injector.py
    - inject_outliers(selected, remaining, outlier_percentage)
    - Products with distance > 0.4 from current position qualify as outliers
    - Random sample from qualified outliers
    - Uses nav_params.exploration_appetite to determine percentage

6.3 Update judge evaluation (agents/judge_ari.yaml or create judge/ari_evaluator.py)
    - Score products on 7 dimensions:
        1. Smoothness (step distance) - 0.15 weight
        2. Coherence (trajectory alignment) - 0.10 weight
        3. Budget fit - 0.15 weight
        4. Brand match - 0.10 weight
        5. Behavioral consistency - 0.20 weight
        6. Multi-agent confidence - 0.10 weight
        7. Rule compliance - 0.20 weight
    - Call MMR selection on scored products
    - Call outlier injection
    - Return final ranked list

6.4 Verification
    - Judge produces diverse results
    - Exploration products included at correct percentage
    - MMR prevents clustering of similar items

Dependencies: Step 5
Unlocks: Step 7

---

## Step 7: LLM #4 Narrative

Journey story generation.

7.1 Create narrative/narrative_llm.py
    - generate_narrative(nav_context, products, user_profile) returns JourneyNarrative
    - Uses validation_sources to frame for audience:
        - self: "how these pieces express who you are"
        - partner: "pieces your partner would love seeing you in"
        - colleagues: "how you'll be perceived professionally"
    - Connects to root_values and style_motivations
    - Explains why each product fits the journey

7.2 Define JourneyNarrative structure
    - opening: Position acknowledgment (2-3 sentences)
    - journey_description: Path explanation
    - product_explanations: Per-product reasoning (1 sentence each)
    - closing: Encouragement

7.3 Integrate into response flow
    - After Judge selects products, generate narrative
    - Narrative can be async/streamed while products render
    - Return products + narrative to user

7.4 Verification
    - Narrative feels personal
    - Connects to user's stated values
    - References their actual words from onboarding where appropriate

Dependencies: Step 5 (structures only - can start parallel with Step 6)
Unlocks: Step 8

---

## Step 8: Main Orchestration

Wire everything together.

8.1 Create navigation/orchestrator.py
    - NavigationOrchestrator class
    - execute_search(user_id, query, occasion) returns SearchResult

8.2 Implement flow
    1. Load raw user data (Pillar 1)
    2. Compute user state with active context
    3. Retrieve styling rules (Pillar 2)
    4. Get interaction patterns (Pillar 3 - existing code)
    5. Call Synthesis LLM (#3)
    6. Exemplar retrieval to compute destination
    7. Calculate path (deterministic)
    8. Dispatch agents (Vibe, Vision, conditional Graph)
    9. Judge evaluation with MMR + outliers
    10. Generate narrative (LLM #4)
    11. Track session (Step 9)
    12. Return products + narrative + session_id

8.3 Update existing entry points
    - cli/chat_interface_v2.py to use new orchestrator
    - Replace old crewai_orchestrator calls
    - Maintain backward compatibility during transition

8.4 Verification
    - Full end-to-end flow works
    - Response times acceptable (target: < 3 seconds excluding LLM streaming)
    - Error handling for each step

Dependencies: Steps 1-7
Unlocks: Steps 9, 10

---

## Step 9: Feedback Loop

Learn from outcomes.

9.1 Create feedback/session_tracker.py
    - track_recommendation_session() returns session_id
    - Store in Neo4j: RecommendationSession nodes
    - Link to user via [:HAD_SESSION]
    - Link to products via [:SHOWED]
    - Store: query, occasion, active_context, style_descriptors, destination_embedding, nav_params, product_ids, product_scores

9.2 Create feedback/outcome_recorder.py
    - record_outcome(session_id, product_id, outcome)
    - Outcome types: viewed, clicked, liked, purchased, rejected
    - Store time_spent_seconds, explicit_feedback (1-5)
    - Update user-product [:INTERACTED_WITH] relationships

9.3 Create feedback/reinterpretation.py
    - check_reinterpretation_trigger(user_id)
    - Requires 30+ interactions before checking
    - Detect divergence signals (2+ triggers re-interpretation):
        1. spending_above_stated: median spend > 1.5x stated budget
        2. spending_below_stated: median spend < 0.3x stated budget
        3. adventurousness_mismatch: actual variance differs by > 0.4
        4. buying_stated_avoids: purchased 3+ items from avoid list
        5. new_life_contexts: 2+ new contexts not in onboarding
        6. brand_loyalty_mismatch: repeat rate differs by > 0.4
    - run_reinterpretation(): re-run LLM #2 with original profile + behavioral summary
    - Update OnboardingProfile and NavigationParameters in Neo4j

9.4 Create feedback/analytics.py
    - analyze_session_outcomes(days)
    - Calculate: click_through_rate, conversion_rate
    - Extract: successful_destinations, failed_destinations
    - Identify: effective_descriptors
    - Analyze: exploration_vs_conversion, diversity_vs_satisfaction

9.5 Integrate into main flow
    - Track session after each recommendation (end of Step 8 flow)
    - Check reinterpretation trigger every 20 interactions
    - on_interaction() hook for all user interactions

9.6 Verification
    - Sessions tracked correctly in Neo4j
    - Outcomes recorded and linked
    - Reinterpretation triggers fire correctly
    - Analytics queries return meaningful data

Dependencies: Step 8
Unlocks: Continuous improvement

---

## Step 10: Social Media Integration (Optional/Parallel)

Rich taste signals from connected accounts. Can be deferred post-MVP.

10.1 Create social/pinterest_processor.py
    - process_pinterest(handle) returns PinterestEmbeddings
    - Pinterest API integration
    - Board analysis: name, embedding, pin_count, dominant_themes
    - Overall embedding: weighted blend by pin_count
    - Filter fashion-related pins

10.2 Create social/instagram_processor.py
    - process_instagram(handle) returns InstagramEmbeddings
    - Instagram API integration (requires business account)
    - Saved posts embedding (0.6 weight - strong signal)
    - Following style embedding (0.4 weight - weaker signal)

10.3 Create social/tiktok_processor.py
    - process_tiktok(handle) returns TikTokEmbeddings
    - TikTok API integration
    - Liked/saved videos analysis

10.4 Create social/social_processor.py
    - compute_unified_social_embedding()
    - Blend all platforms weighted by data richness
    - Pinterest: saturates at 100 pins = 1.0 weight
    - Instagram: 0.8 max weight
    - TikTok: 0.6 max weight

10.5 Integrate into onboarding
    - After handle collection, process accounts async
    - Store SocialTasteEmbeddings in Neo4j
    - Link via [:HAS_SOCIAL_TASTE]

10.6 Integrate into Pillar 1
    - Include social embeddings in compute_user_state()
    - Use for cold start position computation
    - Blend with interaction embeddings based on confidence

10.7 Verification
    - Social signals extracted correctly
    - Unified embedding improves cold start recommendations
    - API rate limits handled gracefully

Dependencies: Steps 1, 2 (can run parallel to Steps 3-9)
Unlocks: Better cold start, richer user understanding

---

## Step 11: Calibration Flow (TBD Placeholder)

Post-onboarding taste calibration. Specification pending.

11.1 Concept
    - Run immediately after onboarding completion
    - Show 5-10 exemplar products based on initial position
    - Collect quick reactions: thumbs up, maybe, not for me
    - Update user embeddings based on responses
    - Dramatically improve cold start quality

11.2 UI Flow
    - "Before we start recommending, let me quickly calibrate to your taste."
    - "I'll show you a few pieces - just tell me if they're you or not."
    - Show product image, collect response
    - After 5-10 responses: "Perfect! I've got a much better sense of your taste now."

11.3 Technical Implementation (when ready)
    - Generate initial position from onboarding
    - Search for 20 diverse products near that position
    - Select 10 with maximum diversity (MMR)
    - Show one at a time, record responses
    - Update embedding: move toward liked, away from disliked
    - Set calibration_completed = TRUE

Status: TBD - placeholder for post-MVP

Dependencies: Steps 1, 2, 3
Unlocks: Improved cold start accuracy

---

## Dependency Graph

```
Step 1 (Data Structures)
    |
    +---> Step 2 (LLM #2 Interpretation)
    |         |
    |         +---> Step 3 (Pillar 1 Personalization)
    |         |         |
    |         |         +---> Step 5 (LLM #3 Synthesis)
    |         |                   |
    |         |                   +---> Step 6 (Judge MMR) ----+
    |         |                   |                            |
    |         |                   +---> Step 7 (Narrative) ----+---> Step 8 (Orchestration)
    |         |                        [parallel with 6]       |           |
    |         |                                                |           +---> Step 9 (Feedback)
    |         |                                                |
    |         +---> Step 10 (Social Media) [parallel, optional]
    |         |
    |         +---> Step 11 (Calibration) [TBD, post-MVP]
    |
    +---> Step 4 (Pillar 2 RAG) ----+
                                    |
                          [joins at Step 5]
```

Parallel Tracks on Day 1:
    - Step 1.1 (StyleContext enum first, then rest of structures)
    - Step 4 (RAG vectorization - needs only StyleContext)

---

## Critical Path

MVP Critical Path: Step 1 --> Step 2 --> Step 3 --> Step 5 --> Step 6 --> Step 8

Steps 4, 7, 9 can run parallel to critical path at appropriate points.

---



## Time Estimates

| Step | Description                  | Effort    | Notes                                    |
|------|------------------------------|-----------|------------------------------------------|
| 1    | Data Structures              | 1-2 days  | Mostly typing, unit tests                |
| 2    | LLM #2 Interpretation        | 2-3 days  | Prompt tuning, structured output         |
| 3    | Pillar 1 Personalization     | 3-4 days  | Per-context trajectory is new logic      |
| 4    | Pillar 2 RAG                 | 2-3 days  | Parallel track, chunking + ingest        |
| 5    | LLM #3 Synthesis             | 3-4 days  | Critical path, prompt iteration          |
| 6    | Judge MMR                    | 1-2 days  | Algorithm defined, straightforward       |
| 7    | LLM #4 Narrative             | 1-2 days  | Prompt work, parallel with Step 6        |
| 8    | Orchestration                | 2-3 days  | Wiring, edge cases, error handling       |
| 9    | Feedback Loop                | 2-3 days  | Neo4j queries, reinterpretation logic    |
| 10   | Social Media                 | TBD 5+days| API integrations, auth flows, DEFER      |
| 11   | Calibration Flow             | TBD       | Post-MVP, specification pending          |

