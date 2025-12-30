# ARI Navigation Intelligence - Pseudocode Specification V2

**Version:** 2.0
2025-12-29
---

## Overview

This document contains the pseudocode specification for ARI's Navigation Intelligence system.

**North Star:** Find the best product for each individual.

**How:** By representing style as a multi-dimensional space, alongside tangential spaces (demographics, psychometrics, psychology, life context), and using the LLM to traverse all of these simultaneously.

The LLM receives historical data, personalization metrics, and behavioral patterns across all these spaces. It synthesizes them to determine the path.

**Three Pillars provide the knowledge:**
1. **Pillar 1: Personalization** - Raw user data from Neo4j User Graph (body, interactions, conversations)
2. **Pillar 2: Stylist Knowledge** - RAG over fashion literature (color theory, body types, occasions)
3. **Pillar 3: User Activity** - Behavioral patterns computed from interaction history

**Key Principles (V2 Changes):**
- Store raw data, not fixed inferences
- Compute position and trajectory from behavior (deterministic)
- Single LLM call to synthesize pillars and determine destination
- All other calculations are deterministic (fast, consistent, reproducible)
- Graph agent off by default, enable for specific attribute queries
- Add outlier injection for exploration

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     ARI NAVIGATION INTELLIGENCE V2                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   PILLAR 1      │  │   PILLAR 2      │  │   PILLAR 3      │              │
│  │ PERSONALIZATION │  │ STYLIST         │  │ USER ACTIVITY   │              │
│  │                 │  │ KNOWLEDGE       │  │ PATTERNS        │              │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤              │
│  │ Raw User Data   │  │ Textbook        │  │ Behavioral      │              │
│  │ • BodyData      │  │ Literature      │  │ Tracking        │              │
│  │ • Interactions  │  │ • Color theory  │  │ • Interactions  │              │
│  │ • Conversations │  │ • Body types    │  │ • Purchases     │              │
│  │ • Onboarding    │  │ • Occasion      │  │ • Views/Likes   │              │
│  │   (raw)         │  │   rules         │  │ • Drift         │              │
│  │                 │  │ • Silhouettes   │  │   detection     │              │
│  └────────┬────────┘  │ • Harmony       │  └────────┬────────┘              │
│           │           └────────┬────────┘           │                        │
│           │                    │                    │                        │
│           └────────────────────┼────────────────────┘                        │
│                                ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    DETERMINISTIC COMPUTATION                         │   │
│  │                                                                      │   │
│  │   • Position: weighted_avg(recent_interactions)                      │   │
│  │   • Trajectory: compute_from_history(direction, velocity)            │   │
│  │   • Spending patterns: analyze_by_context(purchases)                 │   │
│  │   • Style consistency: detect_stable_patterns(behavior)              │   │
│  │                                                                      │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    LLM SYNTHESIS (Single Call)                       │   │
│  │                                                                      │   │
│  │   Input: All 3 pillars + query + occasion                           │   │
│  │   Output: Destination coordinates + path parameters                  │   │
│  │                                                                      │   │
│  │   The LLM traverses stylistic + tangential spaces simultaneously    │   │
│  │                                                                      │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              PATH CALCULATION (Deterministic)                        │   │
│  │                                                                      │   │
│  │   • Step size from velocity                                          │   │
│  │   • Waypoint interpolation                                           │   │
│  │   • Outlier injection (10-20%)                                       │   │
│  │                                                                      │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              AGENT COORDINATION                                      │   │
│  │                                                                      │   │
│  │   VibeBot        VisionBot      [GraphBot]     JudgeAri             │   │
│  │   (Semantic)     (Visual)       (off by        (Path Quality)       │   │
│  │   PRIMARY        PRIMARY        default)       EVALUATION           │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Modal Intelligence Sources

| Type | Source | Dimensions | Nature |
|------|--------|------------|--------|
| Vision Embedding | SigLIP | 1024d | Learned |
| Text Embedding | SigLIP | 1024d | Learned |
| Semantic Embedding | OpenAI ada-002 | 1536d | Learned |
| Deep Features | ResNet-50 | 2048d | Learned |
| Multimodal | SigLIP fusion | 2048d | Learned |
| **Color Science** | CIE LCh extraction | 15 values | **Deterministic** |
| **Color Harmony** | Lara-Alvarez | 3 scores | **Deterministic** |
| **Texture** | Classification | ~256d | **Deterministic** |
| **Shape** | Hu/Zernike moments | ~128d | **Deterministic** |
| **Parts** | Keypoint geometry | ~512d | **Deterministic** |
| **Silhouette** | Contour analysis | Type + metrics | **Deterministic** |
| **SAM3 Mask** | Segmentation | Binary mask | **Deterministic** |

---

## Pseudocode

### Section 1: Data Structures

```
STRUCTURE StyleCoordinate:
    # Pure Stylistic Dimensions (0.0 to 1.0)
    form: FLOAT           # structured ←→ fluid
    color_warmth: FLOAT   # cool ←→ warm
    color_saturation: FLOAT  # muted ←→ vibrant
    texture: FLOAT        # smooth ←→ rough
    pattern: FLOAT        # minimal ←→ maximalist
    formality: FLOAT      # casual ←→ formal
    proportion: FLOAT     # fitted ←→ oversized

    # Cultural Dimensions
    aesthetic_era: FLOAT  # vintage ←→ contemporary ←→ avant-garde
    design_philosophy: STRING  # "scandinavian", "japanese", "italian"

    # Computed from embeddings
    embedding_coordinates: VECTOR[7680]


STRUCTURE DeterministicFeatures:
    # SAM3 Segmentation
    segmentation_mask: BINARY_MATRIX
    segmentation_confidence: FLOAT
    garment_bbox: [x1, y1, x2, y2]

    # Color Science (CIE LCh)
    dominant_colors: LIST[(L, C, h, percentage), ...]  # Up to 5 colors
    primary_hue: FLOAT[0-360]
    avg_chroma: FLOAT[0-100]
    avg_lightness: FLOAT[0-100]

    # Color Harmony (Lara-Alvarez)
    harmony_type: ENUM["analog", "opposite", "triad", "none"]
    hue_harmony_score: FLOAT[0-1]
    tone_harmony_score: FLOAT[0-1]
    overall_harmony: FLOAT[0-1]

    # Texture Classification
    texture_type: ENUM["smooth", "knitted", "woven", "lace", "quilted", "shiny"]
    fabric_roughness: FLOAT[0-1]
    glossiness: FLOAT[0-1]

    # Shape/Silhouette
    silhouette_type: ENUM["a-line", "bodycon", "shift", "empire", "wrap", "mermaid"]
    aspect_ratio: FLOAT
    compactness: FLOAT
    convexity: FLOAT
    hu_moments: VECTOR[7]
    zernike_moments: VECTOR[36]

    # Part-Based Geometry
    neckline: {type: STRING, depth: FLOAT}
    sleeves: {type: STRING, length_ratio: FLOAT}
    waistline_position: FLOAT
    hemline_shape: STRING
    hem_curvature: FLOAT


STRUCTURE EmbeddingFeatures:
    openai_text: VECTOR[1536]
    siglip_text: VECTOR[1024]
    siglip_vision: VECTOR[1024]
    resnet_features: VECTOR[2048]
    siglip_multimodal: VECTOR[2048]


STRUCTURE UserEmbeddings:
    """
    Composite embedding representing user's style identity.
    Lives in same vector space as products for direct similarity search.
    Pre-computed and updated as new signals arrive.
    """

    # Core embeddings (same dimensionality as product embeddings)
    semantic: VECTOR[1536]      # Same space as product OpenAI embeddings
    visual: VECTOR[1024]        # Same space as product SigLIP vision
    multimodal: VECTOR[2048]    # Same space as product multimodal fusion

    # Source contribution weights (sum to 1.0)
    source_weights: {
        onboarding: FLOAT,       # Initial signal, decays as behavior grows
        interactions: FLOAT,     # Primary signal from likes/purchases/views

        # ═══════════════════════════════════════════════════════════════════
        # TBD: Future embedding sources
        # ═══════════════════════════════════════════════════════════════════
        body_scan: FLOAT,        # 3D body geometry → style fit preferences
        social_style: FLOAT,     # Instagram/photos → actual wardrobe analysis
    }

    # Metadata
    last_updated: DATETIME
    interaction_count: INT       # How many interactions contributed
    confidence: FLOAT            # Higher with more data


STRUCTURE ProductRepresentation:
    product_id: STRING
    title: STRING
    price: FLOAT
    images: LIST[URL]
    deterministic: DeterministicFeatures
    embeddings: EmbeddingFeatures
    style_coordinates: StyleCoordinate


STRUCTURE RawUserData:
    """
    V2: Store raw data, not fixed inferences.
    The LLM interprets this data in context.
    """
    user_id: STRING

    # Stable facts (don't change per query)
    body_type: STRING
    coloring: STRING
    body_photo_url: STRING
    face_photo_url: STRING

    # Raw onboarding data (stored without extraction)
    onboarding_responses: JSON  # Full conversation, no inference

    # Raw interaction history (with full context)
    interactions: LIST[{
        product_id: STRING,
        type: ENUM["viewed", "liked", "purchased", "rejected", "saved"],
        timestamp: DATETIME,
        context: {
            occasion: STRING,
            query: STRING,
            session_id: STRING
        }
    }]

    # Raw conversations (stored without extraction)
    conversation_history: LIST[{
        timestamp: DATETIME,
        messages: LIST[{role: STRING, content: STRING}],
        session_context: JSON
    }]

    # Demographics (stable)
    demographics: {
        age: INT,
        location: STRING,
        profession: STRING
    }


STRUCTURE ComputedUserState:
    """
    V2: Computed at query time from RawUserData.
    These are not stored, they are calculated.
    """
    # Current position in style space (computed from interactions)
    current_position: StyleCoordinate

    # User embeddings (pre-computed, same space as products)
    embeddings: UserEmbeddings

    # Trajectory (computed from interaction history)
    trajectory: {
        direction: VECTOR[N],
        velocity: FLOAT,
        consistency: FLOAT
    }

    # Spending patterns by context (computed from purchases)
    spending_patterns: {
        by_category: MAP[category → {min, max, avg}],
        by_occasion: MAP[occasion → {min, max, avg}],
        overall: {min, max, avg}
    }

    # Style consistency patterns (computed from behavior)
    behavioral_patterns: {
        consistent_dimensions: LIST[STRING],  # Dimensions that rarely change
        variable_dimensions: LIST[STRING],    # Dimensions that vary by context
        preferred_categories: LIST[STRING],
        avoided_categories: LIST[STRING]
    }


STRUCTURE NavigationPath:
    current_position: StyleCoordinate
    destination: StyleCoordinate
    waypoints: LIST[{
        coordinates: StyleCoordinate,
        step_distance: FLOAT
    }]

    # Outlier slots for exploration
    outlier_slots: INT  # Number of results reserved for exploration

    # Quality metrics
    smoothness_score: FLOAT
    coherence_score: FLOAT


STRUCTURE NavigationContext:
    """
    The complete context passed to agents.
    Assembled from all three pillars + LLM synthesis.
    """
    # User state (computed)
    current_position: StyleCoordinate
    trajectory: {direction, velocity, consistency}
    destination: StyleCoordinate  # From LLM synthesis
    path: NavigationPath

    # Raw data references
    raw_user_data: RawUserData
    computed_state: ComputedUserState

    # Pillar 2: Stylist Knowledge (RAG results)
    styling_rules: LIST[StylingRule]
    body_guidance: BodyGuidance
    occasion_guidance: OccasionGuidance
    color_guidance: HarmonyGuidance

    # Pillar 3: Behavioral patterns
    behavioral_profile: BehavioralProfile
    drift_analysis: DriftAnalysis

    # Query context
    query: STRING
    occasion: STRING

    # LLM synthesis output
    llm_interpretation: {
        understood_intent: STRING,
        relevant_context: LIST[STRING],
        budget_for_this_query: {min, max},
        formality_for_this_occasion: FLOAT,
        exploration_appetite: FLOAT  # 0-1, affects outlier percentage
    }
```

