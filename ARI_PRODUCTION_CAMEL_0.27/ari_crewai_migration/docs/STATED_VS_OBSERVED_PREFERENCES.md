# Stated vs Observed Preferences Architecture

## Concept: Dual Preference Tracking

### Problem
Users may:
- Not want to answer personal questions directly
- State preferences that differ from actual behavior
- Evolve their preferences over time
- Not be self-aware of their true preferences

### Solution: Track Both

**Stated Preference (Self-Reported)**
- What users tell us during onboarding
- Optional, non-invasive questions
- Can be updated by user anytime

**Observed Preference (Revealed)**
- What we infer from actual behavior
- Product views, saves, purchases
- Search patterns, filter usage
- Continuously updated

---

## Expression Spectrum Example

### Stated Expression Spectrum (Onboarding)

**Discrete Question (Non-Invasive):**
```
"How would you describe your style aesthetic?"

[Slider 1-10]
Structured & Tailored ←→ Fluid & Balanced ←→ Soft & Flowing

Help text: "We'll refine this understanding as we learn your preferences"
Allow skip: "I'd rather show you through my choices"
```

**Why This Works:**
- No explicit "masculine/feminine" labels
- Uses neutral style descriptors
- Optional (skippable)
- Framed as collaborative learning

### Observed Expression Spectrum (Behavioral)

**What We Track:**
```python
# Calculate from user behavior
observed_spectrum = calculate_from_behavior(
    products_viewed,
    products_saved,
    products_purchased,
    search_patterns,
    filter_usage
)

# Signals:
- Tailored blazers, structured pieces → Lower score (1-4)
- Flowing dresses, soft fabrics → Higher score (7-10)
- Mix of both → Middle score (4-7)
```

**Update Frequency:**
- After every 10 interactions
- Weekly recalculation
- Weighted by recency (newer actions matter more)

---

## Neo4j Schema Updates

### GenderExpression Node (Enhanced)

```cypher
(:GenderExpression {
  id: "user_123_expression",

  // STATED (from onboarding)
  stated_expression_spectrum: 5,  // What user told us (1-10)
  stated_at: datetime(),           // When they stated it
  stated_confidence: "low",        // Did they hesitate? Skip?
  allow_tracking: true,            // Consent to track observed

  // OBSERVED (from behavior)
  observed_expression_spectrum: 6.2,  // What we've learned (1-10)
  observed_confidence: 0.78,          // How certain we are (0-1)
  last_calculated: datetime(),        // When we last updated
  calculation_basis: "87 interactions", // How much data

  // VARIANCE
  preference_drift: 1.2,           // |stated - observed|
  drift_direction: "higher",       // "higher", "lower", "stable"
  evolution_trend: "exploring",    // "stable", "exploring", "shifting"

  // METADATA
  manual_override: false,          // User manually corrected us
  created_at: datetime(),
  updated_at: datetime()
})
```

### Tracking Relationship

```cypher
// Track individual observations
(User)-[:OBSERVED_BEHAVIOR {
  interaction_type: "viewed_product",
  product_id: "prod_123",
  product_category: "blazers",
  expression_signal: 3.2,  // This action signals 3.2 on spectrum
  timestamp: datetime(),
  weight: 1.0  // Decays over time
}]->(Product)
```

---

## Behavioral Signals Mapping

### Products → Expression Spectrum Mapping

**Items that signal "Structured/Tailored" (1-4):**
- Blazers, suits, structured jackets
- Button-up shirts, oxford shirts
- Tailored trousers, chinos
- Oxfords, loafers (shoes)
- Minimalist accessories
- Monochrome colors

**Items that signal "Fluid/Balanced" (4-7):**
- Unisex pieces
- Oversized fits
- Androgynous styles
- Mixed materials
- Neutral palettes

**Items that signal "Soft/Flowing" (7-10):**
- Flowing dresses, skirts
- Soft fabrics (silk, chiffon)
- Romantic details (ruffles, lace)
- Pastels, florals
- Delicate accessories
- Heels, strappy sandals

### Search Patterns

