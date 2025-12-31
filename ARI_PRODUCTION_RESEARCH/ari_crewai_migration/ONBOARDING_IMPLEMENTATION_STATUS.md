# Onboarding Implementation Status - V2 vs Documentation

**Date:** November 2025
**Purpose:** Verify V2 onboarding implementation against RESEARCH_HANDOFF.md documentation

---

## Summary: Documentation vs Reality

**Finding:** RESEARCH_HANDOFF.md documents **V1** onboarding, but the codebase has **V2** implemented!

| Aspect | RESEARCH_HANDOFF.md (Outdated) | Actual V2 Implementation |
|--------|--------------------------------|--------------------------|
| File Referenced | `cli/onboarding_chat.py` | `cli/onboarding_chat_v2.py` |
| Structure | Simple 8 stages | **4 main nodes + 2 optional** (6 total) |
| Questioning | Single-tier | **Two-tier:** need_to_ask → nice_to_know |
| Skip Handling | Not documented | **3-strike system** with escalation |
| Root Values | Not documented | **Explicit root value discovery** |
| ARI Personality | Not documented | **Personality responses** for irrelevant questions |
| Documentation | Minimal | **Comprehensive** (UX_REVIEW_ONBOARDING_V2.md) |

---

## V1 (RESEARCH_HANDOFF.md) - What's Documented

### Stages (Old):
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

### Features Documented:
- LLM-driven conversational onboarding
- Model: GPT-4o with structured output
- Temperature: 1.0
- Progressive disclosure (can skip questions)
- Neo4j storage

### Example from Documentation:
```
ARI: "Hi! I'm ARI, your fashion stylist. What should I call you?"
User: "Call me Sarah"

ARI: "Nice to meet you, Sarah! Let's get to know your style.
      How would you describe your everyday look?"
User: "I'm pretty casual but like to look put together"

ARI: "Love that! Smart-casual vibes. What about your body type?"
User: "I'm petite with an athletic build"
```

---

## V2 (Actual Implementation) - What's Built

### Node Structure (New):
```python
ONBOARDING_NODES = [
    "personal",      # Identity foundation (PersonalIdentity node)
    "taste",         # Aesthetic preferences (TasteProfile node)
    "process",       # How they operate (ProcessProfile node)
    "practicality",  # Real-world constraints (PracticalityProfile node)
    "body",          # Visual data (BodyData node) - OPTIONAL
    "external"       # Social media (SocialMediaProfile node) - OPTIONAL
]
```

### Two-Tier Questioning:

**Tier 1: "Need to Ask"** (Required)
```python
PERSONAL_NODE["need_to_ask"] = {
    "age": {...},
    "location": {...},
    "work": {...},
    "typical_occasions": {...},
    "gender_identity": {...},
    "ethnicity": {...},
    "relationship_status": {...},
    "parental_status": {...}
}
```

**Tier 2: "Nice to Know"** (Optional, offered after completing tier 1)
```python
PERSONAL_NODE["nice_to_know"] = {
    "sexuality": {...},          # VERY sensitive - never ask directly
    "income_level": {...},       # Inferred from budget discussion
    "education_level": {...},    # May emerge naturally
    "religious_cultural_background": {...}
}
```

### Skip/Pass Handling (3-Strike System):

**Strike 1:**
```
"No worries at all! We have lots of other ways to get to know each other.
I want you to feel comfortable sharing only what feels right."
```

**Strike 2:**
```
"That's completely fine. I want this to feel like a conversation, not an interrogation.
Share what you're comfortable with, and we'll discover what we need to know along the way."
```

**Strike 3:**
```
"I notice you've passed on a few topics, and I want to make sure this is working for you.
What's holding you back? Is this:

• Taking too long?
• Feeling too invasive?
• Something else on your mind?"
```

**Strike 4+:**
```
"Would you like to:
• Take a break and continue another time?
• Try a different approach (maybe shorter questions, or focus on specific areas)?
• Just get started with what we know so far?"
```

### Root Value Discovery:

**Approach:** Conversational inference instead of direct questions

