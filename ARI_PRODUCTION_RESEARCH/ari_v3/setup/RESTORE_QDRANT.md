# Restoring Qdrant Snapshots

Instructions for restoring the ARI product database from snapshots.

## Prerequisites

1. Qdrant must be running (run `setup_qdrant.sh` first)
2. You have the snapshot files:
   - `fashion_products.snapshot` (43GB) - Semantic search embeddings
   - `fashion_visual.snapshot` (30GB) - Visual search embeddings

## Step 1: Copy Snapshots to Your Machine

Get the snapshot files from your team lead and place them in a directory:

```bash
mkdir -p ~/qdrant_snapshots
# Copy or download the snapshot files to ~/qdrant_snapshots/
```

## Step 2: Upload Snapshots to Qdrant

### Option A: Using curl (Recommended)

```bash
# Restore fashion_products collection (semantic search)
# This will take several minutes for the 43GB file
curl -X POST "http://localhost:6333/collections/fashion_products/snapshots/upload?priority=snapshot" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@/path/to/fashion_products.snapshot"

# Restore fashion_visual collection (visual search)
curl -X POST "http://localhost:6333/collections/fashion_fashionsig_neo4j_1024d/snapshots/upload?priority=snapshot" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@/path/to/fashion_visual.snapshot"
```

### Option B: Using the restore script

Save this as `restore_snapshots.sh`:

```bash
#!/bin/bash
set -e

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
SNAPSHOT_DIR="${1:-$HOME/qdrant_snapshots}"

echo "Restoring Qdrant snapshots from: $SNAPSHOT_DIR"
echo "Qdrant URL: $QDRANT_URL"
echo ""

# Check files exist
if [ ! -f "$SNAPSHOT_DIR/fashion_products.snapshot" ]; then
    echo "ERROR: fashion_products.snapshot not found in $SNAPSHOT_DIR"
    exit 1
fi

if [ ! -f "$SNAPSHOT_DIR/fashion_visual.snapshot" ]; then
    echo "ERROR: fashion_visual.snapshot not found in $SNAPSHOT_DIR"
    exit 1
fi

# Restore semantic collection
echo "[1/2] Restoring fashion_products (43GB - this will take several minutes)..."
curl -X POST "$QDRANT_URL/collections/fashion_products/snapshots/upload?priority=snapshot" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@$SNAPSHOT_DIR/fashion_products.snapshot"

echo ""
echo "[2/2] Restoring fashion_fashionsig_neo4j_1024d (30GB)..."
curl -X POST "$QDRANT_URL/collections/fashion_fashionsig_neo4j_1024d/snapshots/upload?priority=snapshot" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@$SNAPSHOT_DIR/fashion_visual.snapshot"

echo ""
echo "Restore complete! Verifying..."

# Verify collections
curl -s "$QDRANT_URL/collections/fashion_products" | python3 -c "
import sys, json
data = json.load(sys.stdin)
count = data['result']['points_count']
print(f'fashion_products: {count:,} products')
"

curl -s "$QDRANT_URL/collections/fashion_fashionsig_neo4j_1024d" | python3 -c "
import sys, json
data = json.load(sys.stdin)
count = data['result']['points_count']
print(f'fashion_visual: {count:,} products')
"

echo ""
echo "Done!"
```

Run it:
```bash
chmod +x restore_snapshots.sh
./restore_snapshots.sh ~/qdrant_snapshots
```

## Step 3: Verify Restoration

Check that collections have data:

```bash
# List collections
curl http://localhost:6333/collections

# Check product counts
curl http://localhost:6333/collections/fashion_products | python3 -m json.tool | grep points_count
curl http://localhost:6333/collections/fashion_fashionsig_neo4j_1024d | python3 -m json.tool | grep points_count
```

Expected output:
- fashion_products: ~6.4 million points
- fashion_fashionsig_neo4j_1024d: ~6.4 million points

## Troubleshooting

### Upload times out

Large snapshots can take 10-30 minutes to upload. If curl times out:

```bash
# Increase timeout
curl --max-time 3600 -X POST "http://localhost:6333/collections/fashion_products/snapshots/upload?priority=snapshot" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@fashion_products.snapshot"
```

### Not enough disk space

The snapshots need to be extracted, requiring approximately:
- 50GB for fashion_products
- 35GB for fashion_visual
- Plus the 73GB snapshot files

Total: ~160GB free space recommended.

### Collection already exists with data

If you want to replace existing data:

```bash
# Delete existing collection first
curl -X DELETE "http://localhost:6333/collections/fashion_products"

# Then upload snapshot
curl -X POST "http://localhost:6333/collections/fashion_products/snapshots/upload?priority=snapshot" \
    -F "snapshot=@fashion_products.snapshot"
```

### Memory issues during restore

If Qdrant runs out of memory:

```bash
# Stop Qdrant
docker stop ari-qdrant

# Restart with more memory
docker run -d \
    --name ari-qdrant \
    -p 6333:6333 \
    -v ~/qdrant_data:/qdrant/storage \
    -e QDRANT__SERVICE__MAX_SEARCH_THREADS=2 \
    qdrant/qdrant:v1.12.1

# Retry restore
```

## Alternative: Direct File Copy

If you have direct access to the Qdrant storage directory:

```bash
# Stop Qdrant
docker stop ari-qdrant

# Copy snapshot files to Qdrant storage
cp fashion_products.snapshot ~/qdrant_data/snapshots/fashion_products/
cp fashion_visual.snapshot ~/qdrant_data/snapshots/fashion_fashionsig_neo4j_1024d/

# Start Qdrant
docker start ari-qdrant

# Trigger restore via API
curl -X PUT "http://localhost:6333/collections/fashion_products/snapshots/recover" \
    -H "Content-Type: application/json" \
    -d '{"location": "file:///qdrant/storage/snapshots/fashion_products/fashion_products.snapshot"}'
```

## Collection Name Mapping

The ARI system expects these collection names in `.env`:

```bash
QDRANT_COLLECTION_NAME=fashion_products
QDRANT_VISUAL_COLLECTION_NAME=fashion_fashionsig_neo4j_1024d
```

Make sure your `.env` file matches the restored collection names.