```python
# Extract signals from queries
queries_analyzed = [
    "tailored blazer" → signal: 2.5,
    "flowy summer dress" → signal: 8.7,
    "androgynous outfit" → signal: 5.0,
    "structured vs flowing" → signal: ambiguous (track both)
]
```

### Filter Usage

```python
# Track filter preferences
if user_frequently_filters_by("fit: tailored"):
    signal = 2.0
elif user_frequently_filters_by("fit: flowing"):
    signal: 8.5
elif user_uses_both:
    signal = 5.0  # Fluid preference
```

---

## Calculation Algorithm

### Weighted Average of Observations

```python
def calculate_observed_spectrum(user_id: str) -> float:
    """
    Calculate observed expression spectrum from user behavior.
    Returns score 1-10.
    """

    # Get all behavioral signals (last 90 days)
    interactions = get_user_interactions(user_id, days=90)

    # Weight by recency (exponential decay)
    weighted_signals = []
    for interaction in interactions:
        age_days = (now - interaction.timestamp).days
        weight = math.exp(-age_days / 30)  # 30-day half-life

        signal = get_product_expression_signal(interaction.product_id)
        weighted_signals.append(signal * weight)

    # Calculate weighted average
    if not weighted_signals:
        return None  # Not enough data

    observed = sum(weighted_signals) / len(weighted_signals)

    # Clamp to 1-10 range
    return max(1, min(10, observed))


def get_product_expression_signal(product_id: str) -> float:
    """
    Determine where a product falls on expression spectrum.
    Based on category, attributes, styling.
    """

    product = get_product(product_id)

    signals = []

    # Category signals
    if product.category in ["blazers", "suits", "dress-shirts"]:
        signals.append(2.5)
    elif product.category in ["dresses", "skirts", "flowing-tops"]:
        signals.append(8.0)
    elif product.category in ["jeans", "t-shirts", "sneakers"]:
        signals.append(5.0)  # Neutral

    # Attribute signals
    if "tailored" in product.attributes:
        signals.append(2.0)
    if "flowing" in product.attributes or "soft" in product.attributes:
        signals.append(8.5)
    if "androgynous" in product.attributes or "unisex" in product.attributes:
        signals.append(5.0)

    # Fabric signals
    if product.fabric in ["wool", "cotton-poplin", "structured"]:
        signals.append(3.0)
    elif product.fabric in ["silk", "chiffon", "lace"]:
        signals.append(8.0)

    # Color signals (subtle)
    if product.color in ["black", "navy", "charcoal"]:
        signals.append(4.0)  # Slightly structured
    elif product.color in ["pastels", "floral-print"]:
        signals.append(7.0)  # Slightly soft

    # Average all signals
    return sum(signals) / len(signals) if signals else 5.0
```

### Confidence Score

```python
def calculate_confidence(interactions_count: int, variance: float) -> float:
    """
    How confident are we in our observed preference?

    High confidence when:
    - Many interactions (>50)
    - Low variance (consistent behavior)
    - Recent data
    """

    # Confidence from sample size
    sample_confidence = min(1.0, interactions_count / 100)

    # Confidence from consistency (inverse of variance)
    consistency_confidence = 1.0 / (1.0 + variance)

    # Combined confidence (geometric mean)
    confidence = math.sqrt(sample_confidence * consistency_confidence)

    return confidence
```

---

## When to Use Stated vs Observed

### Use Stated Preference:
-  First recommendations (no behavioral data yet)
-  User explicitly wants to change style
-  Respecting user's self-identification
-  Low confidence in observed data (<0.5)

### Use Observed Preference:
-  After 20+ interactions
-  High confidence (>0.7)
-  Stated preference conflicts with behavior
-  User gave ambiguous or skipped stated preference

