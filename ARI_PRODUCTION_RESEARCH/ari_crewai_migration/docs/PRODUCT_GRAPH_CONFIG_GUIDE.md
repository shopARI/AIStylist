# Product Graph Configuration Guide

## Overview

The `product_graph_config.json` is a comprehensive configuration file that defines the entire product graph schema, expression spectrum mapping, and metadata enrichment rules.

**Location:** `/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration/config/product_graph_config.json`

---

## What's Included

### 1. Neo4j Schema Definition

**6 Node Types:**
- `Product` (4.6M+ nodes) - Core product data
- `Brand` - Fashion brands with tier/sustainability info
- `Category` - Hierarchical product categories
- `Color` - Color nodes with hex codes and formality
- `Occasion` - Events/contexts for wearing products
- `Style` - Style tags and aesthetics

**7 Relationship Types:**
- `BELONGS_TO_CATEGORY` - Product → Category
- `MADE_BY` - Product → Brand
- `HAS_COLOR` - Product → Color
- `SUITABLE_FOR` - Product → Occasion
- `HAS_STYLE` - Product → Style
- `SIMILAR_TO` - Product → Product (visual/collaborative similarity)
- `PARENT_CATEGORY` - Category → Category (hierarchy)

### 2. Expression Spectrum Mapping

**The Key Innovation:** Every product gets an `expression_spectrum_signal` (1-10) that indicates where it falls on the style spectrum.

**Formula:**
```
signal = base_signal (category) +
         fabric_modifier +
         fit_modifier +
         color_modifier +
         sum(detail_modifiers)

Clamped to: 1.0 - 10.0
```

**Example Calculation:**
```json
{
  "product": "Silk midi dress with ruffles in pastel pink",
  "base": "dresses = 8.0",
  "fabric": "silk = +2.0",
  "fit": "flowing = +2.0",
  "color": "pastels = +1.5",
  "details": "ruffles = +2.5",
  "total": "16.0 (clamped to 10.0)"
}
```

**Categories Mapped:**
- `blazers` → 2.5 (structured)
- `suits` → 2.0 (very structured)
- `jeans` → 5.0 (neutral)
- `dresses` → 8.0 (soft)
- `maxi-dresses` → 8.5 (very soft)

**Fabric Modifiers:**
- `wool` → -1.0 (more structured)
- `silk` → +2.0 (softer)
- `chiffon` → +2.5 (very soft)

**Fit Modifiers:**
- `tailored` → -2.0 (very structured)
- `fitted` → -1.0 (structured)
- `flowing` → +2.0 (very soft)

**Color Modifiers:**
- `black`, `navy` → -0.5 (formal/structured)
- `pastels` → +1.5 (soft)
- `florals` → +2.0 (very soft)

**Detail Modifiers:**
- `ruffles` → +2.5 (very feminine)
- `lace-trim` → +2.0 (delicate)
- `structured-shoulders` → -1.5 (tailored)

### 3. Category Hierarchy

Complete taxonomy of all product categories with parent-child relationships:

```json
{
  "clothing": {
    "tops": {
      "shirts": ["t-shirts", "button-ups", "dress-shirts"],
      "blouses": ["casual-blouses", "formal-blouses"],
      "sweaters": ["cardigans", "pullovers"]
    },
    "dresses": {
      "casual": ["sundresses", "wrap-dresses"],
      "formal": ["cocktail-dresses", "evening-gowns"]
    }
  }
}
```

### 4. Brand Tiers

Categorizes brands by price point:

- **Luxury:** $500+ (Gucci, Prada, Saint Laurent)
- **Premium:** $200-$500 (Theory, Vince, Rag & Bone)
- **Mid-range:** $50-$200 (Everlane, COS, Madewell)
- **Fast-fashion:** $20-$50 (Zara, H&M, Mango)
- **Budget:** <$20 (Target, Old Navy)

### 5. Metadata Enrichment Rules

**Auto-tagging:**
```json
{
  "condition": "price > 500",
  "add_tags": ["luxury", "investment-piece"]
}
```

