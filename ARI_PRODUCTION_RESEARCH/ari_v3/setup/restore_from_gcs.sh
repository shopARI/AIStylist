#!/bin/bash
# =============================================================================
# ARI V3 - Download and Restore Qdrant Data from GCS
# =============================================================================
# This script downloads product snapshots from Google Cloud Storage and
# restores them to your local Qdrant instance.
#
# Prerequisites:
#   - Google Cloud SDK installed (gcloud, gsutil)
#   - Qdrant running locally (run setup_qdrant.sh first)
#   - ~80GB free disk space
#   - Internet connection for download
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

GCS_BUCKET="gs://shopari_bucket/qdrant-snapshots"
LOCAL_DIR="${SNAPSHOT_DIR:-$HOME/qdrant_snapshots}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"

echo "=============================================="
echo "ARI V3 - Qdrant Data Setup"
echo "=============================================="
echo ""
echo "This script will:"
echo "  1. Authenticate with Google Cloud"
echo "  2. Download snapshots from GCS (~73GB)"
echo "  3. Restore them to Qdrant"
echo ""
echo "GCS Source: $GCS_BUCKET"
echo "Local Dir:  $LOCAL_DIR"
echo "Qdrant:     $QDRANT_URL"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Check prerequisites
# -----------------------------------------------------------------------------
echo "[1/5] Checking prerequisites..."

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}ERROR: gcloud not found. Install Google Cloud SDK:${NC}"
    echo "  https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! command -v gsutil &> /dev/null; then
    echo -e "${RED}ERROR: gsutil not found. Install Google Cloud SDK:${NC}"
    echo "  https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! curl -s "$QDRANT_URL/collections" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Qdrant is not running at $QDRANT_URL${NC}"
    echo "  Run setup_qdrant.sh first"
    exit 1
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 2: Authenticate with Google Cloud
# -----------------------------------------------------------------------------
echo "[2/5] Authenticating with Google Cloud..."

# Check if already authenticated
if gsutil ls "$GCS_BUCKET" > /dev/null 2>&1; then
    echo "Already authenticated."
else
    echo "Opening browser for Google Cloud login..."
    gcloud auth login
fi

echo ""

# -----------------------------------------------------------------------------
# Step 3: Download snapshots
# -----------------------------------------------------------------------------
echo "[3/5] Downloading snapshots from GCS..."

mkdir -p "$LOCAL_DIR"

# Check if files already exist
if [ -f "$LOCAL_DIR/fashion_products.snapshot" ] && [ -f "$LOCAL_DIR/fashion_visual.snapshot" ]; then
    echo -e "${YELLOW}Snapshot files already exist in $LOCAL_DIR${NC}"
    read -p "Re-download? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping download."
    else
        gsutil cp "$GCS_BUCKET/*.snapshot" "$LOCAL_DIR/"
    fi
else
    echo "Downloading ~73GB total (this will take 10-20 minutes)..."
    gsutil cp "$GCS_BUCKET/*.snapshot" "$LOCAL_DIR/"
fi

echo ""
echo "Downloaded files:"
ls -lh "$LOCAL_DIR"/*.snapshot
echo ""

# -----------------------------------------------------------------------------
# Step 4: Restore to Qdrant
# -----------------------------------------------------------------------------
echo "[4/5] Restoring snapshots to Qdrant..."

echo ""
echo "Restoring fashion_products (43GB - semantic search)..."
echo "This may take several minutes..."
curl -X POST "$QDRANT_URL/collections/fashion_products/snapshots/upload?priority=snapshot" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@$LOCAL_DIR/fashion_products.snapshot"

echo ""
echo "Restoring fashion_fashionsig_neo4j_1024d (30GB - visual search)..."
curl -X POST "$QDRANT_URL/collections/fashion_fashionsig_neo4j_1024d/snapshots/upload?priority=snapshot" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@$LOCAL_DIR/fashion_visual.snapshot"

echo ""

# -----------------------------------------------------------------------------
# Step 5: Verify
# -----------------------------------------------------------------------------
echo "[5/5] Verifying restoration..."

PRODUCTS_COUNT=$(curl -s "$QDRANT_URL/collections/fashion_products" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null || echo "0")
VISUAL_COUNT=$(curl -s "$QDRANT_URL/collections/fashion_fashionsig_neo4j_1024d" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null || echo "0")

echo ""
echo -e "${GREEN}=============================================="
echo "Restoration Complete!"
echo "==============================================${NC}"
echo ""
echo "Collections restored:"
printf "  fashion_products:              %'d products\n" $PRODUCTS_COUNT
printf "  fashion_fashionsig_neo4j_1024d: %'d products\n" $VISUAL_COUNT
echo ""
echo "You can now run the ARI demo:"
echo "  cd ../.. && python demo_cli.py"
echo ""
