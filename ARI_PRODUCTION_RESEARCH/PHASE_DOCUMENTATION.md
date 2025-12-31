# Graph Database Enhancement - Phase Implementation Guide

## Overview

This guide covers the implementation phases for enhancing a Neo4j graph database with AI-extracted metadata and fashion ontology relationships. The phases transform raw product data into a structured knowledge graph with intelligent attributes and semantic relationships.

---

## PHASE 1: Advanced LLM-Based Data Extraction

### Purpose
Extract comprehensive fashion attributes using GPT-4o with structured outputs for maximum accuracy and intelligence.

### Implementation
File: `llm_mass_extract.py`

### AI Model Configuration
```python
# Latest OpenAI model with structured outputs
MODEL = "gpt-4o-2024-08-06"
BATCH_SIZE = 50  # Optimized for API rate limits
REQUESTS_PER_MINUTE = 100  # Adjust based on OpenAI tier
```

### Structured Data Models
```python
class ColorExtraction(BaseModel):
    primary_colors: List[str] = Field(max_items=3)
    color_descriptions: List[str] = Field(max_items=2)
    color_confidence: float = Field(description="0-1 confidence score")

class StyleExtraction(BaseModel):
    fashion_styles: List[str] = Field(max_items=3)
    occasions: List[str] = Field(max_items=3)
    target_demographic: str
    formality_level: str

class BrandExtraction(BaseModel):
    brand_name: str
    brand_confidence: float
    brand_tier: str  # luxury, premium, mid-range, budget
```

### Intelligent Extraction Capabilities
- **Contextual Color Understanding**: "midnight blue" → ['blue'], "rose gold" → ['rose', 'gold']
- **Advanced Brand Recognition**: "Police Spl581-52sg1x" → Police (95% confidence)
- **Material Intelligence**: "breathable mesh fabric" → ['mesh']
- **Style Classification**: Fashion domain knowledge for style categorization
- **Seasonal Analysis**: Context-aware seasonal appropriateness
- **Target Demographics**: Intelligent audience identification
- **Price Perception**: Brand-based pricing tier analysis

### Properties Added to Products
```cypher
# Core extracted attributes
p.extracted_colors = ['navy', 'gold']
p.color_confidence = 0.95
p.extracted_styles = ['elegant', 'formal']
p.extracted_brand = 'Zara'
p.brand_confidence = 1.0
p.brand_tier = 'mid-range'

# Advanced attributes
p.materials = ['chiffon', 'polyester']
p.target_demographic = 'women'
p.occasions = ['wedding', 'formal dinner']
p.season = 'spring'
p.formality_level = 'formal'
p.ai_category = 'dress'
p.key_features = ['floral print', 'midi length']
p.extraction_model = 'gpt-4o-2024-08-06'
```

### Execution
```bash
python llm_mass_extract.py
```

### Cost Estimation
- Approximately $0.015 per product with GPT-4o
- 4.6M products = ~$69,000 for complete extraction
- Processing time: Several hours with rate limiting

---

## PHASE 3: Fashion Ontology & Knowledge Graph Enhancement

### Purpose
Create semantic relationships between fashion attributes and establish domain knowledge.

### Implementation
File: `phase3_ontology.py`

### Ontology Structure
```cypher
# Color Complement Relationships
CREATE (red:Color {name: 'red'})
CREATE (blue:Color {name: 'blue'})
CREATE (red)-[:COMPLEMENTS]->(blue)

# Style Compatibility Relationships  
CREATE (casual:Style {name: 'casual'})
CREATE (business:Style {name: 'business'})
CREATE (casual)-[:COMPATIBLE_WITH]->(business)

# Occasion Nodes
CREATE (wedding:Occasion {name: 'wedding', formality: 'formal'})
CREATE (casual_wear:Occasion {name: 'casual', formality: 'casual'})
```

### Created Relationships
- Color Complement Relationships (fashion color theory)
- Style Compatibility Relationships (outfit coordination)
- Occasion Nodes with style mappings
- Price Tier Nodes (budget, mid-range, premium, luxury)

### Execution
```bash
cd graph/phase1 && python phase3_ontology.py
```

