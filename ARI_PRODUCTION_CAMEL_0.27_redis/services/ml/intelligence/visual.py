"""
Aesthetic Analysis Intelligence for VibeBot

Provides style and aesthetic intelligence without requiring PyTorch.
Complements visual_pytorch.py with rule-based aesthetic analysis.
NEVER returns products - only aesthetic insights for VibeBot.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import re

logger = logging.getLogger("intelligence.visual")


class AestheticIntelligence:
    """
    Provides aesthetic and style intelligence for VibeBot.
    
    Uses rule-based analysis and pattern matching.
    CRITICAL: Returns aesthetic insights, NEVER products!
    """
    
    def __init__(self, product_kg: Any = None):
        """
        Initialize aesthetic intelligence system.
        
        Args:
            product_kg: Product knowledge graph
        """
        logger.info("Initializing Aesthetic Intelligence")
        
        self.product_kg = product_kg
        
        # Style taxonomies
        self._initialize_style_taxonomies()
        
        # Color theory rules
        self._initialize_color_rules()
        
        # Trend patterns
        self._initialize_trend_patterns()
        
        logger.info("Aesthetic Intelligence initialized")
    
    def _initialize_style_taxonomies(self):
        """Initialize style categories and relationships."""
        self.style_taxonomy = {
            "classic": {
                "keywords": ["timeless", "elegant", "traditional", "refined"],
                "colors": ["navy", "black", "white", "beige", "gray"],
                "patterns": ["solid", "pinstripe", "houndstooth"],
                "opposite": "trendy"
            },
            "trendy": {
                "keywords": ["modern", "current", "fashionable", "latest"],
                "colors": ["neon", "metallic", "holographic"],
                "patterns": ["abstract", "geometric", "digital"],
                "opposite": "classic"
            },
            "casual": {
                "keywords": ["relaxed", "comfortable", "everyday", "laid-back"],
                "colors": ["denim", "khaki", "olive", "neutral"],
                "patterns": ["solid", "stripe", "plaid"],
                "opposite": "formal"
            },
            "formal": {
                "keywords": ["professional", "business", "elegant", "sophisticated"],
                "colors": ["black", "navy", "charcoal", "white"],
                "patterns": ["solid", "subtle", "pinstripe"],
                "opposite": "casual"
            },
            "bohemian": {
                "keywords": ["free-spirited", "artistic", "eclectic", "vintage"],
                "colors": ["earth", "jewel", "warm", "natural"],
                "patterns": ["paisley", "floral", "ethnic", "mixed"],
                "opposite": "minimalist"
            },
            "minimalist": {
                "keywords": ["simple", "clean", "understated", "essential"],
                "colors": ["neutral", "monochrome", "white", "black"],
                "patterns": ["solid", "minimal", "geometric"],
                "opposite": "bohemian"
            },
            "sporty": {
                "keywords": ["athletic", "active", "performance", "dynamic"],
                "colors": ["bright", "neon", "contrast", "bold"],
                "patterns": ["stripe", "color-block", "logo"],
                "opposite": "glamorous"
            },
            "glamorous": {
                "keywords": ["luxurious", "sparkly", "dramatic", "opulent"],
                "colors": ["gold", "silver", "jewel", "metallic"],
                "patterns": ["sequin", "embellished", "ornate"],
                "opposite": "sporty"
            }
        }
        
        # Style compatibility matrix
        self.style_compatibility = {
            "classic": ["formal", "minimalist"],
            "trendy": ["sporty", "glamorous"],
            "casual": ["sporty", "bohemian"],
            "formal": ["classic", "glamorous"],
            "bohemian": ["casual", "vintage"],
            "minimalist": ["classic", "modern"],
            "sporty": ["casual", "trendy"],
            "glamorous": ["formal", "trendy"]
        }
    
    def _initialize_color_rules(self):
        """Initialize color theory rules."""
        self.color_families = {
            "warm": ["red", "orange", "yellow", "coral", "peach", "gold"],
            "cool": ["blue", "green", "purple", "teal", "mint", "lavender"],
            "neutral": ["black", "white", "gray", "beige", "brown", "navy"],
            "earth": ["brown", "tan", "olive", "rust", "terracotta", "sage"],
            "jewel": ["emerald", "ruby", "sapphire", "amethyst", "topaz"],
            "pastel": ["pink", "baby blue", "mint", "lavender", "peach", "cream"]
        }
        
        # Color harmony rules
        self.color_harmonies = {
            "monochromatic": "Single color in different shades",
            "analogous": "Colors next to each other on color wheel",
            "complementary": "Colors opposite on color wheel",
            "triadic": "Three colors evenly spaced on color wheel",
            "split-complementary": "Base color plus two adjacent to complement",
            "tetradic": "Four colors in two complementary pairs"
        }
        
        # Season color palettes
        self.seasonal_colors = {
            "spring": ["pastel", "fresh green", "coral", "sky blue", "yellow"],
            "summer": ["bright", "white", "navy", "tropical", "neon"],
            "autumn": ["rust", "burgundy", "olive", "mustard", "brown"],
            "winter": ["jewel", "black", "gray", "deep blue", "emerald"]
        }
    
    def _initialize_trend_patterns(self):
        """Initialize trend detection patterns."""
        self.trend_indicators = {
            "2024_trends": [
                "oversized", "dopamine", "quiet luxury", "coastal",
                "barbiecore", "sustainable", "vintage", "y2k"
            ],
            "timeless": [
                "little black dress", "white shirt", "denim",
                "trench coat", "leather jacket", "cashmere"
            ],
            "seasonal": {
                "spring": ["floral", "pastel", "light layers"],
                "summer": ["linen", "sundress", "shorts", "sandals"],
                "autumn": ["knit", "boots", "layering", "scarf"],
                "winter": ["coat", "sweater", "wool", "thermal"]
            }
        }
    
    async def analyze_style(
        self,
        query: Optional[str] = None,
        product_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze style from query or product data.
        
        Args:
            query: Style query text
            product_data: Product information
            
        Returns:
            Style analysis intelligence
        """
        analysis = {
            "primary_style": None,
            "style_attributes": [],
            "compatible_styles": [],
            "color_analysis": {},
            "trend_alignment": 0.0,
            "confidence": 0.0
        }
        
        if query:
            # Analyze query text
            query_lower = query.lower()
            
            # Detect primary style
            style_scores = {}
            for style, info in self.style_taxonomy.items():
                score = sum(1 for kw in info["keywords"] if kw in query_lower)
                if score > 0:
                    style_scores[style] = score
            
            if style_scores:
                primary_style = max(style_scores, key=style_scores.get)
                analysis["primary_style"] = primary_style
                analysis["compatible_styles"] = self.style_compatibility.get(primary_style, [])
                analysis["style_attributes"] = self.style_taxonomy[primary_style]["keywords"]
            
            # Analyze colors mentioned
            analysis["color_analysis"] = self._analyze_colors_in_text(query_lower)
            
            # Check trend alignment
            analysis["trend_alignment"] = self._calculate_trend_score(query_lower)
            
            analysis["confidence"] = 0.7
        
        if product_data:
            # Analyze product attributes
            categories = product_data.get("categories", [])
            tags = product_data.get("tags", [])
            
            # Combine for analysis
            all_text = " ".join(categories + tags).lower()
            
            # Detect styles from product
            product_styles = []
            for style, info in self.style_taxonomy.items():
                if any(kw in all_text for kw in info["keywords"]):
                    product_styles.append(style)
            
            if product_styles and not analysis["primary_style"]:
                analysis["primary_style"] = product_styles[0]
                analysis["compatible_styles"] = self.style_compatibility.get(product_styles[0], [])
            
            # Add product-specific attributes
            analysis["style_attributes"].extend(product_styles)
            
            analysis["confidence"] = 0.8
        
        return analysis
    
    def _analyze_colors_in_text(self, text: str) -> Dict[str, Any]:
        """Analyze color mentions in text."""
        found_colors = []
        color_families = []
        
        # Check each color family
        for family, colors in self.color_families.items():
            for color in colors:
                if color in text:
                    found_colors.append(color)
                    if family not in color_families:
                        color_families.append(family)
        
        # Determine harmony
        harmony = "monochromatic" if len(set(found_colors)) <= 1 else "mixed"
        
        return {
            "colors": found_colors,
            "families": color_families,
            "harmony": harmony,
            "temperature": "warm" if "warm" in color_families else "cool" if "cool" in color_families else "neutral"
        }
    
    def _calculate_trend_score(self, text: str) -> float:
        """Calculate trend alignment score."""
        score = 0.0
        total_indicators = len(self.trend_indicators["2024_trends"])
        
        # Check current trends
        matches = sum(1 for trend in self.trend_indicators["2024_trends"] if trend in text)
        
        if total_indicators > 0:
            score = matches / total_indicators
        
        # Boost for timeless pieces
        if any(item in text for item in self.trend_indicators["timeless"]):
            score += 0.2
        
        return min(score, 1.0)
    
    async def get_style_recommendations(
        self,
        current_style: str,
        target_style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get style transition recommendations.
        
        Args:
            current_style: Current style
            target_style: Desired style
            
        Returns:
            Style recommendation intelligence
        """
        recommendations = {
            "current_style": current_style,
            "target_style": target_style,
            "transition_difficulty": "medium",
            "key_changes": [],
            "color_shifts": [],
            "pattern_changes": [],
            "confidence": 0.7
        }
        
        if current_style not in self.style_taxonomy:
            return recommendations
        
        current_info = self.style_taxonomy[current_style]
        
        if target_style and target_style in self.style_taxonomy:
            target_info = self.style_taxonomy[target_style]
            
            # Calculate transition difficulty
            if target_style in self.style_compatibility.get(current_style, []):
                recommendations["transition_difficulty"] = "easy"
            elif target_style == current_info.get("opposite"):
                recommendations["transition_difficulty"] = "hard"
            
            # Identify key changes
            recommendations["key_changes"] = [
                kw for kw in target_info["keywords"]
                if kw not in current_info["keywords"]
            ]
            
            # Color shifts
            recommendations["color_shifts"] = [
                f"Add {color}" for color in target_info["colors"]
                if color not in current_info["colors"]
            ]
            
            # Pattern changes
            recommendations["pattern_changes"] = [
                f"Try {pattern}" for pattern in target_info["patterns"]
                if pattern not in current_info["patterns"]
            ]
        
        return recommendations
    
    async def analyze_outfit_harmony(
        self,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze harmony of outfit items.
        
        Args:
            items: List of outfit items
            
        Returns:
            Outfit harmony analysis
        """
        if not items:
            return {
                "harmony_score": 0.0,
                "style_coherence": "unknown",
                "color_harmony": "unknown",
                "recommendations": [],
                "confidence": 0.0
            }
        
        # Extract styles from items
        item_styles = []
        item_colors = []
        
        for item in items:
            # Get item attributes
            categories = item.get("categories", [])
            tags = item.get("tags", [])
            
            # Detect styles
            for style, info in self.style_taxonomy.items():
                if any(kw in " ".join(categories + tags).lower() for kw in info["keywords"]):
                    item_styles.append(style)
            
            # Extract colors (simplified)
            for color_family, colors in self.color_families.items():
                for color in colors:
                    if color in " ".join(tags).lower():
                        item_colors.append(color)
        
        # Calculate style coherence
        style_counter = Counter(item_styles)
        dominant_style = style_counter.most_common(1)[0][0] if style_counter else None
        
        style_coherence = "high" if len(set(item_styles)) <= 2 else "medium" if len(set(item_styles)) <= 3 else "low"
        
        # Calculate color harmony
        color_families = []
        for color in item_colors:
            for family, colors in self.color_families.items():
                if color in colors:
                    color_families.append(family)
                    break
        
        color_harmony = "high" if len(set(color_families)) <= 2 else "medium" if len(set(color_families)) <= 3 else "low"
        
        # Calculate overall harmony score
        style_score = 1.0 if style_coherence == "high" else 0.7 if style_coherence == "medium" else 0.4
        color_score = 1.0 if color_harmony == "high" else 0.7 if color_harmony == "medium" else 0.4
        
        harmony_score = (style_score + color_score) / 2
        
        # Generate recommendations
        recommendations = []
        if style_coherence == "low":
            recommendations.append(f"Focus on {dominant_style} style for better coherence")
        if color_harmony == "low":
            recommendations.append("Limit color palette to 2-3 color families")
        
        return {
            "harmony_score": harmony_score,
            "style_coherence": style_coherence,
            "dominant_style": dominant_style,
            "color_harmony": color_harmony,
            "recommendations": recommendations,
            "confidence": 0.75
        }
    
    async def get_seasonal_intelligence(
        self,
        season: str
    ) -> Dict[str, Any]:
        """
        Get seasonal style intelligence.
        
        Args:
            season: Season name
            
        Returns:
            Seasonal intelligence
        """
        season_lower = season.lower()
        
        intelligence = {
            "season": season,
            "color_palette": self.seasonal_colors.get(season_lower, []),
            "key_items": self.trend_indicators["seasonal"].get(season_lower, []),
            "style_tips": [],
            "confidence": 0.8
        }
        
        # Add season-specific tips
        if season_lower == "spring":
            intelligence["style_tips"] = [
                "Layer light pieces",
                "Incorporate florals",
                "Choose fresh colors"
            ]
        elif season_lower == "summer":
            intelligence["style_tips"] = [
                "Opt for breathable fabrics",
                "Embrace bright colors",
                "Keep it minimal"
            ]
        elif season_lower == "autumn":
            intelligence["style_tips"] = [
                "Layer with texture",
                "Add warm tones",
                "Mix patterns"
            ]
        elif season_lower == "winter":
            intelligence["style_tips"] = [
                "Focus on warmth",
                "Add rich colors",
                "Layer strategically"
            ]
        
        return intelligence
    
    async def analyze_trend_potential(
        self,
        item_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze trend potential of an item.
        
        Args:
            item_attributes: Item characteristics
            
        Returns:
            Trend potential analysis
        """
        # Extract relevant text
        categories = item_attributes.get("categories", [])
        tags = item_attributes.get("tags", [])
        description = item_attributes.get("description", "")
        
        all_text = " ".join(categories + tags + [description]).lower()
        
        # Check against current trends
        trend_matches = [
            trend for trend in self.trend_indicators["2024_trends"]
            if trend in all_text
        ]
        
        # Check for timeless qualities
        timeless_matches = [
            item for item in self.trend_indicators["timeless"]
            if item in all_text
        ]
        
        # Calculate scores
        trend_score = len(trend_matches) / len(self.trend_indicators["2024_trends"]) if self.trend_indicators["2024_trends"] else 0
        timeless_score = len(timeless_matches) / len(self.trend_indicators["timeless"]) if self.trend_indicators["timeless"] else 0
        
        # Determine trend status
        if trend_score > 0.3:
            status = "on-trend"
        elif timeless_score > 0.2:
            status = "timeless"
        else:
            status = "classic"
        
        return {
            "trend_status": status,
            "trend_score": trend_score,
            "timeless_score": timeless_score,
            "matching_trends": trend_matches[:3],  # Top 3
            "longevity": "high" if timeless_score > 0.3 else "medium" if timeless_score > 0.1 else "seasonal",
            "confidence": 0.7
        }