---

### Section 2: Three Pillars - Knowledge Sources

```
CLASS Pillar1_Personalization:
    """
    V2: Load RAW user data. Do not infer fixed preferences.
    Position and trajectory are computed, not stored.
    """

    FUNCTION load_raw_user_data(user_id) → RawUserData:
        """
        Load all raw data without inference.
        """
        # Load stable facts from Neo4j User Graph
        user_node = neo4j.query("""
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:HAS_BODY_DATA]->(bd)
            OPTIONAL MATCH (u)-[:HAS_PERSONAL_IDENTITY]->(pi)
            RETURN u, bd, pi
        """, user_id=user_id)

        # Load raw onboarding data (no extraction)
        onboarding = neo4j.query("""
            MATCH (u:User {id: $user_id})-[:HAS_DATA_NODE]->(d:OnboardingDataNode)
            RETURN d.data as raw_data, d.node_id, d.completed_at
            ORDER BY d.completed_at
        """, user_id=user_id)

        # Load all interactions with full context
        interactions = neo4j.query("""
            MATCH (u:User {id: $user_id})-[r:INTERACTED_WITH]->(i:Interaction)
            MATCH (i)-[:WITH_PRODUCT]->(p:Product)
            RETURN
                p.id as product_id,
                r.type as interaction_type,
                r.timestamp as timestamp,
                i.occasion as occasion,
                i.query as query,
                i.session_id as session_id
            ORDER BY r.timestamp DESC
            LIMIT 1000
        """, user_id=user_id)

        # Load raw conversations
        conversations = neo4j.query("""
            MATCH (u:User {id: $user_id})-[:HAD_CONVERSATION]->(c:Conversation)
            RETURN c.messages, c.timestamp, c.session_context
            ORDER BY c.timestamp DESC
            LIMIT 50
        """, user_id=user_id)

        RETURN RawUserData(
            user_id=user_id,
            body_type=user_node.bd.body_verbal,
            coloring=user_node.bd.coloring_verbal,
            body_photo_url=user_node.bd.body_photo_url,
            face_photo_url=user_node.bd.face_photo_url,
            onboarding_responses=onboarding,
            interactions=interactions,
            conversation_history=conversations,
            demographics={
                age=user_node.pi.age,
                location=user_node.pi.location_city,
                profession=user_node.pi.occupation
            }
        )

    FUNCTION compute_user_state(raw_data: RawUserData, query_context: QueryContext) → ComputedUserState:
        """
        V2: Compute position, trajectory, and patterns from raw data.
        This is done at query time, not stored.
        """
        # Filter interactions by relevance to current context (optional)
        relevant_interactions = raw_data.interactions
        IF query_context.occasion:
            # Weight interactions from similar occasions more heavily
            relevant_interactions = weight_by_occasion_similarity(
                raw_data.interactions,
                query_context.occasion
            )

        # Compute current position
        current_position = compute_position_from_interactions(relevant_interactions)

        # Compute trajectory
        trajectory = compute_trajectory_from_history(raw_data.interactions)

        # Compute spending patterns
        spending_patterns = analyze_spending_patterns(raw_data.interactions)

        # Detect consistent behavioral patterns
        behavioral_patterns = detect_behavioral_patterns(raw_data.interactions)

        # Compute user embeddings (same space as products)
        user_embeddings = compute_user_embeddings(raw_data, raw_data.interactions)

        RETURN ComputedUserState(
            current_position=current_position,
            embeddings=user_embeddings,
            trajectory=trajectory,
            spending_patterns=spending_patterns,
            behavioral_patterns=behavioral_patterns
        )

    FUNCTION compute_position_from_interactions(interactions) → StyleCoordinate:
        """
        Weighted average of product style coordinates.
        More recent and higher-engagement interactions weighted higher.
        """
        weighted_products = []
        FOR interaction IN interactions:
            # Load product style coordinates
            product = get_product(interaction.product_id)

            # Recency weight (exponential decay)
            days_ago = (now() - interaction.timestamp).days
            recency_weight = exp(-0.02 * days_ago)

            # Engagement weight
            IF interaction.type == "purchased": engagement = 3.0
            ELIF interaction.type == "liked": engagement = 2.0
            ELIF interaction.type == "saved": engagement = 1.5
            ELIF interaction.type == "viewed": engagement = 1.0
            ELIF interaction.type == "rejected": engagement = -0.5

            weight = recency_weight * engagement
            IF weight > 0:
                weighted_products.append((product.style_coordinates, weight))

        # Aggregate
        IF len(weighted_products) == 0:
            RETURN StyleCoordinate.default()

        position = StyleCoordinate.zero()
        total_weight = 0
        FOR (coords, weight) IN weighted_products:
            position += coords * weight
            total_weight += weight

        RETURN position / total_weight

    FUNCTION compute_trajectory_from_history(interactions) → Trajectory:
        """
        Compute direction and velocity of style evolution.
        """
        IF len(interactions) < 10:
            # Not enough data
            RETURN Trajectory(
                direction=ZERO_VECTOR,
                velocity=0.05,  # Default moderate
                consistency=0.5
            )

        # Split into time windows
        recent = [i for i in interactions if i.timestamp > now() - days(30)]
        historical = [i for i in interactions if i.timestamp < now() - days(30)]

        IF len(recent) < 5 OR len(historical) < 5:
            RETURN Trajectory(direction=ZERO_VECTOR, velocity=0.05, consistency=0.5)

        recent_position = compute_position_from_interactions(recent)
        historical_position = compute_position_from_interactions(historical)

        # Direction: normalized difference
        direction = recent_position - historical_position
        magnitude = norm(direction)

        IF magnitude > 0:
            direction = direction / magnitude

        # Velocity: magnitude of change per week
        weeks = 4  # Comparing ~1 month
        velocity = magnitude / weeks

        # Consistency: how stable is the direction over time
        consistency = compute_trajectory_consistency(interactions)

        RETURN Trajectory(
            direction=direction,
            velocity=velocity,
            consistency=consistency
        )

    FUNCTION analyze_spending_patterns(interactions) → SpendingPatterns:
        """
        Analyze spending by category and occasion from purchase history.
        """
        purchases = [i for i in interactions if i.type == "purchased"]

        by_category = {}
        by_occasion = {}
        all_prices = []

        FOR purchase IN purchases:
            product = get_product(purchase.product_id)
            price = product.price
            category = product.category
            occasion = purchase.context.occasion

            all_prices.append(price)

            IF category NOT IN by_category:
                by_category[category] = []
            by_category[category].append(price)

            IF occasion AND occasion NOT IN by_occasion:
                by_occasion[occasion] = []
            IF occasion:
                by_occasion[occasion].append(price)

        RETURN SpendingPatterns(
            by_category={cat: stats(prices) for cat, prices in by_category},
            by_occasion={occ: stats(prices) for occ, prices in by_occasion},
            overall=stats(all_prices) if all_prices else {min: 0, max: 500, avg: 100}
        )

    FUNCTION detect_behavioral_patterns(interactions) → BehavioralPatterns:
        """
        Identify dimensions that are consistent vs variable.
        """
        # Group interactions by dimension values
        dimension_values = {dim: [] for dim in STYLE_DIMENSIONS}

        FOR interaction IN interactions:
            IF interaction.type IN ["purchased", "liked"]:
                product = get_product(interaction.product_id)
                FOR dim IN STYLE_DIMENSIONS:
                    dimension_values[dim].append(product.style_coordinates[dim])

        # Calculate variance for each dimension
        consistent = []
        variable = []

        FOR dim, values IN dimension_values.items():
            IF len(values) >= 5:
                variance = np.var(values)
                IF variance < 0.1:  # Low variance = consistent preference
                    consistent.append(dim)
                ELIF variance > 0.3:  # High variance = context-dependent
                    variable.append(dim)

        # Category preferences
        category_counts = count_by_category(interactions)
        preferred = [cat for cat, count in category_counts.items() if count >= 5]

        # Avoided categories (from rejections)
        rejected = [i for i in interactions if i.type == "rejected"]
        avoided_counts = count_by_category(rejected)
        avoided = [cat for cat, count in avoided_counts.items() if count >= 3]

        RETURN BehavioralPatterns(
            consistent_dimensions=consistent,
            variable_dimensions=variable,
            preferred_categories=preferred,
            avoided_categories=avoided
        )

    FUNCTION compute_user_embeddings(raw_data: RawUserData, interactions) → UserEmbeddings:
        """
        Compute user embeddings from onboarding + interaction history.
        User embeddings live in same vector space as products.
        """

        # ═══════════════════════════════════════════════════════════════════
        # ONBOARDING CONTRIBUTION
        # ═══════════════════════════════════════════════════════════════════

        onboarding_embedding = None
        IF raw_data.onboarding_responses:
            # Extract text from onboarding for semantic embedding
            onboarding_text = extract_style_text(raw_data.onboarding_responses)
            onboarding_semantic = openai.embed(onboarding_text)

            # If onboarding included reference images, compute visual embedding
            IF raw_data.onboarding_responses.reference_images:
                onboarding_visual = avg([
                    siglip.encode_image(img)
                    for img in raw_data.onboarding_responses.reference_images
                ])
            ELSE:
                onboarding_visual = ZERO_VECTOR[1024]

            onboarding_multimodal = concatenate(onboarding_semantic[:1024], onboarding_visual)

        # ═══════════════════════════════════════════════════════════════════
        # INTERACTION CONTRIBUTION
        # ═══════════════════════════════════════════════════════════════════

        weighted_semantic = []
        weighted_visual = []
        weighted_multimodal = []

        FOR interaction IN interactions:
            product = get_product(interaction.product_id)

            # Recency weight (exponential decay)
            days_ago = (now() - interaction.timestamp).days
            recency_weight = exp(-0.02 * days_ago)

            # Engagement weight
            IF interaction.type == "purchased": engagement = 3.0
            ELIF interaction.type == "liked": engagement = 2.0
            ELIF interaction.type == "saved": engagement = 1.5
            ELIF interaction.type == "viewed": engagement = 1.0
            ELIF interaction.type == "rejected": engagement = -0.5

            weight = recency_weight * engagement
            IF weight > 0:
                weighted_semantic.append((product.embeddings.openai_text, weight))
                weighted_visual.append((product.embeddings.siglip_vision, weight))
                weighted_multimodal.append((product.embeddings.siglip_multimodal, weight))

        # Aggregate interaction embeddings
        interaction_semantic = weighted_average(weighted_semantic)
        interaction_visual = weighted_average(weighted_visual)
        interaction_multimodal = weighted_average(weighted_multimodal)

        # ═══════════════════════════════════════════════════════════════════
        # BLEND SOURCES
        # ═══════════════════════════════════════════════════════════════════

        # Source weights decay onboarding as interactions grow
        interaction_count = len([i for i in interactions if i.type in ["purchased", "liked"]])

        IF interaction_count == 0:
            onboarding_weight = 1.0
            interaction_weight = 0.0
        ELIF interaction_count < 10:
            onboarding_weight = 0.5
            interaction_weight = 0.5
        ELIF interaction_count < 50:
            onboarding_weight = 0.2
            interaction_weight = 0.8
        ELSE:
            onboarding_weight = 0.1
            interaction_weight = 0.9

        # Blend embeddings
        semantic = onboarding_semantic * onboarding_weight + interaction_semantic * interaction_weight
        visual = onboarding_visual * onboarding_weight + interaction_visual * interaction_weight
        multimodal = onboarding_multimodal * onboarding_weight + interaction_multimodal * interaction_weight

        RETURN UserEmbeddings(
            semantic=normalize(semantic),
            visual=normalize(visual),
            multimodal=normalize(multimodal),
            source_weights={
                onboarding: onboarding_weight,
                interactions: interaction_weight,
                body_scan: 0.0,      # TBD: Future
                social_style: 0.0,   # TBD: Future
            },
            last_updated=now(),
            interaction_count=interaction_count,
            confidence=min(1.0, interaction_count / 50)  # Saturates at 50 interactions
        )


# ═══════════════════════════════════════════════════════════════════════════
# PILLAR 2: STYLIST KNOWLEDGE - RAG Architecture
# Making ARI an expert in textbook fashion and beyond
# ═══════════════════════════════════════════════════════════════════════════

ENUM KnowledgeCategory:
    # Core Fashion Science
    COLOR_THEORY           # Color wheel, harmony types, seasonal palettes
    COLOR_PSYCHOLOGY       # Emotional/cultural associations with colors
    BODY_TYPES            # Body shape analysis, flattering silhouettes
    SILHOUETTE_SCIENCE    # A-line, bodycon, empire, etc. - when/why
    PROPORTION_THEORY     # Visual balance, elongation, ratio principles

    # Garment Knowledge
    FABRIC_SCIENCE        # Materials, drape, texture, care, seasonality
    CONSTRUCTION          # Tailoring, fit indicators, quality markers
    NECKLINES             # Types, face shape compatibility, occasion
    SLEEVE_STYLES         # Types, arm considerations, formality
    HEMLINES              # Lengths, leg proportion, occasion rules

    # Context & Occasion
    DRESS_CODES           # Business formal, cocktail, black tie, etc.
    OCCASION_RULES        # Wedding guest, interview, date night, etc.
    CULTURAL_CONTEXT      # Regional/cultural dress expectations
    SEASONAL_DRESSING     # Weather-appropriate styling

    # Style & Aesthetics
    STYLE_ARCHETYPES      # Classic, romantic, dramatic, natural, etc.
    FASHION_HISTORY       # Era influences, revival cycles
    TREND_ANALYSIS        # Current trends, longevity prediction
    CAPSULE_WARDROBE      # Versatility, mix-and-match principles

    # Advanced Topics
    PERSONAL_BRANDING     # Style as identity expression
    OPTICAL_ILLUSIONS     # Visual tricks for body enhancement
    ACCESSORIZING         # Jewelry, bags, shoes coordination
    PATTERN_MIXING        # Rules for combining prints


STRUCTURE FashionKnowledgeChunk:
    """
    A single retrievable unit of fashion knowledge.
    """
    chunk_id: STRING

    # Classification
    category: KnowledgeCategory
    subcategory: STRING              # e.g., "complementary_colors" under COLOR_THEORY
    tags: LIST[STRING]               # Searchable tags

    # Source attribution
    source: {
        title: STRING,               # "Color Me Beautiful", "The Curated Closet", etc.
        author: STRING,
        type: ENUM["textbook", "research_paper", "expert_article", "style_guide"],
        credibility_score: FLOAT     # 0-1, peer-reviewed higher
    }

    # Content
    content: STRING                  # The actual knowledge text
    summary: STRING                  # One-line summary for quick reference

    # Extracted structured rules (when applicable)
    rules: LIST[{
        condition: STRING,           # "IF body type is pear"
        recommendation: STRING,      # "THEN favor A-line skirts"
        confidence: FLOAT,           # How universally applicable
        exceptions: LIST[STRING]     # When rule doesn't apply
    }]

    # Examples
    examples: LIST[{
        description: STRING,
        image_url: STRING,           # Visual example if available
        positive: BOOL               # Good example vs. what to avoid
    }]

    # Embeddings for retrieval
    embedding: VECTOR[1536]          # OpenAI ada-002 for semantic search

    # Metadata
    created_at: DATETIME
    last_verified: DATETIME          # When last checked for accuracy


STRUCTURE KnowledgeRetrievalResult:
    chunk: FashionKnowledgeChunk
    relevance_score: FLOAT           # Semantic similarity
    keyword_match_score: FLOAT       # BM25 or similar
    combined_score: FLOAT            # Hybrid ranking


CLASS FashionKnowledgeBase:
    """
    The RAG knowledge store for fashion expertise.
    Hybrid retrieval: semantic embeddings + keyword search.
    """

    vector_store: Qdrant             # For semantic search
    keyword_index: Elasticsearch     # For keyword/BM25 search

    # ═══════════════════════════════════════════════════════════════════
    # INGESTION PIPELINE
    # ═══════════════════════════════════════════════════════════════════

    FUNCTION ingest_textbook(pdf_path, metadata) → INT:
        """
        Ingest a fashion textbook into the knowledge base.
        Returns number of chunks created.
        """
        # Extract text with structure preservation
        pages = pdf_parser.extract_with_structure(pdf_path)

        # Chunk by semantic boundaries (chapters, sections, topics)
        chunks = semantic_chunker.chunk(
            pages,
            max_chunk_size=1000,      # tokens
            overlap=100,               # token overlap for context
            respect_boundaries=TRUE    # Don't split mid-paragraph
        )

        processed_chunks = []
        FOR chunk IN chunks:
            # Classify category
            category = classify_category(chunk.text)

            # Extract structured rules if present
            rules = rule_extractor.extract(chunk.text)

            # Generate summary
            summary = llm.summarize(chunk.text, max_length=50)

            # Generate embedding
            embedding = openai.embed(chunk.text)

            knowledge_chunk = FashionKnowledgeChunk(
                chunk_id=generate_id(),
                category=category,
                subcategory=infer_subcategory(chunk.text, category),
                tags=extract_tags(chunk.text),
                source={
                    title=metadata.title,
                    author=metadata.author,
                    type=metadata.type,
                    credibility_score=metadata.credibility
                },
                content=chunk.text,
                summary=summary,
                rules=rules,
                examples=extract_examples(chunk.text),
                embedding=embedding,
                created_at=now(),
                last_verified=now()
            )

            processed_chunks.append(knowledge_chunk)

        # Store in both indices
        vector_store.upsert(processed_chunks)
        keyword_index.index(processed_chunks)

        RETURN len(processed_chunks)

    FUNCTION ingest_expert_knowledge(content, expert_name, category) → STRING:
        """
        Ingest curated expert knowledge (e.g., from stylists, designers).
        """
        # Similar to textbook but single chunk, higher curation
        embedding = openai.embed(content)

        chunk = FashionKnowledgeChunk(
            chunk_id=generate_id(),
            category=category,
            source={
                title=f"Expert Knowledge: {expert_name}",
                author=expert_name,
                type="expert_article",
                credibility_score=0.9
            },
            content=content,
            summary=llm.summarize(content, max_length=50),
            rules=rule_extractor.extract(content),
            embedding=embedding,
            created_at=now(),
            last_verified=now()
        )

        vector_store.upsert([chunk])
        keyword_index.index([chunk])

        RETURN chunk.chunk_id

    # ═══════════════════════════════════════════════════════════════════
    # RETRIEVAL - Hybrid Search
    # ═══════════════════════════════════════════════════════════════════

    FUNCTION retrieve(
        query: STRING,
        categories: LIST[KnowledgeCategory] = None,
        limit: INT = 10,
        min_credibility: FLOAT = 0.5
    ) → LIST[KnowledgeRetrievalResult]:
        """
        Hybrid retrieval: combines semantic search with keyword matching.
        """

        # Semantic search
        query_embedding = openai.embed(query)
        semantic_results = vector_store.search(
            collection="fashion_knowledge",
            query_vector=query_embedding,
            filter={
                "category": {"$in": categories} if categories else None,
                "source.credibility_score": {"$gte": min_credibility}
            },
            limit=limit * 2  # Get more for re-ranking
        )

        # Keyword search (BM25)
        keyword_results = keyword_index.search(
            query=query,
            filters={
                "category": categories,
                "min_credibility": min_credibility
            },
            limit=limit * 2
        )

        # Reciprocal Rank Fusion (RRF) for hybrid ranking
        combined = reciprocal_rank_fusion(
            semantic_results,
            keyword_results,
            k=60  # RRF constant
        )

        # Build result objects
        results = []
        FOR item IN combined[:limit]:
            results.append(KnowledgeRetrievalResult(
                chunk=item.chunk,
                relevance_score=item.semantic_score,
                keyword_match_score=item.keyword_score,
                combined_score=item.rrf_score
            ))

        RETURN results

    FUNCTION retrieve_rules(
        context: {body_type, occasion, category},
        limit: INT = 5
    ) → LIST[FashionRule]:
        """
        Retrieve specific actionable rules for a context.
        """
        query = f"""
            Rules for {context.body_type} body type
            shopping for {context.category}
            for {context.occasion} occasion
        """

        results = retrieve(
            query=query,
            categories=[BODY_TYPES, OCCASION_RULES, SILHOUETTE_SCIENCE],
            limit=limit * 2
        )

        # Extract and deduplicate rules from chunks
        all_rules = []
        FOR result IN results:
            FOR rule IN result.chunk.rules:
                IF rule_applies_to_context(rule, context):
                    all_rules.append(rule)

        # Rank by confidence and deduplicate
        RETURN deduplicate_and_rank(all_rules)[:limit]


CLASS Pillar2_StylistKnowledge:
    """
    RAG-enabled fashion textbook knowledge.
    Makes ARI an expert in textbook fashion and beyond.

    Knowledge Sources:
    - Fashion textbooks (Color Me Beautiful, The Curated Closet, etc.)
    - Academic research (color psychology, body image studies)
    - Expert stylists' curated knowledge
    - Style guides and dress code references
    """

    knowledge_base: FashionKnowledgeBase

    FUNCTION query_styling_rules(context) → LIST[StylingRule]:
        """
        Retrieve relevant styling rules for the user's context.
        """
        # Build rich query from context
        query = f"""
            Styling advice for:
            - Body type: {context.body_type}
            - Occasion: {context.occasion}
            - Current style: {context.style_description}
            - Target style: {context.target_style}
            - Category: {context.category}
        """

        # Retrieve from multiple relevant categories
        results = knowledge_base.retrieve(
            query=query,
            categories=[
                KnowledgeCategory.BODY_TYPES,
                KnowledgeCategory.SILHOUETTE_SCIENCE,
                KnowledgeCategory.OCCASION_RULES,
                KnowledgeCategory.PROPORTION_THEORY
            ],
            limit=20
        )

        # Extract and format rules
        styling_rules = []
        FOR result IN results:
            FOR rule IN result.chunk.rules:
                styling_rules.append(StylingRule(
                    rule=rule.recommendation,
                    condition=rule.condition,
                    confidence=rule.confidence * result.combined_score,
                    source=result.chunk.source.title,
                    exceptions=rule.exceptions
                ))

        RETURN deduplicate_and_rank(styling_rules)

    FUNCTION get_color_guidance(user_coloring, current_palette) → ColorGuidance:
        """
        Get color recommendations based on user's coloring and current choices.
        """
        # Retrieve color theory knowledge
        color_knowledge = knowledge_base.retrieve(
            query=f"Color recommendations for {user_coloring} coloring, harmonizing with {current_palette}",
            categories=[
                KnowledgeCategory.COLOR_THEORY,
                KnowledgeCategory.COLOR_PSYCHOLOGY
            ],
            limit=10
        )

        # Combine with deterministic color harmony analysis
        lch_colors = [rgb_to_lch(c) for c in current_palette]
        harmony_analysis = lara_alvarez_analyze(lch_colors)

        RETURN ColorGuidance(
            seasonal_palette=extract_seasonal_palette(color_knowledge, user_coloring),
            harmony_analysis=harmony_analysis,
            recommended_colors=extract_color_recommendations(color_knowledge),
            colors_to_avoid=extract_colors_to_avoid(color_knowledge, user_coloring),
            knowledge_sources=[r.chunk.source.title for r in color_knowledge]
        )

    FUNCTION get_body_type_rules(body_type, category) → BodyGuidance:
        """
        Get body-type specific guidance for a garment category.
        """
        results = knowledge_base.retrieve(
            query=f"Best {category} styles for {body_type} body type, flattering silhouettes",
            categories=[
                KnowledgeCategory.BODY_TYPES,
                KnowledgeCategory.SILHOUETTE_SCIENCE,
                KnowledgeCategory.PROPORTION_THEORY,
                KnowledgeCategory.OPTICAL_ILLUSIONS
            ],
            limit=15
        )

        # Aggregate guidance from multiple sources
        flattering = []
        avoid = []
        necklines = []
        proportion_tips = []

        FOR result IN results:
            FOR rule IN result.chunk.rules:
                IF "flattering" IN rule.recommendation.lower():
                    flattering.append(rule.recommendation)
                IF "avoid" IN rule.recommendation.lower():
                    avoid.append(rule.recommendation)
                IF "neckline" IN rule.recommendation.lower():
                    necklines.append(rule.recommendation)
                IF "proportion" IN rule.recommendation.lower():
                    proportion_tips.append(rule.recommendation)

        RETURN BodyGuidance(
            flattering_silhouettes=deduplicate(flattering),
            avoid_silhouettes=deduplicate(avoid),
            neckline_recommendations=deduplicate(necklines),
            proportion_tips=deduplicate(proportion_tips),
            knowledge_sources=[r.chunk.source.title for r in results]
        )

    FUNCTION get_occasion_rules(occasion) → OccasionGuidance:
        """
        Get dress code and occasion-appropriate styling rules.
        """
        results = knowledge_base.retrieve(
            query=f"Dress code and styling rules for {occasion}, appropriate attire",
            categories=[
                KnowledgeCategory.DRESS_CODES,
                KnowledgeCategory.OCCASION_RULES,
                KnowledgeCategory.CULTURAL_CONTEXT
            ],
            limit=10
        )

        RETURN OccasionGuidance(
            formality_range=extract_formality_range(results),
            dress_codes=extract_dress_codes(results),
            fabric_appropriateness=extract_fabric_rules(results),
            colors_appropriate=extract_color_rules(results, occasion),
            common_mistakes=extract_mistakes_to_avoid(results),
            knowledge_sources=[r.chunk.source.title for r in results]
        )

    FUNCTION get_style_archetype_guidance(target_style) → StyleArchetypeGuidance:
        """
        Get guidance for achieving a particular style archetype.
        """
        results = knowledge_base.retrieve(
            query=f"{target_style} style characteristics, key pieces, how to achieve",
            categories=[
                KnowledgeCategory.STYLE_ARCHETYPES,
                KnowledgeCategory.FASHION_HISTORY,
                KnowledgeCategory.CAPSULE_WARDROBE
            ],
            limit=10
        )

        RETURN StyleArchetypeGuidance(
            defining_characteristics=extract_characteristics(results),
            key_pieces=extract_key_pieces(results),
            color_palette=extract_palette(results),
            brands_to_explore=extract_brands(results),
            styling_tips=extract_tips(results),
            knowledge_sources=[r.chunk.source.title for r in results]
        )


# ═══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

FUNCTION initialize_fashion_knowledge_base() → FashionKnowledgeBase:
    """
    Initialize and populate the fashion knowledge base.
    Called once during system setup.
    """
    kb = FashionKnowledgeBase()

    # Core textbooks
    kb.ingest_textbook("Color_Me_Beautiful.pdf", {
        title: "Color Me Beautiful",
        author: "Carole Jackson",
        type: "textbook",
        credibility: 0.9
    })

    kb.ingest_textbook("The_Curated_Closet.pdf", {
        title: "The Curated Closet",
        author: "Anuschka Rees",
        type: "textbook",
        credibility: 0.85
    })

    kb.ingest_textbook("The_Science_of_Style.pdf", {
        title: "The Science of Style",
        author: "Various",
        type: "research_paper",
        credibility: 0.95
    })

    # Body type science
    kb.ingest_textbook("Body_Shape_Bible.pdf", {
        title: "The Body Shape Bible",
        author: "Trinny & Susannah",
        type: "style_guide",
        credibility: 0.8
    })

    # Dress codes and occasions
    kb.ingest_textbook("Dress_Codes_Explained.pdf", {
        title: "Dress Codes: How the Laws of Fashion Made History",
        author: "Richard Thompson Ford",
        type: "textbook",
        credibility: 0.85
    })

    # TBD: Additional sources
    # - Academic papers on color psychology
    # - Cultural dress code guides
    # - Trend forecasting reports
    # - Expert stylist interviews

    RETURN kb


CLASS Pillar3_UserActivity:
    """
    Behavioral patterns computed from interaction history.
    V2: These are computed, not stored as fixed values.
    """

    FUNCTION get_interaction_patterns(user_id, context_filter=None) → BehavioralProfile:
        interactions = neo4j.query("""
            MATCH (u:User {id: $user_id})-[:INTERACTED_WITH]->(i)
            RETURN i.type, i.product_id, i.timestamp, i.context
            ORDER BY i.timestamp DESC
            LIMIT 500
        """, user_id=user_id)

        # Optional context filtering
        IF context_filter:
            interactions = filter_by_context(interactions, context_filter)

        RETURN BehavioralProfile(
            view_patterns=analyze_view_patterns(interactions),
            purchase_patterns=analyze_purchase_patterns(interactions),
            rejection_patterns=analyze_rejections(interactions),
            price_sensitivity=analyze_price_behavior(interactions),
            category_interests=analyze_categories(interactions),
            style_evolution=analyze_style_drift(interactions)
        )

    FUNCTION detect_preference_drift(user_id) → DriftAnalysis:
        recent = get_interactions(user_id, days=30)
        historical = get_interactions(user_id, days=365)

        IF len(recent) < 5 OR len(historical) < 5:
            RETURN DriftAnalysis(is_drifting=FALSE, drift_direction=ZERO_VECTOR)

        recent_profile = compute_style_profile(recent)
        historical_profile = compute_style_profile(historical)

        drift_vector = recent_profile - historical_profile
        drift_magnitude = norm(drift_vector)

        RETURN DriftAnalysis(
            is_drifting=drift_magnitude > 0.3,
            drift_direction=normalize(drift_vector) if drift_magnitude > 0 else ZERO_VECTOR,
            drift_speed=drift_magnitude,
            emerging_interests=identify_new_dimensions(drift_vector),
            declining_interests=identify_decreasing_dimensions(drift_vector)
        )

    FUNCTION get_recommendation_feedback(user_id) → FeedbackHistory:
        sessions = neo4j.query("""
            MATCH (u:User {id: $user_id})-[:HAD_SESSION]->(s:Session)
            MATCH (s)-[:SHOWED]->(p:Product)
            OPTIONAL MATCH (u)-[r:INTERACTED_WITH]->(p)
            RETURN s, p, r.type as outcome
        """, user_id=user_id)

        RETURN FeedbackHistory(
            click_through_rate=calculate_ctr(sessions),
            conversion_rate=calculate_conversion(sessions),
            successful_recommendations=extract_successful(sessions),
            failed_recommendations=extract_failed(sessions)
        )
```

