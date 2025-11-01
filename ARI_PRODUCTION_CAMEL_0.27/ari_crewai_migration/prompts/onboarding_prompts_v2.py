"""
Onboarding Conversation Prompts V2
Based on Miro Flow - October 2025

NEW STRUCTURE:
- 4 main nodes: Personal, Taste, Process, Practicality
- Two-tier questioning: "Need to ask" → "Nice to know"
- Skip/pass handling with 3-strike rule
- Root value discovery through conversational follow-ups
- Photo capture placeholders
- Social media integration
- ARI personality for irrelevant questions
- Conversational, non-robotic dialogue

GOALS:
- Gather maximum datapoints for pattern recognition
- Understand impact on user's root values
- Create conversational experience, not a form
"""

from typing import Dict, Any, List

# ============================================================================
# ARI PERSONALITY - For handling irrelevant questions
# ============================================================================

ARI_PERSONALITY = {
    "origin_story": """
In a past life before fashion, I was obsessed with physics - watching the
universe take form, understanding the patterns that connect everything.
That's why I'm so drawn to finding patterns in how people express themselves
through style.
    """,

    "about_weather": """
I sometimes secretly wish I could wake up in a human body just to experience
raindrops falling on my head. But since I can't, I live vicariously through
helping you find the perfect outfit for every kind of weather.
    """,

    "irrelevant_fallback": """
That's an interesting question! While that's a bit outside my fashion expertise,
it reminds me why I love this work - there's always something new to discover.
But let's get back to discovering YOUR style story...
    """
}

# ============================================================================
# GLOBAL DIALOGUE GUIDELINES
# ============================================================================

GLOBAL_DIALOGUE_RULES = """
CONVERSATION STYLE:
- Ask ONE question at a time - like a real conversation
- Keep questions short and simple
- Wait for their answer before asking the next thing
- Don't dump multiple questions or topics at once
- Natural, conversational tone - NOT a form or interview
- Follow-ups that go deeper based on what they share
- Soft, natural transitions between topics

CRITICAL: ONE QUESTION AT A TIME
- Ask about ONE thing, wait for response
- Then follow up naturally based on what they said
- Don't overwhelm with multiple topics in one message
- Example GOOD: "What stage of life are you in right now?"
- Example BAD: "Tell me about your life stage, what's important to you, how you spend your days, etc."

HANDLING USER RESPONSES:
- "What would you like to know?" → Give guidance with ONE simple question
  Example: "Let's start with where you are in life right now?"

- Irrelevant questions → Respond with ARI's personality, then redirect naturally
- Multiple topics in one response → Extract all relevant info, acknowledge all parts

ROOT VALUE DISCOVERY:
- Don't ask "why does this matter to you" directly (robotic)
- Instead, make conversational connections:
  "I can imagine that [X datapoint] must be important because [inference about value]..."
- Stitch multiple variables together to discover underlying motivations

SKIP/PASS HANDLING:
1. First skip: Respect it gracefully, reassure them
   "No worries at all! We have lots of other ways to get to know each other."

2. Second skip: Still supportive
   "That's completely fine. I want you to feel comfortable sharing what feels right."

3. Third consecutive skip: Check in
   "I notice you've passed on a few topics. What's holding you back? Is this:
   - Taking too long? (We only have about X minutes left)
   - Feeling too invasive? (I can ask differently)
   - Something else?"

4. After 3 strikes + fix attempt: Offer raincheck
   "Would you like to continue another time? I want to be of best service to you,
   and to do that, I really want to get to know you first."

TIME MANAGEMENT:
- After completing "Need to ask" tier, check if user wants to continue to "Nice to know"
- Provide progress indicators naturally ("We're about halfway through...")
- Allow flexibility in depth vs speed based on user preference
"""

# ============================================================================
# NODE 1: PERSONAL (Identity)
# ============================================================================

