# User Graph Implementation Plan

## Current Situation

- **Product Graph:** 4.6M products (fully operational)
- **User Graph:** Placeholder only (user1, user2 concept - NO real users)
- **Opportunity:** Start fresh with enhanced schema from circular diagram!

---

## Decision: Should We Use MCP + Meta Graph API?

### What Meta Graph API Would Give Us

**User Data from Facebook/Instagram:**
- Demographics: age_range, gender, location, education, work
- Interests: liked pages, brands followed
- Social graph: friends list, connections
- Photos: Visual style analysis from Instagram posts

### Pros of Using Meta Graph API

✅ **Rich data instantly** - Users connect Facebook/Instagram, we get their profile
✅ **Social proof** - Real brand preferences from what they follow
✅ **Visual style analysis** - Analyze their Instagram aesthetic
✅ **Network effects** - "Users like you also like..." recommendations
✅ **Inspiration** - Learn from Meta's graph structure

### Cons of Using Meta Graph API

❌ **Privacy concerns** - Users might not want to share social data
❌ **OAuth complexity** - Facebook OAuth is notoriously difficult
❌ **API limitations** - Strict rate limits, limited data access post-Cambridge Analytica
❌ **Dependency** - Reliant on Meta's API availability
❌ **Development time** - MCP server + OAuth = 2-3 weeks extra
❌ **Approval required** - Facebook App Review process (can take weeks)
❌ **Not fashion-specific** - Generic interests, not style preferences

### My Recommendation: **Skip Meta Graph API for MVP**

**Why:**

1. **You need fashion-specific data**, not generic social data
2. **Onboarding quiz gives better quality** - Direct style preferences vs. inferred
3. **Privacy-first approach** - Users trust you more
4. **Faster to market** - No OAuth complexity
5. **No external dependencies** - You control everything

**Better alternatives:**
- Style quiz (5-7 questions) - Direct fashion preferences
- Pinterest integration - More fashion-focused than Facebook
- Image upload - "Upload inspiration photos"
- Instagram scraper (public data only) - Less invasive than OAuth

**Use Meta Graph API as inspiration for SCHEMA, not as data source.**

---

## Recommended Implementation Path

### Phase 1: Implement Enhanced User Schema (2-3 weeks)

**Update `/services/user/knowledge_graph.py` with enhanced schema:**

