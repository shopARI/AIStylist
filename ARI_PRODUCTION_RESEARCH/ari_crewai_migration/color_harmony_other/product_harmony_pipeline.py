"""
Complete Product Color Harmony Pipeline

Integrates:
1. Garment color extraction (garment_color_extractor.py)
2. Color harmony analysis (lara_alvarez_color_harmony.py)
3. Neo4j product database integration

Pipeline: Product Image URL → Segment → Extract Colors → Convert to LCh → Harmony Analysis
"""

import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from garment_color_extractor import GarmentColorExtractor
from lara_alvarez_color_harmony import LaraAlvarezImplementation


class ProductHarmonyPipeline:
    """
    End-to-end pipeline for analyzing color harmony of fashion products.
    """

    def __init__(self, sam2_checkpoint: Optional[str] = None, device: str = "cuda"):
        """
        Initialize pipeline with SAM2 segmentation.

        Args:
            sam2_checkpoint: Optional path to SAM2 checkpoint
            device: 'cuda' or 'cpu'
        """
        self.color_extractor = GarmentColorExtractor(sam2_checkpoint=sam2_checkpoint, device=device)
        self.harmony_analyzer = LaraAlvarezImplementation()

    def rgb_to_lch(self, rgb_tuple: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """
        Convert RGB (0-255) to LCh format.

        Args:
            rgb_tuple: RGB values in 0-255 range

        Returns:
            LCh tuple (L, C, h)
        """
        r, g, b = rgb_tuple
        # Convert to 0-1 range for harmony analyzer
        return self.harmony_analyzer.rgb_to_lch(r/255, g/255, b/255)

    def lch_to_rgb(self, lch_tuple: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """
        Convert LCh to RGB (0-255).

        Args:
            lch_tuple: LCh values

        Returns:
            RGB tuple in 0-255 range
        """
        L, C, h = lch_tuple
        rgb_01 = self.harmony_analyzer.lch_to_rgb(L, C, h)
        return tuple(int(c * 255) for c in rgb_01)

    def analyze_single_product(
        self,
        image_source: str,
        n_colors: int = 3,
        is_url: bool = False,
        visualize: bool = False,
        save_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze color harmony of a single product.

        Args:
            image_source: File path or URL to product image
            n_colors: Number of dominant colors to extract
            is_url: True if image_source is a URL
            visualize: Whether to create visualization
            save_path: Path to save visualization

        Returns:
            Dictionary with analysis results
        """
        # Step 1: Extract colors from garment
        try:
            rgb_colors, image, mask = self.color_extractor.process_image(
                image_source, n_colors=n_colors, is_url=is_url
            )
        except Exception as e:
            return {
                'error': f'Failed to extract colors: {str(e)}',
                'success': False
            }

        if not rgb_colors:
            return {
                'error': 'No colors extracted from image',
                'success': False
            }

        # Step 2: Convert to LCh
        lch_colors = [self.rgb_to_lch(rgb) for rgb in rgb_colors]

        # Step 3: Analyze harmony
        harmony_result = self.harmony_analyzer.evaluate_complete_harmony(lch_colors)

        # Step 4: Compile results
        result = {
            'success': True,
            'rgb_colors': rgb_colors,
            'lch_colors': lch_colors,
            'hue_pattern': harmony_result['hue_pattern'],
            'tone_harmonic': harmony_result['tone_analysis']['harmonic'],
            'overall_score': harmony_result['overall_score'],
            'is_harmonic': harmony_result['is_harmonic'],
            'full_harmony_analysis': harmony_result
        }

        # Step 5: Visualize if requested
        if visualize:
            self.color_extractor.visualize_extraction(image, mask, rgb_colors, save_path)

        return result

    def analyze_outfit_harmony(
        self,
        product_images: List[str],
        n_colors_per_item: int = 2,
        are_urls: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze color harmony of a complete outfit (multiple products).

        Args:
            product_images: List of image paths/URLs
            n_colors_per_item: Number of dominant colors to extract per item
            are_urls: True if product_images are URLs

        Returns:
            Dictionary with outfit harmony analysis
        """
        all_rgb_colors = []
        all_lch_colors = []
        per_item_results = []

        # Extract colors from each item
        for i, image_source in enumerate(product_images, 1):
            try:
                rgb_colors, _, _ = self.color_extractor.process_image(
                    image_source, n_colors=n_colors_per_item, is_url=are_urls
                )

                if rgb_colors:
                    lch_colors = [self.rgb_to_lch(rgb) for rgb in rgb_colors]
                    all_rgb_colors.extend(rgb_colors)
                    all_lch_colors.extend(lch_colors)

                    per_item_results.append({
                        'item': i,
                        'colors': rgb_colors,
                        'success': True
                    })
                else:
                    per_item_results.append({
                        'item': i,
                        'error': 'No colors extracted',
                        'success': False
                    })
            except Exception as e:
                per_item_results.append({
                    'item': i,
                    'error': str(e),
                    'success': False
                })

        if not all_lch_colors:
            return {
                'error': 'No colors extracted from any item',
                'success': False,
                'per_item_results': per_item_results
            }

        # Analyze overall outfit harmony
        harmony_result = self.harmony_analyzer.evaluate_complete_harmony(all_lch_colors)

        return {
            'success': True,
            'n_items': len(product_images),
            'n_colors_extracted': len(all_lch_colors),
            'outfit_rgb_colors': all_rgb_colors,
            'outfit_lch_colors': all_lch_colors,
            'hue_pattern': harmony_result['hue_pattern'],
            'tone_harmonic': harmony_result['tone_analysis']['harmonic'],
            'overall_score': harmony_result['overall_score'],
            'is_harmonic': harmony_result['is_harmonic'],
            'per_item_results': per_item_results,
            'full_harmony_analysis': harmony_result
        }

    def suggest_complementary_colors(
        self,
        base_color_rgb: Tuple[int, int, int],
        hue_pattern: str = 'analog',
        n_suggestions: int = 3
    ) -> List[Tuple[int, int, int]]:
        """
        Suggest complementary colors based on a base garment color.

        Args:
            base_color_rgb: Base color in RGB (0-255)
            hue_pattern: 'analog', 'opposite', or 'triad'
            n_suggestions: Number of suggestions to generate

        Returns:
            List of suggested RGB colors
        """
        # Convert to LCh
        base_lch = self.rgb_to_lch(base_color_rgb)

        # Generate harmonic palette
        palette_lch = self.harmony_analyzer.generate_harmonic_palette(
            base_color_lch=base_lch,
            n_colors=n_suggestions,
            hue_pattern=hue_pattern,
            line_angle=45  # Default preferred angle
        )

        # Convert back to RGB
        suggested_colors = [self.lch_to_rgb(lch) for lch in palette_lch]

        return suggested_colors

    def print_analysis_report(self, result: Dict[str, Any], title: str = "Color Harmony Analysis"):
        """
        Print a formatted analysis report.

        Args:
            result: Analysis result dictionary
            title: Report title
        """
        print("\n" + "="*60)
        print(f"{title}")
        print("="*60)

        if not result.get('success', False):
            print(f"\nERROR: {result.get('error', 'Unknown error')}")
            return

        print(f"\nExtracted Colors ({len(result.get('rgb_colors', []))}):")
        for i, rgb in enumerate(result.get('rgb_colors', []), 1):
            lch = result.get('lch_colors', [])[i-1] if i <= len(result.get('lch_colors', [])) else None
            print(f"  Color {i}: RGB{rgb}", end="")
            if lch:
                print(f" | LCh(L={lch[0]:.1f}, C={lch[1]:.1f}, h={lch[2]:.1f}°)")
            else:
                print()

        print(f"\nHarmony Analysis:")
        print(f"  Hue Pattern: {result.get('hue_pattern', 'N/A')}")
        print(f"  Tone Harmonic: {result.get('tone_harmonic', 'N/A')}")
        print(f"  Overall Score: {result.get('overall_score', 0):.2f}/1.0")
        print(f"  Is Harmonic: {'[OK] Yes' if result.get('is_harmonic', False) else '[NO]'}")

        print("="*60 + "\n")


# Example usage and testing
if __name__ == "__main__":
    import sys

    # Initialize pipeline with SAM2
    pipeline = ProductHarmonyPipeline()

    print("Product Color Harmony Pipeline - Test Mode")
    print("="*60)

    # Test 1: Single product analysis
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        is_url = image_path.startswith('http')

        print(f"\n[Test 1] Analyzing single product: {image_path}")
        result = pipeline.analyze_single_product(
            image_path,
            n_colors=3,
            is_url=is_url,
            visualize=True,
            save_path='single_product_analysis.png'
        )
        pipeline.print_analysis_report(result, "Single Product Analysis")

        # Test 2: Suggest complementary colors
        if result['success'] and result['rgb_colors']:
            base_color = result['rgb_colors'][0]
            print(f"\n[Test 2] Suggesting complementary colors for RGB{base_color}")

            for pattern in ['analog', 'opposite', 'triad']:
                suggestions = pipeline.suggest_complementary_colors(
                    base_color,
                    hue_pattern=pattern,
                    n_suggestions=3
                )
                print(f"\n  {pattern.title()} suggestions:")
                for i, color in enumerate(suggestions, 1):
                    print(f"    {i}. RGB{color}")
    else:
        print("\nUsage: python product_harmony_pipeline.py <image_path_or_url>")
        print("\nExample:")
        print("  python product_harmony_pipeline.py product.jpg")
        print("  python product_harmony_pipeline.py https://example.com/product.jpg")