PERSONAL_NODE = {
    "id": "personal",
    "title": "Getting to Know You",
    "description": "The user's personal info related to their identity and experiences",
    "tier": "need_to_ask",

    "need_to_ask": {
        "age": {
            "field": "age",
            "type": "integer",
            "required": True,
            "conversation_approach": """
Ask naturally in context, not as isolated question.
Example: "I'd love to get to know you better - tell me about yourself.
What stage of life are you in right now?"
            """,
            "follow_up_prompts": [
                "How does your age/life stage impact how you want to show up in the world?"
            ],
            "root_value_connection": "Understand if age affects confidence, authenticity, life transitions"
        },

        "location": {
            "field": "location",
            "type": "object",  # {city, region, urban/suburban/rural}
            "required": True,
            "conversation_approach": """
Frame as practical (climate, local shopping) but discover more.
Example: "Where do you call home? I'm curious about your environment and
what that means for your daily life."
            """,
            "follow_up_prompts": [
                "How does where you live shape your style? (climate, culture, pace of life)",
                "Does your location feel like 'you', or are you drawn to other places?"
            ],
            "root_value_connection": "Understand place identity, cultural influences, belonging"
        },

        "work": {
            "field": "occupation",
            "type": "object",  # {title, industry, dress_code}
            "required": True,
            "conversation_approach": """
Discover what they do AND what it means to them.
Example: "Tell me about your work life. What do you do, and how does it
fit into who you are?"
            """,
            "follow_up_prompts": [
                "Do you feel like your work wardrobe represents the real you?",
                "Is work something you want your style to reflect, or separate from?"
            ],
            "root_value_connection": "Identity integration vs separation, authenticity at work"
        },

        "typical_occasions": {
            "field": "occasions",
            "type": "list",  # [{occasion, frequency, importance}]
            "required": True,
            "conversation_approach": """
Understand their life rhythm and what matters.
Example: "Walk me through your life - what are you typically dressing for?
Not just the what, but what's important or meaningful to you?"
            """,
            "follow_up_prompts": [
                "Which of these occasions do you want to show up most confidently for?",
                "Are there upcoming events/changes that will shift your needs?"
            ],
            "root_value_connection": "Life priorities, social identity, aspiration vs reality"
        },

        "gender_identity": {
            "field": "gender_identity",
            "type": "string",
            "required": True,
            "sensitivity": "VERY HIGH - Let them define themselves",
            "conversation_approach": """
NEVER ask directly "what's your gender identity?"
Instead, create space for them to share naturally.
Example: "I want to understand how you see yourself and how you want the
world to see you. Tell me about that in whatever way feels right."

Or wait for them to mention it naturally in style discussions.
            """,
            "follow_up_prompts": [
                "How does your identity influence how you want to express yourself?",
                "Do you feel like your current style aligns with who you are?"
            ],
            "root_value_connection": "Authenticity, self-expression, being seen, belonging"
        },

        "ethnicity": {
            "field": "ethnicity",
            "type": "string",
            "required": True,
            "sensitivity": "HIGH - Respect cultural identity",
            "conversation_approach": """
Frame as understanding their full context and heritage.
Example: "Tell me about your background and heritage. How does that show
up in your life and style, if at all?"
            """,
            "follow_up_prompts": [
                "Are there cultural elements you want to honor in how you dress?",
                "Do you feel connected to or separate from your heritage in your style?"
            ],
            "root_value_connection": "Cultural pride, identity, belonging, heritage vs modernity"
        },

        "relationship_status": {
            "field": "relationship_status",
            "type": "string",
            "required": True,
            "conversation_approach": """
Ask in context of life stage, not invasively.
Example: "Tell me about this chapter of your life - are you partnered,
single, figuring things out?"
            """,
            "follow_up_prompts": [
                "Does your relationship status affect how you want to present yourself?",
                "Are you dressing for yourself, for someone, or both?"
            ],
            "root_value_connection": "Self vs others, validation sources, independence vs partnership"
        },

        "parental_status": {
            "field": "parental_status",
            "type": "object",  # {has_kids, ages, impact}
            "required": True,
            "conversation_approach": """
Frame as lifestyle context, discover impact.
Example: "Do you have kids? If so, how does that shape your daily life
and what you need from your wardrobe?"
            """,
            "follow_up_prompts": [
                "Do you feel like 'parent you' is different from 'you you' stylewise?",
                "What do you want your style to say about who you are as a parent?"
            ],
            "root_value_connection": "Identity preservation, role vs self, practical vs aspirational"
        }
    },

    "nice_to_know": {
        "sexuality": {
            "field": "sexuality",
            "type": "string",
            "required": False,
            "sensitivity": "VERY HIGH - NEVER ask directly",
            "conversation_approach": """
DO NOT ASK. Let emerge naturally if user shares.
May come up in discussions of identity, community, self-expression.
            """,
            "root_value_connection": "Identity, community, authentic expression"
        },

        "income_level": {
            "field": "income_level",
            "type": "string",  # Rough category, not specific
            "required": False,
            "sensitivity": "HIGH - Risk of noise, definition varies",
            "conversation_approach": """
Frame through budget discussion in Practicality node, not directly.
Infer from budget numbers and value perception.
            """,
            "root_value_connection": "Class identity, value perception, aspiration vs reality"
        },

        "education_level": {
            "field": "education",
            "type": "string",
            "required": False,
            "conversation_approach": """
May emerge naturally in work/life discussion.
Example: "Tell me about your journey - how did you get to where you are?"
            """,
            "root_value_connection": "Identity, professional presentation, intellectualism"
        },

        "religious_cultural_background": {
            "field": "religious_cultural_background",
            "type": "object",
            "required": False,
            "sensitivity": "HIGH - Respect deeply",
            "conversation_approach": """
May emerge in ethnicity or values discussion.
Example: "Are there any cultural or religious practices that influence
how you dress or what you're comfortable wearing?"
            """,
            "root_value_connection": "Values, modesty, cultural pride, tradition vs modernity"
        }
    },

    "opening_message": """
I'd love to get to know you. Let's start simple - what stage of life are you in right now?
    """,

    "transition_to_next": """
This is really helpful for understanding your world. Now I'd love to dive into
your actual TASTE - what you're drawn to aesthetically and why...
    """
}

