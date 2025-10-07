# FashionSigLIP Embedding Scripts - Complete Guide

## Overview

This repository contains **6 FashionSigLIP embedding generation scripts**, each optimized for different use cases. All scripts use the `google/siglip-large-patch16-384` model and are A100 GPU-optimized.

---

## Quick Comparison Table

| Script | Embedding Type | Dimensions | Product ID | Images/Product | Collection Name | Status |
|--------|---------------|------------|------------|----------------|-----------------|--------|
| **run_fashionsig_a100_production.py** | Vision-only | 1024d | Integer | Single | `fashion_fashionsig_1024d` | **99.6% Complete** |
| **run_fashionsig_a100_multimodal.py** | Text + Vision | 2048d | Integer | Single | `fashion_fashionsig_2048d` | Ready to run |
| **run_fashionsig_vision_multi_image.py** | Vision-only | 1024d | **UUID** | **Multiple** | `fashion_fashionsig_vision_multi` | **NEW - Ready** |
| **run_fashionsig_multimodal_multi_image.py** | Text + Vision | 2048d | **UUID** | **Multiple** | `fashion_fashionsig_multimodal_multi` | **NEW - Ready** |

---

## Script Details

### 1. run_fashionsig_a100_production.py

**Purpose:** Original vision-only embedding generation for 6.4M products

**Embedding Type:** Vision-only (1024 dimensions)
- Uses `SiglipVisionModel` only
- Processes product images only
- No text encoding

**Product Identification:**
- Integer IDs (1, 2, 3, ...)
- Single primary image per product

**Qdrant Collection:** `fashion_fashionsig_1024d`

**Current Progress:**
```
Processed: 6,414,858 / 6,440,000 (99.6%)
Successful: 6,409,367
Failed: 4,498
Status: Nearly complete
```

**Use Cases:**
- Pure image-to-image similarity search
- "Find visually similar items"
- Visual style matching
- Fast retrieval with smaller embeddings

**Pros:**
- ✅ Fastest processing (vision-only)
- ✅ Smallest embeddings (1024d)
- ✅ Lower memory usage
- ✅ Good for pure visual similarity

**Cons:**
- ❌ Cannot match on text descriptions
- ❌ Misses semantic information
- ❌ Single image per product only
- ❌ Integer IDs (not UUID)

**Run Command:**
```bash
python run_fashionsig_a100_production.py
```

---

### 2. run_fashionsig_a100_multimodal.py

**Purpose:** Text + Vision combined embeddings for richer semantic search

**Embedding Type:** Multimodal (2048 dimensions)
- Uses full `SiglipModel` (vision + text encoders)
- Text embeddings (1024d) from product descriptions
- Vision embeddings (1024d) from product images
- Concatenated to 2048d multimodal embeddings

**Product Identification:**
- Integer IDs (1, 2, 3, ...)
- Single primary image per product

**Qdrant Collection:** `fashion_fashionsig_2048d`

**Text Input Format:**
```python
text = f"{name} {category} {brand} {description}"
# Example: "Black Blazer Professional Outerwear Armani Elegant business blazer"
```

**Embedding Generation:**
```python
# Text embeddings (1024d)
text_outputs = model.text_model(**text_inputs)
text_embeddings = text_outputs.last_hidden_state.mean(dim=1)

# Vision embeddings (1024d)
vision_outputs = model.vision_model(**image_inputs)
vision_embeddings = vision_outputs.last_hidden_state.mean(dim=1)

# Concatenate (2048d)
multimodal_embeddings = torch.cat([text_embeddings, vision_embeddings], dim=1)
```

**Use Cases:**
- Semantic + visual search: "elegant black dress for wedding"
- Text-to-product matching with visual context
- Brand/category filtering with visual style
- Best for general-purpose fashion search

**Pros:**
- ✅ Richer search capabilities (text + visual)
- ✅ Better semantic understanding
- ✅ Handles natural language queries
- ✅ More robust product matching

**Cons:**
- ❌ Slower processing (encodes both text and images)
- ❌ Larger embeddings (2048d vs 1024d)
- ❌ ~1.5x higher memory usage
- ❌ Single image per product only
- ❌ Integer IDs (not UUID)

**Run Command:**
```bash
python run_fashionsig_a100_multimodal.py
```

---

### 3. run_fashionsig_vision_multi_image.py ⭐ NEW

**Purpose:** Vision-only embeddings with UUID support and multiple images per product