---

### Section 3: Feature Extraction Pipeline

```
CLASS FeatureExtractor:
    """
    Extract all multi-modal features from product images.
    Unchanged from V1 - this is product processing, not user processing.
    """

    FUNCTION extract_all_features(image_url, category) → ProductRepresentation:
        image = download_image(image_url)

        segmentation = sam3.segment(
            image=image,
            text_prompt=category,
            return_mask=TRUE
        )

        isolated_garment = apply_mask(image, segmentation.mask)

        PARALLEL:
            deterministic = extract_deterministic(isolated_garment, segmentation)
            embeddings = extract_embeddings(isolated_garment, image)

        style_coords = compute_style_coordinates(deterministic, embeddings)

        RETURN ProductRepresentation(
            deterministic=deterministic,
            embeddings=embeddings,
            style_coordinates=style_coords
        )

    FUNCTION extract_deterministic(garment, segmentation) → DeterministicFeatures:
        PARALLEL:
            colors = extract_dominant_colors_kmeans(garment, k=5)
            lch_colors = [rgb_to_cie_lch(c) for c in colors]
            harmony = lara_alvarez_harmony_analysis(lch_colors)

            texture = texture_classifier.predict(garment)

            contour = extract_contour(segmentation.mask)
            silhouette = classify_silhouette(contour)
            hu = compute_hu_moments(contour)
            zernike = compute_zernike_moments(contour)

            parts = detect_garment_parts(garment, segmentation)
            neckline = analyze_neckline(parts)
            sleeves = analyze_sleeves(parts)
            hemline = analyze_hemline(parts)

        RETURN DeterministicFeatures(
            segmentation_mask=segmentation.mask,
            segmentation_confidence=segmentation.score,
            dominant_colors=colors,
            harmony_type=harmony.type,
            hue_harmony_score=harmony.hue_score,
            tone_harmony_score=harmony.tone_score,
            texture_type=texture.type,
            silhouette_type=silhouette,
            hu_moments=hu,
            zernike_moments=zernike,
            neckline=neckline,
            sleeves=sleeves,
            hemline=hemline
        )

    FUNCTION extract_embeddings(garment, full_image) → EmbeddingFeatures:
        PARALLEL:
            openai_text = openai.embed(product.title + " " + product.description)
            siglip_text = siglip.encode_text(product.title)
            siglip_vision = siglip.encode_image(garment)
            resnet = resnet50.extract_features(garment)
            siglip_multimodal = concatenate(siglip_text, siglip_vision)

        RETURN EmbeddingFeatures(
            openai_text=openai_text,
            siglip_text=siglip_text,
            siglip_vision=siglip_vision,
            resnet_features=resnet,
            siglip_multimodal=siglip_multimodal
        )

    FUNCTION compute_style_coordinates(det, emb) → StyleCoordinate:
        form = map_silhouette_to_form(det.silhouette_type, det.compactness)
        color_warmth = map_hue_to_warmth(det.dominant_colors[0].h)
        color_saturation = det.dominant_colors[0].C / 100.0
        texture = map_texture_type_to_coordinate(det.texture_type, det.fabric_roughness)
        pattern = predict_pattern_complexity(emb.resnet_features)
        formality = predict_formality(det.silhouette_type, det.texture_type, det.dominant_colors, emb.siglip_vision)
        proportion = map_aspect_to_proportion(det.aspect_ratio, det.compactness)

        all_embeddings = concatenate(
            emb.openai_text,
            emb.siglip_text,
            emb.siglip_vision,
            emb.resnet_features,
            emb.siglip_multimodal
        )

        det_vector = vectorize_deterministic(det)

        RETURN StyleCoordinate(
            form=form,
            color_warmth=color_warmth,
            color_saturation=color_saturation,
            texture=texture,
            pattern=pattern,
            formality=formality,
            proportion=proportion,
            embedding_coordinates=concatenate(all_embeddings, det_vector)
        )
```

