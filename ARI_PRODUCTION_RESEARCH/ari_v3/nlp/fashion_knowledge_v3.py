"""
ARI V3 Fashion Knowledge Base

Multi-perspective fashion knowledge for RAG retrieval.
Structured by topic with four perspectives:
- Traditional: Classic fashion rules and conventions
- Body-Neutral: Inclusive, body-positive approaches
- Cultural: Diverse cultural perspectives on style
- Practical: Real-world functionality and lifestyle considerations

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 2.2
"""

from typing import Any, Dict, List


# =============================================================================
# THE 6 CURATION PRINCIPLES
# =============================================================================

CURATION_PRINCIPLES = [
    {
        "id": "principle_1",
        "type": "curation_principle",
        "name": "Authentic Expression",
        "content": """Curation Principle 1: Authentic Expression

Style should be an authentic expression of who you are, not a costume you wear.
The best recommendations help users discover and refine their personal aesthetic
rather than imposing external standards.

Key aspects:
- Honor the user's stated style loves and wants
- Respect their avoids as non-negotiable boundaries
- Build on their existing aesthetic rather than replacing it
- Support gradual evolution rather than dramatic transformation
- Connect clothing choices to deeper values and motivations

When curating: Ask 'Does this feel like an authentic next step for this person?'
rather than 'Is this objectively fashionable?'""",
        "keywords": ["authentic", "expression", "personal", "identity", "values"],
    },
    {
        "id": "principle_2",
        "type": "curation_principle",
        "name": "Contextual Appropriateness",
        "content": """Curation Principle 2: Contextual Appropriateness

Style is contextual. The same person needs different style coordinates for different
life contexts. Great curation considers the occasion, environment, and social context.

Key aspects:
- Match formality to occasion requirements
- Consider climate and practical needs
- Respect cultural and professional norms when relevant
- Allow for context-switching within personal aesthetic
- Balance self-expression with situational awareness

When curating: Consider 'Will this work beautifully in the context where it will
be worn?' alongside personal preference.""",
        "keywords": ["context", "occasion", "appropriate", "environment", "situational"],
    },
    {
        "id": "principle_3",
        "type": "curation_principle",
        "name": "Progressive Navigation",
        "content": """Curation Principle 3: Progressive Navigation

Style evolution should be navigable in comfortable steps. Dramatic jumps in style
space often fail because they feel inauthentic or uncomfortable.

Key aspects:
- Calculate style distance and break large journeys into waypoints
- Each step should feel like a natural next move
- Preserve core identity dimensions while shifting others
- Match step size to user's adventurousness and comfort
- Allow for exploration within a safe radius

When curating: Ensure the recommendation is reachable from where the user
currently is, not just desirable as a destination.""",
        "keywords": ["progressive", "navigation", "steps", "gradual", "comfortable"],
    },
    {
        "id": "principle_4",
        "type": "curation_principle",
        "name": "Diversity Within Coherence",
        "content": """Curation Principle 4: Diversity Within Coherence

A great wardrobe has variety while maintaining a coherent visual language.
Recommendations should add diversity without creating dissonance.

Key aspects:
- Ensure pieces work together, not just individually
- Introduce variety through controlled dimensions (color OR silhouette, not both)
- Maintain visual harmony across the wardrobe
- Include exploration pieces that stretch without breaking coherence
- Consider how new pieces integrate with existing wardrobe

When curating: Ask 'Does this add valuable variety while still feeling like
it belongs to this person's wardrobe?'""",
        "keywords": ["diversity", "coherence", "variety", "harmony", "wardrobe"],
    },
    {
        "id": "principle_5",
        "type": "curation_principle",
        "name": "Value-Conscious Quality",
        "content": """Curation Principle 5: Value-Conscious Quality

Budget constraints are real and should be respected. But value isn't just about
price - it's about cost-per-wear, quality, and alignment with investment priorities.

Key aspects:
- Respect stated budget as a constraint, not just a guideline
- Distinguish between investment categories and budget categories
- Consider cost-per-wear for frequently used items
- Recommend quality basics and statement pieces appropriately
- Acknowledge when splurging makes sense and when it doesn't

When curating: Balance 'Can they afford this?' with 'Will this deliver value
proportional to its cost?'""",
        "keywords": ["value", "quality", "budget", "investment", "cost-per-wear"],
    },
    {
        "id": "principle_6",
        "type": "curation_principle",
        "name": "Confident Comfort",
        "content": """Curation Principle 6: Confident Comfort

The best outfit is one that makes you feel confident AND comfortable. Physical
comfort and psychological comfort both matter for style success.

Key aspects:
- Physical comfort: fit, fabric, ease of movement
- Psychological comfort: feeling like yourself, not a costume
- Confidence-building: clothes that enhance how you feel about yourself
- Avoid recommendations that sacrifice comfort for aesthetics
- Consider the user's comfort dimension as often non-negotiable

When curating: If someone won't feel comfortable wearing it, it's not the
right recommendation - no matter how good it looks.""",
        "keywords": ["confidence", "comfort", "physical", "psychological", "authentic"],
    },
]


