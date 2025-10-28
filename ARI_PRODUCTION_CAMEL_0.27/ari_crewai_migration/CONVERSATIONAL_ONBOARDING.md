# Conversational Onboarding System

## Overview

ARI's conversational onboarding system uses AI agents to discover user preferences through natural dialogue instead of rigid question-and-answer forms. This creates a more human, empathetic experience especially for sensitive topics like gender expression, style identity, and personal values.

## Philosophy

**Traditional Onboarding Problems:**
- Feels like filling out a form
- Forces users into predefined boxes
- Doesn't allow exploration or uncertainty
- Misses nuance in sensitive topics
- Can't adapt to individual communication styles

**Conversational Approach:**
- Natural dialogue that feels like talking to a stylist
- Pursues understanding through follow-up questions
- Allows users to explore and articulate at their own pace
- Handles sensitive topics (gender, identity) with care
- Adapts conversation flow based on user responses
- Extracts structured data without feeling transactional

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                 Conversational Onboarding                    │
│                                                               │
│  ┌──────────────┐         ┌────────────────┐                │
│  │  User Chat   │────────▶│ OnboardingCrew │                │
│  │  Interface   │◀────────│                │                │
│  └──────────────┘         └────────────────┘                │
│                                  │                           │
│                                  │                           │
│                    ┌─────────────┴─────────────┐            │
│                    │                             │            │
│           ┌────────▼────────┐       ┌───────────▼────────┐  │
│           │ Onboarding      │       │ Information        │  │
│           │ Agent           │       │ Extraction Agent   │  │
│           │                 │       │                    │  │
│           │ - Conversation  │       │ - Data Parsing     │  │
│           │ - Empathy       │       │ - Validation       │  │
│           │ - Follow-ups    │       │ - Completeness     │  │
│           └─────────────────┘       └────────────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Conversation Prompts                       │   │
│  │  - 7 topic-specific guidelines                        │   │
│  │  - Sensitivity notes                                  │   │
│  │  - Sample conversation starters                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│                         │                                     │
│                         ▼                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            User Graph Manager                         │   │
│  │  - Store extracted data in Neo4j                      │   │
│  │  - Track onboarding progress                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Key Files

- **`agents/onboarding_agent.py`** - AI agent definitions
  - `OnboardingAgent` - Conversational discovery specialist
  - `InformationExtractionAgent` - Data parsing specialist

- **`prompts/onboarding_prompts.py`** - Conversation guidelines
  - Topic-specific prompts for 7 onboarding steps
  - Sensitivity notes for handling delicate topics
  - Sample conversation starters
  - Information extraction specifications

- **`crews/onboarding_crew.py`** - Orchestration
  - `OnboardingCrew` - Manages conversation flow
  - Coordinates between agents
  - Tracks progress and extracted data
  - Validates completeness

- **`cli/onboarding_chat.py`** - User interface
  - `ConversationalOnboarding` - Chat interface
  - Progress tracking
  - Data persistence

## The 7 Conversation Topics

### 1. Style Autonomy (How We'll Work Together)
**Focus:** Understanding decision-making preferences

**What we discover:**
- How much guidance vs autonomy they want
- Comfort with trying new things (risk tolerance)
- Preference for being told, shown curated options, or many options
- Past experiences with styling/shopping

**Sensitive considerations:**
- Respect past negative experiences with pushy stylists
- Validate uncertainty about preferences
- Don't assume everyone shops the same way

---

### 2. Gender Expression (Your Style Expression)
**Focus:** Style identity and gendered expression

**What we discover:**
- Where they fall on structured ↔ fluid ↔ soft spectrum
- Words they use to describe their style
- Fits that make them feel confident
- How much style varies by occasion

**⚠️ CRITICAL Sensitivity:**
- NEVER ask "are you more masculine or feminine?"
- Let user define their own terms
- Use gender-neutral language unless user specifies
- Don't pathologize non-binary or gender-fluid expression
- This is identity territory - tread carefully

---

### 3. Self Expression (Style & Identity)
**Focus:** Role of style in identity and aspirations

**What we discover:**
- How bold/statement-making they want to be
- Whether seeking refinement, evolution, or transformation
- Style aspirations and inspirations
- What they're moving toward or away from

**Sensitive considerations:**
- Validate current style even if they want change
- Don't push transformation if they want refinement
- Respect exploration mode

---

### 4. Lifestyle Context (Your Life & Occasions)
**Focus:** Practical contexts that shape needs

