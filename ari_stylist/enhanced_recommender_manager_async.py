"""
Enhanced Recommender Manager - FEEDS CAMEL BATTLE AGENTS
ML recommenders (clustering, RFM, visual) provide intelligence to CAMEL agents
NEVER bypasses the battle system - only enhances it
Compatible with CAMEL-AI 0.2.64, ready for 0.2.7
"""
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Import ML recommenders that provide intelligence
from multi_cluster_recommender import MultiClusterRecommender
from hybrid_visual_recommender import HybridVisualRecommender
from rfm_apriori_recommender_async import RFMAprioriRecommenderAsync
from memory_rag_recommender import MemoryRAGRecommender
from ensemble_recommender import EnsembleRecommender

logger = logging.getLogger("enhanced_recommender_manager")

class EnhancedRecommenderManagerAsync:
    """
    Manages ML recommenders that provide intelligence to CAMEL battle agents.

    ARCHITECTURE:
    - ML recommenders analyze patterns and provide insights
    - These insights are fed to CypherBot and VibeBot CAMEL agents
    - The CAMEL agents use this intelligence in their Neo4j/Qdrant searches
    - Battle system remains the ONLY path to recommendations
    """

    def __init__(
        self,
        competitive_search_system,  # REQUIRED - the battle system
        data_store=None,  # HybridDataStore for ML analysis
        user_kg=None,  # UserKnowledgeGraphAsync for user analysis
        product_retriever=None,  # For product data access
        memory_setup_func=None  # For memory-based ML
    ):
        """
        Initialize the recommender manager.

        Args:
            competitive_search_system: The CAMEL battle system (REQUIRED!)
            data_store: HybridDataStore for ML recommenders to analyze
            user_kg: User knowledge graph for behavioral analysis
            product_retriever: Product retriever for ML analysis
            memory_setup_func: Memory setup for context-aware ML
        """
        if not competitive_search_system:
            raise ValueError(
                "Battle system is REQUIRED! This manager only provides "
                "intelligence to battles, never bypasses them!"
            )

        logger.info("Initializing ML intelligence provider for CAMEL battle system")

        self.battle_system = competitive_search_system
        self.data_store = data_store
        self.user_kg = user_kg
        self.product_retriever = product_retriever
        self.memory_setup_func = memory_setup_func

        # ML recommenders that provide intelligence
        self.ml_systems = {}
        self.ensemble = None

        # Initialize ML systems
        self._initialize_ml_systems()

        # Track how ML enhances battles
        self.enhancement_stats = {
            "total_battles": 0,
            "ml_enhanced_battles": 0,
            "intelligence_contributions": {},
            "avg_intelligence_gathering_time": 0.0
        }

    def _initialize_ml_systems(self):
        """Initialize ML systems that will provide intelligence."""
        logger.info("Initializing ML intelligence systems")

        try:
            # Multi-cluster for pattern analysis (feeds CypherBot)
            if self.data_store:
                self.ml_systems['multi_cluster'] = MultiClusterRecommender(
                    product_kg=self.data_store,
                    n_clusters=8
                )
                logger.info("Multi-cluster analyzer ready for CypherBot")

            # Visual recommender for aesthetic analysis (feeds VibeBot)
            if self.data_store:
                self.ml_systems['hybrid_visual'] = HybridVisualRecommender(
                    product_kg=self.data_store,
                    storage_path="product_data/visual_embeddings"
                )
                logger.info("Visual analyzer ready for VibeBot")

            # RFM for user behavior analysis (feeds CypherBot)
            if self.data_store and self.user_kg:
                self.ml_systems['rfm_apriori'] = RFMAprioriRecommenderAsync(
                    product_kg=self.data_store,
                    user_kg=self.user_kg,
                    memory_setup_func=self.memory_setup_func
                )
                logger.info("RFM behavioral analyzer ready for CypherBot")

            # Memory RAG for context (feeds both agents)
            if self.data_store and self.user_kg and self.memory_setup_func:
                self.ml_systems['memory_rag'] = MemoryRAGRecommender(
                    product_kg=self.data_store,
                    user_kg=self.user_kg,
                    memory_setup_func=self.memory_setup_func
                )
                logger.info("Memory context analyzer ready for both agents")

            # Ensemble intelligence coordinator
            if self.ml_systems:
                self.ensemble = EnsembleRecommender()
                for name, system in self.ml_systems.items():
                    self.ensemble.add_recommender(system, name=name)
                logger.info("Ensemble intelligence coordinator ready")

        except Exception as e:
            logger.error(f"Error initializing ML systems: {e}")
            logger.warning("Battles will proceed without ML enhancement")

    async def get_recommendations(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        product_id: Optional[str] = None,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations through CAMEL battle system enhanced with ML intelligence.

        THIS ALWAYS GOES THROUGH BATTLES - NO BYPASSES!

        Args:
            user_id: User ID for personalization
            session_id: Session ID for context
            product_id: Reference product for similarity
            query: Search query
            filters: Search filters
            limit: Number of recommendations

        Returns:
            Battle-tested recommendations from Judge Ari
        """
        self.enhancement_stats["total_battles"] += 1

        # Step 1: Gather ML intelligence for the CAMEL agents
        start_intel_time = time.time()

        ml_intelligence = await self._gather_ml_intelligence(
            user_id=user_id,
            session_id=session_id,
            product_id=product_id,
            query=query
        )

        intel_time = time.time() - start_intel_time

        if ml_intelligence:
            self.enhancement_stats["ml_enhanced_battles"] += 1
            logger.info(
                f"Gathered ML intelligence in {intel_time:.2f}s for CAMEL agents"
            )

            # Update average intelligence gathering time
            total = self.enhancement_stats["ml_enhanced_battles"]
            current_avg = self.enhancement_stats["avg_intelligence_gathering_time"]
            self.enhancement_stats["avg_intelligence_gathering_time"] = (
                (current_avg * (total - 1) + intel_time) / total
            )

        # Step 2: Create battle context
        user_context = {
            "user_id": user_id,
            "session_id": session_id,
            "product_id": product_id
        }

        # Step 3: Execute CAMEL battle with ML intelligence
        logger.info(
            f"Executing CAMEL battle for query: '{query or 'general recommendations'}'"
        )

        battle_results = await self.battle_system.execute_battle(
            query=query or self._generate_query(product_id, user_id),
            filters=filters,
            limit=limit,
            user_context=user_context,
            ml_intelligence=ml_intelligence  # This enhances the CAMEL agents!
        )

        logger.info(f"Battle complete: {len(battle_results)} recommendations")

        return battle_results

    async def _gather_ml_intelligence(
        self,
        user_id: Optional[str],
        session_id: Optional[str],
        product_id: Optional[str],
        query: Optional[str]
    ) -> Dict[str, Any]:
        """
        Gather intelligence from ML systems for CAMEL agents.

        Returns:
            Intelligence dict with:
            - cypher_intel: For CypherBot (graph patterns, user behavior)
            - vibe_intel: For VibeBot (visual, aesthetic analysis)
            - shared_intel: For both agents (memory, context)
        """
        if not self.ml_systems:
            return {}

        intelligence = {
            "cypher_intel": {},  # For CypherBot's Neo4j queries
            "vibe_intel": {},    # For VibeBot's Qdrant searches
            "shared_intel": {},  # For both agents
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "sources": []
            }
        }

        # Use ensemble if available for coordinated intelligence
        if self.ensemble:
            ensemble_intel = await self.ensemble.provide_intelligence_for_battle(
                query=query,
                user_id=user_id,
                session_id=session_id,
                product_id=product_id
            )

            # Merge ensemble intelligence
            intelligence.update(ensemble_intel)

        else:
            # Gather intelligence individually
            tasks = []

            # Cluster analysis for CypherBot
            if 'multi_cluster' in self.ml_systems and (product_id or query):
                tasks.append(('cypher', 'clusters',
                    self._get_cluster_intelligence(product_id, query)))

            # Visual analysis for VibeBot
            if 'hybrid_visual' in self.ml_systems and product_id:
                tasks.append(('vibe', 'visual',
                    self._get_visual_intelligence(product_id)))

            # RFM analysis for CypherBot
            if 'rfm_apriori' in self.ml_systems and user_id:
                tasks.append(('cypher', 'rfm',
                    self._get_rfm_intelligence(user_id)))

            # Memory context for both
            if 'memory_rag' in self.ml_systems and (user_id or session_id):
                tasks.append(('shared', 'memory',
                    self._get_memory_intelligence(user_id, session_id, query)))

            # Gather all intelligence in parallel
            if tasks:
                results = await asyncio.gather(
                    *[task for _, _, task in tasks],
                    return_exceptions=True
                )

                # Process results
                for (target, intel_type, _), result in zip(tasks, results):
                    if not isinstance(result, Exception) and result:
                        if target == 'cypher':
                            intelligence["cypher_intel"][intel_type] = result
                        elif target == 'vibe':
                            intelligence["vibe_intel"][intel_type] = result
                        else:  # shared
                            intelligence["shared_intel"][intel_type] = result

                        intelligence["metadata"]["sources"].append(intel_type)

                        # Track contribution
                        if intel_type not in self.enhancement_stats["intelligence_contributions"]:
                            self.enhancement_stats["intelligence_contributions"][intel_type] = 0
                        self.enhancement_stats["intelligence_contributions"][intel_type] += 1

        return intelligence if intelligence["metadata"]["sources"] else {}

    async def _get_cluster_intelligence(
        self,
        product_id: Optional[str],
        query: Optional[str]
    ) -> Dict[str, Any]:
        """Get clustering intelligence for CypherBot."""
        try:
            recommender = self.ml_systems['multi_cluster']

            if product_id and hasattr(recommender, 'get_product_cluster'):
                # Get cluster for reference product
                cluster_info = await asyncio.to_thread(
                    recommender.get_product_cluster,
                    product_id
                )

                return {
                    "cluster_id": cluster_info.get("cluster_id"),
                    "cluster_characteristics": cluster_info.get("characteristics"),
                    "cluster_keywords": cluster_info.get("keywords", []),
                    "confidence": 0.8
                }

            elif query and hasattr(recommender, 'find_relevant_clusters'):
                # Find relevant clusters for query
                clusters = await asyncio.to_thread(
                    recommender.find_relevant_clusters,
                    query
                )

                return {
                    "relevant_clusters": clusters,
                    "confidence": 0.6
                }

        except Exception as e:
            logger.warning(f"Cluster intelligence error: {e}")

        return {}

    async def _get_visual_intelligence(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Get visual intelligence for VibeBot."""
        try:
            recommender = self.ml_systems['hybrid_visual']

            if hasattr(recommender, 'get_visual_features'):
                features = await asyncio.to_thread(
                    recommender.get_visual_features,
                    product_id
                )

                return {
                    "visual_features": features,
                    "dominant_colors": features.get("colors", []),
                    "style_attributes": features.get("styles", []),
                    "aesthetic_score": features.get("aesthetic_score", 0.5),
                    "confidence": 0.85
                }

        except Exception as e:
            logger.warning(f"Visual intelligence error: {e}")

        return {}

    async def _get_rfm_intelligence(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get RFM behavioral intelligence for CypherBot."""
        try:
            recommender = self.ml_systems['rfm_apriori']

            intel = {}

            # Get user segment
            if hasattr(recommender, 'get_user_segment'):
                segment = await recommender.get_user_segment(user_id)
                intel["user_segment"] = segment.get("segment", "standard")
                intel["user_tier"] = segment.get("tier", "regular")
                intel["user_value"] = segment.get("monetary_score", 0)

            # Get purchase patterns
            if hasattr(recommender, 'get_user_patterns'):
                patterns = await recommender.get_user_patterns(user_id)
                intel["frequent_together"] = patterns.get("frequent_items", [])
                intel["purchase_patterns"] = patterns.get("rules", [])

            intel["confidence"] = 0.75
            return intel

        except Exception as e:
            logger.warning(f"RFM intelligence error: {e}")

        return {}

    async def _get_memory_intelligence(
        self,
        user_id: Optional[str],
        session_id: Optional[str],
        query: Optional[str]
    ) -> Dict[str, Any]:
        """Get memory context for both agents."""
        try:
            recommender = self.ml_systems['memory_rag']

            if hasattr(recommender, 'get_relevant_context'):
                context = await recommender.get_relevant_context(
                    user_id=user_id,
                    session_id=session_id,
                    query=query
                )

                return {
                    "relevant_memories": context.get("memories", []),
                    "style_preferences": context.get("preferences", {}),
                    "recent_interactions": context.get("interactions", []),
                    "confidence": 0.9
                }

        except Exception as e:
            logger.warning(f"Memory intelligence error: {e}")

        return {}

    def _generate_query(
        self,
        product_id: Optional[str],
        user_id: Optional[str]
    ) -> str:
        """Generate query when none provided."""
        if product_id:
            return f"Products similar to item {product_id}"
        elif user_id:
            return "Personalized recommendations based on your style"
        else:
            return "Trending fashion recommendations"

    async def record_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str
    ):
        """Record user interaction for ML learning."""
        # Update ML systems with feedback
        tasks = []

        if 'memory_rag' in self.ml_systems:
            tasks.append(
                self.ml_systems['memory_rag'].add_interaction(
                    user_id, product_id, interaction_type
                )
            )

        if 'rfm_apriori' in self.ml_systems and interaction_type == "purchased":
            tasks.append(
                self.ml_systems['rfm_apriori'].add_transaction(
                    user_id, product_id
                )
            )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get enhancement statistics."""
        stats = self.enhancement_stats.copy()

        # Calculate enhancement rate
        if stats["total_battles"] > 0:
            stats["ml_enhancement_rate"] = (
                stats["ml_enhanced_battles"] / stats["total_battles"] * 100
            )
        else:
            stats["ml_enhancement_rate"] = 0

        # Add ML system status
        stats["ml_systems_active"] = list(self.ml_systems.keys())
        stats["provides_recommendations"] = False  # Never!
        stats["enhances_battles"] = True  # Always!

        return stats