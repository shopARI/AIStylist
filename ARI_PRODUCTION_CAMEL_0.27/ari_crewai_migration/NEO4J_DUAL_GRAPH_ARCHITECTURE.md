# Neo4j Dual Graph Architecture
## Separation of User Ontology and Product Ontology

---

## Architecture Overview

**Two Separate Graphs:**
1. **User Graph** - User profiles, preferences, onboarding, conversation history, interactions
2. **Product Graph** - Product catalog, brands, categories, styles, visual embeddings

**Benefits of Separation:**
- Independent scaling (product catalog can grow without affecting user data performance)
- Different query patterns and optimization strategies
- Clearer data ownership and access control
- Separate backup/restore strategies
- Different retention policies

**Cross-Graph References:**
- User preferences reference Product graph entities via IDs
- Product interactions bridge both graphs
- Separate databases or same database with clear naming conventions

---

# GRAPH 1: USER ONTOLOGY

## Purpose
Store user identity, preferences, onboarding history, conversation patterns, and interaction history.

## Nodes (14 Total)

### 1. User
**Description:** Core user entity - central hub
**Properties:**
```json
{
  "user_id": "uuid (primary key)",
  "username": "string",
  "email": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "last_active": "datetime",
  "onboarding_completed": "boolean",
  "onboarding_completed_at": "datetime",
  "onboarding_version": "string"
}
```

---

### 2. PersonalIdentity
**Description:** Who the user is - demographic and life context
**Properties:**
```json
{
  "age": "integer",
  "location_city": "string",
  "location_region": "string",
  "location_type": "string (urban/suburban/rural)",
  "occupation": "string",
  "occupation_industry": "string",
  "typical_occasions": "json",
  "gender_identity": "string",
  "ethnicity": "string",
  "relationship_status": "string",
  "parental_status": "json",
  "sexuality": "string",
  "income_level": "string",
  "education": "string",
  "religious_cultural_background": "json"
}
```

---

### 3. TasteProfile
**Description:** Aesthetic preferences and style identity
**Properties:**
```json
{
  "gender_expression": "json",
  "brand_preferences": "json (brand IDs + preference strength)",
  "shape_preferences": "json",
  "fit_preferences": "json",
  "style_loves": "string",
  "style_wants": "string",
  "style_avoids": "string",
  "occasion_styles": "json",
  "style_icons": "json",
  "style_evolution_notes": "text (PROPOSED)",
  "inspiration_sources": "string[] (PROPOSED)",
  "style_confidence": "float 0-1 (PROPOSED)",
  "openness_to_new_styles": "float 0-1 (PROPOSED)"
}
```

---

### 4. ProcessProfile
**Description:** How they make decisions and shop
**Properties:**
```json
{
  "style_motivations": "json",
  "creative_control": "integer 1-10",
  "style_goals": "string",
  "brand_loyalty": "integer 1-10",
  "style_adventurousness": "integer 1-10",
  "validation_sources": "json",
  "exploration_style": "string",
  "social_influences": "json",
  "ideal_process_description": "text (PROPOSED)",
  "pain_points": "string[] (PROPOSED)",
  "decision_speed": "enum[quick, moderate, deliberate] (PROPOSED)",
  "returns_frequency": "enum[rarely, sometimes, often] (PROPOSED)"
}
```

---

### 5. PracticalityProfile
**Description:** Budget and practical constraints
**Properties:**
```json
{
  "monthly_budget_min": "float",
  "monthly_budget_max": "float",
  "yearly_budget": "float",
  "budget_flexibility": "string",
  "category_budgets": "json (category ID → budget)",
  "investment_philosophy": "text (PROPOSED)",
  "budget_flexibility_triggers": "text (PROPOSED)",
  "value_priorities_ranking": "string[] (PROPOSED)"
}
```

---

### 6. BodyData
**Description:** Physical attributes and visual data
**Properties:**
```json
{
  "face_photo_id": "string",
  "face_photo_url": "string",
  "body_photo_id": "string",
  "body_photo_url": "string",
  "coloring_verbal": "string",
  "body_verbal": "string",
  "body_insecurities": "json",
  "favorite_features": "json",
  "captured_at": "datetime",
  "fit_challenges": "string[] (PROPOSED)",
  "ideal_silhouettes": "string[] (PROPOSED)",
  "comfort_requirements": "text (PROPOSED)"
}
```