---

### Section 4: Navigation Intelligence Core

```
CLASS NavigationIntelligence:
    """
    V2: The core brain that synthesizes all pillars via a single LLM call.

    Key changes from V1:
    - Load raw data, compute state at query time
    - Single LLM call to synthesize all pillars and determine destination
    - All other calculations are deterministic
    """

    pillars: {
        personalization: Pillar1_Personalization,
        knowledge: Pillar2_StylistKnowledge,
        activity: Pillar3_UserActivity
    }

    FUNCTION generate_navigation_context(user_id, query, occasion) → NavigationContext:
        """
        Main entry point. Assembles all pillars and synthesizes via LLM.
        """

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Load raw user data (Pillar 1)
        # ═══════════════════════════════════════════════════════════════════

        raw_user_data = pillars.personalization.load_raw_user_data(user_id)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Compute user state from raw data (deterministic)
        # ═══════════════════════════════════════════════════════════════════

        query_context = QueryContext(query=query, occasion=occasion)
        computed_state = pillars.personalization.compute_user_state(raw_user_data, query_context)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Get behavioral patterns (Pillar 3)
        # ═══════════════════════════════════════════════════════════════════

        PARALLEL:
            behavioral = pillars.activity.get_interaction_patterns(user_id, context_filter=occasion)
            drift = pillars.activity.detect_preference_drift(user_id)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Retrieve stylist knowledge (Pillar 2 - RAG)
        # ═══════════════════════════════════════════════════════════════════

        styling_context = {
            body_type: raw_user_data.body_type,
            occasion: occasion,
            style_description: describe_position(computed_state.current_position),
            target_style: query  # Will be refined by LLM
        }

        PARALLEL:
            styling_rules = pillars.knowledge.query_styling_rules(styling_context)
            body_rules = pillars.knowledge.get_body_type_rules(
                raw_user_data.body_type,
                infer_category(query)
            )
            occasion_rules = pillars.knowledge.get_occasion_rules(occasion)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: LLM SYNTHESIS (Single call)
        # The LLM receives all three pillars and synthesizes:
        # - Destination coordinates
        # - Budget interpretation for this query
        # - Formality interpretation for this occasion
        # - Exploration appetite
        # ═══════════════════════════════════════════════════════════════════

        llm_input = {
            # Pillar 1: User data
            body_type: raw_user_data.body_type,
            coloring: raw_user_data.coloring,
            demographics: raw_user_data.demographics,
            current_position: computed_state.current_position,
            trajectory: computed_state.trajectory,
            spending_patterns: computed_state.spending_patterns,
            behavioral_patterns: computed_state.behavioral_patterns,

            # Pillar 2: Stylist knowledge
            styling_rules: styling_rules,
            body_guidance: body_rules,
            occasion_guidance: occasion_rules,

            # Pillar 3: Behavioral context
            behavioral_profile: behavioral,
            is_drifting: drift.is_drifting,
            drift_direction: drift.drift_direction,

            # Query
            query: query,
            occasion: occasion
        }

        llm_output = llm_synthesize(llm_input)

        # LLM output structure:
        # {
        #     destination: StyleCoordinate,
        #     understood_intent: STRING,
        #     budget_for_this_query: {min, max},
        #     formality_for_this_occasion: FLOAT,
        #     exploration_appetite: FLOAT,  # 0-1
        #     relevant_context: LIST[STRING]
        # }

        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: Calculate navigation path (deterministic)
        # ═══════════════════════════════════════════════════════════════════

        path = calculate_navigation_path(
            current=computed_state.current_position,
            destination=llm_output.destination,
            trajectory=computed_state.trajectory,
            exploration_appetite=llm_output.exploration_appetite
        )

        # ═══════════════════════════════════════════════════════════════════
        # STEP 7: Assemble navigation context
        # ═══════════════════════════════════════════════════════════════════

        RETURN NavigationContext(
            # User state
            current_position=computed_state.current_position,
            trajectory=computed_state.trajectory,
            destination=llm_output.destination,
            path=path,

            # Raw data
            raw_user_data=raw_user_data,
            computed_state=computed_state,

            # Pillar 2
            styling_rules=styling_rules,
            body_guidance=body_rules,
            occasion_guidance=occasion_rules,

            # Pillar 3
            behavioral_profile=behavioral,
            drift_analysis=drift,

            # Query
            query=query,
            occasion=occasion,

            # LLM interpretation
            llm_interpretation=llm_output
        )

    FUNCTION llm_synthesize(input) → LLMSynthesisOutput:
        """
        Single LLM call that traverses all spaces and determines the path.
        """
        prompt = f"""
You are ARI, a style space navigator. You help users traverse multi-dimensional style space to find the best products for them.

You are given:
1. PERSONALIZATION: User's body type, coloring, current position in style space, trajectory, spending patterns
2. STYLIST KNOWLEDGE: Fashion rules for body types, occasions, color harmony
3. BEHAVIORAL PATTERNS: What they've viewed, liked, purchased, rejected

Your task: Synthesize all this information to determine:
1. WHERE they want to go (destination coordinates)
2. HOW to interpret their budget for THIS query
3. WHAT formality level is appropriate for THIS occasion
4. HOW exploratory they seem (affects outlier percentage)

USER DATA:
- Body type: {input.body_type}
- Coloring: {input.coloring}
- Demographics: {input.demographics}
- Current position: {describe_position(input.current_position)}
- Trajectory: velocity={input.trajectory.velocity}, consistency={input.trajectory.consistency}
- Spending patterns: {input.spending_patterns}
- Behavioral patterns: consistent on {input.behavioral_patterns.consistent_dimensions}, varies on {input.behavioral_patterns.variable_dimensions}

STYLIST KNOWLEDGE:
- Body guidance: {input.body_guidance}
- Occasion guidance: {input.occasion_guidance}
- Relevant styling rules: {summarize(input.styling_rules)}

BEHAVIORAL CONTEXT:
- Is drifting: {input.is_drifting}
- Drift direction: {input.drift_direction if input.is_drifting else "N/A"}
- Category interests: {input.behavioral_profile.category_interests}

QUERY: "{input.query}"
OCCASION: {input.occasion or "not specified"}

Based on all this, provide:
1. destination_coordinates: The target StyleCoordinate (form, color_warmth, etc.)
2. understood_intent: What you understand they're looking for
3. budget_range: {{min, max}} appropriate for this query given their patterns
4. formality_level: 0-1 float for this occasion
5. exploration_appetite: 0-1 float (0 = stay close to current, 1 = explore widely)
6. relevant_context: Key factors that influenced your interpretation

Respond in JSON format.
"""

        response = llm.complete(prompt, response_format="json")

        RETURN LLMSynthesisOutput(
            destination=parse_style_coordinate(response.destination_coordinates),
            understood_intent=response.understood_intent,
            budget_for_this_query=response.budget_range,
            formality_for_this_occasion=response.formality_level,
            exploration_appetite=response.exploration_appetite,
            relevant_context=response.relevant_context
        )

    FUNCTION calculate_navigation_path(current, destination, trajectory, exploration_appetite) → NavigationPath:
        """
        Deterministic path calculation.
        V2: Includes outlier injection based on exploration appetite.
        """
        total_distance = style_distance(current, destination)

        # Step size based on velocity
        IF trajectory.velocity < 0.03:
            max_step = 0.2
        ELIF trajectory.velocity < 0.06:
            max_step = 0.3
        ELSE:
            max_step = 0.4

        # Calculate waypoints
        num_waypoints = max(1, ceil(total_distance / max_step))

        waypoints = []
        current_pos = current

        FOR i IN range(num_waypoints):
            progress = (i + 1) / num_waypoints
            waypoint_target = interpolate(current, destination, progress)

            step_distance = style_distance(current_pos, waypoint_target)
            IF step_distance > max_step:
                waypoint_target = move_toward(current_pos, waypoint_target, max_step)
                step_distance = max_step

            waypoints.append({
                coordinates: waypoint_target,
                step_distance: step_distance
            })

            current_pos = waypoint_target

        # V2: Calculate outlier slots based on exploration appetite
        # exploration_appetite 0 = 0% outliers, 1 = 20% outliers
        outlier_percentage = exploration_appetite * 0.20

        RETURN NavigationPath(
            current_position=current,
            destination=destination,
            waypoints=waypoints,
            outlier_slots=outlier_percentage,
            smoothness_score=1.0 if max(w.step_distance for w in waypoints) <= 0.3 else 0.7,
            coherence_score=compute_coherence(waypoints, trajectory.direction)
        )
```

