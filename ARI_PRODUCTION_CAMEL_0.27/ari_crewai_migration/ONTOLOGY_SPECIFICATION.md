# ARI Neo4j Ontology Specification

## Dual Graph Architecture

The ARI system uses two separate Neo4j graphs for optimal performance and scalability:

**User Graph**: Stores user profiles, preferences, onboarding history, conversation patterns, and interaction history. This graph is write-heavy with user-scoped queries and privacy-sensitive data.

**Product Graph**: Stores product catalog, brand hierarchies, style taxonomies, and visual embeddings. This graph is read-heavy with large traversals and similarity searches, shared across all users.

**Cross-Graph References**: User graph stores Product graph entity IDs as strings. Application layer performs joins between graphs when needed.

---

## Graph 1: User Ontology

### Current Nodes

**User**
```
user_id: uuid
username: string
email: string
created_at: datetime
updated_at: datetime
last_active: datetime
onboarding_completed: boolean
onboarding_completed_at: datetime
onboarding_version: string
```

**PersonalIdentity**
```
age: integer
location_city: string
location_region: string
location_type: string
occupation: string
occupation_industry: string
typical_occasions: json
gender_identity: string
ethnicity: string
relationship_status: string
parental_status: json
sexuality: string
income_level: string
education: string
religious_cultural_background: json
```

**TasteProfile**
```
gender_expression: json
brand_preferences: json
shape_preferences: json
fit_preferences: json
style_loves: string
style_wants: string
style_avoids: string
occasion_styles: json
style_icons: json
```

**ProcessProfile**
```
style_motivations: json
creative_control: integer
style_goals: string
brand_loyalty: integer
style_adventurousness: integer
validation_sources: json
exploration_style: string
social_influences: json
```

**PracticalityProfile**
```
monthly_budget_min: float
monthly_budget_max: float
yearly_budget: float
budget_flexibility: string
category_budgets: json
```

**BodyData**
```
face_photo_id: string
face_photo_url: string
body_photo_id: string
body_photo_url: string
coloring_verbal: string
body_verbal: string
body_insecurities: json
favorite_features: json
captured_at: datetime
```

**SocialMediaProfile**
```
instagram_handle: string
instagram_connected_at: datetime
pinterest_handle: string
pinterest_connected_at: datetime
tiktok_handle: string
tiktok_connected_at: datetime
```

**RootValue**
```
value_id: uuid
value: string
source_node: string
discovered_at: datetime
confidence: float
```

**OnboardingMetadata**
```
total_skip_count: integer
skip_counts_by_node: json
completion_time_minutes: integer
tiers_completed: json
started_at: datetime
completed_at: datetime
conversation_quality_score: float
```

**OnboardingDataNode**
```
node_id: string
tier: string
data: json
completed_at: datetime
skip_count: integer
```

### Proposed Nodes

**UserOccasion**
```
occasion_id: uuid
occasion_type: enum
name: string
formality_level: enum
mentioned_count: integer
context: text
date: datetime
status: enum
created_from: enum
```

**ConversationPattern**
```
pattern_id: uuid
pattern_type: enum
topic: string
evidence: text[]
frequency: integer
confidence: float
inferred_value: string
```

**UserVisualEmbedding**
```
embedding_id: uuid
embedding_vector: float[]
source: enum
analysis: json
timestamp: datetime
```

**UserProductInteraction**
```
interaction_id: uuid
product_id: string
interaction_type: enum
timestamp: datetime
context: string
recommended_by_agent: enum
user_feedback: text
implicit_score: float
```

**RecommendationSession**
```
session_id: uuid
timestamp: datetime
occasion_context: string
cypher_bot_recommendations: string[]
vibe_bot_recommendations: string[]
vision_bot_recommendations: string[]
final_selections: string[]
reasoning: text
quality_scores: json
user_feedback: enum
```

**UserOutfit**
```
outfit_id: uuid
name: string
occasion_id: string
product_ids: string[]
created_by: enum
style_description: text
completeness_score: float
harmony_score: float
user_rating: float
worn: boolean
worn_date: datetime
created_at: datetime
```