---

### 7. SocialMediaProfile
**Description:** Connected social media accounts
**Properties:**
```json
{
  "instagram_handle": "string",
  "instagram_connected_at": "datetime",
  "pinterest_handle": "string",
  "pinterest_connected_at": "datetime",
  "tiktok_handle": "string",
  "tiktok_connected_at": "datetime"
}
```

---

### 8. RootValue
**Description:** Core values discovered during onboarding
**Properties:**
```json
{
  "value_id": "uuid",
  "value": "string (e.g., 'sustainability', 'self-expression')",
  "source_node": "string (which node discovered this)",
  "discovered_at": "datetime",
  "confidence": "float 0-1"
}
```

---

### 9. OnboardingMetadata
**Description:** Metadata about the onboarding session
**Properties:**
```json
{
  "total_skip_count": "integer",
  "skip_counts_by_node": "json",
  "completion_time_minutes": "integer",
  "tiers_completed": "json",
  "started_at": "datetime",
  "completed_at": "datetime",
  "conversation_quality_score": "float 0-1"
}
```

---

### 10. OnboardingDataNode
**Description:** Raw data from each onboarding node
**Properties:**
```json
{
  "node_id": "string",
  "tier": "string",
  "data": "json",
  "completed_at": "datetime",
  "skip_count": "integer"
}
```

---

### 11. UserOccasion (PROPOSED)
**Description:** User-specific occasions they need outfits for
**Properties:**
```json
{
  "occasion_id": "uuid",
  "occasion_type": "enum[wedding, interview, date, casual, work, party, travel, custom]",
  "name": "string (e.g., 'Sarah's wedding', 'park with Max')",
  "formality_level": "enum[very_formal, formal, business_casual, casual, very_casual]",
  "mentioned_count": "integer",
  "context": "text",
  "date": "datetime (if specified)",
  "status": "enum[upcoming, recurring, past, hypothetical]",
  "created_from": "enum[onboarding, chat, explicit_add]"
}
```

---

### 12. ConversationPattern (PROPOSED)
**Description:** Patterns identified during conversations
**Properties:**
```json
{
  "pattern_id": "uuid",
  "pattern_type": "enum[repeated_mention, value_signal, contradiction, strong_preference, avoidance]",
  "topic": "string (e.g., 'sustainability', 'comfort')",
  "evidence": "text[] (quotes from conversation)",
  "frequency": "integer",
  "confidence": "float 0-1",
  "inferred_value": "string (RootValue this suggests)"
}
```

---

### 13. UserVisualEmbedding (PROPOSED)
**Description:** Visual embeddings from user's body/face photos
**Properties:**
```json
{
  "embedding_id": "uuid",
  "embedding_vector": "float[] (FashionSigLIP embedding)",
  "source": "enum[body_photo, face_photo]",
  "analysis": "json {colors, patterns, visual_features detected}",
  "timestamp": "datetime"
}
```

---

### 14. UserProductInteraction (PROPOSED)
**Description:** User interactions with products (bridge to Product graph)
**Properties:**
```json
{
  "interaction_id": "uuid",
  "product_id": "string (reference to Product graph)",
  "interaction_type": "enum[recommended, viewed, liked, purchased, rejected, saved]",
  "timestamp": "datetime",
  "context": "string (occasion, search query)",
  "recommended_by_agent": "enum[judge_ari, cypher_bot, vibe_bot, vision_bot]",
  "user_feedback": "text (optional explicit feedback)",
  "implicit_score": "float (derived from interaction type)"
}
```

---

