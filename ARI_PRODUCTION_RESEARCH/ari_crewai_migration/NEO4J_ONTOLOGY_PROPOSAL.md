# Neo4j Ontology Proposal for ARI System
## Enhanced Graph Schema for Onboarding V2 + Agent Intelligence

---

## Executive Summary

This proposal enhances the current Neo4j schema to support:
1. **Onboarding V2** - Adaptive, conversational data collection with pattern recognition
2. **Agent Intelligence** - Judge Ari, CypherBot, VibeBot, VisionBot reasoning and recommendations
3. **Feedback Loops** - Learning from user interactions and agent judgments
4. **Contextual Recommendations** - Occasion-based, relationship-driven product discovery

**Key Additions:**
- Occasion entities and relationships
- Structured brand/category/silhouette tracking
- Conversation pattern analysis (mention frequency, confidence scoring)
- Product interaction history
- Aesthetic/vibe descriptors as first-class entities
- Visual embedding linkage
- Agent judgment and learning metadata

---

## Current Schema Overview

**Existing Nodes:**
- User, PersonalIdentity, TasteProfile, ProcessProfile, PracticalityProfile
- BodyData, SocialMediaProfile, RootValue
- OnboardingMetadata, OnboardingDataNode

**Existing Relationships:**
- HAS_PERSONAL_IDENTITY, HAS_TASTE_PROFILE, HAS_PROCESS_PROFILE
- HAS_PRACTICALITY_PROFILE, HAS_BODY_DATA, HAS_SOCIAL_MEDIA
- HAS_ROOT_VALUE, HAS_ONBOARDING_METADATA, HAS_DATA_NODE, RELATES_TO_VALUE

---

## Proposed New Nodes

### 1. Occasion
**Purpose:** Track occasions mentioned by user for dynamic styling recommendations

**Properties:**
```json
{
  "occasion_id": "uuid",
  "occasion_type": "enum[wedding, interview, date, casual, work, party, travel, custom]",
  "name": "string (e.g., 'Sarah's wedding', 'park with Max')",
  "formality_level": "enum[very_formal, formal, business_casual, casual, very_casual]",
  "mentioned_count": "integer (how many times user mentioned this)",
  "context": "text (additional details from conversation)",
  "date": "datetime (if user specified)",
  "status": "enum[upcoming, recurring, past, hypothetical]",
  "created_from": "enum[onboarding, chat, explicit_add]"
}
```

**Why:** CypherBot and VibeBot reason heavily about occasions. User mentions "park with Max" or "wedding in June" - these become queryable entities for recommendations.

---

### 2. Brand
**Purpose:** Structure brand preferences as entities rather than flat strings

**Properties:**
```json
{
  "brand_id": "uuid",
  "name": "string",
  "preference_type": "enum[loves, likes, dislikes, never_mentioned]",
  "mention_count": "integer",
  "price_tier": "enum[luxury, premium, mid, affordable, budget]",
  "aesthetic": "string[] (e.g., ['boho', 'minimalist', 'edgy'])",
  "confidence": "float (0-1, how confident we are about this preference)"
}
```

**Why:** TasteProfile currently has "brand_preferences" as a string. Structuring as nodes enables:
- CypherBot to traverse brand relationships
- Judge Ari to evaluate brand alignment
- Pattern recognition (user mentions 3 sustainable brands → high sustainability value)

---

### 3. Category
**Purpose:** Track clothing categories user gravitates toward or avoids

**Properties:**
```json
{
  "category_id": "uuid",
  "name": "string (e.g., 'dresses', 'blazers', 'sneakers')",
  "parent_category": "string (e.g., 'tops', 'bottoms', 'shoes', 'accessories')",
  "preference_level": "float (-1 to 1, negative = avoid, positive = prefer)",
  "mention_count": "integer",
  "context_notes": "text (why they prefer/avoid this)"
}
```