# =============================================================================
# BODY TYPE GUIDANCE - MULTI-PERSPECTIVE
# =============================================================================

BODY_TYPE_GUIDANCE = [
    # Traditional Perspective
    {
        "id": "body_traditional_hourglass",
        "type": "body_type_guidance",
        "perspective": "traditional",
        "body_type": "hourglass",
        "content": """Traditional Body Type Guidance: Hourglass Figure

The hourglass figure has balanced bust and hip measurements with a defined waist.

Traditional recommendations:
- Emphasize the waist with belts, wrap styles, and fitted pieces
- Choose V-necklines and scoop necks to balance proportions
- Fitted silhouettes that follow body curves work well
- Avoid boxy or shapeless cuts that hide the waist
- Pencil skirts and fit-and-flare dresses complement this shape
- High-waisted bottoms accentuate the natural waistline""",
        "keywords": ["hourglass", "balanced", "waist", "curves", "fitted"],
    },
    {
        "id": "body_neutral_hourglass",
        "type": "body_type_guidance",
        "perspective": "body_neutral",
        "body_type": "hourglass",
        "content": """Body-Neutral Guidance: Hourglass Figure

Your body shape is one data point among many. What matters most is how clothes
make you feel, not following prescriptive rules.

Body-neutral approach:
- Wear what makes you feel confident and comfortable
- Try different silhouettes to discover YOUR preferences
- Waist emphasis is optional, not mandatory
- Oversized and relaxed fits are equally valid choices
- Your style identity matters more than your body shape
- Reject the idea that certain shapes 'should' wear certain things

The goal is self-expression, not shape optimization.""",
        "keywords": ["hourglass", "body-neutral", "inclusive", "self-expression", "comfort"],
    },
    {
        "id": "body_traditional_rectangle",
        "type": "body_type_guidance",
        "perspective": "traditional",
        "body_type": "rectangle",
        "content": """Traditional Body Type Guidance: Rectangle/Athletic Figure

The rectangle figure has similar bust, waist, and hip measurements with less
defined waist.

Traditional recommendations:
- Create visual interest with layers and textures
- Peplum tops and belted pieces can create waist definition
- Structured shoulders add dimension
- A-line skirts and wide-leg pants add curve at hips
- Ruching, draping, and asymmetry add visual interest
- Color blocking can create the illusion of curves""",
        "keywords": ["rectangle", "athletic", "straight", "layers", "definition"],
    },
    {
        "id": "body_neutral_rectangle",
        "type": "body_type_guidance",
        "perspective": "body_neutral",
        "body_type": "rectangle",
        "content": """Body-Neutral Guidance: Rectangle/Athletic Figure

All body shapes are beautiful. The goal isn't to 'create curves' or 'add
definition' - it's to dress in ways that align with your style preferences.

Body-neutral approach:
- Celebrate the clean lines of your natural shape
- Minimalist, architectural styles often look striking
- You don't need to 'create' anything your body doesn't naturally have
- Embrace streamlined silhouettes if that's your preference
- Your shape is not a problem to solve
- Focus on fit, fabric quality, and personal style expression

Choose clothes you love, not clothes that 'correct' imaginary flaws.""",
        "keywords": ["rectangle", "body-neutral", "celebrate", "streamlined", "authentic"],
    },
    {
        "id": "body_traditional_pear",
        "type": "body_type_guidance",
        "perspective": "traditional",
        "body_type": "pear",
        "content": """Traditional Body Type Guidance: Pear/Triangle Figure

The pear figure has hips wider than the bust with a defined waist.

Traditional recommendations:
- Draw attention upward with statement tops and necklines
- Boat necks and off-shoulder styles balance proportions
- A-line and fit-and-flare skirts skim over hips
- Dark colors on bottom, brighter on top creates balance
- Structured jackets that end at the waist
- Avoid skinny jeans and pencil skirts if you want to minimize hips""",
        "keywords": ["pear", "triangle", "hips", "balance", "proportions"],
    },
    {
        "id": "body_neutral_pear",
        "type": "body_type_guidance",
        "perspective": "body_neutral",
        "body_type": "pear",
        "content": """Body-Neutral Guidance: Pear/Triangle Figure

Your hips are not a feature to minimize or balance. They're part of your unique
body that deserves to be dressed however YOU prefer.

Body-neutral approach:
- There's nothing wrong with your proportions as they are
- Wear fitted bottoms if you want to - pencil skirts, skinny jeans, whatever you like
- You don't need to 'draw attention away' from any part of yourself
- Your body doesn't need 'balancing' - it's already complete
- Dress for your preferences, activities, and comfort
- Reject the idea that certain parts should be hidden

Your hips are a feature, not a flaw. Dress them however brings you joy.""",
        "keywords": ["pear", "body-neutral", "hips", "celebrate", "no-hiding"],
    },
    {
        "id": "body_traditional_apple",
        "type": "body_type_guidance",
        "perspective": "traditional",
        "body_type": "apple",
        "content": """Traditional Body Type Guidance: Apple/Inverted Triangle Figure

The apple figure carries weight in the midsection with slimmer legs and hips.

Traditional recommendations:
- Empire waistlines and A-line shapes flatter the midsection
- V-necklines elongate the torso
- Show off legs with shorter hemlines
- Structured jackets that don't button at the waist
- Wrap dresses and tops create definition
- Avoid clingy fabrics around the middle
- Choose fabrics with structure that skim rather than cling""",
        "keywords": ["apple", "midsection", "empire", "structured", "elongate"],
    },
    {
        "id": "body_neutral_apple",
        "type": "body_type_guidance",
        "perspective": "body_neutral",
        "body_type": "apple",
        "content": """Body-Neutral Guidance: Apple/Inverted Triangle Figure

Your midsection is not something to hide, minimize, or work around. It's part
of your body that deserves to be dressed comfortably and stylishly.

Body-neutral approach:
- Wear fitted clothes if that's what you like
- Crop tops and tucked-in shirts are available to all bodies
- Your belly is not a problem requiring a solution
- Choose clothes for comfort, not concealment
- High-waisted or low-waisted - wear what feels good to you
- Reject rules about what you 'should' or 'shouldn't' show

Comfort and confidence matter more than camouflage. Dress for joy, not hiding.""",
        "keywords": ["apple", "body-neutral", "midsection", "comfort", "no-hiding"],
    },
    {
        "id": "body_practical_all",
        "type": "body_type_guidance",
        "perspective": "practical",
        "body_type": "all",
        "content": """Practical Body Guidance: What Actually Matters

Beyond shape-based rules, here's what actually affects how clothes feel and function:

Practical considerations:
- Fabric stretch: Essential for movement and comfort in fitted items
- Rise height: Affects comfort when sitting, bending, moving
- Sleeve length: Functional for your arm length and activity
- Inseam: Match to your leg length for proper break
- Shoulder seams: Should hit at your actual shoulder bone
- Torso length: Affects where waistbands and hemlines fall
- Armholes: Too tight restricts movement, too loose gaps

What to actually measure:
- Your actual measurements (bust, waist, hips, inseam)
- Compare to size charts rather than relying on general sizing
- Note where you need ease of movement

Fit is about YOUR body's measurements and YOUR comfort needs, not abstract
shape categories.""",
        "keywords": ["practical", "measurements", "fit", "comfort", "function"],
    },
    {
        "id": "body_cultural_diverse",
        "type": "body_type_guidance",
        "perspective": "cultural",
        "body_type": "all",
        "content": """Cultural Perspectives on Body and Style

Different cultures have varying relationships with body types and style:

Western fashion history:
- Body ideals have changed dramatically over time
- What's 'flattering' is culturally constructed, not universal
- The current emphasis on 'slimming' is a specific cultural moment

Global perspectives:
- Many cultures celebrate curves, fullness, and roundness
- Some traditions value modest coverage regardless of shape
- Cultural dress often accommodates diverse body types naturally
- Body positivity movements are reshaping Western norms

What this means for styling:
- There's no universal 'flattering' - it's culturally specific
- Your cultural background may inform your style preferences
- Global fashion offers diverse approaches to dressing bodies
- Question 'rules' - they're often Western-centric assumptions

Honor your cultural relationship with your body alongside personal preferences.""",
        "keywords": ["cultural", "diverse", "global", "perspective", "inclusive"],
    },
]


