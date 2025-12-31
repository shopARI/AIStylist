# Color Harmony Implementation - Lara-Alvarez Method

## Overview
Complete implementation of the paper "A Geometric Approach to Harmonic Color Palette Design" by Carlos Lara-Alvarez and Tania Reyes (2017). This implementation provides algorithms for evaluating and generating harmonic color palettes using uncertainty modeling and geometric patterns in CIE L*C*h color space.

## Key Features

### 1. **Uncertainty Modeling**
- Colors are represented with normal distributions to model uncertainty
- Neutral colors (low chroma) have higher hue uncertainty
- Tone (chroma-lightness) uncertainty follows CIE ΔE2000 formula

### 2. **Hue Harmony Patterns**
The system recognizes three main hue patterns:
- **Analog**: Colors within ~30° on the hue wheel
- **Opposite**: Colors ~180° apart
- **Triad**: Colors ~120° apart

### 3. **Tone Harmony (Chroma-Lightness Plane)**
- Harmonic colors follow linear patterns in the chroma-lightness plane
- Non-ambiguous condition: colors must be sufficiently different (Bhattacharyya distance ≥ 3)
- Preferred line angles: 30° to 155° (excluding 90°)

## Implementation Files

### `lara_alvarez_color_harmony.py`
Core implementation with:
- **Algorithm 1**: Hue harmony evaluation
- **Algorithm 2**: Line harmony evaluation in chroma-lightness plane  
- **Algorithm 3**: Harmonic palette generation
- Color space conversions (RGB ↔ LCh)
- Uncertainty calculations

### `lara_alvarez_visualization.py`
Extended implementation with visualization:
- Hue wheel plots with uncertainty regions
- Chroma-lightness plane analysis
- Color swatch displays
- Complete harmony analysis reports

## Usage Examples

### Basic Usage
```python
from lara_alvarez_color_harmony import LaraAlvarezImplementation

# Initialize
harmony = LaraAlvarezImplementation()

# Define colors in LCh format (Lightness, Chroma, Hue)
colors = [
    (70, 30, 30),   # Light, moderate chroma, red-orange
    (50, 40, 35),   # Medium lightness, higher chroma
    (30, 50, 40),   # Dark, high chroma
]

# Evaluate harmony
result = harmony.evaluate_complete_harmony(colors)
print(f"Hue Pattern: {result['hue_pattern']}")
print(f"Overall Score: {result['overall_score']:.2f}/1.0")
```

### Generate Harmonic Palette
```python
# Start with a base color
base_color = (60, 35, 120)  # Medium lightness, moderate chroma, green

# Generate analog palette with preferred line angle
palette = harmony.generate_harmonic_palette(
    base_color, 
    n_colors=3, 
    hue_pattern='analog',  # or 'opposite', 'triad'
    line_angle=45  # Degrees in chroma-lightness plane
)

# Visualize results
harmony.visualize_palette(palette)
```

### Advanced Visualization
```python
from lara_alvarez_visualization import LaraAlvarezVisualization

viz = LaraAlvarezVisualization()

# Create complete analysis with plots
viz.visualize_complete_analysis(
    colors, 
    save_path='harmony_analysis.png'
)
```

## Key Algorithms

### Algorithm 1: Hue Harmony Evaluation
1. Calculate hue uncertainty for each color based on chroma
2. Check if colors follow analog, opposite, or triad patterns
3. Use Bhattacharyya distance to evaluate pattern fit
4. Fuse distributions incrementally for multi-color palettes

### Algorithm 2: Line Harmony Evaluation  
1. Check non-ambiguous condition (sufficient color difference)
2. Fit weighted least-squares line to tone points
3. Calculate perpendicular distance of each point to line
4. Points within tolerance are considered harmonic
5. Certain line angles are preferred (30°-155°, excluding 90°)

### Algorithm 3: Palette Generation
1. Start with base color and desired pattern
2. Generate hue values following selected pattern
3. Create points along line in chroma-lightness plane
4. Ensure minimum distance between colors
5. Add controlled uncertainty for natural variation