**What we discover:**
- Life stages (parenthood, career transition, etc.)
- Regular occasions they dress for
- Workplace expectations
- How needs vary

**Sensitive considerations:**
- Don't assume life stages from age
- Respect all work situations (unemployment is valid)
- Validate all lifestyles equally

---

### 5. Values & Shopping (What Matters to You)
**Focus:** Beyond aesthetics - what drives decisions

**What we discover:**
- Values (sustainability, ethics, quality)
- Style motivations (confidence, expression, credibility)
- Shopping preferences and habits
- Brand relationships

**Sensitive considerations:**
- Validate all values without judgment
- Respect budget constraints on values
- Don't shame any shopping behavior

---

### 6. Budget (Budget & Value)
**Focus:** Financial parameters and value perception

**What we discover:**
- Realistic monthly budget
- Category-specific budgets
- What "value" means to them
- Splurge vs save preferences

**⚠️ SENSITIVE:**
- Budget is personal - never judge
- Frame as practical planning
- Validate all budget ranges
- Respect financial constraints

---

### 7. Demographics & Contact (Getting to Know You)
**Focus:** Basic info for personalization

**What we discover:**
- Age range (not specific age)
- Location (for climate/local context)
- Optional social media handles

**Sensitive considerations:**
- Age can be sensitive - use ranges
- Explain why we're asking
- Emphasize what's optional

## How Conversation Works

### Opening
```
Agent: "Tell me about a recent shopping experience - what was that like for you?"
```
- Warm, open-ended question
- Sets conversational tone
- No information dump

### Discovery Phase
```
User: "I went to the mall last week but got overwhelmed with all the choices..."

Agent: "It sounds like having too many options made it hard to decide. Do you
usually prefer when someone narrows things down for you, or do you like browsing
everything yourself?"
```
- Acknowledge what user shared
- Ask thoughtful follow-up
- Explore deeper if uncertain

### Extraction (Behind the Scenes)
```json
{
  "decision_making_style": "curated_options",
  "creative_control": 4,
  "completeness": 0.4,
  "confidence": "medium"
}
```
- Structured data extracted from conversation
- Completeness tracking
- No interruption to user

### Progression
- Agent checks completeness
- Offers to move on when ready
- Never rushes user
- Allows exploration

## Running Conversational Onboarding

### Quick Start

```bash
./run_onboarding.sh
```

Or directly:
```bash
python cli/onboarding_chat.py
```

### Commands During Onboarding

- **Type naturally** - Just respond conversationally
- **`skip`** or **`next`** - Move to next topic
- **`quit`** or **`exit`** - Save progress and exit

### Sample Conversation Flow

```
========================================
Welcome to ARI
========================================

What would you like me to call you? Alex

What's your email address? alex@example.com

Press Enter when you're ready to begin...

========================================
How We'll Work Together
========================================

ARI: Tell me about a recent shopping experience - what was that like for you?

You: I went to Nordstrom last weekend but left empty-handed. There was too much stuff.

ARI: It sounds like having so many options made it hard to decide. Do you usually
prefer when someone narrows things down for you, or do you like browsing everything?

You: I think I want someone to show me a few good options, not everything.

ARI: That makes sense - curated options can make decisions easier. How do you feel
about trying styles that are a bit outside your usual comfort zone? Are you more
"play it safe" or "let's see what happens"?

You: I'm open to trying new things but not too crazy.

ARI: I hear you - adventurous but not too far out there. It sounds like you want
some guidance with carefully selected options, and you're open to exploring new
styles within reason. Does that feel right?

You: Yes, exactly!

ARI: Perfect! Ready to move on to talking about your style expression?

You: yes

[Progress: 1/7 topics complete - 14%]

========================================
Your Style Expression
========================================

ARI: How would you describe your style in a few words?

...
```

## Data Storage

Extracted data flows to Neo4j via existing services:

```python
# Extracted from conversation
{
  "advice_receptiveness": 7,
  "creative_control": 5,
  "decision_making_style": "curated_options",
  "risk_tolerance": 6
}

# Stored in Neo4j User node
User {
  stated_advice_receptiveness: 7,
  stated_creative_control: 5,
  decision_making_style: "curated_options",
  stated_risk_tolerance: 6
}
```

Multi-select responses create relationships:
```python
# Extracted
{
  "style_adjectives": ["Minimalist", "Professional", "Contemporary"]
}

# Creates relationships
(User)-[:IDENTIFIES_WITH {priority: 1}]->(StyleAdjective {name: "Minimalist"})
(User)-[:IDENTIFIES_WITH {priority: 2}]->(StyleAdjective {name: "Professional"})
(User)-[:IDENTIFIES_WITH {priority: 3}]->(StyleAdjective {name: "Contemporary"})
```