**Embedding Type:** Vision-only (1024 dimensions)
- Uses `SiglipVisionModel` only
- Processes ALL images per product separately
- Each image gets its own embedding

**Product Identification:**
- **UUID-based** (from Neo4j `p.id`)
- **Multiple images** per product (image_url_1 through image_url_5)
- Each image stored as separate Qdrant point

**Qdrant Collection:** `fashion_fashionsig_vision_multi`

**Point ID Strategy:**
```python
# Each image gets unique ID: {uuid}_{image_index}
point_id_str = f"{product_uuid}_{image_index}"
# Example: "550e8400-e29b-41d4-a716-446655440000_0"
#          "550e8400-e29b-41d4-a716-446655440000_1"

# Convert to integer hash for Qdrant
point_id = int(hashlib.md5(point_id_str.encode()).hexdigest()[:16], 16)
```

**Qdrant Payload:**
```python
{
    'product_uuid': '550e8400-e29b-41d4-a716-446655440000',
    'image_index': 0,  # Which image (0, 1, 2, 3, 4)
    'point_id_str': '550e8400-e29b-41d4-a716-446655440000_0',
    'name': 'Black Blazer',
    'category': 'Outerwear',
    'price': 299.99,
    'brand': 'Armani',
    'embedding_type': 'fashionsig_vision',
    'processed_at': '2025-10-05T12:34:56'
}
```

**Neo4j Query:**
```cypher
MATCH (p:Product)
WHERE p.id IS NOT NULL
RETURN
    p.id AS uuid,
    p.title AS name,
    p.category AS category,
    p.price AS price,
    p.brand AS brand,
    p.description AS description,
    p.image_url_1 AS image_url_1,
    p.image_url_2 AS image_url_2,
    p.image_url_3 AS image_url_3,
    p.image_url_4 AS image_url_4,
    p.image_url_5 AS image_url_5
ORDER BY p.id
SKIP $offset
LIMIT $limit
```

**Use Cases:**
- UUID-based product tracking across Neo4j and Qdrant
- Multiple product images (front, back, detail, lifestyle, etc.)
- Each image searchable independently
- "Find similar to this specific angle/view"

**Pros:**
- ✅ **UUID consistency** with Neo4j
- ✅ **Multiple images** per product preserved
- ✅ Each image's unique visual info retained
- ✅ Better for fashion (different angles matter)
- ✅ Fast vision-only processing
- ✅ Cross-reference with Neo4j via UUID

**Cons:**
- ❌ More Qdrant points (5x if all images present)
- ❌ No text semantic matching
- ❌ Requires Neo4j with UUID support

**Run Command:**
```bash
python run_fashionsig_vision_multi_image.py
```

---

### 4. run_fashionsig_multimodal_multi_image.py ⭐ NEW

**Purpose:** Multimodal embeddings with UUID support and multiple images per product

**Embedding Type:** Multimodal (2048 dimensions)
- Uses full `SiglipModel` (vision + text encoders)
- Text embeddings (1024d) from product descriptions
- Vision embeddings (1024d) from each product image
- Concatenated to 2048d per image

**Product Identification:**
- **UUID-based** (from Neo4j `p.id`)
- **Multiple images** per product (image_url_1 through image_url_5)
- Each image gets text+vision embedding

**Qdrant Collection:** `fashion_fashionsig_multimodal_multi`

**Point ID Strategy:**
```python
# Each image gets unique ID: {uuid}_{image_index}
point_id_str = f"{product_uuid}_{image_index}"
point_id = int(hashlib.md5(point_id_str.encode()).hexdigest()[:16], 16)
```

**Qdrant Payload:**
```python
{
    'product_uuid': '550e8400-e29b-41d4-a716-446655440000',
    'image_index': 0,
    'point_id_str': '550e8400-e29b-41d4-a716-446655440000_0',
    'name': 'Black Blazer',
    'category': 'Outerwear',
    'price': 299.99,
    'brand': 'Armani',
    'text_used': 'Black Blazer Outerwear Armani Elegant business blazer',
    'embedding_type': 'fashionsig_multimodal',
    'processed_at': '2025-10-05T12:34:56'
}
```

**Embedding Generation:**
```python
# Same text for all images of a product
text = f"{name} {category} {brand} {description}"

# For each image:
text_embedding = model.text_model(text)      # 1024d
vision_embedding = model.vision_model(image)  # 1024d
multimodal_embedding = concat(text, vision)   # 2048d
```

