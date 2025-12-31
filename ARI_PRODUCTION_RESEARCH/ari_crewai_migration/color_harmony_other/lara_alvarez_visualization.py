import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Ellipse
from scipy import stats
from typing import List, Tuple, Optional, Dict
import colorsys

# Import the base implementation
from lara_alvarez_color_harmony import LaraAlvarezImplementation

class LaraAlvarezVisualization(LaraAlvarezImplementation):
    """
    Extended implementation with visualization capabilities for the 
    Lara-Alvarez color harmony paper
    """
    
    def __init__(self):
        super().__init__()
    
    def plot_hue_wheel(self, colors_lch: List[Tuple[float, float, float]], 
                       ax: Optional[plt.Axes] = None) -> plt.Axes:
        """Plot colors on a hue wheel with uncertainty regions"""
        if ax is None:
            fig, ax = plt.subplots(1, 1, figsize=(6, 6), subplot_kw=dict(projection='polar'))
        
        # Draw hue wheel background
        theta = np.linspace(0, 2*np.pi, 360)
        r = np.ones_like(theta)
        
        # Color each segment
        for i in range(len(theta)-1):
            hue = np.degrees(theta[i])
            # Use a standard saturation and lightness for display
            rgb = self.lch_to_rgb(60, 50, hue)
            ax.fill_between([theta[i], theta[i+1]], 0, 1, 
                           color=rgb, alpha=0.3)
        
        # Plot each color with uncertainty
        for i, (L, c, h) in enumerate(colors_lch):
            h_rad = np.radians(h)
            
            # Calculate hue uncertainty
            sigma_h = np.sqrt(self.calculate_hue_variance(h, c))
            
            # Plot point
            radius = 0.5 + 0.4 * (c / 100)  # Map chroma to radius
            ax.plot(h_rad, radius, 'o', markersize=15, 
                   color=self.lch_to_rgb(L, c, h),
                   markeredgecolor='black', markeredgewidth=2)
            
            # Plot uncertainty arc
            if sigma_h < 180:  # Only if uncertainty is reasonable
                theta_range = np.linspace(h_rad - np.radians(sigma_h), 
                                        h_rad + np.radians(sigma_h), 50)
                ax.fill_between(theta_range, radius - 0.05, radius + 0.05,
                               alpha=0.2, color='gray')
            
            # Add label
            ax.text(h_rad, radius + 0.15, f'C{i+1}', 
                   ha='center', va='center', fontsize=10)
        
        # Detect and draw hue pattern
        pattern = self.evaluate_hue_harmony(colors_lch)
        if pattern == 'analog':
            # Draw arc connecting analog colors
            hues = [np.radians(h) for L, c, h in colors_lch]
            min_h, max_h = min(hues), max(hues)
            if max_h - min_h < np.pi:  # Normal case
                theta_conn = np.linspace(min_h, max_h, 50)
                ax.plot(theta_conn, np.ones_like(theta_conn) * 0.85, 
                       'g--', linewidth=2, alpha=0.7)
            
        elif pattern == 'opposite':
            # Draw diameter
            h1 = np.radians(colors_lch[0][2])
            ax.plot([h1, h1 + np.pi], [0.85, 0.85], 
                   'b--', linewidth=2, alpha=0.7)
            
        elif pattern == 'triad':
            # Draw triangle
            if len(colors_lch) >= 3:
                hues = [np.radians(h) for L, c, h in colors_lch[:3]]
                for i in range(3):
                    ax.plot([hues[i], hues[(i+1)%3]], [0.85, 0.85], 
                           'r--', linewidth=2, alpha=0.7)
        
        ax.set_ylim(0, 1)
        ax.set_title(f'Hue Wheel - Pattern: {pattern}', fontsize=12, pad=20)
        ax.grid(True, alpha=0.3)
        
        return ax
    
    def plot_tone_plane(self, colors_lch: List[Tuple[float, float, float]], 
                        ax: Optional[plt.Axes] = None) -> plt.Axes:
        """Plot colors in the chroma-lightness plane with line fitting"""
        if ax is None:
            fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        
        # Extract tones
        tones = [(c, L) for L, c, h in colors_lch]
        
        # Plot each color point with uncertainty ellipse
        for i, (L, c, h) in enumerate(colors_lch):
            # Get RGB for color display
            rgb = self.lch_to_rgb(L, c, h)
            
            # Plot point
            ax.plot(c, L, 'o', markersize=20, color=rgb,
                   markeredgecolor='black', markeredgewidth=2)
            
            # Calculate and plot uncertainty ellipse
            cov = self.calculate_tone_covariance(L, c)
            eigenvalues, eigenvectors = np.linalg.eig(cov)
            angle = np.degrees(np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0]))
            
            # 2-sigma ellipse (95% confidence)
            ellipse = Ellipse((c, L), 
                            2 * 2 * np.sqrt(eigenvalues[0]),
                            2 * 2 * np.sqrt(eigenvalues[1]),
                            angle=angle, 
                            facecolor='gray', alpha=0.2, 
                            edgecolor='gray', linewidth=1)
            ax.add_patch(ellipse)
            
            # Add label
            ax.text(c + 2, L + 2, f'C{i+1}', fontsize=10)
        
        # Fit and plot line if more than 1 point
        if len(tones) >= 2:
            try:
                r, phi = self.fit_line_to_tones(tones)
                
                # Generate line points
                if abs(np.cos(phi)) > abs(np.sin(phi)):
                    # More horizontal - vary chroma
                    c_line = np.linspace(0, 100, 100)
                    L_line = (r - c_line * np.cos(phi)) / np.sin(phi)
                else:
                    # More vertical - vary lightness
                    L_line = np.linspace(0, 100, 100)
                    c_line = (r - L_line * np.sin(phi)) / np.cos(phi)
                
                # Clip to valid range
                valid = (c_line >= 0) & (c_line <= 100) & (L_line >= 0) & (L_line <= 100)
                c_line = c_line[valid]
                L_line = L_line[valid]
                
                # Plot line
                ax.plot(c_line, L_line, 'g--', linewidth=2, alpha=0.7, 
                       label=f'Fitted line (φ={np.degrees(phi):.1f}°)')
                
                # Show deviation for each point
                for tone in tones:
                    dist = self.point_to_line_distance(tone, r, phi)
                    # Draw perpendicular line to show distance
                    c, L = tone
                    c_proj = (r * np.cos(phi) + L * np.sin(phi) * np.cos(phi) + 
                             c * np.sin(phi)**2)
                    L_proj = (r * np.sin(phi) - c * np.sin(phi) * np.cos(phi) + 
                             L * np.cos(phi)**2)
                    
                    ax.plot([c, c_proj], [L, L_proj], 'r:', linewidth=1, alpha=0.5)
                
            except Exception as e:
                print(f"Could not fit line: {e}")
        
        # Add grid and labels
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.set_xlabel('Chroma (C*)', fontsize=12)
        ax.set_ylabel('Lightness (L*)', fontsize=12)
        ax.set_title('Tone Plane (Chroma-Lightness)', fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add legend
        if len(tones) >= 2:
            ax.legend(loc='best')
        
        # Color the background to show preferred angles
        # According to paper: 30° to 155° are preferred
        x = np.linspace(0, 100, 100)
        y = np.linspace(0, 100, 100)
        X, Y = np.meshgrid(x, y)
        
        # Preferred angle regions (subtle shading)
        for angle in [30, 45, 60, 75, 90, 105, 120, 135, 150]:
            phi_rad = np.radians(angle)
            # Line equation: x*cos(phi) + y*sin(phi) = r
            # We'll shade a band around lines through center
            r_center = 50 * np.cos(phi_rad) + 50 * np.sin(phi_rad)
            distance = np.abs(X * np.cos(phi_rad) + Y * np.sin(phi_rad) - r_center)
            
            if 30 <= angle <= 155 and angle != 90:
                # Preferred angles
                mask = distance < 3
                ax.contourf(X, Y, mask.astype(float), levels=[0.5, 1],
                          colors=['green'], alpha=0.02)
        
        return ax
    
    def visualize_complete_analysis(self, colors_lch: List[Tuple[float, float, float]],
                                   save_path: Optional[str] = None):
        """Create complete visualization with all analyses"""
        fig = plt.figure(figsize=(16, 10))
        
        # Create grid layout
        gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
        
        # 1. Color swatches
        ax1 = fig.add_subplot(gs[0, 0])
        self.plot_color_swatches(colors_lch, ax1)
        
        # 2. Hue wheel
        ax2 = fig.add_subplot(gs[0, 1], projection='polar')
        self.plot_hue_wheel(colors_lch, ax2)
        
        # 3. Tone plane
        ax3 = fig.add_subplot(gs[0, 2])
        self.plot_tone_plane(colors_lch, ax3)
        
        # 4. Harmony analysis text
        ax4 = fig.add_subplot(gs[1, :])
        self.plot_harmony_analysis(colors_lch, ax4)
        
        # Overall title
        fig.suptitle('Color Harmony Analysis (Lara-Alvarez Method)', 
                    fontsize=16, fontweight='bold')
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        plt.show()
    
    def plot_color_swatches(self, colors_lch: List[Tuple[float, float, float]], 
                           ax: plt.Axes):
        """Display color swatches"""
        ax.set_xlim(0, 10)
        ax.set_ylim(0, len(colors_lch))
        
        for i, (L, c, h) in enumerate(colors_lch):
            rgb = self.lch_to_rgb(L, c, h)
            
            # Draw color rectangle
            rect = patches.Rectangle((0, i), 8, 0.8, 
                                    linewidth=2, edgecolor='black',
                                    facecolor=rgb)
            ax.add_patch(rect)
            
            # Add text
            hex_color = '#{:02x}{:02x}{:02x}'.format(
                int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)
            )
            ax.text(8.5, i + 0.4, hex_color, 
                   va='center', fontsize=10, family='monospace')
            
            # Add LCh values
            ax.text(0.5, i + 0.4, f'L:{L:.0f} C:{c:.0f} h:{h:.0f}°',
                   va='center', fontsize=9, color='white' if L < 50 else 'black',
                   fontweight='bold')
        
        ax.set_title('Color Palette', fontsize=12)
        ax.axis('off')
    
    def plot_harmony_analysis(self, colors_lch: List[Tuple[float, float, float]], 
                             ax: plt.Axes):
        """Display harmony analysis results"""
        result = self.evaluate_complete_harmony(colors_lch)
        
        # Format text
        text = []
        text.append("HARMONY ANALYSIS RESULTS\n")
        text.append("=" * 50 + "\n\n")
        
        # Hue analysis
        text.append(f"Hue Pattern: {result['hue_pattern'].upper()}\n")
        
        # Tone analysis
        tone_info = result['tone_analysis']
        text.append(f"Tone Harmony: {'✓ HARMONIC' if tone_info['harmonic'] else '✗ NOT HARMONIC'}\n")
        
        if tone_info['harmonic'] and 'line_params' in tone_info:
            params = tone_info['line_params']
            text.append(f"  • Line angle: {params['phi']:.1f}°\n")
            text.append(f"  • Distance from origin: {params['r']:.1f}\n")
            text.append(f"  • Max deviation: {tone_info['max_deviation']:.2f}\n")
            text.append(f"  • Preference score: {tone_info['preference_score']:.2f}\n")
        elif not tone_info['harmonic']:
            text.append(f"  • Reason: {tone_info.get('reason', 'unknown').replace('_', ' ').title()}\n")
        
        text.append("\n")
        
        # Overall score
        score = result['overall_score']
        text.append(f"Overall Harmony Score: {score:.2f}/1.0 ")
        
        if score >= 0.9:
            text.append("(Excellent)\n")
        elif score >= 0.7:
            text.append("(Good)\n")
        elif score >= 0.5:
            text.append("(Acceptable)\n")
        else:
            text.append("(Poor)\n")
        
        # Recommendations
        text.append("\n" + "=" * 50 + "\n")
        text.append("RECOMMENDATIONS:\n")
        
        if result['hue_pattern'] == 'no_harmonic':
            text.append("• Consider using analog, opposite, or triad hue patterns\n")
        
        if not tone_info['harmonic']:
            if 'ambiguous' in tone_info.get('reason', ''):
                text.append("• Increase contrast between colors (min ΔE = 20)\n")
            elif 'non_linear' in tone_info.get('reason', ''):
                text.append("• Align colors along a line in the chroma-lightness plane\n")
        
        if tone_info['harmonic'] and 'line_params' in tone_info:
            phi = tone_info['line_params']['phi']
            if abs(phi) == 90:
                text.append("• Vertical lines (90°) are less preferred; try 30-75° or 105-155°\n")
            elif not (30 <= abs(phi) <= 155):
                text.append("• Line angles between 30° and 155° are preferred\n")
        
        # Display text
        ax.text(0.05, 0.95, ''.join(text), 
               transform=ax.transAxes,
               fontsize=10, 
               verticalalignment='top',
               fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax.axis('off')


# Extended example with visualizations
if __name__ == "__main__":
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    
    # Initialize visualization system
    harmony_viz = LaraAlvarezVisualization()
    
    print("\n=== VISUAL HARMONY ANALYSIS SYSTEM ===\n")
    
    # Example 1: Analog harmony with good line
    palette1 = [
        (70, 30, 30),   # Light, moderate chroma, red-orange
        (50, 40, 35),   # Medium lightness, higher chroma
        (30, 50, 40),   # Dark, high chroma
    ]
    
    print("Creating visualization for Palette 1 (Analog)...")
    harmony_viz.visualize_complete_analysis(palette1, 
                                           save_path='/home/claude/harmony_palette1.png')
    
    # Example 2: Triad harmony
    palette2 = [
        (60, 40, 0),     # Red
        (60, 40, 120),   # Green  
        (60, 40, 240),   # Blue
    ]
    
    print("Creating visualization for Palette 2 (Triad)...")
    harmony_viz.visualize_complete_analysis(palette2,
                                           save_path='/home/claude/harmony_palette2.png')
    
    # Example 3: Non-harmonic (for comparison)
    palette3 = [
        (70, 30, 30),    
        (68, 32, 35),    # Too similar (ambiguous)
        (20, 80, 200),   # Random position
    ]
    
    print("Creating visualization for Palette 3 (Non-harmonic)...")
    harmony_viz.visualize_complete_analysis(palette3,
                                           save_path='/home/claude/harmony_palette3.png')
    
    # Example 4: Generate optimized palette
    print("\nGenerating optimized harmonic palette...")
    base = (50, 35, 180)  # Cyan base
    
    # Generate with preferred angle (45°)
    optimized = harmony_viz.generate_harmonic_palette(
        base, n_colors=4, hue_pattern='analog', line_angle=45
    )
    
    print("Creating visualization for Generated Palette...")
    harmony_viz.visualize_complete_analysis(optimized,
                                           save_path='/home/claude/harmony_generated.png')
    
    print("\nVisualizations saved as PNG files!")
    print("  - harmony_palette1.png (Analog example)")
    print("  - harmony_palette2.png (Triad example)")  
    print("  - harmony_palette3.png (Non-harmonic example)")
    print("  - harmony_generated.png (Generated optimized palette)")