### Proposed Property Enhancements

**TasteProfile**
```
style_evolution_notes: text
inspiration_sources: string[]
style_confidence: float
openness_to_new_styles: float
```

**ProcessProfile**
```
ideal_process_description: text
pain_points: string[]
decision_speed: enum
returns_frequency: enum
```

**PracticalityProfile**
```
investment_philosophy: text
budget_flexibility_triggers: text
value_priorities_ranking: string[]
```

**BodyData**
```
fit_challenges: string[]
ideal_silhouettes: string[]
comfort_requirements: text
```

### Current Relationships

```
User -[HAS_PERSONAL_IDENTITY]-> PersonalIdentity
  created_at: datetime
  updated_at: datetime

User -[HAS_TASTE_PROFILE]-> TasteProfile
  created_at: datetime
  updated_at: datetime

User -[HAS_PROCESS_PROFILE]-> ProcessProfile
  created_at: datetime
  updated_at: datetime

User -[HAS_PRACTICALITY_PROFILE]-> PracticalityProfile
  created_at: datetime
  updated_at: datetime

User -[HAS_BODY_DATA]-> BodyData
  created_at: datetime
  updated_at: datetime

User -[HAS_SOCIAL_MEDIA]-> SocialMediaProfile
  created_at: datetime
  updated_at: datetime

User -[HAS_ROOT_VALUE]-> RootValue
  discovered_at: datetime
  strength: float

User -[HAS_ONBOARDING_METADATA]-> OnboardingMetadata
  created_at: datetime

User -[HAS_DATA_NODE]-> OnboardingDataNode
  created_at: datetime

PersonalIdentity -[RELATES_TO_VALUE]-> RootValue
  connection_strength: float

TasteProfile -[RELATES_TO_VALUE]-> RootValue
  connection_strength: float

ProcessProfile -[RELATES_TO_VALUE]-> RootValue
  connection_strength: float
```

### Proposed Relationships

```
User -[MENTIONED_OCCASION]-> UserOccasion
  mention_count: integer
  first_mentioned: datetime
  last_mentioned: datetime
  importance_score: float

User -[HAS_PATTERN]-> ConversationPattern
  identified_at: datetime

User -[INTERACTED_WITH]-> UserProductInteraction
  timestamp: datetime

User -[HAD_SESSION]-> RecommendationSession
  timestamp: datetime

User -[HAS_OUTFIT]-> UserOutfit
  created_at: datetime
  updated_at: datetime

BodyData -[HAS_VISUAL_EMBEDDING]-> UserVisualEmbedding
  created_at: datetime

ConversationPattern -[SUGGESTS_VALUE]-> RootValue
  confidence: float

RecommendationSession -[FOR_OCCASION]-> UserOccasion

UserOutfit -[FOR_OCCASION]-> UserOccasion
```

### Cross-Graph Preference Relationships

```
User -[PREFERS_BRAND]-> Brand (Product Graph)
  preference_strength: float
  mention_count: integer
  confidence: float

User -[AVOIDS_BRAND]-> Brand (Product Graph)
  reason: text
  mention_count: integer

User -[PREFERS_CATEGORY]-> Category (Product Graph)
  preference_score: float
  for_occasions: string[]
  context: text

User -[AVOIDS_CATEGORY]-> Category (Product Graph)
  reason: text

User -[EXHIBITS_STYLE]-> StyleDescriptor (Product Graph)
  confidence: float
  source: enum
  occasions: string[]
  mention_count: integer
```

---

## Graph 2: Product Ontology

### Nodes

**Product**
```
product_id: string
name: string
brand_id: string
category_id: string
price: float
currency: string
image_url: string
image_urls: string[]
description: text
color: string
colors: string[]
size_options: string[]
material: string
pattern: string
season: string
gender_target: string
availability: enum
popularity_score: float
quality_indicators: json
retailer: string
retailer_url: string
created_at: datetime
updated_at: datetime
```