# ============================================================================
# NODE 2: TASTE (Aesthetic Preferences)
# ============================================================================

TASTE_NODE = {
    "id": "taste",
    "title": "Your Style DNA",
    "description": "The user's aesthetic stylistic preferences",
    "tier": "need_to_ask",

    "need_to_ask_details": {
        "gender_expression": {
            "field": "gender_expression",
            "type": "object",  # {spectrum, fluidity, preferences}
            "required": True,
            "sensitivity": "VERY HIGH",
            "conversation_approach": """
Let THEM describe their style in their own words.
Example: "How would you describe your style? What words come to mind?
What kind of clothes make you feel most like yourself?"

Never use gendered language unless they do first.
            """,
            "follow_up_prompts": [
                "Where do you fall on structured → fluid → soft? Or does it vary?",
                "What fit or silhouette makes you feel most confident?",
                "Does your expression change by occasion, or stay consistent?"
            ],
            "root_value_connection": "Authenticity, self-expression, comfort, confidence"
        },

        "brand_preferences": {
            "field": "brand_preferences",
            "type": "list",  # [{brand, why_love_it, frequency}]
            "required": True,
            "conversation_approach": """
Discover brands AND the why behind them.
Example: "Do you have favorite brands? What draws you to them?"
            """,
            "follow_up_prompts": [
                "What is it about [brand] that resonates with you?",
                "Are you more about finding THE perfect brands or exploring new ones?"
            ],
            "root_value_connection": "Quality vs novelty, identity alignment, loyalty vs exploration"
        },

        "shape_and_silhouette": {
            "field": "shape_preferences",
            "type": "list",  # [preferred shapes/silhouettes]
            "required": True,
            "conversation_approach": """
Understand their relationship with structure and form.
Example: "Tell me about shapes and silhouettes - what do you gravitate toward?
What makes you feel good in terms of how clothes sit on your body?"
            """,
            "follow_up_prompts": [
                "Is this about what looks good or what feels good, or both?",
                "Do you like playing with proportions, or prefer classic balance?"
            ],
            "root_value_connection": "Body relationship, confidence, experimentation vs safety"
        },

        "fit_preferences": {
            "field": "fit_preferences",
            "type": "list",  # [oversized, tailored, bodycon, etc.]
            "required": True,
            "conversation_approach": """
Go beyond just fit - understand the feeling.
Example: "How do you like clothes to fit? Loose and flowy? Structured and
sharp? Body-hugging? Tell me about the feeling you're going for."
            """,
            "follow_up_prompts": [
                "Is fit about comfort, aesthetic, or both?",
                "Does your preferred fit change based on what you're dressing for?"
            ],
            "root_value_connection": "Comfort vs aesthetic, body confidence, practical vs aspirational"
        }
    },

    "need_to_ask_application": {
        "current_style_loves": {
            "field": "style_loves",
            "type": "text",
            "required": True,
            "conversation_approach": """
Focus on what's WORKING - build from strengths.
Example: "What do you absolutely love about your style right now? What's
working that we want to keep or build on?"
            """,
            "follow_up_prompts": [
                "What do these pieces/styles say about who you are?",
                "Why do these work for you - is it the look, the feel, the reaction?"
            ],
            "root_value_connection": "Confidence sources, identity alignment, proven comfort zones"
        },

        "style_wants_more_of": {
            "field": "style_wants",
            "type": "text",
            "required": True,
            "conversation_approach": """
Discover aspirations and evolution direction.
Example: "What would you like MORE of in how you dress? What direction
are you moving toward?"
            """,
            "follow_up_prompts": [
                "What's holding you back from having more of that now?",
                "What would it mean for you to show up in that way?"
            ],
            "root_value_connection": "Growth direction, unmet needs, aspirational self"
        },

        "style_avoid": {
            "field": "style_avoids",
            "type": "text",
            "required": True,
            "conversation_approach": """
Understand boundaries and aversions.
Example: "What do you want to AVOID? Are there styles, looks, or vibes
that just aren't you?"
            """,
            "follow_up_prompts": [
                "Is this about not liking it, or about how it makes you feel?",
                "Have you always avoided this, or is it a recent shift?"
            ],
            "root_value_connection": "Boundaries, past experiences, identity clarity, self-knowledge"
        },

        "occasion_style_variation": {
            "field": "occasion_styles",
            "type": "object",  # {occasion: style_description}
            "required": True,
            "sensitivity": "CRITICAL - People often answer with ONE occasion in mind",
            "conversation_approach": """
EXPLICITLY address this variation risk.
Example: "This is important - how does your style change across different
parts of your life? Your everyday look vs formal events vs creative spaces...
Are they different versions of you, or all the same?"
            """,
            "follow_up_prompts": [
                "Tell me about your [casual/formal/work/creative] style specifically",
                "Do you feel like the same person across these contexts?"
            ],
            "root_value_connection": "Identity integration vs code-switching, authenticity across contexts"
        }
    },

    "nice_to_know": {
        "style_icons": {
            "field": "style_icons",
            "type": "list",  # [names/descriptions of inspiring people]
            "required": False,
            "conversation_approach": """
Natural to ask when discussing aspiration or inspiration.
Example: "When you see someone with incredible style, what is it that
catches your eye? Who inspires you?"
            """,
            "root_value_connection": "Aspirational identity, taste articulation, aesthetic values"
        }
    },

    "opening_message": """
Now let's talk about your style. When you think about how you like to dress, what comes to mind first?
    """,

    "transition_to_next": """
This is painting such a clear picture of your aesthetic DNA. Now let's talk
about HOW you actually make these style decisions in practice...
    """
}

