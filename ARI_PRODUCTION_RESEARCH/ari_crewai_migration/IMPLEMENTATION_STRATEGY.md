# User Onboarding Implementation Strategy

## Current State Analysis

### What You Already Have

Your codebase **already has a user knowledge graph system** at `/services/user/knowledge_graph.py`!

**Existing Infrastructure:**
-  `UserKnowledgeGraphService` - Async Neo4j service (878 lines)
-  User nodes with basic profile data
-  Product interaction tracking (VIEWED, PURCHASED, etc.)
-  User preference system (categories, brands, colors, budget)
-  User segments (BELONGS_TO relationships)
-  Style profiles (HAS_STYLE relationships)
-  Connection pooling, retry logic, health checks
-  Schema creation with constraints and indexes

**Current Schema:**
```cypher
(:User)
  [:HAS_PREFERENCE]→(:UserPreference)
  [:HAS_INTERACTION]→(:ProductInteraction)
  [:BELONGS_TO]→(:UserSegment)
  [:HAS_STYLE]→(:StyleProfile)
```

**User Properties Currently Tracked:**
- Basic: id, email, name, location, age_group, gender
- Behavioral: total_interactions, total_purchases, lifetime_value
- Temporal: created_at, last_active, updated_at

### What's Missing (From Our Enhanced Design)

Comparing to the circular diagram schema, you need:

**Missing Nodes:**
-  `:Demographic` (income, education, occupation, marital_status)
-  `:Personality` (style_archetype, fashion_confidence, values)
-  Separate `:Brand`, `:Color`, `:Occasion` nodes (currently just preferences)
-  `:SocialProfile` (Instagram, Facebook connections)

**Missing Relationships:**
-  `User-[:FOLLOWS]→User` (social graph)
-  `User-[:INSPIRED_BY]→User`
-  `User-[:SIMILAR_TO {score}]→User` (for recommendations)
-  `User-[:CONNECTED_TO {platform}]→SocialProfile`
-  `User-[:LOVES_BRAND]→Brand`
-  `User-[:AVOIDS_BRAND]→Brand`
-  `User-[:DRESSES_FOR]→Occasion`

**Missing Features:**
-  Vector embeddings (style_embedding, profile_embedding)
-  Social auth integration (Facebook/Instagram OAuth)
-  Onboarding flow (multi-step wizard)
-  MCP server for Meta Graph API
-  Integration with ProductSearchFlow (user_id parameter)

---

## Strategic Options

### Option A: Prototype First (RECOMMENDED)

**Approach:** Build enhanced schema in parallel, test, then migrate.

**Pros:**
-  Zero risk to production system
-  Can test and iterate quickly
-  Validate design before committing
-  Side-by-side comparison with existing system
-  Easy rollback if issues arise

**Cons:**
- ⏱ Takes slightly longer (2-3 weeks extra)
-  Requires migration step afterward
-  Duplicate code during transition

**Timeline:** 8-10 weeks total
- Weeks 1-3: Prototype enhanced schema
- Weeks 4-6: Build onboarding flow
- Weeks 7-8: Test and validate
- Weeks 9-10: Migrate production

---

### Option B: Direct Integration (FASTER BUT RISKIER)

**Approach:** Extend existing `UserKnowledgeGraphService` directly.

**Pros:**
-  Faster to production (6-8 weeks)
-  Single codebase, no duplication
-  Lower development cost
-  Immediate benefits

**Cons:**
-  Risk to existing user data
-  Harder to debug issues
-  Can't easily rollback
-  No A/B testing capability

**Timeline:** 6-8 weeks total
- Weeks 1-2: Extend schema in place
- Weeks 3-5: Build onboarding flow
- Weeks 6-8: Test and deploy

---

### Option C: Hybrid (BALANCED)

**Approach:** Prototype new features, integrate incrementally.

**Pros:**
-  Balanced risk/speed
-  Can deploy features progressively
-  Test each feature independently
- ↩ Easy rollback per feature

**Cons:**
-  More complex planning
-  Requires feature flags
-  More testing scenarios

**Timeline:** 7-9 weeks total
- Phase 1: Demographics & Personality (2 weeks)
- Phase 2: Social connections (2 weeks)
- Phase 3: Embeddings & similarity (2 weeks)
- Phase 4: Onboarding flow (2-3 weeks)

---

## Recommended Path: Option A (Prototype First)

### Why This Makes Sense