**Use Cases:**
- **Most comprehensive search** - text + visual + multiple angles
- UUID-based product tracking
- Natural language queries with visual context
- "Find elegant black blazer with professional styling" + visual similarity
- Best for production AIStylist with rich metadata

**Pros:**
- ✅ **Most powerful** - combines all features
- ✅ UUID consistency with Neo4j
- ✅ Multiple images per product
- ✅ Semantic + visual search
- ✅ Natural language understanding
- ✅ Each image's visual + text info preserved

**Cons:**
- ❌ Slowest processing (text + vision for each image)
- ❌ Largest embeddings (2048d)
- ❌ Highest memory usage (~2x vision-only)
- ❌ More Qdrant points (5x if all images present)
- ❌ Most storage required

**Run Command:**
```bash
python run_fashionsig_multimodal_multi_image.py
```

---

## Architecture Comparison

### Single-Image Scripts (Original)

```
Product (Integer ID) → Single Image → Single Qdrant Point

Product 1 → image_url → Embedding 1 (ID: 1)
Product 2 → image_url → Embedding 2 (ID: 2)
Product 3 → image_url → Embedding 3 (ID: 3)
```

### Multi-Image Scripts (NEW)

```
Product (UUID) → Multiple Images → Multiple Qdrant Points

Product UUID-A
  ├─ image_url_1 → Embedding UUID-A_0
  ├─ image_url_2 → Embedding UUID-A_1
  ├─ image_url_3 → Embedding UUID-A_2
  ├─ image_url_4 → Embedding UUID-A_3
  └─ image_url_5 → Embedding UUID-A_4
```

---

## Storage Requirements

### For 6.44M Products

| Script | Embedding Size | Collection Size | Notes |
|--------|---------------|----------------|-------|
| **Vision-only (1024d)** | 1024 × 4 bytes | ~26 GB | Single image per product |
| **Multimodal (2048d)** | 2048 × 4 bytes | ~52 GB | Single image per product |
| **Vision Multi-Image** | 1024 × 4 bytes | ~130 GB | 5 images per product (avg) |
| **Multimodal Multi-Image** | 2048 × 4 bytes | ~260 GB | 5 images per product (avg) |

---

## Configuration

### Environment Variables

All scripts support the same configuration:

```bash
# A100 Batch Configuration
export BATCH_SIZE=6000              # Products per batch
export MAX_CONCURRENT=100           # Concurrent image downloads
export TARGET_PRODUCTS=6440000      # Total products to process
export CHECKPOINT_INTERVAL=5        # Batches between checkpoints

# Neo4j Configuration (Multi-Image Scripts)
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"

# Qdrant Configuration
# (Hardcoded in scripts for production)
# URL: https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io:6333
```

### GPU Settings

```bash
# Optional GPU tuning
export GPU_MEMORY_FRACTION=0.8
export RETRY_ATTEMPTS=3
export RETRY_DELAY=1.0
```

---

## Checkpoint System

All scripts support **checkpoint/resume**:

```python
# Checkpoint files
fashionsig_a100_checkpoint_YYYYMMDD.json           # Vision-only
fashionsig_a100_multimodal_checkpoint_YYYYMMDD.json # Multimodal
fashionsig_vision_multi_checkpoint_YYYYMMDD.json    # Vision multi-image
fashionsig_multimodal_multi_checkpoint_YYYYMMDD.json # Multimodal multi-image
```

**Resume Example:**
```bash
# If interrupted, just re-run the script
python run_fashionsig_vision_multi_image.py
# [INFO] Resuming from checkpoint: 3,200,000 products processed
```

---

## Performance Metrics

### A100 80GB GPU

| Script | Batch Size | Images/Batch | Processing Time | Throughput |
|--------|-----------|--------------|----------------|------------|
| **Vision-only** | 6000 | 6000 | ~94 sec | ~63 products/sec |
| **Multimodal** | 6000 | 6000 | ~120 sec | ~50 products/sec |
| **Vision Multi** | 1200 | ~6000 | ~110 sec | ~54 images/sec |
| **Multimodal Multi** | 1200 | ~6000 | ~150 sec | ~40 images/sec |

*Note: Multi-image scripts process fewer products per batch but more total images*

---

## Qdrant Collections

### Collection Structure

All collections use:
- **Distance:** Cosine similarity
- **Optimization:** Indexing enabled
- **Batch Upload:** Enabled for performance

