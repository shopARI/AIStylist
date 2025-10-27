# Social Influence Graph Design

## CEO Vision: Track External Influencers

### Concept
When a user says "I follow @fashioninfluencer on Instagram", we should:
1. Create a profile for that influencer (even if they're not an ARI user)
2. Analyze their public style from Instagram
3. Use their style to inform recommendations for followers
4. Build a network of influence relationships

### Use Cases

**Example Flow:**
```
User: "I love @tanfrance's style"
   ↓
ARI creates (:ExternalProfile {handle: "tanfrance", platform: "instagram"})
   ↓
ARI scrapes public Instagram (profile, bio, top posts)
   ↓
Vision AI analyzes: "Tailored menswear, bold colors, statement pieces"
   ↓
User gets recommendations aligned with Tan France's aesthetic
```

### Schema Design

```cypher
// ARI Users (registered)
(:User {
  id, username, email,
  onboarding_completed: true
})

// External Influencers (not ARI users... yet)
(:ExternalProfile {
  id: "ext_instagram_tanfrance",
  platform: "instagram",
  handle: "@tanfrance",
  display_name: "Tan France",
  is_verified: true,
  follower_count: 4500000,
  bio: "Fashion designer, TV personality...",

  // Scraped/analyzed data
  style_tags: ["tailored", "menswear", "bold-colors", "statement-pieces"],
  dominant_colors: ["navy", "burgundy", "tan"],
  typical_items: ["blazers", "dress-shirts", "chinos"],
  aesthetic_score: {minimalist: 3, maximalist: 8, classic: 9, trendy: 6},

  // Metadata
  last_scraped: datetime(),
  scrape_status: "success",
  became_user: false,  // True if they sign up for ARI later
  user_id: null  // Linked if they become a real user
})

// Relationships
(User)-[:FOLLOWS {
  platform: "instagram",
  discovered_from: "onboarding",  // or "manual_add"
  influence_score: 0.85,  // How much this person influences user
  added_at: datetime()
}]->(ExternalProfile)

(User)-[:INSPIRED_BY {
  confidence: 0.9,
  reason: "User mentioned as style icon"
}]->(ExternalProfile)

// When external profile becomes a real user
(ExternalProfile)-[:BECAME_USER]->(User)
```

### Data Sources

**What We Can Scrape (Public Data Only):**

1. **Instagram Public Profile:**
   - Handle, display name, bio
   - Follower count, verification status
   - Profile picture
   - Public posts (images only if account is public)

2. **Analysis via AI:**
   - Vision AI on public photos → style tags
   - NLP on bio → interests, values
   - Color analysis → dominant palette
   - Item detection → "often wears blazers"

3. **Manual Curation (Optional):**
   - Product team can tag well-known influencers
   - "Celebrity Style Profiles" database

### Privacy & Legal Compliance

**Safe Practices:**
- ✅ Only public data (no authentication required)
- ✅ Comply with platform ToS (rate limits, no scraping APIs)
- ✅ Clear user disclosure: "We analyze public profiles you mention"
- ✅ Allow users to remove connections
- ✅ Don't store scraped images, only analysis results
- ✅ Respect robots.txt and scraping guidelines

**Risk Mitigation:**
- Don't violate Instagram ToS (no automated scraping of private accounts)
- Use official APIs where available
- Rate limit aggressively
- Manual review for high-profile influencers

### Implementation Approach

#### Phase 1: Manual Entry (MVP)
```
User: "I love Tan France's style"
   ↓
ARI: Creates ExternalProfile manually
   ↓
Product team curates style tags for well-known influencers
```

**No scraping, just manual curation of ~100 top fashion influencers**

#### Phase 2: Public API Integration
```
User provides Instagram handle
   ↓
Use Instagram Basic Display API (if user authorizes)
   ↓
Fetch public profile info only
   ↓
Store: bio, follower count, profile picture
```

#### Phase 3: AI Analysis
```
User uploads screenshots of influencer's posts
   OR
User pastes image URLs
   ↓
Vision AI analyzes style
   ↓
Generate style tags automatically
```

#### Phase 4: Automated Scraping (High Risk)
```
⚠️ Only if legal team approves
⚠️ Only for public accounts
⚠️ With strict rate limits
```

### Benefits of This Approach

1. **Network Effects**
   - "Users who follow X also love Y"
   - Discover new influencers
   - Build taste graphs

2. **Better Recommendations**
   - "Your style icons wear brands like..."
   - "Outfits inspired by @tanfrance"

3. **Viral Growth**
   - Influencers see they're being referenced
   - "500 ARI users follow you - claim your profile!"
   - Convert ExternalProfile → Real User

4. **Rich Data Without Onboarding Fatigue**
   - Instead of asking 50 questions
   - "Who do you follow?" → Instant style profile

### Query Examples

**Find users with similar taste:**
```cypher
// Find users who follow the same influencers
MATCH (u1:User)-[:FOLLOWS]->(ep:ExternalProfile)<-[:FOLLOWS]-(u2:User)
WHERE u1.id = $user_id AND u1.id <> u2.id
RETURN u2, count(ep) as shared_influencers
ORDER BY shared_influencers DESC
LIMIT 10
```

**Recommend products based on influencer style:**
```cypher
// Get style tags from user's followed influencers
MATCH (u:User {id: $user_id})-[:FOLLOWS]->(ep:ExternalProfile)
UNWIND ep.style_tags as tag

// Find products matching those tags
MATCH (p:Product)
WHERE tag IN p.tags

RETURN p, count(DISTINCT ep) as influencer_match_count
ORDER BY influencer_match_count DESC
LIMIT 20
```

**Influencer impact score:**
```cypher
// Which influencers are most popular among ARI users?
MATCH (u:User)-[:FOLLOWS]->(ep:ExternalProfile)
WITH ep, count(u) as follower_count
ORDER BY follower_count DESC
LIMIT 50

RETURN ep.handle, ep.display_name, follower_count as ari_followers
```

### Metrics to Track

- **External Profiles Created:** Count of influencers in graph
- **Follow Connections:** (User)-[:FOLLOWS]->(ExternalProfile) count
- **Conversion Rate:** ExternalProfiles who become real Users
- **Influence Score:** Correlation between following X and buying Y
- **Style Tag Accuracy:** Do AI-generated tags match reality?

### Onboarding Integration

**Modified Question:**
```json
{
  "id": "inspiration_sources",
  "type": "multi_text",
  "question": "Who inspires your style? (Instagram handles, celebrities, etc.)",
  "placeholder": "@fashioninfluencer, @stylistname, Zendaya...",
  "parse_strategy": "extract_handles",
  "create_external_profiles": true
}
```

**What Happens:**
1. User types: "@tanfrance, @patrickta, Zendaya"
2. System extracts: ["tanfrance", "patrickta"] (Instagram), ["Zendaya"] (general)
3. Creates ExternalProfile nodes for each
4. Links: (User)-[:FOLLOWS]->(ExternalProfile)
5. Background job: Scrape/analyze these profiles

### Next Steps

**Decision Points:**

1. **Start with manual curation?** (Safer, faster)
   - Product team tags 100 top influencers
   - Users select from list + add custom

2. **Or build scraping pipeline?** (More powerful, riskier)
   - Automated Instagram analysis
   - Legal review required

3. **Hybrid approach?** (Recommended)
   - Manual for top 100 influencers
   - User-provided screenshots for others
   - No automated scraping

**My Recommendation: Start with Hybrid**

```python
# services/external_profile_service.py

class ExternalProfileService:
    async def create_from_handle(self, handle: str, platform: str):
        """Create external profile from handle."""
        # Check if exists in curated database first
        # If not, create placeholder
        # Queue for manual review/analysis

    async def analyze_from_screenshot(self, user_id: str, image_url: str):
        """User uploads screenshot, we analyze style."""
        # Vision AI analysis
        # Generate style tags
        # Link to user
```

### Risk Assessment

**Low Risk (Start Here):**
- ✅ Manual curation of top influencers
- ✅ User-provided screenshots
- ✅ Text-based inspiration sources

**Medium Risk:**
- ⚠️ Scraping public profile data only
- ⚠️ Using official APIs with auth

**High Risk (Avoid Initially):**
- ❌ Automated scraping without user consent
- ❌ Storing scraped images
- ❌ Bypassing rate limits

### Competitive Advantage

**This is powerful because:**
- Pinterest does this (visual inspiration)
- Lyst does this (influencer tracking)
- But you're combining: social graph + product recommendations + AI styling

**"We recommend based on YOUR taste graph, not generic trends"**

---

## Implementation Checklist

- [ ] Add ExternalProfile node to Neo4j schema
- [ ] Create ExternalProfileService
- [ ] Add "inspiration sources" to onboarding
- [ ] Build manual curation interface (for Product team)
- [ ] Implement handle parsing (extract @instagram handles)
- [ ] Create FOLLOWS relationship logic
- [ ] Build "Find similar users" based on shared follows
- [ ] Modify ProductSearchFlow to use influencer data
- [ ] Add metrics tracking
- [ ] Legal review of scraping approach

**Timeline: 2-3 weeks for MVP (manual curation approach)**