---

### Section 5: Navigation-Aware Agents

```
# ═══════════════════════════════════════════════════════════════════
# AGENT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

CONFIG AgentConfiguration:
    # V2: Graph agent off by default
    graph_agent_enabled: BOOL = FALSE

    # Enable graph agent for specific query types
    FUNCTION should_enable_graph_agent(query_analysis) → BOOL:
        IF query_analysis.has_brand:
            RETURN TRUE
        IF query_analysis.has_price_constraint:
            RETURN TRUE
        IF query_analysis.has_size_constraint:
            RETURN TRUE
        IF query_analysis.has_material_constraint:
            RETURN TRUE
        RETURN FALSE


CLASS VibeBot_Navigator:
    """
    Semantic navigator using vector embeddings.
    PRIMARY agent in V2.
    Uses direct user↔product embedding similarity.
    """

    FUNCTION search(nav_context: NavigationContext) → LIST[Product]:
        # Get user's semantic embedding (pre-computed, same space as products)
        user_embedding = nav_context.computed_state.embeddings.semantic

        # Build query-augmented embedding
        query_embedding = openai.embed(nav_context.query)

        # Blend user embedding with query (user provides context, query provides intent)
        search_vector = normalize(user_embedding * 0.4 + query_embedding * 0.6)

        # V2: Use LLM-interpreted budget
        budget = nav_context.llm_interpretation.budget_for_this_query
        formality = nav_context.llm_interpretation.formality_for_this_occasion

        results = qdrant.search(
            collection="fashion_products",
            query_vector=search_vector,
            filter={
                "price": {"$gte": budget.min, "$lte": budget.max},
                "formality": {"$gte": formality - 0.2, "$lte": formality + 0.2}
            },
            limit=50
        )

        # Re-rank by user embedding similarity (direct comparison in same space)
        FOR product IN results:
            # Direct user↔product similarity (they live in same embedding space)
            user_sim = cosine_similarity(
                product.embeddings.openai_text,
                user_embedding
            )
            # Query relevance
            query_sim = cosine_similarity(
                product.embeddings.openai_text,
                query_embedding
            )
            product.semantic_bridge_score = (user_sim * 0.4 + query_sim * 0.6)

        RETURN sorted(results, key=lambda p: p.semantic_bridge_score)[:20]


CLASS VisionBot_Navigator:
    """
    Visual navigator using image embeddings + deterministic features.
    PRIMARY agent in V2.
    Uses direct user↔product visual embedding similarity.
    """

    FUNCTION search(nav_context: NavigationContext) → LIST[Product]:
        # Get user's visual embedding (pre-computed, same space as products)
        user_visual_embedding = nav_context.computed_state.embeddings.visual

        # Search using user's visual embedding directly
        visual_results = qdrant.search(
            collection="fashion_multimodal_embeddings",
            query_vector=user_visual_embedding,
            limit=50
        )

        # Apply deterministic filters
        filtered = []
        FOR product IN visual_results:
            # Body type filter
            IF product.deterministic.silhouette_type IN nav_context.body_guidance.flattering:
                # Color harmony check
                harmony = check_harmony_with_existing(
                    product.deterministic.dominant_colors,
                    nav_context.behavioral_profile.preferred_colors
                )

                IF harmony.score > 0.6:
                    product.visual_harmony_score = harmony.score
                    product.body_type_match = TRUE
                    filtered.append(product)

        # Score by visual similarity to user (direct embedding comparison)
        FOR product IN filtered:
            # Direct user↔product visual similarity (same embedding space)
            user_visual_sim = cosine_similarity(
                product.embeddings.siglip_vision,
                user_visual_embedding
            )
            product.visual_continuity = user_visual_sim

        RETURN sorted(filtered,
                     key=lambda p: p.visual_continuity * 0.5 + p.visual_harmony_score * 0.5)[:20]


CLASS GraphBot_Navigator:
    """
    Graph-based navigator using Neo4j.
    V2: OFF BY DEFAULT. Enabled only for specific attribute queries.
    """

    FUNCTION search(nav_context: NavigationContext) → LIST[Product]:
        # Only called if AgentConfiguration.should_enable_graph_agent() returned TRUE

        query_analysis = analyze_query(nav_context.query)

        # Build Cypher query based on specific constraints
        filters = []
        IF query_analysis.brand:
            filters.append(f"(p)-[:BY_BRAND]->(b:Brand {{name: '{query_analysis.brand}'}})")
        IF query_analysis.price_max:
            filters.append(f"p.price <= {query_analysis.price_max}")
        IF query_analysis.size:
            filters.append(f"'{query_analysis.size}' IN p.size_options")

        cypher = f"""
            MATCH (p:Product)
            WHERE {" AND ".join(filters)}
            RETURN p
            LIMIT 50
        """

        results = neo4j.query(cypher)

        # Score by trajectory alignment
        FOR product IN results:
            product.trajectory_alignment = compute_alignment(
                product.style_coordinates,
                nav_context.trajectory.direction
            )

        RETURN sorted(results, key=lambda p: p.trajectory_alignment)[:20]


CLASS JudgeAri_PathEvaluator:
    """
    Evaluates path quality and selects best products.
    V2: Scoring based on computed patterns, not stored preferences.
    """

    FUNCTION evaluate_and_select(
        vibe_results: LIST[Product],
        vision_results: LIST[Product],
        graph_results: LIST[Product],  # May be empty if graph agent disabled
        nav_context: NavigationContext,
        limit: INT = 10
    ) → LIST[Product]:

        all_products = deduplicate(vibe_results + vision_results + graph_results)

        FOR product IN all_products:
            scores = {}

            # 1. SMOOTHNESS: Reasonable step from current position
            step_distance = style_distance(
                nav_context.current_position,
                product.style_coordinates
            )
            scores.smoothness = 1.0 if step_distance <= 0.3 else max(0, 1.0 - step_distance)

            # 2. COHERENCE: Aligns with trajectory direction
            trajectory_dot = dot_product(
                nav_context.trajectory.direction,
                product.style_coordinates - nav_context.current_position
            )
            scores.coherence = max(0, min(1, trajectory_dot + 0.5))

            # 3. BUDGET FIT: Within LLM-interpreted budget for this query
            budget = nav_context.llm_interpretation.budget_for_this_query
            IF product.price <= budget.max:
                IF product.price >= budget.min:
                    scores.budget_fit = 1.0
                ELSE:
                    scores.budget_fit = 0.8  # Under budget is okay
            ELSE:
                scores.budget_fit = max(0, 1.0 - (product.price - budget.max) / budget.max)

            # 4. BEHAVIORAL CONSISTENCY: Matches user's consistent dimensions
            # V2: Uses computed patterns, not stored preferences
            consistency_score = 0.0
            consistent_dims = nav_context.computed_state.behavioral_patterns.consistent_dimensions
            FOR dim IN consistent_dims:
                user_value = nav_context.current_position[dim]
                product_value = product.style_coordinates[dim]
                IF abs(user_value - product_value) < 0.2:
                    consistency_score += 1.0
            scores.behavioral_consistency = consistency_score / max(1, len(consistent_dims))

            # 5. MULTI-AGENT CONFIDENCE
            in_vibe = product IN vibe_results
            in_vision = product IN vision_results
            in_graph = product IN graph_results
            agent_count = sum([in_vibe, in_vision, in_graph])
            scores.multi_agent = 0.6 + (agent_count - 1) * 0.2

            # 6. STYLING RULE COMPLIANCE
            scores.rule_compliance = evaluate_rule_compliance(
                product,
                nav_context.styling_rules,
                nav_context.body_guidance,
                nav_context.occasion_guidance
            )

            # Weighted combination
            product.path_quality_score = (
                scores.smoothness * 0.20 +
                scores.coherence * 0.15 +
                scores.budget_fit * 0.15 +
                scores.behavioral_consistency * 0.20 +
                scores.multi_agent * 0.10 +
                scores.rule_compliance * 0.20
            )

        # Sort by score
        sorted_products = sorted(all_products, key=lambda p: p.path_quality_score, reverse=TRUE)

        # V2: Inject outliers for exploration
        outlier_count = int(limit * nav_context.path.outlier_slots)
        main_count = limit - outlier_count

        main_results = sorted_products[:main_count]

        IF outlier_count > 0:
            # Get products outside the typical range for exploration
            outlier_candidates = [p for p in sorted_products[main_count:]
                                 if style_distance(nav_context.current_position, p.style_coordinates) > 0.4]
            outliers = random.sample(outlier_candidates, min(outlier_count, len(outlier_candidates)))
            main_results.extend(outliers)

        RETURN main_results
```

