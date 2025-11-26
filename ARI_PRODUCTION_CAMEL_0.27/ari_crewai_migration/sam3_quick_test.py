#!/usr/bin/env python3
"""
Quick SAM3 test - minimal example for single image segmentation
"""

import torch
from transformers import Sam3Model, Sam3Processor
from PIL import Image
import requests
from io import BytesIO

# Load model
print("Loading SAM3...")
model = Sam3Model.from_pretrained("facebook/sam3", device_map="auto")
processor = Sam3Processor.from_pretrained("facebook/sam3")
print("✓ Model loaded")

# Load a test image (cats on couch from COCO dataset)
image_url = "http://images.cocodataset.org/val2017/000000039769.jpg"
image = Image.open(BytesIO(requests.get(image_url).content))
print(f"✓ Image loaded: {image.size}")

# Segment with text prompt
text_prompt = "cat"
print(f"✓ Segmenting: '{text_prompt}'")

inputs = processor(image, text=[text_prompt], return_tensors="pt")
inputs = {k: v.to(model.device) for k, v in inputs.items()}

with torch.no_grad():
    outputs = model(**inputs)

masks = processor.post_process_masks(
    outputs.pred_masks,
    inputs["original_sizes"],
    inputs["reshaped_input_sizes"]
)

print(f"✓ Found {len(masks[0])} masks")
print(f"✓ Scores: {outputs.iou_scores[0].cpu().numpy()}")
print("\n✓ SAM3 is working correctly!")