### 15. RecommendationSession (PROPOSED)
**Description:** Agent recommendation sessions and judgments
**Properties:**
```json
{
  "session_id": "uuid",
  "timestamp": "datetime",
  "occasion_context": "string (UserOccasion ID)",
  "cypher_bot_recommendations": "string[] (Product IDs)",
  "vibe_bot_recommendations": "string[] (Product IDs)",
  "vision_bot_recommendations": "string[] (Product IDs)",
  "final_selections": "string[] (Product IDs chosen by Judge Ari)",
  "reasoning": "text",
  "quality_scores": "json {product_id: score}",
  "user_feedback": "enum[accepted, rejected, modified, pending]"
}
```

---

### 16. UserOutfit (PROPOSED)
**Description:** User's saved/created outfit combinations
**Properties:**
```json
{
  "outfit_id": "uuid",
  "name": "string",
  "occasion_id": "string (UserOccasion ID)",
  "product_ids": "string[] (references to Product graph)",
  "created_by": "enum[judge_ari, user, stylist]",
  "style_description": "text",
  "completeness_score": "float 0-1",
  "harmony_score": "float 0-1",
  "user_rating": "float 1-5",
  "worn": "boolean",
  "worn_date": "datetime",
  "created_at": "datetime"
}
```

---

## User Graph Relationships (23 Total)

### Core Profile Relationships

1. **User → PersonalIdentity** (HAS_PERSONAL_IDENTITY)
   - Properties: created_at, updated_at

2. **User → TasteProfile** (HAS_TASTE_PROFILE)
   - Properties: created_at, updated_at

3. **User → ProcessProfile** (HAS_PROCESS_PROFILE)
   - Properties: created_at, updated_at

4. **User → PracticalityProfile** (HAS_PRACTICALITY_PROFILE)
   - Properties: created_at, updated_at

5. **User → BodyData** (HAS_BODY_DATA)
   - Properties: created_at, updated_at

6. **User → SocialMediaProfile** (HAS_SOCIAL_MEDIA)
   - Properties: created_at, updated_at

7. **User → RootValue** (HAS_ROOT_VALUE)
   - Properties: discovered_at, strength

8. **User → OnboardingMetadata** (HAS_ONBOARDING_METADATA)
   - Properties: created_at

9. **User → OnboardingDataNode** (HAS_DATA_NODE)
   - Properties: created_at

### Cross-Node Value Relationships

10. **[PersonalIdentity, TasteProfile, ProcessProfile] → RootValue** (RELATES_TO_VALUE)
    - Properties: connection_strength

11. **ConversationPattern → RootValue** (SUGGESTS_VALUE)
    - Properties: confidence

### Occasion & Pattern Relationships (PROPOSED)

12. **User → UserOccasion** (MENTIONED_OCCASION)
    - Properties: mention_count, first_mentioned, last_mentioned, importance_score

13. **User → ConversationPattern** (HAS_PATTERN)
    - Properties: identified_at

### Visual Data Relationships (PROPOSED)

14. **BodyData → UserVisualEmbedding** (HAS_VISUAL_EMBEDDING)
    - Properties: created_at

### Product Interaction Relationships (PROPOSED)

15. **User → UserProductInteraction** (INTERACTED_WITH)
    - Properties: timestamp

16. **User → RecommendationSession** (HAD_SESSION)
    - Properties: timestamp

17. **RecommendationSession → UserOccasion** (FOR_OCCASION)
    - Links session to occasion context

### Outfit Relationships (PROPOSED)

18. **User → UserOutfit** (HAS_OUTFIT)
    - Properties: created_at, updated_at

19. **UserOutfit → UserOccasion** (FOR_OCCASION)
    - Links outfit to occasion

### Preference Reference Relationships (to Product Graph) (PROPOSED)

20. **User → Brand** (PREFERS_BRAND)
    - Properties: preference_strength, mention_count, confidence
    - **CROSS-GRAPH**: Brand exists in Product graph

21. **User → Brand** (AVOIDS_BRAND)
    - Properties: reason, mention_count
    - **CROSS-GRAPH**: Brand exists in Product graph

22. **User → Category** (PREFERS_CATEGORY)
    - Properties: preference_score, for_occasions, context
    - **CROSS-GRAPH**: Category exists in Product graph

23. **User → Category** (AVOIDS_CATEGORY)
    - Properties: reason
    - **CROSS-GRAPH**: Category exists in Product graph

