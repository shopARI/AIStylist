# UI/UX Customization Guide for Conversational Onboarding

This guide shows where to customize the onboarding experience **without touching complex Python logic**.

---

##  1. CONVERSATION CONTENT (Primary Customization Point)

### File: `prompts/onboarding_prompts.py`

**What it does:** Defines all 7 conversation topics, their flow, and AI behavior

**What can be customized:**

### A. Topic Titles
```python
"title": "How We'll Work Together"  # ← Change this to customize header
```

### B. Conversation Guidelines
```python
"conversation_guide": """
You're exploring how the user prefers to make style decisions.

Key areas to discover:  # ← Customize what the AI should explore
- Do they want guidance or complete control?
- How open are they to trying new things?

Conversation approach:  # ← Customize conversation style
- Start by asking how they typically shop
- Listen for cues about their comfort with advice

Sample conversation starters:  # ← Customize example questions
- "Tell me about a recent shopping experience..."
- "When you're getting dressed, do you prefer having options..."
"""
```

### C. Sensitivity Notes
```python
"sensitivity_notes": """
- Don't assume everyone shops the same way  # ← Add cultural considerations
- Respect if someone has had bad experiences
- Validate uncertainty - it's okay not to know
"""
```

### D. Add/Remove/Reorder Topics

The topics are processed in this order:
1. `style_autonomy` - How they make decisions
2. `gender_expression` - Style identity
3. `self_expression` - Goals and inspiration
4. `lifestyle_context` - Daily life needs
5. `values_shopping` - What matters to them
6. `budget` - Budget constraints
7. `demographics_contact` - Age, location, social

**To change order:** Reorder keys in `ONBOARDING_STEP_PROMPTS` dictionary

**To skip a topic:** Comment it out or remove it

**To add a topic:** Add a new dictionary entry following the same structure

---

##  2. DYNAMIC STYLE ADAPTATION

### File: `crews/onboarding_crew.py` (Lines 91-128)

**What it does:** Adjusts conversation style based on user's autonomy preferences

**What can be customized:**

### A. Directive Style (For users who want guidance)
```python
if style == "directive":
    return """
CONVERSATION STYLE ADAPTATION:
Based on this user's preferences, they want more guidance and direction.

Adjust your approach:
- Be more direct and specific in your questions  # ← Customize tone
- Offer concrete examples and suggestions
- Guide them toward decisions with your expertise
- Don't overwhelm with too many options
- Example: "Based on what you've shared, I'd recommend focusing on..."
    """
```

### B. Exploratory Style (For users who want freedom)
```python
elif style == "exploratory":
    return """
...
- Ask more open-ended questions  # ← Customize for creative users
- Let them lead the conversation
- Encourage exploration and experimentation
- Example: "Tell me more about what draws you to that style..."
    """
```

### C. Balanced Style (Default)
```python
else:  # balanced
    return """
...
- Mix directed questions with open exploration  # ← Customize middle ground
- Offer curated options (not too many, not just one)
- Example: "Here are a few directions we could explore..."
    """
```

### D. Autonomy Thresholds

**Line 75:** Adjust when system switches styles
```python
if autonomy_score <= 4 or decision_style == 'tell_me':
    return "directive"  # ← Change threshold (currently ≤4)
elif autonomy_score >= 7 or decision_style == 'many_options':
    return "exploratory"  # ← Change threshold (currently ≥7)
```

---

##  3. UI TEXT & MESSAGES

### File: `cli/chat_interface_v2.py`

**What can be customized:**

### A. Welcome Message (Lines 73-79)
```python
print("\n" + "=" * 70)
print(" Welcome to ARI - Your Personal Style Discovery Experience")  # ← Customize
print("=" * 70)
print("\nI'm here to help you discover and articulate your style identity.")  # ← Customize
print("This isn't a form or quiz - it's a conversation.")  # ← Customize
print("\nTake your time. There are no wrong answers.")  # ← Customize
print("=" * 70 + "\n")
```

### B. Progress Indicators (Lines 90-93)
```python
print(f"\n{'=' * 70}")
print(f" Topic {all_steps.index(step_id) + 1}/{len(all_steps)}")  # ← Customize format
print(f"{'=' * 70}\n")
```

### C. Completion Messages (Lines 131-133, 153)
```python
print("\n" + "=" * 70)
print(" Saving Your Style Profile...")  # ← Customize
print("=" * 70 + "\n")

print("Your style profile has been saved!\n")  # ← Customize
```

### D. User Prompts (Lines 103-107)
```python
user_input = input("You: ").strip()

if not user_input:
    print("(Please share your thoughts, or type 'skip' to move on)\n")  # ← Customize
    continue
```

### E. Skip/Navigation Messages (Lines 110-112)
```python
if user_input.lower() in ['skip', 'next']:  # ← Add more keywords
    crew.complete_step()
    break
```

---

##  4. CONVERSATION FLOW LOGIC

### File: `cli/chat_interface_v2.py` (Lines 115-128)

**What can be customized:**

