# User Onboarding Research: Meta API Integration & Neo4j User Profiles

## Overview

This document outlines research findings and implementation plans for building a user onboarding system that collects social, demographic, and psychographic data. The system will be inspired by Meta's Graph API structure and implemented using Neo4j for user profile storage, with eventual integration into the ARI fashion recommendation system.

---

## 1. Meta Graph API Structure Analysis

### What Meta Tracks (User Profile Fields)

Meta's Graph API v22.0 structures user data in a graph format with these key components:

**Identity & Demographics:**
- `id`, `name`, `first_name`, `last_name`, `email`
- `age_range`, `birthday`, `gender`
- `hometown`, `location` (current city)
- `languages`, `timezone`, `locale`

**Social Graph:**
- `friends` - Friend relationships
- `family` - Family member connections
- `accounts` - Connected pages/accounts

**Interests & Psychographics:**
- `likes` - Pages/brands liked
- `favorite_athletes`, `favorite_teams`
- `inspirational_people`
- `interests` - Topics of interest
- `music`, `books`, `movies`, `television`

**Behavioral Data:**
- `feed` - User's timeline posts
- `photos`, `videos` - Media content
- `events` - Event attendance/RSVPs
- `groups` - Group memberships

**Professional:**
- `education` - Schools attended
- `work` - Employment history

### Key Architectural Insights

1. **Graph-First Design** - Everything is a node with edges (relationships)
2. **Permissioned Access** - Different OAuth scopes for different data types
3. **Discoverable Schema** - Use `?metadata=1` to discover available fields dynamically
4. **Relationship Types** - FRIENDS_WITH, WORKS_AT, LIKES, ATTENDED, etc.

---

## 2. MCP (Model Context Protocol) Capabilities

### What is MCP?

MCP is Anthropic's open standard (launched Nov 2024) that standardizes how AI systems access external APIs and data sources. Think of it as "USB-C for AI" - one protocol for all integrations.

### Key Features for This Use Case

**Architecture:**
```
Claude/LLM Application (Host)
    ↓
MCP Client (built-in)
    ↓
MCP Server (custom connector) ←→ Meta Graph API
```

**Advantages Over Traditional API Integration:**
- Standardized tool discovery (LLM auto-discovers available functions)
- Built on JSON-RPC 2.0 (structured communication)
- OAuth 2.0 support built-in
- One MCP server = works with any MCP-compatible LLM

### Implementation Approaches

**Option 1: FastMCP (Python) - Recommended**
```python
from fastmcp import FastMCP
from fastmcp.server.auth import GoogleProvider, CustomOAuthProvider

# Facebook OAuth adapter
auth = CustomOAuthProvider(
    client_id="your_fb_app_id",
    client_secret="your_fb_secret",
    authorization_endpoint="https://www.facebook.com/v22.0/dialog/oauth",
    token_endpoint="https://graph.facebook.com/v22.0/oauth/access_token"
)

mcp = FastMCP("Facebook Profile Connector", auth=auth)

@mcp.tool()
async def fetch_user_profile(fields: list[str]) -> dict:
    """Fetch user profile data from Facebook Graph API"""
    # Call Meta Graph API
    # Return structured data
    pass

@mcp.tool()
async def fetch_user_interests(user_id: str) -> list[dict]:
    """Fetch user's interests and likes"""
    pass
```

**Option 2: Official MCP Python SDK**
- More control, more verbose
- Better for complex authentication flows
- Example in official repo: github.com/modelcontextprotocol/python-sdk

**Option 3: Use Existing MCP Servers**
- Check if community has built Facebook Graph API MCP server
- Anthropic maintains servers for: Google Drive, Slack, GitHub, Postgres

---

## 3. Proposed Neo4j User Profile Schema

### Inspired by Meta, Optimized for ARI Fashion

**Node Types:**

```cypher
// Core user profile
(:User {
  id: "uuid",
  email: "user@example.com",
  first_name: "Jane",
  last_name: "Doe",
  age_range: "25-34",
  gender: "female",
  location: "New York, NY",
  timezone: "America/New_York",
  joined_at: datetime(),
  last_active: datetime()
})

// Demographics
(:Demographic {
  income_range: "75k-100k",
  education_level: "Bachelor's",
  occupation: "Marketing Manager",
  marital_status: "single"
})

// Psychographics
(:Personality {
  style_archetype: "Minimalist",
  fashion_confidence: 7,  // 1-10 scale
  values: ["sustainability", "quality", "versatility"],
  shopping_behavior: "intentional",
  brand_affinity: "premium_mid"
})

// Fashion Interests
(:StylePreference {
  category: "dress",
  preference_type: "loves",
  occasions: ["work", "date_night"],
  fit_preferences: ["fitted", "midi"],
  color_palette: ["black", "navy", "burgundy"]
})

(:Brand {
  name: "Everlane",
  preference_level: "favorite"  // favorite/interested/avoid
})

(:Color {
  name: "burgundy",
  hex: "#800020"
})

(:Occasion {
  name: "wedding_guest",
  formality_level: "semi-formal"
})

// Social connections
(:SocialProfile {
  platform: "instagram",
  username: "@janedoe",
  follower_count: 2500,
  profile_url: "...",
  connected_at: datetime()
})
```