**Brand**
```
brand_id: uuid
name: string
price_tier: enum
aesthetic: string[]
country_of_origin: string
sustainability_rating: float
popularity_score: float
description: text
logo_url: string
website: string
```

**Category**
```
category_id: uuid
name: string
parent_category_id: string
level: integer
description: text
typical_occasions: string[]
```

**StyleDescriptor**
```
descriptor_id: uuid
term: string
category: enum
description: text
color_palette: string[]
pattern_types: string[]
typical_silhouettes: string[]
formality_level: enum
seasonal_relevance: string[]
```

**ProductVisualEmbedding**
```
embedding_id: uuid
product_id: string
embedding_vector: float[]
image_angle: enum
analysis: json
timestamp: datetime
```

**OccasionType**
```
occasion_type_id: uuid
name: string
formality_level: enum
description: text
typical_dress_codes: string[]
seasonal_considerations: text
```

**StylingRule**
```
rule_id: uuid
rule_type: enum
description: text
confidence: float
source: enum
applicable_occasions: string[]
```

### Relationships

```
Product -[MADE_BY]-> Brand
  verified: boolean

Product -[BELONGS_TO]-> Category
  primary: boolean

Product -[HAS_AESTHETIC]-> StyleDescriptor
  confidence: float
  tagged_by: enum

Product -[SUITED_FOR]-> OccasionType
  appropriateness_score: float
  recommended_by: string

Product -[HAS_VISUAL_EMBEDDING]-> ProductVisualEmbedding
  is_primary: boolean

Product -[OFTEN_BOUGHT_TOGETHER]-> Product
  co_occurrence_count: integer
  confidence: float

Product -[SIMILAR_STYLE]-> Product
  similarity_score: float
  reason: string

Product -[SAME_OUTFIT]-> Product
  outfit_count: integer

Category -[PARENT_CATEGORY]-> Category
  level: integer

StyleDescriptor -[RELATED_STYLE]-> StyleDescriptor
  similarity_score: float

OccasionType -[TYPICALLY_FEATURES]-> StyleDescriptor
  strength: float

ProductVisualEmbedding -[VISUALLY_SIMILAR]-> ProductVisualEmbedding
  similarity_score: float

StylingRule -[APPLIES_TO_CATEGORY]-> Category
  relevance: float

StylingRule -[APPLIES_TO_STYLE]-> StyleDescriptor
  relevance: float

Product -[FOLLOWS_RULE]-> StylingRule
  compliance_score: float
```

---

## Agent-Graph Mapping

### CypherBot
**Primary Graph**: Product
**Secondary Graph**: User
**Usage**: Searches product catalog using graph relationships and collaborative filtering. Filters results based on user's brand and category preferences from User graph.

### VibeBot
**Primary Graph**: Product
**Secondary Graph**: User
**Usage**: Finds products through semantic similarity and aesthetic matching. Queries StyleDescriptor relationships in Product graph and matches against user's EXHIBITS_STYLE from User graph.

### VisionBot
**Primary Graph**: Product
**Secondary Graph**: User
**Usage**: Performs visual similarity search by comparing UserVisualEmbedding from User graph against ProductVisualEmbedding in Product graph using FashionSigLIP embeddings.

### Judge Ari
**Primary Graph**: User
**Secondary Graph**: Product
**Usage**: Evaluates recommendations from other agents. Reads user context from User graph including preferences, occasions, and root values. Accesses Product graph to evaluate product alignment. Stores judgments in RecommendationSession nodes in User graph for learning.

---

## Node Summary

**User Graph**
- Current: 10 nodes
- Proposed: 6 additional nodes
- Total: 16 nodes

**Product Graph**
- Total: 7 nodes

**Combined System**
- Total: 23 nodes

## Relationship Summary

**User Graph**
- Current: 13 relationships
- Proposed: 10 additional relationships
- Total: 23 relationships

**Product Graph**
- Total: 15 relationships

**Combined System**
- Total: 38 relationships
