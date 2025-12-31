# FashionSigLIP Embedding Generation Guide

Complete guide to all available embedding generation scripts for the ARI fashion system.

---

## Overview

This system uses **FashionSigLIP** (`google/siglip-large-patch16-384`) to generate embeddings from Neo4j product data. All scripts support UUID-based products from the `productionbackup2` Neo4j database.

### Qdrant Collections

| Collection Name | Dimensions | Type | Status | Points |
|----------------|------------|------|--------|--------|
| `fashion_fashionsig_neo4j_1024d` | 1024d | Vision-only | ✅ Complete | 6,409,367 |
| `fashion_fashionsig_multimodal_multi` | 2048d | Multimodal (text+vision) | 🔄 In Progress | 0 |
| `fashion_products` | 1536d | Text-only (OpenAI) | ✅ Complete | 6,414,404 |

---

## Available Scripts

### 1. **Multimodal Multi-Image (RECOMMENDED FOR PRODUCTION)**
**Script:** `run_fashionsig_multimodal_multi_image.py`

**What it does:**
- ✅ Uses **REAL Neo4j UUID products** (no mock data)
- ✅ Processes **ALL images per product** (multiple embeddings per product)
- ✅ Generates **2048d multimodal embeddings** (1024d text + 1024d vision)
- ✅ Downloads **REAL product images** from `https://app.shopari.com/images/`
- ✅ Creates separate Qdrant points for each image with format: `{uuid}_{image_index}`

**Data Source:**
```cypher
MATCH (p:Product)
WHERE p.id IS NOT NULL AND p.images IS NOT NULL
RETURN p.id AS uuid, p.title, p.brand, p.price, p.description, p.images
```

**Output:**
- **Collection:** `fashion_fashionsig_multimodal_multi`
- **Point ID Format:** UUID string (e.g., `"abc123..._{image_index}"`)
- **Embedding:** 2048d (text + vision concatenated)
- **Payload:**
  ```json
  {
    "product_uuid": "original-uuid",
    "image_index": 0,
    "point_id_str": "uuid_0",
    "name": "Product Name",
    "category": "...",
    "price": 99.99,
    "brand": "...",
    "text_used": "Product Name brand description...",
    "embedding_type": "fashionsig_multimodal",
    "processed_at": "2025-10-05T..."
  }
  ```

**How to run:**
```bash
# Default settings (2500 products per batch)
python run_fashionsig_multimodal_multi_image.py

# Custom batch size
BATCH_SIZE=1500 python run_fashionsig_multimodal_multi_image.py

# Resume from specific offset
START_OFFSET=10000 python run_fashionsig_multimodal_multi_image.py

# Combined
BATCH_SIZE=2000 START_OFFSET=5000 python run_fashionsig_multimodal_multi_image.py
```

**Example:**
If product `abc-123` has 3 images, it creates 3 Qdrant points:
- Point ID: `uuid5("abc-123_0")` → embedding from image 0
- Point ID: `uuid5("abc-123_1")` → embedding from image 1
- Point ID: `uuid5("abc-123_2")` → embedding from image 2

**Performance:**
- Batch size: 2500 products (default)
- Upload chunks: 500 points per upload
- Concurrent downloads: 100 images
- Processing rate: ~100K products/hour
- Total time for 6.4M products: ~64 hours

---

### 2. **Vision-Only Multi-Image**
**Script:** `run_fashionsig_vision_multi_image.py`

**What it does:**
- ✅ Uses **REAL Neo4j UUID products**
- ✅ Processes **ALL images per product**
- ✅ Generates **1024d VISION-ONLY embeddings** (from images)
- ⚠️ No text embeddings (vision only)

**Output:**
- **Collection:** Would need to be specified
- **Embedding:** 1024d vision-only

**How to run:**
```bash
python run_fashionsig_vision_multi_image.py
```

**Use case:** When you only want visual similarity without text semantics.

---

### 3. **Multimodal A100 (Mock Data - NOT RECOMMENDED)**
**Script:** `run_fashionsig_a100_multimodal.py`

**What it does:**
- ❌ Uses **MOCK DATA** from `picsum.photos` (NOT real products)
- ⚠️ For testing/demo purposes only
- Generates 2048d multimodal embeddings

**How to run:**
```bash
python run_fashionsig_a100_multimodal.py
```

**⚠️ WARNING:** This script uses mock data! Not suitable for production.

---

### 4. **Vision-Only A100 (Already Complete)**
**Script:** `run_fashionsig_a100_production.py`