1. **You have a working system** - Don't break what works
2. **New schema is significantly different** - Separate nodes vs. properties
3. **Can validate with real users** before migration
4. **Your production system has 4.6M products** - High stakes
5. **Test performance** of new graph structure at scale

### Implementation Plan

#### Phase 1: Prototype Module (3 weeks)

**Create new module:** `/ari_crewai_migration/services/enhanced_user_service.py`

```
ari_crewai_migration/
 services/
    user_profile_service.py         # NEW: Enhanced user service
    onboarding_service.py           # NEW: Onboarding orchestration
 models/
    user_models.py                  # NEW: Enhanced Pydantic models
    onboarding_models.py            # NEW: Onboarding flow models
 tools/
    user_profile_tools.py           # NEW: CrewAI tools for user data
    social_auth_tools.py            # NEW: Facebook/Instagram tools
 mcp/
     meta_graph_server.py            # NEW: MCP server (optional)
```

**Tasks:**
- [ ] Create enhanced Neo4j schema (demographics, personality, social)
- [ ] Build `EnhancedUserProfileService` class
- [ ] Implement vector embedding generation and storage
- [ ] Create Pydantic models matching circular diagram
- [ ] Write unit tests for new schema
- [ ] Test with sample data (100 users)
- [ ] Benchmark query performance

**Deliverable:** Working prototype with enhanced schema, isolated from production

---

#### Phase 2: Onboarding Flow (3 weeks)

**Create onboarding system:**

```python
# services/onboarding_service.py

class OnboardingService:
    """
    Multi-step onboarding wizard.
    Collects demographics, psychographics, style preferences.
    """

    async def start_onboarding(self, user_id: str) -> OnboardingSession
    async def collect_demographics(self, session_id: str, data: Demographics) -> bool
    async def collect_personality(self, session_id: str, data: Personality) -> bool
    async def collect_style_quiz(self, session_id: str, answers: StyleQuiz) -> bool
    async def connect_social(self, session_id: str, platform: str, token: str) -> bool
    async def finalize_onboarding(self, session_id: str) -> UserProfile
```

**Tasks:**
- [ ] Design onboarding flow (5-7 steps)
- [ ] Build backend API endpoints
- [ ] Implement social OAuth (Facebook/Instagram)
- [ ] Generate embeddings from onboarding data
- [ ] Create user similarity calculations
- [ ] Write integration tests
- [ ] Build simple frontend prototype (optional)

**Deliverable:** Complete onboarding system writing to prototype schema

---

#### Phase 3: Integration with ProductSearchFlow (2 weeks)

**Modify existing flows to accept user context:**

```python
# flows/product_search_flow.py (ENHANCED)

class ProductSearchState(BaseModel):
    query: str
    filters: Dict[str, Any]
    limit: int = 10
    user_id: Optional[str] = None  # NEW: User context
    user_profile: Optional[UserProfile] = None  # NEW: Profile data

class ProductSearchFlow(Flow[ProductSearchState]):
    """Enhanced with user personalization"""

    @start()
    async def personalize_query(self):
        """NEW: Inject user preferences into query"""
        if self.state.user_id:
            profile = await get_user_profile(self.state.user_id)
            self.state.user_profile = profile
            # Enrich query with user preferences
            self.state.filters.update({
                "preferred_brands": profile.preferences.preferred_brands,
                "budget_range": profile.preferences.budget_range,
                # etc.
            })
```

**Tasks:**
- [ ] Add `user_id` parameter to ProductSearchFlow
- [ ] Create `UserProfileTool` for agents
- [ ] Modify agent prompts to use user context
- [ ] Implement personalized ranking
- [ ] A/B test personalized vs. non-personalized
- [ ] Measure recommendation quality improvement

**Deliverable:** ARI agents now use user profiles for personalization

---

#### Phase 4: Migration & Production Deploy (2 weeks)

**Migrate data from old schema to enhanced schema:**

```python
# migration/user_schema_migration.py

class UserSchemaMigration:
    """Migrate existing user data to enhanced schema"""

    async def migrate_users(self):
        """Migrate all users"""
        old_users = await old_service.get_all_users()
        for user in old_users:
            enhanced_profile = self.transform_user(user)
            await new_service.create_enhanced_user(enhanced_profile)

    def transform_user(self, old_user: Dict) -> UserProfile:
        """Transform old format to new format"""
        # Map old UserPreference → new nodes (Brand, Color, etc.)
        # Generate embeddings for existing users
        # Calculate similarity scores
```

