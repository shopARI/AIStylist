"""
Intelligence Router for CAMEL Battle Agents

Routes intelligence to appropriate CAMEL agents based on keywords and content.
CRITICAL: This determines which agent (CypherBot vs VibeBot) gets what intelligence!

Based on ensemble_recommender.py IntelligenceRouter (lines 50-134).
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("intelligence.router")


@dataclass
class IntelligencePacket:
    """Structured intelligence data packet"""
    source: str
    target_agent: str  # 'cypher', 'vibe', or 'shared'
    intelligence_type: str
    data: Dict[str, Any]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "source": self.source,
            "target": self.target_agent,
            "type": self.intelligence_type,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }


class IntelligenceRouter:
    """
    Routes intelligence to appropriate CAMEL agents.
    
    CRITICAL ROUTING RULES (from ensemble_recommender.py lines 80-108):
    - CypherBot: Gets data-driven intelligence (graph, behavioral, clustering)
    - VibeBot: Gets aesthetic intelligence (visual, style, trends)
    - Both: Get contextual intelligence (memory, preferences)
    """
    
    def __init__(self):
        """Initialize the intelligence router with routing rules."""
        # EXACT routing rules from ensemble_recommender.py lines 82-108
        self.routing_rules = {
            # Data-driven intelligence goes to CypherBot
            "cypher": {
                "keywords": [
                    "cluster", "rfm", "segment", "behavior", "pattern",
                    "collaborative", "graph", "relationship", "purchase",
                    "frequency", "monetary", "recency", "association"
                ],
                "sources": [
                    "multi_cluster_recommender",
                    "rfm_apriori_recommender",
                    "behavioral_analyzer",
                    "graph_pattern_detector",
                    "clustering",
                    "behavioral"
                ]
            },
            # Aesthetic intelligence goes to VibeBot
            "vibe": {
                "keywords": [
                    "visual", "style", "aesthetic", "color", "design",
                    "trend", "fashion", "vibe", "look", "appearance",
                    "texture", "pattern", "silhouette", "mood"
                ],
                "sources": [
                    "hybrid_visual_recommender",
                    "style_analyzer",
                    "trend_detector",
                    "aesthetic_scorer",
                    "visual",
                    "visual_pytorch"
                ]
            },
            # Contextual intelligence goes to both
            "shared": {
                "keywords": [
                    "memory", "context", "preference", "history", "session",
                    "interaction", "feedback", "profile", "intent"
                ],
                "sources": [
                    "memory_rag_recommender",
                    "context_analyzer",
                    "preference_tracker",
                    "session_manager",
                    "memory_rag"
                ]
            }
        }
        
        # Track routing statistics
        self.routing_stats = {
            "total_routed": 0,
            "routed_to_cypher": 0,
            "routed_to_vibe": 0,
            "routed_to_shared": 0
        }
        
        logger.info("Intelligence Router initialized with keyword-based routing")
    
    def route_intelligence(
        self,
        source_name: str,
        intelligence_data: Dict[str, Any]
    ) -> str:
        """
        Determine which agent should receive this intelligence.
        
        Based on ensemble_recommender.py route_intelligence method (lines 110-176).
        
        Args:
            source_name: Name of the intelligence source
            intelligence_data: Intelligence data to route
            
        Returns:
            'cypher', 'vibe', or 'shared'
        """
        source_lower = source_name.lower()
        
        # Update statistics
        self.routing_stats["total_routed"] += 1
        
        # Check source-based routing first (most specific)
        for target, rules in self.routing_rules.items():
            for source_pattern in rules["sources"]:
                if source_pattern in source_lower:
                    self._update_stats(target)
                    logger.debug(f"Routed {source_name} to {target} by source match")
                    return target
        
        # Check intelligence type keywords
        if isinstance(intelligence_data, dict):
            # Get all text from intelligence data for keyword matching
            data_str = self._extract_text_from_data(intelligence_data)
            data_lower = data_str.lower()
            
            # Count keyword matches for each target
            keyword_counts = {}
            for target, rules in self.routing_rules.items():
                count = sum(1 for kw in rules["keywords"] if kw in data_lower)
                keyword_counts[target] = count
            
            # Route to target with most keyword matches
            if keyword_counts:
                best_target = max(keyword_counts, key=keyword_counts.get)
                if keyword_counts[best_target] > 0:
                    self._update_stats(best_target)
                    logger.debug(
                        f"Routed {source_name} to {best_target} by keyword match "
                        f"(count: {keyword_counts[best_target]})"
                    )
                    return best_target
        
        # Default to shared if no clear match
        self._update_stats("shared")
        logger.debug(f"Routed {source_name} to shared (default)")
        return "shared"
    
    def route_packet(self, packet: IntelligencePacket) -> str:
        """
        Route an intelligence packet to the appropriate agent.
        
        Args:
            packet: IntelligencePacket to route
            
        Returns:
            Target agent: 'cypher', 'vibe', or 'shared'
        """
        target = self.route_intelligence(packet.source, packet.data)
        packet.target_agent = target
        return target
    
    def _extract_text_from_data(self, data: Any, max_depth: int = 3, max_size: int = 10000) -> str:

        """
        Extract all text content from nested data structure.
        
        Args:
            data: Data to extract text from
            max_depth: Maximum recursion depth
            
        Returns:
            Concatenated text string
        """
        if len(text_parts) > max_size:
            return " ".join(text_parts[:max_size])
        
        if max_depth <= 0:
            return ""
        
        text_parts = []
        
        if isinstance(data, str):
            text_parts.append(data)
        elif isinstance(data, dict):
            for key, value in data.items():
                text_parts.append(str(key))
                text_parts.append(self._extract_text_from_data(value, max_depth - 1))
        elif isinstance(data, (list, tuple)):
            for item in data:
                text_parts.append(self._extract_text_from_data(item, max_depth - 1))
        else:
            text_parts.append(str(data))
        
        return " ".join(filter(None, text_parts))
    
    def _update_stats(self, target: str):
        """Update routing statistics."""
        if target == "cypher":
            self.routing_stats["routed_to_cypher"] += 1
        elif target == "vibe":
            self.routing_stats["routed_to_vibe"] += 1
        else:
            self.routing_stats["routed_to_shared"] += 1
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = self.routing_stats.copy()
        
        # Calculate percentages
        total = stats["total_routed"]
        if total > 0:
            stats["cypher_percentage"] = (stats["routed_to_cypher"] / total) * 100
            stats["vibe_percentage"] = (stats["routed_to_vibe"] / total) * 100
            stats["shared_percentage"] = (stats["routed_to_shared"] / total) * 100
        else:
            stats["cypher_percentage"] = 0
            stats["vibe_percentage"] = 0
            stats["shared_percentage"] = 0
        
        return stats
    
    def update_routing_rules(
        self,
        target: str,
        keywords: Optional[List[str]] = None,
        sources: Optional[List[str]] = None
    ):
        """
        Update routing rules dynamically.
        
        Args:
            target: Target agent ('cypher', 'vibe', or 'shared')
            keywords: Additional keywords to add
            sources: Additional sources to add
        """
        if target not in self.routing_rules:
            logger.warning(f"Invalid target: {target}")
            return
        
        if keywords:
            current_keywords = set(self.routing_rules[target]["keywords"])
            current_keywords.update(keywords)
            self.routing_rules[target]["keywords"] = list(current_keywords)
            logger.info(f"Added {len(keywords)} keywords to {target} routing")
        
        if sources:
            current_sources = set(self.routing_rules[target]["sources"])
            current_sources.update(sources)
            self.routing_rules[target]["sources"] = list(current_sources)
            logger.info(f"Added {len(sources)} sources to {target} routing")
    
    def get_routing_rules(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Get current routing rules.
        
        Returns:
            Copy of routing rules dictionary
        """
        return {
            target: {
                "keywords": rules["keywords"].copy(),
                "sources": rules["sources"].copy()
            }
            for target, rules in self.routing_rules.items()
        }