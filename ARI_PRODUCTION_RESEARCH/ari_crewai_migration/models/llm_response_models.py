"""
Pydantic models for LLM structured outputs (response_format).
Used for direct LLM.call() without agent overhead.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class CypherQuery(BaseModel):
    """Single Cypher query with metadata."""
    query: str = Field(..., description="The Cypher query string")
    strategy: str = Field(..., description="Search strategy name (e.g., COLLABORATIVE, CATEGORY_FOCUSED)")
    reasoning: str = Field(..., description="Why this query is appropriate")


class CypherQueries(BaseModel):
    """
    Structured output for CypherBot query generation.
    LLM generates optimized Cypher queries based on user intent.
    """
    main_query: str = Field(..., description="Primary Cypher query for product search")
    fallback_query: Optional[str] = Field(None, description="Fallback query if main fails")
    search_strategy: str = Field(
        ...,
        description="Strategy used: COLLABORATIVE, CATEGORY_FOCUSED, BRAND_RELATIONSHIPS, OCCASION_PATTERNS, or GENERAL"
    )
    reasoning: str = Field(..., description="Explanation of strategy and query design")

    class Config:
        json_schema_extra = {
            "example": {
                "main_query": "MATCH (p:Product)-[:BOUGHT_WITH]->(:Product)<-[:BOUGHT]-(u:User) WHERE p.occasion = 'wedding' RETURN p LIMIT 10",
                "fallback_query": "MATCH (p:Product) WHERE p.occasion = 'wedding' RETURN p LIMIT 10",
                "search_strategy": "OCCASION_PATTERNS",
                "reasoning": "Wedding context requires elegant formal attire, using occasion-based pattern matching"
            }
        }


class SearchStrategy(BaseModel):
    """
    Structured output for VibeBot search strategy selection.
    LLM determines the best vector search approach.
    """
    strategy: str = Field(
        ...,
        description="Strategy: SEMANTIC (text embedding), VISUAL (image similarity), COLOR (color-based), STYLE (style-based), or GENERAL"
    )
    reasoning: str = Field(..., description="Why this strategy is appropriate for the query")
    search_terms: List[str] = Field(default_factory=list, description="Key terms or concepts to emphasize")

    class Config:
        json_schema_extra = {
            "example": {
                "strategy": "SEMANTIC",
                "reasoning": "Query emphasizes aesthetic qualities requiring semantic similarity matching",
                "search_terms": ["elegant", "sophisticated", "timeless"]
            }
        }


class VisualSearchStrategy(BaseModel):
    """
    Structured output for VisionBot visual search strategy.
    LLM determines how to approach visual similarity search.
    """
    strategy: str = Field(
        ...,
        description="Strategy: VISUAL_SIMILARITY, COLOR_BASED_VISUAL, STYLE_VISUAL, TEXTURE_VISUAL, or GENERAL_VISUAL"
    )
    reasoning: str = Field(..., description="Why this visual strategy is appropriate")
    visual_features: List[str] = Field(
        default_factory=list,
        description="Key visual features to prioritize (color, pattern, silhouette, texture)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "strategy": "VISUAL_SIMILARITY",
                "reasoning": "Query describes visual characteristics that require image-based matching",
                "visual_features": ["flowing silhouette", "floral pattern", "light colors"]
            }
        }


class ProductEvaluation(BaseModel):
    """Evaluation of a single product by the judge."""
    product_id: str = Field(..., description="Product UUID")
    quality_score: float = Field(..., ge=0, le=1, description="Quality score (0-1)")
    relevance_score: float = Field(..., ge=0, le=1, description="Relevance to query (0-1)")
    reasoning: str = Field(..., description="Why this product was scored this way")
    include: bool = Field(..., description="Whether to include in final recommendations")


class JudgeEvaluation(BaseModel):
    """
    Structured output for Judge evaluation of search results.
    LLM evaluates quality, detects consensus, and selects best products.
    """
    evaluations: List[ProductEvaluation] = Field(
        default_factory=list,
        description="Individual product evaluations"
    )
    consensus_product_ids: List[str] = Field(
        default_factory=list,
        description="Product IDs found by multiple search agents"
    )
    final_product_ids: List[str] = Field(
        ...,
        description="Ordered list of product IDs to include in final recommendations"
    )
    overall_reasoning: str = Field(
        ...,
        description="Overall justification for selection decisions"
    )
    judgment_confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in the recommendations (0-1)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "evaluations": [
                    {
                        "product_id": "550e8400-e29b-41d4-a716-446655440000",
                        "quality_score": 0.95,
                        "relevance_score": 0.92,
                        "reasoning": "Perfect match for wedding occasion with high quality",
                        "include": True
                    }
                ],
                "consensus_product_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                "final_product_ids": ["550e8400-e29b-41d4-a716-446655440000", "..."],
                "overall_reasoning": "Selected products balance quality, consensus, and occasion appropriateness",
                "judgment_confidence": 0.92
            }
        }