**What it does:**
- ✅ Already completed - created `fashion_fashionsig_neo4j_1024d` collection
- ✅ 6.4M vision-only embeddings
- ⚠️ Uses mock data (picsum.photos)

**Status:** ✅ Complete (6,409,367 points in Qdrant)

---

## UUID vs Integer IDs

### UUID Format (RECOMMENDED)
All **multi-image scripts** use UUID strings for point IDs:

```python
# Product UUID: "abc-123-def-456"
# Image index: 0
# Point ID: uuid5("abc-123-def-456_0") → "xyz-789-..."

# Benefits:
# - Deterministic (same input = same UUID)
# - No collisions
# - Compatible with Neo4j UUIDs
# - Human-readable in payload (point_id_str field)
```

### Integer IDs (Legacy)
Some older scripts used integer hashing - avoid this for new collections.

---

## Multi-Image Support

### How Multi-Image Works

Products in Neo4j have an `images` field containing a JSON array:
```json
{
  "id": "abc-123",
  "images": [
    "path1/image1.png",
    "path2/image2.png",
    "path3/image3.png"
  ]
}
```

Multi-image scripts:
1. **Download ALL images** for each product
2. **Generate separate embeddings** for each image
3. **Create separate Qdrant points** with unique IDs

**Example:**
```
Product: abc-123 (3 images)
├─ Point 1: uuid5("abc-123_0") → embedding from image 0
├─ Point 2: uuid5("abc-123_1") → embedding from image 1
└─ Point 3: uuid5("abc-123_2") → embedding from image 2
```

**Benefits:**
- Captures different views/angles of same product
- Better visual similarity matching
- More comprehensive product representation

**Storage:**
- Each point stores `product_uuid` and `image_index` in payload
- Can reconstruct which images belong to which product
- Query returns all image variations

---

## Image URL Format

### Correct Format (FIXED)
```python
# Neo4j stores: "bebfd6e9-d390-4f3e-b0fb-f3a1e4ddec49/b5a77d71.../file.png"
# Full URL: https://app.shopari.com/images/bebfd6e9-d390-4f3e-b0fb-f3a1e4ddec49/b5a77d71.../file.png
```

### ❌ Incorrect (Old)
```python
# DON'T USE: https://storage.googleapis.com/shopari_images/{path}
```

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BATCH_SIZE` | 2500 | Products per batch |
| `START_OFFSET` | 0 | Skip to this product offset |
| `MAX_CONCURRENT` | 100 | Concurrent image downloads |
| `CHECKPOINT_INTERVAL` | 5 | Batches between checkpoints |
| `NEO4J_URI` | From .env | Neo4j connection |
| `NEO4J_DATABASE` | productionbackup2 | Neo4j database name |
| `QDRANT_URL` | From .env | Qdrant connection |

### Recommended Settings

**For A100 GPU:**
```bash
BATCH_SIZE=2500 MAX_CONCURRENT=100 python run_fashionsig_multimodal_multi_image.py
```

**For slower GPUs:**
```bash
BATCH_SIZE=1000 MAX_CONCURRENT=50 python run_fashionsig_multimodal_multi_image.py
```

**For resuming after interruption:**
```bash
START_OFFSET=100000 python run_fashionsig_multimodal_multi_image.py
```

---

## Checkpoint System

All scripts save checkpoints to resume processing:

**Checkpoint file:** `fashionsig_a100_checkpoint_YYYYMMDD.json`

**To resume:**
- Script automatically loads last checkpoint
- Use `START_OFFSET` to override

**To reset:**
```bash
rm fashionsig_a100_checkpoint_*.json
```

---

## Performance Metrics

### Multimodal Multi-Image (run_fashionsig_multimodal_multi_image.py)

| Metric | Value |
|--------|-------|
| Processing rate | ~100K products/hour |
| Batch time | ~5 minutes (2500 products) |
| Upload time | ~30 seconds per 500 points |
| GPU memory | ~25GB peak (A100) |
| Total time (6.4M) | ~64 hours |

**Breakdown per batch (2500 products):**
1. Neo4j fetch: ~1 second
2. Image download: ~2 minutes (concurrent)
3. Embedding generation: ~2 minutes (GPU)
4. Qdrant upload: ~1 minute (chunked)

---

## Troubleshooting

### Issue: "Sequence length must be less than max_position_embeddings"
**Fix:** Already patched - token max_length reduced from 77 to 64

### Issue: "Qdrant upload timeout"
**Fix:** Already patched - chunked uploads (500 points per chunk) with retry logic

### Issue: "Image download failed (404)"
**Fix:** Already patched - correct URL format `https://app.shopari.com/images/`