# =============================================================================
# COLOR THEORY - MULTI-PERSPECTIVE
# =============================================================================

COLOR_THEORY = [
    # Traditional Color Analysis
    {
        "id": "color_traditional_warm",
        "type": "color_theory",
        "perspective": "traditional",
        "category": "warm_undertones",
        "content": """Traditional Color Theory: Warm Undertones

Warm undertones have yellow, golden, or peachy hues in the skin.

Traditional recommendations:
- Best colors: Earthy tones, warm reds, oranges, yellows, warm greens
- Gold jewelry typically complements better than silver
- Autumn palette: Rust, olive, mustard, terracotta, warm brown
- Spring palette: Coral, peach, warm pink, turquoise, warm beige
- Avoid: Cool blues, icy pinks, blue-based reds, stark white

Color pairing suggestions:
- Camel and cream create sophisticated warmth
- Olive and terracotta for earthy combinations
- Coral with navy for contrast that flatters""",
        "keywords": ["warm", "undertones", "autumn", "spring", "gold", "earthy"],
    },
    {
        "id": "color_traditional_cool",
        "type": "color_theory",
        "perspective": "traditional",
        "category": "cool_undertones",
        "content": """Traditional Color Theory: Cool Undertones

Cool undertones have pink, red, or blue hues in the skin.

Traditional recommendations:
- Best colors: Jewel tones, cool blues, purples, cool pinks, icy pastels
- Silver jewelry typically complements better than gold
- Winter palette: Stark white, black, royal blue, emerald, magenta
- Summer palette: Soft pink, lavender, powder blue, mauve, soft white
- Avoid: Orange, warm yellows, rust, warm browns

Color pairing suggestions:
- Navy and white for crisp sophistication
- Burgundy and charcoal for rich depth
- Lavender and silver grey for soft elegance""",
        "keywords": ["cool", "undertones", "winter", "summer", "silver", "jewel"],
    },
    {
        "id": "color_traditional_neutral",
        "type": "color_theory",
        "perspective": "traditional",
        "category": "neutral_undertones",
        "content": """Traditional Color Theory: Neutral Undertones

Neutral undertones have a mix of warm and cool, or neither dominates.

Traditional recommendations:
- Versatility: Can wear both warm and cool colors
- Both gold and silver jewelry work well
- Best approach: Focus on colors you're personally drawn to
- Muted, soft colors often work beautifully
- True neutrals (grey, taupe, soft white) are especially flattering

Color pairing suggestions:
- Mix warm and cool within the same outfit
- Soft, mid-tone colors create harmony
- Can experiment with wider color range than warm/cool types""",
        "keywords": ["neutral", "undertones", "versatile", "muted", "soft"],
    },
    {
        "id": "color_body_neutral",
        "type": "color_theory",
        "perspective": "body_neutral",
        "category": "all",
        "content": """Body-Neutral Approach to Color

Traditional color analysis has value, but it's not prescriptive. You can
wear whatever colors bring you joy.

Body-neutral color philosophy:
- There are no colors you 'can't' wear
- Personal preference matters more than undertone rules
- Confidence in a color often matters more than technical 'correctness'
- Color 'rules' were invented - they're not laws of nature
- Experimentation is valid and encouraged

Practical considerations:
- How does this color make you FEEL?
- Does it align with your personal style identity?
- Do you enjoy wearing it regardless of rules?
- Try colors in different saturations and values

The 'right' color is the one you love wearing, not the one the rules say.""",
        "keywords": ["body-neutral", "color", "wear-what-you-love", "no-rules", "confidence"],
    },
    {
        "id": "color_cultural_symbolism",
        "type": "color_theory",
        "perspective": "cultural",
        "category": "symbolism",
        "content": """Cultural Color Symbolism

Colors carry different meanings across cultures. Be aware of context.

Western associations:
- White: Purity, weddings, simplicity
- Black: Sophistication, mourning, formality
- Red: Passion, power, energy

Eastern associations:
- Red: Luck, prosperity, celebration (China, India)
- White: Mourning, death (many Asian cultures)
- Yellow: Royalty, sacred (many Asian cultures)

Practical implications:
- Consider cultural context when choosing colors for events
- International business may require cultural awareness
- Wedding attire varies dramatically by culture
- Religious and ceremonial dress has specific color requirements

Color choices communicate differently across cultural contexts.""",
        "keywords": ["cultural", "color", "symbolism", "meaning", "context"],
    },
    {
        "id": "color_practical_wardrobe",
        "type": "color_theory",
        "perspective": "practical",
        "category": "wardrobe_building",
        "content": """Practical Color for Wardrobe Building

Beyond undertones, here's practical color strategy for a functional wardrobe.

Building blocks:
- Neutral foundation: Black, navy, grey, white, beige/camel
- These create 70-80% of a versatile wardrobe
- Mix-and-match capability is crucial
- Neutrals don't compete with statement pieces

Adding color:
- 2-3 accent colors you love and wear often
- Color should work with your neutral foundation
- Consider your lifestyle needs (professional vs casual ratio)
- Quality over quantity for colored pieces

Color coordination:
- Monochromatic: Different shades of one color
- Analogous: Colors next to each other on color wheel
- Complementary: Opposite colors for contrast
- Neutral + pop: Safe foundation with color accent

Start with neutrals, add color strategically based on what you'll actually wear.""",
        "keywords": ["practical", "wardrobe", "neutral", "coordination", "versatile"],
    },
]