**Relationship Types:**

```cypher
// Demographics
(User)-[:HAS_DEMOGRAPHIC]->(Demographic)

// Psychographics
(User)-[:HAS_PERSONALITY]->(Personality)

// Style preferences
(User)-[:PREFERS_STYLE {strength: 0.9}]->(StylePreference)
(User)-[:LOVES_BRAND]->(Brand)
(User)-[:AVOIDS_BRAND]->(Brand)
(User)-[:PREFERS_COLOR {intensity: "primary"}]->(Color)
(User)-[:DRESSES_FOR]->(Occasion)

// Social graph
(User)-[:CONNECTED_TO {platform: "instagram"}]->(SocialProfile)
(User)-[:FOLLOWS {platform: "instagram"}]->(User)
(User)-[:INSPIRED_BY]->(User)

// Behavioral
(User)-[:VIEWED]->(Product {timestamp: datetime(), duration_seconds: 45})
(User)-[:PURCHASED]->(Product {timestamp: datetime(), price: 89.99})
(User)-[:SAVED]->(Product)
(User)-[:SHARED]->(Product {platform: "instagram"})

// Similarity (for recommendations)
(User)-[:SIMILAR_TO {score: 0.85, basis: "style_preferences"}]->(User)
```

### Schema Design Principles

1. **Query-First Design** - Based on questions you'll ask:
   - "Find users with similar style to user X"
   - "What occasions does this user dress for?"
   - "Which users love sustainable brands?"

2. **Embeddings-Ready** - Store vector embeddings for semantic matching:
   ```cypher
   (:User {
     style_embedding: [0.23, -0.45, ...],  // 1536-dim vector
     profile_embedding: [...]
   })
   ```

3. **Temporal Tracking** - Preferences evolve over time:
   ```cypher
   (User)-[:PREFERS_STYLE {
     strength: 0.9,
     created_at: datetime(),
     last_reinforced: datetime(),
     decay_rate: 0.95
   }]->(StylePreference)
   ```

---

## 4. Implementation Plan

### Phase 1: MCP Server for Meta Graph API

**MCP Server Foundation**
- [ ] Set up FastMCP development environment
- [ ] Implement Facebook OAuth 2.0 authentication flow
- [ ] Create basic tools:
  - `fetch_user_profile()` - Basic profile data
  - `fetch_user_interests()` - Likes and interests
  - `fetch_user_demographics()` - Age, location, etc.
- [ ] Test with Claude Code IDE

**Advanced Integration**
- [ ] Add tools for:
  - `fetch_user_friends()` - Social graph
  - `fetch_user_photos()` - Visual style analysis
  - `analyze_fashion_content()` - Parse fashion posts
- [ ] Implement caching (Redis) for API rate limiting
- [ ] Error handling and retry logic
- [ ] Unit tests

**Deployment**
- [ ] Deploy MCP server (Docker container recommended)
- [ ] Document OAuth setup for users
- [ ] Integration testing with ARI system
- [ ] Security audit (OAuth token handling)

### Phase 2: Neo4j User Profile Schema

**Schema Design**
- [ ] Design comprehensive Cypher schema
- [ ] Create indices:
  ```cypher
  CREATE INDEX user_email FOR (u:User) ON (u.email)
  CREATE INDEX user_id FOR (u:User) ON (u.id)
  CREATE VECTOR INDEX user_style_embedding FOR (u:User) ON (u.style_embedding)
  ```
- [ ] Design constraint system:
  ```cypher
  CREATE CONSTRAINT user_email_unique FOR (u:User) REQUIRE u.email IS UNIQUE
  ```
- [ ] Migration scripts for existing data

**CRUD Operations**
- [ ] Build Python service layer:
  - `UserProfileService` - CRUD operations
  - `StylePreferenceService` - Manage style data
  - `SocialGraphService` - Handle connections