**Why:** Agents reason about categories ("For WEDDINGS: Consider elegant dresses, formal suits..."). Need to track which categories user prefers.

---

### 4. StyleDescriptor
**Purpose:** Capture style/aesthetic descriptors as first-class entities

**Properties:**
```json
{
  "descriptor_id": "uuid",
  "term": "string (e.g., 'boho chic', 'minimalist', 'rock and roll')",
  "source": "enum[user_said, ari_inferred, visual_analysis]",
  "confidence": "float (0-1)",
  "mention_count": "integer",
  "associated_occasions": "string[] (which occasions this applies to)",
  "color_palette": "string[] (associated colors)",
  "pattern_types": "string[] (associated patterns)"
}
```

**Why:** Mid-conversation feedback says "Sounds like you're very boho chic but sometimes have a rock and roll flair." These descriptors should be queryable for:
- VibeBot aesthetic matching
- VisionBot visual similarity
- Judge Ari evaluation of product alignment

---

### 5. Product
**Purpose:** Track products user has interacted with

**Properties:**
```json
{
  "product_id": "string (external product ID)",
  "name": "string",
  "brand": "string",
  "category": "string",
  "price": "float",
  "image_url": "string",
  "description": "text",
  "visual_embedding_id": "string (reference to FashionSigLIP embedding)"
}
```

**Why:** CypherBot searches 6.4M product graph. Need to track which products were:
- Recommended by which agent
- Viewed/liked/purchased/rejected by user
- Used in outfit combinations

---

### 6. ProductInteraction
**Purpose:** Track user interactions with products for learning and feedback loops

**Properties:**
```json
{
  "interaction_id": "uuid",
  "interaction_type": "enum[recommended, viewed, liked, purchased, rejected, saved]",
  "timestamp": "datetime",
  "context": "string (occasion, search query, etc.)",
  "recommended_by_agent": "enum[judge_ari, cypher_bot, vibe_bot, vision_bot]",
  "user_feedback": "text (optional explicit feedback)",
  "implicit_score": "float (derived from interaction type)"
}
```

**Why:** Judge Ari has "learning_analysis_tool" - needs interaction history to learn preferences.

---

### 7. ConversationPattern
**Purpose:** Track patterns identified during onboarding conversations

**Properties:**
```json
{
  "pattern_id": "uuid",
  "pattern_type": "enum[repeated_mention, value_signal, contradiction, strong_preference, avoidance]",
  "topic": "string (e.g., 'sustainability', 'comfort', 'bold colors')",
  "evidence": "text[] (quotes or references from conversation)",
  "frequency": "integer (how many times this came up)",
  "confidence": "float (0-1)",
  "inferred_value": "string (optional RootValue this suggests)"
}
```

**Why:** Onboarding V2 feedback system says "I notice you mentioned sustainability 3 times." Need to track these patterns for:
- Real-time feedback generation
- RootValue inference
- Consistency checking

---

### 8. AgentJudgment
**Purpose:** Store Judge Ari's evaluations for learning and improvement

**Properties:**
```json
{
  "judgment_id": "uuid",
  "timestamp": "datetime",
  "occasion_context": "string",
  "cypher_bot_recommendations": "string[] (product IDs)",
  "vibe_bot_recommendations": "string[] (product IDs)",
  "final_selections": "string[] (product IDs chosen)",
  "reasoning": "text (why these were chosen)",
  "quality_scores": "json {product_id: score}",
  "user_feedback": "enum[accepted, rejected, modified]"
}
```

**Why:** Judge Ari uses "quality_scoring_tool", "consensus_detection_tool", "learning_analysis_tool". Need to store judgments to improve future recommendations.

---

### 9. VisualEmbedding
**Purpose:** Link body photos to visual style analysis

**Properties:**
```json
{
  "embedding_id": "uuid",
  "embedding_vector": "float[] (FashionSigLIP embedding)",
  "source": "enum[body_photo, product_image, inspiration_image]",
  "analysis": "json {colors, patterns, silhouettes detected}",
  "timestamp": "datetime"
}
```

