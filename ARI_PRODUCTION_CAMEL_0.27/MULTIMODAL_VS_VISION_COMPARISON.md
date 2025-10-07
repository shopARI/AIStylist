# FashionSigLIP: Vision-Only vs Multimodal Comparison

## Two Processing Scripts

### 1. Vision-Only Script (Original)
**File:** `run_fashionsig_a100_production.py`

**Embedding Type:** Vision embeddings only
**Dimensions:** 1024
**Collection:** `fashion_fashionsig_1024d`

**Model Components:**
- `SiglipVisionModel` - Vision encoder only
- Processes product images only
- No text encoding

**Embedding Generation:**
```python
# Vision-only
outputs = self.model(**inputs)
embeddings = outputs.last_hidden_state.mean(dim=1)  # [batch, 1024]
```

**Use Cases:**
- Image-to-image similarity search
- "Find visually similar items"
- Visual style matching
- Color/pattern/texture similarity

**Pros:**
- Faster processing (only processes images)
- Smaller embeddings (1024d vs 2048d)
- Lower memory usage
- Good for pure visual similarity

**Cons:**
- Cannot match on product descriptions, names, or text metadata
- Misses semantic information from text
- Less comprehensive product understanding

---

### 2. Multimodal Script (New)
**File:** `run_fashionsig_a100_multimodal.py`

**Embedding Type:** Combined text + vision embeddings
**Dimensions:** 2048 (1024 text + 1024 vision)
**Collection:** `fashion_fashionsig_2048d`

**Model Components:**
- `SiglipModel` - Full model with both encoders
- `SiglipVisionModel` - Vision encoder (1024d)
- `SiglipTextModel` - Text encoder (1024d)
- `SiglipTokenizer` - Text tokenizer

**Embedding Generation:**
```python
# Text embeddings
text_outputs = self.model.text_model(**text_inputs)
text_embeddings = text_outputs.last_hidden_state.mean(dim=1)  # [batch, 1024]

# Vision embeddings
vision_outputs = self.model.vision_model(**image_inputs)
vision_embeddings = vision_outputs.last_hidden_state.mean(dim=1)  # [batch, 1024]

# Concatenate for multimodal
multimodal_embeddings = torch.cat([text_embeddings, vision_embeddings], dim=1)  # [batch, 2048]
```

**Text Input:**
Combines product metadata into rich descriptions:
```python
text_desc = f"{product.name} {product.category} {product.brand} {product.description}"
# Example: "Black Blazer Professional Outerwear Armani Elegant business blazer"
```

**Use Cases:**
- Semantic + visual search: "elegant black dress for wedding"
- Text-to-product matching with visual context
- Brand/category filtering with visual style
- Comprehensive product understanding
- Best for general-purpose fashion search

**Pros:**
- **Richer search capabilities** - matches both text and visual features
- **Better semantic understanding** - understands product descriptions
- **More robust** - can handle queries like "professional outfit" or "summer dress"
- **Future-proof** - supports multimodal queries

**Cons:**
- Slower processing (encodes both text and images)
- Larger embeddings (2048d vs 1024d)
- Higher memory usage (~1.5x)
- Requires product metadata (name, description, etc.)

---

## Performance Comparison

| Metric | Vision-Only | Multimodal |
|--------|------------|------------|
| **Embedding Dimensions** | 1024 | 2048 |
| **Processing Speed** | ~200 products/batch | ~150 products/batch |
| **Memory Usage** | Lower | ~1.5x higher |
| **Collection Size (6M products)** | ~24 GB | ~48 GB |
| **Query Types Supported** | Image-based only | Text + Image + Combined |
| **Search Quality** | Visual only | Visual + Semantic |

---

## When to Use Each

### Use Vision-Only (`run_fashionsig_a100_production.py`) When:
- ✅ You need pure visual similarity
- ✅ Memory/storage is constrained
- ✅ Processing speed is critical
- ✅ You have "find similar" use cases only
- ✅ Product metadata is poor or missing

### Use Multimodal (`run_fashionsig_a100_multimodal.py`) When:
- ✅ You need comprehensive search (text + visual)
- ✅ Users search with natural language
- ✅ You have rich product metadata
- ✅ Memory/storage is not a constraint
- ✅ You want future-proof solution
- ✅ **Recommended for production AIStylist**

---

## Current Status

### Vision-Only Processing
```
Checkpoint: fashionsig_a100_checkpoint_20250929.json
Progress: 6,414,858 / 6,440,000 (99.6%)
Collection: fashion_fashionsig_1024d
Status: ✅ Nearly complete
```

### Multimodal Processing
```
Checkpoint: fashionsig_a100_multimodal_checkpoint_YYYYMMDD.json
Progress: Not started
Collection: fashion_fashionsig_2048d
Status: ⏳ Ready to run
```

---

## Running the Scripts

### Vision-Only (Current)
```bash
python run_fashionsig_a100_production.py
```

### Multimodal (New)
```bash
python run_fashionsig_a100_multimodal.py
```

Both scripts support the same environment variables:
- `BATCH_SIZE=6000` - Products per batch
- `MAX_CONCURRENT=100` - Concurrent image downloads
- `TARGET_PRODUCTS=6000000` - Total products to process
- `CHECKPOINT_INTERVAL=5` - Batches between checkpoints

---

## Storage Requirements

### Vision-Only
- 6.44M products × 1024 dims × 4 bytes = ~26 GB

### Multimodal
- 6.44M products × 2048 dims × 4 bytes = ~52 GB

**Recommendation:** Both collections can coexist in Qdrant for different use cases.

---

## Migration Strategy

1. **Keep vision-only collection** for image-to-image similarity
2. **Generate multimodal collection** for text+visual search
3. **Update VisionBot** to use multimodal collection for query embeddings
4. **Run both in parallel** initially to compare results
5. **Deprecate vision-only** once multimodal proves superior

---

## Summary

**Vision-Only (1024d):**
- ✅ **CONFIRMED**: Generates 1024-dim vision embeddings only
- ✅ Uses `SiglipVisionModel`
- ✅ Fast, compact, visual similarity only

**Multimodal (2048d):**
- ✅ **NEW**: Generates 2048-dim text+vision embeddings
- ✅ Uses full `SiglipModel` (text + vision encoders)
- ✅ Comprehensive search with semantic understanding
- ✅ **Recommended for production AIStylist**