- [ ] Pydantic models (matching existing pattern):
  ```python
  class UserProfile(BaseModel):
      id: str
      email: EmailStr
      demographics: Optional[Demographics]
      style_preferences: List[StylePreference]
      social_profiles: List[SocialProfile]
  ```

**Integration**
- [ ] Connect MCP server → Neo4j write pipeline
- [ ] Data validation and sanitization
- [ ] Privacy controls (GDPR compliance)
- [ ] Backup and recovery procedures

### Phase 3: Onboarding Flow

**UI/UX Design**
- [ ] Design multi-step onboarding wizard:
  1. Social auth (Facebook/Instagram OAuth)
  2. Demographics questionnaire
  3. Style quiz (psychographics)
  4. Brand preferences
  5. Occasion/lifestyle questions
- [ ] Wireframes and user flow
- [ ] Progress indicators

**Frontend Implementation**
- [ ] Build onboarding interface (framework of your choice)
- [ ] Integrate Facebook Login SDK
- [ ] Form validation and error handling
- [ ] Mobile-responsive design

**Backend Integration**
- [ ] API endpoints for onboarding data collection
- [ ] MCP server integration for social data fetch
- [ ] Neo4j write operations
- [ ] Session management

**Testing & Optimization**
- [ ] User testing (5-10 beta users)
- [ ] A/B test completion rates
- [ ] Performance optimization
- [ ] Analytics tracking (completion funnel)

### Phase 4: Embedding & ARI Integration

**Vector Embeddings**
- [ ] Generate user profile embeddings:
  ```python
  # Combine demographics + psychographics + preferences
  profile_text = f"""
  User: {age_range} {gender} from {location}
  Style: {style_archetype}, loves {brands}
  Occasions: {occasions}
  Values: {values}
  """
  embedding = openai.embeddings.create(
      model="text-embedding-3-large",
      input=profile_text
  )
  ```
- [ ] Store embeddings in Neo4j AND Qdrant
- [ ] Create hybrid search: graph + vector

**ARI Agent Enhancement**
- [ ] Add `UserProfileTool` to existing tools:
  ```python
  @tool
  async def get_user_style_profile(user_id: str) -> UserProfile:
      """Fetch complete user style profile from Neo4j"""
      pass

  @tool
  async def find_similar_users(user_id: str, limit: int = 10) -> List[User]:
      """Find users with similar style preferences"""
      pass
  ```
- [ ] Update agent prompts to include user context
- [ ] Modify `ProductSearchFlow` to accept `user_id` parameter

**Personalization**
- [ ] Personalized product ranking based on user profile
- [ ] Style compatibility scoring
- [ ] Occasion-aware recommendations
- [ ] A/B test personalized vs. non-personalized results

---

## 5. Technical Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    User Onboarding Flow                      │
└────────────────────────┬────────────────────────────────────┘
                         ↓
        ┌────────────────┴────────────────┐
        │                                 │
        ↓                                 ↓
┌──────────────────┐            ┌──────────────────┐
│  Frontend Form   │            │  Facebook OAuth  │
│  Demographics    │            │  (MCP Server)    │
│  Style Quiz      │            │  Social Data     │
└────────┬─────────┘            └────────┬─────────┘
         │                               │
         └───────────┬───────────────────┘
                     ↓
         ┌───────────────────────┐
         │  ARI Backend API      │
         │  - Validation         │
         │  - Data enrichment    │
         │  - Embedding gen      │
         └───────────┬───────────┘
                     ↓
         ┌───────────┴───────────┐
         │                       │
         ↓                       ↓
┌────────────────┐      ┌────────────────┐
│  Neo4j         │      │  Qdrant        │
│  User Profile  │      │  User Vector   │
│  Graph         │      │  Embeddings    │
└────────┬───────┘      └────────┬───────┘
         │                       │
         └───────────┬───────────┘
                     ↓
         ┌───────────────────────┐
         │  ARI CrewAI System    │
         │  + User Context       │
         │  = Personalized Recs  │
         └───────────────────────┘