**Why:** VisionBot uses FashionSigLIP embeddings. User's body photos should be embedded and linked to:
- Style preferences
- Visual similarity searches
- Color palette extraction

---

### 10. OutfitCombination
**Purpose:** Track outfit combinations recommended or created by user

**Properties:**
```json
{
  "outfit_id": "uuid",
  "occasion": "string",
  "product_ids": "string[]",
  "created_by": "enum[judge_ari, user, stylist]",
  "style_description": "text",
  "completeness_score": "float (0-1, does it cover all needed categories)",
  "harmony_score": "float (0-1, visual and style harmony)",
  "user_rating": "float (1-5, if user provided)",
  "worn": "boolean",
  "worn_date": "datetime"
}
```

**Why:** Judge Ari evaluates "completeness - do the recommendations work together as cohesive outfits?"

---

## Proposed New Relationships

### User → Occasion
```
(User)-[:MENTIONED_OCCASION {
  mention_count: integer,
  first_mentioned: datetime,
  last_mentioned: datetime,
  importance_score: float
}]->(Occasion)
```

### User → Brand
```
(User)-[:PREFERS_BRAND {
  preference_strength: float,
  mention_count: integer,
  confidence: float
}]->(Brand)

(User)-[:AVOIDS_BRAND {
  reason: text,
  mention_count: integer
}]->(Brand)
```

### User → Category
```
(User)-[:PREFERS_CATEGORY {
  preference_score: float,
  for_occasions: string[],
  context: text
}]->(Category)

(User)-[:AVOIDS_CATEGORY {
  reason: text
}]->(Category)
```

### User → StyleDescriptor
```
(User)-[:EXHIBITS_STYLE {
  confidence: float,
  source: enum[user_said, ari_inferred, visual_analysis],
  occasions: string[],
  mention_count: integer
}]->(StyleDescriptor)
```

### User → Product
```
(User)-[:INTERACTED_WITH]->(ProductInteraction)-[:INVOLVES_PRODUCT]->(Product)

Alternative direct relationships:
(User)-[:LIKED]->(Product)
(User)-[:PURCHASED]->(Product)
(User)-[:REJECTED {reason: text}]->(Product)
(User)-[:SAVED_FOR_LATER {occasion: string}]->(Product)
```

### User → ConversationPattern
```
(User)-[:HAS_PATTERN]->(ConversationPattern)
```

### Occasion → StyleDescriptor
```
(Occasion)-[:REQUIRES_STYLE]->(StyleDescriptor)
```

### Occasion → Product
```
(Occasion)-[:SUITED_FOR]->(Product)
```

### Product → Brand
```
(Product)-[:MADE_BY]->(Brand)
```

### Product → Category
```
(Product)-[:BELONGS_TO]->(Category)
```

### Product → StyleDescriptor
```
(Product)-[:HAS_AESTHETIC {confidence: float}]->(StyleDescriptor)
```

### Product → VisualEmbedding
```
(Product)-[:HAS_VISUAL_EMBEDDING]->(VisualEmbedding)
```

### OutfitCombination → Product
```
(OutfitCombination)-[:INCLUDES_PRODUCT {
  role: enum[top, bottom, shoes, accessory, outerwear],
  essential: boolean
}]->(Product)
```

### OutfitCombination → Occasion
```
(OutfitCombination)-[:FOR_OCCASION]->(Occasion)
```

### AgentJudgment → Product
```
(AgentJudgment)-[:RECOMMENDED_BY_CYPHER]->(Product)
(AgentJudgment)-[:RECOMMENDED_BY_VIBE]->(Product)
(AgentJudgment)-[:SELECTED_FINAL]->(Product)
```

### ConversationPattern → RootValue
```
(ConversationPattern)-[:SUGGESTS_VALUE {confidence: float}]->(RootValue)
```

