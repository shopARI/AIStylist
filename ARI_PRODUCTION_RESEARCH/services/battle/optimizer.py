"""
Battle Optimizer - Optimizes battle parameters based on context
Based on optimization patterns from ai_stylist_app_async.py
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("services.battle.optimizer")

class BattleOptimizer:
    """
    Optimizes battle parameters based on query context and user profile.
    Implements the optimization logic from ai_stylist_app_async.py.
    """
    
    def __init__(self):
        """Initialize the battle optimizer."""
        # Optimization rules from ai_stylist_app_async.py
        self.optimization_rules = {
            "luxury": {
                "prefetch_multiplier": 3,
                "quality_threshold": 0.9,
                "timeout_extension": 1.5,
                "require_consensus": True,
                "include_details": True
            },
            "specific_item": {
                "prefetch_multiplier": 1.5,
                "quality_threshold": 0.2,
                "timeout_extension": 0.8,
                "require_consensus": False,
                "include_details": True
            },
            "occasion": {
                "prefetch_multiplier": 2.5,
                "quality_threshold": 0.2,
                "timeout_extension": 1.2,
                "require_consensus": False,
                "include_details": True
            },
            "wardrobe": {
                "prefetch_multiplier": 4,
                "quality_threshold": 0.2,
                "timeout_extension": 2.0,
                "require_consensus": False,
                "include_coordination": True
            },
            "vip": {
                "prefetch_multiplier": 3.5,
                "quality_threshold": 0.95,
                "timeout_extension": 1.6,
                "require_consensus": True,
                "include_details": True
            },
            "standard": {
                "prefetch_multiplier": 2,
                "quality_threshold": 0.2,
                "timeout_extension": 1.0,
                "require_consensus": False,
                "include_details": False
            }
        }
        
        # Keyword mappings for context detection
        from config.fashion_vocabulary import SPECIFIC_ITEMS
        self.context_keywords = {
            "luxury": ["couture", "designer", "luxury", "high-end", "exclusive", "bespoke", "premium"],
            "specific_item": SPECIFIC_ITEMS,
            "occasion": ["wedding", "gala", "event", "party", "formal", "dinner", "date", "interview"],
            "wardrobe": ["wardrobe", "capsule", "collection", "essentials", "basics", "complete"],
            "trending": ["trending", "popular", "latest", "new", "hot", "viral"]
        }
        
        logger.info("BattleOptimizer initialized with optimization rules")
    
    def optimize(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        base_limit: int = 5,
        base_timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Optimize battle parameters based on context.
        
        Args:
            query: Search query
            user_context: User information
            ml_intelligence: ML insights
            base_limit: Base result limit
            base_timeout: Base timeout in seconds
            
        Returns:
            Optimized parameters dictionary
        """
        # Detect context type
        context_type = self._detect_context(query, user_context, ml_intelligence)
        
        # Get optimization rules for context
        rules = self.optimization_rules.get(context_type, self.optimization_rules["standard"])
        
        # Calculate optimized parameters
        optimized = {
            "prefetch_limit": int(base_limit * rules["prefetch_multiplier"]),
            "quality_threshold": rules["quality_threshold"],
            "timeout": base_timeout * rules["timeout_extension"],
            "require_consensus": rules.get("require_consensus", False),
            "include_details": rules.get("include_details", False),
            "context_type": context_type
        }
        
        # Add coordination flag for wardrobe building
        if rules.get("include_coordination"):
            optimized["include_coordination"] = True
        
        logger.info(f"Optimized for '{context_type}' context: prefetch={optimized['prefetch_limit']}, timeout={optimized['timeout']:.1f}s")
        
        return optimized
    
    def _detect_context(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> str:
        """
        Detect the context type from query and user information.
        
        Returns:
            Context type string
        """
        query_lower = query.lower() if query else ""
        
        # Check for VIP status first (highest priority)
        if user_context and user_context.get("vip_status"):
            logger.debug("VIP context detected from user profile")
            return "vip"
        
        # Check ML intelligence for high-value user
        if ml_intelligence and "cypher_intel" in ml_intelligence:
            for source, data in ml_intelligence["cypher_intel"].items():
                if isinstance(data, dict):
                    if "user_segment" in data:
                        segment = data["user_segment"]
                        if isinstance(segment, dict) and segment.get("tier") == "vip":
                            logger.debug("VIP context detected from ML intelligence")
                            return "vip"
        
        # Check for luxury keywords
        if any(keyword in query_lower for keyword in self.context_keywords["luxury"]):
            logger.debug("Luxury context detected from query")
            return "luxury"
        
        # Check for wardrobe building
        if any(keyword in query_lower for keyword in self.context_keywords["wardrobe"]):
            logger.debug("Wardrobe context detected from query")
            return "wardrobe"
        
        # Check for occasions
        if any(keyword in query_lower for keyword in self.context_keywords["occasion"]):
            logger.debug("Occasion context detected from query")
            return "occasion"
        
        # Check for specific items
        if any(keyword in query_lower for keyword in self.context_keywords["specific_item"]):
            logger.debug("Specific item context detected from query")
            return "specific_item"
        
        # Default to standard
        logger.debug("Standard context (no special markers)")
        return "standard"
    
    def apply_luxury_filters(
        self,
        filters: Dict[str, Any],
        user_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Apply luxury-specific filters.
        
        Args:
            filters: Existing filters
            user_context: User context
            
        Returns:
            Enhanced filters for luxury context
        """
        luxury_filters = filters.copy() if filters else {}
        
        # Luxury brand list
        luxury_brands = [
            "Chanel", "Dior", "Gucci", "Prada", "Versace", "Balenciaga",
            "Saint Laurent", "Bottega Veneta", "Burberry", "Givenchy",
            "Hermès", "Louis Vuitton", "Valentino", "Celine", "Fendi"
        ]
        
        # Apply user's preferred brands or suggest luxury brands
        if user_context and user_context.get('preferred_brands'):
            luxury_filters['brands'] = user_context['preferred_brands']
        else:
            luxury_filters['suggested_brands'] = luxury_brands[:5]
        
        # Set minimum price for luxury items
        if not luxury_filters.get('min_price'):
            luxury_filters['min_price'] = 500
        
        # Add quality indicators
        luxury_filters['quality_indicators'] = ["premium", "luxury", "designer", "exclusive"]
        
        logger.debug(f"Applied luxury filters: min_price=${luxury_filters.get('min_price')}")
        
        return luxury_filters
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """
        Get optimization statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "available_contexts": list(self.optimization_rules.keys()),
            "total_rules": len(self.optimization_rules),
            "keyword_categories": list(self.context_keywords.keys()),
            "luxury_brands_count": 15
        }
    
    def update_rules(self, context_type: str, rules: Dict[str, Any]):
        """
        Update optimization rules for a context type.
        
        Args:
            context_type: Context type to update
            rules: New rules dictionary
        """
        if context_type in self.optimization_rules:
            self.optimization_rules[context_type].update(rules)
            logger.info(f"Updated optimization rules for '{context_type}'")
        else:
            self.optimization_rules[context_type] = rules
            logger.info(f"Added new optimization rules for '{context_type}'")
    
    def add_keywords(self, category: str, keywords: list):
        """
        Add keywords to a category.
        
        Args:
            category: Keyword category
            keywords: List of keywords to add
        """
        if category not in self.context_keywords:
            self.context_keywords[category] = []
        
        # Add unique keywords
        existing = set(self.context_keywords[category])
        new_keywords = [k for k in keywords if k not in existing]
        self.context_keywords[category].extend(new_keywords)
        
        logger.info(f"Added {len(new_keywords)} keywords to '{category}'")
