"""
Improved Lara-Alvarez Color Harmony Implementation v2.0
Addresses issues identified in code review:
- Better error handling
- Input validation  
- Performance optimizations
- Clearer algorithm implementation
- Reduced magic numbers
"""

import numpy as np
from scipy import stats
from scipy.spatial.distance import mahalanobis
from typing import List, Tuple, Optional, Dict, Union
from functools import lru_cache
from dataclasses import dataclass
import logging
import warnings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class HarmonyConfig:
    """Configuration parameters for harmony evaluation"""
    # Hue parameters
    kh: float = 15  # Base hue standard deviation
    kN: float = 30  # Neutral color hue uncertainty
    gamma: float = 10  # Controls neutral color threshold
    
    # Tone parameters  
    kc: float = 2  # Chroma uncertainty multiplier
    kL: float = 2  # Lightness uncertainty multiplier
    
    # Harmony thresholds
    bhattacharyya_threshold: float = 3
    min_tone_distance: float = 20
    line_tolerance: float = 10.0
    
    # Pattern thresholds
    analog_angle_threshold: float = 30
    opposite_angle_tolerance: float = 30
    triad_angle_tolerance: float = 30
    
    # Numerical stability
    min_variance: float = 1e-10
    min_determinant: float = 1e-10


class ColorSpaceError(Exception):
    """Custom exception for color space conversion errors"""
    pass


class HarmonyEvaluationError(Exception):
    """Custom exception for harmony evaluation errors"""
    pass


