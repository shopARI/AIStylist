#!/usr/bin/env python3
"""
Quick SAM3 test - minimal example for single image segmentation
"""

import torch
from PIL import Image
import requests
from io import BytesIO
from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor

# Load model
print("Loading SAM3...")
model = build_sam3_image_model()
processor = Sam3Processor(model)
print("✓ Model loaded")

# Load a test image (cats on couch from COCO dataset)
image_url = "http://images.cocodataset.org/val2017/000000039769.jpg"
image = Image.open(BytesIO(requests.get(image_url).content))
print(f"✓ Image loaded: {image.size}")

# Segment with text prompt
text_prompt = "cat"
print(f"✓ Segmenting: '{text_prompt}'")

# Step 1: Set image
inference_state = processor.set_image(image)

# Step 2: Set text prompt
output = processor.set_text_prompt(state=inference_state, prompt=text_prompt)

# Step 3: Extract results
masks, boxes, scores = output["masks"], output["boxes"], output["scores"]

print(f"✓ Found {len(masks)} masks")
print(f"✓ Scores: {scores}")

print("\n✓ SAM3 is working correctly!")