24. **User → StyleDescriptor** (EXHIBITS_STYLE)
    - Properties: confidence, source, occasions, mention_count
    - **CROSS-GRAPH**: StyleDescriptor exists in Product graph

---

## User Graph Indexes

```cypher
// User indexes
CREATE INDEX user_id_idx FOR (u:User) ON (u.user_id);
CREATE INDEX user_email_idx FOR (u:User) ON (u.email);
CREATE INDEX user_username_idx FOR (u:User) ON (u.username);

// Occasion indexes
CREATE INDEX occasion_type_idx FOR (o:UserOccasion) ON (o.occasion_type);
CREATE INDEX occasion_status_idx FOR (o:UserOccasion) ON (o.status);
CREATE INDEX occasion_date_idx FOR (o:UserOccasion) ON (o.date);

// Pattern indexes
CREATE INDEX pattern_topic_idx FOR (p:ConversationPattern) ON (p.topic);
CREATE INDEX pattern_type_idx FOR (p:ConversationPattern) ON (p.pattern_type);

// Root value indexes
CREATE INDEX root_value_idx FOR (rv:RootValue) ON (rv.value);

// Interaction indexes
CREATE INDEX interaction_type_idx FOR (i:UserProductInteraction) ON (i.interaction_type);
CREATE INDEX interaction_timestamp_idx FOR (i:UserProductInteraction) ON (i.timestamp);
CREATE INDEX interaction_product_idx FOR (i:UserProductInteraction) ON (i.product_id);

// Session indexes
CREATE INDEX session_timestamp_idx FOR (s:RecommendationSession) ON (s.timestamp);

// Fulltext search
CREATE FULLTEXT INDEX occasion_search FOR (o:UserOccasion) ON EACH [o.name, o.context];
CREATE FULLTEXT INDEX pattern_search FOR (p:ConversationPattern) ON EACH [p.topic, p.evidence];
```

---

# GRAPH 2: PRODUCT ONTOLOGY

## Purpose
Store product catalog, brand/category hierarchies, style taxonomies, and visual embeddings for recommendations.

## Nodes (7 Total)