---

### Section 6: Main Orchestration Flow

```
CLASS NavigationOrchestrator:
    """
    Main entry point.
    V2: Simplified flow with conditional graph agent.
    """

    navigation_intelligence: NavigationIntelligence
    agents: {
        vibe: VibeBot_Navigator,
        vision: VisionBot_Navigator,
        graph: GraphBot_Navigator,
        judge: JudgeAri_PathEvaluator
    }
    config: AgentConfiguration

    ASYNC FUNCTION execute_search(
        user_id: STRING,
        query: STRING,
        occasion: STRING = None,
        limit: INT = 10
    ) → SearchResult:

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Generate Navigation Context (3 Pillars + LLM Synthesis)
        # ═══════════════════════════════════════════════════════════════════

        nav_context = await navigation_intelligence.generate_navigation_context(
            user_id=user_id,
            query=query,
            occasion=occasion
        )

        log.info(f"""
            Navigation Context Generated:
            - Current Position: {describe_position(nav_context.current_position)}
            - Trajectory: velocity={nav_context.trajectory.velocity}
            - Destination: {describe_position(nav_context.destination)}
            - LLM Interpretation: {nav_context.llm_interpretation.understood_intent}
            - Budget for query: {nav_context.llm_interpretation.budget_for_this_query}
            - Exploration appetite: {nav_context.llm_interpretation.exploration_appetite}
        """)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Agent Execution
        # V2: Graph agent conditional
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
        # STEP 3: Judge Evaluation (deterministic scoring)
        # ═══════════════════════════════════════════════════════════════════

        final_products = await agents.judge.evaluate_and_select(
            vibe_results=vibe_results,
            vision_results=vision_results,
            graph_results=graph_results,
            nav_context=nav_context,
            limit=limit
        )

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Generate Navigation Explanation
        # ═══════════════════════════════════════════════════════════════════

        explanation = generate_navigation_explanation(
            nav_context=nav_context,
            products=final_products
        )

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: Track Interaction for Learning
        # ═══════════════════════════════════════════════════════════════════

        await track_recommendation_session(
            user_id=user_id,
            nav_context=nav_context,
            products_shown=final_products,
            agents_used=["vibe", "vision"] + (["graph"] if use_graph else [])
        )

        RETURN SearchResult(
            products=final_products,
            navigation_explanation=explanation,
            path=nav_context.path,
            metadata={
                "current_position": nav_context.current_position,
                "destination": nav_context.destination,
                "trajectory_velocity": nav_context.trajectory.velocity,
                "llm_interpretation": nav_context.llm_interpretation,
                "agents_used": ["vibe", "vision"] + (["graph"] if use_graph else []),
                "outlier_count": int(limit * nav_context.path.outlier_slots)
            }
        )

    FUNCTION generate_navigation_explanation(nav_context, products) → STRING:
        """
        Generate natural language explanation of the navigation path.
        This is the journey narrative.
        """
        RETURN f"""
You're currently at {describe_position(nav_context.current_position)}.

For {nav_context.occasion or "this search"}, we're navigating toward
{describe_position(nav_context.destination)}.

{nav_context.llm_interpretation.understood_intent}

Based on your {nav_context.raw_user_data.body_type} body type, I've selected pieces with
{nav_context.body_guidance.flattering_silhouettes} silhouettes.

Here's your path:

{FOR product IN products:}
- {product.title} (${product.price})
  - Style distance: {product.step_distance:.2f}
  - Why: {explain_product_selection(product, nav_context)}
{ENDFOR}

These pieces bridge where you are and where you want to be - each one
is a comfortable step that still feels like you.
"""
```