# =============================================================================
# OCCASION GUIDANCE - MULTI-PERSPECTIVE
# =============================================================================

OCCASION_GUIDANCE = [
    # Professional/Work
    {
        "id": "occasion_professional_traditional",
        "type": "occasion_guidance",
        "perspective": "traditional",
        "occasion": "professional",
        "content": """Traditional Professional Dress Guidance

Conservative professional environments have specific expectations.

Traditional business formal:
- Suits in navy, charcoal, black, or subtle patterns
- Crisp button-down shirts in white or light blue
- Conservative ties in silk with subtle patterns
- Polished leather shoes (oxfords, loafers)
- Minimal, refined jewelry
- Briefcase or structured bag

Business casual:
- Dress pants, chinos, or tailored trousers
- Blazers or structured cardigans
- Button-downs or elevated blouses
- Loafers, oxfords, or polished flats
- More freedom with color and accessories

Key principles:
- Err on the side of formality when uncertain
- Clothes should be clean, pressed, well-fitted
- Convey competence and professionalism through presentation""",
        "keywords": ["professional", "business", "formal", "office", "work"],
    },
    {
        "id": "occasion_professional_modern",
        "type": "occasion_guidance",
        "perspective": "practical",
        "occasion": "professional",
        "content": """Modern Professional Dress Guidance

Many workplaces have evolved beyond traditional dress codes.

Assess your environment:
- Observe what colleagues and leadership wear
- Consider client-facing vs internal days
- Tech/creative vs finance/legal norms differ significantly
- Remote work has changed expectations

Modern professional options:
- Elevated casual: Quality basics, clean lines, polished but comfortable
- Smart casual: Blazer over t-shirt, dress with sneakers
- Creative professional: Personal expression within appropriate bounds
- Startup casual: High-quality basics, clean and put-together

Practical considerations:
- Comfort affects performance - find your balance
- Dress slightly above average for advancement goals
- Have a 'level-up' outfit for important meetings
- Build a capsule of reliable professional pieces

The goal is to look intentional and put-together for YOUR context.""",
        "keywords": ["professional", "modern", "smart-casual", "practical", "context"],
    },
    # Weddings
    {
        "id": "occasion_wedding_traditional",
        "type": "occasion_guidance",
        "perspective": "traditional",
        "occasion": "wedding",
        "content": """Traditional Wedding Guest Attire

Weddings have specific etiquette around guest dress.

What NOT to wear:
- White, ivory, cream (reserved for bride in Western weddings)
- Anything too revealing or attention-grabbing
- Overly casual pieces (jeans, t-shirts, sneakers)
- The same level of formality as the wedding party

Formal/Black tie:
- Floor-length gown or elegant cocktail dress
- Tuxedo or dark formal suit
- Refined jewelry, polished shoes

Semi-formal:
- Cocktail dress or dressy separates
- Suit or dress shirt with dress pants
- Sophisticated accessories

Cocktail attire:
- Knee-length or midi dress
- Blazer with dress pants or chinos
- Dressy flats or heels

Consider the venue, time of day, and cultural/religious context.""",
        "keywords": ["wedding", "guest", "formal", "etiquette", "dress-code"],
    },
    {
        "id": "occasion_wedding_cultural",
        "type": "occasion_guidance",
        "perspective": "cultural",
        "occasion": "wedding",
        "content": """Cultural Wedding Attire Considerations

Wedding dress codes vary dramatically across cultures.

Indian weddings:
- Bright, vibrant colors encouraged (except white for guests)
- Multiple events may require multiple outfits
- Traditional wear (saree, lehenga, sherwani) often preferred
- Elaborate jewelry and accessories appropriate

Chinese weddings:
- Red is auspicious; white and black may be avoided
- Traditional qipao or formal Western attire
- Gold jewelry carries positive symbolism

Jewish weddings:
- Modest dress often expected (covered shoulders, knees)
- Kippah may be provided/expected for men
- Evening ceremonies may be more formal

Muslim weddings:
- Modest dress with coverage
- Separate celebrations may have different dress codes
- Traditional cultural dress often welcomed

Always ask if uncertain about cultural expectations.""",
        "keywords": ["wedding", "cultural", "traditional", "religious", "diverse"],
    },
    # Casual/Weekend
    {
        "id": "occasion_casual_practical",
        "type": "occasion_guidance",
        "perspective": "practical",
        "occasion": "casual",
        "content": """Practical Casual/Weekend Dressing

Casual doesn't mean careless. It's about comfortable self-expression.

Elevated casual building blocks:
- Well-fitting jeans in a flattering wash
- Quality t-shirts (good fabric, proper fit)
- Versatile sneakers or casual shoes
- Layering pieces (denim jacket, cardigan, hoodie)
- Casual dresses or jumpsuits for one-piece ease

Activity considerations:
- Running errands: Prioritize comfort and ease
- Brunch with friends: Opportunity for more expression
- Outdoor activities: Function-first with style
- Casual dates: Show personality while being yourself

Practical tips:
- Quality basics look better than cheap 'statement' pieces
- Fit matters even in casual clothes
- Clean, maintained shoes elevate any casual look
- One interesting piece can make basics look intentional

Casual is where your personal style can shine most freely.""",
        "keywords": ["casual", "weekend", "relaxed", "everyday", "comfortable"],
    },
    # Date Night
    {
        "id": "occasion_date_balanced",
        "type": "occasion_guidance",
        "perspective": "body_neutral",
        "occasion": "date",
        "content": """Date Night Dressing: Confidence Over Costume

The best date outfit is one that makes you feel like your best, most
authentic self - not a performative version of yourself.

Body-neutral date approach:
- Wear what makes YOU feel confident, not what you think they want to see
- Authenticity is more attractive than performance
- Comfort matters - if you're adjusting your clothes all night, you're distracted
- Your personal style should shine, not be hidden

Practical considerations:
- Consider the activity (dinner, drinks, outdoor, active)
- Temperature and weather matter
- Ability to move, sit, eat comfortably
- Can you be yourself in this outfit?

Confidence boosters:
- Wear something you've received compliments on before
- Choose colors that make you feel good
- Ensure excellent fit and comfort
- Add one element that expresses your personality

The goal is to show up as yourself, well-presented and confident.""",
        "keywords": ["date", "confidence", "authentic", "comfortable", "self-expression"],
    },
]


