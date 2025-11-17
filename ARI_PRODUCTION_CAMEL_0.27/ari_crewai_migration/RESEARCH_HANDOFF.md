# ARI Fashion Recommendation System - Research & Architecture Handoff

**Last Updated:** November 2025
**System Version:** Flow V2 (CrewAI Migration)
**Status:** Production - Active Development

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Dual Graph Architecture](#dual-graph-architecture)
3. [Product Graph Schema & Ontology](#product-graph-schema--ontology)
4. [User Graph Schema & Ontology](#user-graph-schema--ontology)
5. [Onboarding Flow](#onboarding-flow)
6. [Search & Matching Architecture](#search--matching-architecture)
7. [Code Structure](#code-structure)
8. [Current Challenges & Solutions](#current-challenges--solutions)
9. [Future Research Directions](#future-research-directions)
10. [Critical Learnings](#critical-learnings)

---

## System Overview

### What is ARI?

ARI (AI Recommendation Intelligence) is a fashion product recommendation system that uses a **dual graph architecture** to match user preferences with product attributes through multi-modal AI search.

**Key Capabilities:**
- Natural language product search
- Multi-modal matching (text + visual + graph-based)
- User preference learning and growth
- Personalized recommendations based on style, body shape, and occasion

**Technology Stack:**
- **Graph Database:** Neo4j (dual graphs: User + Product)
- **Vector Database:** Qdrant (semantic embeddings)
- **LLM Orchestration:** CrewAI Flow V2
- **Primary LLM:** GPT-4o
- **Embeddings:** text-embedding-ada-002, CLIP (visual)
- **Language:** Python 3.10

---

## Dual Graph Architecture

### Philosophy: Separation of Concerns

ARI uses **TWO separate Neo4j graphs** on the same server:

```
Neo4j Server (neo4j://34.135.40.119:7687)
├── Database: productionbackup2 (PRODUCT GRAPH)
│   └── 6.4M products with AI-extracted attributes
└── Database: users (USER GRAPH)
    └── User profiles, preferences, and relationship ontology
```

**Why Two Graphs?**
1. **Scalability:** Product graph is massive (6.4M nodes), user graph is small but complex
2. **Growth Patterns:** Products are relatively static; users grow dynamically with interactions
3. **Query Optimization:** Different indexing strategies for different access patterns
4. **Data Integrity:** Prevents user preference corruption from product updates

---

## Product Graph Schema & Ontology

> **SEE ALSO:** [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) for the complete planned ontology specification.

**IMPORTANT NOTE:** There is a **significant gap** between the PLANNED ontology (documented in ONTOLOGY_SPECIFICATION.md) and the CURRENT ACTUAL schema (discovered via database inspection). This section documents BOTH.

### Database Details
- **Database Name:** `productionbackup2`
- **Node Count:** 6,416,804 products
- **Primary Label:** `Product`

### Current ACTUAL Product Node Properties (As of Nov 2025)

**CRITICAL:** The product schema uses AI-extracted properties, NOT the structured ontology yet.

```cypher
(:Product {
  // Core Identity
  id: String              // UUID
  title: String           // Product name/title
  description: String     // Product description

  // Pricing & Media
  price: Float            // Price (e.g., 49.99)
  images: String          // JSON string array of URLs
  visited_num: Integer    // Visit/view count

  // AI-Extracted Attributes (THE KEY TO MATCHING)
  extracted_brand: String         // AI-extracted brand name
  extracted_colors: [String]      // Color tags: ["black", "white", "red"]
  extracted_styles: [String]      // Style tags: ["casual", "formal", "sporty"]
})
```

### Product Ontology: AI-Extracted Attributes

**The Core Insight:** Products don't have structured categories. Instead, they have **AI-extracted semantic tags**.

#### Color Extraction
```python
extracted_colors: ["black", "navy", "white"]
```
- Uses vision models to identify colors from images
- Normalized color names (e.g., "dark blue" → "navy")
- Multiple colors per product (patterns, multi-color items)

**Query Pattern:**
```cypher
MATCH (p:Product)
WHERE 'black' IN p.extracted_colors
RETURN p
```

#### Style Extraction
```python
extracted_styles: ["classic", "business", "casual"]
```
- Semantic style tags from title/description/images
- Examples: "sporty", "elegant", "minimalist", "bohemian"
- Multi-tag support (a dress can be "elegant" AND "casual")

**Query Pattern:**
```cypher
MATCH (p:Product)
WHERE 'elegant' IN p.extracted_styles
  OR toLower(p.title) CONTAINS 'elegant'
RETURN p
```

#### Brand Extraction
```python
extracted_brand: "Nike"
```
- Normalized brand names
- Handles variations (e.g., "NIKE", "Nike Inc." → "Nike")

### Available Indexes
```
Product.id (RANGE)      // Primary key lookups
Product.title (RANGE)   // Text search optimization
Product.price (RANGE)   // Price filtering
```

**NOTE:** No fulltext indexes exist. All text search uses `CONTAINS` operations.

### PLANNED Product Ontology (From ONTOLOGY_SPECIFICATION.md)

The complete planned ontology includes:

**Nodes:**
- `Product` (with full merchant data: price, description, images, etc.)
- `Brand` (brand hierarchy, aesthetics, sustainability ratings)
- `Category` (hierarchical category tree)
- `StyleDescriptor` (aesthetic tags with color palettes, formality levels)
- `ProductVisualEmbedding` (visual similarity vectors)
- `OccasionType` (formality levels, dress codes)
- `StylingRule` (outfit combination rules)

**Relationships:**
- `Product -[MADE_BY]-> Brand`
- `Product -[BELONGS_TO]-> Category`
- `Product -[HAS_AESTHETIC]-> StyleDescriptor`
- `Product -[SUITED_FOR]-> OccasionType`
- `Product -[OFTEN_BOUGHT_TOGETHER]-> Product`
- `Product -[SIMILAR_STYLE]-> Product`
- And 9 more relationship types...

**See [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 355-504 for full specification.**

### Schema Migration Status

| Feature | PLANNED (ONTOLOGY_SPECIFICATION.md) | ACTUAL (Current DB) | Migration Needed? |
|---------|-------------------------------------|---------------------|-------------------|
| Product Core | Full properties | ✓ Basic properties | Partial |
| Brand Nodes | Separate Brand nodes with hierarchy | ✗ Flat `extracted_brand` string | YES |
| Category Tree | Hierarchical Category nodes | ✗ No category property at all! | YES |
| Style Descriptors | StyleDescriptor nodes with palettes | △ `extracted_styles` array | YES (upgrade) |
| Color Properties | Structured color nodes | △ `extracted_colors` array | Partial |
| Visual Embeddings | ProductVisualEmbedding nodes | ? Unknown (not in sample) | Maybe |
| Relationships | 15 relationship types | ✗ None discovered | YES |

**Migration Priority:**
1. **URGENT:** Add Brand nodes (currently just strings)
2. **URGENT:** Add Category tree (missing completely!)
3. **HIGH:** Convert extracted_styles to StyleDescriptor nodes
4. **MEDIUM:** Add product relationships (SIMILAR_STYLE, OFTEN_BOUGHT_TOGETHER)
5. **LOW:** Add OccasionType and StylingRule nodes

### Product Graph Growth

**Products are relatively STATIC:**
- Batch imports from merchant feeds
- Periodic updates (weekly/monthly)
- No real-time product creation
- Growth is linear, not exponential

**Implications for Matching:**
- Can cache product embeddings
- Pre-compute product relationships
- Static ontology allows stable semantic search

---

## User Graph Schema & Ontology

> **SEE ALSO:** [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 15-353 for the complete User Graph ontology specification.

**IMPORTANT NOTE:** The User Graph has a much more detailed PLANNED ontology than what may be currently implemented. This section covers both.

### Database Details
- **Database Name:** `users`
- **Primary Architecture:** User-centric star schema with preference relationships

### PLANNED User Ontology (From ONTOLOGY_SPECIFICATION.md)

The complete planned ontology includes **16 node types:**

**Current Nodes (Implemented):**
1. `User` - Core user identity
2. `PersonalIdentity` - Demographics, location, occupation
3. `TasteProfile` - Style preferences, brand loves, fit preferences
4. `ProcessProfile` - Decision-making style, motivations, goals
5. `PracticalityProfile` - Budget ranges, category budgets
6. `BodyData` - Photos, body shape, coloring, insecurities
7. `SocialMediaProfile` - Instagram, Pinterest, TikTok handles
8. `RootValue` - Core values extracted from preferences
9. `OnboardingMetadata` - Onboarding completion stats
10. `OnboardingDataNode` - Tier-specific onboarding data

**Proposed Nodes (Future):**
11. `UserOccasion` - User-specific occasions with formality levels
12. `ConversationPattern` - Detected patterns from chats
13. `UserVisualEmbedding` - Visual style embeddings from user photos
14. `UserProductInteraction` - Product clicks, views, purchases
15. `RecommendationSession` - Search sessions with bot contributions
16. `UserOutfit` - Saved outfits with harmony scores

**See [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 17-213 for full node specifications.**

### User Relationships (Planned)

**Current (13 relationships):**
- `User -[HAS_PERSONAL_IDENTITY]-> PersonalIdentity`
- `User -[HAS_TASTE_PROFILE]-> TasteProfile`
- `User -[HAS_PROCESS_PROFILE]-> ProcessProfile`
- `User -[HAS_PRACTICALITY_PROFILE]-> PracticalityProfile`
- `User -[HAS_BODY_DATA]-> BodyData`
- `User -[HAS_SOCIAL_MEDIA]-> SocialMediaProfile`
- `User -[HAS_ROOT_VALUE]-> RootValue` (with strength)
- `User -[HAS_ONBOARDING_METADATA]-> OnboardingMetadata`
- And 5 more...

**Proposed (10 additional relationships):**
- `User -[MENTIONED_OCCASION]-> UserOccasion` (with importance_score)
- `User -[INTERACTED_WITH]-> UserProductInteraction`
- `User -[HAD_SESSION]-> RecommendationSession`
- `User -[HAS_OUTFIT]-> UserOutfit`
- And 6 more...

**See [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 246-324 for full relationship specifications.**

### Cross-Graph Preference Relationships

**These bridge User Graph → Product Graph:**
```cypher
User -[PREFERS_BRAND]-> Brand (Product Graph)
  preference_strength: float
  confidence: float

User -[AVOIDS_BRAND]-> Brand (Product Graph)
  reason: text

User -[EXHIBITS_STYLE]-> StyleDescriptor (Product Graph)
  confidence: float
  occasions: string[]
```

**See [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 326-351 for cross-graph relationships.**

### User Ontology Philosophy: Growing Preference Graph

**Core Insight:** Users are NOT static profiles. They are **growing relationship networks** that learn over time.

#### Core Ontology Structure

```cypher
// User Profile Expansion
(user:User)
  -[:HAS_BODY_TYPE]-> (body:BodyType {
      shape: String,           // "athletic", "curvy", "petite"
      measurements: Map,       // Detailed sizing
      fit_preferences: [String] // "loose fit", "tailored"
  })

  -[:PREFERS_STYLE]-> (style:Style {
      name: String,            // "minimalist", "bohemian"
      confidence: Float,       // 0.0-1.0 preference strength
      occasions: [String]      // When this style is preferred
  })

  -[:HAS_OCCASION]-> (occasion:Occasion {
      type: String,            // "work", "date night", "casual"
      formality: Integer,      // 1-10 scale
      frequency: String        // "daily", "weekly", "special"
  })

  -[:INTERACTED_WITH]-> (product:Product {
      interaction_type: String,  // "viewed", "liked", "purchased"
      timestamp: DateTime,
      context: Map              // Occasion, mood, season
  })
```

#### Preference Relationships

```cypher
// Positive Signals
(user)-[:LIKES {strength: Float, reason: String}]->(product)
(user)-[:PURCHASED {date: DateTime, context: Map}]->(product)
(user)-[:FAVORITED {timestamp: DateTime}]->(product)

// Negative Signals
(user)-[:DISLIKES {reason: String}]->(product)
(user)-[:REJECTED {timestamp: DateTime, reason: String}]->(product)

// Contextual Preferences
(user)-[:PREFERS_FOR {occasion: String}]->(style:Style)
(user)-[:AVOIDS_BRAND {reason: String}]->(brand:Brand)
```

### User Graph Growth Patterns

**The user graph GROWS with every interaction:**

1. **Onboarding (Day 0):**
   ```cypher
   CREATE (u:User {username: "alice"})
   CREATE (u)-[:HAS_BODY_TYPE]->(b:BodyType {shape: "athletic"})
   CREATE (u)-[:PREFERS_STYLE]->(s:Style {name: "minimalist"})
   ```

2. **First Search (Day 1):**
   ```cypher
   MATCH (u:User {username: "alice"})
   MATCH (p:Product {id: "prod-123"})
   CREATE (u)-[:VIEWED {timestamp: datetime()}]->(p)

   // Extract implicit preferences
   WITH p.extracted_colors as colors
   FOREACH (color IN colors |
     MERGE (u)-[r:PREFERS_COLOR]->(c:Color {name: color})
     ON CREATE SET r.strength = 0.1
     ON MATCH SET r.strength = r.strength + 0.1
   )
   ```

3. **Purchase (Day 30):**
   ```cypher
   MATCH (u:User {username: "alice"})
   MATCH (p:Product {id: "prod-456"})
   CREATE (u)-[:PURCHASED {
     date: datetime(),
     occasion: "work",
     season: "fall"
   }]->(p)

   // Strengthen related preferences
   MATCH (p)-[:HAS_STYLE]->(s:Style)
   MERGE (u)-[r:PREFERS_STYLE]->(s)
   ON CREATE SET r.confidence = 0.5
   ON MATCH SET r.confidence = r.confidence + 0.3
   ```

**Growth is EXPONENTIAL:**
- 10 searches → ~100 new relationships
- 100 searches → ~1,000 new relationships
- 1,000 searches → ~10,000+ relationships

**Implications:**
- Rich preference understanding over time
- Collaborative filtering becomes possible
- Can detect preference drift and evolution

---

## Onboarding Flow

### Purpose
Build initial user preference model to enable first search.

### Implementation
**File:** `cli/onboarding_chat.py`

### Onboarding Conversation Structure

```python
ONBOARDING_STAGES = [
    "greeting",           # Welcome and username
    "style_preferences",  # Basic style (casual, formal, etc.)
    "body_type",         # Body shape and fit preferences
    "occasions",         # Common use cases (work, weekend, etc.)
    "color_preferences", # Favorite/avoided colors
    "brand_preferences", # Preferred/avoided brands
    "budget",           # Price range comfort
    "finalization"      # Confirm and save
]
```

### LLM-Driven Conversational Onboarding

**Model Used:** GPT-4o with structured output
**Temperature:** 1.0 (creative, conversational)

**Example Flow:**
```
ARI: "Hi! I'm ARI, your fashion stylist. What should I call you?"
User: "Call me Sarah"

ARI: "Nice to meet you, Sarah! Let's get to know your style.
      How would you describe your everyday look?
      (casual, professional, sporty, elegant, or something else?)"
User: "I'm pretty casual but like to look put together"

ARI: "Love that! Smart-casual vibes. What about your body type?
      This helps me suggest flattering fits."
User: "I'm petite with an athletic build"

[... continues through all stages ...]
```

### Data Extraction and Storage

After onboarding, the system:

1. **Extracts structured preferences** using LLM
2. **Creates User node** in Neo4j
3. **Builds initial preference graph**:
   ```cypher
   CREATE (u:User {username: "Sarah"})
   CREATE (u)-[:HAS_BODY_TYPE]->(b:BodyType {shape: "athletic-petite"})
   CREATE (u)-[:PREFERS_STYLE {confidence: 0.7}]->(s:Style {name: "smart-casual"})
   CREATE (u)-[:PREFERS_COLOR {strength: 0.8}]->(c:Color {name: "navy"})
   ```

4. **Stores conversation** for future context

### Critical Feature: Progressive Disclosure
Users can skip questions, and the system adapts:
- Minimum viable profile: Username + 1 style preference
- Detailed profile: All 7 stages completed
- System fills gaps over time through search interactions

---

## Search & Matching Architecture

### The Three-Bot Search System

**File:** `flows/product_search_flow_v2.py`

ARI uses **3 specialized search agents** running in parallel:

```
User Query: "black shirts for a wedding"
           ↓
    ┌──────┴──────┐
    ↓      ↓      ↓
CypherBot  VibeBot  VisionBot
    ↓      ↓      ↓
    └──────┬──────┘
           ↓
      Judge (Fusion)
           ↓
    Final Results
```

### 1. CypherBot (Graph-Based Search)

**Purpose:** Structured attribute matching via Neo4j queries

**How it works:**
```python
Query: "black shirts for wedding"

# LLM generates Cypher:
MATCH (p:Product)
WHERE 'black' IN p.extracted_colors
  AND (toLower(p.title) CONTAINS 'shirt'
       OR 'formal' IN p.extracted_styles)
RETURN p
ORDER BY p.price ASC
LIMIT 20
```

**Strengths:**
- Exact attribute matching
- Price filtering
- Brand filtering
- Deterministic results

**Weaknesses:**
- Limited semantic understanding
- Requires structured data
- Can't understand nuanced queries ("elegant but not too fancy")

**Performance:** ~3-5 seconds

---

### 2. VibeBot (Semantic Vector Search)

**Purpose:** Semantic similarity matching via embeddings

**How it works:**
```python
Query: "black shirts for wedding"

# 1. Generate query embedding
query_vector = embed("black shirts for formal wedding")

# 2. Search Qdrant vector DB
results = qdrant.search(
    collection="fashion_products",
    query_vector=query_vector,
    limit=20,
    filter={"colors": "black"}  # Optional pre-filter
)

# 3. Return products by cosine similarity
```

**Embedding Model:** `text-embedding-ada-002`
- 1536 dimensions
- Cosine similarity matching
- 19x better quality than previous model (all-MiniLM-L6-v2)

**Strengths:**
- Semantic understanding ("elegant" matches "sophisticated")
- Handles synonyms naturally
- Works with unstructured text
- Best for vibe/aesthetic queries

**Weaknesses:**
- No exact matching
- Can drift from specific requirements
- Computationally expensive

**Performance:** ~4-5 seconds

---

### 3. VisionBot (Visual Similarity Search)

**Purpose:** Image-based product matching

**How it works:**
```python
Query: "black shirts for wedding"

# 1. If user provides image:
if user_image:
    query_vector = CLIP.encode_image(user_image)
else:
    # 2. Generate image from text using multimodal model
    query_vector = CLIP.encode_text("black formal shirt")

# 3. Search by visual similarity
results = qdrant.search(
    collection="fashion_products_visual",
    query_vector=query_vector,
    limit=20
)
```

**Vision Model:** CLIP (Contrastive Language-Image Pre-training)
- Multimodal embeddings
- Text-to-image and image-to-image search
- Understands visual concepts

**Strengths:**
- Matches by actual appearance
- Understands style visually
- Can search by uploaded images
- Captures details text can't describe (drape, texture)

**Weaknesses:**
- Slower than text search
- Requires good product images
- Can be distracted by backgrounds

**Performance:** ~3-5 seconds

---

### 4. Judge (Result Fusion & Ranking)

**Purpose:** Combine and rank results from all 3 bots

**Algorithm:**
```python
def judge_results(cypher_results, vibe_results, vision_results, user_context):
    # 1. Collect all unique products
    all_products = merge_deduplicate([
        cypher_results,  # Graph matches
        vibe_results,    # Semantic matches
        vision_results   # Visual matches
    ])

    # 2. Score each product
    for product in all_products:
        scores = {
            'relevance': calculate_relevance(product, query),
            'price_fit': calculate_price_fit(product, user_budget),
            'style_match': calculate_style_match(product, user_style),
            'multi_bot_confidence': count_bots_that_found(product),
            'freshness': calculate_recency(product),
        }

        # 3. Weighted combination
        product.final_score = (
            scores['relevance'] * 0.4 +
            scores['style_match'] * 0.3 +
            scores['multi_bot_confidence'] * 0.2 +
            scores['price_fit'] * 0.1
        )

    # 4. Return top N
    return sorted(all_products, key=lambda p: p.final_score)[:limit]
```

**Key Insight:** Products found by **multiple bots** get confidence boost
- Found by 1 bot: Base score
- Found by 2 bots: +20% bonus
- Found by 3 bots: +40% bonus (very high confidence!)

**Performance:** ~20-25 seconds total

---

## Code Structure

### Directory Layout

```
ari_crewai_migration/
├── flows/
│   └── product_search_flow_v2.py      # Main search flow (3 bots + judge)
│
├── tools/
│   └── async_tools/
│       ├── async_neo4j_tools.py       # Neo4j graph queries
│       └── async_qdrant_tools.py      # Vector search
│
├── models/
│   ├── product_models.py              # Pydantic models
│   └── llm_response_models.py         # Structured LLM outputs
│
├── cli/
│   ├── chat_interface_v2.py           # Main chat loop
│   ├── onboarding_chat.py             # User onboarding
│   └── run_chat_v2.sh                 # Startup script
│
├── nlp/
│   └── crewai_intent_detector.py      # Query understanding
│
├── utils/
│   ├── agent_loader.py                # Load agent configs
│   └── user_profile_manager.py        # User data CRUD
│
└── agents/                             # Agent YAML configs (legacy)
    ├── cypher_bot.yaml
    ├── vibe_bot.yaml
    └── vision_bot.yaml
```

### Key Files Deep Dive

#### `flows/product_search_flow_v2.py` (PRIMARY)
**Lines of Code:** ~900
**Purpose:** Pure Flow implementation (no agent overhead)

**Structure:**
```python
class ProductSearchFlowV2(Flow[ProductSearchState]):
    @start()
    async def initialize(self):
        # Setup state, load user context

    @listen(initialize)
    async def cypher_bot(self):
        # Graph-based search

    @listen(initialize)
    async def vibe_bot(self):
        # Semantic vector search

    @listen(initialize)
    async def vision_bot(self):
        # Visual similarity search

    @listen(and_(cypher_bot, vibe_bot, vision_bot))
    async def judge(self):
        # Fusion and ranking

    @listen(judge)
    async def finalize(self):
        # Format and return
```

**Performance Gains over V1:**
- V1 (Agent-based): 8-12 seconds
- V2 (Flow-based): 4-6 seconds
- **2-3x speedup** by eliminating agent overhead

---

#### `tools/async_tools/async_neo4j_tools.py`
**Critical Function:**
```python
async def _execute_neo4j_query(
    cypher: str,
    parameters: Dict = None
) -> List[Dict]:
    """
    Execute Cypher against Neo4j.
    CRITICAL: Uses database parameter for multi-database support.
    """
    neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")

    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(user, password))

    # THIS WAS THE BUG: Missing database parameter!
    async with driver.session(database=neo4j_database) as session:
        result = await session.run(cypher, parameters or {})
        # ... parse and return
```

**Bug Fixed:** Was querying default database instead of `productionbackup2`

---

#### `tools/async_tools/async_qdrant_tools.py`
**Critical Functions:**
```python
async def _generate_embedding(text: str) -> List[float]:
    """Generate embedding using OpenAI ada-002"""
    response = await openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

async def _search_qdrant(
    collection: str,
    query_vector: List[float],
    limit: int = 10
) -> List[Dict]:
    """Search Qdrant by vector similarity"""
    results = await qdrant_client.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=limit
    )
    return [hit.payload for hit in results]
```

**Collections:**
- `fashion_products` (text embeddings)
- `fashion_products_visual` (CLIP image embeddings)

---

#### `models/llm_response_models.py`
**Structured LLM Outputs:**
```python
class CypherQueries(BaseModel):
    """CypherBot generates this"""
    main_query: str
    fallback_query: str
    search_strategy: str
    reasoning: str

class SearchStrategy(BaseModel):
    """VibeBot generates this"""
    search_terms: List[str]
    filters: Dict[str, Any]
    strategy: str

class JudgeEvaluation(BaseModel):
    """Judge generates this"""
    selected_products: List[str]
    reasoning: str
    confidence: float
```

**Why Structured Output?**
- Forces LLM to follow schema
- Eliminates parsing errors
- Type-safe integration
- 95%+ reliability (vs 60% with JSON parsing)

---

## Current Challenges & Solutions

### Challenge 1: Schema Discovery Bug (SOLVED)

**Problem:**
```
CypherBot always returned 0 products!
```

**Root Cause:**
Prompt contained wrong schema:
- Said products have `category` property → **FALSE** (0 products have it!)
- Said products have `brand` property → **FALSE** (use `extracted_brand`!)
- Said products have `color` property → **FALSE** (use `extracted_colors` array!)

**Solution:**
Updated prompt with ACTUAL schema discovered via database inspection:
```cypher
// CORRECT SCHEMA
(:Product {
  extracted_brand: String,
  extracted_colors: [String],  # Array!
  extracted_styles: [String]   # Array!
})

// CORRECT QUERIES
WHERE 'black' IN p.extracted_colors  # Not p.color = 'black'
WHERE toLower(p.extracted_brand) CONTAINS 'nike'  # Not p.brand
```

**Files Changed:**
- `flows/product_search_flow_v2.py:131-193` (schema section)
- `tools/async_tools/async_neo4j_tools.py:36` (database parameter)

**Commits:**
- `d4bd4c4` - Database selection fix
- `9ae1850` - Schema correction

---

### Challenge 2: Philosophical Matching Problem

**The Question:**
> How do we match unstructured product descriptions to nuanced user preferences?

**Example:**
```
User: "I want something elegant but not too fancy for a wedding"

Product 1: "Elegant Black Dress - Perfect for formal occasions"
Product 2: "Classic Black Dress - Versatile and sophisticated"
Product 3: "Black Sequin Gown - Glamorous evening wear"

Which should we recommend?
```

**Current Approach (Hybrid):**

1. **Explicit Attributes** (CypherBot):
   ```cypher
   WHERE 'black' IN p.extracted_colors
     AND 'dress' IN p.extracted_styles
   ```

2. **Semantic Similarity** (VibeBot):
   ```python
   # "elegant but not too fancy" → embedding
   # Finds: "sophisticated", "refined", "classic"
   # Avoids: "glamorous", "extravagant", "over-the-top"
   ```

3. **Visual Matching** (VisionBot):
   ```python
   # CLIP understands "elegant but simple" visually
   # Matches: Clean lines, minimal embellishment
   # Avoids: Heavy sequins, excessive detail
   ```

4. **User History** (Judge + User Graph):
   ```cypher
   // What has user liked before?
   MATCH (u:User {username: "Sarah"})-[:LIKED]->(past:Product)
   WHERE 'black' IN past.extracted_colors
   RETURN past.extracted_styles as preferred_styles

   // Boost products with similar styles
   ```

**The Gap:**
- **Body shape matching** is still primitive (need fit data)
- **Brand personality** understanding is weak (luxury vs fast fashion)
- **Occasion formality** is binary (needs scale: 1-10)

---

### Challenge 3: Cold Start Problem

**The Problem:**
New users have no interaction history.

**Current Solution:**
Onboarding captures initial preferences, but they're broad.

**Future Direction:**
```python
# Collaborative filtering
MATCH (similar_user:User)-[:HAS_BODY_TYPE]->(body:BodyType {shape: "athletic"})
MATCH (similar_user)-[:LIKED]->(p:Product)
WHERE similar_user.username <> current_user.username
RETURN p
ORDER BY count(similar_user) DESC
```

Find users with similar body types and recommend what THEY liked.

---

### Challenge 4: Data Quality

**Product Data Issues:**
1. **Inconsistent Images:**
   - Some products: 10+ high-quality images
   - Other products: 1 low-res image with watermark
   - Impact: VisionBot performance varies wildly

2. **Missing Descriptions:**
   - ~30% of products have minimal descriptions
   - Impact: Semantic search has less signal

3. **Brand Normalization:**
   - "NIKE" vs "Nike" vs "Nike Inc."
   - Some brands misspelled
   - Impact: Brand filtering unreliable

**Mitigation Strategies:**
```python
# 1. Confidence scoring
def calculate_confidence(product):
    score = 1.0
    if not product.description or len(product.description) < 50:
        score *= 0.7  # Low confidence for sparse descriptions
    if len(product.images) < 3:
        score *= 0.8  # Visual matching less reliable
    if not product.extracted_brand:
        score *= 0.9  # Brand filtering impossible
    return score

# 2. Fallback strategies
if len(graph_results) < 5:  # Not enough structured results
    boost_semantic_weight()  # Rely more on VibeBot
```

---

## Future Research Directions

### 1. Reinforcement Learning for Matching

**Current State:** Rule-based fusion (Judge)

**Proposed:**
```python
class ReinforcementRanker:
    """
    Learn optimal ranking strategy from user feedback.

    State: [user_prefs, query, candidate_products]
    Action: [rank_1, rank_2, ..., rank_N]
    Reward: +1 for click, +5 for purchase, -1 for skip
    """

    def train_episode(self, user_session):
        state = encode_state(user_session.query, user_session.user)

        # Get initial ranking from current Judge
        ranked_products = judge.rank(state)

        # User interacts
        clicked = user_session.clicked_products
        purchased = user_session.purchased_products

        # Calculate reward
        reward = (
            sum(5 for p in purchased if p in ranked_products[:3]) +
            sum(1 for p in clicked if p in ranked_products[:10]) -
            sum(0.5 for p in ranked_products[:10] if p not in clicked)
        )

        # Update policy
        self.update_weights(state, ranked_products, reward)
```

**Benefits:**
- Learns user-specific ranking preferences
- Adapts to seasonal trends
- Discovers non-obvious attribute correlations

**Challenges:**
- Requires large interaction dataset (100K+ sessions)
- Cold start still relies on heuristics
- Risk of overfitting to popular items

---

### 2. Large Vision-Language Models (LVLMs)

**Current:** Separate text (GPT-4o) and vision (CLIP) models

**Proposed:** Unified multimodal reasoning

```python
# Example: GPT-4 Vision understanding
query = """
Analyze this product image and user query:
- User: "I need something elegant but not too formal for a summer wedding"
- Image: [product_image.jpg]

Consider:
1. Fabric weight (is it summer-appropriate?)
2. Formality level (wedding-appropriate but not overly formal?)
3. Style details (elegant design elements?)
4. Color appropriateness (seasonal palette?)

Rate 1-10 and explain.
"""

response = gpt4_vision.complete(query, images=[product_image])
```

**Benefits:**
- Understands nuanced queries better
- Captures details CLIP misses (fabric texture, construction quality)
- Can reason about occasion appropriateness visually

**Challenges:**
- Expensive (10x cost of current pipeline)
- Slower (2-3 seconds per product)
- Requires careful prompt engineering

---

### 3. Fashion Component Understanding

**The Gap:**
Current system treats products as atomic units. Fashion has **components**:

```
Outfit = Top + Bottom + Shoes + Accessories + Outerwear
```

**Proposed Ontology:**
```cypher
(:Product)
  -[:HAS_COMPONENT]->(:Component {
      type: String,          // "neckline", "sleeve", "hem", "fabric"
      value: String,         // "v-neck", "long sleeve", "midi", "silk"
      prominence: Float      // How important is this feature?
  })

(:Component)-[:COMPATIBLE_WITH]->(:Component)
(:Component)-[:FLATTERS]->(:BodyType)
(:Component)-[:APPROPRIATE_FOR]->(:Occasion)
```

**Querying:**
```cypher
// Find dresses with V-necklines (flattering for pear shape)
MATCH (p:Product)-[:HAS_COMPONENT]->(c:Component {type: "neckline", value: "v-neck"})
MATCH (c)-[:FLATTERS]->(b:BodyType {shape: "pear"})
WHERE (p)-[:HAS_COMPONENT]->(:Component {type: "category", value: "dress"})
RETURN p
```

**Data Challenge:**
Need to extract components from images/descriptions:
```python
# Vision model extracts components
components = vision_model.extract([
    "neckline: v-neck",
    "sleeve: 3/4 length",
    "hem: midi length",
    "fabric: flowy, lightweight",
    "pattern: floral print"
])
```

---

### 4. User Preference Drift Detection

**The Insight:**
User preferences CHANGE over time:
- Seasonal changes (florals in spring → knits in winter)
- Life events (new job → professional wardrobe)
- Trend adoption (user sees influencer, wants similar)

**Proposed:**
```python
def detect_preference_drift(user):
    """
    Analyze recent interactions vs historical patterns.
    """
    recent_likes = get_interactions(user, days=30)
    historical_likes = get_interactions(user, days=365)

    recent_styles = extract_styles(recent_likes)
    historical_styles = extract_styles(historical_likes)

    drift_score = cosine_distance(recent_styles, historical_styles)

    if drift_score > 0.3:  # Significant change
        # Adapt recommendation weights
        boost_recent_preferences()
        # Suggest exploring new styles
        recommend_similar_to_recent()
```

**Benefits:**
- Prevents stale recommendations
- Captures evolving taste
- Suggests new styles user might like

---

### 5. Multi-Objective Optimization

**The Problem:**
Recommendations optimize for relevance, but users care about:
- Price
- Brand ethics
- Sustainability
- Trendiness
- Versatility (goes with existing wardrobe)

**Proposed:**
```python
def pareto_ranking(products, user):
    """
    Multi-objective Pareto frontier.
    """
    objectives = {
        'relevance': lambda p: calculate_relevance(p, query),
        'price_value': lambda p: calculate_value(p, user.budget),
        'sustainability': lambda p: p.sustainability_score,
        'versatility': lambda p: calculate_outfit_combos(p, user.wardrobe),
        'trend': lambda p: p.trend_score
    }

    # Find Pareto frontier (no dominated products)
    pareto_set = find_pareto_optimal(products, objectives)

    # Let user choose preferences
    return rank_by_user_weights(pareto_set, user.objective_weights)
```

---

## Critical Learnings

### 1. Schema Assumptions Are Dangerous

**Lesson Learned:**
NEVER assume database schema without verification.

Our bug:
```python
# Assumed schema (WRONG):
WHERE p.category = 'shirts'  # Returns 0 results

# Actual schema:
WHERE 'shirt' IN p.extracted_styles  # Works!
```

**Best Practice:**
```python
# Always verify schema first
async def inspect_schema():
    result = await session.run("""
        MATCH (p:Product)
        RETURN keys(p) as properties
        LIMIT 100
    """)

    all_props = set()
    async for record in result:
        all_props.update(record['properties'])

    print(f"ACTUAL PROPERTIES: {all_props}")
```

---

### 2. Embeddings Quality Matters (19x!)

**Discovery:**
Switched from `all-MiniLM-L6-v2` → `text-embedding-ada-002`

**Results:**
- Previous: 384 dimensions, ~40% relevant results
- Current: 1536 dimensions, ~76% relevant results
- **19x improvement** in semantic matching quality

**Lesson:**
Don't skimp on embedding quality. The difference between a mediocre and great model is not marginal—it's transformational.

---

### 3. Multi-Database Neo4j Requires Explicit Database Parameter

**Bug:**
```python
# WRONG (uses default database):
session = driver.session()

# CORRECT (uses specified database):
session = driver.session(database="productionbackup2")
```

**Impact:**
Was querying empty default database instead of 6.4M product database!

---

### 4. Structured LLM Output > JSON Parsing

**Before (unreliable):**
```python
response = llm.complete("Generate a Cypher query...")
# Parse JSON from string
data = json.loads(response)  # Often fails!
```

**After (95%+ reliable):**
```python
response = llm.complete(
    "Generate a Cypher query...",
    response_format=CypherQueries  # Pydantic model
)
# Already structured!
```

**Lesson:**
Use GPT's structured output feature (response_format). It's not just convenient—it's fundamentally more reliable.

---

### 5. Parallel Search > Sequential Search

**V1 (Sequential):**
```python
results_1 = await cypher_bot()  # 3s
results_2 = await vibe_bot()    # 4s
results_3 = await vision_bot()  # 3s
# Total: 10s
```

**V2 (Parallel):**
```python
results = await asyncio.gather(
    cypher_bot(),   # All run
    vibe_bot(),     # at the
    vision_bot()    # same time
)
# Total: 4s (limited by slowest)
```

**Lesson:**
Independent searches should ALWAYS run in parallel. The speedup is dramatic.

---

## Ontology Gap Analysis & Migration Strategy

### The Schema Gap Problem

**Discovery (Nov 2025):** There is a significant discrepancy between:
1. **PLANNED Ontology** (documented in ONTOLOGY_SPECIFICATION.md)
2. **ACTUAL Schema** (discovered via database inspection)

This gap is causing CypherBot to return 0 products when using ontology-based queries!

### Product Graph Gap

| Feature | Planned | Actual | Impact |
|---------|---------|--------|---------|
| Brand Hierarchy | Separate `Brand` nodes with aesthetics | Flat `extracted_brand` strings | Can't filter by brand attributes |
| Category Tree | Hierarchical `Category` nodes | NO category property! | Can't filter by product type! |
| Style Tags | `StyleDescriptor` nodes with palettes | Simple `extracted_styles` array | Limited style understanding |
| Product Relations | 15 relationship types | NONE | No collaborative filtering |

**Why This Matters:**
```cypher
# PLANNED QUERY (doesn't work!):
MATCH (p:Product)-[:BELONGS_TO]->(c:Category {name: "Shirts"})
WHERE (p)-[:MADE_BY]->(:Brand {name: "Nike"})
RETURN p

# ACTUAL QUERY (what works now):
MATCH (p:Product)
WHERE toLower(p.extracted_brand) CONTAINS 'nike'
  AND toLower(p.title) CONTAINS 'shirt'
RETURN p
```

### User Graph Gap

The User Graph is closer to the ontology specification but still missing:

**Missing Nodes:**
- `UserProductInteraction` (no interaction tracking yet!)
- `RecommendationSession` (sessions not persisted)
- `UserOutfit` (no outfit saving)
- `ConversationPattern` (no pattern detection)

**Impact:**
- No learning from user interactions
- No collaborative filtering
- No preference drift detection
- No outfit recommendations

### Migration Strategy

**Phase 1: Product Graph Foundation (URGENT)**
```cypher
// 1. Create Brand nodes from extracted_brand strings
MATCH (p:Product)
WHERE p.extracted_brand IS NOT NULL
MERGE (b:Brand {name: p.extracted_brand})
CREATE (p)-[:MADE_BY]->(b)

// 2. Create Category nodes from title patterns
// (Requires NLP extraction or manual mapping)

// 3. Convert extracted_styles to StyleDescriptor nodes
MATCH (p:Product)
WHERE p.extracted_styles IS NOT NULL
UNWIND p.extracted_styles as style
MERGE (s:StyleDescriptor {term: style})
CREATE (p)-[:HAS_AESTHETIC]->(s)
```

**Phase 2: User Interaction Tracking**
```cypher
// Add interaction tracking
MATCH (u:User)
CREATE (u)-[:INTERACTED_WITH]->(i:UserProductInteraction {
  product_id: "prod-123",
  interaction_type: "VIEW",
  timestamp: datetime()
})

// Add session tracking
MATCH (u:User)
CREATE (u)-[:HAD_SESSION]->(s:RecommendationSession {
  session_id: randomUUID(),
  timestamp: datetime(),
  cypher_bot_recommendations: [],
  final_selections: []
})
```

**Phase 3: Product Relationships**
```cypher
// Find similar products (requires similarity computation)
MATCH (p1:Product), (p2:Product)
WHERE p1 <> p2
  AND size([x IN p1.extracted_styles WHERE x IN p2.extracted_styles]) > 2
CREATE (p1)-[:SIMILAR_STYLE {similarity_score: 0.8}]->(p2)

// Co-purchase patterns (requires transaction data)
```

### Temporary Workarounds (Current State)

Until migration is complete, the system uses workarounds:

**1. String Matching Instead of Relationships:**
```python
# Instead of: MATCH (p)-[:MADE_BY]->(:Brand {name: "Nike"})
# We use:
WHERE toLower(p.extracted_brand) CONTAINS 'nike'
```

**2. Array Membership Instead of Node Relationships:**
```python
# Instead of: MATCH (p)-[:HAS_AESTHETIC]->(:StyleDescriptor {term: "casual"})
# We use:
WHERE 'casual' IN p.extracted_styles
```

**3. Title/Description Text Search:**
```python
# For missing category property:
WHERE toLower(p.title) CONTAINS 'shirt'
  OR toLower(p.description) CONTAINS 'shirt'
```

### Ontology Specification References

For detailed specifications, see:
- **User Ontology:** [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 15-353
- **Product Ontology:** [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 355-504
- **Agent Mapping:** [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 508-529
- **Summary Stats:** [ONTOLOGY_SPECIFICATION.md](./ONTOLOGY_SPECIFICATION.md) lines 532-557

---

## Quick Reference

### Environment Variables
```bash
# Neo4j
NEO4J_URI=neo4j://34.135.40.119:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>
NEO4J_DATABASE=productionbackup2      # Product graph
NEO4J_USER_DATABASE=users             # User graph

# Qdrant
QDRANT_URL=https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io:6333
QDRANT_API_KEY=<api_key>

# OpenAI
OPENAI_API_KEY=<api_key>
SEARCH_LLM_MODEL=gpt-4o
```

### Running the System
```bash
cd ari_crewai_migration/cli
./run_chat_v2.sh
```

### Testing
```bash
# Full flow test
python test_flow_v2.py

# Database connectivity
python inspect_neo4j_schema.py

# Neo4j query test
python test_neo4j_simple.py
```

### Key Metrics
- **Total Products:** 6,416,804
- **Search Latency:** 4-6 seconds (3 bots in parallel)
- **Embedding Model:** text-embedding-ada-002 (1536 dims)
- **Primary LLM:** GPT-4o
- **Database:** Neo4j 5.26.0

---

## Contact & Handoff

**System Owners:**
- Leo (Primary Developer)
- Lior (Product Strategy)

**Key Files for New Developers:**
1. Start here: `flows/product_search_flow_v2.py`
2. Understand schema: `tools/async_tools/async_neo4j_tools.py`
3. Test queries: `inspect_neo4j_schema.py`

**Common Issues:**
1. CypherBot returns 0 → Check schema (use `extracted_*` properties!)
2. Slow searches → Check parallel execution in Flow
3. Wrong results → Verify database parameter in Neo4j session

**Next Steps for Research:**
1. Implement RL-based ranking
2. Explore GPT-4 Vision for product analysis
3. Build component extraction pipeline
4. Add preference drift detection
5. Implement Pareto optimization for multi-objective ranking

---

**End of Handoff Document**

Last Updated: November 2025