### 1. Product
**Description:** Core product entity from 6.4M catalog
**Properties:**
```json
{
  "product_id": "string (primary key)",
  "name": "string",
  "brand_id": "string (reference to Brand)",
  "category_id": "string (reference to Category)",
  "price": "float",
  "currency": "string",
  "image_url": "string",
  "image_urls": "string[] (multiple angles)",
  "description": "text",
  "color": "string",
  "colors": "string[] (if multi-color)",
  "size_options": "string[]",
  "material": "string",
  "pattern": "string",
  "season": "string",
  "gender_target": "string",
  "availability": "enum[in_stock, out_of_stock, limited, pre_order]",
  "popularity_score": "float",
  "quality_indicators": "json",
  "retailer": "string",
  "retailer_url": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### 2. Brand
**Description:** Fashion brands
**Properties:**
```json
{
  "brand_id": "uuid",
  "name": "string",
  "price_tier": "enum[luxury, premium, mid, affordable, budget]",
  "aesthetic": "string[] (e.g., ['boho', 'minimalist', 'edgy'])",
  "country_of_origin": "string",
  "sustainability_rating": "float 0-10",
  "popularity_score": "float",
  "description": "text",
  "logo_url": "string",
  "website": "string"
}
```

---

### 3. Category
**Description:** Product categories and hierarchy
**Properties:**
```json
{
  "category_id": "uuid",
  "name": "string (e.g., 'dresses', 'blazers', 'sneakers')",
  "parent_category_id": "string (e.g., reference to 'tops', 'bottoms', 'shoes')",
  "level": "integer (1=top level, 2=subcategory, etc.)",
  "description": "text",
  "typical_occasions": "string[] (occasions this category suits)"
}
```

**Example Hierarchy:**
```
Level 1: Clothing → Level 2: Tops → Level 3: Blouses → Level 4: Silk Blouses
Level 1: Clothing → Level 2: Bottoms → Level 3: Pants → Level 4: Jeans
Level 1: Shoes → Level 2: Sneakers → Level 3: High-top Sneakers
Level 1: Accessories → Level 2: Bags → Level 3: Clutches
```

---

### 4. StyleDescriptor
**Description:** Style and aesthetic descriptors
**Properties:**
```json
{
  "descriptor_id": "uuid",
  "term": "string (e.g., 'boho chic', 'minimalist', 'preppy')",
  "category": "enum[aesthetic, vibe, mood, trend, era]",
  "description": "text",
  "color_palette": "string[] (associated colors)",
  "pattern_types": "string[] (associated patterns)",
  "typical_silhouettes": "string[]",
  "formality_level": "enum[very_formal, formal, business_casual, casual, very_casual]",
  "seasonal_relevance": "string[] (spring, summer, fall, winter)"
}
```

---

### 5. ProductVisualEmbedding
**Description:** Visual embeddings for product images
**Properties:**
```json
{
  "embedding_id": "uuid",
  "product_id": "string (reference to Product)",
  "embedding_vector": "float[] (FashionSigLIP embedding)",
  "image_angle": "enum[front, back, side, detail, styled]",
  "analysis": "json {dominant_colors, patterns, silhouette, texture}",
  "timestamp": "datetime"
}
```

---

### 6. OccasionType
**Description:** Generic occasion types for product tagging
**Properties:**
```json
{
  "occasion_type_id": "uuid",
  "name": "string (e.g., 'wedding', 'interview', 'casual')",
  "formality_level": "enum[very_formal, formal, business_casual, casual, very_casual]",
  "description": "text",
  "typical_dress_codes": "string[]",
  "seasonal_considerations": "text"
}
```

---

### 7. StylingRule
**Description:** Fashion rules and outfit guidelines
**Properties:**
```json
{
  "rule_id": "uuid",
  "rule_type": "enum[color_harmony, pattern_mixing, proportion, occasion_appropriateness]",
  "description": "text",
  "confidence": "float 0-1",
  "source": "enum[fashion_theory, trend_analysis, user_data]",
  "applicable_occasions": "string[]"
}
```

---

## Product Graph Relationships (15 Total)

### Product → Brand/Category

1. **Product → Brand** (MADE_BY)
   - Properties: verified

2. **Product → Category** (BELONGS_TO)
   - Properties: primary (boolean, if primary category)

3. **Category → Category** (PARENT_CATEGORY)
   - Properties: level

### Product → Style

4. **Product → StyleDescriptor** (HAS_AESTHETIC)
   - Properties: confidence, tagged_by (algorithm/human)

5. **StyleDescriptor → StyleDescriptor** (RELATED_STYLE)
   - Properties: similarity_score
   - Example: "boho chic" → "hippie" (0.8), "bohemian" → "eclectic" (0.7)

### Product → Occasion

6. **Product → OccasionType** (SUITED_FOR)
   - Properties: appropriateness_score, recommended_by

7. **OccasionType → StyleDescriptor** (TYPICALLY_FEATURES)
   - Properties: strength
   - Example: Wedding → Elegant (0.9), Wedding → Formal (0.95)

### Product → Visual

8. **Product → ProductVisualEmbedding** (HAS_VISUAL_EMBEDDING)
   - Properties: is_primary

9. **ProductVisualEmbedding → ProductVisualEmbedding** (VISUALLY_SIMILAR)
   - Properties: similarity_score
   - Self-referencing for visual similarity

### Product Relationships

10. **Product → Product** (OFTEN_BOUGHT_TOGETHER)
    - Properties: co_occurrence_count, confidence

11. **Product → Product** (SIMILAR_STYLE)
    - Properties: similarity_score, reason

12. **Product → Product** (SAME_OUTFIT)
    - Properties: outfit_count (how many times styled together)

### Styling Rules

13. **StylingRule → Category** (APPLIES_TO_CATEGORY)
    - Properties: relevance

14. **StylingRule → StyleDescriptor** (APPLIES_TO_STYLE)
    - Properties: relevance

15. **Product → StylingRule** (FOLLOWS_RULE)
    - Properties: compliance_score

---

## Product Graph Indexes

```cypher
// Product indexes
CREATE INDEX product_id_idx FOR (p:Product) ON (p.product_id);
CREATE INDEX product_brand_idx FOR (p:Product) ON (p.brand_id);
CREATE INDEX product_category_idx FOR (p:Product) ON (p.category_id);
CREATE INDEX product_price_idx FOR (p:Product) ON (p.price);
CREATE INDEX product_availability_idx FOR (p:Product) ON (p.availability);
CREATE INDEX product_color_idx FOR (p:Product) ON (p.color);