## Agent Capabilities

### Onboarding Agent
**Strengths:**
- Natural conversation flow
- Empathetic responses
- Sensitive topic handling
- Adaptive follow-up questions
- Reading between the lines

**Techniques:**
- Reflective listening ("It sounds like...")
- Open-ended questions
- Exploring uncertainty
- Validating responses
- Offering transitions

### Extraction Agent
**Strengths:**
- Parsing free-form responses
- Identifying implicit information
- Mapping to data schema
- Tracking completeness
- Validation

**Outputs:**
- Structured JSON data
- Completeness percentage
- Confidence levels
- Missing information list

## Comparison: CLI vs Conversational

### Old CLI Approach
```
Question: How open are you to style advice?
[Scale 1-10, 1=DIY, 10=tell me what to wear]
Enter value: _
```
- Rigid
- Assumes user understands scale
- No context
- No exploration

### Conversational Approach
```
ARI: Tell me about a recent shopping experience -
what was that like for you?

You: I went to the mall but got overwhelmed...

ARI: It sounds like having too many options made
it hard. Do you prefer when someone narrows things
down, or browsing everything?

You: Definitely prefer someone to narrow it down.

[Extracts: advice_receptiveness: 7, decision_making_style: "curated_options"]
```
- Natural
- Contextual understanding
- Allows exploration
- Feels human

## Advantages

1. **Better Data Quality**
   - Users give richer, more honest responses
   - Nuance is captured, not lost
   - Uncertainty is explored, not forced into boxes

2. **Sensitive Topic Handling**
   - Gender expression discussed respectfully
   - Identity exploration encouraged
   - No assumptions made

3. **User Experience**
   - Feels like talking to a stylist, not filling a form
   - Engaging and personal
   - Adaptable to communication style

4. **Flexibility**
   - Can go deep or stay surface level
   - User controls pacing
   - Can revisit topics

## Technical Details

### Dependencies
- CrewAI for agent orchestration
- Existing user_graph_manager for storage
- Existing onboarding_service for data mapping
- Neo4j for persistence

### LLM Usage
- Each conversation turn uses 2 LLM calls:
  1. Extraction agent analyzes response
  2. Onboarding agent generates next message

- Average onboarding: ~30-50 conversation turns
- Can use any OpenAI-compatible LLM

### Memory & Context
- Full conversation history maintained per step
- Context provided to agents on each turn
- Extracted data accumulated across conversation
- Progress tracked automatically

## Future Enhancements

1. **Resume Capability**
   - Save partial progress
   - Resume from any step
   - Update responses later

2. **Voice Interface**
   - Speech-to-text integration
   - Even more natural conversation

3. **Multi-language**
   - Detect user language
   - Conduct onboarding in native language

4. **Adaptive Depth**
   - AI decides when to go deeper
   - Detects user engagement level
   - Adjusts conversation complexity

5. **Visual Aids**
   - Show style images during conversation
   - "Which of these resonates?"
   - Combination of dialogue + visual

## Testing

Run a test conversation:
```bash
./run_onboarding.sh
```

Sample test scenario:
- User uncertain about preferences
- Explores gender expression in non-binary way
- Has specific budget constraints
- Values sustainability

The agent should:
- Not rush uncertain exploration
- Use inclusive, non-gendered language
- Validate budget without judgment
- Deep-dive on sustainability if user wants

## Troubleshooting

**Agent responses feel robotic:**
- Check agent backstory emphasizes warmth
- Ensure prompts don't sound like forms
- LLM temperature may need adjustment

**Data not being extracted:**
- Check extraction agent task description
- Verify JSON output format
- Review conversation for ambiguity

**Conversations too long:**
- Adjust completeness threshold (default 80%)
- Agent can be more directive about moving on
- User can always type "next"

**Sensitive topic issues:**
- Review sensitivity notes in prompts
- Ensure agent backstory emphasizes care
- Test with diverse scenarios

## Summary

The conversational onboarding system represents a paradigm shift from transactional data collection to discovery-based dialogue. By using AI agents to conduct empathetic conversations, we:

1. Collect richer, more nuanced data
2. Handle sensitive topics with care
3. Adapt to individual communication styles
4. Create a memorable, human experience
5. Build trust and rapport from the start

This sets the foundation for a truly personalized styling relationship.