### BodyData → VisualEmbedding
```
(BodyData)-[:HAS_VISUAL_EMBEDDING]->(VisualEmbedding)
```

---

## Enhanced Existing Nodes

### TasteProfile - New Properties
```json
{
  // Existing properties remain...
  "style_evolution_notes": "text (how their style is changing)",
  "inspiration_sources": "string[] (magazines, influencers, etc.)",
  "style_confidence": "float (0-1, how confident they are in their style)",
  "openness_to_new_styles": "float (0-1, willingness to experiment)"
}
```

### ProcessProfile - New Properties
```json
{
  // Existing properties remain...
  "ideal_process_description": "text (how they want shopping to be better)",
  "pain_points": "string[] (current frustrations)",
  "decision_speed": "enum[quick, moderate, deliberate]",
  "returns_frequency": "enum[rarely, sometimes, often]"
}
```

### PracticalityProfile - New Properties
```json
{
  // Existing properties remain...
  "investment_philosophy": "text (what makes something worth investing in)",
  "budget_flexibility_triggers": "text (when willing to stretch budget)",
  "value_priorities_ranking": "string[] (ordered list)"
}
```

### BodyData - New Properties
```json
{
  // Existing properties remain...
  "fit_challenges": "string[] (specific fit issues)",
  "ideal_silhouettes": "string[] (flattering shapes)",
  "comfort_requirements": "text (special needs, sensitivities)"
}
```

---

## Example Queries

### 1. Find occasions user needs outfits for
```cypher
MATCH (u:User {user_id: $userId})-[m:MENTIONED_OCCASION]->(o:Occasion)
WHERE o.status = 'upcoming'
RETURN o.name, o.occasion_type, o.formality_level, m.importance_score
ORDER BY m.importance_score DESC
```

### 2. Get user's style profile with confidence scores
```cypher
MATCH (u:User {user_id: $userId})-[e:EXHIBITS_STYLE]->(s:StyleDescriptor)
RETURN s.term, e.confidence, e.mention_count, e.occasions
ORDER BY e.confidence DESC
```

### 3. Find products for specific occasion matching user's style
```cypher
MATCH (u:User {user_id: $userId})-[:EXHIBITS_STYLE]->(s:StyleDescriptor)
MATCH (u)-[:MENTIONED_OCCASION]->(o:Occasion {name: $occasionName})
MATCH (p:Product)-[:HAS_AESTHETIC]->(s)
MATCH (p)-[:SUITED_FOR]->(o)
WHERE NOT EXISTS((u)-[:REJECTED]->(p))
RETURN p
ORDER BY p.relevance_score DESC
```

### 4. Identify root values from conversation patterns
```cypher
MATCH (u:User {user_id: $userId})-[:HAS_PATTERN]->(cp:ConversationPattern)
WHERE cp.frequency >= 3
MATCH (cp)-[s:SUGGESTS_VALUE]->(rv:RootValue)
RETURN rv.value, s.confidence, cp.topic, cp.evidence
ORDER BY s.confidence DESC
```

### 5. Get brands user loves with high confidence
```cypher
MATCH (u:User {user_id: $userId})-[p:PREFERS_BRAND]->(b:Brand)
WHERE p.preference_strength > 0.7 AND p.confidence > 0.6
RETURN b.name, b.aesthetic, p.preference_strength, p.mention_count
ORDER BY p.preference_strength DESC
```

### 6. Find similar users for collaborative filtering (CypherBot)
```cypher
MATCH (u:User {user_id: $userId})-[:PREFERS_BRAND]->(b:Brand)<-[:PREFERS_BRAND]-(similar:User)
WHERE similar.user_id <> $userId
WITH similar, COUNT(b) as shared_brands
MATCH (similar)-[:PURCHASED]->(p:Product)
WHERE NOT EXISTS((u)-[:PURCHASED]->(p))
RETURN p, shared_brands
ORDER BY shared_brands DESC
LIMIT 20
```

