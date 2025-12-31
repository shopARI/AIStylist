"""
ML Intelligence Coordinator for CAMEL Battle Agents

Coordinates all ML systems to provide intelligence packets to battle agents.
CRITICAL: This coordinator NEVER returns products, only intelligence!

Based on enhanced_recommender_manager_async.py patterns.
"""

import time
import logging
import asyncio
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from .router import IntelligenceRouter

from functools import lru_cache

from neo4j import AsyncGraphDatabase, AsyncSession
from typing import AsyncContextManager
import asyncio
from contextlib import asynccontextmanager

# @lru_cache(maxsize=1000)
# async def gather_intelligence_cached(self, cache_key: str):
#     # Implementation

logger = logging.getLogger("intelligence.coordinator")


class IntelligenceCoordinator:
    """
    Manages ML systems that provide intelligence to CAMEL battle agents.
    
    ARCHITECTURE:
    - ML systems analyze patterns and provide insights
    - These insights are fed to CypherBot and VibeBot CAMEL agents
    - The CAMEL agents use this intelligence in their Neo4j/Qdrant searches
    - Battle system remains the ONLY path to recommendations
    """
    

    def __init__(
        self,
        data_store: Optional[Any] = None,
        user_kg: Optional[Any] = None,
        product_retriever: Optional[Any] = None,
        memory_setup_func: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the intelligence coordinator.
        
        Args:
            data_store: HybridDataStore for ML analysis
            user_kg: User knowledge graph for behavioral analysis
            product_retriever: Product retriever for ML analysis
            memory_setup_func: Memory setup for context-aware ML
            config: Configuration dictionary
        """
        
         # ADD: Connection pool configuration
        self.neo4j_pool = None
        self.qdrant_pool = None
        
        # Initialize pools if services available
        if user_kg:
            self.neo4j_pool = self._create_neo4j_pool(user_kg)
        if product_retriever:
            self.qdrant_pool = self._create_qdrant_pool(product_retriever)
        
        logger.info("Initializing ML Intelligence Coordinator")
        logger.info("Purpose: Provide ML intelligence to CAMEL agents")
        logger.info("Note: NEVER provides direct recommendations!")
        
        self.data_store = data_store
        self.user_kg = user_kg
        self.product_retriever = product_retriever
        self.memory_setup_func = memory_setup_func
        
        # Configuration
        self.config = config or {}
        
        # ML systems registry
        self.ml_systems = {}
        self.system_weights = {}
        
        # Intelligence router
        self.router = IntelligenceRouter()
        
        # Track statistics
        self.stats = {
            "total_intelligence_requests": 0,
            "successful_intelligence_provided": 0,
            "intelligence_by_source": defaultdict(int),
            "intelligence_by_target": defaultdict(int),
            "avg_intelligence_gathering_time": 0.0,
            "last_request_time": None
        }
        
        logger.info("Intelligence Coordinator initialized")
    

    def _create_neo4j_pool(self, user_kg):
        """Reuse existing Neo4j connection pool - DO NOT create duplicate pools"""
        # ALWAYS reuse existing driver to prevent connection bloat
        if hasattr(user_kg, 'driver') and user_kg.driver is not None:
            return user_kg.driver
        else:
            logger.warning("User KG service has no active driver - this may cause failures")
            return None
                
    def _create_qdrant_pool(self, product_retriever):
        """Create Qdrant connection pool"""
        # Return the existing Qdrant client from product retriever
        if hasattr(product_retriever, 'client'):
            return product_retriever.client
        # If no client available, return None - ML systems will handle gracefully
        return None

    @asynccontextmanager
    async def get_neo4j_session(self) -> AsyncContextManager[AsyncSession]:
        """Get session from pool with database selection"""
        if self.neo4j_pool:
            database = os.getenv("NEO4J_DATABASE", "neo4j")
            async with self.neo4j_pool.session(database=database) as session:
                yield session
        else:
            yield None

    def register_intelligence_system(
        self,
        name: str,
        system: Any,
        weight: float = 1.0
    ) -> bool:
        """
        Register an ML system that will provide intelligence.
        
        Args:
            name: Name of the ML system
            system: ML system instance
            weight: Importance weight for this system
            
        Returns:
            Success status
        """
        if system is None:
            logger.warning(f"Cannot register None system: {name}")
            return False
        
        self.ml_systems[name] = system
        self.system_weights[name] = weight
        logger.info(f"Registered ML system: {name} (weight: {weight})")
        return True
    
    async def gather_intelligence(
        self,
        query: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        product_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Coordinate ML systems to provide intelligence for CAMEL battle agents.
        
        THIS IS THE MAIN METHOD - WE DON'T PROVIDE RECOMMENDATIONS!
        
        Args:
            query: Search query
            user_id: User ID for behavioral analysis
            session_id: Session ID for context
            product_id: Reference product for similarity
            context: Additional context
            
        Returns:
            Intelligence dictionary with:
            - cypher_intel: For CypherBot (data-driven)
            - vibe_intel: For VibeBot (aesthetic)
            - shared_intel: For both agents (context)
        """
        self.stats["total_intelligence_requests"] += 1
        start_time = time.time()
        
        logger.info(f"Gathering ML intelligence for query: '{query[:50] if query else 'general'}...'")
        
        # Initialize intelligence structure
        intelligence = {
            "cypher_intel": {},  # For CypherBot's Neo4j queries
            "vibe_intel": {},    # For VibeBot's Qdrant searches
            "shared_intel": {},  # For both agents
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "sources": [],
                "gathering_time": 0.0
            }
        }
        
        if not self.ml_systems:
            logger.warning("No ML systems registered")
            return intelligence
        
        # Gather intelligence from all systems in parallel
        tasks = []
        
        for name, system in self.ml_systems.items():
            task = self._get_system_intelligence(
                name, system, query, user_id, session_id, product_id, context
            )
            tasks.append((name, task))
        
        # Execute all tasks
        # results = await asyncio.gather(
        #     *[task for _, task in tasks],
        #     return_exceptions=True
        # )
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[task for _, task in tasks], return_exceptions=True),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            logger.error("Intelligence gathering timeout")

        # Process results
        for (name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"Error getting intelligence from {name}: {result}")
                continue
            
            if result and isinstance(result, dict):
                # Route intelligence to appropriate agent
                target = self.router.route_intelligence(name, result)
                
                # Add to appropriate section
                if target == "cypher":
                    intelligence["cypher_intel"][name] = result
                elif target == "vibe":
                    intelligence["vibe_intel"][name] = result
                else:  # shared
                    intelligence["shared_intel"][name] = result
                
                # Update metadata
                intelligence["metadata"]["sources"].append(name)
                self.stats["intelligence_by_source"][name] += 1
                self.stats["intelligence_by_target"][target] += 1
        
        # Calculate gathering time
        elapsed = time.time() - start_time
        intelligence["metadata"]["gathering_time"] = elapsed
        
        # Update statistics
        if intelligence["metadata"]["sources"]:
            self.stats["successful_intelligence_provided"] += 1
            
            # Update average gathering time
            total = self.stats["successful_intelligence_provided"]
            current_avg = self.stats["avg_intelligence_gathering_time"]
            self.stats["avg_intelligence_gathering_time"] = (
                (current_avg * (total - 1) + elapsed) / total
            )
        
        self.stats["last_request_time"] = datetime.now().isoformat()
        
        logger.info(
            f"Gathered intelligence from {len(intelligence['metadata']['sources'])} sources "
            f"in {elapsed:.2f}s"
        )
        
        return intelligence
    
    async def gather_intelligence_batch(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Gather intelligence for multiple requests in batch.
        
        Args:
            requests: List of request dictionaries with keys:
                - query, user_id, session_id, product_id, context
                
        Returns:
            List of intelligence dictionaries
        """
        # Group by type for batch processing
        user_ids = list(set(r.get('user_id') for r in requests if r.get('user_id')))
        product_ids = list(set(r.get('product_id') for r in requests if r.get('product_id')))
        
        # Batch load data
        batch_data = {}
        
        # Load behavioral data in batch
        if user_ids and 'behavioral' in self.ml_systems:
            behavioral = self.ml_systems['behavioral']
            if hasattr(behavioral, 'load_transactions_batch'):
                batch_data['behavioral'] = await behavioral.load_transactions_batch(user_ids)
        
        # Load clustering data in batch
        if product_ids and 'clustering' in self.ml_systems:
            clustering = self.ml_systems['clustering']
            if hasattr(clustering, 'get_product_clusters_batch'):
                batch_data['clusters'] = await clustering.get_product_clusters_batch(product_ids)
        
        # Process each request with cached batch data
        results = []
        for request in requests:
            # Use batch data instead of individual queries
            intelligence = await self._gather_with_cache(request, batch_data)
            results.append(intelligence)
        
        return results

    async def _get_system_intelligence(
        self,
        name: str,
        system: Any,
        query: Optional[str],
        user_id: Optional[str],
        session_id: Optional[str],
        product_id: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Get intelligence from a specific ML system.
        
        Args:
            name: System name
            system: ML system instance
            query: Search query
            user_id: User ID
            session_id: Session ID
            product_id: Product ID
            context: Additional context
            
        Returns:
            Intelligence data or None
        """
        try:
            # Different methods based on system type
            intelligence = {}
            
            # Clustering systems (for CypherBot)
            if "cluster" in name.lower():
                if product_id and hasattr(system, "get_product_cluster"):
                    cluster_info = await self._safe_async_call(
                        system.get_product_cluster, product_id
                    )
                    if cluster_info:
                        intelligence["cluster_analysis"] = {
                            "cluster_id": cluster_info.get("cluster_id"),
                            "characteristics": cluster_info.get("characteristics"),
                            "keywords": cluster_info.get("keywords", []),
                            "confidence": 0.8 * self.system_weights.get(name, 1.0)
                        }
                
                elif query and hasattr(system, "find_relevant_clusters"):
                    clusters = await self._safe_async_call(
                        system.find_relevant_clusters, query
                    )
                    if clusters:
                        intelligence["relevant_clusters"] = {
                            "clusters": clusters,
                            "confidence": 0.6 * self.system_weights.get(name, 1.0)
                        }
            
            # Visual systems (for VibeBot)
            elif "visual" in name.lower():
                # Query-based visual analysis (NEW: Always run for fashion queries)
                if query and hasattr(system, "analyze_query_visual_patterns"):
                    print(f"ML COORDINATOR: Calling Visual Intelligence for query analysis...")
                    logger.info(f"ML Coordinator running visual query analysis for: '{query[:30]}...'")
                    query_analysis = await self._safe_async_call(
                        system.analyze_query_visual_patterns, query, context
                    )
                    if query_analysis:
                        intelligence["query_visual_analysis"] = {
                            "visual_cues": query_analysis.get("visual_cues", {}),
                            "style_analysis": query_analysis.get("style_analysis", {}),
                            "search_enhancements": query_analysis.get("search_enhancements", {}),
                            "visual_relevance_score": query_analysis.get("query_visual_score", 0.5),
                            "confidence": query_analysis.get("confidence", 0.75) * self.system_weights.get(name, 1.0),
                            "source": "query_analysis"
                        }
                        print(f"   Visual Intelligence data prepared for VibeBot")
                        logger.info(f"Visual query analysis completed for: {query[:30]}...")

                # Product-specific visual analysis (existing functionality)
                if product_id and hasattr(system, "get_visual_features"):
                    features = await self._safe_async_call(
                        system.get_visual_features, product_id
                    )
                    if features:
                        intelligence["product_visual_analysis"] = {
                            "colors": features.get("dominant_colors", []),
                            "styles": features.get("style_attributes", []),
                            "aesthetic_score": features.get("aesthetic_score", 0.5),
                            "confidence": 0.85 * self.system_weights.get(name, 1.0),
                            "source": "product_analysis"
                        }
            
            # Behavioral systems (for CypherBot)
            elif "rfm" in name.lower() or "behavioral" in name.lower():
                if user_id and hasattr(system, "get_user_segment"):
                    segment = await self._safe_async_call(
                        system.get_user_segment, user_id
                    )
                    if segment:
                        intelligence["user_segment"] = {
                            "segment": segment.get("segment", "standard"),
                            "tier": segment.get("tier", "regular"),
                            "value_score": segment.get("monetary", 0),
                            "confidence": 0.75 * self.system_weights.get(name, 1.0)
                        }
                
                if user_id and hasattr(system, "get_purchase_patterns"):
                    patterns = await self._safe_async_call(
                        system.get_purchase_patterns, user_id
                    )
                    if patterns:
                        intelligence["purchase_patterns"] = {
                            "frequent_items": patterns.get("frequent", []),
                            "associations": patterns.get("rules", []),
                            "confidence": 0.7 * self.system_weights.get(name, 1.0)
                        }
            
            # Memory/RAG systems (for both agents)
            elif "memory" in name.lower() or "rag" in name.lower():
                if hasattr(system, "get_relevant_context"):
                    context_data = await self._safe_async_call(
                        system.get_relevant_context,
                        user_id=user_id,
                        session_id=session_id,
                        query=query
                    )
                    if context_data:
                        intelligence["memory_context"] = {
                            "memories": context_data.get("memories", []),
                            "preferences": context_data.get("preferences", {}),
                            "interactions": context_data.get("interactions", []),
                            "confidence": 0.9 * self.system_weights.get(name, 1.0)
                        }
            
            return intelligence if intelligence else None
            
        except Exception as e:
            logger.error(f"Error getting intelligence from {name}: {e}")
            return None
    
    async def _safe_async_call(self, func, *args, **kwargs):
        """
        Safely call a function that might be sync or async.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result or None
        """
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # Run sync function in thread pool
                return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as e:
            logger.warning(f"Error in safe async call: {e}")
            return None
    
    async def record_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str
    ):
        """
        Record user interaction for ML learning.
        
        Args:
            user_id: User ID
            product_id: Product ID
            interaction_type: Type of interaction
        """
        # Update ML systems with feedback
        tasks = []
        
        for name, system in self.ml_systems.items():
            if hasattr(system, "add_interaction"):
                task = self._safe_async_call(
                    system.add_interaction,
                    user_id, product_id, interaction_type
                )
                tasks.append(task)
            elif hasattr(system, "add_transaction") and interaction_type == "purchased":
                task = self._safe_async_call(
                    system.add_transaction,
                    user_id, product_id
                )
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get coordinator statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()
        
        # Calculate success rate
        if stats["total_intelligence_requests"] > 0:
            stats["success_rate"] = (
                stats["successful_intelligence_provided"] / 
                stats["total_intelligence_requests"] * 100
            )
        else:
            stats["success_rate"] = 0
        
        # Add ML system status
        stats["ml_systems_active"] = list(self.ml_systems.keys())
        stats["provides_recommendations"] = False  # NEVER!
        stats["enhances_battles"] = True  # ALWAYS!
        
        return stats