---

## PHASE 4: Performance Optimization

### Purpose
Create indexes and optimize query performance for large-scale graph operations.

### Implementation
File: `phase4_performance.py`

### Index Creation
```cypher
# Core product indexes
CREATE INDEX product_title_idx FOR (p:Product) ON (p.title)
CREATE INDEX product_price_idx FOR (p:Product) ON (p.price)
CREATE INDEX product_brand_idx FOR (p:Product) ON (p.extracted_brand)

# Attribute indexes
CREATE INDEX color_name_idx FOR (c:Color) ON (c.name)
CREATE INDEX style_name_idx FOR (s:Style) ON (s.name)
CREATE INDEX brand_name_idx FOR (b:Brand) ON (b.name)
CREATE INDEX material_name_idx FOR (m:Material) ON (m.name)

# AI-specific indexes
CREATE INDEX ai_category_idx FOR (p:Product) ON (p.ai_category)
CREATE INDEX target_demographic_idx FOR (p:Product) ON (p.target_demographic)
CREATE INDEX formality_level_idx FOR (p:Product) ON (p.formality_level)
```

### Performance Improvements
- 13+ Performance Indexes created
- Query Response Times optimized to sub-10ms
- Memory usage optimization
- Relationship caching for frequent queries

### Execution
```bash
cd graph/phase1 && python phase4_performance.py
```

---

## PHASE 5: Advanced Query Capabilities

### Purpose
Implement complex search patterns and multi-dimensional filtering capabilities.

### Implementation
File: `phase5_advanced_queries.py`

### Query Examples
```cypher
# Multi-dimensional Product Search with AI attributes
MATCH (p:Product)-[:HAS_COLOR]->(c:Color)
MATCH (p)-[:HAS_STYLE]->(s:Style)
WHERE c.name IN ['red', 'blue'] 
  AND s.name IN ['casual', 'formal']
  AND p.price BETWEEN 20 AND 100
  AND p.target_demographic = 'women'
  AND p.brand_tier IN ['mid-range', 'premium']
RETURN p, c.name, s.name
ORDER BY p.brand_confidence DESC, p.price ASC
```

### Advanced Search Capabilities
- **Brand Confidence Filtering**: Filter by brand identification confidence
- **Seasonal Search**: Find products appropriate for specific seasons
- **Occasion-Based Discovery**: Search by specific occasions with formality levels
- **Material-Based Filtering**: Search by extracted materials
- **Demographic Targeting**: Find products for specific target audiences
- **Price Perception Search**: Search by perceived price tier vs actual price

### API Endpoints
- `GET /search/products` - Multi-dimensional filtering with AI attributes
- `GET /recommendations/color/{color}` - Color-based suggestions with confidence
- `GET /recommendations/style/{style}` - Style compatibility with formality levels
- `GET /search/occasion/{occasion}` - Context-appropriate discovery
- `GET /search/demographic/{target}` - Demographic-specific products
- `GET /search/brand-tier/{tier}` - Brand positioning-based search
- `GET /outfits/build` - Intelligent outfit assembly with AI attributes

### Execution
```bash
cd graph/phase1 && python phase5_advanced_queries.py
```

---

## Enhanced System Architecture

### Database Structure
```
Nodes:
├── Products: 4.6M+ (fashion products with AI-extracted attributes)
├── Colors: 11+ nodes (fashion color ontology)
├── Styles: 11+ nodes (style classification)
├── Brands: Variable (extracted brand nodes with tiers)
├── Materials: Variable (extracted material nodes)
├── Occasions: 6+ nodes (context-aware filtering)
└── PriceTiers: 4 nodes (budget, mid-range, premium, luxury)

Relationships:
├── HAS_COLOR: Product to color (with confidence scores)
├── HAS_STYLE: Product to style (with formality levels)
├── HAS_BRAND: Product to brand (with confidence scores)
├── MADE_OF: Product to material connections
├── COMPLEMENTS: Color harmony relationships
├── COMPATIBLE_WITH: Style coordination relationships
└── SUITABLE_FOR: Occasion mapping relationships
```

