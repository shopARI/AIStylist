import numpy as np
from scipy import stats
from scipy.spatial.distance import mahalanobis
from typing import List, Tuple, Optional, Dict
import colorsys
import warnings

class LaraAlvarezImplementation:
    """
    Implementation of "A Geometric Approach to Harmonic Color Palette Design"
    by Carlos Lara-Alvarez and Tania Reyes (2017)
    
    This implementation provides:
    - Uncertainty modeling for colors in CIE LCh space
    - Hue harmony evaluation (Algorithm 1)
    - Tone harmony evaluation in chroma-lightness plane (Algorithm 2)
    - Harmonic palette generation (Algorithm 3)
    """
    
    def __init__(self):
        # From paper: normal distributions with σ=15 for tone, σ=30 for hue
        # These are approximations from the paper's formulas
        self.kh = 15  # Base hue standard deviation
        self.kN = 30  # Neutral color hue uncertainty
        self.gamma = 10  # Controls neutral color threshold
        
        # Tone (chroma-lightness) parameters
        self.kc = 2  # Chroma uncertainty multiplier
        self.kL = 2  # Lightness uncertainty multiplier
        
        # Harmony evaluation thresholds
        self.bhattacharyya_threshold = 3  # For both hue and tone harmony
        self.min_tone_distance = 20  # Minimum distance between tones
        
    def rgb_to_lch(self, r: float, g: float, b: float) -> Tuple[float, float, float]:
        """Convert RGB (0-1) to CIE LCh approximation via Lab"""
        # This is a simplified conversion - for production use a proper color library
        # First to XYZ (using sRGB D65 illuminant)
        r, g, b = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 
                   for c in [r, g, b]]
        
        X = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
        Y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
        Z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
        
        # Normalize for D65 illuminant
        X, Y, Z = X / 0.95047, Y / 1.00000, Z / 1.08883
        
        # To Lab
        fx = X**(1/3) if X > 0.008856 else (7.787 * X + 16/116)
        fy = Y**(1/3) if Y > 0.008856 else (7.787 * Y + 16/116)
        fz = Z**(1/3) if Z > 0.008856 else (7.787 * Z + 16/116)
        
        L = 116 * fy - 16
        a = 500 * (fx - fy)
        b_val = 200 * (fy - fz)
        
        # To LCh
        C = np.sqrt(a**2 + b_val**2)
        h = np.degrees(np.arctan2(b_val, a))
        if h < 0:
            h += 360
            
        return L, C, h
    
    def lch_to_rgb(self, L: float, C: float, h: float) -> Tuple[float, float, float]:
        """Convert CIE LCh to RGB (0-1) approximation"""
        # Convert to Lab
        h_rad = np.radians(h)
        a = C * np.cos(h_rad)
        b = C * np.sin(h_rad)
        
        # To XYZ
        fy = (L + 16) / 116
        fx = a / 500 + fy
        fz = fy - b / 200
        
        X = fx**3 if fx**3 > 0.008856 else (fx - 16/116) / 7.787
        Y = fy**3 if fy**3 > 0.008856 else (fy - 16/116) / 7.787
        Z = fz**3 if fz**3 > 0.008856 else (fz - 16/116) / 7.787
        
        # Denormalize
        X, Y, Z = X * 0.95047, Y * 1.00000, Z * 1.08883
        
        # To RGB
        r = X * 3.2404542 - Y * 1.5371385 - Z * 0.4985314
        g = -X * 0.9692660 + Y * 1.8760108 + Z * 0.0415560
        b_val = X * 0.0556434 - Y * 0.2040259 + Z * 1.0572252
        
        # Gamma correction
        rgb = []
        for c in [r, g, b_val]:
            if c > 0.0031308:
                c = 1.055 * (c**(1/2.4)) - 0.055
            else:
                c = 12.92 * c
            rgb.append(max(0, min(1, c)))
            
        return tuple(rgb)
    
    def calculate_hue_variance(self, h: float, c: float) -> float:
        """
        Calculate hue variance based on Equation 1 from the paper
        Neutral colors (low chroma) have higher variance
        """
        # HT term makes hue space more uniform
        HT = (1 - 0.17 * np.cos(np.radians(h - 30)) +
              0.24 * np.cos(np.radians(2 * h)) +
              0.32 * np.cos(np.radians(3 * h + 6)) -
              0.20 * np.cos(np.radians(4 * h - 65)))
        
        # Hue standard deviation increases for neutral colors (low chroma)
        sigma_h = self.kh * (1 + 0.015 * c * HT) + self.kN * (self.gamma**2 / (c**2 + self.gamma**2))
        
        return sigma_h**2
    
    def calculate_tone_covariance(self, L: float, c: float) -> np.ndarray:
        """
        Calculate chroma-lightness covariance matrix (Equation 4)
        """
        SL = 1 + 0.015 * (L - 50)**2 / np.sqrt(20 + (L - 50)**2)
        Sc = 1 + 0.045 * c
        
        cov = np.array([
            [self.kc**2 * Sc**2, 0],
            [0, self.kL**2 * SL**2]
        ])
        
        return cov
    
    def bhattacharyya_distance(self, mean1: np.ndarray, cov1: np.ndarray, 
                               mean2: np.ndarray, cov2: np.ndarray) -> float:
        """Calculate Bhattacharyya distance between two normal distributions"""
        mean_diff = mean1 - mean2
        cov_avg = (cov1 + cov2) / 2
        
        try:
            inv_cov_avg = np.linalg.inv(cov_avg)
            term1 = 0.125 * mean_diff.T @ inv_cov_avg @ mean_diff
            term2 = 0.5 * np.log(np.linalg.det(cov_avg) / 
                                 np.sqrt(np.linalg.det(cov1) * np.linalg.det(cov2)))
            return term1 + term2
        except np.linalg.LinAlgError:
            return float('inf')
    
    def evaluate_hue_harmony(self, colors_lch: List[Tuple[float, float, float]]) -> str:
        """
        Algorithm 1: Evaluating Hue Harmony
        Returns: 'no_harmonic', 'analog', 'opposite', or 'triad'
        """
        if len(colors_lch) < 2:
            return 'no_harmonic'
        
        patterns = {
            1: 'analog',     # Colors close together
            2: 'opposite',   # Colors ~180° apart
            3: 'triad'       # Colors ~120° apart
        }
        
        for pattern_type, pattern_name in patterns.items():
            # Start with first color's hue distribution
            h1, c1 = colors_lch[0][2], colors_lch[0][1]
            var_h1 = self.calculate_hue_variance(h1, c1)
            
            # Accumulated hue and chroma for fusion
            h_acc = h1
            c_acc = c1
            v_acc = 1 / var_h1  # precision (inverse variance)
            
            harmonious = True
            
            for i in range(1, len(colors_lch)):
                hi, ci = colors_lch[i][2], colors_lch[i][1]
                var_hi = self.calculate_hue_variance(hi, ci)
                
                # Check if this color is harmonious with accumulated pattern
                if pattern_type == 1:  # Analog - should be close
                    angle_diff = min(abs(hi - h_acc), 360 - abs(hi - h_acc))
                    if angle_diff > 30:  # Threshold for analog colors
                        harmonious = False
                        break
                        
                elif pattern_type == 2:  # Opposite
                    expected_angle = (h_acc + 180) % 360
                    angle_diff = min(abs(hi - expected_angle), 360 - abs(hi - expected_angle))
                    if angle_diff > 30:
                        harmonious = False
                        break
                        
                elif pattern_type == 3:  # Triad
                    # Check if it's ~120° or ~240° from first color
                    expected1 = (h1 + 120) % 360
                    expected2 = (h1 + 240) % 360
                    diff1 = min(abs(hi - expected1), 360 - abs(hi - expected1))
                    diff2 = min(abs(hi - expected2), 360 - abs(hi - expected2))
                    if min(diff1, diff2) > 30:
                        harmonious = False
                        break
                
                # Fuse distributions (Equation 6)
                vi = 1 / var_hi
                h_acc = (v_acc * h_acc + vi * hi) / (v_acc + vi)
                c_acc = (v_acc * c_acc + vi * ci) / (v_acc + vi)
                v_acc = v_acc + vi
            
            if harmonious:
                return pattern_name
        
        return 'no_harmonic'
    
    def fit_line_to_tones(self, tones: List[Tuple[float, float]], 
                          weights: Optional[List[float]] = None) -> Tuple[float, float]:
        """
        Fit a line to tone points using weighted least squares (Equation 8)
        Returns (r, phi) in polar form where r is distance to origin and phi is angle
        """
        if len(tones) < 2:
            raise ValueError("Need at least 2 points to fit a line")
        
        tones = np.array(tones)
        c_values = tones[:, 0]
        L_values = tones[:, 1]
        
        if weights is None:
            weights = np.ones(len(tones))
        weights = np.array(weights)
        
        # Weighted means
        c_mean = np.sum(weights * c_values) / np.sum(weights)
        L_mean = np.sum(weights * L_values) / np.sum(weights)
        
        # Calculate angle phi (Equation 8)
        numerator = -2 * np.sum(weights * (L_values - L_mean) * (c_values - c_mean))
        denominator = np.sum(weights * ((L_values - L_mean)**2 - (c_values - c_mean)**2))
        
        if abs(denominator) < 1e-10:
            phi = np.pi / 2 if numerator > 0 else -np.pi / 2
        else:
            phi = 0.5 * np.arctan2(numerator, denominator)
        
        # Calculate r
        r = c_mean * np.cos(phi) + L_mean * np.sin(phi)
        
        return r, phi
    
    def point_to_line_distance(self, point: Tuple[float, float], 
                               r: float, phi: float) -> float:
        """Calculate perpendicular distance from point to line"""
        c, L = point
        return abs(r - c * np.cos(phi) - L * np.sin(phi))
    
    def evaluate_line_harmony(self, colors_lch: List[Tuple[float, float, float]], 
                             tolerance: float = 10.0) -> Dict:
        """
        Algorithm 2: Evaluating tone harmony in chroma-lightness plane
        Returns dictionary with harmony status and line parameters if applicable
        """
        if len(colors_lch) < 2:
            return {'harmonic': True, 'type': 'single_point'}
        
        # Extract tones (chroma, lightness)
        tones = [(c, L) for L, c, h in colors_lch]
        
        # Check non-ambiguous condition (Equation 7)
        for i in range(len(tones)):
            for j in range(i + 1, len(tones)):
                ti = np.array(tones[i])
                tj = np.array(tones[j])
                
                # Calculate covariances
                Li, ci = colors_lch[i][0], colors_lch[i][1]
                Lj, cj = colors_lch[j][0], colors_lch[j][1]
                cov_i = self.calculate_tone_covariance(Li, ci)
                cov_j = self.calculate_tone_covariance(Lj, cj)
                
                # Bhattacharyya distance
                dist = self.bhattacharyya_distance(ti, cov_i, tj, cov_j)
                
                if dist < self.bhattacharyya_threshold:
                    return {'harmonic': False, 'reason': 'ambiguous_tones', 
                           'problem_indices': (i, j)}
        
        # Fit line to tones
        try:
            r, phi = self.fit_line_to_tones(tones)
        except:
            return {'harmonic': False, 'reason': 'cannot_fit_line'}
        
        # Check if all points follow the line (within tolerance)
        max_distance = 0
        for tone in tones:
            dist = self.point_to_line_distance(tone, r, phi)
            max_distance = max(max_distance, dist)
            if dist > tolerance:
                return {'harmonic': False, 'reason': 'non_linear', 
                       'max_distance': dist}
        
        # Convert phi to degrees for interpretation
        phi_degrees = np.degrees(phi)
        
        # According to the paper, certain angles are preferred
        # Lines between 30° and 155° are more harmonic
        preference_score = 1.0
        if 30 <= abs(phi_degrees) <= 155:
            preference_score = 1.5
        elif abs(phi_degrees) == 90:  # Vertical lines less preferred
            preference_score = 0.7
        
        return {
            'harmonic': True,
            'type': 'linear',
            'line_params': {'r': r, 'phi': phi_degrees},
            'max_deviation': max_distance,
            'preference_score': preference_score
        }
    
    def generate_harmonic_palette(self, base_color_lch: Tuple[float, float, float],
                                  n_colors: int = 3, 
                                  hue_pattern: str = 'analog',
                                  line_angle: Optional[float] = None) -> List[Tuple[float, float, float]]:
        """
        Algorithm 3 (adapted): Generate harmonic palette
        
        Args:
            base_color_lch: Starting color in LCh format
            n_colors: Number of colors to generate
            hue_pattern: 'analog', 'opposite', 'triad', or 'random'
            line_angle: Angle for line in chroma-lightness plane (degrees)
        
        Returns:
            List of colors in LCh format
        """
        L0, c0, h0 = base_color_lch
        colors = [base_color_lch]
        
        # Generate hue values based on pattern
        hues = [h0]
        if hue_pattern == 'analog':
            # Spread colors within 30 degrees
            if n_colors > 1:
                step = 30 / (n_colors - 1)
                for i in range(1, n_colors):
                    hues.append((h0 + i * step) % 360)
                    
        elif hue_pattern == 'opposite' and n_colors == 2:
            hues.append((h0 + 180) % 360)
            
        elif hue_pattern == 'triad' and n_colors == 3:
            hues.append((h0 + 120) % 360)
            hues.append((h0 + 240) % 360)
            
        else:  # Random or unsupported pattern
            for i in range(1, n_colors):
                hues.append(np.random.uniform(0, 360))
        
        # Generate points along a line in chroma-lightness plane
        if line_angle is None:
            # Use a preferred angle (e.g., 45 degrees)
            line_angle = 45
        
        phi_rad = np.radians(line_angle)
        
        # Generate points along the line
        # Start from base tone and move along line
        base_tone = np.array([c0, L0])
        direction = np.array([np.cos(phi_rad), np.sin(phi_rad)])
        
        # Ensure minimum distance between points
        step_size = self.min_tone_distance
        
        for i in range(1, n_colors):
            # Move along line
            t = i * step_size
            new_tone = base_tone + t * direction
            
            # Clip to valid ranges
            new_c = np.clip(new_tone[0], 0, 100)
            new_L = np.clip(new_tone[1], 0, 100)
            
            # Add some controlled randomness (uncertainty)
            cov = self.calculate_tone_covariance(new_L, new_c)
            noise = np.random.multivariate_normal([0, 0], cov * 0.1)
            new_c = np.clip(new_c + noise[0], 0, 100)
            new_L = np.clip(new_L + noise[1], 0, 100)
            
            colors.append((new_L, new_c, hues[i]))
        
        return colors
    
    def evaluate_complete_harmony(self, colors_lch: List[Tuple[float, float, float]]) -> Dict:
        """
        Complete harmony evaluation combining hue and tone harmony
        """
        hue_harmony = self.evaluate_hue_harmony(colors_lch)
        tone_harmony = self.evaluate_line_harmony(colors_lch)
        
        # Calculate overall harmony score
        score = 0
        if hue_harmony != 'no_harmonic':
            score += 0.5
            if hue_harmony == 'analog':
                score += 0.1  # Analog slightly preferred per paper
        
        if tone_harmony['harmonic']:
            score += 0.5 * tone_harmony.get('preference_score', 1.0)
        
        return {
            'hue_pattern': hue_harmony,
            'tone_analysis': tone_harmony,
            'overall_score': score,
            'is_harmonic': score > 0.5
        }
    
    def visualize_palette(self, colors_lch: List[Tuple[float, float, float]]):
        """Create a simple text visualization of the palette"""
        print("\n" + "="*60)
        print("COLOR PALETTE ANALYSIS")
        print("="*60)
        
        # Display colors
        print("\nColors (LCh format):")
        for i, (L, c, h) in enumerate(colors_lch, 1):
            rgb = self.lch_to_rgb(L, c, h)
            hex_color = '#{:02x}{:02x}{:02x}'.format(
                int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)
            )
            print(f"  Color {i}: L={L:.1f}, C={c:.1f}, h={h:.1f}° | {hex_color}")
        
        # Evaluate harmony
        result = self.evaluate_complete_harmony(colors_lch)
        
        print(f"\nHue Pattern: {result['hue_pattern']}")
        print(f"Tone Harmony: {'Yes' if result['tone_analysis']['harmonic'] else 'No'}")
        
        if result['tone_analysis']['harmonic'] and 'line_params' in result['tone_analysis']:
            params = result['tone_analysis']['line_params']
            print(f"  Line angle: {params['phi']:.1f}°")
            print(f"  Max deviation: {result['tone_analysis']['max_deviation']:.2f}")
        
        print(f"\nOverall Harmony Score: {result['overall_score']:.2f}/1.0")
        print(f"Is Harmonic: {'YES' if result['is_harmonic'] else 'NO'}")
        print("="*60)