**Tasks:**
- [ ] Write migration scripts
- [ ] Test migration on staging environment
- [ ] Backup production data
- [ ] Run migration (can be done gradually)
- [ ] Update `crewai_orchestrator.py` to use new service
- [ ] Monitor for issues
- [ ] Deprecate old schema (after validation period)

**Deliverable:** Production system using enhanced user profiles

---

## Directory Structure (After Implementation)

```
ARI_PRODUCTION_CAMEL_0.27/
 services/
    user/
        knowledge_graph.py          # LEGACY: Keep for backward compatibility
        enhanced_profile.py         # NEW: Enhanced user service
        migration.py                # NEW: Migration utilities

 ari_crewai_migration/
     services/
        onboarding_service.py       # NEW: Onboarding orchestration
        user_similarity.py          # NEW: User similarity engine
     models/
        user_models.py              # NEW: Enhanced Pydantic models
        onboarding_models.py        # NEW: Onboarding models
     tools/
        user_profile_tools.py       # NEW: User data tools for agents
        social_auth_tools.py        # NEW: OAuth tools
     flows/
        product_search_flow.py      # MODIFIED: Now user-aware
        onboarding_flow.py          # NEW: Onboarding as a flow
     crews/
        crewai_orchestrator.py      # MODIFIED: User context injection
     mcp/
         meta_graph_server.py        # OPTIONAL: MCP server for Meta API
         user_profile_server.py      # OPTIONAL: MCP server for user data
```

---

## Decision Criteria

### Choose Option A (Prototype) If:
-  You want zero risk to production
-  You have 2-3 months timeline
-  You want to test with real users first
-  Performance at scale is unknown
-  Team has bandwidth for prototyping

### Choose Option B (Direct Integration) If:
-  You need it ASAP (< 2 months)
-  You're comfortable with production changes
-  You have strong rollback plan
-  Schema changes are well understood
-  Small user base currently

### Choose Option C (Hybrid) If:
-  You want progressive rollout
-  You can deploy features independently
-  You have feature flag infrastructure
-  You want to A/B test each addition
-  You need some features urgently, others later

---

## My Recommendation

**Go with Option A (Prototype First)** because:

1. **You have production data** - 4.6M products, unknown number of users
2. **Schema is significantly different** - Not just additive changes
3. **Vector embeddings are new** - Need to test performance
4. **Social auth is sensitive** - OAuth requires careful testing
5. **You have time** - Better to do it right than fast

### Next Steps

If you agree with Option A:

1. **Week 1-2:** I'll help you build the enhanced user service prototype
2. **Week 3:** Test with sample data, benchmark queries
3. **Week 4-6:** Build onboarding flow
4. **Week 7-8:** Integration with ProductSearchFlow
5. **Week 9-10:** Migration and production deployment

---

## Quick Start (Minimal Viable Enhancement)

If you want to START IMMEDIATELY with minimal changes:

### Step 1: Add Demographics (1 week)
```python
# Extend existing UserKnowledgeGraphService
async def add_demographics(user_id: str, demographics: Dict):
    query = """
    MATCH (u:User {id: $user_id})
    CREATE (d:Demographic {
        income_range: $income_range,
        education: $education,
        occupation: $occupation
    })
    CREATE (u)-[:HAS_DEMOGRAPHIC]->(d)
    """
```

### Step 2: Add Style Quiz (1 week)
```python
async def complete_style_quiz(user_id: str, answers: Dict):
    # Store as Personality node
    # Generate initial style_embedding
```

### Step 3: Use in ProductSearch (1 week)
```python
# Modify ProductSearchFlow to inject user preferences
```

**Total: 3 weeks for MVP enhancement**

Then iterate and add more features progressively.

---

## Questions for You

1. **Timeline:** How urgent is this? 2 months? 3 months? 6 months?

2. **Risk Tolerance:** Comfortable modifying production user data directly, or prefer prototype?

3. **Current Users:** How many users do you have now? (affects migration complexity)

4. **Social Auth:** Is Facebook/Instagram integration critical, or can you start with just a style quiz?

5. **Priority Features:** What's most important?
   - Demographics collection?
   - Style quiz/psychographics?
   - Social connections?
   - User similarity?
   - All of the above?

6. **Team Size:** Just you, or do you have developers to parallelize work?

Let me know your answers and I'll help you execute the chosen strategy!