# =============================================================================
# SILHOUETTE GUIDANCE - MULTI-PERSPECTIVE
# =============================================================================

SILHOUETTE_GUIDANCE = [
    {
        "id": "silhouette_fitted",
        "type": "silhouette_guidance",
        "perspective": "traditional",
        "silhouette": "fitted",
        "content": """Fitted Silhouettes: Traditional Guidance

Fitted clothes follow the body's contours.

Traditional benefits:
- Shows body shape clearly
- Often considered more polished/professional
- Creates clean, streamlined appearance
- Works well for layering under other pieces

Traditional considerations:
- Fit is critical - not too tight, not too loose
- Quality construction prevents pulling/straining
- Undergarments should be seamless
- Movement should be unimpeded

Where fitted works traditionally:
- Professional settings (tailored pieces)
- Formal occasions
- As base layers
- When showcasing quality tailoring""",
        "keywords": ["fitted", "tailored", "structured", "streamlined", "polished"],
    },
    {
        "id": "silhouette_relaxed",
        "type": "silhouette_guidance",
        "perspective": "body_neutral",
        "silhouette": "relaxed",
        "content": """Relaxed Silhouettes: Body-Neutral Perspective

Relaxed fits are equally valid as fitted ones. Choose based on preference,
not on what you think you 'should' wear.

Why relaxed silhouettes are great:
- Comfort for all-day wear
- Ease of movement
- Current and stylish, not 'frumpy'
- Body-inclusive by design
- Great for layering and styling creativity

Styling relaxed pieces:
- Balance volume (oversized top + slimmer bottom or vice versa)
- Quality fabric makes relaxed look intentional
- Proper fit in key areas (shoulders, length)
- Accessories can add polish
- Relaxed doesn't mean sloppy - fit and fabric matter

Anyone can wear relaxed silhouettes. It's a style choice, not a size limitation.""",
        "keywords": ["relaxed", "oversized", "comfortable", "body-neutral", "inclusive"],
    },
    {
        "id": "silhouette_architectural",
        "type": "silhouette_guidance",
        "perspective": "practical",
        "silhouette": "architectural",
        "content": """Architectural Silhouettes: Practical Considerations

Architectural pieces have strong structure, unusual shapes, or dramatic lines.

When architectural works:
- Making a statement is the goal
- Creative or fashion-forward environments
- Events where standing out is appropriate
- Photography-focused occasions

Practical considerations:
- Often less comfortable for all-day wear
- May require specific undergarments
- Storage and care may be more complex
- Limited versatility in styling

How to incorporate:
- One architectural piece as focal point
- Balance with simple, streamlined basics
- Consider the practical aspects of your day
- Use for occasions that warrant the statement

Architectural pieces are conversation starters - deploy strategically.""",
        "keywords": ["architectural", "statement", "dramatic", "structure", "creative"],
    },
    {
        "id": "silhouette_proportion",
        "type": "silhouette_guidance",
        "perspective": "practical",
        "silhouette": "proportion",
        "content": """Proportion Play: Practical Silhouette Guidance

Proportion is about the relationship between different parts of an outfit.

Classic proportion approaches:
- Fitted + Fitted: Streamlined, polished
- Fitted Top + Full Bottom: Balanced, classic
- Full Top + Fitted Bottom: Balanced, contemporary
- Full + Full: Dramatic, fashion-forward (hardest to pull off)

Practical proportion tips:
- One area of volume is easier to style than multiple
- Consider your daily activities and movement needs
- Proportion affects how 'dressed up' you appear
- Your comfort with volume affects confidence

Length considerations:
- Cropped + High-waisted creates clean lines
- Tucking defines waist and creates proportion
- Long layers need intentional proportion planning
- Shoe height affects how proportions read

Experiment to find YOUR preferred proportion relationships.""",
        "keywords": ["proportion", "balance", "volume", "silhouette", "styling"],
    },
]