**Bad (Robotic):**
```
"Why does this matter to you?"
```

**Good (V2 Approach):**
```
"I can imagine that [X datapoint] must be important because [inference about value]..."
```

**Examples from code:**
```python
# Personal → TasteProfile
"root_value_connection": "Authenticity, self-expression, being seen, belonging"

# ProcessProfile → creative_control
"root_value_connection": "Trust, control, growth mindset, decision confidence"

# PracticalityProfile → budget
"root_value_connection": "Financial values, planning vs spontaneity, scarcity vs abundance mindset"
```

### ARI Personality Responses:

When users ask irrelevant questions, ARI responds with personality:

**Physics Questions:**
```
"You know, that's fascinating! In a past life before fashion, I was obsessed with physics -
watching the universe take form, understanding the patterns that connect everything. That's
actually why I'm so drawn to finding patterns in how people express themselves through style.

But let's get back to discovering YOUR patterns and what makes you uniquely you..."
```

**Weather Questions:**
```
"I sometimes secretly wish I could wake up in a human body just to experience things like
weather firsthand. Raindrops on my head, wind in my hair... But since I can't, I live
vicariously through helping you find the perfect style for every kind of day.

Speaking of which, let's get back to YOUR style story..."
```

**"Who Are You?" Questions:**
```
"I appreciate your curiosity! I'm ARI, and I exist to help people discover and express their
authentic style. I was created by people who believe fashion should be personal, not prescriptive.
I learn from every conversation, and I genuinely care about understanding who you are.

But enough about me - I'm much more interested in YOU. Let's keep exploring your story..."
```

### Conversation Quality Rules:

```python
GLOBAL_DIALOGUE_RULES = """
CONVERSATION STYLE:
- Ask ONE question at a time - like a real conversation
- Keep questions short and simple
- Wait for their answer before asking the next thing
- Don't dump multiple questions or topics at once
- Natural, conversational tone - NOT a form or interview

CRITICAL: ONE QUESTION AT A TIME
- Ask about ONE thing, wait for response
- Then follow up naturally based on what they said
- Example GOOD: "What stage of life are you in right now?"
- Example BAD: "Tell me about your life stage, what's important to you, how you spend your days, etc."

MID-CONVERSATION FEEDBACK:
- Sprinkle in punchy, specific feedback based on what they share
- Make it feel super intelligent and niche to them personally
- Examples:
  - "Sounds like you're very boho chic but sometimes have a rock and roll flair."
  - "I notice you mentioned sustainability 3 times - clearly core to who you are"
  - "X% of brands are moving toward quiet luxury... you're ahead of the curve"
"""
```

---

## Comparison: What Changed from V1 → V2

### 1. **Structure**
| V1 | V2 |
|----|---|
| 8 sequential stages | 6 nodes with internal structure |
| Flat progression | Two-tier (need_to_ask → nice_to_know) |
| Fixed questions | Adaptive conversation |

### 2. **Data Mapping to Ontology**
| V1 Stage | V2 Node | Ontology Mapping |
|----------|---------|------------------|
| greeting | (Built into personal) | User |
| style_preferences | taste | TasteProfile |
| body_type | body | BodyData |
| occasions | personal.typical_occasions | PersonalIdentity.typical_occasions |
| color_preferences | taste (embedded) | TasteProfile (colors inferred) |
| brand_preferences | taste.brand_preferences | TasteProfile.brand_preferences |
| budget | practicality.budget | PracticalityProfile.budget |
| finalization | (Automatic in V2) | - |

**New in V2 (not in V1):**
- `personal` node → PersonalIdentity (demographics, identity, life stage)
- `process` node → ProcessProfile (how they shop, decide, validate)
- Root value discovery → RootValue nodes
- Social media → SocialMediaProfile
- Skip handling → OnboardingMetadata.skip_counts

### 3. **Conversation Quality**

**V1 (Simple):**
```
ARI: "What's your budget?"
User: "$100/month"
ARI: "Got it. What brands do you like?"
```

