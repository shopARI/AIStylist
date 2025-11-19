# Lara-Alvarez Color Harmony - Quick Reference

## Quick Start

```python
from lara_alvarez_color_harmony import LaraAlvarezImplementation

harmony = LaraAlvarezImplementation()

# Evaluate harmony of existing colors (LCh format)
colors = [(70, 30, 30), (50, 40, 35), (60, 35, 25)]
result = harmony.evaluate_complete_harmony(colors)
print(f"{result['hue_pattern']}, score: {result['overall_score']:.2f}")

# Generate new harmonic palette
palette = harmony.generate_harmonic_palette(
    base_color=(60, 35, 120),
    n_colors=4,
    hue_pattern='analog',  # or 'opposite', 'triad'
    line_angle=45
)
```

## Color Format - CRITICAL!

**RGB: Use 0.0-1.0 range, NOT 0-255!**
```python
# CORRECT:
harmony.rgb_to_lch(1.0, 0.0, 0.0)  # Pure red

# WRONG:
harmony.rgb_to_lch(255, 0, 0)  # Will fail!
```

**LCh Format:**
- L (Lightness): 0-100
- C (Chroma): 0-100+
- h (Hue): 0-360°

## Main Methods

### 1. Evaluate Existing Colors
```python
result = harmony.evaluate_complete_harmony(colors_lch)

# Returns:
{
    'hue_pattern': 'analog' | 'opposite' | 'triad' | 'no_harmonic',
    'tone_analysis': {'harmonic': bool, ...},
    'overall_score': float,  # 0-1+
    'is_harmonic': bool      # True if score > 0.5
}
```

### 2. Generate Harmonic Palette
```python
palette = harmony.generate_harmonic_palette(
    base_color=(L, C, h),     # LCh tuple
    n_colors=3,               # How many colors
    hue_pattern='analog',     # 'analog', 'opposite', 'triad'
    line_angle=45             # 30-155° (avoid 90°)
)
# Returns: List of LCh tuples
```

### 3. Color Space Conversions
```python
# RGB (0-1) to LCh
lch = harmony.rgb_to_lch(r, g, b)

# LCh to RGB (0-1)
rgb = harmony.lch_to_rgb(L, C, h)

# For 0-255 RGB, divide by 255:
lch = harmony.rgb_to_lch(255/255, 127/255, 0/255)
```

## Harmony Patterns

| Pattern | Hue Relationship | Use Case |
|---------|------------------|----------|
| **Analog** | ~30° apart | Subtle, cohesive looks |
| **Opposite** | ~180° apart | Bold, contrasting outfits |
| **Triad** | ~120° apart | Balanced, vibrant palettes |

## Preferred Line Angles (Tone Harmony)

- **Best**: 30° - 155° in chroma-lightness plane
- **Avoid**: 90° (vertical lines less preferred)
- **Recommended**: 45° (diagonal increase in both C and L)

## Visualization

```python
from lara_alvarez_visualization import LaraAlvarezVisualization

viz = LaraAlvarezVisualization()

# Generate and visualize in one go
palette = viz.generate_harmonic_palette(...)
viz.visualize_complete_analysis(
    palette,
    save_path='my_palette.png'
)
```

Creates PNG with:
- Color swatches
- Hue wheel with uncertainty
- Chroma-lightness plane analysis
- Harmony report

## Parameters You Can Tune

```python
harmony.kh = 15          # Base hue uncertainty (degrees)
harmony.kN = 30          # Neutral color hue uncertainty
harmony.gamma = 10       # Neutral color threshold
harmony.bhattacharyya_threshold = 3  # Harmony threshold
```

## Test Commands

```bash
# Core functionality test
python3 test_harmony.py

# Visualization test (creates PNGs)
python3 test_visualization.py
```

## Common Patterns

### Fashion Outfit Evaluation
```python
# Extract LCh values from garment images
shirt_lch = (70, 35, 220)   # Blue shirt
pants_lch = (40, 30, 225)   # Navy pants
shoes_lch = (60, 20, 30)    # Tan shoes

outfit = [shirt_lch, pants_lch, shoes_lch]
result = harmony.evaluate_complete_harmony(outfit)

if result['is_harmonic']:
    print(f"Great outfit! {result['hue_pattern']} harmony")
else:
    print(f"Score {result['overall_score']:.2f} - might clash")
```

### Suggest Complementary Items
```python
# User has a green jacket
jacket_lch = (60, 40, 120)

# Generate complementary suggestions
for pattern in ['analog', 'opposite', 'triad']:
    palette = harmony.generate_harmonic_palette(
        jacket_lch,
        n_colors=3,
        hue_pattern=pattern
    )
    print(f"{pattern.title()} suggestions: {palette}")
```

## Files in This Directory

| File | Purpose |
|------|---------|
| `lara_alvarez_color_harmony.py` | Core implementation |
| `lara_alvarez_visualization.py` | Visualization extension |
| `README.md` | Full documentation |
| `IMPLEMENTATION_STATUS.md` | Test results and status |
| `QUICK_REFERENCE.md` | This file |
| `test_harmony.py` | Core functionality tests |
| `test_visualization.py` | Visualization tests |

## Library Dependencies (All Installed)

- numpy
- scipy
- matplotlib
- colorsys (built-in)

## Status

✓ **FULLY FUNCTIONAL** - Ready to use, no setup needed
