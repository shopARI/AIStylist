"""
Ensemble Recommender - COMPLETE INTELLIGENCE PROVIDER FOR CAMEL AGENTS
Coordinates ML systems to provide intelligence to battle agents
NEVER provides direct recommendations - only insights
Compatible with CAMEL-AI 0.2.64, ready for 0.2.7
"""

import logging
import asyncio
import json
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import Counter, defaultdict, OrderedDict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import hashlib

logger = logging.getLogger("ensemble_recommender")


@dataclass
class IntelligencePacket:
    """Structured intelligence data"""
    source: str
    target_agent: str  # 'cypher', 'vibe', or 'shared'
    intelligence_type: str
    data: Dict[str, Any]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target_agent,
            "type": self.intelligence_type,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }


class IntelligenceRouter:
    """Routes intelligence to appropriate CAMEL agents"""
    
    def __init__(self):
        # Define routing rules based on intelligence type
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
                    "graph_pattern_detector"
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
                    "aesthetic_scorer"
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
                    "session_manager"
                ]
            }
        }
    
    def route_intelligence(
        self,
        source_name: str,
        intelligence_type: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Determine which agent should receive this intelligence
        
        Returns:
            'cypher', 'vibe', or 'shared'
        """
        source_lower = source_name.lower()
        type_lower = intelligence_type.lower()
        
        # Check source-based routing
        for target, rules in self.routing_rules.items():
            for source_pattern in rules["sources"]:
                if source_pattern in source_lower:
                    return target
        
        # Check keyword-based routing
        for target, rules in self.routing_rules.items():
            for keyword in rules["keywords"]:
                if keyword in type_lower or keyword in source_lower:
                    return target
        
        # Check data content for routing hints
        if isinstance(data, dict):
            data_str = json.dumps(data).lower()
            
            # Count keyword matches
            keyword_counts = {}
            for target, rules in self.routing_rules.items():
                count = sum(1 for kw in rules["keywords"] if kw in data_str)
                keyword_counts[target] = count
            
            # Route to target with most matches
            if keyword_counts:
                best_target = max(keyword_counts, key=keyword_counts.get)
                if keyword_counts[best_target] > 0:
                    return best_target
        
        # Default to shared
        return "shared"


class IntelligenceAggregator:
    """Aggregates and processes intelligence from multiple sources"""
    
    def __init__(self):
        self.intelligence_buffer = OrderedDict()
        self.max_buffer_size = 1000
        self.aggregation_window = timedelta(seconds=5)
    
    def add_intelligence(self, packet: IntelligencePacket):
        """Add intelligence packet to buffer"""
        key = f"{packet.source}:{packet.intelligence_type}:{packet.timestamp.timestamp()}"
        self.intelligence_buffer[key] = packet
        
        # Maintain buffer size
        if len(self.intelligence_buffer) > self.max_buffer_size:
            # Remove oldest entries
            for _ in range(len(self.intelligence_buffer) - self.max_buffer_size):
                self.intelligence_buffer.popitem(last=False)
    
    def aggregate_recent(
        self,
        window: Optional[timedelta] = None
    ) -> Dict[str, List[IntelligencePacket]]:
        """
        Aggregate recent intelligence by target agent
        
        Returns:
            Dict mapping target agents to intelligence packets
        """
        window = window or self.aggregation_window
        cutoff_time = datetime.now() - window
        
        aggregated = defaultdict(list)
        
        for packet in self.intelligence_buffer.values():
            if packet.timestamp >= cutoff_time:
                aggregated[packet.target_agent].append(packet)
        
        return dict(aggregated)
    
    def get_confidence_scores(self) -> Dict[str, float]:
        """Calculate aggregate confidence scores by source"""
        source_confidences = defaultdict(list)
        
        for packet in self.intelligence_buffer.values():
            source_confidences[packet.source].append(packet.confidence)
        
        # Calculate average confidence per source
        return {
            source: sum(confs) / len(confs)
            for source, confs in source_confidences.items()
        }


class MLSystemCoordinator:
    """Coordinates multiple ML systems to provide intelligence"""
    
    def __init__(self):
        self.ml_systems = {}
        self.system_weights = {}
        self.system_stats = defaultdict(lambda: {
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "total_time": 0.0,
            "avg_confidence": 0.0
        })
    
    def register_ml_system(
        self,
        name: str,
        system: Any,
        weight: float = 1.0
    ):
        """Register an ML system"""
        self.ml_systems[name] = system
        self.system_weights[name] = weight
        logger.info(f"Registered ML system: {name} (weight: {weight})")
    
    async def gather_intelligence(
        self,
        query: str,
        user_id: Optional[str],
        session_id: Optional[str],
        product_id: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> List[IntelligencePacket]:
        """
        Gather intelligence from all ML systems
        
        Returns:
            List of intelligence packets
        """
        if not self.ml_systems:
            return []
        
        # Create tasks for parallel execution
        tasks = []
        for name, system in self.ml_systems.items():
            task = self._get_system_intelligence(
                name, system, query, user_id,
                session_id, product_id, context
            )
            tasks.append((name, task))
        
        # Execute all tasks
        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True
        )
        
        # Process results into intelligence packets
        packets = []
        for (name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                self._record_system_failure(name, result)
            elif result:
                self._record_system_success(name, result)
                packets.extend(result)
        
        return packets
    
    async def _get_system_intelligence(
        self,
        name: str,
        system: Any,
        query: str,
        user_id: Optional[str],
        session_id: Optional[str],
        product_id: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> List[IntelligencePacket]:
        """Get intelligence from a specific ML system"""
        start_time = time.time()
        packets = []
        
        try:
            # Different intelligence extraction based on system type
            intelligence_data = await self._extract_intelligence_by_type(
                name, system, query, user_id,
                session_id, product_id, context
            )
            
            # Convert to intelligence packets
            if intelligence_data:
                for intel_type, data in intelligence_data.items():
                    if data and isinstance(data, dict):
                        confidence = data.get("confidence", 0.5) * self.system_weights[name]
                        
                        packet = IntelligencePacket(
                            source=name,
                            target_agent="",  # Will be set by router
                            intelligence_type=intel_type,
                            data=data,
                            confidence=min(confidence, 1.0)
                        )
                        packets.append(packet)
            
            # Update stats
            elapsed = time.time() - start_time
            self.system_stats[name]["calls"] += 1
            self.system_stats[name]["successes"] += 1
            self.system_stats[name]["total_time"] += elapsed
            
        except Exception as e:
            logger.error(f"Error getting intelligence from {name}: {e}")
            self.system_stats[name]["calls"] += 1
            self.system_stats[name]["failures"] += 1
        
        return packets
    
    async def _extract_intelligence_by_type(
        self,
        name: str,
        system: Any,
        query: str,
        user_id: Optional[str],
        session_id: Optional[str],
        product_id: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract intelligence based on system type"""
        intelligence = {}
        
        # Clustering systems
        if "cluster" in name.lower():
            intelligence.update(
                await self._extract_cluster_intelligence(
                    system, query, product_id
                )
            )
        
        # Visual/aesthetic systems
        if "visual" in name.lower() or "aesthetic" in name.lower():
            intelligence.update(
                await self._extract_visual_intelligence(
                    system, product_id, query
                )
            )
        
        # RFM/behavioral systems
        if "rfm" in name.lower() or "behavior" in name.lower():
            intelligence.update(
                await self._extract_behavioral_intelligence(
                    system, user_id
                )
            )
        
        # Memory/context systems
        if "memory" in name.lower() or "context" in name.lower():
            intelligence.update(
                await self._extract_contextual_intelligence(
                    system, user_id, session_id, query
                )
            )
        
        # Generic extraction for unknown types
        if not intelligence:
            intelligence.update(
                await self._extract_generic_intelligence(
                    system, query, user_id, product_id
                )
            )
        
        return intelligence
    
    async def _extract_cluster_intelligence(
        self,
        system: Any,
        query: str,
        product_id: Optional[str]
    ) -> Dict[str, Any]:
        """Extract clustering intelligence"""
        intelligence = {}
        
        try:
            if hasattr(system, "get_cluster_analysis"):
                analysis = await asyncio.to_thread(
                    system.get_cluster_analysis,
                    query=query,
                    product_id=product_id
                )
                intelligence["cluster_analysis"] = {
                    "clusters": analysis.get("clusters", []),
                    "keywords": analysis.get("keywords", []),
                    "distribution": analysis.get("distribution", {}),
                    "coherence": analysis.get("coherence", 0.5),
                    "confidence": 0.8
                }
            
            if product_id and hasattr(system, "get_product_cluster"):
                cluster_info = await asyncio.to_thread(
                    system.get_product_cluster,
                    product_id
                )
                intelligence["product_cluster"] = {
                    "cluster_id": cluster_info.get("cluster_id"),
                    "neighbors": cluster_info.get("neighbors", []),
                    "characteristics": cluster_info.get("characteristics", {}),
                    "confidence": 0.85
                }
        
        except Exception as e:
            logger.warning(f"Cluster intelligence extraction error: {e}")
        
        return intelligence
    
    async def _extract_visual_intelligence(
        self,
        system: Any,
        product_id: Optional[str],
        query: str
    ) -> Dict[str, Any]:
        """Extract visual/aesthetic intelligence"""
        intelligence = {}
        
        try:
            if product_id and hasattr(system, "analyze_visual_features"):
                features = await asyncio.to_thread(
                    system.analyze_visual_features,
                    product_id
                )
                intelligence["visual_features"] = {
                    "colors": features.get("dominant_colors", []),
                    "patterns": features.get("patterns", []),
                    "textures": features.get("textures", []),
                    "style_attributes": features.get("styles", []),
                    "complexity": features.get("complexity", "medium"),
                    "aesthetic_score": features.get("score", 0.5),
                    "confidence": 0.9
                }
            
            if hasattr(system, "analyze_style_query"):
                style_analysis = await asyncio.to_thread(
                    system.analyze_style_query,
                    query
                )
                intelligence["style_analysis"] = {
                    "inferred_styles": style_analysis.get("styles", []),
                    "mood": style_analysis.get("mood", "neutral"),
                    "formality": style_analysis.get("formality", "casual"),
                    "season": style_analysis.get("season"),
                    "confidence": 0.7
                }
        
        except Exception as e:
            logger.warning(f"Visual intelligence extraction error: {e}")
        
        return intelligence
    
    async def _extract_behavioral_intelligence(
        self,
        system: Any,
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Extract behavioral intelligence"""
        intelligence = {}
        
        if not user_id:
            return intelligence
        
        try:
            if hasattr(system, "get_user_segment"):
                segment = await asyncio.to_thread(
                    system.get_user_segment,
                    user_id
                )
                intelligence["user_segment"] = {
                    "segment": segment.get("segment", "standard"),
                    "tier": segment.get("tier", "regular"),
                    "recency": segment.get("recency_score", 0),
                    "frequency": segment.get("frequency_score", 0),
                    "monetary": segment.get("monetary_score", 0),
                    "lifetime_value": segment.get("ltv", 0),
                    "confidence": 0.85
                }
            
            if hasattr(system, "get_purchase_patterns"):
                patterns = await asyncio.to_thread(
                    system.get_purchase_patterns,
                    user_id
                )
                intelligence["purchase_patterns"] = {
                    "frequent_items": patterns.get("frequent", []),
                    "associations": patterns.get("rules", []),
                    "seasonality": patterns.get("seasonal", {}),
                    "brand_loyalty": patterns.get("brands", {}),
                    "price_sensitivity": patterns.get("price_range", {}),
                    "confidence": 0.75
                }
        
        except Exception as e:
            logger.warning(f"Behavioral intelligence extraction error: {e}")
        
        return intelligence
    
    async def _extract_contextual_intelligence(
        self,
        system: Any,
        user_id: Optional[str],
        session_id: Optional[str],
        query: str
    ) -> Dict[str, Any]:
        """Extract contextual intelligence"""
        intelligence = {}
        
        try:
            if hasattr(system, "get_relevant_memories"):
                memories = await asyncio.to_thread(
                    system.get_relevant_memories,
                    user_id=user_id,
                    session_id=session_id,
                    query=query,
                    k=5
                )
                intelligence["memory_context"] = {
                    "relevant_memories": memories,
                    "memory_count": len(memories),
                    "confidence": 0.9 if memories else 0.3
                }
            
            if hasattr(system, "get_session_context"):
                session_context = await asyncio.to_thread(
                    system.get_session_context,
                    session_id
                )
                intelligence["session_context"] = {
                    "intent": session_context.get("intent"),
                    "conversation_stage": session_context.get("stage"),
                    "topics": session_context.get("topics", []),
                    "mood": session_context.get("mood"),
                    "confidence": 0.8
                }
            
            if user_id and hasattr(system, "get_user_preferences"):
                preferences = await asyncio.to_thread(
                    system.get_user_preferences,
                    user_id
                )
                intelligence["user_preferences"] = {
                    "styles": preferences.get("preferred_styles", []),
                    "brands": preferences.get("preferred_brands", []),
                    "categories": preferences.get("preferred_categories", []),
                    "colors": preferences.get("preferred_colors", []),
                    "avoid": preferences.get("avoid_list", []),
                    "budget": preferences.get("budget_range", {}),
                    "confidence": 0.85
                }
        
        except Exception as e:
            logger.warning(f"Contextual intelligence extraction error: {e}")
        
        return intelligence
    
    async def _extract_generic_intelligence(
        self,
        system: Any,
        query: str,
        user_id: Optional[str],
        product_id: Optional[str]
    ) -> Dict[str, Any]:
        """Extract generic intelligence from unknown system types"""
        intelligence = {}
        
        try:
            # Try various common method names
            if hasattr(system, "get_intelligence"):
                intel = await asyncio.to_thread(
                    system.get_intelligence,
                    query=query,
                    user_id=user_id,
                    product_id=product_id
                )
                intelligence["generic_intelligence"] = intel
            
            elif hasattr(system, "analyze"):
                analysis = await asyncio.to_thread(
                    system.analyze,
                    query
                )
                intelligence["generic_analysis"] = analysis
            
            elif hasattr(system, "get_insights"):
                insights = await asyncio.to_thread(
                    system.get_insights,
                    query=query
                )
                intelligence["generic_insights"] = insights
        
        except Exception as e:
            logger.warning(f"Generic intelligence extraction error: {e}")
        
        return intelligence
    
    def _record_system_success(self, name: str, packets: List[IntelligencePacket]):
        """Record successful intelligence extraction"""
        if packets:
            avg_confidence = sum(p.confidence for p in packets) / len(packets)
            
            current_avg = self.system_stats[name]["avg_confidence"]
            total_successes = self.system_stats[name]["successes"]
            
            # Update running average
            self.system_stats[name]["avg_confidence"] = (
                (current_avg * total_successes + avg_confidence) /
                (total_successes + 1)
            )
    
    def _record_system_failure(self, name: str, error: Exception):
        """Record failed intelligence extraction"""
        logger.error(f"ML system {name} failed: {error}")
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get statistics for all ML systems"""
        stats = {}
        
        for name, system_stats in self.system_stats.items():
            if system_stats["calls"] > 0:
                stats[name] = {
                    "success_rate": system_stats["successes"] / system_stats["calls"] * 100,
                    "avg_response_time": system_stats["total_time"] / system_stats["calls"],
                    "avg_confidence": system_stats["avg_confidence"],
                    "total_calls": system_stats["calls"],
                    "weight": self.system_weights.get(name, 1.0)
                }
        
        return stats


class EnsembleRecommender:
    """
    Coordinates ML recommenders to provide intelligence for CAMEL battle agents.
    
    KEY PRINCIPLE: This class NEVER returns products, only intelligence!
    - Gathers insights from multiple ML systems
    - Routes intelligence to appropriate CAMEL agents
    - Enhances battle quality without bypassing it
    """
    
    def __init__(self):
        """Initialize the ensemble intelligence coordinator"""
        logger.info("Initializing Ensemble Intelligence Provider")
        logger.info("Purpose: Provide ML intelligence to CAMEL agents")
        logger.info("Note: NEVER provides direct recommendations!")
        
        # Core components
        self.router = IntelligenceRouter()
        self.aggregator = IntelligenceAggregator()
        self.coordinator = MLSystemCoordinator()
        
        # Tracking
        self.intelligence_requests = 0
        self.intelligence_provided = 0
        self.last_intelligence_time = None
        
        # Configuration
        self.config = {
            "enable_routing": True,
            "enable_aggregation": True,
            "enable_caching": True,
            "cache_ttl": 60,  # seconds
            "min_confidence": 0.3
        }
        
        # Intelligence cache
        self.intelligence_cache = OrderedDict()
        self.max_cache_size = 100
        
        logger.info("Ensemble intelligence coordinator ready")
    
    def add_recommender(
        self,
        recommender,
        weight: float = 1.0,
        name: Optional[str] = None
    ) -> bool:
        """
        Add an ML recommender that will provide intelligence
        
        Args:
            recommender: ML recommender instance
            weight: Importance weight
            name: Name of the recommender
            
        Returns:
            Success status
        """
        if recommender is None:
            logger.warning("Cannot add None recommender")
            return False
        
        if name is None:
            name = recommender.__class__.__name__
        
        self.coordinator.register_ml_system(name, recommender, weight)
        return True
    
    async def provide_intelligence_for_battle(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        product_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Coordinate ML systems to provide intelligence for CAMEL battle agents
        
        THIS IS THE ONLY PUBLIC METHOD - WE DON'T PROVIDE RECOMMENDATIONS!
        
        Args:
            query: Search query
            user_id: User ID for behavioral analysis
            session_id: Session ID for context
            product_id: Reference product for similarity
            context: Additional context
            
        Returns:
            Intelligence dictionary for CAMEL agents
        """
        self.intelligence_requests += 1
        start_time = time.time()
        
        logger.info(f"Gathering ML intelligence for: '{query[:50] if query else 'general'}...'")
        
        # Check cache if enabled
        if self.config["enable_caching"]:
            cache_key = self._create_cache_key(
                query, user_id, session_id, product_id
            )
            
            if cache_key in self.intelligence_cache:
                cached = self.intelligence_cache[cache_key]
                # Check if cache is still valid
                if (datetime.now() - cached["timestamp"]).seconds < self.config["cache_ttl"]:
                    logger.info("Using cached intelligence")
                    return cached["intelligence"]
        
        # Gather intelligence from all ML systems
        packets = await self.coordinator.gather_intelligence(
            query, user_id, session_id, product_id, context
        )
        
        # Route intelligence packets to appropriate agents
        if self.config["enable_routing"]:
            for packet in packets:
                packet.target_agent = self.router.route_intelligence(
                    packet.source,
                    packet.intelligence_type,
                    packet.data
                )
        
        # Add to aggregator if enabled
        if self.config["enable_aggregation"]:
            for packet in packets:
                self.aggregator.add_intelligence(packet)
        
        # Build final intelligence structure
        intelligence = self._build_intelligence_structure(packets)
        
        # Update tracking
        elapsed = time.time() - start_time
        self.last_intelligence_time = elapsed
        
        if intelligence["metadata"]["sources"]:
            self.intelligence_provided += 1
        
        # Cache if enabled
        if self.config["enable_caching"] and cache_key:
            self._cache_intelligence(cache_key, intelligence)
        
        # Log summary
        self._log_intelligence_summary(intelligence, elapsed)
        
        return intelligence
    
    def _build_intelligence_structure(
        self,
        packets: List[IntelligencePacket]
    ) -> Dict[str, Any]:
        """Build the final intelligence structure for battle agents"""
        intelligence = {
            "cypher_intel": {},
            "vibe_intel": {},
            "shared_intel": {},
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "sources": [],
                "packet_count": len(packets),
                "confidence_scores": {},
                "routing_distribution": Counter()
            }
        }
        
        # Filter by minimum confidence
        packets = [
            p for p in packets
            if p.confidence >= self.config["min_confidence"]
        ]
        
        # Organize packets by target agent
        for packet in packets:
            target = packet.target_agent
            source = packet.source
            intel_type = packet.intelligence_type
            
            # Add to appropriate section
            if target == "cypher":
                if source not in intelligence["cypher_intel"]:
                    intelligence["cypher_intel"][source] = {}
                intelligence["cypher_intel"][source][intel_type] = packet.data
            
            elif target == "vibe":
                if source not in intelligence["vibe_intel"]:
                    intelligence["vibe_intel"][source] = {}
                intelligence["vibe_intel"][source][intel_type] = packet.data
            
            else:  # shared
                if source not in intelligence["shared_intel"]:
                    intelligence["shared_intel"][source] = {}
                intelligence["shared_intel"][source][intel_type] = packet.data
            
            # Update metadata
            if source not in intelligence["metadata"]["sources"]:
                intelligence["metadata"]["sources"].append(source)
            
            intelligence["metadata"]["confidence_scores"][source] = max(
                intelligence["metadata"]["confidence_scores"].get(source, 0),
                packet.confidence
            )
            
            intelligence["metadata"]["routing_distribution"][target] += 1
        
        # Calculate overall confidence
        if intelligence["metadata"]["confidence_scores"]:
            intelligence["metadata"]["overall_confidence"] = sum(
                intelligence["metadata"]["confidence_scores"].values()
            ) / len(intelligence["metadata"]["confidence_scores"])
        else:
            intelligence["metadata"]["overall_confidence"] = 0.0
        
        # Add aggregated insights if available
        if self.config["enable_aggregation"]:
            aggregated = self.aggregator.aggregate_recent()
            intelligence["metadata"]["aggregated_insights"] = {
                target: len(packets)
                for target, packets in aggregated.items()
            }
        
        return intelligence
    
    def _create_cache_key(
        self,
        query: str,
        user_id: Optional[str],
        session_id: Optional[str],
        product_id: Optional[str]
    ) -> str:
        """Create cache key for intelligence"""
        key_parts = [
            query or "",
            user_id or "",
            session_id or "",
            product_id or ""
        ]
        
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _cache_intelligence(
        self,
        cache_key: str,
        intelligence: Dict[str, Any]
    ):
        """Cache intelligence with timestamp"""
        self.intelligence_cache[cache_key] = {
            "intelligence": intelligence,
            "timestamp": datetime.now()
        }
        
        # Maintain cache size
        if len(self.intelligence_cache) > self.max_cache_size:
            # Remove oldest entry
            self.intelligence_cache.popitem(last=False)
    
    def _log_intelligence_summary(
        self,
        intelligence: Dict[str, Any],
        elapsed_time: float
    ):
        """Log summary of gathered intelligence"""
        cypher_count = len(intelligence["cypher_intel"])
        vibe_count = len(intelligence["vibe_intel"])
        shared_count = len(intelligence["shared_intel"])
        confidence = intelligence["metadata"].get("overall_confidence", 0)
        sources = intelligence["metadata"].get("sources", [])
        
        logger.info(
            f"Intelligence gathered in {elapsed_time:.2f}s: "
            f"CypherBot={cypher_count}, VibeBot={vibe_count}, "
            f"Shared={shared_count}, Confidence={confidence:.2f}"
        )
        
        if sources:
            logger.info(f"Sources: {', '.join(sources)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        return {
            "requests": {
                "total": self.intelligence_requests,
                "successful": self.intelligence_provided,
                "success_rate": (
                    self.intelligence_provided / self.intelligence_requests * 100
                    if self.intelligence_requests > 0 else 0
                )
            },
            "performance": {
                "last_response_time": self.last_intelligence_time,
                "cache_size": len(self.intelligence_cache),
                "cache_enabled": self.config["enable_caching"]
            },
            "ml_systems": self.coordinator.get_system_stats(),
            "routing": {
                "enabled": self.config["enable_routing"],
                "rules": self.router.routing_rules
            },
            "aggregation": {
                "enabled": self.config["enable_aggregation"],
                "buffer_size": len(self.aggregator.intelligence_buffer),
                "confidence_scores": self.aggregator.get_confidence_scores()
            },
            "configuration": self.config,
            "provides_recommendations": False,  # NEVER!
            "provides_intelligence": True  # ALWAYS!
        }
    
    def update_config(self, config_updates: Dict[str, Any]):
        """Update configuration"""
        self.config.update(config_updates)
        logger.info(f"Configuration updated: {config_updates}")
    
    def clear_cache(self):
        """Clear intelligence cache"""
        self.intelligence_cache.clear()
        logger.info("Intelligence cache cleared")