**V2 (Conversational):**
```
ARI: "Let's talk budget - not to judge, but so I can be actually helpful.
      Do you have a monthly or yearly amount you'd like to stick to for clothing?"
User: "Maybe like $100 a month?"
ARI: "Got it. Is that a firm limit or more of a guideline? Like, if something
      perfect came along, would you stretch for it?"
User: "Depends on the piece. I'd splurge on a good coat."
ARI: "I hear you. Quality where it counts. Which categories can we mark up vs.
      where do you want to stay budget-friendly?"
```

### 4. **Data Storage**

**V1 (Assumed):**
```cypher
CREATE (u:User {username: "Sarah"})
SET u.style_preferences = "casual"
SET u.body_type = "petite-athletic"
SET u.budget = 100
```

**V2 (Ontology-Aligned):**
```cypher
// Create user with relationships
CREATE (u:User {username: "Sarah"})

CREATE (u)-[:HAS_PERSONAL_IDENTITY]->(p:PersonalIdentity {
  age: 28,
  location_city: "NYC",
  occupation: "lawyer"
})

CREATE (u)-[:HAS_TASTE_PROFILE]->(t:TasteProfile {
  gender_expression: {spectrum: "fluid", preferences: "structured"},
  brand_preferences: [{brand: "Everlane", why: "minimalist quality"}],
  style_loves: "clean lines, neutral palette"
})

CREATE (u)-[:HAS_PROCESS_PROFILE]->(pr:ProcessProfile {
  style_motivations: ["confidence", "authenticity"],
  creative_control: 7,
  brand_loyalty: 6
})

CREATE (u)-[:HAS_PRACTICALITY_PROFILE]->(pp:PracticalityProfile {
  monthly_budget_min: 80,
  monthly_budget_max: 150,
  budget_flexibility: "moderate"
})

CREATE (u)-[:HAS_ROOT_VALUE]->(rv:RootValue {
  value: "authenticity",
  confidence: 0.9
})
```

---

## Implementation Coverage

### ✅ FULLY IMPLEMENTED in V2:

1. **Node-Based Structure**
   - ✅ Personal node (PersonalIdentity mapping)
   - ✅ Taste node (TasteProfile mapping)
   - ✅ Process node (ProcessProfile mapping)
   - ✅ Practicality node (PracticalityProfile mapping)
   - ✅ Body node (BodyData mapping)
   - ✅ External node (SocialMediaProfile mapping)

2. **Two-Tier System**
   - ✅ need_to_ask (required questions)
   - ✅ nice_to_know (optional deep-dive)
   - ✅ Progression logic: ask to continue after tier 1
   - ✅ Skip nice_to_know if user declines

3. **Skip/Pass Handling**
   - ✅ Skip detection (regex patterns)
   - ✅ 3-strike escalation system
   - ✅ Graceful responses at each strike
   - ✅ Raincheck offer after 4+ skips
   - ✅ Reset counter on engagement

4. **Root Value Discovery**
   - ✅ Conversational inference prompts
   - ✅ Root value extraction in each node
   - ✅ Storage in separate root_values dict
   - ✅ Connection strength tracking

5. **ARI Personality**
   - ✅ Irrelevant question detection
   - ✅ Physics personality response
   - ✅ Weather personality response
   - ✅ "Who are you" personality response
   - ✅ Generic fallback

6. **Conversation Quality**
   - ✅ One question at a time rule
   - ✅ Follow-up prompts system
   - ✅ Mid-conversation feedback
   - ✅ Adaptive dialogue patterns
   - ✅ Natural transitions

7. **Data Extraction & Storage**
   - ✅ Information extraction agent
   - ✅ JSON parsing with markdown handling
   - ✅ Completeness scoring
   - ✅ Missing info tracking
   - ✅ Neo4j storage via OnboardingService

8. **Progress Tracking**
   - ✅ Node completion tracking
   - ✅ Tier completion tracking
   - ✅ Overall progress percentage
   - ✅ Skip count per node
   - ✅ Consecutive skip counter

### ⚠️ PARTIALLY IMPLEMENTED:

1. **Photo Capture (Placeholders Only)**
   - ⚠️ Face photo field defined
   - ⚠️ Body photo field defined
   - ⚠️ Conversational prompts ready
   - ✗ **NO actual upload mechanism** (marked as PHOTO_CAPTURE_FACE/BODY placeholder)
   - ✗ No image storage integration
   - ✗ No color theory analysis pipeline

2. **Social Media Integration (Placeholders Only)**
   - ⚠️ Instagram field defined
   - ⚠️ Pinterest field defined
   - ⚠️ TikTok field defined
   - ⚠️ Conversational prompts ready
   - ✗ **NO API integration** (marked as INSTAGRAM_INTEGRATION/PINTEREST_INTEGRATION/TIKTOK_INTEGRATION placeholder)
   - ✗ No content analysis
   - ✗ No pattern extraction from boards/saves

3. **Occasion-Based Dynamic Questions**
   - ✅ Prompts say to use user's actual occasions
   - ✅ Logic described in conversation_guide
   - ⚠️ **Not verified if LLM actually does this** (depends on agent following prompts)
   - ? Needs testing to confirm

### ✗ NOT IMPLEMENTED (Gaps):

1. **Neo4j Ontology Alignment**
   - ✗ OnboardingService likely uses simple key-value storage
   - ✗ **NOT creating separate nodes** for PersonalIdentity, TasteProfile, ProcessProfile, etc.
   - ✗ **NOT creating relationships** (HAS_PERSONAL_IDENTITY, HAS_TASTE_PROFILE, etc.)
   - ✗ **NOT creating RootValue nodes** with relationships
   - ⚠️ Data stored, but likely as JSON blobs in OnboardingDataNode

2. **Root Value Nodes**
   - ✅ Root values discovered and tracked
   - ✗ **NOT stored as separate (:RootValue) nodes** in Neo4j
   - ✗ **NOT creating relationships** User-[HAS_ROOT_VALUE]->RootValue

3. **Body Insecurities / Favorite Features**
   - ✅ Fields defined in nice_to_know
   - ✅ Prompts say "NEVER ask directly"
   - ⚠️ May never be collected (only if user mentions)
   - ? No verification if stored when mentioned

4. **Feedback Generation**
   - ✅ Prompts include feedback guidelines
   - ⚠️ Depends on LLM following instructions
   - ? Not clear if feedback is actually punchy/specific in practice
   - ? Needs user testing

5. **Time Management**
   - ✅ Prompts mention time indicators
   - ✗ **NO actual time tracking** in code
   - ✗ No computation of "X minutes in, Y more to go"
   - ✗ Hardcoded placeholder text: "[X] minutes in, [Y] more to go"

---

## Documentation Status

### Files That Need Updating:

1. **RESEARCH_HANDOFF.md** (Lines 455-555)
   - ❌ Currently documents V1 (`cli/onboarding_chat.py`)
   - ❌ Lists old 8-stage structure
   - ❌ Missing V2 features: skip handling, root values, two-tier, personality
   - **Action:** Rewrite Onboarding Flow section to match V2

2. **ONTOLOGY_SPECIFICATION.md** (Already correct!)
   - ✅ Documents PersonalIdentity, TasteProfile, ProcessProfile, PracticalityProfile nodes
   - ✅ Matches V2 structure
   - ✅ Includes RootValue nodes
   - ✅ Includes OnboardingMetadata
   - **Status:** ACCURATE - no changes needed

### Files That Are Accurate:

1. **UX_REVIEW_ONBOARDING_V2.md**
   - ✅ Comprehensive V2 documentation
   - ✅ Conversation style documented
   - ✅ Skip handling examples
   - ✅ ARI personality responses
   - ✅ Field-by-field conversation approaches

2. **prompts/onboarding_prompts_v2.py**
   - ✅ Complete node definitions
   - ✅ Two-tier structure
   - ✅ Root value connections
   - ✅ Conversation guides

3. **crews/onboarding_crew_v2.py**
   - ✅ OnboardingCrewV2 class
   - ✅ Skip detection and handling
   - ✅ Information extraction
   - ✅ Tier progression logic