### 7. Analyze Judge Ari's learning over time
```cypher
MATCH (aj:AgentJudgment)-[:SELECTED_FINAL]->(p:Product)
MATCH (u:User)-[i:INTERACTED_WITH]->(pi:ProductInteraction)-[:INVOLVES_PRODUCT]->(p)
WHERE i.timestamp > aj.timestamp
RETURN
  aj.judgment_id,
  p.product_id,
  aj.reasoning,
  pi.interaction_type,
  pi.user_feedback
ORDER BY aj.timestamp DESC
```

### 8. Get visual embedding for style similarity (VisionBot)
```cypher
MATCH (u:User {user_id: $userId})-[:HAS_BODY_DATA]->(bd:BodyData)
MATCH (bd)-[:HAS_VISUAL_EMBEDDING]->(ve:VisualEmbedding)
RETURN ve.embedding_vector, ve.analysis
```

### 9. Find incomplete outfits needing additional pieces
```cypher
MATCH (u:User {user_id: $userId})-[:SAVED_FOR_LATER]->(p:Product)
MATCH (p)-[:BELONGS_TO]->(c:Category)
WITH u, COLLECT(DISTINCT c.name) as owned_categories
WHERE NOT 'shoes' IN owned_categories OR NOT 'accessories' IN owned_categories
RETURN owned_categories,
       CASE WHEN NOT 'shoes' IN owned_categories THEN 'shoes' ELSE NULL END as missing_1,
       CASE WHEN NOT 'accessories' IN owned_categories THEN 'accessories' ELSE NULL END as missing_2
```

### 10. Track mid-conversation feedback patterns for new users
```cypher
MATCH (u:User)-[:HAS_PATTERN]->(cp:ConversationPattern)
WHERE cp.frequency >= 2
WITH cp.topic as recurring_topic, COUNT(DISTINCT u) as user_count
WHERE user_count >= 10
RETURN recurring_topic, user_count
ORDER BY user_count DESC
```

---

## Implementation Strategy

### Phase 1: Core Enhancements (Immediate)
1. Add **Occasion**, **Brand**, **StyleDescriptor** nodes
2. Implement relationships: MENTIONED_OCCASION, PREFERS_BRAND, EXHIBITS_STYLE
3. Modify onboarding save logic to create these nodes from conversation data
4. Update CypherBot queries to leverage occasion and brand relationships

### Phase 2: Product Integration (Week 2)
1. Add **Product**, **ProductInteraction**, **Category** nodes
2. Import existing product catalog into Neo4j
3. Link products to brands, categories, style descriptors
4. Implement interaction tracking (viewed, liked, purchased, rejected)

### Phase 3: Agent Intelligence (Week 3)
1. Add **AgentJudgment** node for Judge Ari learning
2. Implement judgment storage after each recommendation cycle
3. Add feedback loop queries for improving recommendations
4. Update Judge Ari to query past judgments for learning

### Phase 4: Visual Intelligence (Week 4)
1. Add **VisualEmbedding** node
2. Generate FashionSigLIP embeddings for body photos
3. Link BodyData → VisualEmbedding
4. Enable VisionBot to query visual similarity based on user's photos

### Phase 5: Pattern Recognition (Week 5)
1. Add **ConversationPattern** node
2. Implement pattern detection during onboarding conversations
3. Link patterns to RootValues for automatic value inference
4. Use patterns for real-time mid-conversation feedback

### Phase 6: Outfit Intelligence (Week 6)
1. Add **OutfitCombination** node
2. Store Judge Ari's outfit recommendations
3. Track outfit usage and ratings
4. Implement outfit completion suggestions

---

## Migration Notes

### Backward Compatibility
- All existing nodes/relationships remain unchanged
- New properties on existing nodes are optional
- Queries can be gradually updated to leverage new structure