class ImprovedLaraAlvarezImplementation:
    """
    Improved implementation of "A Geometric Approach to Harmonic Color Palette Design"
    with better error handling, validation, and performance optimizations
    """
    
    def __init__(self, config: Optional[HarmonyConfig] = None):
        self.config = config or HarmonyConfig()
        self._cache_clear()
    
    def _cache_clear(self):
        """Clear all cached calculations"""
        if hasattr(self, '_calculate_tone_covariance_cached'):
            self._calculate_tone_covariance_cached.cache_clear()
        if hasattr(self, '_calculate_hue_variance_cached'):
            self._calculate_hue_variance_cached.cache_clear()
    
    def validate_rgb(self, r: float, g: float, b: float) -> None:
        """Validate RGB values are in [0, 1]"""
        if not all(0 <= c <= 1 for c in [r, g, b]):
            raise ColorSpaceError(f"RGB values must be in [0, 1], got ({r:.2f}, {g:.2f}, {b:.2f})")
    
    def validate_lch(self, L: float, C: float, h: float) -> None:
        """Validate LCh values are in valid ranges"""
        if not (0 <= L <= 100):
            raise ColorSpaceError(f"Lightness must be in [0, 100], got {L}")
        if not (0 <= C <= 100):
            raise ColorSpaceError(f"Chroma must be in [0, 100], got {C}")
        if not (0 <= h < 360):
            raise ColorSpaceError(f"Hue must be in [0, 360), got {h}")
    
    def rgb_to_lch(self, r: float, g: float, b: float) -> Tuple[float, float, float]:
        """
        Convert RGB (0-1) to CIE LCh with validation
        For production, consider using colour-science library
        """
        self.validate_rgb(r, g, b)
        
        # Linearize RGB (remove gamma)
        r_linear = ((r + 0.055) / 1.055) ** 2.4 if r > 0.04045 else r / 12.92
        g_linear = ((g + 0.055) / 1.055) ** 2.4 if g > 0.04045 else g / 12.92
        b_linear = ((b + 0.055) / 1.055) ** 2.4 if b > 0.04045 else b / 12.92
        
        # RGB to XYZ (D65 illuminant)
        X = r_linear * 0.4124564 + g_linear * 0.3575761 + b_linear * 0.1804375
        Y = r_linear * 0.2126729 + g_linear * 0.7151522 + b_linear * 0.0721750
        Z = r_linear * 0.0193339 + g_linear * 0.1191920 + b_linear * 0.9503041
        
        # Normalize
        X, Y, Z = X / 0.95047, Y / 1.00000, Z / 1.08883
        
        # XYZ to Lab
        epsilon = 0.008856
        kappa = 903.3
        
        fx = X**(1/3) if X > epsilon else (kappa * X + 16) / 116
        fy = Y**(1/3) if Y > epsilon else (kappa * Y + 16) / 116
        fz = Z**(1/3) if Z > epsilon else (kappa * Z + 16) / 116
        
        L = 116 * fy - 16
        a = 500 * (fx - fy)
        b_val = 200 * (fy - fz)
        
        # Lab to LCh
        C = np.sqrt(a**2 + b_val**2)
        h = np.degrees(np.arctan2(b_val, a))
        if h < 0:
            h += 360
        
        # Ensure valid ranges
        L = np.clip(L, 0, 100)
        C = np.clip(C, 0, 100)
        
        return L, C, h
    
    def lch_to_rgb(self, L: float, C: float, h: float) -> Tuple[float, float, float]:
        """Convert CIE LCh to RGB (0-1) with validation"""
        self.validate_lch(L, C, h)
        
        # LCh to Lab
        h_rad = np.radians(h)
        a = C * np.cos(h_rad)
        b_val = C * np.sin(h_rad)
        
        # Lab to XYZ
        epsilon = 0.008856
        kappa = 903.3
        
        fy = (L + 16) / 116
        fx = a / 500 + fy
        fz = fy - b_val / 200
        
        X = fx**3 if fx**3 > epsilon else (116 * fx - 16) / kappa
        Y = fy**3 if fy**3 > epsilon else (116 * fy - 16) / kappa
        Z = fz**3 if fz**3 > epsilon else (116 * fz - 16) / kappa
        
        # Denormalize
        X, Y, Z = X * 0.95047, Y * 1.00000, Z * 1.08883
        
        # XYZ to RGB
        r = X * 3.2404542 - Y * 1.5371385 - Z * 0.4985314
        g = -X * 0.9692660 + Y * 1.8760108 + Z * 0.0415560
        b_val = X * 0.0556434 - Y * 0.2040259 + Z * 1.0572252
        
        # Apply gamma correction
        def gamma_correct(channel):
            if channel > 0.0031308:
                return 1.055 * (channel**(1/2.4)) - 0.055
            return 12.92 * channel
        
        r = np.clip(gamma_correct(r), 0, 1)
        g = np.clip(gamma_correct(g), 0, 1)
        b = np.clip(gamma_correct(b_val), 0, 1)
        
        return r, g, b
    
    @lru_cache(maxsize=256)
    def _calculate_hue_variance_cached(self, h: float, c: float) -> float:
        """Cached version of hue variance calculation"""
        # HT term for hue space uniformity (from paper)
        h_rad = np.radians(h)
        HT = (1.0 - 0.17 * np.cos(h_rad - np.radians(30)) +
              0.24 * np.cos(2 * h_rad) +
              0.32 * np.cos(3 * h_rad + np.radians(6)) -
              0.20 * np.cos(4 * h_rad - np.radians(65)))
        
        # Equation 1 from paper
        sigma_h = (self.config.kh * (1 + 0.015 * c * HT) + 
                   self.config.kN * (self.config.gamma**2 / (c**2 + self.config.gamma**2)))
        
        return max(sigma_h**2, self.config.min_variance)
    
    def calculate_hue_variance(self, h: float, c: float) -> float:
        """Calculate hue variance with caching"""
        # Round to reduce cache misses
        h_rounded = round(h, 1)
        c_rounded = round(c, 1)
        return self._calculate_hue_variance_cached(h_rounded, c_rounded)
    
    @lru_cache(maxsize=256)  
    def _calculate_tone_covariance_cached(self, L: float, c: float) -> np.ndarray:
        """Cached version of tone covariance calculation"""
        # Equation 4 from paper
        SL = 1 + 0.015 * (L - 50)**2 / np.sqrt(20 + (L - 50)**2)
        Sc = 1 + 0.045 * c
        
        cov = np.array([
            [self.config.kc**2 * Sc**2, 0],
            [0, self.config.kL**2 * SL**2]
        ])
        
        return cov
    
    def calculate_tone_covariance(self, L: float, c: float) -> np.ndarray:
        """Calculate tone covariance with caching"""
        L_rounded = round(L, 1)
        c_rounded = round(c, 1)
        return self._calculate_tone_covariance_cached(L_rounded, c_rounded).copy()
    
    def bhattacharyya_distance(self, mean1: np.ndarray, cov1: np.ndarray, 
                              mean2: np.ndarray, cov2: np.ndarray) -> float:
        """
        Calculate Bhattacharyya distance with improved numerical stability
        """
        mean_diff = mean1 - mean2
        cov_avg = (cov1 + cov2) / 2
        
        # Check for numerical stability
        det_avg = np.linalg.det(cov_avg)
        det1 = np.linalg.det(cov1)
        det2 = np.linalg.det(cov2)
        
        if det_avg < self.config.min_determinant or det1 < self.config.min_determinant or det2 < self.config.min_determinant:
            logger.warning("Singular covariance matrix detected")
            return float('inf')
        
        try:
            inv_cov_avg = np.linalg.inv(cov_avg)
            term1 = 0.125 * mean_diff.T @ inv_cov_avg @ mean_diff
            term2 = 0.5 * np.log(det_avg / np.sqrt(det1 * det2))
            return float(term1 + term2)
        except np.linalg.LinAlgError as e:
            logger.warning(f"Matrix inversion failed: {e}")
            return float('inf')
    
    def _check_hue_pattern(self, colors_lch: List[Tuple[float, float, float]], 
                           pattern: str) -> bool:
        """
        Check if colors match a specific hue pattern
        Improved logic compared to original implementation
        """
        if len(colors_lch) < 2:
            return False
        
        hues = [h for L, c, h in colors_lch]
        
        if pattern == 'analog':
            # All colors should be within threshold
            # Handle wrap-around at 0/360
            min_span = float('inf')
            for start in range(360):
                span = 0
                for h in hues:
                    dist = min(abs(h - start), 360 - abs(h - start))
                    span = max(span, dist)
                min_span = min(min_span, span)
            return min_span <= self.config.analog_angle_threshold
        
        elif pattern == 'opposite' and len(colors_lch) == 2:
            diff = abs(hues[0] - hues[1])
            diff = min(diff, 360 - diff)
            return abs(diff - 180) <= self.config.opposite_angle_tolerance
        
        elif pattern == 'triad' and len(colors_lch) == 3:
            # Check if hues are approximately 120° apart
            hues_sorted = sorted(hues)
            diffs = []
            for i in range(len(hues_sorted)):
                next_i = (i + 1) % len(hues_sorted)
                diff = (hues_sorted[next_i] - hues_sorted[i]) % 360
                if diff == 0:
                    diff = 360
                diffs.append(diff)
            
            # All differences should be close to 120°
            target = 120
            return all(abs(d - target) <= self.config.triad_angle_tolerance for d in diffs)
        
        return False
    
    def evaluate_hue_harmony(self, colors_lch: List[Tuple[float, float, float]]) -> str:
        """
        Improved Algorithm 1: Evaluating Hue Harmony
        Uses proper pattern checking instead of incremental fusion
        """
        if len(colors_lch) < 2:
            return 'no_harmonic'
        
        # Validate input colors
        for L, c, h in colors_lch:
            try:
                self.validate_lch(L, c, h)
            except ColorSpaceError as e:
                logger.warning(f"Invalid color in harmony evaluation: {e}")
                return 'no_harmonic'
        
        # Check patterns in order of preference (from paper)
        for pattern in ['analog', 'opposite', 'triad']:
            if self._check_hue_pattern(colors_lch, pattern):
                return pattern
        
        return 'no_harmonic'
    
    def fit_line_to_tones(self, tones: List[Tuple[float, float]], 
                          weights: Optional[List[float]] = None) -> Tuple[float, float]:
        """
        Fit line using weighted least squares with improved numerical stability
        """
        if len(tones) < 2:
            raise ValueError("Need at least 2 points to fit a line")
        
        tones_array = np.array(tones)
        if tones_array.shape[0] < 2:
            raise ValueError("Insufficient unique points for line fitting")
        
        c_values = tones_array[:, 0]
        L_values = tones_array[:, 1]
        
        if weights is None:
            weights = np.ones(len(tones))
        weights = np.array(weights)
        
        # Normalize weights
        weights = weights / np.sum(weights)
        
        # Weighted means
        c_mean = np.sum(weights * c_values)
        L_mean = np.sum(weights * L_values)
        
        # Calculate angle (Equation 8 from paper)
        c_centered = c_values - c_mean
        L_centered = L_values - L_mean
        
        numerator = -2 * np.sum(weights * L_centered * c_centered)
        denominator = np.sum(weights * (L_centered**2 - c_centered**2))
        
        # Handle degenerate cases
        if abs(denominator) < 1e-10:
            # Points are on a circle or line through origin
            if abs(numerator) < 1e-10:
                # Arbitrary angle
                phi = 0
            else:
                phi = np.pi / 2 * np.sign(numerator)
        else:
            phi = 0.5 * np.arctan2(numerator, denominator)
        
        # Calculate r (distance from origin to line)
        r = c_mean * np.cos(phi) + L_mean * np.sin(phi)
        
        return r, phi
    
    def evaluate_line_harmony(self, colors_lch: List[Tuple[float, float, float]]) -> Dict:
        """
        Improved Algorithm 2: Evaluating tone harmony with better error handling
        """
        if len(colors_lch) < 2:
            return {'harmonic': True, 'type': 'single_point', 'details': {}}
        
        # Extract and validate tones
        tones = []
        for i, (L, c, h) in enumerate(colors_lch):
            try:
                self.validate_lch(L, c, h)
                tones.append((c, L))
            except ColorSpaceError as e:
                return {
                    'harmonic': False, 
                    'reason': 'invalid_color',
                    'error': str(e),
                    'problem_index': i
                }
        
        # Pre-calculate covariances for efficiency
        covariances = [
            self.calculate_tone_covariance(L, c) 
            for L, c, h in colors_lch
        ]
        
        # Check non-ambiguous condition (Equation 7)
        for i in range(len(tones)):
            for j in range(i + 1, len(tones)):
                ti = np.array(tones[i])
                tj = np.array(tones[j])
                
                dist = self.bhattacharyya_distance(ti, covariances[i], 
                                                  tj, covariances[j])
                
                if dist < self.config.bhattacharyya_threshold:
                    return {
                        'harmonic': False, 
                        'reason': 'ambiguous_tones',
                        'problem_indices': (i, j),
                        'bhattacharyya_distance': dist
                    }
        
        # Fit line to tones
        try:
            r, phi = self.fit_line_to_tones(tones)
        except (ValueError, np.linalg.LinAlgError) as e:
            logger.warning(f"Line fitting failed: {e}")
            return {
                'harmonic': False, 
                'reason': 'cannot_fit_line',
                'error': str(e)
            }
        
        # Check if all points follow the line
        distances = []
        for tone in tones:
            c, L = tone
            dist = abs(r - c * np.cos(phi) - L * np.sin(phi))
            distances.append(dist)
        
        max_distance = max(distances)
        avg_distance = np.mean(distances)
        
        if max_distance > self.config.line_tolerance:
            return {
                'harmonic': False, 
                'reason': 'non_linear',
                'max_distance': max_distance,
                'avg_distance': avg_distance,
                'distances': distances
            }
        
        # Calculate preference score based on angle
        phi_degrees = np.degrees(phi)
        
        # Normalize to [0, 180]
        phi_abs = abs(phi_degrees)
        if phi_abs > 90:
            phi_abs = 180 - phi_abs
        
        # Preference scoring from paper
        if 30 <= phi_abs <= 75 or 105 <= phi_abs <= 155:
            preference_score = 1.5
        elif phi_abs == 90:
            preference_score = 0.7
        else:
            preference_score = 1.0
        
        return {
            'harmonic': True,
            'type': 'linear',
            'line_params': {
                'r': r, 
                'phi': phi_degrees,
                'phi_normalized': phi_abs
            },
            'max_deviation': max_distance,
            'avg_deviation': avg_distance,
            'preference_score': preference_score,
            'point_distances': distances
        }
    
    def evaluate_complete_harmony(self, colors_lch: List[Tuple[float, float, float]]) -> Dict:
        """
        Complete harmony evaluation with detailed analysis
        """
        # Input validation
        if not colors_lch:
            return {
                'error': 'No colors provided',
                'is_harmonic': False,
                'overall_score': 0
            }
        
        if len(colors_lch) > 10:
            logger.warning(f"Large palette size ({len(colors_lch)}) may affect performance")
        
        # Evaluate both aspects
        hue_harmony = self.evaluate_hue_harmony(colors_lch)
        tone_harmony = self.evaluate_line_harmony(colors_lch)
        
        # Calculate overall score with weights
        hue_weight = 0.5
        tone_weight = 0.5
        
        hue_score = 0
        if hue_harmony != 'no_harmonic':
            # Different patterns have different base scores
            pattern_scores = {
                'analog': 0.6,    # Slightly preferred (from paper)
                'opposite': 0.5,
                'triad': 0.4
            }
            hue_score = pattern_scores.get(hue_harmony, 0.5)
        
        tone_score = 0
        if tone_harmony['harmonic']:
            # Base score with preference modifier
            tone_score = 0.5 * tone_harmony.get('preference_score', 1.0)
            
            # Penalty for high deviation
            if 'avg_deviation' in tone_harmony:
                deviation_penalty = min(tone_harmony['avg_deviation'] / self.config.line_tolerance, 1.0)
                tone_score *= (1 - 0.3 * deviation_penalty)
        
        overall_score = hue_weight * hue_score + tone_weight * tone_score
        
        # Generate recommendations
        recommendations = []
        if hue_harmony == 'no_harmonic':
            recommendations.append("Consider using analog, opposite, or triad hue patterns")
        
        if not tone_harmony['harmonic']:
            reason = tone_harmony.get('reason', '')
            if 'ambiguous' in reason:
                recommendations.append("Increase color contrast (minimum ΔE ≈ 20)")
            elif 'non_linear' in reason:
                recommendations.append("Align colors along a line in the chroma-lightness plane")
        
        elif tone_harmony['harmonic'] and 'line_params' in tone_harmony:
            phi_norm = tone_harmony['line_params'].get('phi_normalized', 0)
            if phi_norm == 90:
                recommendations.append("Vertical lines (90°) are less preferred; try 30-75° or 105-155°")
            elif not (30 <= phi_norm <= 155) or (75 < phi_norm < 105):
                recommendations.append("Line angles between 30-75° or 105-155° are preferred")
        
        return {
            'hue_pattern': hue_harmony,
            'tone_analysis': tone_harmony,
            'overall_score': overall_score,
            'is_harmonic': overall_score >= 0.5,
            'scores': {
                'hue': hue_score,
                'tone': tone_score,
                'weighted': overall_score
            },
            'recommendations': recommendations,
            'color_count': len(colors_lch)
        }


