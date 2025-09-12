"""
ML Intelligence System for CAMEL Battle Agents

This package provides intelligence to CAMEL battle agents.
CRITICAL: Intelligence systems NEVER return products, only intelligence packets!

The intelligence is routed based on keywords:
- CypherBot: Gets data-driven intelligence (clustering, RFM, behavioral)
- VibeBot: Gets aesthetic intelligence (visual, style, trends)
- Both: Get contextual intelligence (memory, preferences)
"""

from typing import Dict, Any, List, Optional

# Version info
__version__ = "1.0.0"
__camel_version__ = "0.2.70"

# Import intelligence components
from .coordinator import IntelligenceCoordinator
from .router import IntelligenceRouter
from .clustering import ClusteringIntelligence
from .visual_pytorch import VisualIntelligence
from .memory_rag import MemoryRAGIntelligence
from .behavioral import BehavioralIntelligence

# Public API
__all__ = [
    "IntelligenceCoordinator",
    "IntelligenceRouter", 
    "ClusteringIntelligence",
    "VisualIntelligence",
    "MemoryRAGIntelligence",
    "BehavioralIntelligence",
    "create_intelligence_system",
    "get_intelligence_health",
]


def create_intelligence_system(
    data_store: Optional[Any] = None,
    user_kg: Optional[Any] = None,
    product_retriever: Optional[Any] = None,
    memory_setup_func: Optional[Any] = None,
    config: Optional[Dict[str, Any]] = None
) -> IntelligenceCoordinator:
    """
    Factory function to create complete ML intelligence system.
    
    CRITICAL: This system provides intelligence to battle agents,
    it NEVER returns products directly!
    
    Args:
        data_store: HybridDataStore for ML analysis
        user_kg: User knowledge graph for behavioral analysis
        product_retriever: Product retriever for ML analysis
        memory_setup_func: Memory setup for context-aware ML
        config: Configuration overrides
        
    Returns:
        Configured IntelligenceCoordinator
    """
    # Default configuration
    default_config = {
        "enable_clustering": True,
        "enable_visual": True,
        "enable_behavioral": True,
        "enable_memory_rag": True,
        "clustering": {
            "n_clusters": 8,
            "min_cluster_size": 5
        },
        "visual": {
            "model_name": "resnet50",
            "device": "auto"  # auto, cpu, or cuda
        },
        "behavioral": {
            "min_support": 0.01,
            "min_confidence": 0.3,
            "min_lift": 1.0
        },
        "routing": {
            "min_confidence": 0.3,
            "cache_ttl": 60
        }
    }
    
    # Merge with provided config
    if config:
        default_config.update(config)
    
    # Create coordinator
    coordinator = IntelligenceCoordinator(
        data_store=data_store,
        user_kg=user_kg,
        product_retriever=product_retriever,
        memory_setup_func=memory_setup_func,
        config=default_config
    )
    
    # Initialize ML systems based on configuration
    if default_config["enable_clustering"] and data_store:
        clustering = ClusteringIntelligence(
            product_kg=data_store,
            n_clusters=default_config["clustering"]["n_clusters"]
        )
        coordinator.register_intelligence_system(
            "clustering", clustering, weight=1.0
        )
    
    if default_config["enable_visual"] and data_store:
        visual = VisualIntelligence(
            product_kg=data_store,
            model_name=default_config["visual"]["model_name"]
        )
        coordinator.register_intelligence_system(
            "visual", visual, weight=1.2  # Slightly higher weight for visual
        )
    
    if default_config["enable_behavioral"] and data_store and user_kg:
        behavioral = BehavioralIntelligence(
            product_kg=data_store,
            user_kg=user_kg,
            memory_setup_func=memory_setup_func,
            min_support=default_config["behavioral"]["min_support"],
            min_confidence=default_config["behavioral"]["min_confidence"],
            min_lift=default_config["behavioral"]["min_lift"]
        )
        coordinator.register_intelligence_system(
            "behavioral", behavioral, weight=1.1
        )
    
    if default_config["enable_memory_rag"] and data_store and memory_setup_func:
        memory_rag = MemoryRAGIntelligence(
            product_kg=data_store,
            user_kg=user_kg,
            memory_setup_func=memory_setup_func
        )
        coordinator.register_intelligence_system(
            "memory_rag", memory_rag, weight=1.3  # Highest weight for memory
        )
    
    return coordinator


def get_intelligence_health() -> Dict[str, Any]:
    """
    Get health status of intelligence systems.
    
    Returns:
        Health status dictionary
    """
    import torch
    import sklearn
    
    health = {
        "status": "healthy",
        "components": {
            "pytorch": {
                "available": torch is not None,
                "version": torch.__version__ if torch else None,
                "cuda": torch.cuda.is_available() if torch else False
            },
            "sklearn": {
                "available": sklearn is not None,
                "version": sklearn.__version__ if sklearn else None
            }
        },
        "provides_recommendations": False,  # NEVER!
        "provides_intelligence": True,  # ALWAYS!
        "intelligence_types": [
            "clustering",
            "visual",
            "behavioral",
            "memory_context"
        ]
    }
    
    # Check if any component is missing
    if not all([
        health["components"]["pytorch"]["available"],
        health["components"]["sklearn"]["available"]
    ]):
        health["status"] = "degraded"
    
    return health