### Use Blended Approach:
```python
def get_effective_expression_spectrum(user_id: str) -> float:
    """
    Blend stated and observed preferences intelligently.
    """

    stated = user.stated_expression_spectrum
    observed = user.observed_expression_spectrum
    obs_confidence = user.observed_confidence

    # If no observed data yet, use stated
    if observed is None:
        return stated if stated else 5.0  # Default to center

    # If user skipped stating preference, use observed
    if stated is None:
        return observed

    # Blend based on confidence and drift
    drift = abs(stated - observed)

    # High confidence + high drift = trust observed more
    if obs_confidence > 0.7 and drift > 2.0:
        # User's behavior suggests different preference
        weight_observed = 0.7
        weight_stated = 0.3

    # Low confidence = trust stated more
    elif obs_confidence < 0.5:
        weight_observed = 0.3
        weight_stated = 0.7

    # Balanced
    else:
        weight_observed = 0.5
        weight_stated = 0.5

    blended = (stated * weight_stated) + (observed * weight_observed)

    return blended
```

---

## User Transparency & Control

### Show Users the Difference

**In User Profile Dashboard:**
```
Your Style Profile

Expression Spectrum:
  What you told us: "Fluid & Balanced" (5/10) 
  What we've learned: "Soft & Flowing" (7.2/10) 

  Notice a difference? Your choices lean more toward flowing styles.
  [Use my stated preference] [Trust what you've learned] [Update my stated preference]
```

### Let Users Override

```cypher
// User manually adjusts
MATCH (u:User)-[:HAS_EXPRESSION_PROFILE]->(ge:GenderExpression)
SET ge.stated_expression_spectrum = $new_value,
    ge.manual_override = true,
    ge.override_reason = "User manually adjusted",
    ge.override_at = datetime()

// Reset to observed
SET ge.manual_override = false,
    ge.use_observed = true
```

---

## Privacy & Ethics

### Consent

**During Onboarding:**
```
"As you use ARI, we'll learn from your choices to improve recommendations.
This includes understanding style preferences you might not articulate directly.

[x] Allow ARI to learn from my behavior
[ ] Only use what I explicitly tell you

You can change this anytime in settings."
```

### Transparency

- Show users what we've learned
- Explain why recommendations were made
- Allow users to correct our inferences
- Never share observed preferences externally

### Data Minimization

- Only track necessary signals
- Aggregate older data (>90 days)
- Delete on user request
- No cross-user behavioral sharing without consent

---

## Implementation Checklist

### JSON Config Updates
- [x] Make expression_spectrum optional
- [x] Add discrete language ("Structured" vs "Soft")
- [x] Add skip option
- [x] Add help text about behavioral learning

### Neo4j Schema Updates
- [ ] Add `stated_expression_spectrum` field
- [ ] Add `observed_expression_spectrum` field
- [ ] Add `observed_confidence` field
- [ ] Add variance tracking fields
- [ ] Create (:BehavioralSignal) nodes for tracking

### Service Layer
- [ ] Implement `calculate_observed_spectrum()`
- [ ] Implement `get_effective_expression_spectrum()`
- [ ] Background job to recalculate weekly
- [ ] Drift detection alerts

### Product Mapping
- [ ] Map all products to expression signals
- [ ] Create category → signal lookup table
- [ ] Tag products with expression indicators

### User Interface
- [ ] Show stated vs observed in profile
- [ ] Allow manual override
- [ ] Explain recommendations with reasoning
- [ ] Consent management

---

## Example User Journey

**Day 1: Onboarding**
```
User selects: "Structured & Tailored" (3/10)
Stated: 3
Observed: null
Effective: 3 (using stated)
```

**Week 2: After 20 interactions**
```
User viewed/saved mostly:
- Flowing dresses (signal: 8.0)
- Soft blouses (signal: 7.5)
- Minimal blazers (signal: 6.0)

Calculated observed: 7.2
Confidence: 0.65
Drift: 4.2 (high)

Effective: 5.4 (blended 30% stated + 70% observed)
```

**Month 2: High confidence**
```
User continues choosing soft styles
Observed: 7.5
Confidence: 0.85
Drift: 4.5

System notifies user:
"We've noticed your style leans more toward flowing pieces
than your initial preference. Would you like to update your profile?"

User: "Yes, update to 7.5" → Stated now matches observed
```

---

## Benefits

1. **Less Invasive Onboarding** - Users can skip sensitive questions
2. **More Accurate** - Revealed preference > stated preference
3. **Adaptive** - Evolves with user's changing taste
4. **Transparent** - Users see what we've learned
5. **Respectful** - Users maintain control

This is state-of-the-art personalization!
