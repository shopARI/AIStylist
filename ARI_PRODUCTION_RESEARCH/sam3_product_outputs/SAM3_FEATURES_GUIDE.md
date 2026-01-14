# SAM3 Complete Feature Extraction Guide

## Summary
Successfully extracted ALL available SAM3 features for fashion product analysis.

## Extracted Features (Per Product)

### 1. **Vision Features** (`*_vision_features.npy`)
- **Shape**: `(1, 256, 72, 72)`
- **Size**: ~5.1 MB
- **Description**: High-level 256-dimensional vision features at 1/16 resolution
- **Use Cases**:
  - Texture descriptors
  - Global appearance features
  - Content-based image retrieval
  - Can be averaged/pooled to get 256-dim product embeddings

### 2. **Feature Pyramid Network (FPN)** (`*_backbone_fpn.pkl`)
- **Shape**: 3 scales
  - Scale 0: `(1, 256, 288, 288)` - Fine details
  - Scale 1: `(1, 256, 144, 144)` - Medium details
  - Scale 2: `(1, 256, 72, 72)` - Coarse details
- **Size**: ~107 MB
- **Description**: Multi-scale feature representations capturing details at different resolutions
- **Use Cases**:
  - Multi-scale texture analysis
  - Hierarchical pattern recognition
  - Fine-grained vs coarse-grained feature extraction

### 3. **Position Encodings** (`*_vision_pos_enc.pkl`)
- **Shape**: 3 levels (same as FPN)
  - Level 0: `(1, 256, 288, 288)`
  - Level 1: `(1, 256, 144, 144)`
  - Level 2: `(1, 256, 72, 72)`
- **Size**: ~107 MB
- **Description**: Spatial position encodings for vision features
- **Use Cases**:
  - Spatial awareness
  - Location-based feature weighting

### 4. **Mask Logits** (`*_masks_logits.npy`)
- **Shape**: `(N, 1, 1000, 1000)` where N = number of masks
- **Size**: ~3.9 MB per mask
- **Description**: Raw probability maps before sigmoid activation (soft masks)
- **Use Cases**:
  - Confidence heatmaps
  - Uncertainty estimation
  - Fine-tuning segmentation thresholds

### 5. **Binary Masks** (`masks/*_mask_*.png`)
- **Shape**: `(H, W)` - typically 1000x1000
- **Size**: ~5 KB per mask
- **Description**: Hard binary segmentation masks
- **Use Cases**:
  - Object isolation
  - Background removal
  - ROI extraction for texture/color analysis

### 6. **Bounding Boxes** (in metadata JSON)
- **Format**: `[x0, y0, x1, y1]` in pixel coordinates
- **Description**: Tight bounding boxes around detected objects
- **Use Cases**:
  - Object cropping
  - Region proposal

### 7. **IoU Scores** (in metadata JSON)
- **Range**: 0.0 - 1.0
- **Description**: Confidence scores for each mask
- **Example**: `[0.9782561659812927]` = 97.8% confidence

## File Structure

```
/home/leo/sam3_product_outputs/
├── images/
│   └── 8109787549439014466.png (original image)
├── masks/
│   └── 8109787549439014466_mask_0.png (binary mask)
├── results/
│   ├── 8109787549439014466_overlay.png (visualization)
│   ├── 8109787549439014466_vision_features.npy (5.1 MB)
│   ├── 8109787549439014466_backbone_fpn.pkl (107 MB)
│   ├── 8109787549439014466_vision_pos_enc.pkl (107 MB)
│   └── 8109787549439014466_masks_logits.npy (3.9 MB)
└── metadata/
    └── 8109787549439014466_metadata.json (complete info)
```

## How to Use These Features

### Loading Features in Python