```python
class EnhancedUserKnowledgeGraphService(UserKnowledgeGraphService):
    """
    Enhanced user service with full circular diagram schema.
    Extends existing service rather than replacing it.
    """

    async def ensure_enhanced_schema(self) -> bool:
        """Create enhanced schema matching circular diagram."""

        constraints = [
            # Core nodes
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Demographic) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Personality) REQUIRE p.id IS UNIQUE",

            # Preference nodes
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:StylePreference) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Color) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Occasion) REQUIRE o.name IS UNIQUE",

            # Social nodes (for future)
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sp:SocialProfile) REQUIRE sp.id IS UNIQUE",
        ]

        indexes = [
            # User indexes
            "CREATE INDEX IF NOT EXISTS FOR (u:User) ON (u.email)",
            "CREATE INDEX IF NOT EXISTS FOR (u:User) ON (u.created_at)",

            # Vector index for similarity
            "CREATE VECTOR INDEX user_style_embedding IF NOT EXISTS FOR (u:User) ON (u.style_embedding) OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}",

            # Brand/Color/Occasion indexes for fast lookups
            "CREATE INDEX IF NOT EXISTS FOR (b:Brand) ON (b.name)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Color) ON (c.name)",
            "CREATE INDEX IF NOT EXISTS FOR (o:Occasion) ON (o.name)",
        ]

        # Execute constraints and indexes
        # ...

    async def create_enhanced_user(
        self,
        user_id: str,
        email: str,
        demographics: Optional[Dict] = None,
        personality: Optional[Dict] = None,
        style_preferences: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create user with enhanced schema.

        Creates:
        - User node (center)
        - Demographic node + relationship
        - Personality node + relationship
        - StylePreference nodes + relationships
        - Brand/Color/Occasion nodes + relationships
        - Vector embeddings
        """

        query = """
        // Create User
        CREATE (u:User {
            id: $user_id,
            email: $email,
            created_at: datetime(),
            last_active: datetime()
        })

        // Create Demographics if provided
        WITH u
        FOREACH (ignoreMe IN CASE WHEN $demographics IS NOT NULL THEN [1] ELSE [] END |
            CREATE (d:Demographic {
                id: $user_id + '_demo',
                income_range: $demographics.income_range,
                education_level: $demographics.education_level,
                occupation: $demographics.occupation,
                marital_status: $demographics.marital_status
            })
            CREATE (u)-[:HAS_DEMOGRAPHIC]->(d)
        )

        // Create Personality if provided
        WITH u
        FOREACH (ignoreMe IN CASE WHEN $personality IS NOT NULL THEN [1] ELSE [] END |
            CREATE (p:Personality {
                id: $user_id + '_personality',
                style_archetype: $personality.style_archetype,
                fashion_confidence: $personality.fashion_confidence,
                values: $personality.values,
                shopping_behavior: $personality.shopping_behavior,
                brand_affinity: $personality.brand_affinity
            })
            CREATE (u)-[:HAS_PERSONALITY]->(p)
        )

        RETURN u.id as user_id
        """

        params = {
            "user_id": user_id,
            "email": email,
            "demographics": demographics,
            "personality": personality
        }

        result = await self.query(query, params)

        # Add style preferences, brands, colors, occasions
        if style_preferences:
            await self.add_style_preferences(user_id, style_preferences)

        # Generate and store embeddings
        await self.generate_user_embeddings(user_id)

        return {"user_id": user_id, "status": "created"}

    async def add_style_preferences(
        self,
        user_id: str,
        preferences: List[Dict]
    ) -> bool:
        """Add style preferences with relationships to brands, colors, occasions."""

        for pref in preferences:
            query = """
            MATCH (u:User {id: $user_id})

            // Create StylePreference
            CREATE (sp:StylePreference {
                id: randomUUID(),
                category: $category,
                preference_type: $preference_type,
                occasions: $occasions,
                fit_preferences: $fit_preferences,
                color_palette: $color_palette
            })
            CREATE (u)-[:PREFERS_STYLE {strength: $strength}]->(sp)

            // Link to Brands
            WITH u, sp
            UNWIND $brands as brand_name
            MERGE (b:Brand {name: brand_name})
            CREATE (u)-[:LOVES_BRAND]->(b)

            // Link to Colors
            WITH u, sp
            UNWIND $colors as color_name
            MERGE (c:Color {name: color_name})
            CREATE (u)-[:PREFERS_COLOR {intensity: 'primary'}]->(c)

            // Link to Occasions
            WITH u, sp
            UNWIND $occasions as occasion_name
            MERGE (o:Occasion {name: occasion_name})
            CREATE (u)-[:DRESSES_FOR]->(o)
            """

            params = {
                "user_id": user_id,
                "category": pref.get("category"),
                "preference_type": pref.get("preference_type", "loves"),
                "occasions": pref.get("occasions", []),
                "fit_preferences": pref.get("fit_preferences", []),
                "color_palette": pref.get("color_palette", []),
                "strength": pref.get("strength", 0.8),
                "brands": pref.get("brands", []),
                "colors": pref.get("color_palette", [])
            }

            await self.query(query, params)

        return True

    async def generate_user_embeddings(self, user_id: str) -> bool:
        """
        Generate vector embeddings for user profile.
        Uses OpenAI to create semantic representation of user.
        """

        # Get user data
        user_data = await self.get_user_details(user_id)

        # Build profile text
        profile_text = self._build_profile_text(user_data)

        # Generate embedding using OpenAI
        import openai
        embedding_response = await openai.embeddings.create(
            model="text-embedding-3-large",
            input=profile_text
        )

        embedding = embedding_response.data[0].embedding

        # Store in Neo4j
        query = """
        MATCH (u:User {id: $user_id})
        SET u.style_embedding = $embedding,
            u.profile_embedding = $embedding,
            u.embedding_generated_at = datetime()
        """

        await self.query(query, {
            "user_id": user_id,
            "embedding": embedding
        })

        return True

    def _build_profile_text(self, user_data: Dict) -> str:
        """Build text representation of user for embedding."""

        parts = []

        # Demographics
        if user_data.get("age_group"):
            parts.append(f"Age: {user_data['age_group']}")
        if user_data.get("gender"):
            parts.append(f"Gender: {user_data['gender']}")
        if user_data.get("location"):
            parts.append(f"Location: {user_data['location']}")

        # Personality
        prefs = user_data.get("preferences", {})
        if prefs.get("style_attributes"):
            parts.append(f"Style: {', '.join(prefs['style_attributes'])}")
        if prefs.get("preferred_brands"):
            parts.append(f"Loves brands: {', '.join(prefs['preferred_brands'])}")
        if prefs.get("preferred_colors"):
            parts.append(f"Favorite colors: {', '.join(prefs['preferred_colors'])}")

        return " | ".join(parts)

    async def find_similar_users(
        self,
        user_id: str,
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        """
        Find similar users using vector similarity.
        Uses cosine similarity on style_embedding.
        """

        query = """
        MATCH (u1:User {id: $user_id})
        WHERE u1.style_embedding IS NOT NULL

        CALL db.index.vector.queryNodes(
            'user_style_embedding',
            $limit * 2,
            u1.style_embedding
        ) YIELD node as u2, score

        WHERE u2.id <> $user_id AND score >= $min_similarity

        RETURN u2.id as user_id,
               u2.email as email,
               score as similarity_score
        ORDER BY score DESC
        LIMIT $limit
        """

        result = await self.query(query, {
            "user_id": user_id,
            "limit": limit,
            "min_similarity": min_similarity
        })

        return result

    async def link_similar_users(self, user_id: str) -> bool:
        """
        Create SIMILAR_TO relationships based on embeddings.
        Run this periodically or after profile updates.
        """

        similar_users = await self.find_similar_users(user_id, limit=20)

        for similar in similar_users:
            query = """
            MATCH (u1:User {id: $user_id})
            MATCH (u2:User {id: $similar_user_id})
            MERGE (u1)-[r:SIMILAR_TO]->(u2)
            SET r.score = $score,
                r.basis = 'style_preferences',
                r.computed_at = datetime()
            """

            await self.query(query, {
                "user_id": user_id,
                "similar_user_id": similar["user_id"],
                "score": similar["similarity_score"]
            })

        return True
```

