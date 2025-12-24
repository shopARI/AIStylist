# ARI Navigation Intelligence — Formal Specification

## 1. Core Data Structures

```
User U = {
    style_position: Vector[7],      // Current location in style space
    preferences: Set[Attribute],    // Learned from behavior
    constraints: Set[Rule],         // Budget, size, non-negotiables
    history: Sequence[Interaction]  // What user has done
}

Product P = {
    embeddings: {
        visual: Vector[1024],       // What it looks like
        semantic: Vector[1536],     // What it means
        fashion: Vector[1024]       // Fashion-specific features
    },
    features: {
        colors: List[RGB],          // Extracted via segmentation
        harmony: Float,             // Color harmony score
        texture: Category,          // Smooth, rough, patterned, etc.
        silhouette: Category        // Fitted, relaxed, structured, etc.
    }
}
```

## 2. Style Space Navigation

```
FUNCTION compute_style_position(user) → Vector[7]:
    dimensions = [
        form,              // structured ←→ fluid
        color_warmth,      // cool ←→ warm
        color_saturation,  // muted ←→ vibrant
        texture,           // smooth ←→ rough
        pattern,           // minimal ←→ maximalist
        formality,         // casual ←→ formal
        proportion         // fitted ←→ oversized
    ]

    FOR each dimension d:
        position[d] = weighted_average(
            user.history.filter(positive_interactions),
            weights = recency_decay(λ = 0.9)
        )

    RETURN normalize(position)
```

## 3. Navigation Direction

```
FUNCTION compute_navigation(user, request, occasion) → Direction:

    current = user.style_position

    destination = infer_destination(
        explicit = parse(request),
        implicit = occasion_defaults(occasion),
        trajectory = user.style_evolution_trend
    )

    direction = destination - current

    // Limit step size to comfortable range
    IF magnitude(direction) > user.comfort_threshold:
        direction = normalize(direction) × user.comfort_threshold

    RETURN direction
```

## 4. Path Quality Scoring

```
FUNCTION score_product(product, user, direction) → Float:

    // Factor 1: SMOOTHNESS — Is this a reasonable step?
    step_distance = style_distance(user.position, product.position)
    smoothness = 1.0 if step_distance ≤ 0.3 else (1.0 - step_distance)

    // Factor 2: COHERENCE — Does this align with trajectory?
    coherence = dot_product(user.trajectory, product.position - user.position)
    coherence = clamp(coherence, 0.0, 1.0)  // Normalize to [0,1]

    // Factor 3: ACHIEVABILITY — Budget + availability
    achievability = 1.0 if product.price ≤ user.budget.max else 0.0

    // Factor 4: AUTHENTICITY — Preserves core style values
    violations = count(product violates user.core_dimensions)
    authenticity = 1.0 - (violations / total_core_dimensions)

    // Factor 5: MULTI-BOT — Found by multiple search agents
    bot_count = count(agents that found this product)
    multi_bot = 0.6 + (bot_count - 1) × 0.2

    // Factor 6: RULE COMPLIANCE — Follows styling rules
    rule_compliance = evaluate(
        color_harmony(product, user),
        body_flattery(product.silhouette, user.body_type),
        occasion_fit(product, user.occasion)
    )

    // Weighted combination
    RETURN (
        0.20 × smoothness +
        0.20 × coherence +
        0.10 × achievability +
        0.25 × authenticity +
        0.10 × multi_bot +
        0.15 × rule_compliance
    )
```

## 5. Product Retrieval (Four Agents)

```
FUNCTION find_products(user, direction, k=20) → List[Product]:

    // Run three search agents in parallel
    candidates = UNION(
        // CypherBot: Graph-based trajectory navigation
        CypherBot.search(user.trajectory, similar_navigators),

        // VibeBot: Semantic/vector similarity
        VibeBot.search(user.request_embedding, top_n=100),

        // VisionBot: Visual + deterministic features
        VisionBot.search(user.style_position + direction, top_n=100)
    )

    // JudgeAri: Evaluate path quality and select best
    FOR each product in candidates:
        product.score = JudgeAri.evaluate(product, user, direction)

    // Filter by constraints
    valid = candidates.filter(
        meets_budget(user.budget),
        meets_size(user.size),
        not_in(user.rejected_items),
        authenticity ≥ 0.7  // Must preserve core identity
    )

    RETURN JudgeAri.select_top_k(valid, k=k)
```

## 6. Recommendation with Explanation

```
FUNCTION recommend(user, request) → Response:

    direction = compute_navigation(user, request, context.occasion)
    products = find_products(user, direction)

    FOR each product in products:
        product.explanation = generate_explanation(
            why_fits_you = personalization_reasons(product, user),
            why_looks_good = styling_rules_applied(product),
            why_now = navigation_progress(product, direction)
        )

    RETURN {
        products: products,
        navigation_summary: describe_journey(user.position, direction),
        next_steps: suggest_complementary(products)
    }
```

## 7. Learning Loop

```
ON user_interaction(user, product, action):

    IF action IN {purchase, save, like}:
        // Positive signal — move toward this style
        user.style_position = lerp(
            user.style_position,
            product.style_position,
            learning_rate = 0.1
        )

    ELSE IF action IN {skip, reject, return}:
        // Negative signal — note avoidance
        user.constraints.add(infer_dislike(product))

    // Update embeddings
    user.preference_embedding = recompute(user.history)
```

## Summary

```
INPUT:  User profile + Request + Context
OUTPUT: Ranked products + Personalized explanations

AGENTS:
    CypherBot  → Graph-based trajectory navigation (Neo4j)
    VibeBot    → Semantic vector similarity (Qdrant)
    VisionBot  → Visual + deterministic features (SAM3, color, texture)
    JudgeAri   → Path quality evaluation and final selection

PROCESS:
    1. Locate user in style space (7 dimensions)
    2. Compute direction toward request destination
    3. Search via 3 parallel agents (CypherBot, VibeBot, VisionBot)
    4. Score by 6 factors (smoothness, coherence, achievability,
                          authenticity, multi-bot, rule compliance)
    5. JudgeAri selects and explains each recommendation
    6. Learn from user response (update position)
```