**Expression spectrum auto-calculate:**
- Runs on product create/update
- Uses formula from mapping section
- Fallback: 5.0 if unable to calculate

**Occasion auto-suggest:**
```json
{
  "category": "suits",
  "occasions": ["work", "business-formal", "interviews"]
}
```

### 6. Integration with User Graph

**How Products Match Users:**

```python
# Recommendation pipeline (from config)
1. Filter by user budget
   → Use user.budget_profile.monthly_budget_max

2. Filter by occasions
   → Match user.lifestyle_context.social_occasions

3. Match expression spectrum
   → Find products where:
     product.expression_spectrum_signal
     ≈ user.effective_expression_spectrum (±2.0)

4. Boost loved brands
   → Increase score for brands in user.values_profile

5. Rank by combined score
   → visual_similarity (30%) +
     style_similarity (30%) +
     collaborative_filtering (20%) +
     user_preference_match (20%)
```

---

## Use Cases

### Use Case 1: Auto-Calculate Expression Spectrum for New Product

**When adding a new product:**
```python
product = {
    "title": "Tailored Navy Blazer",
    "category": "blazers",
    "fabric": "wool",
    "fit": "tailored",
    "color": "navy"
}

# System automatically calculates:
signal = 2.5 (blazer) + (-1.0 wool) + (-2.0 tailored) + (-0.5 navy)
       = -1.0 (clamped to 1.0)

# Product gets: expression_spectrum_signal = 1.0
# → Very structured/masculine end of spectrum
```

### Use Case 2: Match Products to User Profile

**User profile:**
```json
{
  "stated_expression_spectrum": 3.0,  // User said "structured"
  "observed_expression_spectrum": 5.5, // But buys more balanced
  "effective_expression_spectrum": 4.5  // Blended
}
```

**Query products:**
```cypher
// Find products matching user's effective spectrum (±2.0 tolerance)
MATCH (p:Product)
WHERE p.expression_spectrum_signal >= 2.5  // 4.5 - 2.0
  AND p.expression_spectrum_signal <= 6.5  // 4.5 + 2.0
RETURN p
ORDER BY abs(p.expression_spectrum_signal - 4.5) ASC
```

### Use Case 3: Product Team Adds New Category

**Edit JSON (no code changes needed):**
```json
{
  "categories": {
    "jumpsuits": {
      "base_signal": 6.5,
      "description": "One-piece alternatives to dresses"
    }
  }
}
```

System automatically:
- Creates Category node in Neo4j
- Calculates expression spectrum for all jumpsuit products
- Makes them discoverable in search

### Use Case 4: Update Brand Tier

**Product team reclassifies brand:**
```json
{
  "brand_tiers": {
    "premium": {
      "examples": ["Theory", "Vince", "Everlane"]  // Moved Everlane up
    }
  }
}
```

Affects:
- Pricing recommendations
- User budget matching
- Brand loyalty scoring

---

## Product Properties Explained

### Core Properties (Required)
```json
{
  "id": "uuid",                    // Unique identifier
  "title": "Product name",         // Display name
  "price": 129.99,                 // Price in USD
  "category": "dresses",           // Main category
  "images": ["url1.jpg"]           // At least 1 image
}
```

### Enrichment Properties (Optional but Recommended)
```json
{
  "brand": "Everlane",
  "description": "Sustainable midi dress...",
  "subcategory": "midi-dress",
  "colors": ["black", "navy"],
  "sizes": ["XS", "S", "M", "L"],
  "fabric": "silk",
  "fit": "flowing",
  "tags": ["sustainable", "work", "casual"]
}
```

### Computed Properties (Auto-generated)
```json
{
  "expression_spectrum_signal": 8.2,  // Auto-calculated
  "popularity_score": 0.87,           // From user interactions
  "completeness_score": 85            // Data quality %
}
```

---

## Data Quality Scoring

**Completeness Score (0-100):**
```
has_description: 10 points
has_brand: 15 points
has_colors: 10 points
has_sizes: 10 points
has_fabric: 5 points
has_fit: 5 points
has_tags: 15 points
has_multiple_images: 10 points
has_expression_signal: 10 points
has_occasion_links: 10 points

Total: 100 points
```