**Schema matches your circular HTML diagram exactly!**

---

### Phase 2: Build Onboarding Service (2-3 weeks)

**Create `/ari_crewai_migration/services/onboarding_service.py`:**

```python
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict

class Demographics(BaseModel):
    age_range: str  # "18-24", "25-34", "35-44", etc.
    gender: Optional[str] = None
    location: Optional[str] = None
    income_range: Optional[str] = None
    education_level: Optional[str] = None
    occupation: Optional[str] = None

class Personality(BaseModel):
    style_archetype: str  # "Minimalist", "Boho", "Classic", "Trendy"
    fashion_confidence: int  # 1-10
    values: List[str]  # ["sustainability", "quality", "affordability"]
    shopping_behavior: str  # "impulse", "intentional", "budget-conscious"
    brand_affinity: str  # "luxury", "premium_mid", "fast_fashion"

class StyleQuizAnswer(BaseModel):
    question_id: str
    answer: str
    confidence: float = 1.0

class OnboardingSession(BaseModel):
    session_id: str
    user_id: str
    email: EmailStr
    current_step: int = 1
    total_steps: int = 7
    demographics: Optional[Demographics] = None
    personality: Optional[Personality] = None
    style_quiz_answers: List[StyleQuizAnswer] = []
    completed: bool = False

class OnboardingService:
    """
    Multi-step onboarding wizard.
    NO social auth - just direct questions.
    """

    def __init__(self, user_service: EnhancedUserKnowledgeGraphService):
        self.user_service = user_service
        self.sessions = {}  # In-memory for MVP, move to Redis later

    async def start_onboarding(self, email: str) -> OnboardingSession:
        """Start new onboarding session."""
        user_id = f"user_{uuid.uuid4()}"
        session_id = f"onboard_{uuid.uuid4()}"

        session = OnboardingSession(
            session_id=session_id,
            user_id=user_id,
            email=email
        )

        self.sessions[session_id] = session
        return session

    async def collect_demographics(
        self,
        session_id: str,
        demographics: Demographics
    ) -> OnboardingSession:
        """Step 1: Collect demographics."""
        session = self.sessions[session_id]
        session.demographics = demographics
        session.current_step = 2
        return session

    async def collect_style_quiz(
        self,
        session_id: str,
        answers: List[StyleQuizAnswer]
    ) -> OnboardingSession:
        """Step 2-6: Style quiz (5 questions)."""
        session = self.sessions[session_id]
        session.style_quiz_answers.extend(answers)
        session.current_step = min(session.current_step + len(answers), 6)
        return session

    async def finalize_onboarding(self, session_id: str) -> str:
        """Step 7: Create user in Neo4j."""
        session = self.sessions[session_id]

        # Analyze quiz answers to build Personality
        personality = self._analyze_quiz_answers(session.style_quiz_answers)

        # Extract preferences from quiz
        style_preferences = self._extract_style_preferences(session.style_quiz_answers)

        # Create user in Neo4j
        await self.user_service.create_enhanced_user(
            user_id=session.user_id,
            email=session.email,
            demographics=session.demographics.dict() if session.demographics else None,
            personality=personality.dict(),
            style_preferences=style_preferences
        )

        # Generate embeddings
        await self.user_service.generate_user_embeddings(session.user_id)

        # Find similar users
        await self.user_service.link_similar_users(session.user_id)

        session.completed = True
        return session.user_id

    def _analyze_quiz_answers(self, answers: List[StyleQuizAnswer]) -> Personality:
        """Analyze quiz answers to infer personality."""
        # Simple rule-based system for MVP
        # Later: use LLM to analyze

        style_keywords = []
        values = []

        for answer in answers:
            if "minimalist" in answer.answer.lower():
                style_keywords.append("minimalist")
            if "sustainable" in answer.answer.lower():
                values.append("sustainability")
            # ... more rules

        # Determine archetype
        if "minimalist" in style_keywords:
            archetype = "Minimalist"
        else:
            archetype = "Classic"  # Default

        return Personality(
            style_archetype=archetype,
            fashion_confidence=7,  # Default, can ask in quiz
            values=values or ["quality"],
            shopping_behavior="intentional",
            brand_affinity="premium_mid"
        )

    def _extract_style_preferences(self, answers: List[StyleQuizAnswer]) -> List[Dict]:
        """Extract concrete preferences from quiz."""
        preferences = []

        # Example: If user said "I love black and white"
        # Create: {category: "color", colors: ["black", "white"]}

        # You'd parse answers here
        # For MVP, return some defaults

        return [
            {
                "category": "dress",
                "preference_type": "loves",
                "occasions": ["work", "casual"],
                "fit_preferences": ["fitted", "midi"],
                "color_palette": ["black", "navy", "white"],
                "brands": ["Everlane", "COS"],
                "strength": 0.9
            }
        ]
```

