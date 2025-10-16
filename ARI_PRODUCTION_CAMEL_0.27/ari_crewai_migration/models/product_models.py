"""
Pydantic models for structured CrewAI output.
Eliminates 107-line regex parser!
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class Product(BaseModel):
    """Single product model with validation."""
    id: str = Field(..., description="Unique product identifier (UUID)")
    title: str = Field(..., description="Product name")
    price: float = Field(..., gt=0, description="Product price (must be positive)")
    category: str = Field(..., description="Product category")
    images: List[str] = Field(default_factory=list, description="Product image URLs")

    # Optional fields
    description: Optional[str] = Field(None, description="Product description")
    brand: Optional[str] = Field(None, description="Product brand")
    colors: Optional[List[str]] = Field(default_factory=list, description="Available colors")
    in_stock: bool = Field(default=True, description="Availability status")

    # Agent-specific scores
    cypher_score: Optional[float] = Field(None, ge=0, le=1, description="CypherBot relevance score")
    vibe_score: Optional[float] = Field(None, ge=0, le=1, description="VibeBot relevance score")
    visual_score: Optional[float] = Field(None, ge=0, le=1, description="VisionBot relevance score")
    judge_score: Optional[float] = Field(None, ge=0, le=1, description="Judge quality score")

    # Metadata
    agent_source: Optional[str] = Field(None, description="Which agent found this product")
    search_method: Optional[str] = Field(None, description="Search method used")
    reasoning: Optional[str] = Field(None, description="Why this product was selected")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Elegant Black Dress",
                "price": 129.99,
                "category": "dress",
                "images": ["https://example.com/image.jpg"],
                "cypher_score": 0.95,
                "agent_source": "CypherBot"
            }
        }


class GraphSearchResult(BaseModel):
    """Output from Graph Search Crew (CypherBot)."""
    products: List[Product] = Field(default_factory=list, description="Products found via graph search")
    search_strategy: str = Field(..., description="Strategy used (e.g., COLLABORATIVE, CATEGORY_FOCUSED)")
    reasoning: str = Field(..., description="Why this strategy was chosen")
    execution_time: float = Field(..., gt=0, description="Execution time in seconds")
    products_found: int = Field(..., ge=0, description="Number of products found")

    class Config:
        json_schema_extra = {
            "example": {
                "products": [],
                "search_strategy": "COLLABORATIVE",
                "reasoning": "Wedding context requires formal attire with collaborative filtering...",
                "execution_time": 2.5,
                "products_found": 10
            }
        }


class VectorSearchResult(BaseModel):
    """Output from Vector Search Crew (VibeBot)."""
    products: List[Product] = Field(default_factory=list, description="Products found via vector search")
    search_strategy: str = Field(..., description="Strategy used (e.g., SEMANTIC, VISUAL, COLOR)")
    reasoning: str = Field(..., description="Why this strategy was chosen")
    execution_time: float = Field(..., gt=0, description="Execution time in seconds")
    products_found: int = Field(..., ge=0, description="Number of products found")

    class Config:
        json_schema_extra = {
            "example": {
                "products": [],
                "search_strategy": "SEMANTIC",
                "reasoning": "Semantic similarity for aesthetic matching...",
                "execution_time": 1.8,
                "products_found": 8
            }
        }


class VisualSearchResult(BaseModel):
    """Output from Visual Search Crew (VisionBot)."""
    products: List[Product] = Field(default_factory=list, description="Products found via visual search")
    search_strategy: str = Field(..., description="Strategy used (e.g., VISUAL_SIMILARITY)")
    reasoning: str = Field(..., description="Why this strategy was chosen")
    execution_time: float = Field(..., gt=0, description="Execution time in seconds")
    products_found: int = Field(..., ge=0, description="Number of products found")

    class Config:
        json_schema_extra = {
            "example": {
                "products": [],
                "search_strategy": "VISUAL_SIMILARITY",
                "reasoning": "Visual similarity matching using FashionSigLIP embeddings...",
                "execution_time": 2.1,
                "products_found": 6
            }
        }


class JudgmentResult(BaseModel):
    """Output from Judge Evaluation Crew (Judge Ari)."""
    final_products: List[Product] = Field(default_factory=list, description="Top ranked products after quality control")
    quality_assessments: Dict[str, float] = Field(default_factory=dict, description="Quality scores by product ID")
    consensus_products: List[str] = Field(default_factory=list, description="Product IDs found by multiple agents")
    rejected_products: List[Dict[str, str]] = Field(default_factory=list, description="Rejected products with reasons")
    judgment_confidence: float = Field(..., ge=0, le=1, description="Overall confidence in recommendations")
    detailed_reasoning: str = Field(..., description="Explanation of selection criteria and decisions")
    execution_time: float = Field(..., gt=0, description="Execution time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "final_products": [],
                "quality_assessments": {"product-id-1": 0.95},
                "consensus_products": ["product-id-1", "product-id-2"],
                "rejected_products": [{"id": "product-id-3", "reason": "Low quality score"}],
                "judgment_confidence": 0.92,
                "detailed_reasoning": "Selected products based on quality, consensus, and occasion appropriateness...",
                "execution_time": 1.5
            }
        }


class ProductSearchState(BaseModel):
    """Flow state - tracks execution through all steps."""
    # Input
    query: str = Field(..., description="User search query")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Search filters")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum products to return")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    ml_intelligence: Dict[str, Any] = Field(default_factory=dict, description="ML-generated context")
    conversation_context: Dict[str, Any] = Field(default_factory=dict, description="Conversation state")

    # Intermediate results
    graph_result: Optional[GraphSearchResult] = Field(None, description="Graph search output")
    vector_result: Optional[VectorSearchResult] = Field(None, description="Vector search output")
    visual_result: Optional[VisualSearchResult] = Field(None, description="Visual search output")
    judgment_result: Optional[JudgmentResult] = Field(None, description="Judge evaluation output")

    # Execution metadata
    current_step: str = Field(default="initialized", description="Current execution step")
    start_time: Optional[datetime] = Field(default=None, description="Flow start time")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")

    # Timeouts
    parallel_search_timeout: int = Field(default=90, description="Timeout for parallel search step (seconds)")
    individual_crew_timeout: int = Field(default=30, description="Timeout per individual crew (seconds)")
    judge_timeout: int = Field(default=30, description="Timeout for judge step (seconds)")

    class Config:
        arbitrary_types_allowed = True


class ProductSearchResult(BaseModel):
    """Final output from ProductSearchFlow."""
    products: List[Product] = Field(default_factory=list, description="Final product recommendations")
    reasoning: str = Field(..., description="Overall reasoning and strategy")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata")
    execution_time: float = Field(..., gt=0, description="Total execution time in seconds")

    # Source counts
    graph_count: int = Field(default=0, description="Products from graph search")
    vector_count: int = Field(default=0, description="Products from vector search")
    visual_count: int = Field(default=0, description="Products from visual search")
    consensus_count: int = Field(default=0, description="Products found by multiple agents")

    # Quality metrics
    quality_controlled: bool = Field(default=False, description="Whether judge quality control was applied")
    average_quality_score: Optional[float] = Field(None, ge=0, le=1, description="Average quality score")

    class Config:
        json_schema_extra = {
            "example": {
                "products": [],
                "reasoning": "Selected 5 products based on quality, consensus, and occasion appropriateness...",
                "execution_time": 5.2,
                "graph_count": 10,
                "vector_count": 8,
                "visual_count": 6,
                "consensus_count": 3,
                "quality_controlled": True,
                "average_quality_score": 0.87
            }
        }
