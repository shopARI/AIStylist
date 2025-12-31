#!/usr/bin/env python3
"""
SAM3 Image Segmentation Example
Demonstrates how to use SAM3 for single image segmentation with text prompts
"""

import torch
from transformers import Sam3Model, Sam3Processor
from PIL import Image
import numpy as np
import requests
from io import BytesIO

def load_model():
    """Load SAM3 model and processor"""
    print("Loading SAM3 model...")
    model = Sam3Model.from_pretrained("facebook/sam3", device_map="auto")
    processor = Sam3Processor.from_pretrained("facebook/sam3")
    print("Model loaded successfully!")
    return model, processor

def segment_image_with_text(image_path, text_prompt, model, processor):
    """
    Segment objects in an image using a text prompt

    Args:
        image_path: Path to image file or URL
        text_prompt: Text description of what to segment (e.g., "person", "cat", "car")
        model: SAM3 model
        processor: SAM3 processor

    Returns:
        masks: Segmentation masks
        scores: Confidence scores for each mask
    """
    # Load image
    if image_path.startswith('http'):
        response = requests.get(image_path)
        image = Image.open(BytesIO(response.content))
    else:
        image = Image.open(image_path)

    print(f"Image size: {image.size}")
    print(f"Segmenting: '{text_prompt}'")

    # Prepare inputs
    inputs = processor(image, text=[text_prompt], return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    # Run inference
    with torch.no_grad():
        outputs = model(**inputs)

    # Post-process to get masks
    masks = processor.post_process_masks(
        outputs.pred_masks,
        inputs["original_sizes"],
        inputs["reshaped_input_sizes"]
    )

    # Get scores
    scores = outputs.iou_scores

    return masks, scores

def segment_image_with_boxes(image_path, boxes, model, processor):
    """
    Segment objects in an image using bounding boxes

    Args:
        image_path: Path to image file or URL
        boxes: List of bounding boxes [[x1, y1, x2, y2], ...]
        model: SAM3 model
        processor: SAM3 processor

    Returns:
        masks: Segmentation masks
        scores: Confidence scores for each mask
    """
    # Load image
    if image_path.startswith('http'):
        response = requests.get(image_path)
        image = Image.open(BytesIO(response.content))
    else:
        image = Image.open(image_path)

    print(f"Image size: {image.size}")
    print(f"Segmenting {len(boxes)} bounding boxes")

    # Prepare inputs with boxes
    inputs = processor(image, input_boxes=[boxes], return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    # Run inference
    with torch.no_grad():
        outputs = model(**inputs)

    # Post-process to get masks
    masks = processor.post_process_masks(
        outputs.pred_masks,
        inputs["original_sizes"],
        inputs["reshaped_input_sizes"]
    )

    # Get scores
    scores = outputs.iou_scores

    return masks, scores

def visualize_masks(image_path, masks, scores, output_path="output_segmentation.png"):
    """
    Visualize segmentation masks overlaid on the original image

    Args:
        image_path: Path to original image
        masks: Segmentation masks
        scores: Confidence scores
        output_path: Path to save output image
    """
    import matplotlib.pyplot as plt

    # Load original image
    if image_path.startswith('http'):
        response = requests.get(image_path)
        image = Image.open(BytesIO(response.content))
    else:
        image = Image.open(image_path)

    # Convert to numpy
    image_np = np.array(image)

    # Get first batch of masks
    masks_np = masks[0].cpu().numpy()
    scores_np = scores[0].cpu().numpy()

    # Create figure
    fig, axes = plt.subplots(1, min(3, len(masks_np)), figsize=(15, 5))
    if len(masks_np) == 1:
        axes = [axes]

    for idx, (mask, score) in enumerate(zip(masks_np[:3], scores_np[:3])):
        ax = axes[idx] if idx < len(axes) else None
        if ax is None:
            break

        # Overlay mask on image
        ax.imshow(image_np)
        ax.imshow(mask, alpha=0.5, cmap='jet')
        ax.set_title(f'Mask {idx+1} (Score: {score:.3f})')
        ax.axis('off')

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=150)
    print(f"Visualization saved to: {output_path}")
    plt.close()

# Example usage
if __name__ == "__main__":
    # Load model (only needs to be done once)
    model, processor = load_model()

    # Example 1: Segment with text prompt
    print("\n" + "="*60)
    print("Example 1: Text-based segmentation")
    print("="*60)

    # Use a sample image URL
    image_url = "http://images.cocodataset.org/val2017/000000039769.jpg"  # cats on couch

    # Segment with text prompt
    masks, scores = segment_image_with_text(
        image_url,
        "cat",
        model,
        processor
    )

    print(f"Found {len(masks[0])} masks")
    print(f"Scores: {scores[0].cpu().numpy()}")

    # Visualize results
    visualize_masks(image_url, masks, scores, "sam3_text_segmentation.png")

    # Example 2: Segment with bounding boxes
    print("\n" + "="*60)
    print("Example 2: Box-based segmentation")
    print("="*60)

    # Define bounding boxes [x1, y1, x2, y2]
    # These coordinates should match objects in your image
    boxes = [[50, 50, 200, 200]]  # Example box

    masks, scores = segment_image_with_boxes(
        image_url,
        boxes,
        model,
        processor
    )

    print(f"Found {len(masks[0])} masks")
    print(f"Scores: {scores[0].cpu().numpy()}")

    visualize_masks(image_url, masks, scores, "sam3_box_segmentation.png")

    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)