# Example usage with improved error handling
if __name__ == "__main__":
    # Initialize with custom config
    config = HarmonyConfig(
        kh=15,
        kN=30,
        line_tolerance=12.0  # Slightly more lenient
    )
    
    harmony = ImprovedLaraAlvarezImplementation(config)
    
    # Test with various palettes
    test_palettes = [
        {
            'name': 'Analog Harmony',
            'colors': [(70, 30, 30), (50, 40, 35), (30, 50, 40)]
        },
        {
            'name': 'Triad Harmony', 
            'colors': [(60, 40, 0), (60, 40, 120), (60, 40, 240)]
        },
        {
            'name': 'Invalid Colors',
            'colors': [(70, 30, 30), (150, 40, 35), (30, 50, 40)]  # L=150 invalid
        },
        {
            'name': 'Ambiguous Colors',
            'colors': [(70, 30, 30), (68, 32, 35), (20, 80, 200)]
        }
    ]
    
    for palette_info in test_palettes:
        print(f"\n{'='*60}")
        print(f"Testing: {palette_info['name']}")
        print('='*60)
        
        try:
            result = harmony.evaluate_complete_harmony(palette_info['colors'])
            
            print(f"Hue Pattern: {result['hue_pattern']}")
            print(f"Tone Harmonic: {result['tone_analysis']['harmonic']}")
            
            if not result['tone_analysis']['harmonic']:
                print(f"  Reason: {result['tone_analysis'].get('reason', 'unknown')}")
            
            print(f"\nScores:")
            print(f"  Hue: {result['scores']['hue']:.2f}")
            print(f"  Tone: {result['scores']['tone']:.2f}")
            print(f"  Overall: {result['overall_score']:.2f}")
            
            print(f"\nIs Harmonic: {'YES' if result['is_harmonic'] else 'NO'}")
            
            if result['recommendations']:
                print("\nRecommendations:")
                for rec in result['recommendations']:
                    print(f"  • {rec}")
                    
        except Exception as e:
            print(f"Error evaluating palette: {e}")
            logger.error(f"Evaluation failed for {palette_info['name']}", exc_info=True)
