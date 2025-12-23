# ARI Navigation Intelligence - Pseudocode Specification

**Version:** 1.0
**Status:** Design Specification

---

## Overview

This document contains the pseudocode specification for ARI's Navigation Intelligence system, which replaces the simple ML Intelligence layer with a RAG-enabled stylist that combines:

1. **Pillar 1: Personalization** - User-specific data from Neo4j User Graph
2. **Pillar 2: Stylist Knowledge** - Textbook fashion literature (RAG)
3. **Pillar 3: User Activity** - Behavioral patterns and interaction history

The system uses both **learned embeddings** (SigLIP, OpenAI, ResNet) and **deterministic features** (SAM3 segmentation, color science, texture, shape) to navigate users through multi-dimensional style space.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     ARI NAVIGATION INTELLIGENCE                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   PILLAR 1      │  │   PILLAR 2      │  │   PILLAR 3      │              │
│  │ PERSONALIZATION │  │ STYLIST         │  │ USER ACTIVITY   │              │
│  │                 │  │ KNOWLEDGE       │  │ PATTERNS        │              │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤              │
│  │ User Graph      │  │ Textbook        │  │ Behavioral      │              │
│  │ • TasteProfile  │  │ Literature      │  │ Tracking        │              │
│  │ • BodyData      │  │ • Color theory  │  │ • Interactions  │              │
│  │ • RootValues    │  │ • Body types    │  │ • Purchases     │              │
│  │ • StyleProfile  │  │ • Occasion      │  │ • Views/Likes   │              │
│  │ • Trajectory    │  │   rules         │  │ • Session data  │              │
│  │                 │  │ • Silhouettes   │  │ • Trajectory    │              │
│  └────────┬────────┘  │ • Harmony       │  │   velocity      │              │
│           │           └────────┬────────┘  └────────┬────────┘              │
│           │                    │                    │                        │
│           └────────────────────┼────────────────────┘                        │
│                                ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              MULTI-MODAL FEATURE EXTRACTION                          │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │   EMBEDDINGS (Learned)              DETERMINISTIC (Computed)         │   │
│  │   ─────────────────────────         ───────────────────────────      │   │
│  │   • SigLIP Vision (1024d)           • SAM3 Segmentation Masks        │   │
│  │   • SigLIP Text (1024d)             • Color Science (CIE LCh)        │   │
│  │   • OpenAI Text (1536d)             • Color Harmony (Lara-Alvarez)   │   │
│  │   • ResNet-50 (2048d)               • Texture Classification         │   │
│  │   • Multimodal Fusion (2048d)       • Shape Descriptors (Hu, Zernike)│   │
│  │                                     • Silhouette Type (A-line, etc.) │   │
│  │   Total: ~7,700 dimensions          • Part-Based Geometry            │   │
│  │                                     • Contour/Lines Analysis         │   │
│  │                                                                      │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              STYLE SPACE NAVIGATION ENGINE                           │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │   Position → Trajectory → Destination → Path → Waypoints            │   │
│  │                                                                      │   │
│  │   [current coordinates] + [movement vector] + [tangential context]  │   │
│  │                     ↓                                                │   │
│  │   [smooth path with ≤0.3 unit steps preserving authenticity]        │   │
│  │                                                                      │   │
│  └───────────────────────────────┬──────────────────────────────────────┘   │
│                                  ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              AGENT COORDINATION                                      │   │
│  │                                                                      │   │
│  │   CypherBot     VibeBot      VisionBot     JudgeAri                 │   │
│  │   (Trajectory)  (Semantic)   (Visual)      (Path Quality)           │   │
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
    embedding_coordinates: VECTOR[10600]  # All embeddings concatenated


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
    hu_moments: VECTOR[7]  # Rotation/scale invariant
    zernike_moments: VECTOR[36]

    # Part-Based Geometry
    neckline: {type: STRING, depth: FLOAT}
    sleeves: {type: STRING, length_ratio: FLOAT}
    waistline_position: FLOAT
    hemline_shape: STRING
    hem_curvature: FLOAT


STRUCTURE EmbeddingFeatures:
    # Text Embeddings
    openai_text: VECTOR[1536]      # General semantics
    siglip_text: VECTOR[1024]      # Fashion-specific semantics

    # Vision Embeddings
    siglip_vision: VECTOR[1024]    # Fashion visual features
    resnet_features: VECTOR[2048]  # Deep CNN features

    # Multimodal
    siglip_multimodal: VECTOR[2048]  # Text + Vision fused


STRUCTURE ProductRepresentation:
    product_id: STRING
    title: STRING
    price: FLOAT
    images: LIST[URL]

    # Multi-modal features
    deterministic: DeterministicFeatures
    embeddings: EmbeddingFeatures

    # Computed style coordinates (from all features)
    style_coordinates: StyleCoordinate