```

---

## 6. Data Privacy & Compliance Considerations

**Critical Requirements:**

1. **OAuth Scopes** - Request minimum necessary:
   - `public_profile` - Basic info
   - `email` - Email address
   - `user_likes` - Interests (optional)
   - Don't request: `user_posts`, `user_photos` without clear value

2. **Data Storage**
   - Encrypt PII in Neo4j (email, location)
   - Store only hashed Facebook tokens
   - Implement data retention policy (delete after X months of inactivity)

3. **User Control**
   - Allow users to:
     - View their profile data
     - Edit preferences
     - Disconnect social accounts
     - Delete their profile (GDPR "right to be forgotten")

4. **Transparency**
   - Clear privacy policy
   - Explain why you need each data point
   - Show how data improves recommendations

---

## 7. Cost Estimates

**MCP Server Infrastructure:**
- Hosting: $20-50/month (small container)
- Meta API calls: Free (within rate limits)

**Neo4j User Database:**
- Neo4j Aura (managed): $65-200/month depending on scale
- OR self-hosted: $30-100/month
- Storage: ~10KB per user profile

**Embeddings:**
- OpenAI text-embedding-3-large: $0.13 per 1M tokens
- 1000 users × 500 tokens each = 500K tokens = $0.065
- Negligible cost

**Total Estimated Monthly Operating Cost:** $115-350/month

---

## 8. Recommended Tech Stack

```python
# New dependencies to add to requirements.txt
fastmcp>=2.0.0           # MCP server framework
httpx>=0.27.0            # Async HTTP client for Facebook API
neo4j>=5.0.0             # Neo4j Python driver
pydantic>=2.0.0          # Already have this!
redis>=5.0.0             # Caching (already using for memory)
python-jose>=3.3.0       # JWT handling for OAuth
cryptography>=42.0.0     # Token encryption
```

---

## 9. Key Decision Points

**MCP vs Direct API Integration**
- MCP: Build reusable server for multiple AI systems
- Direct API: Simpler FastAPI → Facebook API integration for single use case

**Data Collection Scope**
- Minimal: Email + style quiz only (fast onboarding)
- Moderate: + demographics + brand preferences
- Maximal: + social auth + friend network + Instagram style analysis

**Privacy-First vs Data-Rich**
- Privacy-conscious users: minimal data collection
- Data-rich approach: better recommendations but requires more user trust

**Instagram vs Facebook**
- Instagram: More relevant for fashion, focuses on media/visual content
- Facebook: Broader demographic and interest data

---

## 10. Quick Win: Minimum Viable Onboarding (MVP)

If starting small and iterating:

**Simple Onboarding (No MCP)**
```python
# Just collect this data via a form:
- Email (authentication)
- Age range
- Gender
- Location (city)
- 5-question style quiz:
  1. "Describe your style" (free text)
  2. "Favorite brands" (multi-select)
  3. "Shopping occasions" (checkboxes)
  4. "Preferred colors" (color picker)
  5. "Budget range" (slider)
```

**Basic Neo4j Schema**
```cypher
CREATE (u:User {
  id: randomUUID(),
  email: "user@example.com",
  age_range: "25-34",
  style_description: "Minimalist and modern",
  brands: ["Everlane", "COS"],
  occasions: ["work", "casual"],
  colors: ["black", "white", "navy"],
  budget_range: "mid"
})
```

**Integrate with ARI**
- Pass `user_id` to ProductSearchFlow
- Filter products by user preferences
- See if personalization improves recommendations

**Then iterate:**
- Add social auth in Phase 2
- Add embeddings in Phase 3
- Add MCP server in Phase 4

---

## 11. Resources & References

**Meta Graph API:**
- Official Documentation: https://developers.facebook.com/docs/graph-api/
- User Reference: https://developers.facebook.com/docs/graph-api/reference/user/
- Current Version: v22.0

**MCP (Model Context Protocol):**
- Official Site: https://modelcontextprotocol.io/
- Specification: https://modelcontextprotocol.io/specification/2025-06-18
- FastMCP GitHub: https://github.com/jlowin/fastmcp
- Official Python SDK: https://github.com/modelcontextprotocol/python-sdk

**Neo4j Resources:**
- Social Network Use Cases: https://neo4j.com/use-cases/social-network/
- Data Modeling Tutorial: https://neo4j.com/docs/getting-started/data-modeling/
- Python Driver: https://neo4j.com/docs/python-manual/current/

**Tutorials:**
- Building MCP Servers: https://nordicapis.com/how-to-turn-any-api-into-an-mcp-server/
- FastMCP Guide: https://www.leanware.co/insights/how-to-build-mcp-server
- Neo4j Social Networks: https://medium.com/neo4j/getting-started-with-neo4j-making-a-follow-system-6530ee435392

---

## Next Steps

1. Review this document and decide on approach (MCP vs Direct API, MVP vs Full Build)
2. Prioritize phases based on business requirements
3. Set up development environment for chosen tech stack
4. Begin with MVP if uncertain, iterate based on user feedback
5. Consider data privacy and compliance requirements early