### Data Migration
1. Existing `brand_preferences` strings → Brand nodes
2. Existing `style_descriptors` strings → StyleDescriptor nodes
3. Parse `OnboardingDataNode` for occasions → Occasion nodes
4. Extract patterns from conversation history → ConversationPattern nodes

### Indexes Required
```cypher
// Performance indexes
CREATE INDEX occasion_type_idx FOR (o:Occasion) ON (o.occasion_type);
CREATE INDEX brand_name_idx FOR (b:Brand) ON (b.name);
CREATE INDEX category_name_idx FOR (c:Category) ON (c.name);
CREATE INDEX style_term_idx FOR (s:StyleDescriptor) ON (s.term);
CREATE INDEX product_category_idx FOR (p:Product) ON (p.category);

// Fulltext indexes for search
CREATE FULLTEXT INDEX occasion_search FOR (o:Occasion) ON EACH [o.name, o.context];
CREATE FULLTEXT INDEX style_search FOR (s:StyleDescriptor) ON EACH [s.term];
CREATE FULLTEXT INDEX product_search FOR (p:Product) ON EACH [p.name, p.description];
```

---

## Benefits by Agent

### CypherBot
- Traverse occasion → product relationships directly
- Query "users who mentioned similar occasions bought these products"
- Filter by brand preferences and category avoidances
- Leverage structured category hierarchies

### VibeBot
- Query StyleDescriptor nodes for semantic matching
- Find products with matching aesthetic relationships
- Use color palette and pattern associations
- Filter by user's exhibited styles with confidence scores

### VisionBot
- Access VisualEmbedding nodes for similarity search
- Link user's body photos to product visual embeddings
- Query products by visual characteristics
- Use embedding vectors for FashionSigLIP matching

### Judge Ari
- Query past AgentJudgment nodes for learning
- Evaluate product alignment with user's StyleDescriptors
- Consider occasion context and formality levels
- Track which recommendations led to purchases
- Improve scoring based on user feedback patterns

---

## ROI Estimate

**Current State:** Flat data structures, limited relationship traversal, no learning loops

**Enhanced State:** Rich graph relationships, pattern recognition, agent learning, contextual recommendations

**Expected Improvements:**
1. **Recommendation Relevance:** +40% (occasion-based, style-matched)
2. **User Engagement:** +35% (personalized, learns from interactions)
3. **Conversion Rate:** +25% (better product-occasion-style alignment)
4. **Onboarding Completion:** +20% (adaptive conversation, real-time feedback)
5. **Agent Efficiency:** +30% (structured queries vs. full-text search)

---

## Next Steps

1. Review this proposal with technical and UX teams
2. Prioritize phase implementation based on business goals
3. Create migration scripts for existing user data
4. Update onboarding save logic to create new nodes/relationships
5. Modify agent tools to leverage enhanced schema
6. Implement monitoring for new relationship queries
7. A/B test enhanced recommendations vs. current system

---

## Appendix: Complete Schema Diagram