## Parameters

### Adjustable Settings
```python
harmony.kh = 15          # Base hue standard deviation
harmony.kN = 30          # Neutral color hue uncertainty  
harmony.gamma = 10       # Neutral color threshold
harmony.kc = 2           # Chroma uncertainty multiplier
harmony.kL = 2           # Lightness uncertainty multiplier
harmony.bhattacharyya_threshold = 3  # Harmony threshold
harmony.min_tone_distance = 20       # Min distance between colors
```

## Color Space Notes

### CIE L*C*h Format
- **L (Lightness)**: 0-100 (black to white)
- **C (Chroma)**: 0-100 (gray to vivid)
- **h (Hue)**: 0-360° angle on color wheel

### Conversion Functions
The implementation includes approximate RGB ↔ LCh conversions. For production use, consider using a proper color library like `colorspacious` or `colour-science`.

## Experimental Results (from Paper)

The paper's experiments showed:
1. **Non-ambiguous condition is mandatory** for harmony
2. **Linear patterns outperform non-linear** arrangements
3. **Preferred line angles**: 30° to 155° (excluding 90°)
4. **Hue pattern preferences**: Analog > Opposite > Triad
5. **Vertical lines (90°) are less preferred**

## Applications

This implementation is suitable for:
- **Fashion & Apparel**: Coordinating outfit colors
- **Interior Design**: Room color schemes
- **UI/UX Design**: Interface color palettes
- **Brand Design**: Logo and marketing materials
- **Data Visualization**: Chart color schemes
- **Art & Creative**: Painting and digital art palettes

## Example Outputs

The implementation generates four example visualizations:

1. **harmony_palette1.png**: Analog harmony example
2. **harmony_palette2.png**: Triad harmony example
3. **harmony_palette3.png**: Non-harmonic example (for comparison)
4. **harmony_generated.png**: Algorithmically generated optimal palette

Each visualization includes:
- Color swatches with hex codes
- Hue wheel with uncertainty regions
- Chroma-lightness plane with fitted line
- Complete harmony analysis report

## Integration with ARI Fashion System

For integration with your ARI fashion recommendation system:

```python
class ARIColorHarmony:
    def __init__(self):
        self.harmony_evaluator = LaraAlvarezImplementation()
    
    def evaluate_outfit_harmony(self, garment_colors):
        """Evaluate color harmony of outfit combination"""
        # Convert garment colors to LCh
        lch_colors = [self.rgb_to_lch(r, g, b) for r, g, b in garment_colors]
        
        # Get harmony score
        result = self.harmony_evaluator.evaluate_complete_harmony(lch_colors)
        
        return {
            'harmony_score': result['overall_score'],
            'is_harmonic': result['is_harmonic'],
            'pattern_type': result['hue_pattern'],
            'recommendations': self.get_recommendations(result)
        }
    
    def suggest_complementary_colors(self, base_garment_color):
        """Suggest colors that would be harmonic with base"""
        base_lch = self.rgb_to_lch(*base_garment_color)
        
        suggestions = []
        for pattern in ['analog', 'opposite', 'triad']:
            palette = self.harmony_evaluator.generate_harmonic_palette(
                base_lch, n_colors=3, hue_pattern=pattern, line_angle=45
            )
            suggestions.append({
                'pattern': pattern,
                'colors': [self.lch_to_rgb(*color) for color in palette]
            })
        
        return suggestions
```

## Future Enhancements

Potential improvements:
1. **Machine Learning Integration**: Train on user preferences
2. **Context-Aware Palettes**: Season, occasion, personal style
3. **Texture & Pattern**: Consider fabric textures alongside color
4. **Multi-Modal Harmony**: Include shape, style elements
5. **Real-Time Feedback**: Interactive palette adjustment
6. **Color Trends**: Incorporate fashion trend data

## References

Lara-Alvarez, C., & Reyes, T. (2017). A Geometric Approach to Harmonic Color Palette Design. arXiv:1709.02252 [cs.CV]

## License

This implementation is provided for educational and research purposes.