### Configuration Requirements
```bash
# Neo4j Database
NEO4J_URL=neo4j://your-host:7687
NEO4J_DATABASE=your_database
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# OpenAI Integration (Required for Phase 1)
OPENAI_API_KEY=your_openai_key

# Optional: Qdrant Vector Database
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
```

---

## Implementation Order

| Phase | Duration | Purpose | Cost |
|-------|----------|---------|------|
| Phase 1 | Hours | LLM-based extraction with structured outputs | ~$69k for 4.6M products |
| Phase 3 | Seconds | Fashion ontology creation | Minimal |
| Phase 4 | Seconds | Performance optimization | Minimal |
| Phase 5 | Seconds | Advanced query capabilities | Minimal |

---

## Monitoring & Validation

### Check LLM Extraction Progress
```python
import asyncio
from services.user.knowledge_graph import UserKnowledgeGraphService

async def check_progress():
    service = UserKnowledgeGraphService('neo4j://host:7687', 'user', 'pass')
    await service.initialize()
    
    # Check extraction progress
    result = await service.query('''
        MATCH (p:Product) 
        WHERE p.extracted_colors IS NOT NULL 
        RETURN count(p) as extracted, 
               avg(p.color_confidence) as avg_confidence
    ''')
    
    print(f'Products with AI extraction: {result[0]["extracted"]:,}')
    print(f'Average confidence: {result[0]["avg_confidence"]:.2f}')
```

### Validate Enhanced Relationships
```cypher
MATCH ()-[r]->()
RETURN type(r) as relationship_type, count(r) as count,
       avg(r.confidence) as avg_confidence
ORDER BY count DESC
```

### Check AI Attribute Distribution
```cypher
MATCH (p:Product)
WHERE p.extracted_brand IS NOT NULL
RETURN p.brand_tier, count(p) as products
ORDER BY products DESC
```

---

## Success Metrics

### Technical Targets
- Data Coverage: 90%+ products with AI-extracted metadata
- Extraction Confidence: >85% average confidence scores
- Query Performance: <1 second for multi-attribute searches  
- Relationship Count: 10M+ product-attribute relationships
- Brand Recognition: >90% accuracy on known brands

### Expected Results After LLM Extraction
- **Enhanced Accuracy**: Contextual understanding vs pattern matching
- **Rich Metadata**: 15+ attributes per product vs basic title/description
- **Intelligent Relationships**: Confidence-scored connections
- **Advanced Search**: Multi-dimensional filtering with AI insights
- **Brand Intelligence**: Tier-based brand positioning analysis
- **Material Knowledge**: Extracted fabric and construction details
- **Demographic Insights**: Target audience identification
- **Seasonal Intelligence**: Context-appropriate seasonal classification

---

## Usage Examples

### AI-Enhanced Color Search
```cypher
MATCH (p:Product)-[:HAS_COLOR {confidence: conf}]->(c:Color {name: 'blue'})
WHERE conf > 0.8
RETURN p.title, p.extracted_brand, conf
ORDER BY conf DESC
LIMIT 10
```

### Brand Tier Analysis
```cypher
MATCH (p:Product)
WHERE p.brand_tier = 'luxury' AND p.extracted_brand IS NOT NULL
RETURN p.extracted_brand, count(p) as products, avg(p.price) as avg_price
ORDER BY products DESC
```

### Multi-Attribute Intelligence Search
```cypher
MATCH (p:Product)
WHERE 'elegant' IN p.extracted_styles 
  AND 'formal' IN p.occasions
  AND p.target_demographic = 'women'
  AND p.season IN ['spring', 'all-season']
  AND p.brand_confidence > 0.9
RETURN p.title, p.extracted_brand, p.materials, p.price
ORDER BY p.brand_confidence DESC, p.price ASC
```

### Material-Based Discovery
```cypher
MATCH (p:Product)-[:MADE_OF]->(m:Material {name: 'silk'})
WHERE p.price_perception = 'luxury'
RETURN p.title, p.extracted_brand, p.key_features
LIMIT 20
```

This guide provides a comprehensive framework for implementing advanced AI-powered graph database enhancement on any fashion product dataset.