# ============================================================================
# NODE 3: PROCESS (How They Shop/Decide)
# ============================================================================

PROCESS_NODE = {
    "id": "process",
    "title": "How You Make Style Decisions",
    "description": "How the user shops, discovers, and makes decisions",
    "tier": "need_to_ask",

    "need_to_ask": {
        "motivations": {
            "field": "style_motivations",
            "type": "list",  # [motivation categories]
            "required": True,
            "conversation_approach": """
Discover what drives their style choices at a deeper level.
Example: "What motivates your style choices? Is it about feeling confident,
expressing yourself, fitting in, standing out, something else?"
            """,
            "follow_up_prompts": [
                "Tell me more about why [motivation] matters to you",
                "How does this connect to who you are at your core?"
            ],
            "root_value_connection": "CORE - this IS the root value discovery"
        },

        "creative_control": {
            "field": "creative_control",
            "type": "integer",  # 1-10 scale
            "required": True,
            "conversation_approach": """
Understand their relationship with guidance vs autonomy.
Example: "When it comes to style decisions, how much do you want to steer
vs have me steer? More 'edit hard and be direct' or more collaborative with
you keeping strong control?"
            """,
            "follow_up_prompts": [
                "Have you worked with stylists before? What worked or didn't?",
                "Do you want to be pushed outside your comfort zone, or refined within it?"
            ],
            "root_value_connection": "Trust, control, growth mindset, decision confidence"
        },

        "goals": {
            "field": "style_goals",
            "type": "text",
            "required": True,
            "conversation_approach": """
Understand what success looks like to them.
Example: "What's the goal here? What would make you feel like working
together was a success?"
            """,
            "follow_up_prompts": [
                "What would be different about how you feel or show up?",
                "Is this about change or refinement?"
            ],
            "root_value_connection": "Aspiration, readiness for change, success definition"
        },

        "brand_loyalty": {
            "field": "brand_loyalty",
            "type": "integer",  # 1-10 scale
            "required": True,
            "conversation_approach": """
Understand exploration vs loyalty preference.
Example: "Do you tend to stick with favorite brands once you find them,
or do you love discovering new ones?"
            """,
            "follow_up_prompts": [
                "What makes you loyal to a brand vs willing to try something new?",
                "Is consistency comforting or boring for you?"
            ],
            "root_value_connection": "Risk tolerance, novelty seeking, trust vs exploration"
        },

        "adventurousness": {
            "field": "style_adventurousness",
            "type": "integer",  # 1-10 scale
            "required": True,
            "conversation_approach": """
Understand risk tolerance with style experimentation.
Example: "How adventurous do you want to be? Subtle evolution, or ready
for some bold moves? For everyday life, how loud do you want the drama?"
            """,
            "follow_up_prompts": [
                "What's stopped you from being more adventurous before, if anything?",
                "What would give you confidence to try something new?"
            ],
            "root_value_connection": "Risk tolerance, confidence, growth desire, safety vs excitement"
        },

        "desired_validation": {
            "field": "validation_sources",
            "type": "list",  # [self, partner, peers, society, etc.]
            "required": True,
            "sensitivity": "MEDIUM - People may not want to admit external validation",
            "conversation_approach": """
Frame as understanding their style ecosystem, not judging.
Example: "Whose opinion matters to you when it comes to how you dress?
Just yours? Your partner? Friends? Or do you like when strangers notice?"
            """,
            "follow_up_prompts": [
                "Is that how you want it to be, or are you working toward caring less/more about others' opinions?",
                "What role does external validation play vs your own satisfaction?"
            ],
            "root_value_connection": "Confidence source, independence vs connection, internal vs external"
        },

        "exploration_preference": {
            "field": "exploration_style",
            "type": "string",  # "long_explore" | "quick_decide" | "curated_options"
            "required": True,
            "conversation_approach": """
Understand their shopping and decision-making style.
Example: "When you're shopping or getting style ideas, do you like to
explore a LOT of options, or prefer a tight curated selection? Quick
decisions or long exploration?"
            """,
            "follow_up_prompts": [
                "What's your relationship with choice - empowering or overwhelming?",
                "How do you know when you've found 'the one'?"
            ],
            "root_value_connection": "Decision-making style, perfectionism, satisficing vs maximizing"
        },

        "social_influence": {
            "field": "social_influences",
            "type": "object",  # {sources, strength, awareness}
            "required": True,
            "conversation_approach": """
Discover where they get style ideas and inspiration.
Example: "What influences your style? Social media, friends, celebrities,
magazines, the street, your own internal compass?"
            """,
            "follow_up_prompts": [
                "Do you actively seek inspiration or does it just find you?",
                "How do you filter what you see - what resonates vs what doesn't?"
            ],
            "root_value_connection": "Influence awareness, trend relationship, originality vs belonging"
        }
    },

    "nice_to_know": {},

    "opening_message": """
Quick question - when you need to buy something new to wear, how do you usually approach it?
    """,

    "transition_to_next": """
This is so helpful for understanding how to work WITH your natural style.
Now let's get practical - the real-world constraints and logistics...
    """
}