```
┌─────────┐
│  User   │
└────┬────┘
     │
     ├─[HAS_PERSONAL_IDENTITY]──────────┐
     │                                   ▼
     │                        ┌──────────────────┐
     │                        │ PersonalIdentity │
     │                        └──────────────────┘
     │
     ├─[HAS_TASTE_PROFILE]──────────────┐
     │                                   ▼
     │                        ┌──────────────────┐
     │                        │  TasteProfile    │
     │                        └──────────────────┘
     │
     ├─[HAS_PROCESS_PROFILE]────────────┐
     │                                   ▼
     │                        ┌──────────────────────┐
     │                        │  ProcessProfile      │
     │                        └──────────────────────┘
     │
     ├─[HAS_PRACTICALITY_PROFILE]───────┐
     │                                   ▼
     │                        ┌──────────────────────────┐
     │                        │ PracticalityProfile      │
     │                        └──────────────────────────┘
     │
     ├─[HAS_BODY_DATA]──────────────────┐
     │                                   ▼
     │                        ┌──────────────────┐───[HAS_VISUAL_EMBEDDING]───┐
     │                        │    BodyData      │                             ▼
     │                        └──────────────────┘              ┌──────────────────────┐
     │                                                           │  VisualEmbedding     │
     ├─[MENTIONED_OCCASION]─────────────┐                       └──────────────────────┘
     │                                   ▼                                   ▲
     │                        ┌──────────────────┐                          │
     │                        │    Occasion      │───[REQUIRES_STYLE]───────┤
     │                        └──────────────────┘                          │
     │                                   │                                   │
     │                                   └─[SUITED_FOR]─────┐               │
     │                                                       ▼               │
     ├─[PREFERS_BRAND]──────────────────┐       ┌──────────────────┐       │
     │                                   ▼       │     Product      │───────┤
     │                        ┌──────────────────┤                  │       │
     │                        │      Brand       │←──[MADE_BY]──────┘       │
     │                        └──────────────────┘                          │
     │                                                       │               │
     ├─[EXHIBITS_STYLE]─────────────────┐                   │               │
     │                                   ▼                   │               │
     │                        ┌──────────────────────┐      │               │
     │                        │  StyleDescriptor     │←─────┴[HAS_AESTHETIC]┤
     │                        └──────────────────────┘                      │
     │                                   ▲                                   │
     │                                   │                                   │
     ├─[PREFERS_CATEGORY]───────────────┼──────┐                           │
     │                                   │      ▼                           │
     │                        ┌──────────┴───────────┐                     │
     │                        │      Category        │                     │
     │                        └──────────────────────┘                     │
     │                                   ▲                                   │
     │                                   └──[BELONGS_TO]────────────────────┘
     │
     ├─[HAS_PATTERN]────────────────────┐
     │                                   ▼
     │                        ┌──────────────────────┐
     │                        │ ConversationPattern  │───[SUGGESTS_VALUE]───┐
     │                        └──────────────────────┘                       ▼
     │                                                            ┌──────────────────┐
     ├─[HAS_ROOT_VALUE]──────────────────────────────────────────│    RootValue     │
     │                                                            └──────────────────┘
     │
     ├─[INTERACTED_WITH]────────────────┐
     │                                   ▼
     │                        ┌──────────────────────────┐
     │                        │  ProductInteraction      │───[INVOLVES_PRODUCT]───┐
     │                        └──────────────────────────┘                         │
     │                                                                              ▼
     │                                                                   ┌──────────────────┐
     │                                                                   │     Product      │
     └─[SAVED_FOR_LATER/LIKED/PURCHASED/REJECTED]────────────────────►  └──────────────────┘
                                                                                    │
                                                                                    │
                                                         ┌──────────────────────────┘
                                                         ▼
                                          ┌──────────────────────────┐
                                          │   OutfitCombination      │───[FOR_OCCASION]───┐
                                          └──────────────────────────┘                     │
                                                         │                                  ▼
                                                         └──[INCLUDES_PRODUCT]───►  ┌──────────────┐
                                                                                    │   Occasion   │
                                          ┌──────────────────────────┐            └──────────────┘
                                          │    AgentJudgment         │
                                          └──────────────────────────┘
                                                         │
                                                         ├──[RECOMMENDED_BY_CYPHER]────┐
                                                         ├──[RECOMMENDED_BY_VIBE]──────┤
                                                         └──[SELECTED_FINAL]───────────┤
                                                                                        ▼
                                                                             ┌──────────────────┐
                                                                             │     Product      │
                                                                             └──────────────────┘
```

---

**Document Version:** 1.0
**Date:** 2025-11-06
**Author:** Claude (Sonnet 4.5) based on ARI V2 system analysis
**Status:** Proposal - Pending Review