STRUCTURE UserProfile:
    user_id: STRING

    # Current Style Position (computed)
    current_position: StyleCoordinate

    # Trajectory (computed from history)
    trajectory: {
        direction: VECTOR[N],      # Which dimensions changing
        velocity: FLOAT,           # Rate of change (units/week)
        consistency: FLOAT         # Stable vs erratic
    }

    # Core Identity (non-negotiables from onboarding)
    core_dimensions: LIST[STRING]  # e.g., ["minimalist", "comfortable"]
    core_minimum_values: MAP[dimension → min_value]

    # Tangential Context
    demographics: {age, location, profession}
    psychometrics: {openness, risk_tolerance, conscientiousness}
    psychology: {confidence, aspirations, no_go_zones}
    life_context: {current_events, goals}

    # Body Data
    body_type: STRING
    coloring: STRING
    fit_preferences: LIST[STRING]

    # Budget
    budget_range: {min: FLOAT, max: FLOAT}


STRUCTURE NavigationPath:
    current_position: StyleCoordinate
    destination: StyleCoordinate
    waypoints: LIST[{
        coordinates: StyleCoordinate,
        products: LIST[ProductRepresentation],
        step_distance: FLOAT,
        week_target: INT
    }]

    # Quality metrics
    smoothness_score: FLOAT
    coherence_score: FLOAT
    achievability_score: FLOAT
    authenticity_score: FLOAT
    overall_quality: FLOAT
```

---

### Section 2: Three Pillars - Knowledge Sources

```
CLASS Pillar1_Personalization:
    """
    User-specific data from Neo4j User Graph + Mem0
    """

    FUNCTION load_user_context(user_id) → UserProfile:
        # Load from Neo4j User Graph
        user_node = neo4j.query("""
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:HAS_PERSONAL_IDENTITY]->(pi)
            OPTIONAL MATCH (u)-[:HAS_TASTE_PROFILE]->(tp)
            OPTIONAL MATCH (u)-[:HAS_PROCESS_PROFILE]->(pp)
            OPTIONAL MATCH (u)-[:HAS_PRACTICALITY_PROFILE]->(prp)
            OPTIONAL MATCH (u)-[:HAS_BODY_DATA]->(bd)
            OPTIONAL MATCH (u)-[:HAS_ROOT_VALUE]->(rv)
            RETURN u, pi, tp, pp, prp, bd, collect(rv) as values
        """, user_id=user_id)

        # Compute current position from interactions
        interactions = neo4j.query("""
            MATCH (u:User {id: $user_id})-[r:INTERACTED_WITH]->(i:Interaction)
            WHERE r.timestamp > datetime() - duration('P3M')
            MATCH (i)-[:WITH_PRODUCT]->(p:Product)
            RETURN p, r.type, r.timestamp
            ORDER BY r.timestamp DESC
        """, user_id=user_id)

        current_position = compute_position_from_interactions(interactions)
        trajectory = compute_trajectory_from_history(interactions)

        # Load episodic memory from Mem0
        episodic = mem0.get_episodic(user_id, limit=20)

        RETURN UserProfile(
            current_position=current_position,
            trajectory=trajectory,
            core_dimensions=extract_core_from(user_node.tp),
            ...
        )

    FUNCTION compute_position_from_interactions(interactions) → StyleCoordinate:
        # Weight recent interactions more heavily
        weighted_products = []
        FOR interaction IN interactions:
            weight = recency_weight(interaction.timestamp)
            IF interaction.type == "PURCHASED": weight *= 3.0
            IF interaction.type == "LIKED": weight *= 2.0
            IF interaction.type == "VIEWED": weight *= 1.0
            weighted_products.append((interaction.product, weight))

        # Aggregate style coordinates
        position = StyleCoordinate.zero()
        total_weight = 0
        FOR (product, weight) IN weighted_products:
            position += product.style_coordinates * weight
            total_weight += weight

        RETURN position / total_weight


CLASS Pillar2_StylistKnowledge:
    """
    RAG-enabled fashion textbook knowledge
    """

    # Preloaded knowledge base (vectorized for semantic search)
    knowledge_base: VectorStore  # Contains fashion rules, theories, guidelines

    FUNCTION query_styling_rules(context) → LIST[StylingRule]:
        """
        Retrieve relevant styling rules based on context
        """
        # Build query from context
        query_text = f"""
            User body type: {context.body_type}
            Occasion: {context.occasion}
            Current style: {context.style_description}
            Destination style: {context.target_style}
        """

        # Semantic search in knowledge base
        relevant_rules = knowledge_base.search(
            query=query_text,
            filters={
                "category": ["body_type", "occasion", "color_theory", "silhouette"]
            },
            limit=20
        )

        RETURN relevant_rules

    FUNCTION get_color_harmony_rules(colors) → HarmonyGuidance:
        """
        Apply Lara-Alvarez color science
        """
        lch_colors = [rgb_to_lch(c) for c in colors]

        # Determine harmony type
        harmony = lara_alvarez_analyze(lch_colors)

        # Get complementary suggestions
        IF harmony.type == "none":
            suggestions = generate_harmonious_palette(lch_colors[0])
        ELSE:
            suggestions = []

        RETURN HarmonyGuidance(
            current_harmony=harmony,
            suggestions=suggestions,
            rules=lookup_harmony_rules(harmony.type)
        )

    FUNCTION get_body_type_rules(body_type, category) → BodyGuidance:
        """
        Retrieve silhouette recommendations for body type
        """
        rules = knowledge_base.query(
            """
            body_type:{body_type} AND category:{category}
            """,
            collection="body_silhouette_rules"
        )

        RETURN BodyGuidance(
            flattering_silhouettes=rules.flattering,
            avoid_silhouettes=rules.avoid,
            neckline_recommendations=rules.necklines,
            proportion_tips=rules.proportions
        )

    FUNCTION get_occasion_rules(occasion) → OccasionGuidance:
        """
        Formality and appropriateness rules
        """
        RETURN knowledge_base.lookup(
            "occasions",
            occasion,
            fields=["formality_range", "dress_codes", "fabric_appropriateness"]
        )