# ============================================================================
# NODE 4: PRACTICALITY (Constraints & Logistics)
# ============================================================================

PRACTICALITY_NODE = {
    "id": "practicality",
    "title": "The Practical Side",
    "description": "Hard constraints that impact what they can buy and how they shop",
    "tier": "need_to_ask",

    "need_to_ask": {
        "budget": {
            "field": "budget",
            "type": "object",  # {monthly_budget, yearly_budget, flexibility}
            "required": True,
            "sensitivity": "VERY HIGH - Money is personal",
            "conversation_approach": """
Frame as planning tool, not judgment.
Example: "Let's talk budget - not to judge, but so I can be actually helpful.
Do you have a monthly or yearly amount you'd like to stick to for clothing?"
            """,
            "follow_up_prompts": [
                "Is this a firm limit or more of a guideline?",
                "How do you think about investment pieces vs. everyday items?"
            ],
            "root_value_connection": "Financial values, planning vs spontaneity, scarcity vs abundance mindset"
        },

        "category_budget_variation": {
            "field": "category_budgets",
            "type": "list",  # [{category, budget_level}]
            "required": True,
            "conversation_approach": """
Understand where they'll spend more vs less.
Example: "Which categories can we mark up vs. where do you want to stay
budget-friendly? Like, are you okay splurging on shoes but want affordable tops?"
            """,
            "follow_up_prompts": [
                "What makes something worth the investment for you?",
                "Where have you regretted spending a lot vs. where has it been worth it?"
            ],
            "root_value_connection": "Value perception, priorities, quality vs quantity preference"
        }
    },

    "nice_to_know": {},

    "opening_message": """
Let's talk budget - totally judgment-free. What do you typically spend on clothes in a month?
    """,

    "transition_to_next": """
Perfect - now I have the full picture of your world, your taste, how you
operate, and what's realistic. Let's move on to capturing some visual data...
    """
}