### A. Auto-Completion Threshold
```python
if completeness >= 0.8 or 'move on' in agent_response.lower():  # ← Change 0.8 threshold
    crew.complete_step()
    step_complete = True
```

**Lower = moves on faster** (e.g., 0.6)
**Higher = more thorough** (e.g., 0.9)

### B. Move-On Detection
```python
if 'move on' in agent_response.lower():  # ← Add more phrases
    # Could add: 'next topic', 'ready to continue', etc.
```

---

##  5. DATA FIELDS COLLECTED

### File: `prompts/onboarding_prompts.py`

Each topic has a `"focus"` array defining what data is collected:

```python
"focus": [
    "advice_receptiveness",    # ← These determine what gets saved
    "creative_control",
    "risk_tolerance",
    "decision_making_style"
]
```

**To add a field:**
1. Add it to the `"focus"` array
2. Describe it in `"conversation_guide"`
3. Update extraction example in prompts

**To remove a field:**
- Remove from `"focus"` array

---

##  QUICK REFERENCE: What to Edit Where

| **What You Want to Change** | **File to Edit** | **Lines** |
|------------------------------|------------------|-----------|
| Conversation questions | `prompts/onboarding_prompts.py` | 11-354 |
| Topic order | `prompts/onboarding_prompts.py` | 11-12 |
| Welcome message | `cli/chat_interface_v2.py` | 73-79 |
| Progress format | `cli/chat_interface_v2.py` | 90-93 |
| Directive style tone | `crews/onboarding_crew.py` | 91-103 |
| Exploratory style tone | `crews/onboarding_crew.py` | 104-116 |
| Balanced style tone | `crews/onboarding_crew.py` | 117-128 |
| Autonomy thresholds | `crews/onboarding_crew.py` | 75-80 |
| Completion threshold | `cli/chat_interface_v2.py` | 123 |
| Skip/next commands | `cli/chat_interface_v2.py` | 110-112 |

---

##  WHAT NOT TO TOUCH (For Non-Developers)

**Files to avoid editing:**
- `services/user_graph_manager.py` - Database operations
- `services/user_service.py` - User creation logic
- `models/user_models.py` - Data structure definitions
- `agents/onboarding_agent.py` - AI agent configuration

**Lines to avoid in safe files:**
- Function definitions (`def function_name():`)
- Import statements (`from x import y`)
- Class definitions (`class ClassName:`)
- Return statements (`return ...`)

---

##  TESTING YOUR CHANGES

After making changes:

1. **Test the conversation flow:**
```bash
./run_chat.sh
```

2. **Check for Python syntax errors:**
```bash
python -m py_compile prompts/onboarding_prompts.py
```

3. **Verify prompt changes:**
```bash
python -c "from prompts.onboarding_prompts import get_all_step_ids; print(get_all_step_ids())"
```

---

##  COMMON CUSTOMIZATIONS

### Make conversations shorter:
- Reduce number of topics in `prompts/onboarding_prompts.py`
- Lower completion threshold from 0.8 to 0.6 in `cli/chat_interface_v2.py:123`

### Make conversations more thorough:
- Add more sample questions to each topic
- Raise completion threshold from 0.8 to 0.9
- Add more fields to `"focus"` arrays

### Change conversation tone:
- Edit the style guidance in `crews/onboarding_crew.py:91-128`
- Adjust language in conversation guides

### Add a new topic:
1. Add new entry to `ONBOARDING_STEP_PROMPTS` dictionary
2. Follow existing structure with title, focus, conversation_guide, sensitivity_notes

### Skip topics for certain users:
This requires Python code changes - consult a developer

---

##  NEED HELP?

**For conversation content changes:** Edit `prompts/onboarding_prompts.py` directly
**For UI text changes:** Edit `cli/chat_interface_v2.py` carefully
**For behavior changes:** Edit `crews/onboarding_crew.py` (ask developer if unsure)
**For everything else:** Ask the development team

---

##  EXAMPLE: Adding a New Topic

```python
# In prompts/onboarding_prompts.py, add to ONBOARDING_STEP_PROMPTS:

"color_preferences": {
    "title": "Colors That Speak to You",
    "focus": [
        "favorite_colors",
        "color_comfort_level",
        "seasonal_color_preferences"
    ],
    "conversation_guide": """
You're exploring the user's relationship with color.

Key areas to discover:
- What colors do they gravitate toward?
- Are they comfortable with bold colors or prefer neutrals?
- Do their color preferences change with seasons?

Conversation approach:
- Ask about colors that make them feel confident
- Explore past experiences with color choices
- Understand any color aversions or favorites

Sample conversation starters:
- "What colors make you feel most like yourself?"
- "Are there any colors you absolutely love or avoid?"
- "Do your color choices change with the seasons?"
    """,
    "sensitivity_notes": """
- Color preferences are deeply personal
- Some cultures have color associations to be aware of
- Not everyone has the same color vocabulary
    """
}
```

That's it! The AI will automatically have this new conversation topic.
