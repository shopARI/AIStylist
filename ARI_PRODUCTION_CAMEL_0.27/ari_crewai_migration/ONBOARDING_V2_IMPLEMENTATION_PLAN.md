# Onboarding V2 Implementation Plan

Based on Miro Flow - October 2025

## Overview

Complete redesign of the onboarding flow to align with the Miro board structure and new requirements.

## Key Changes

### 1. Structure Change
**OLD:** 7 sequential steps
- style_autonomy
- gender_expression
- self_expression
- lifestyle_context
- values_shopping
- budget
- demographics_contact

**NEW:** 4 main nodes + 2 special sections
- **Personal** (Identity) - who they are
- **Taste** (Aesthetic) - what they like
- **Process** (Decision-making) - how they operate
- **Practicality** (Constraints) - real-world limits
- **Body** (Visual data) - photos
- **External** (Social media) - Instagram/Pinterest/TikTok

### 2. Two-Tier Questioning System
Each node has:
- **Need to ask**: Required information for minimum viable service
- **Nice to know**: Enrichment data collected if time/engagement allows

After completing "Need to ask", crew should check: "Ready to move on, or want to go deeper?"

### 3. Skip/Pass Handling (3-Strike Rule)

**Strike 1:**
```
User skips → Agent: "No worries at all! We have lots of other ways to get to know each other."
Continue to next question.
```

**Strike 2:**
```
User skips again → Agent: "That's completely fine. I want you to feel comfortable sharing what feels right."
Continue to next question.
```

**Strike 3:**
```
After 3 consecutive skips → Agent: "I notice you've passed on a few topics. What's holding you back? Is this:
- Taking too long? (We only have about X minutes left)
- Feeling too invasive? (I can ask differently)
- Something else?"

If user provides feedback → Adjust approach
If user still wants to skip → "Would you like to continue another time? I want to be of best service to you, and to do that, I really want to get to know you first."
```

### 4. Root Value Discovery

**BAD (Robotic):**
```
Agent: "Why does [X] matter to you?"
```

**GOOD (Conversational):**
```
Agent: "I can imagine that [living in NYC] must be important because [fast-paced energy matches your style]... does that resonate?"

Agent: "It sounds like [working in tech] and [loving structured fits] might connect - is that about credibility in your field?"
```

**Approach:**
- Make connections between multiple datapoints
- Infer root values, then validate with user
- Use follow-up questions naturally embedded in conversation
- Avoid direct "why" interrogation

### 5. ARI Personality Responses

When user asks irrelevant questions:

**Physics question:**
```
Agent: "In a past life before fashion, I was obsessed with physics - watching the universe take form. That's why I'm so drawn to finding patterns in how people express themselves. But let's get back to discovering YOUR patterns..."
```

**Weather question:**
```
Agent: "Weather is [current weather] - I sometimes secretly wish I could wake up in a human body to experience raindrops falling on my head. But since I can't, I live vicariously through helping you find the perfect outfit for every kind of weather. Speaking of which..."
```

**Generic irrelevant:**
```
Agent: "That's an interesting question! While that's outside my fashion expertise, it reminds me why I love this work - there's always something new to discover. But let's get back to discovering YOUR style story..."
```

### 6. Conversational Guidelines

**BAD:**
```
User: "What would you like to know?"
Agent: "Tell me your age, name, occupation, and place of residence."
```

**GOOD:**
```
User: "What would you like to know?"
Agent: "Whatever you think would be best to get to know who you are - could be general information about yourself, what's important to you... How would a best friend describe who you are?"
```

**Principles:**
- Open-ended questions that create space
- Guide without prescribing
- Allow multi-topic responses
- Soft, natural transitions
- Never feel like a form

### 7. Photo Capture (Placeholders)

**Face Photo (Color Theory):**
```
Agent: "To understand your color palette - what flatters your skin tone, hair, eyes - I'd love a photo of your face. Natural lighting, no makeup is ideal. This helps me suggest colors that make YOU glow.

This is completely optional, but it does help a lot. What do you think?"

[PLACEHOLDER: PHOTO_CAPTURE_FACE]
→ If yes: Trigger photo upload UI
→ If no: "No problem! Can you describe your coloring? Skin tone, hair color, eye color?"
```

**Body Photo:**
```
Agent: "If you're comfortable, a full-body photo helps me understand proportions and what fits will work best. This is completely optional - I can work without it, but it does help with recommendations.

No pressure at all - only if you're comfortable."

[PLACEHOLDER: PHOTO_CAPTURE_BODY]
→ If yes: Trigger photo upload UI
→ If no: "Totally understand! Can you describe your build and proportions in whatever way feels comfortable?"
```

### 8. Social Media Integration (Placeholders)

**Instagram:**
```
Agent: "Do you have Instagram? If you save style inspo there, I can learn from what you're drawn to. No pressure if not - or if you prefer to keep it private!"

[PLACEHOLDER: INSTAGRAM_INTEGRATION]
→ If yes: Request handle, explain what you'll analyze (saved posts, likes, follows)
→ If no: "No worries! We'll discover your style through our conversation."
```