CLASS Pillar3_UserActivity:
    """
    Behavioral patterns and interaction history
    """

    FUNCTION get_interaction_patterns(user_id) → BehavioralProfile:
        # Query all interactions
        interactions = neo4j.query("""
            MATCH (u:User {id: $user_id})-[:INTERACTED_WITH]->(i)
            RETURN i.type, i.product_id, i.timestamp, i.context
            ORDER BY i.timestamp DESC
            LIMIT 500
        """, user_id=user_id)

        RETURN BehavioralProfile(
            view_patterns=analyze_view_patterns(interactions),
            purchase_patterns=analyze_purchase_patterns(interactions),
            rejection_patterns=analyze_rejections(interactions),
            time_of_day_preferences=analyze_timing(interactions),
            price_sensitivity=analyze_price_behavior(interactions),
            category_interests=analyze_categories(interactions),
            style_evolution=analyze_style_drift(interactions)
        )

    FUNCTION detect_preference_drift(user_id) → DriftAnalysis:
        """
        Compare recent behavior to historical patterns
        """
        recent = get_interactions(user_id, days=30)
        historical = get_interactions(user_id, days=365)

        recent_profile = compute_style_profile(recent)
        historical_profile = compute_style_profile(historical)

        drift_vector = recent_profile - historical_profile
        drift_magnitude = norm(drift_vector)

        RETURN DriftAnalysis(
            is_drifting=drift_magnitude > 0.3,
            drift_direction=normalize(drift_vector),
            drift_speed=drift_magnitude,
            emerging_interests=identify_new_dimensions(drift_vector),
            declining_interests=identify_decreasing_dimensions(drift_vector)
        )

    FUNCTION get_recommendation_feedback(user_id) → FeedbackHistory:
        """
        Learn from past recommendation outcomes
        """
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
    Extract all multi-modal features from product images
    """

    FUNCTION extract_all_features(image_url, category) → ProductRepresentation:
        # 1. Download image
        image = download_image(image_url)

        # 2. SAM3 Segmentation (text-prompted)
        segmentation = sam3.segment(
            image=image,
            text_prompt=category,  # "dress", "shirt", etc.
            return_mask=TRUE
        )

        # 3. Extract isolated garment
        isolated_garment = apply_mask(image, segmentation.mask)

        # 4. PARALLEL extraction of all features
        PARALLEL:
            deterministic = extract_deterministic(isolated_garment, segmentation)
            embeddings = extract_embeddings(isolated_garment, image)

        # 5. Compute unified style coordinates
        style_coords = compute_style_coordinates(deterministic, embeddings)

        RETURN ProductRepresentation(
            deterministic=deterministic,
            embeddings=embeddings,
            style_coordinates=style_coords
        )

    FUNCTION extract_deterministic(garment, segmentation) → DeterministicFeatures:
        PARALLEL:
            # Color Science
            colors = extract_dominant_colors_kmeans(garment, k=5)
            lch_colors = [rgb_to_cie_lch(c) for c in colors]
            harmony = lara_alvarez_harmony_analysis(lch_colors)

            # Texture Classification
            texture = texture_classifier.predict(garment)
            gabor_features = extract_gabor_features(garment)
            lbp_features = extract_lbp_features(garment)

            # Shape/Silhouette
            contour = extract_contour(segmentation.mask)
            silhouette = classify_silhouette(contour)
            hu = compute_hu_moments(contour)
            zernike = compute_zernike_moments(contour)
            shape_context = compute_shape_context(contour)

            # Part-Based Geometry
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
            neckline=neckline,
            sleeves=sleeves,
            ...
        )

    FUNCTION extract_embeddings(garment, full_image) → EmbeddingFeatures:
        PARALLEL:
            # Text embeddings (from title/description)
            openai_text = openai.embed(product.title + " " + product.description)
            siglip_text = siglip.encode_text(product.title)

            # Vision embeddings
            siglip_vision = siglip.encode_image(garment)
            resnet = resnet50.extract_features(garment)

            # Multimodal fusion
            siglip_multimodal = concatenate(siglip_text, siglip_vision)

        RETURN EmbeddingFeatures(
            openai_text=openai_text,
            siglip_text=siglip_text,
            siglip_vision=siglip_vision,
            resnet_features=resnet,
            siglip_multimodal=siglip_multimodal
        )

    FUNCTION compute_style_coordinates(det, emb) → StyleCoordinate:
        """
        Map all features to unified style space
        """
        # Form: from silhouette + structure detection
        form = map_silhouette_to_form(det.silhouette_type, det.compactness)

        # Color: from CIE LCh analysis
        color_warmth = map_hue_to_warmth(det.dominant_colors[0].h)
        color_saturation = det.dominant_colors[0].C / 100.0

        # Texture: from texture classifier
        texture = map_texture_type_to_coordinate(det.texture_type, det.fabric_roughness)

        # Pattern: from vision embeddings (detect pattern complexity)
        pattern = predict_pattern_complexity(emb.resnet_features)

        # Formality: from ensemble of signals
        formality = predict_formality(
            silhouette=det.silhouette_type,
            texture=det.texture_type,
            colors=det.dominant_colors,
            embeddings=emb.siglip_vision
        )

        # Embedding coordinates: concatenate all
        all_embeddings = concatenate(
            emb.openai_text,      # 1536
            emb.siglip_text,      # 1024
            emb.siglip_vision,    # 1024
            emb.resnet_features,  # 2048
            emb.siglip_multimodal # 2048
        )  # Total: 7680d for embeddings

        # Add deterministic as additional dimensions
        det_vector = vectorize_deterministic(det)  # ~900d

        RETURN StyleCoordinate(
            form=form,
            color_warmth=color_warmth,
            color_saturation=color_saturation,
            texture=texture,
            pattern=pattern,
            formality=formality,
            embedding_coordinates=concatenate(all_embeddings, det_vector)
        )
```

---

### Section 4: Navigation Intelligence Core

```
CLASS NavigationIntelligence:
    """
    The core brain that replaces simple LLM prompting with RAG-enabled navigation
    """

    pillars: {
        personalization: Pillar1_Personalization,
        knowledge: Pillar2_StylistKnowledge,
        activity: Pillar3_UserActivity
    }

    FUNCTION generate_navigation_context(user_id, query, occasion) → NavigationContext:
        """
        Synthesize all pillars into navigation context for agents
        """
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Load user from all three pillars
        # ═══════════════════════════════════════════════════════════════════

        PARALLEL:
            user_profile = pillars.personalization.load_user_context(user_id)
            behavioral = pillars.activity.get_interaction_patterns(user_id)
            drift = pillars.activity.detect_preference_drift(user_id)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Parse query and determine destination
        # ═══════════════════════════════════════════════════════════════════

        query_analysis = analyze_query(query)

        # Infer destination coordinates
        IF query_analysis.has_explicit_destination:
            # User said "I want professional clothes"
            destination = map_description_to_coordinates(query_analysis.target_style)
        ELSE:
            # Infer from context + trajectory
            destination = infer_destination(
                current=user_profile.current_position,
                trajectory=user_profile.trajectory,
                occasion=occasion,
                query_intent=query_analysis.intent
            )

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Retrieve relevant stylist knowledge (RAG)
        # ═══════════════════════════════════════════════════════════════════

        styling_context = {
            body_type=user_profile.body_type,
            occasion=occasion,
            style_description=describe_position(user_profile.current_position),
            target_style=describe_position(destination)
        }

        PARALLEL:
            styling_rules = pillars.knowledge.query_styling_rules(styling_context)
            body_rules = pillars.knowledge.get_body_type_rules(
                user_profile.body_type,
                query_analysis.category
            )
            occasion_rules = pillars.knowledge.get_occasion_rules(occasion)
            color_guidance = pillars.knowledge.get_color_harmony_rules(
                user_profile.preferred_colors
            )

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Calculate navigation path
        # ═══════════════════════════════════════════════════════════════════

        path = calculate_navigation_path(
            current=user_profile.current_position,
            destination=destination,
            trajectory=user_profile.trajectory,
            core_dimensions=user_profile.core_dimensions,
            core_minimums=user_profile.core_minimum_values,
            constraints={
                budget=user_profile.budget_range,
                timeline=query_analysis.timeline,
                psychometrics=user_profile.psychometrics
            }
        )

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: Assemble navigation context for agents
        # ═══════════════════════════════════════════════════════════════════

        RETURN NavigationContext(
            # User State
            current_position=user_profile.current_position,
            trajectory=user_profile.trajectory,
            destination=destination,
            path=path,

            # Personalization (Pillar 1)
            body_type=user_profile.body_type,
            core_dimensions=user_profile.core_dimensions,
            core_minimums=user_profile.core_minimum_values,
            budget=user_profile.budget_range,

            # Knowledge (Pillar 2)
            styling_rules=styling_rules,
            body_guidance=body_rules,
            occasion_guidance=occasion_rules,
            color_guidance=color_guidance,

            # Behavioral (Pillar 3)
            behavioral_profile=behavioral,
            is_drifting=drift.is_drifting,
            drift_direction=drift.drift_direction,
            successful_past_recs=behavioral.successful_recommendations,

            # Query
            query=query,
            query_analysis=query_analysis,
            occasion=occasion
        )

    FUNCTION calculate_navigation_path(current, destination, trajectory,
                                       core_dimensions, core_minimums,
                                       constraints) → NavigationPath:
        """
        A* pathfinding through style space with constraints
        """
        # Calculate total distance
        total_distance = style_distance(current, destination)

        # Determine step size based on user's velocity
        IF trajectory.velocity < 0.03:  # Slow mover
            max_step = 0.2
        ELIF trajectory.velocity < 0.06:  # Moderate
            max_step = 0.3
        ELSE:  # Fast explorer
            max_step = 0.4

        # Calculate number of waypoints needed
        num_waypoints = ceil(total_distance / max_step)

        waypoints = []
        current_pos = current

        FOR i IN range(num_waypoints):
            # Calculate target for this waypoint
            progress = (i + 1) / num_waypoints
            waypoint_target = interpolate(current, destination, progress)

            # CRITICAL: Preserve core dimensions
            FOR dim IN core_dimensions:
                IF waypoint_target[dim] < core_minimums[dim]:
                    waypoint_target[dim] = core_minimums[dim]

            # Validate step size
            step_distance = style_distance(current_pos, waypoint_target)
            IF step_distance > max_step:
                waypoint_target = move_toward(current_pos, waypoint_target, max_step)

            waypoints.append({
                coordinates: waypoint_target,
                step_distance: step_distance,
                week_target: i + 1
            })

            current_pos = waypoint_target

        RETURN NavigationPath(
            current_position=current,
            destination=destination,
            waypoints=waypoints
        )
```

---

### Section 5: Navigation-Aware Agents

```
CLASS CypherBot_Navigator:
    """
    Graph-based trajectory navigator using Neo4j
    """

    FUNCTION search(nav_context: NavigationContext) → LIST[Product]:
        # Find users who successfully navigated similar paths
        similar_navigators = neo4j.query("""
            MATCH (u:User)
            WHERE u.trajectory_direction ~ $direction
              AND u.trajectory_start ~ $current_position
            MATCH (u)-[:PURCHASED]->(p:Product)
            WHERE (u)-[:REACHED_DESTINATION {success: true}]->()
            RETURN p, count(u) as navigator_count
            ORDER BY navigator_count DESC
            LIMIT 50
        """,
            direction=nav_context.trajectory.direction,
            current_position=nav_context.current_position
        )

        # Find products at waypoint coordinates
        waypoint = nav_context.path.waypoints[0]
        waypoint_products = neo4j.query("""
            MATCH (p:Product)
            WHERE p.style_coordinates.formality
                  BETWEEN $min_form AND $max_form
              AND p.price BETWEEN $budget_min AND $budget_max
              AND p.silhouette_type IN $flattering_silhouettes
            RETURN p
        """,
            min_form=waypoint.coordinates.formality - 0.15,
            max_form=waypoint.coordinates.formality + 0.15,
            budget_min=nav_context.budget.min,
            budget_max=nav_context.budget.max,
            flattering_silhouettes=nav_context.body_guidance.flattering
        )

        # Score by trajectory alignment
        FOR product IN waypoint_products:
            product.trajectory_alignment = compute_alignment(
                product.style_coordinates,
                nav_context.trajectory.direction
            )
            product.waypoint_distance = style_distance(
                product.style_coordinates,
                waypoint.coordinates
            )
            product.similar_navigator_count = count_in(product, similar_navigators)

        RETURN sorted(waypoint_products,
                     key=lambda p: p.trajectory_alignment * 0.4
                                 + (1 - p.waypoint_distance) * 0.4
                                 + p.similar_navigator_count * 0.2)[:20]


CLASS VibeBot_Navigator:
    """
    Semantic navigator using vector embeddings
    """

    FUNCTION search(nav_context: NavigationContext) → LIST[Product]:
        # Build semantic query incorporating navigation context
        semantic_query = build_navigation_aware_query(
            base_query=nav_context.query,
            current_style=describe_position(nav_context.current_position),
            target_style=describe_position(nav_context.destination),
            styling_rules=nav_context.styling_rules,
            body_guidance=nav_context.body_guidance
        )

        # Generate embedding
        query_embedding = openai.embed(semantic_query)

        # Search with navigation-aware filters
        results = qdrant.search(
            collection="fashion_products",
            query_vector=query_embedding,
            filter={
                "price": {"$gte": nav_context.budget.min,
                         "$lte": nav_context.budget.max},
                "formality": {"$gte": nav_context.path.waypoints[0].formality - 0.2,
                             "$lte": nav_context.path.waypoints[0].formality + 0.2}
            },
            limit=50
        )

        # Re-rank by semantic alignment with trajectory
        FOR product IN results:
            # Check semantic distance from current position
            current_sim = cosine_similarity(
                product.embeddings.siglip_text,
                embed_position(nav_context.current_position)
            )

            # Check semantic alignment with destination
            dest_sim = cosine_similarity(
                product.embeddings.siglip_text,
                embed_position(nav_context.destination)
            )

            # Prefer products that bridge current → destination
            product.semantic_bridge_score = (current_sim * 0.3 + dest_sim * 0.7)

        RETURN sorted(results, key=lambda p: p.semantic_bridge_score)[:20]


CLASS VisionBot_Navigator:
    """
    Visual navigator using image embeddings + deterministic features
    """

    FUNCTION search(nav_context: NavigationContext) → LIST[Product]:
        # Build visual target from waypoint coordinates
        waypoint = nav_context.path.waypoints[0]

        # Generate target visual embedding
        visual_query = generate_visual_target(
            target_formality=waypoint.coordinates.formality,
            target_color_warmth=waypoint.coordinates.color_warmth,
            target_texture=waypoint.coordinates.texture,
            user_color_preferences=nav_context.behavioral_profile.preferred_colors
        )

        # Search by visual similarity
        visual_results = qdrant.search(
            collection="fashion_multimodal_embeddings",
            query_vector=visual_query,
            limit=50
        )

        # Apply deterministic filters (body type + color harmony)
        filtered = []
        FOR product IN visual_results:
            # Check silhouette against body type rules
            IF product.deterministic.silhouette_type IN nav_context.body_guidance.flattering:
                # Check color harmony with user's wardrobe
                harmony = check_harmony_with_existing(
                    product.deterministic.dominant_colors,
                    nav_context.behavioral_profile.wardrobe_colors
                )

                IF harmony.is_harmonic OR harmony.score > 0.6:
                    product.visual_harmony_score = harmony.score
                    product.body_type_match = TRUE
                    filtered.append(product)

        # Score by visual continuity with trajectory
        FOR product IN filtered:
            # Visual distance from current position
            current_dist = visual_distance(
                product.embeddings.siglip_vision,
                embed_visual_position(nav_context.current_position)
            )

            # Check visual progression is smooth
            product.visual_continuity = 1.0 if current_dist <= 0.3 else (1.0 - current_dist)

        RETURN sorted(filtered,
                     key=lambda p: p.visual_continuity * 0.5
                                 + p.visual_harmony_score * 0.3
                                 + p.body_type_match * 0.2)[:20]


CLASS JudgeAri_PathEvaluator:
    """
    Evaluates path quality and selects best products
    """

    FUNCTION evaluate_and_select(
        cypher_results: LIST[Product],
        vibe_results: LIST[Product],
        vision_results: LIST[Product],
        nav_context: NavigationContext
    ) → LIST[Product]:

        # Merge all results
        all_products = deduplicate(cypher_results + vibe_results + vision_results)

        # Score each product on path quality dimensions
        FOR product IN all_products:
            scores = {}

            # 1. SMOOTHNESS: Is this a reasonable step from current position?
            step_distance = style_distance(
                nav_context.current_position,
                product.style_coordinates
            )
            scores.smoothness = 1.0 if step_distance <= 0.3 else (1.0 - step_distance)

            # 2. COHERENCE: Does this align with user's trajectory?
            trajectory_dot = dot_product(
                nav_context.trajectory.direction,
                product.style_coordinates - nav_context.current_position
            )
            scores.coherence = max(0, trajectory_dot)  # Positive = aligned

            # 3. ACHIEVABILITY: Budget + availability
            IF product.price <= nav_context.budget.max:
                scores.achievability = 1.0 - (product.price / nav_context.budget.max) * 0.5
            ELSE:
                scores.achievability = 0.0

            # 4. AUTHENTICITY: Preserves core dimensions
            authenticity_violations = 0
            FOR dim IN nav_context.core_dimensions:
                IF product.style_coordinates[dim] < nav_context.core_minimums[dim]:
                    authenticity_violations += 1
            scores.authenticity = 1.0 - (authenticity_violations / len(nav_context.core_dimensions))

            # 5. MULTI-BOT CONFIDENCE: Found by multiple agents
            in_cypher = product IN cypher_results
            in_vibe = product IN vibe_results
            in_vision = product IN vision_results
            bot_count = sum([in_cypher, in_vibe, in_vision])
            scores.multi_bot = 0.6 + (bot_count - 1) * 0.2  # 0.6, 0.8, or 1.0

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
                scores.coherence * 0.20 +
                scores.achievability * 0.10 +
                scores.authenticity * 0.25 +
                scores.multi_bot * 0.10 +
                scores.rule_compliance * 0.15
            )

        # Filter out products that fail authenticity
        valid = [p for p in all_products if p.scores.authenticity >= 0.7]

        # Return top products
        RETURN sorted(valid, key=lambda p: p.path_quality_score, reverse=TRUE)[:limit]
```

---

### Section 6: Main Orchestration Flow

```
CLASS NavigationOrchestrator:
    """
    Main entry point - replaces the old ML Intelligence layer
    """

    navigation_intelligence: NavigationIntelligence
    agents: {
        cypher: CypherBot_Navigator,
        vibe: VibeBot_Navigator,
        vision: VisionBot_Navigator,
        judge: JudgeAri_PathEvaluator
    }

    ASYNC FUNCTION execute_search(
        user_id: STRING,
        query: STRING,
        occasion: STRING = None,
        limit: INT = 10
    ) → SearchResult:

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Generate Navigation Context (3 Pillars + All Features)
        # ═══════════════════════════════════════════════════════════════════

        nav_context = await navigation_intelligence.generate_navigation_context(
            user_id=user_id,
            query=query,
            occasion=occasion
        )

        # Log navigation state
        log.info(f"""
            Navigation Context Generated:
            - Current Position: {describe_position(nav_context.current_position)}
            - Trajectory: {nav_context.trajectory.direction} @ {nav_context.trajectory.velocity}/week
            - Destination: {describe_position(nav_context.destination)}
            - Waypoints: {len(nav_context.path.waypoints)}
            - Styling Rules Retrieved: {len(nav_context.styling_rules)}
            - Body Guidance: {nav_context.body_guidance.flattering_silhouettes}
        """)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Parallel Agent Execution
        # ═══════════════════════════════════════════════════════════════════

        PARALLEL:
            cypher_results = await agents.cypher.search(nav_context)
            vibe_results = await agents.vibe.search(nav_context)
            vision_results = await agents.vision.search(nav_context)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Judge Evaluation with Path Quality
        # ═══════════════════════════════════════════════════════════════════

        final_products = await agents.judge.evaluate_and_select(
            cypher_results=cypher_results,
            vibe_results=vibe_results,
            vision_results=vision_results,
            nav_context=nav_context
        )[:limit]

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Generate Navigation Explanation
        # ═══════════════════════════════════════════════════════════════════

        explanation = generate_navigation_explanation(
            current=nav_context.current_position,
            destination=nav_context.destination,
            products=final_products,
            styling_rules=nav_context.styling_rules,
            body_guidance=nav_context.body_guidance
        )

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: Track Interaction for Learning
        # ═══════════════════════════════════════════════════════════════════

        await track_recommendation_session(
            user_id=user_id,
            nav_context=nav_context,
            products_shown=final_products,
            cypher_contribution=len(set(final_products) & set(cypher_results)),
            vibe_contribution=len(set(final_products) & set(vibe_results)),
            vision_contribution=len(set(final_products) & set(vision_results))
        )

        RETURN SearchResult(
            products=final_products,
            navigation_explanation=explanation,
            path=nav_context.path,
            metadata={
                "current_position": nav_context.current_position,
                "destination": nav_context.destination,
                "trajectory_velocity": nav_context.trajectory.velocity,
                "styling_rules_applied": len(nav_context.styling_rules),
                "body_type_filtering": TRUE,
                "color_harmony_applied": TRUE
            }
        )

    FUNCTION generate_navigation_explanation(current, destination, products,
                                             styling_rules, body_guidance) → STRING:
        """
        Generate natural language explanation of navigation
        (NOT just product list, but WHY these products for THIS user)
        """
        RETURN f"""
        You're currently at {describe_position(current)}, which reflects your
        {extract_dominant_traits(current)} aesthetic.

        For {destination_occasion}, we're navigating toward
        {describe_position(destination)}.

        Based on your {body_guidance.body_type} body type, I've selected pieces with
        {body_guidance.flattering_silhouettes} silhouettes that will flatter your shape.

        Here's your path:

        {FOR product IN products:}
        - {product.title} ({product.price})
          - Style distance: {product.step_distance:.2f} (comfortable step)
          - Why: {explain_product_selection(product, styling_rules, body_guidance)}
          - Harmony: {product.color_harmony_note}
        {ENDFOR}

        These pieces maintain your core {current.core_dimensions} aesthetic
        while moving you {trajectory.distance:.1f} units toward your destination.
        """
```

---

### Section 7: Knowledge Base Population (One-Time Setup)

```
FUNCTION populate_stylist_knowledge_base():
    """
    Load textbook styling knowledge into vector store for RAG
    """

    knowledge_chunks = []

    # COLOR THEORY
    knowledge_chunks.extend([
        "Complementary colors (opposite on wheel) create high contrast and energy",
        "Analogous colors (adjacent on wheel) create harmony and cohesion",
        "Triadic colors (equidistant on wheel) create balanced vibrancy",
        "Warm colors (red, orange, yellow) advance and add energy",
        "Cool colors (blue, green, purple) recede and add calm",
        "Neutral colors (black, white, grey, beige) balance bold choices",
        ...
    ])

    # BODY TYPE RULES
    FOR body_type IN ["pear", "apple", "hourglass", "rectangle", "inverted_triangle"]:
        knowledge_chunks.extend([
            f"{body_type} body type: {BODY_TYPE_DESCRIPTIONS[body_type]}",
            f"Flattering silhouettes for {body_type}: {FLATTERING_SILHOUETTES[body_type]}",
            f"Avoid for {body_type}: {AVOID_SILHOUETTES[body_type]}",
            f"Necklines for {body_type}: {NECKLINE_GUIDANCE[body_type]}",
            ...
        ])

    # OCCASION RULES
    FOR occasion IN ["wedding", "interview", "casual", "date_night", "business"]:
        knowledge_chunks.extend([
            f"{occasion}: Formality level {FORMALITY_LEVELS[occasion]}/10",
            f"{occasion}: Appropriate dress codes: {DRESS_CODES[occasion]}",
            f"{occasion}: Fabric recommendations: {FABRICS[occasion]}",
            f"{occasion}: Colors to consider: {COLORS[occasion]}",
            ...
        ])

    # SILHOUETTE SCIENCE
    knowledge_chunks.extend([
        "A-line silhouette: Fitted at waist, flares outward, flatters most body types",
        "Bodycon silhouette: Tight-fitting, emphasizes curves, best for confidence",
        "Empire waist: High waistline under bust, elongates torso, hides midsection",
        "Wrap dress: Creates V-neckline, defines waist, universally flattering",
        ...
    ])

    # PROPORTION RULES
    knowledge_chunks.extend([
        "Golden ratio 1:1.618 creates visual harmony in outfit proportions",
        "Rule of thirds: Divide outfit into unequal portions (1/3 top, 2/3 bottom)",
        "High-waisted bottoms elongate legs and shorten torso visually",
        "Cropped tops balance wide-leg pants",
        ...
    ])

    # Embed and store all chunks
    FOR chunk IN knowledge_chunks:
        embedding = openai.embed(chunk)
        knowledge_base.upsert(
            id=hash(chunk),
            vector=embedding,
            metadata={
                "text": chunk,
                "category": extract_category(chunk)
            }
        )
```

---

### Section 8: Batch Processing for Product Catalog

```
ASYNC FUNCTION batch_process_products():
    """
    Process all 6.4M products to extract features and compute style coordinates
    """

    batch_size = 100
    products = neo4j.query("MATCH (p:Product) RETURN p.id, p.images[0] as image")

    FOR batch IN chunks(products, batch_size):
        PARALLEL FOR product IN batch:
            TRY:
                # Extract all features
                representation = feature_extractor.extract_all_features(
                    image_url=product.image,
                    category=infer_category(product)
                )

                # Update Neo4j with computed features
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

                # Update Qdrant with embeddings
                qdrant.upsert(
                    collection="fashion_multimodal_embeddings",
                    points=[{
                        id=product.id,
                        vector=representation.embeddings.siglip_multimodal,
                        payload={
                            "style_coordinates": representation.style_coordinates,
                            "deterministic": representation.deterministic
                        }
                    }]
                )

            CATCH Exception as e:
                log.error(f"Failed to process {product.id}: {e}")
                continue

        # Rate limiting
        await sleep(1.0)
```

---

## Key Architectural Changes

| Current System | Navigation Intelligence |
|----------------|------------------------|
| ML Intelligence Layer (simple prompts) | 3-Pillar RAG System |
| GPT with context injection | Stylist knowledge base + personalization + behavioral |
| Basic embedding search | Multi-modal: Embeddings + Deterministic features |
| Agent-based results | Path-quality-scored navigation |
| "Here are similar products" | "Here's your next waypoint toward your style destination" |

---

## Implementation Priority

### Phase 1: Core Infrastructure
1. Implement `StyleCoordinate` and `DeterministicFeatures` data structures
2. Build `FeatureExtractor` with SAM3 + color science + shape analysis
3. Create stylist knowledge base vector store

### Phase 2: Navigation Engine
1. Implement `Pillar1_Personalization` with Neo4j User Graph integration
2. Implement `Pillar2_StylistKnowledge` RAG system
3. Implement `Pillar3_UserActivity` behavioral tracking
4. Build `NavigationIntelligence.calculate_navigation_path()`

### Phase 3: Agent Refactoring
1. Refactor `CypherBot` → `CypherBot_Navigator`
2. Refactor `VibeBot` → `VibeBot_Navigator`
3. Refactor `VisionBot` → `VisionBot_Navigator`
4. Refactor `JudgeAri` → `JudgeAri_PathEvaluator`

### Phase 4: Orchestration & Batch Processing
1. Build `NavigationOrchestrator.execute_search()`
2. Implement `generate_navigation_explanation()`
3. Run `batch_process_products()` on 6.4M catalog

---

**Document Version:** 1.0
**Status:** Design Specification - Ready for Implementation