// Brand indexes
CREATE INDEX brand_id_idx FOR (b:Brand) ON (b.brand_id);
CREATE INDEX brand_name_idx FOR (b:Brand) ON (b.name);
CREATE INDEX brand_tier_idx FOR (b:Brand) ON (b.price_tier);

// Category indexes
CREATE INDEX category_id_idx FOR (c:Category) ON (c.category_id);
CREATE INDEX category_name_idx FOR (c:Category) ON (c.name);
CREATE INDEX category_parent_idx FOR (c:Category) ON (c.parent_category_id);
CREATE INDEX category_level_idx FOR (c:Category) ON (c.level);

// Style indexes
CREATE INDEX style_term_idx FOR (s:StyleDescriptor) ON (s.term);
CREATE INDEX style_category_idx FOR (s:StyleDescriptor) ON (s.category);
CREATE INDEX style_formality_idx FOR (s:StyleDescriptor) ON (s.formality_level);

// Occasion indexes
CREATE INDEX occasion_type_idx FOR (o:OccasionType) ON (o.name);
CREATE INDEX occasion_formality_idx FOR (o:OccasionType) ON (o.formality_level);

// Visual embedding indexes
CREATE INDEX embedding_product_idx FOR (e:ProductVisualEmbedding) ON (e.product_id);

// Fulltext search
CREATE FULLTEXT INDEX product_search FOR (p:Product) ON EACH [p.name, p.description];
CREATE FULLTEXT INDEX brand_search FOR (b:Brand) ON EACH [b.name, b.description];
CREATE FULLTEXT INDEX style_search FOR (s:StyleDescriptor) ON EACH [s.term, s.description];
```

---

## Cross-Graph Reference Strategy

### Option 1: Store IDs Only (Recommended)
**User Graph** stores Product graph entity IDs as strings:
- TasteProfile.brand_preferences: `["brand_uuid_1", "brand_uuid_2"]`
- UserProductInteraction.product_id: `"product_id_123"`
- UserOutfit.product_ids: `["prod_1", "prod_2", "prod_3"]`

**Queries:** Application layer joins data from both graphs

**Benefits:**
- Clean separation
- Independent scaling
- No circular dependencies

---

### Option 2: Federated Queries (Neo4j 4.0+)
Use Neo4j fabric to query across databases:

```cypher
// Query user preferences and resolve to products
USE users.user_graph
MATCH (u:User {user_id: $userId})-[:PREFERS_BRAND]->(b:Brand)
WITH collect(b.brand_id) as brand_ids