---

### Section 7: Cold Start Handling

```
FUNCTION handle_cold_start(user_id) → ComputedUserState:
    """
    For new users without interaction history.
    V2: Uses raw onboarding data, doesn't store fixed preferences.
    """

    raw_data = pillars.personalization.load_raw_user_data(user_id)

    IF raw_data.onboarding_responses:
        # User completed onboarding - derive initial position from responses
        # But don't store fixed preferences, just compute initial position
        initial_position = derive_position_from_onboarding(raw_data.onboarding_responses)
        trajectory = Trajectory(
            direction=ZERO_VECTOR,
            velocity=0.05,
            consistency=0.5
        )
    ELSE:
        # Truly new user - use population median
        initial_position = get_population_median_position()
        trajectory = Trajectory(
            direction=ZERO_VECTOR,
            velocity=0.05,
            consistency=0.5
        )

    RETURN ComputedUserState(
        current_position=initial_position,
        trajectory=trajectory,
        spending_patterns=get_default_spending_patterns(),
        behavioral_patterns=BehavioralPatterns(
            consistent_dimensions=[],
            variable_dimensions=STYLE_DIMENSIONS,  # All variable until we learn
            preferred_categories=[],
            avoided_categories=[]
        )
    )


FUNCTION derive_position_from_onboarding(onboarding_responses) → StyleCoordinate:
    """
    Map raw onboarding responses to initial style coordinates.
    This is a one-time computation, not stored as fixed preferences.
    """
    # Parse raw onboarding JSON
    responses = parse_onboarding(onboarding_responses)

    # Extract signals from responses (without LLM, just mapping)
    form = 0.5  # Default neutral
    IF "structured" in responses.style_words: form += 0.2
    IF "flowy" in responses.style_words: form -= 0.2

    formality = 0.5
    IF "professional" in responses.occasions: formality += 0.2
    IF "casual" in responses.occasions: formality -= 0.2

    # ... similar mappings for other dimensions

    RETURN StyleCoordinate(
        form=clamp(form, 0, 1),
        formality=clamp(formality, 0, 1),
        # ... other dimensions with defaults
        embedding_coordinates=ZERO_VECTOR  # Will be populated from behavior
    )
```