# Example usage
if __name__ == "__main__":
    # Initialize the implementation
    harmony_system = LaraAlvarezImplementation()
    
    # Example 1: Evaluate existing palette
    print("\n--- Example 1: Evaluating an existing palette ---")
    
    # Define some colors in LCh (you can convert from RGB)
    test_palette = [
        (70, 30, 30),   # Light, moderate chroma, red-orange
        (50, 40, 35),   # Medium lightness, higher chroma, similar hue
        (30, 45, 40),   # Dark, high chroma, slightly shifted hue
    ]
    
    harmony_system.visualize_palette(test_palette)
    
    # Example 2: Generate harmonic palette
    print("\n--- Example 2: Generating harmonic palettes ---")
    
    # Starting from a base color
    base_color = (60, 35, 120)  # Medium lightness, moderate chroma, green
    
    # Generate analog palette
    analog_palette = harmony_system.generate_harmonic_palette(
        base_color, n_colors=3, hue_pattern='analog', line_angle=45
    )
    print("\nAnalog Palette:")
    harmony_system.visualize_palette(analog_palette)
    
    # Generate triad palette
    triad_palette = harmony_system.generate_harmonic_palette(
        base_color, n_colors=3, hue_pattern='triad', line_angle=60
    )
    print("\nTriad Palette:")
    harmony_system.visualize_palette(triad_palette)
    
    # Example 3: Test non-harmonic palette
    print("\n--- Example 3: Non-harmonic palette (for comparison) ---")
    
    non_harmonic = [
        (70, 30, 30),   
        (68, 32, 35),   # Too similar to first (ambiguous)
        (20, 80, 200),  # Doesn't follow line pattern
    ]
    
    harmony_system.visualize_palette(non_harmonic)