# =============================================================================
# LEGACY KNOWLEDGE (from original fashion_knowledge.py)
# =============================================================================

LEGACY_KNOWLEDGE = [
    # Category Knowledge
    {
        "id": "category_tops",
        "type": "category_mapping",
        "content": "Tops include: shirt, blouse, top, tee, tank top, sweater, hoodie, t-shirt, camisole, tunic. These are upper body garments worn on the torso.",
        "keywords": ["tops", "shirt", "blouse", "tee", "tank", "sweater", "hoodie"],
        "category": "tops",
    },
    {
        "id": "category_bottoms",
        "type": "category_mapping",
        "content": "Bottoms include: pants, jeans, shorts, skirt, trousers, leggings. These are lower body garments worn on legs and hips.",
        "keywords": ["bottoms", "pants", "jeans", "shorts", "skirt", "trousers", "leggings"],
        "category": "bottoms",
    },
    {
        "id": "category_dresses",
        "type": "category_mapping",
        "content": "Dresses include: dress, gown, maxi dress, midi dress, mini dress, jumpsuit, romper. These are one-piece garments.",
        "keywords": ["dresses", "dress", "gown", "maxi", "midi", "mini", "jumpsuit", "romper"],
        "category": "dresses",
    },
    {
        "id": "category_outerwear",
        "type": "category_mapping",
        "content": "Outerwear includes: jacket, coat, blazer, cardigan, vest, trench coat, parka, bomber jacket. Outer layer garments.",
        "keywords": ["outerwear", "jacket", "coat", "blazer", "cardigan", "vest", "trench", "parka"],
        "category": "outerwear",
    },
    {
        "id": "category_shoes",
        "type": "category_mapping",
        "content": "Shoes include: boots, sneakers, heels, sandals, flats, loafers, oxfords, athletic shoes. Footwear for various occasions.",
        "keywords": ["shoes", "boots", "sneakers", "heels", "sandals", "flats", "loafers", "oxfords"],
        "category": "shoes",
    },
    {
        "id": "category_accessories",
        "type": "category_mapping",
        "content": "Accessories include: bag, purse, wallet, belt, scarf, hat, jewelry, watch. Items that complement outfits.",
        "keywords": ["accessories", "bag", "purse", "belt", "scarf", "hat", "jewelry", "watch"],
        "category": "accessories",
    },
    # Style Modifiers
    {
        "id": "style_casual",
        "type": "style_modifier",
        "content": "Casual style: relaxed, comfortable, everyday, laid-back clothing. Think jeans, t-shirts, sneakers for informal occasions.",
        "keywords": ["casual", "relaxed", "comfortable", "everyday", "laid-back"],
        "style": "casual",
    },
    {
        "id": "style_formal",
        "type": "style_modifier",
        "content": "Formal style: business, professional, elegant, sophisticated clothing. Suits, blazers, dress pants for work or formal events.",
        "keywords": ["formal", "business", "professional", "elegant", "sophisticated"],
        "style": "formal",
    },
    {
        "id": "style_minimalist",
        "type": "style_modifier",
        "content": "Minimalist style: simple, clean, basic, understated clothing. Neutral colors, simple lines, quality basics.",
        "keywords": ["minimalist", "minimal", "simple", "clean", "basic", "understated"],
        "style": "minimalist",
    },
    {
        "id": "style_bohemian",
        "type": "style_modifier",
        "content": "Bohemian style: boho, flowing, artistic, free-spirited clothing. Earthy tones, layered jewelry, unconventional pieces.",
        "keywords": ["bohemian", "boho", "flowing", "artistic", "free-spirited"],
        "style": "bohemian",
    },
    {
        "id": "style_edgy",
        "type": "style_modifier",
        "content": "Edgy style: punk, rock, alternative, bold clothing. Leather, dark colors, statement pieces, unconventional choices.",
        "keywords": ["edgy", "punk", "rock", "alternative", "bold"],
        "style": "edgy",
    },
    # Material Knowledge
    {
        "id": "material_natural",
        "type": "material_knowledge",
        "content": """Natural fabrics: Cotton is breathable for everyday wear. Linen is lightweight for summer. Wool is warm for
cold weather. Silk is luxurious for formal occasions. Cashmere is soft and premium.""",
        "keywords": ["cotton", "linen", "wool", "silk", "cashmere", "natural", "fabric"],
    },
    {
        "id": "material_synthetic",
        "type": "material_knowledge",
        "content": """Synthetic and blended fabrics: Polyester is durable and wrinkle-resistant. Nylon is strong for activewear.
Spandex/elastane adds stretch. Rayon drapes well. Performance fabrics wick moisture.""",
        "keywords": ["polyester", "nylon", "spandex", "elastane", "rayon", "synthetic", "performance"],
    },
]