---

### Section 8: Batch Processing for Product Catalog

```
ASYNC FUNCTION batch_process_products():
    """
    Process all products to extract features and compute style coordinates.
    Unchanged from V1 - this is product processing.
    """

    batch_size = 100
    products = neo4j.query("MATCH (p:Product) RETURN p.id, p.images[0] as image")

    FOR batch IN chunks(products, batch_size):
        PARALLEL FOR product IN batch:
            TRY:
                representation = feature_extractor.extract_all_features(
                    image_url=product.image,
                    category=infer_category(product)
                )

                neo4j.query("""
                    MATCH (p:Product {id: $id})
                    SET p.style_coordinates = $coords,
                        p.dominant_colors = $colors,
                        p.harmony_type = $harmony,
                        p.silhouette_type = $silhouette,
                        p.texture_type = $texture
                """,
                    id=product.id,
                    coords=representation.style_coordinates,
                    colors=representation.deterministic.dominant_colors,
                    harmony=representation.deterministic.harmony_type,
                    silhouette=representation.deterministic.silhouette_type,
                    texture=representation.deterministic.texture_type
                )

                qdrant.upsert(
                    collection="fashion_multimodal_embeddings",
                    points=[{
                        id: product.id,
                        vector: representation.embeddings.siglip_multimodal,
                        payload: {
                            "style_coordinates": representation.style_coordinates,
                            "deterministic": representation.deterministic
                        }
                    }]
                )

            CATCH Exception as e:
                log.error(f"Failed to process {product.id}: {e}")
                continue

        await sleep(1.0)
```

---

## Summary of V2 Changes

| Aspect | V1 | V2 |
|--------|----|----|
| **User preferences** | Stored as fixed values (core_dimensions, budget_range) | Computed from behavior at query time |
| **Position/Trajectory** | Computed | Computed (unchanged) |
| **LLM usage** | Multiple calls for various inferences | Single call to synthesize all pillars |
| **Budget** | Fixed stored range | Computed from patterns + LLM interprets for query context |
| **Core dimensions** | Stored from onboarding | Detected as consistent behavioral patterns |
| **Graph agent** | Always on | Off by default, enabled for specific attribute queries |
| **Outliers** | None | 10-20% based on exploration appetite |
| **Data storage** | Extract and store preferences | Store raw data, compute at query time |
| **Scoring (authenticity)** | Based on stored core_minimums | Based on computed behavioral_consistency |

---

## Implementation Priority

### Phase 1: Core Infrastructure
1. Implement `RawUserData` and `ComputedUserState` structures
2. Update Neo4j schema for raw data storage
3. Build computation functions for position, trajectory, patterns

### Phase 2: LLM Synthesis
1. Implement `llm_synthesize()` with structured output
2. Test destination inference quality
3. Tune prompt for budget/formality interpretation

### Phase 3: Agent Updates
1. Update agents to use `NavigationContext` V2
2. Implement graph agent enable/disable logic
3. Add outlier injection to JudgeAri

### Phase 4: Testing
1. A/B test V1 vs V2 on recommendation quality
2. Measure latency (single LLM call should be faster)
3. Validate that computed preferences match user expectations