---

### Phase 3: Sample Onboarding Questions (Fashion-Specific)

**Step 1: Demographics (1-2 questions)**
```
Q1: What's your age range?
- 18-24, 25-34, 35-44, 45-54, 55+

Q2: Where are you based?
- [City input]
```

**Step 2-6: Style Quiz (5 questions)**
```
Q1: Describe your style in 3 words
- [Free text input]
- Later: Parse with LLM to extract style_archetype

Q2: What occasions do you dress for most?
- [Multi-select: Work, Casual, Date Night, Formal Events, Travel, Fitness]

Q3: Which brands do you love? (Select all that apply)
- [Grid of brand logos: Everlane, COS, Zara, H&M, Mango, Uniqlo, etc.]
- [+ "Add custom brand" input]

Q4: What colors do you gravitate toward?
- [Color palette selector: visual interface]

Q5: Upload 1-3 inspiration photos
- [File upload or paste image URL]
- Later: Analyze with vision model to extract style attributes
```

**Step 7: Review & Submit**
```
Review your style profile:
- Demographics: ✓
- Style: Minimalist, loves Everlane & COS
- Colors: Black, white, navy
- Occasions: Work, casual

[Finalize Profile]
```

---

### Phase 4: Integration with ProductSearchFlow (1-2 weeks)

