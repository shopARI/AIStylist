# ARI V3 Demo Users

Three preset demo users with complete onboarding profiles for testing the recommendation system.

---

## Demo User 1: Emma (Creative Professional)

**ID:** `demo_emma_creative`
**Description:** Creative professional, loves bold colors and unique pieces

### Personal
| Field | Value |
|-------|-------|
| Root Value | self-expression |
| Validation Source | self |
| Style Goal | stand out authentically |

**Occasions:**
- Work (formality: 0.6, context: creative_professional)
- Gallery openings (formality: 0.7, context: artistic)
- Weekend brunch (formality: 0.3, context: casual)

### Taste
| Field | Value |
|-------|-------|
| Style Words | bold, artistic, eclectic, colorful |
| Avoids | basic, corporate, beige |
| Color Preferences | emerald, cobalt, coral, mustard |
| Pattern Comfort | 0.8 (high) |
| Adventurousness | 8/10 |

### Process
| Field | Value |
|-------|-------|
| Decision Speed | deliberate |
| Research Depth | deep |
| Brand Loyalty | 4/10 |
| Trend Following | 5/10 |

### Practicality
| Field | Value |
|-------|-------|
| Monthly Budget | $600 |
| Budget Flexibility | 30% |
| Care Tolerance | medium |
| Versatility Priority | 0.6 |

### Body
| Field | Value |
|-------|-------|
| Height | 5'7" |
| Body Type | hourglass |
| Favorite Features | waist, legs |
| Fit Preferences | fitted waist, midi length |

### External
| Field | Value |
|-------|-------|
| Pinterest | connected |
| Instagram Aesthetic | artistic |

---

## Demo User 2: Marcus (Finance Professional)

**ID:** `demo_marcus_classic`
**Description:** Finance professional, prefers timeless quality pieces

### Personal
| Field | Value |
|-------|-------|
| Root Value | competence |
| Validation Source | peers |
| Style Goal | look polished and trustworthy |

**Occasions:**
- Client meetings (formality: 0.85, context: business_formal)
- Office (formality: 0.7, context: business_casual)
- Golf weekends (formality: 0.3, context: smart_casual)

### Taste
| Field | Value |
|-------|-------|
| Style Words | classic, refined, quality, timeless |
| Avoids | trendy, flashy, loud patterns |
| Color Preferences | navy, charcoal, burgundy, white |
| Pattern Comfort | 0.3 (low) |
| Adventurousness | 3/10 |

### Process
| Field | Value |
|-------|-------|
| Decision Speed | quick |
| Research Depth | moderate |
| Brand Loyalty | 8/10 |
| Trend Following | 2/10 |

### Practicality
| Field | Value |
|-------|-------|
| Monthly Budget | $1,200 |
| Budget Flexibility | 50% |
| Care Tolerance | high |
| Versatility Priority | 0.8 |

### Body
| Field | Value |
|-------|-------|
| Height | 6'1" |
| Body Type | athletic |
| Favorite Features | shoulders, build |
| Fit Preferences | tailored, slim fit |

### External
| Field | Value |
|-------|-------|
| Pinterest | not connected |
| Instagram Aesthetic | none |

---

## Demo User 3: Sophia (Tech Founder)

**ID:** `demo_sophia_minimal`
**Description:** Tech founder, loves minimalist Scandinavian style

### Personal
| Field | Value |
|-------|-------|
| Root Value | authenticity |
| Validation Source | self |
| Style Goal | effortless and intentional |

**Occasions:**
- Investor pitches (formality: 0.6, context: startup_professional)
- Team meetings (formality: 0.4, context: casual_professional)
- Travel (formality: 0.3, context: comfortable)

### Taste
| Field | Value |
|-------|-------|
| Style Words | minimal, clean, Scandinavian, architectural |
| Avoids | fussy, decorative, bright colors |
| Color Preferences | black, white, grey, camel |
| Pattern Comfort | 0.2 (very low) |
| Adventurousness | 5/10 |

### Process
| Field | Value |
|-------|-------|
| Decision Speed | quick |
| Research Depth | deep |
| Brand Loyalty | 7/10 |
| Trend Following | 4/10 |

### Practicality
| Field | Value |
|-------|-------|
| Monthly Budget | $800 |
| Budget Flexibility | 40% |
| Care Tolerance | low (easy care only) |
| Versatility Priority | 0.9 (very high) |

### Body
| Field | Value |
|-------|-------|
| Height | 5'9" |
| Body Type | tall_slim |
| Favorite Features | height, posture |
| Fit Preferences | relaxed, oversized, clean lines |

### External
| Field | Value |
|-------|-------|
| Pinterest | connected |
| Instagram Aesthetic | minimalist |

---

## Usage

These demo users are defined in `ari_v3/demo_cli.py` and can be used by running:

```bash
cd /home/ubuntu/AIStylist/ARI_PRODUCTION_RESEARCH
source venv/bin/activate
python ari_v3/demo_cli.py
```

Select option 1 "Use demo user" and choose Emma, Marcus, or Sophia.

## Data Structure

Each demo user profile maps to the ARI V3 OnboardingProfile structure:

```
OnboardingProfile
├── personal (PersonalNode)
│   ├── root_value
│   ├── validation_source
│   ├── style_goal
│   └── occasions[]
├── taste (TasteNode)
│   ├── style_words[]
│   ├── style_avoids[]
│   ├── color_preferences[]
│   ├── pattern_comfort
│   └── adventurousness
├── process (ProcessNode)
│   ├── decision_speed
│   ├── research_depth
│   ├── brand_loyalty
│   └── trend_following
├── practicality (PracticalityNode)
│   ├── budget_monthly
│   ├── budget_flexibility
│   ├── care_tolerance
│   └── versatility_priority
├── body (BodyNode)
│   ├── height
│   ├── body_type
│   ├── favorite_features[]
│   └── fit_preferences[]
└── external (ExternalNode)
    ├── pinterest_connected
    └── instagram_aesthetic
```