**Minimum for display:** 40 points (required fields + 1 enrichment)

---

## Search & Filtering

### Text Search (Boost Weights)
```
title: 2.0× boost
brand: 1.5× boost
tags: 1.0× boost
description: 0.5× boost
```

### Price Range Filters
```
Under $50
$50-$100
$100-$200
$200-$500
$500+
```

### Expression Spectrum Filters
```
Structured & Tailored (1-3.5)
Balanced & Versatile (3.5-6.5)
Soft & Flowing (6.5-10)
```

---

## Extending the Configuration

### Add New Fabric Type
```json
{
  "fabrics": {
    "cashmere": {
      "signal_modifier": 1.2,
      "description": "Soft luxurious"
    }
  }
}
```

### Add New Occasion
```json
{
  "tree": {
    "occasions": {
      "micro-wedding": {
        "formality_level": "business-casual",
        "season": ["spring", "summer", "fall"],
        "time_of_day": "day"
      }
    }
  }
}
```

### Add New Auto-Tag Rule
```json
{
  "auto_tagging": {
    "rules": [
      {
        "condition": "sustainability_score > 7",
        "add_tags": ["eco-friendly", "conscious"]
      }
    ]
  }
}
```

---

## Validation

**The config includes validation rules:**

```json
{
  "validation_rules": [
    {
      "field": "price",
      "rule": "price > 0 AND price < 100000",
      "error": "Price must be between $0 and $100,000"
    },
    {
      "field": "expression_spectrum_signal",
      "rule": "signal >= 1.0 AND signal <= 10.0",
      "error": "Expression spectrum signal must be 1-10"
    }
  ]
}
```

---

## Migration from Current Schema

### Current State (Python-based)
```python
# models/product_models.py
class Product(BaseModel):
    id: str
    title: str
    price: float
    category: str
    # ... hardcoded in Python
```

### Future State (JSON-driven)
```python
# Load schema from JSON
config = load_json("product_graph_config.json")

# Dynamically create Pydantic model
Product = create_model_from_schema(config["schema"]["nodes"]["Product"])

# Auto-calculate expression spectrum
product.expression_spectrum_signal = calculate_signal(
    product,
    config["expression_spectrum_mapping"]
)
```

**Benefits:**
- Product team can modify without engineering
- A/B test different category signals
- Easy to add new attributes
- Consistent with user onboarding JSON approach

---

## Next Steps

1. **Validate mapping accuracy** - Test expression spectrum calculations on sample products
2. **Enrich existing products** - Run batch job to add expression_spectrum_signal to 4.6M products
3. **Build admin UI** - Allow Product team to edit JSON via interface
4. **Implement auto-enrichment** - Apply metadata rules to new products
5. **Connect to user graph** - Use in recommendation pipeline

---

## Files

**IMPORTANT - Two Product Graph Configs:**

1. **AS-IS Schema (Current State):**
   - `/ari_crewai_migration/config/product_graph_schema_current.json`
   - Documents what EXISTS NOW in Neo4j (6.4M products)
   - Shows actual properties, node counts, relationship counts
   - Highlights data quality issues (NULL tags, missing colors/styles)
   - Use this to understand current database state

2. **Future State Config (What We Want):**
   - `/ari_crewai_migration/config/product_graph_config.json`
   - Documents PLANNED features (expression spectrum mapping, auto-enrichment)
   - Shows desired schema improvements
   - Use this as roadmap for enhancements

**Related:**
- `/ari_crewai_migration/config/onboarding_config.json` (user graph)
- `/ari_crewai_migration/models/product_models.py` (Pydantic models)
- `/database_diagnostic_report.md` (detailed database analysis)

**Documentation:**
- This file: `docs/PRODUCT_GRAPH_CONFIG_GUIDE.md`
- User graph: `docs/STATED_VS_OBSERVED_PREFERENCES.md`
- Social influence: `SOCIAL_INFLUENCE_GRAPH.md`