```python
import numpy as np
import pickle
from PIL import Image

product_id = "8109787549439014466"
base_path = "/home/leo/sam3_product_outputs/results"

# Load vision features
vision_features = np.load(f"{base_path}/{product_id}_vision_features.npy")
print(f"Vision features: {vision_features.shape}")  # (1, 256, 72, 72)

# Load FPN features (multi-scale)
with open(f"{base_path}/{product_id}_backbone_fpn.pkl", 'rb') as f:
    fpn_features = pickle.load(f)
    for i, fpn in enumerate(fpn_features):
        print(f"FPN scale {i}: {fpn.shape}")

# Load mask logits
mask_logits = np.load(f"{base_path}/{product_id}_masks_logits.npy")
print(f"Mask logits: {mask_logits.shape}")  # (1, 1, 1000, 1000)

# Load binary mask
mask = Image.open(f"/home/leo/sam3_product_outputs/masks/{product_id}_mask_0.png")
mask_array = np.array(mask) > 127  # Convert to boolean
```

### Texture Extraction on Isolated Regions

```python
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern
from skimage.filters import gabor
import cv2

# Load original image and mask
image = np.array(Image.open(f"/home/leo/sam3_product_outputs/images/{product_id}.png"))
mask = np.array(Image.open(f"/home/leo/sam3_product_outputs/masks/{product_id}_mask_0.png")) > 127

# Apply mask to isolate garment
garment_region = image * mask[:, :, np.newaxis]
gray = cv2.cvtColor(garment_region, cv2.COLOR_RGB2GRAY)

# Extract textures only from masked region
masked_pixels = gray[mask]

# Gabor filters for orientation/frequency
gabor_responses = []
for theta in np.arange(0, np.pi, np.pi / 4):
    for frequency in [0.1, 0.2, 0.3]:
        filt_real, filt_imag = gabor(gray, frequency=frequency, theta=theta)
        gabor_responses.append(filt_real[mask].mean())

# LBP for micro-texture patterns
lbp = local_binary_pattern(gray, P=8, R=1, method='uniform')
lbp_hist, _ = np.histogram(lbp[mask], bins=10, density=True)

# GLCM for texture statistics
glcm = graycomatrix(gray[mask], distances=[1], angles=[0], levels=256)
contrast = graycoprops(glcm, 'contrast')[0, 0]
homogeneity = graycoprops(glcm, 'homogeneity')[0, 0]
energy = graycoprops(glcm, 'energy')[0, 0]
```

## Next Steps for Fashion Product Analysis

1. **Texture Feature Extraction**:
   - Use masks to isolate garments
   - Apply Gabor/LBP/GLCM on masked regions
   - Extract ~256-512 texture features per product

2. **Color Extraction**:
   - K-Means clustering on masked pixels only
   - Extract dominant colors without background interference
   - Convert to perceptual color spaces (CIE LCh)

3. **Shape Analysis**:
   - Extract contours from masks
   - Compute Hu moments / Zernike moments
   - Detect garment parts (collar, sleeves, hem)

4. **Multi-Scale Features**:
   - Use FPN features for hierarchical texture analysis
   - Fine-scale FPN for fabric patterns
   - Coarse-scale FPN for overall garment structure

5. **Integration**:
   - Combine with existing ~10,600d embeddings
   - Add texture (~512d) + shape (~640d) + refined color features
   - Store in Qdrant for similarity search

## Performance Stats

- **Processing Speed**: ~15-20 seconds per product (including download)
- **Success Rate**: 100% (5/5 products)
- **Average Confidence**: 97-98% IoU scores
- **Storage per Product**: ~220 MB (with all features)
  - Vision features: 5 MB
  - FPN features: 107 MB
  - Position encodings: 107 MB
  - Mask logits: 4 MB
  - Overlays + masks: ~340 KB

## Conclusion

SAM3 provides **comprehensive visual features** for fashion product analysis:
- ✓ High-quality segmentation masks (97%+ confidence)
- ✓ Multi-scale deep features (FPN at 3 resolutions)
- ✓ High-level vision embeddings (256-dim at 72x72)
- ✓ Raw probability maps for custom threshold tuning

These features enable:
- Accurate garment isolation for texture/color extraction
- Multi-scale pattern recognition
- Content-based similarity search
- Hierarchical visual understanding

**SAM3's "raised texture" capability** works through its semantic understanding of texture terms in text prompts, not by extracting explicit 3D depth maps. For actual texture features, apply traditional CV methods (Gabor/LBP/GLCM) on SAM3-masked regions.