**Modify existing flow to use user profiles:**

```python
# flows/product_search_flow.py

from models.product_models import ProductSearchState
from services.user.knowledge_graph import EnhancedUserKnowledgeGraphService

class ProductSearchFlow(Flow[ProductSearchState]):
    """Enhanced with user context."""

    def __init__(self, user_service: EnhancedUserKnowledgeGraphService):
        super().__init__()
        self.user_service = user_service

    @start()
    async def inject_user_context(self):
        """NEW: Fetch user profile and inject into query."""

        if self.state.user_id:
            # Get user profile
            profile = await self.user_service.get_user_details(self.state.user_id)

            # Enrich filters with user preferences
            self.state.filters.update({
                "preferred_brands": profile["preferences"]["preferred_brands"],
                "preferred_colors": profile["preferences"]["preferred_colors"],
                "budget_max": profile["preferences"]["budget_range"].get("max"),
                "excluded_items": profile["preferences"]["excluded_items"]
            })

            # Add user context to agent prompts
            self.state.user_context = f"""
            User Style Profile:
            - Archetype: {profile.get('style_profile', 'Unknown')}
            - Loves: {', '.join(profile['preferences']['preferred_brands'][:3])}
            - Occasions: {', '.join(profile['preferences']['preferred_tags'])}
            - Budget: ${profile['preferences']['budget_range'].get('min')}-${profile['preferences']['budget_range'].get('max')}
            """

        return await self.parallel_search_step()
```

---

## Timeline Summary

**Total: 6-8 weeks (WITHOUT Meta Graph API)**

1. **Weeks 1-3:** Implement enhanced user schema in Neo4j
2. **Weeks 4-6:** Build onboarding service + quiz
3. **Weeks 7-8:** Integration with ProductSearchFlow + testing

**If you want Meta Graph API later:** +2-3 weeks

---

## Decision Matrix

### Start WITHOUT Meta Graph API

✅ **Start with:**
- Enhanced Neo4j schema (circular diagram)
- Simple onboarding quiz (5-7 questions)
- Direct style preferences
- Vector embeddings for similarity
- User-aware product search

✅ **Add LATER if needed:**
- Pinterest integration (more fashion-focused)
- Instagram public profile scraping
- Image upload + vision analysis
- Meta Graph API (after Facebook App Review)

### Key Principle: **Own Your Data**

Build your own user preference graph based on fashion-specific questions, not generic social data. This gives you:
- Better quality data
- Privacy compliance
- No external dependencies
- Faster development
- User trust

---

## Next Steps

1. **Do you agree with skipping Meta Graph API for MVP?**

2. **Should I start implementing the enhanced user schema?**
   - Extend `knowledge_graph.py` with enhanced methods
   - Add vector embeddings support
   - Create sample onboarding questions

3. **What's most urgent:**
   - Schema implementation?
   - Onboarding quiz design?
   - Integration with existing flows?

Let me know and I'll start building!