USE products.product_graph
MATCH (p:Product)-[:MADE_BY]->(b:Brand)
WHERE b.brand_id IN brand_ids
RETURN p
```

---

### Option 3: Shared Reference Nodes
Keep Brand, Category, StyleDescriptor as shared nodes in both graphs (duplicated):

**Pros:** Faster queries, no cross-graph lookups
**Cons:** Data duplication, sync complexity

---

## Agent-Graph Mapping

### CypherBot → Product Graph
**Primary:** Product graph for catalog search
**Secondary:** User graph for preference filtering
**Queries:**
- Traverse Product → Brand → StyleDescriptor
- Use OFTEN_BOUGHT_TOGETHER relationships
- Filter by User's PREFERS_CATEGORY

---

### VibeBot → Product Graph
**Primary:** Product graph for aesthetic matching
**Secondary:** User graph for style preferences
**Queries:**
- Match Product → StyleDescriptor → User's EXHIBITS_STYLE
- Use visual similarity via ProductVisualEmbedding
- Filter by User's occasion context

---

### VisionBot → Both Graphs
**Primary:** Product graph for visual embeddings
**Secondary:** User graph for user's body photo embeddings
**Queries:**
- Compare UserVisualEmbedding to ProductVisualEmbedding
- Find visually similar products
- Use color/pattern analysis from BodyData

---

### Judge Ari → Both Graphs
**Primary:** User graph for preferences and context
**Secondary:** Product graph for evaluation
**Queries:**
- Read RecommendationSession history
- Evaluate Product alignment with User's RootValues
- Check Product → OccasionType → User's UserOccasion
- Store judgments in User graph (RecommendationSession)

---

## Example Cross-Graph Queries

### 1. Get recommendations for user's upcoming wedding
```cypher
// User Graph: Get user's occasion
USE user_graph
MATCH (u:User {user_id: $userId})-[m:MENTIONED_OCCASION]->(o:UserOccasion)
WHERE o.occasion_type = 'wedding' AND o.status = 'upcoming'
WITH o.occasion_type as occasion, o.formality_level as formality

// Product Graph: Find suited products
USE product_graph
MATCH (p:Product)-[s:SUITED_FOR]->(ot:OccasionType {name: occasion})
WHERE ot.formality_level = formality
RETURN p
ORDER BY s.appropriateness_score DESC
LIMIT 20
```

---

### 2. Find products matching user's exhibited styles
```cypher
// User Graph: Get user's style descriptors
USE user_graph
MATCH (u:User {user_id: $userId})-[e:EXHIBITS_STYLE]->(sd:StyleDescriptor)
WHERE e.confidence > 0.6
WITH collect(sd.descriptor_id) as style_ids

// Product Graph: Match products with those styles
USE product_graph
MATCH (p:Product)-[h:HAS_AESTHETIC]->(sd:StyleDescriptor)
WHERE sd.descriptor_id IN style_ids
RETURN p, sd.term, h.confidence
ORDER BY h.confidence DESC
```

---

### 3. Visual similarity search from user's body photo
```cypher
// User Graph: Get user's visual embedding
USE user_graph
MATCH (u:User {user_id: $userId})-[:HAS_BODY_DATA]->(bd:BodyData)
MATCH (bd)-[:HAS_VISUAL_EMBEDDING]->(uve:UserVisualEmbedding)
WITH uve.embedding_vector as user_vector

// Product Graph: Find visually similar products
USE product_graph
MATCH (p:Product)-[:HAS_VISUAL_EMBEDDING]->(pve:ProductVisualEmbedding)
// Vector similarity computation (using Qdrant or Neo4j vector index)
RETURN p
ORDER BY vectorSimilarity(user_vector, pve.embedding_vector) DESC
LIMIT 20
```

---

## Migration from Single Graph

### Phase 1: Duplicate Schema
1. Create Product graph database
2. Copy product-related nodes (Product, Brand, Category, StyleDescriptor)
3. Maintain sync during transition

### Phase 2: Update Application
1. Modify queries to target correct graph
2. Implement cross-graph reference resolution
3. Update write operations to target correct graph

### Phase 3: Clean User Graph
1. Remove product nodes from User graph
2. Replace with ID references
3. Verify all queries working

### Phase 4: Optimize
1. Add graph-specific indexes
2. Tune query patterns per graph
3. Set up separate scaling strategies

---

## Summary

**User Graph:**
- 16 node types (10 current + 6 proposed)
- 23 relationships
- Focus: User identity, preferences, history, interactions
- Write-heavy: User actions, sessions, interactions
- Smaller, user-scoped queries

**Product Graph:**
- 7 node types
- 15 relationships
- Focus: Product catalog, brand hierarchy, style taxonomy
- Read-heavy: Product discovery, recommendations
- Large graph traversals, similarity searches

**Cross-Graph:**
- ID-based references (recommended)
- Application-layer joins or Neo4j Fabric
- Clear separation enables independent scaling

---

**Document Version:** 1.0
**Date:** 2025-11-06
**Author:** Claude (Sonnet 4.5) based on ARI system analysis
**Status:** Proposal - Pending Review