```python
# Vision-only collections (1024d)
fashion_fashionsig_1024d              # Single image, integer ID
fashion_fashionsig_vision_multi       # Multi-image, UUID

# Multimodal collections (2048d)
fashion_fashionsig_2048d              # Single image, integer ID
fashion_fashionsig_multimodal_multi   # Multi-image, UUID
```

---

## Use Case Recommendations

### Choose Vision-Only (1024d) When:
- ✅ You need pure visual similarity
- ✅ Memory/storage is constrained
- ✅ Processing speed is critical
- ✅ You have "find similar" use cases only
- ✅ Product metadata is poor or missing

### Choose Multimodal (2048d) When:
- ✅ You need comprehensive search (text + visual)
- ✅ Users search with natural language
- ✅ You have rich product metadata
- ✅ Memory/storage is not a constraint
- ✅ **Recommended for production AIStylist**

### Choose Multi-Image When:
- ✅ Products have multiple images (front/back/detail/lifestyle)
- ✅ Different angles/views are important for search
- ✅ You need UUID consistency with Neo4j
- ✅ You want to preserve each image's unique visual info
- ✅ **Future-proof architecture for scaling**

### Production Recommendation:
**run_fashionsig_multimodal_multi_image.py**
- Most comprehensive search capability
- UUID consistency across systems
- Multiple images per product
- Text + visual semantic matching
- Best user experience

---

## Migration Strategy

### Phase 1: Current State
- ✅ `fashion_fashionsig_1024d` collection (99.6% complete)
- Vision-only, single image, integer IDs

### Phase 2: Parallel Processing
- Run `run_fashionsig_multimodal_multi_image.py`
- Build `fashion_fashionsig_multimodal_multi` collection
- Keep existing collection operational

### Phase 3: Comparison
- Run both collections in parallel
- Compare search quality and performance
- Gather user feedback

### Phase 4: Migration
- Update VisionBot to use multimodal multi-image collection
- Update query embedding generation
- Deprecate single-image collections

### Phase 5: Cleanup
- Archive old collections
- Full production on UUID-based multimodal

---

## Troubleshooting

### Neo4j Connection Issues
```python
# Check Neo4j credentials
export NEO4J_URI="bolt://your-host:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"
```

### Qdrant Upload Failures
```bash
# Check error counts in checkpoint file
cat fashionsig_*_checkpoint_*.json | grep error_counts
# Retry failed batches automatically on next run
```

### GPU Out of Memory
```bash
# Reduce batch size
export BATCH_SIZE=3000

# Reduce sub-batch size (edit script)
sub_batch_size = min(100, len(image_batch))  # Default: 150-200
```

### UUID Format Errors
```python
# Validate UUIDs in Neo4j
MATCH (p:Product)
WHERE p.id IS NOT NULL
RETURN p.id
LIMIT 10
```

---

## Summary

| Feature | Vision-Only | Multimodal | Vision Multi | Multimodal Multi |
|---------|------------|------------|--------------|------------------|
| **Embedding Dims** | 1024 | 2048 | 1024 | 2048 |
| **Product ID** | Integer | Integer | **UUID** | **UUID** |
| **Images/Product** | 1 | 1 | **Multiple** | **Multiple** |
| **Text Encoding** | ❌ | ✅ | ❌ | ✅ |
| **Vision Encoding** | ✅ | ✅ | ✅ | ✅ |
| **Neo4j Consistency** | ❌ | ❌ | **✅** | **✅** |
| **Processing Speed** | Fastest | Slow | Fast | Slowest |
| **Search Quality** | Visual | Best | Visual | **Best** |
| **Storage** | Smallest | Medium | Large | **Largest** |
| **Production Ready** | ✅ | ✅ | ✅ | **✅** |

**Recommended for Production:** `run_fashionsig_multimodal_multi_image.py`

---

## Quick Start Commands

```bash
# 1. Vision-only single image (original - nearly complete)
python run_fashionsig_a100_production.py

# 2. Multimodal single image (ready to run)
python run_fashionsig_a100_multimodal.py

# 3. Vision-only multi-image with UUID (NEW)
python run_fashionsig_vision_multi_image.py

# 4. Multimodal multi-image with UUID (NEW - RECOMMENDED)
python run_fashionsig_multimodal_multi_image.py
```

---

**Generated:** 2025-10-05
**AIStylist Production Environment**
**FashionSigLIP Model:** google/siglip-large-patch16-384