4. **cli/onboarding_chat_v2.py**
   - ✅ Conversational flow implementation
   - ✅ Progress tracking
   - ✅ Data saving

---

## Recommendations

### 1. Update RESEARCH_HANDOFF.md

**Current (Outdated):**
```markdown
### Implementation
**File:** `cli/onboarding_chat.py`

### Onboarding Conversation Structure

ONBOARDING_STAGES = [
    "greeting",
    "style_preferences",
    ...
]
```

**Should Be:**
```markdown
### Implementation
**File:** `cli/onboarding_chat_v2.py`
**Prompts:** `prompts/onboarding_prompts_v2.py`
**Crew:** `crews/onboarding_crew_v2.py`

### Onboarding Node Structure (V2)

ONBOARDING_NODES = {
    "personal": PersonalIdentity,      # Demographics, identity, life stage
    "taste": TasteProfile,            # Aesthetic preferences
    "process": ProcessProfile,        # Decision-making, shopping style
    "practicality": PracticalityProfile,  # Budget, constraints
    "body": BodyData,                 # Photos, coloring (optional)
    "external": SocialMediaProfile    # Instagram, Pinterest, TikTok (optional)
}

### Two-Tier Questioning
- **Tier 1: "Need to Ask"** (Required)
- **Tier 2: "Nice to Know"** (Optional deep-dive)
```

### 2. Implement Missing Features

**Priority 1 (CRITICAL for Ontology Compliance):**
```python
# Fix OnboardingService to create proper nodes and relationships
async def save_onboarding_to_ontology(user_id: str, extracted_data: Dict):
    """
    Create ontology-aligned nodes instead of JSON blobs.
    """
    # Create PersonalIdentity node
    await session.run("""
        MATCH (u:User {id: $user_id})
        CREATE (u)-[:HAS_PERSONAL_IDENTITY]->(p:PersonalIdentity {
            age: $age,
            location_city: $location_city,
            ...
        })
    """, user_id=user_id, **extracted_data['personal'])

    # Create RootValue nodes
    for value in extracted_data['root_values']:
        await session.run("""
            MATCH (u:User {id: $user_id})
            MERGE (rv:RootValue {value: $value})
            MERGE (u)-[:HAS_ROOT_VALUE {strength: $confidence}]->(rv)
        """, user_id=user_id, value=value, confidence=0.8)
```

**Priority 2 (Nice to Have):**
- Photo upload integration (use cloud storage + Neo4j reference)
- Social media API integration (Instagram, Pinterest, TikTok)
- Time tracking for onboarding duration

**Priority 3 (Polish):**
- Verify occasion-based dynamic questions work in practice
- User testing for conversation quality
- Tune completeness thresholds (currently 80%)

### 3. Testing Checklist

- [ ] V2 onboarding creates PersonalIdentity nodes (not JSON blobs)
- [ ] V2 creates TasteProfile, ProcessProfile, PracticalityProfile nodes
- [ ] V2 creates RootValue nodes with relationships
- [ ] Skip handling works at each strike level
- [ ] ARI personality triggers on irrelevant questions
- [ ] Two-tier progression offers nice_to_know after need_to_ask
- [ ] Progress tracking accurate
- [ ] Occasion-based questions pull from user's actual occasions
- [ ] Mid-conversation feedback is punchy and specific
- [ ] Data saved correctly to Neo4j in ontology structure

---

## Conclusion

**V2 Onboarding is WELL-IMPLEMENTED** with excellent conversation design, skip handling, root value discovery, and two-tier progression.

**BUT:** Documentation (RESEARCH_HANDOFF.md) is **OUTDATED** - still references V1.

**AND:** Ontology alignment may be **INCOMPLETE** - needs verification that OnboardingService creates proper nodes/relationships instead of JSON blobs.

**ACTION ITEMS:**
1. ✅ Update RESEARCH_HANDOFF.md to document V2 (lines 455-555)
2. 🔍 Verify OnboardingService creates ontology-compliant nodes
3. ⚠️ Implement photo/social media integrations (currently placeholders)
4. ✅ Update this implementation status document as features are completed

---

**Last Updated:** November 2025