**Pinterest:**
```
Agent: "Pinterest? If you have boards, they're perfect for showing me your vibe. Want to share your handle or is that private?"

[PLACEHOLDER: PINTEREST_INTEGRATION]
→ If yes: Request handle, analyze boards
→ If no: "That's fine! Plenty of other ways to understand your taste."
```

**TikTok:**
```
Agent: "TikTok? If you follow style content, that helps me understand what you're seeing and drawn to. Share if you're comfortable!"

[PLACEHOLDER: TIKTOK_INTEGRATION]
→ If yes: Request handle, analyze followed accounts/likes
→ If no: "No problem at all!"
```

## Implementation Tasks

### Phase 1: Core Structure (PRIORITY)
- [x] Create `onboarding_prompts_v2.py` with new node structure
- [ ] Create `onboarding_crew_v2.py` with new crew logic
- [ ] Update `OnboardingService` to store node-based data
- [ ] Add skip counter and handling logic
- [ ] Implement two-tier progression (need_to_ask → nice_to_know)

### Phase 2: Enhanced Features
- [ ] Add root value discovery system (follow-up question generation)
- [ ] Implement ARI personality response handling
- [ ] Add conversational quality checks (avoid robotic responses)
- [ ] Implement multi-topic response parsing

### Phase 3: Special Sections
- [ ] Add photo capture placeholders (UI hooks)
- [ ] Add social media integration placeholders
- [ ] Implement fallback flows for declined photos/social
- [ ] Add verbal description alternatives

### Phase 4: Neo4j Schema Update
- [ ] Update schema to support node-based structure
- [ ] Add fields for root values
- [ ] Add fields for skip/pass tracking
- [ ] Add fields for photo references
- [ ] Add fields for social media handles

### Phase 5: Testing & Refinement
- [ ] Test full flow with new structure
- [ ] Test skip/pass handling (all 3 strikes)
- [ ] Test two-tier progression
- [ ] Test ARI personality responses
- [ ] Test photo capture flows
- [ ] Test social media integration
- [ ] Validate data storage in Neo4j

## File Changes Required

### New Files
- `prompts/onboarding_prompts_v2.py` ✅ CREATED
- `crews/onboarding_crew_v2.py` (in progress)
- `services/onboarding_service_v2.py` (optional - may update existing)

### Modified Files
- `cli/chat_interface_v2.py` - Switch to v2 crew
- `cli/onboarding_chat.py` - Switch to v2 crew
- `services/onboarding_service.py` - Update data structure
- `config/neo4j_schema.json` - Add new fields

### Backward Compatibility
- Keep v1 files for now
- Add migration script if needed
- Gradually deprecate v1 after v2 proven stable

## Data Structure Changes

### OLD (Step-based):
```json
{
  "style_autonomy": {...},
  "gender_expression": {...},
  "self_expression": {...},
  ...
}
```

### NEW (Node-based):
```json
{
  "personal": {
    "age": 28,
    "location": {"city": "NYC", "type": "urban"},
    "occupation": "Software Engineer",
    ...
    "root_values": ["authenticity", "professionalism", "creativity"]
  },
  "taste": {
    "gender_expression": {...},
    "brand_preferences": [...],
    "style_loves": "...",
    "style_wants": "...",
    "style_avoids": "...",
    ...
    "root_values": ["confidence", "self-expression"]
  },
  "process": {
    "style_motivations": ["confidence", "professional credibility"],
    "creative_control": 7,
    "adventurousness": 5,
    ...
    "root_values": ["growth", "trust"]
  },
  "practicality": {
    "budget": {"monthly": 300, "yearly": 3600},
    "category_budgets": [...],
    ...
  },
  "body": {
    "face_photo_id": "photo_123",
    "body_photo_id": null,
    "coloring_verbal": "Fair skin, dark hair, green eyes"
  },
  "external": {
    "instagram_handle": "@user123",
    "pinterest_handle": "user123",
    "tiktok_handle": null
  },
  "metadata": {
    "skip_count_by_node": {"personal": 0, "taste": 2, ...},
    "completion_time_minutes": 25,
    "tier_completed": {"personal": "both", "taste": "need_to_ask", ...}
  }
}
```

## Next Steps

1. **IMMEDIATE**: Create `onboarding_crew_v2.py` with skip handling and two-tier system
2. Test the new flow with a real conversation
3. Gather feedback on conversational quality
4. Implement photo/social placeholders
5. Update Neo4j schema
6. Full integration testing

## Success Metrics

- Conversational quality (less robotic, more natural)
- Skip rate per node (target: <20%)
- Completion rate (target: >80%)
- Average completion time (target: 15-25 minutes)
- User satisfaction with depth vs. speed balance
- Data richness (root values captured per user)

## Notes

- This is a significant UX upgrade, not just a technical refactor
- Focus on making it feel like a conversation, not a form
- The goal is maximum data while maintaining engagement
- Skip handling is critical - respect user boundaries
- Root value discovery is the secret sauce for personalization