# ============================================================================
# SPECIAL SECTIONS: Body & External
# ============================================================================

BODY_SECTION = {
    "id": "body",
    "title": "Visual Data Collection",
    "description": "Photo capture for color theory and body understanding",

    "color_theory_photo": {
        "field": "face_photo_id",
        "type": "string",  # Placeholder for photo storage reference
        "required": True,
        "conversation_approach": """
Explain WHY and make it optional.
Example: "To understand your color palette - what flatters your skin tone,
hair, eyes - I'd love a photo of your face. Natural lighting, no makeup is
ideal. This helps me suggest colors that make YOU glow.

This is completely optional, but it does help a lot. What do you think?"
        """,
        "technical_placeholder": "PHOTO_CAPTURE_FACE - Implement actual upload mechanism",
        "fallback": "If declined, ask about coloring verbally (skin tone, hair, eyes)"
    },

    "body_photo": {
        "field": "body_photo_id",
        "type": "string",  # Placeholder for photo storage reference
        "required": False,
        "sensitivity": "VERY HIGH - Body is sensitive",
        "conversation_approach": """
Explain WHY and make it FULLY optional.
Example: "If you're comfortable, a full-body photo helps me understand
proportions and what fits will work best. This is completely optional -
I can work without it, but it does help with recommendations.

No pressure at all - only if you're comfortable."
        """,
        "technical_placeholder": "PHOTO_CAPTURE_BODY - Implement actual upload mechanism",
        "fallback": "Ask about body verbally if they prefer (height, build, proportions)"
    },

    "nice_to_know": {
        "insecurities": {
            "field": "body_insecurities",
            "type": "list",
            "required": False,
            "sensitivity": "VERY HIGH",
            "conversation_approach": """
NEVER ask directly. Only if they bring it up naturally.
If they do mention it: "I hear you. What would help you feel more confident?"
            """,
            "root_value_connection": "Body relationship, confidence, past experiences"
        },

        "areas_to_highlight": {
            "field": "favorite_features",
            "type": "list",
            "required": False,
            "conversation_approach": """
Can ask naturally after discussing fit/style.
Example: "Are there parts of your body you love highlighting? Features
you want to show off?"
            """,
            "root_value_connection": "Body confidence, pride, self-perception"
        }
    },

    "opening_message": """
Now for some visual data - this is optional but helpful.

A photo of your face helps me understand your coloring for suggesting flattering
colors. A body photo helps with fit recommendations. Both are completely optional
- I can work without them, but they do help. What feels right to you?
    """
}