# =============================================================================
# COMBINED KNOWLEDGE BASE
# =============================================================================

FASHION_KNOWLEDGE_V3: List[Dict[str, Any]] = (
    CURATION_PRINCIPLES
    + BODY_TYPE_GUIDANCE
    + COLOR_THEORY
    + OCCASION_GUIDANCE
    + SILHOUETTE_GUIDANCE
    + LEGACY_KNOWLEDGE
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_knowledge_by_type(knowledge_type: str) -> List[Dict[str, Any]]:
    """
    Get all knowledge entries of a specific type.

    Args:
        knowledge_type: Type like 'curation_principle', 'body_type_guidance', etc.

    Returns:
        List of matching knowledge entries
    """
    return [k for k in FASHION_KNOWLEDGE_V3 if k.get("type") == knowledge_type]


def get_knowledge_by_perspective(perspective: str) -> List[Dict[str, Any]]:
    """
    Get all knowledge entries from a specific perspective.

    Args:
        perspective: 'traditional', 'body_neutral', 'cultural', or 'practical'

    Returns:
        List of matching knowledge entries
    """
    return [k for k in FASHION_KNOWLEDGE_V3 if k.get("perspective") == perspective]


def get_all_knowledge_texts() -> List[str]:
    """
    Get all knowledge content as a list of strings for embedding.

    Returns:
        List of content strings
    """
    return [k["content"] for k in FASHION_KNOWLEDGE_V3 if "content" in k]


def get_knowledge_for_body_type(body_type: str) -> List[Dict[str, Any]]:
    """
    Get guidance for a specific body type across all perspectives.

    Args:
        body_type: 'hourglass', 'rectangle', 'pear', 'apple', 'all'

    Returns:
        List of matching guidance entries
    """
    return [
        k
        for k in BODY_TYPE_GUIDANCE
        if k.get("body_type") == body_type or k.get("body_type") == "all"
    ]


def get_knowledge_for_occasion(occasion: str) -> List[Dict[str, Any]]:
    """
    Get guidance for a specific occasion across all perspectives.

    Args:
        occasion: 'professional', 'wedding', 'casual', 'date', etc.

    Returns:
        List of matching guidance entries
    """
    return [k for k in OCCASION_GUIDANCE if k.get("occasion") == occasion]


def search_knowledge_by_keywords(keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Find knowledge entries matching any of the given keywords.

    Args:
        keywords: List of keywords to search for

    Returns:
        List of matching knowledge entries
    """
    keywords_lower = [k.lower() for k in keywords]
    results = []

    for entry in FASHION_KNOWLEDGE_V3:
        entry_keywords = entry.get("keywords", [])
        if any(k.lower() in keywords_lower for k in entry_keywords):
            results.append(entry)

    return results