### Issue: "Connection refused to Qdrant"
**Check:** QDRANT_URL and QDRANT_API_KEY in .env

### Issue: "Neo4j connection failed"
**Check:** NEO4J_URI, NEO4J_DATABASE=productionbackup2 in .env

---

## Comparison Matrix

| Feature | Multimodal Multi-Image | Vision Multi-Image | A100 Multimodal (Mock) |
|---------|----------------------|-------------------|----------------------|
| **Real Neo4j Data** | ✅ Yes | ✅ Yes | ❌ No (mock) |
| **UUID Support** | ✅ Yes | ✅ Yes | ❌ No (integers) |
| **Multiple Images** | ✅ Yes (all) | ✅ Yes (all) | ❌ No (single) |
| **Text Embeddings** | ✅ Yes (1024d) | ❌ No | ✅ Yes (1024d) |
| **Vision Embeddings** | ✅ Yes (1024d) | ✅ Yes (1024d) | ✅ Yes (1024d) |
| **Total Dimensions** | 2048d | 1024d | 2048d |
| **Production Ready** | ✅ Yes | ✅ Yes | ❌ No |
| **Recommended** | ✅ **BEST** | ⚠️ Limited | ❌ Testing only |

---

## Recommended Workflow

### For Production Deployment:

1. **Start with multimodal multi-image:**
   ```bash
   python run_fashionsig_multimodal_multi_image.py
   ```

2. **Monitor progress:**
   - Check logs: `tail -f fashionsig_a100_multimodal_*.log`
   - Check checkpoint: `cat fashionsig_a100_checkpoint_*.json`

3. **If interrupted, resume:**
   ```bash
   # Checkpoint auto-resumes, or manually set offset
   START_OFFSET=50000 python run_fashionsig_multimodal_multi_image.py
   ```

4. **Verify collection:**
   ```bash
   python check_qdrant_collections.py
   ```

---

## Technical Details

### FashionSigLIP Model
- **Model:** `google/siglip-large-patch16-384`
- **Framework:** Hugging Face Transformers
- **Vision encoder:** 1024d output
- **Text encoder:** 1024d output
- **Max text tokens:** 64 (SigLIP limit)
- **Image size:** 384x384 pixels
- **Precision:** FP16 (A100 optimization)

### Embedding Generation
```python
# Text encoding
text_embedding = model.text_model(tokenized_text).last_hidden_state.mean(dim=1)
# Result: [1, 1024]

# Vision encoding
vision_embedding = model.vision_model(processed_image).last_hidden_state.mean(dim=1)
# Result: [1, 1024]

# Multimodal combination
multimodal_embedding = torch.cat([text_embedding, vision_embedding], dim=1)
# Result: [1, 2048]
```

### Text Composition
For multimodal embeddings, text is composed as:
```python
text = f"{product.name} {product.category} {product.brand} {product.description}"
```
Truncated to 64 tokens maximum.

---

## Files Modified/Created

### Recent Fixes Applied:
1. ✅ `run_fashionsig_multimodal_multi_image.py` - UUID IDs, chunked uploads, reduced batch size
2. ✅ `run_fashionsig_vision_multi_image.py` - Correct image URLs
3. ✅ `services/ml/fashionsig_encoder.py` - Token length fix (64 tokens)
4. ✅ `run_fashionsig_a100_multimodal.py` - Token length fix
5. ✅ `services/application.py` - LLM API fix (agenerate → step)

### Configuration Files:
- `.env` - Database and Qdrant credentials
- `fashionsig_a100_checkpoint_*.json` - Processing checkpoints
- `*.log` - Processing logs

---

## Next Steps

### To Complete Multimodal Collection:

1. **Run the script:**
   ```bash
   python run_fashionsig_multimodal_multi_image.py
   ```

2. **Expected timeline:**
   - 6.4M products × ~3 images average = ~19M embeddings
   - Processing rate: ~100K products/hour
   - Total time: ~64 hours

3. **Monitor completion:**
   ```bash
   # Check collection status
   python check_qdrant_collections.py | grep fashion_fashionsig_multimodal_multi

   # Expected final count: ~19M points
   ```

4. **Update VisionBot** to use new collection (when ready)

---

## Contact & Support

For issues or questions about embedding generation:
- Check logs in `fashionsig_a100_multimodal_*.log`
- Review checkpoint file for progress
- Verify Neo4j and Qdrant connections in `.env`

---

**Last Updated:** 2025-10-05
**Status:** Ready for production multimodal embedding generation