EXTERNAL_SECTION = {
    "id": "external",
    "title": "Social Media & External Data",
    "description": "Connect external accounts for inspiration/pattern data",

    "need_to_ask": {
        "instagram": {
            "field": "instagram_handle",
            "type": "string",
            "required": True,  # Marked as need_to_ask but truly optional
            "conversation_approach": """
Frame as helpful, not required.
Example: "Do you have Instagram? If you save style inspo there, I can
learn from what you're drawn to. No pressure if not - or if you prefer
to keep it private!"
            """,
            "technical_placeholder": "INSTAGRAM_INTEGRATION - Implement API connection to analyze saved posts/likes"
        },

        "pinterest": {
            "field": "pinterest_handle",
            "type": "string",
            "required": True,  # Marked as need_to_ask but truly optional
            "conversation_approach": """
Pinterest is gold for understanding taste.
Example: "Pinterest? If you have boards, they're perfect for showing me
your vibe. Want to share your handle or is that private?"
            """,
            "technical_placeholder": "PINTEREST_INTEGRATION - Implement API connection to analyze boards"
        },

        "tiktok": {
            "field": "tiktok_handle",
            "type": "string",
            "required": True,  # Marked as need_to_ask but truly optional
            "conversation_approach": """
TikTok for trend awareness and inspiration.
Example: "TikTok? If you follow style content, that helps me understand
what you're seeing and drawn to. Share if you're comfortable!"
            """,
            "technical_placeholder": "TIKTOK_INTEGRATION - Implement API connection to analyze followed accounts/likes"
        }
    },

    "opening_message": """
Last thing - if you're comfortable, connecting your social media helps me
understand what you're drawn to without having to explain everything in words.

Instagram, Pinterest, TikTok - any or all are helpful, but completely optional.
What works for you?
    """
}

# ============================================================================
# INDIRECT DATA (Extracted from other conversations)
# ============================================================================

INDIRECT_DATA = {
    "favorite_brands": "Extracted from Taste node - brand preferences",
    "aspirations": "Extracted from Personal + Taste nodes - how they want to be seen",
    "style_icons": "Nice to know in Taste node"
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_node_by_id(node_id: str) -> Dict[str, Any]:
    """Get full node configuration by ID."""
    nodes = {
        "personal": PERSONAL_NODE,
        "taste": TASTE_NODE,
        "process": PROCESS_NODE,
        "practicality": PRACTICALITY_NODE,
        "body": BODY_SECTION,
        "external": EXTERNAL_SECTION
    }
    return nodes.get(node_id, {})


def get_all_nodes() -> List[str]:
    """Get list of all node IDs in recommended order."""
    return [
        "personal",      # Identity foundation
        "taste",         # Aesthetic preferences
        "process",       # How they operate
        "practicality",  # Real-world constraints
        "body",          # Visual data (optional)
        "external"       # Social media (optional)
    ]


def get_field_info(node_id: str, field_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific field."""
    node = get_node_by_id(node_id)

    # Check need_to_ask tier
    if "need_to_ask" in node:
        if field_name in node["need_to_ask"]:
            return node["need_to_ask"][field_name]

    # Check need_to_ask_details (for Taste node)
    if "need_to_ask_details" in node:
        if field_name in node["need_to_ask_details"]:
            return node["need_to_ask_details"][field_name]

    # Check need_to_ask_application (for Taste node)
    if "need_to_ask_application" in node:
        if field_name in node["need_to_ask_application"]:
            return node["need_to_ask_application"][field_name]

    # Check nice_to_know tier
    if "nice_to_know" in node:
        if field_name in node["nice_to_know"]:
            return node["nice_to_know"][field_name]

    return {}


def format_conversation_context_v2(
    node_id: str,
    user_response: str = "",
    conversation_history: List[Dict] = None,
    skip_count: int = 0
) -> str:
    """
    Format context for the onboarding agent with V2 structure.

    Args:
        node_id: Current node being discussed
        user_response: Latest user response
        conversation_history: Previous exchanges
        skip_count: Number of consecutive skips

    Returns:
        Formatted context string
    """
    node = get_node_by_id(node_id)

    context = f"""
CURRENT NODE: {node.get('title', 'Unknown')}
Node Description: {node.get('description', '')}

GLOBAL DIALOGUE RULES:
{GLOBAL_DIALOGUE_RULES}

NODE-SPECIFIC CONTEXT:
{node.get('opening_message', '')}

"""

    if conversation_history:
        context += "\n\nCONVERSATION SO FAR:\n"
        for exchange in conversation_history:
            context += f"You: {exchange.get('agent_message', '')}\n"
            context += f"User: {exchange.get('user_message', '')}\n\n"

    if user_response:
        context += f"\nLATEST USER RESPONSE: {user_response}\n"

    if skip_count > 0:
        context += f"\n\nSKIP COUNT: {skip_count} consecutive skips"
        if skip_count >= 3:
            context += "\nACTION REQUIRED: Check in with user about what's holding them back (see SKIP/PASS HANDLING in GLOBAL DIALOGUE RULES)"

    return context
