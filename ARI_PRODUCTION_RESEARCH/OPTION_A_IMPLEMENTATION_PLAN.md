# Option A: CrewAI Flows + Pydantic - Full Implementation Plan
**Status:** APPROVED - Full Speed Ahead 🚀
**Estimated Time:** 20-30 hours
**Target:** Production-ready CrewAI implementation using 2025 best practices

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Implementation Phases](#implementation-phases)
3. [File Structure](#file-structure)
4. [Detailed Implementation Steps](#detailed-implementation-steps)
5. [Testing Strategy](#testing-strategy)
6. [Migration Path](#migration-path)

---

## Architecture Overview

### Current (Broken) Architecture
```
CrewAIOrchestrator
  └── ProductSearchCrew (monolithic)
      ├── 4 agents (cypher, vibe, vision, judge)
      ├── 5 tasks (intelligence, graph_search, vector_search, visual_search, evaluation)
      └── crew.kickoff_async() ← BLACK BOX with infinite loop
```

### New (Flows) Architecture
```
ProductSearchFlow
  ├── State: ProductSearchState (Pydantic)
  ├── Step 1: parallel_search_step()
  │   ├── GraphSearchCrew (mini: 1 agent, 1 task, Pydantic output)
  │   ├── VectorSearchCrew (mini: 1 agent, 1 task, Pydantic output)
  │   └── VisualSearchCrew (mini: 1 agent, 1 task, Pydantic output)
  │   └── asyncio.gather() with individual timeouts ← CONTROLLED
  ├── Step 2: judge_evaluation_step()
  │   └── JudgeCrew (mini: 1 agent, 1 task, Pydantic output)
  └── Step 3: finalize_results_step()
      └── Returns structured ProductSearchResult
```

**Key Improvements:**
- ✅ **Parallel execution** like CAMEL-AI (asyncio.gather)
- ✅ **Timeout per mini-crew** (30s each, total 120s max)
- ✅ **Pydantic structured output** (no regex parsing!)
- ✅ **State visibility** (see what's happening at each step)
- ✅ **Error isolation** (one crew failure doesn't crash all)
- ✅ **Graceful degradation** (can return partial results)

---

## Implementation Phases

### Phase 1: Foundation (5-7 hours)
**Goal:** Create Pydantic models and basic Flow structure

**Deliverables:**
- [ ] Pydantic models (Product, SearchResult, etc.)
- [ ] ProductSearchState model
- [ ] ProductSearchFlow skeleton
- [ ] Basic flow structure with @listen decorators

**Files to Create:**
- `ari_crewai_migration/models/product_models.py`
- `ari_crewai_migration/flows/product_search_flow.py`
- `ari_crewai_migration/flows/__init__.py`

---

### Phase 2: Mini-Crews (6-8 hours)
**Goal:** Break monolithic crew into 4 mini-crews

**Deliverables:**
- [ ] GraphSearchCrew (cypher_bot only, Pydantic output)
- [ ] VectorSearchCrew (vibe_bot only, Pydantic output)
- [ ] VisualSearchCrew (vision_bot only, Pydantic output)
- [ ] JudgeCrew (judge_ari only, Pydantic output)

**Files to Create:**
- `ari_crewai_migration/crews/mini_crews/graph_search_crew.py`
- `ari_crewai_migration/crews/mini_crews/vector_search_crew.py`
- `ari_crewai_migration/crews/mini_crews/visual_search_crew.py`
- `ari_crewai_migration/crews/mini_crews/judge_crew.py`

**Files to Update:**
- `ari_crewai_migration/tasks/graph_search.yaml` (add output_pydantic)
- `ari_crewai_migration/tasks/vector_search.yaml` (add output_pydantic)
- `ari_crewai_migration/tasks/visual_search.yaml` (add output_pydantic)
- `ari_crewai_migration/tasks/result_evaluation.yaml` (add output_pydantic)

---

### Phase 3: Flow Implementation (5-7 hours)
**Goal:** Implement parallel execution and state management

**Deliverables:**
- [ ] parallel_search_step() with asyncio.gather
- [ ] Individual timeout wrappers (30s per crew)
- [ ] judge_evaluation_step()
- [ ] finalize_results_step()
- [ ] State transitions

**Files to Update:**
- `ari_crewai_migration/flows/product_search_flow.py` (complete implementation)

---

### Phase 4: Async Tools (3-4 hours)
**Goal:** Convert blocking tools to async

**Deliverables:**
- [ ] AsyncNeo4jTool
- [ ] AsyncQdrantTool
- [ ] AsyncFashionSigTool

**Files to Create:**
- `ari_crewai_migration/tools/async_neo4j_tools.py`
- `ari_crewai_migration/tools/async_qdrant_tools.py`
- `ari_crewai_migration/tools/async_fashionsig_tools.py`

---

### Phase 5: Integration & Testing (4-6 hours)
**Goal:** Wire up Flow to orchestrator and test

**Deliverables:**
- [ ] Update CrewAIOrchestrator to use Flow
- [ ] Error handling and callbacks
- [ ] Test with real queries
- [ ] Performance benchmarking

**Files to Update:**
- `ari_crewai_migration/crews/crewai_orchestrator.py`

---

## File Structure

```
ari_crewai_migration/
├── models/
│   ├── __init__.py
│   └── product_models.py           # NEW: Pydantic models
├── flows/
│   ├── __init__.py                 # NEW
│   └── product_search_flow.py      # NEW: Main Flow implementation
├── crews/
│   ├── mini_crews/                 # NEW: Mini-crew implementations
│   │   ├── __init__.py
│   │   ├── graph_search_crew.py
│   │   ├── vector_search_crew.py
│   │   ├── visual_search_crew.py
│   │   └── judge_crew.py
│   ├── crewai_orchestrator.py      # UPDATE: Use Flow instead of monolithic crew
│   └── product_search_crew.py      # DEPRECATED: Keep for reference
├── tools/
│   ├── async_neo4j_tools.py        # NEW: Async tools
│   ├── async_qdrant_tools.py       # NEW
│   └── async_fashionsig_tools.py   # NEW
├── tasks/
│   ├── graph_search.yaml           # UPDATE: Add output_pydantic
│   ├── vector_search.yaml          # UPDATE: Add output_pydantic
│   ├── visual_search.yaml          # UPDATE: Add output_pydantic
│   └── result_evaluation.yaml      # UPDATE: Add output_pydantic
└── agents/
    ├── cypher_bot.yaml             # UPDATE: Reference async tools
    ├── vibe_bot.yaml               # UPDATE: Reference async tools
    ├── vision_bot.yaml             # UPDATE: Reference async tools
    └── judge_ari.yaml              # UPDATE: Reference async tools
```

---

## Detailed Implementation Steps

### STEP 1: Create Pydantic Models (1-2 hours)

**File:** `ari_crewai_migration/models/product_models.py`

```python
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
                "reasoning": "Wedding context requires formal attire...",
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


class VisualSearchResult(BaseModel):
    """Output from Visual Search Crew (VisionBot)."""
    products: List[Product] = Field(default_factory=list, description="Products found via visual search")
    search_strategy: str = Field(..., description="Strategy used (e.g., VISUAL_SIMILARITY)")
    reasoning: str = Field(..., description="Why this strategy was chosen")
    execution_time: float = Field(..., gt=0, description="Execution time in seconds")
    products_found: int = Field(..., ge=0, description="Number of products found")


class JudgmentResult(BaseModel):
    """Output from Judge Evaluation Crew (Judge Ari)."""
    final_products: List[Product] = Field(default_factory=list, description="Top ranked products after quality control")
    quality_assessments: Dict[str, float] = Field(default_factory=dict, description="Quality scores by product ID")
    consensus_products: List[str] = Field(default_factory=list, description="Product IDs found by multiple agents")
    rejected_products: List[Dict[str, str]] = Field(default_factory=list, description="Rejected products with reasons")
    judgment_confidence: float = Field(..., ge=0, le=1, description="Overall confidence in recommendations")
    detailed_reasoning: str = Field(..., description="Explanation of selection criteria and decisions")
    execution_time: float = Field(..., gt=0, description="Execution time in seconds")


class ProductSearchState(BaseModel):
    """Flow state - tracks execution through all steps."""
    # Input
    query: str = Field(..., description="User search query")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Search filters")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum products to return")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    ml_intelligence: Dict[str, Any] = Field(default_factory=dict, description="ML-generated context")

    # Intermediate results
    graph_result: Optional[GraphSearchResult] = Field(None, description="Graph search output")
    vector_result: Optional[VectorSearchResult] = Field(None, description="Vector search output")
    visual_result: Optional[VisualSearchResult] = Field(None, description="Visual search output")
    judgment_result: Optional[JudgmentResult] = Field(None, description="Judge evaluation output")

    # Execution metadata
    current_step: str = Field(default="initialized", description="Current execution step")
    start_time: datetime = Field(default_factory=datetime.now, description="Flow start time")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")

    # Timeouts
    parallel_search_timeout: int = Field(default=90, description="Timeout for parallel search step (seconds)")
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

    class Config:
        json_schema_extra = {
            "example": {
                "products": [],
                "reasoning": "Selected 5 products based on...",
                "execution_time": 5.2,
                "graph_count": 10,
                "vector_count": 8,
                "visual_count": 6,
                "consensus_count": 3
            }
        }
```

**Validation:**
- [ ] Run `python -c "from models.product_models import *; print('Models OK')"`
- [ ] Test Pydantic validation with sample data

---

### STEP 2: Create ProductSearchFlow Skeleton (2-3 hours)

**File:** `ari_crewai_migration/flows/product_search_flow.py`

```python
"""
ProductSearchFlow - CrewAI Flow implementation for product search.
Uses 2025 Flow patterns with state management and parallel execution.
"""
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel

from models.product_models import (
    ProductSearchState,
    ProductSearchResult,
    GraphSearchResult,
    VectorSearchResult,
    VisualSearchResult,
    JudgmentResult,
    Product
)

logger = logging.getLogger("crewai.flows.product_search")


class ProductSearchFlow(Flow[ProductSearchState]):
    """
    Flow for product search using parallel mini-crews.

    Architecture:
    1. parallel_search_step: Launch 3 mini-crews in parallel (graph, vector, visual)
    2. judge_evaluation_step: Judge evaluates all results
    3. finalize_results_step: Package final output

    Timeout Strategy:
    - Each mini-crew: 30 seconds max
    - Parallel search total: 90 seconds max
    - Judge evaluation: 30 seconds max
    - Total flow: 120 seconds max
    """

    def __init__(
        self,
        graph_search_crew,
        vector_search_crew,
        visual_search_crew,
        judge_crew
    ):
        """
        Initialize flow with mini-crews.

        Args:
            graph_search_crew: GraphSearchCrew instance
            vector_search_crew: VectorSearchCrew instance
            visual_search_crew: VisualSearchCrew instance
            judge_crew: JudgeCrew instance
        """
        super().__init__()

        self.graph_crew = graph_search_crew
        self.vector_crew = vector_search_crew
        self.visual_crew = visual_search_crew
        self.judge_crew = judge_crew

        logger.info("ProductSearchFlow initialized with 4 mini-crews")

    @start()
    def initialize_search(self):
        """
        Flow entry point - initialize state and route to parallel search.

        Returns:
            str: Next step name ('parallel_search')
        """
        logger.info(f"=== FLOW START: Query='{self.state.query[:50]}...' ===")
        self.state.current_step = "parallel_search"
        self.state.start_time = datetime.now()

        return "parallel_search"

    @listen("parallel_search")
    async def parallel_search_step(self):
        """
        Execute graph, vector, and visual searches in parallel.
        Each mini-crew has 30s timeout. Total step: 90s max.

        Returns:
            str: Next step name ('judge_evaluation' or 'error')
        """
        logger.info("=== STEP 1: PARALLEL SEARCH ===")
        step_start = time.time()

        try:
            # Prepare inputs for all crews
            search_inputs = {
                "query": self.state.query,
                "filters": self.state.filters,
                "limit": self.state.limit * 2,  # Prefetch 2x for judge to filter
                "ml_intelligence": self.state.ml_intelligence,
                "user_context": self.state.user_context
            }

            # Launch all 3 searches in parallel with individual timeouts
            logger.info("Launching 3 mini-crews in parallel...")

            tasks = [
                asyncio.wait_for(
                    self._run_graph_search(search_inputs),
                    timeout=30  # 30s per crew
                ),
                asyncio.wait_for(
                    self._run_vector_search(search_inputs),
                    timeout=30
                ),
                asyncio.wait_for(
                    self._run_visual_search(search_inputs),
                    timeout=30
                )
            ]

            # Execute in parallel with error isolation
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results (handle exceptions gracefully)
            self.state.graph_result = results[0] if not isinstance(results[0], Exception) else None
            self.state.vector_result = results[1] if not isinstance(results[1], Exception) else None
            self.state.visual_result = results[2] if not isinstance(results[2], Exception) else None

            # Log errors but don't fail
            for idx, result in enumerate(results):
                crew_names = ["Graph", "Vector", "Visual"]
                if isinstance(result, Exception):
                    error_msg = f"{crew_names[idx]} search failed: {result}"
                    logger.error(error_msg)
                    self.state.errors.append(error_msg)
                else:
                    logger.info(f"{crew_names[idx]} search: {result.products_found} products in {result.execution_time:.2f}s")

            step_time = time.time() - step_start
            logger.info(f"=== PARALLEL SEARCH COMPLETE: {step_time:.2f}s ===")

            # Route to judge if we have any results
            if any([self.state.graph_result, self.state.vector_result, self.state.visual_result]):
                return "judge_evaluation"
            else:
                logger.warning("All searches failed - no results to judge")
                return "finalize_results"

        except Exception as e:
            logger.error(f"Parallel search step failed: {e}", exc_info=True)
            self.state.errors.append(f"Parallel search error: {e}")
            return "finalize_results"

    async def _run_graph_search(self, inputs: Dict[str, Any]) -> GraphSearchResult:
        """Execute graph search crew and parse Pydantic output."""
        logger.info("  → GraphSearchCrew starting...")
        result = await self.graph_crew.kickoff_async(inputs=inputs)

        # CrewAI returns CrewOutput - extract Pydantic model
        if hasattr(result, 'pydantic') and result.pydantic:
            return result.pydantic
        else:
            raise ValueError("Graph crew did not return Pydantic output")

    async def _run_vector_search(self, inputs: Dict[str, Any]) -> VectorSearchResult:
        """Execute vector search crew and parse Pydantic output."""
        logger.info("  → VectorSearchCrew starting...")
        result = await self.vector_crew.kickoff_async(inputs=inputs)

        if hasattr(result, 'pydantic') and result.pydantic:
            return result.pydantic
        else:
            raise ValueError("Vector crew did not return Pydantic output")

    async def _run_visual_search(self, inputs: Dict[str, Any]) -> VisualSearchResult:
        """Execute visual search crew and parse Pydantic output."""
        logger.info("  → VisualSearchCrew starting...")
        result = await self.visual_crew.kickoff_async(inputs=inputs)

        if hasattr(result, 'pydantic') and result.pydantic:
            return result.pydantic
        else:
            raise ValueError("Visual crew did not return Pydantic output")

    @listen("judge_evaluation")
    async def judge_evaluation_step(self):
        """
        Judge evaluates all search results and selects best products.
        Timeout: 30 seconds.

        Returns:
            str: Next step name ('finalize_results')
        """
        logger.info("=== STEP 2: JUDGE EVALUATION ===")
        step_start = time.time()

        try:
            # Prepare inputs for judge
            judge_inputs = {
                "query": self.state.query,
                "graph_results": self.state.graph_result.products if self.state.graph_result else [],
                "vector_results": self.state.vector_result.products if self.state.vector_result else [],
                "visual_results": self.state.visual_result.products if self.state.visual_result else [],
                "ml_intelligence": self.state.ml_intelligence,
                "user_context": self.state.user_context,
                "limit": self.state.limit
            }

            # Execute judge with timeout
            logger.info("Launching JudgeCrew...")
            result = await asyncio.wait_for(
                self._run_judge(judge_inputs),
                timeout=self.state.judge_timeout
            )

            self.state.judgment_result = result

            step_time = time.time() - step_start
            logger.info(f"=== JUDGE EVALUATION COMPLETE: {len(result.final_products)} products in {step_time:.2f}s ===")

            return "finalize_results"

        except asyncio.TimeoutError:
            logger.error(f"Judge evaluation timed out after {self.state.judge_timeout}s")
            self.state.errors.append("Judge evaluation timeout")
            return "finalize_results"
        except Exception as e:
            logger.error(f"Judge evaluation failed: {e}", exc_info=True)
            self.state.errors.append(f"Judge error: {e}")
            return "finalize_results"

    async def _run_judge(self, inputs: Dict[str, Any]) -> JudgmentResult:
        """Execute judge crew and parse Pydantic output."""
        logger.info("  → JudgeCrew starting...")
        result = await self.judge_crew.kickoff_async(inputs=inputs)

        if hasattr(result, 'pydantic') and result.pydantic:
            return result.pydantic
        else:
            raise ValueError("Judge crew did not return Pydantic output")

    @listen("finalize_results")
    def finalize_results_step(self) -> ProductSearchResult:
        """
        Package final results into ProductSearchResult.
        This is the flow's final output.

        Returns:
            ProductSearchResult: Structured final output
        """
        logger.info("=== STEP 3: FINALIZE RESULTS ===")

        total_time = (datetime.now() - self.state.start_time).total_seconds()

        # Get final products from judgment or fallback to raw results
        if self.state.judgment_result:
            final_products = self.state.judgment_result.final_products
            reasoning = self.state.judgment_result.detailed_reasoning
        else:
            # Fallback: combine all results if judge failed
            all_products = []
            if self.state.graph_result:
                all_products.extend(self.state.graph_result.products)
            if self.state.vector_result:
                all_products.extend(self.state.vector_result.products)
            if self.state.visual_result:
                all_products.extend(self.state.visual_result.products)

            # Deduplicate and limit
            seen = set()
            final_products = []
            for p in all_products:
                if p.id not in seen:
                    seen.add(p.id)
                    final_products.append(p)
                    if len(final_products) >= self.state.limit:
                        break

            reasoning = "Judge evaluation failed - returning combined raw results"

        # Build metadata
        metadata = {
            "execution_steps": [
                "parallel_search",
                "judge_evaluation" if self.state.judgment_result else "judge_failed",
                "finalize_results"
            ],
            "errors": self.state.errors,
            "graph_execution_time": self.state.graph_result.execution_time if self.state.graph_result else 0,
            "vector_execution_time": self.state.vector_result.execution_time if self.state.vector_result else 0,
            "visual_execution_time": self.state.visual_result.execution_time if self.state.visual_result else 0,
            "judge_execution_time": self.state.judgment_result.execution_time if self.state.judgment_result else 0,
            "quality_controlled": bool(self.state.judgment_result),
            "flow_implementation": "ProductSearchFlow_2025"
        }

        # Count sources
        graph_count = len(self.state.graph_result.products) if self.state.graph_result else 0
        vector_count = len(self.state.vector_result.products) if self.state.vector_result else 0
        visual_count = len(self.state.visual_result.products) if self.state.visual_result else 0
        consensus_count = len(self.state.judgment_result.consensus_products) if self.state.judgment_result else 0

        result = ProductSearchResult(
            products=final_products,
            reasoning=reasoning,
            metadata=metadata,
            execution_time=total_time,
            graph_count=graph_count,
            vector_count=vector_count,
            visual_count=visual_count,
            consensus_count=consensus_count
        )

        logger.info(f"=== FLOW COMPLETE: {len(final_products)} products in {total_time:.2f}s ===")

        return result


async def create_and_run_flow(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 5,
    user_context: Optional[Dict[str, Any]] = None,
    ml_intelligence: Optional[Dict[str, Any]] = None,
    graph_crew=None,
    vector_crew=None,
    visual_crew=None,
    judge_crew=None
) -> ProductSearchResult:
    """
    Factory function to create and execute ProductSearchFlow.

    Args:
        query: User search query
        filters: Search filters
        limit: Maximum products to return
        user_context: User preferences
        ml_intelligence: ML-generated context
        graph_crew: GraphSearchCrew instance
        vector_crew: VectorSearchCrew instance
        visual_crew: VisualSearchCrew instance
        judge_crew: JudgeCrew instance

    Returns:
        ProductSearchResult: Structured output with products and metadata
    """
    # Initialize state
    initial_state = ProductSearchState(
        query=query,
        filters=filters or {},
        limit=limit,
        user_context=user_context or {},
        ml_intelligence=ml_intelligence or {}
    )

    # Create flow
    flow = ProductSearchFlow(
        graph_search_crew=graph_crew,
        vector_search_crew=vector_crew,
        visual_search_crew=visual_crew,
        judge_crew=judge_crew
    )

    # Execute flow
    result = await flow.kickoff(state=initial_state)

    return result
```

**Validation:**
- [ ] Run `python -c "from flows.product_search_flow import ProductSearchFlow; print('Flow OK')"`
- [ ] Verify Flow structure (no syntax errors)

---

### STEP 3: Create Mini-Crews (4-5 hours)

Now we need to create 4 small crews, each with 1 agent and 1 task.

**File:** `ari_crewai_migration/crews/mini_crews/graph_search_crew.py`

```python
"""
GraphSearchCrew - Mini-crew for Neo4j graph search.
Single agent (CypherBot), single task, Pydantic output.
"""
import logging
from pathlib import Path
from crewai import Crew, Agent, Task, Process
from pydantic import BaseModel

from models.product_models import GraphSearchResult
from utils.agent_loader import load_agent

logger = logging.getLogger("crewai.mini_crews.graph_search")


def create_graph_search_crew(agents_dir: str = None, tasks_dir: str = None) -> Crew:
    """
    Create graph search mini-crew with Pydantic output.

    Returns:
        Crew with 1 agent, 1 task, structured output
    """
    # Load CypherBot agent
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent.parent / 'agents'

    cypher_agent = load_agent(str(agents_dir / 'cypher_bot.yaml'))

    # Create task with Pydantic output
    task = Task(
        description="""
        Search Neo4j graph database for products matching the query.

        Strategy:
        1. Analyze query for occasion and context
        2. Choose search strategy (COLLABORATIVE, CATEGORY_FOCUSED, etc.)
        3. Execute optimized Cypher query
        4. Return structured products with scores

        Input: {query}, {filters}, {ml_intelligence}, {limit}
        """,
        expected_output="Structured graph search results with products and strategy reasoning",
        agent=cypher_agent,
        output_pydantic=GraphSearchResult  # ← STRUCTURED OUTPUT!
    )

    # Create mini-crew (no process needed for single task)
    crew = Crew(
        agents=[cypher_agent],
        tasks=[task],
        process=Process.sequential,  # Single task = sequential is fine
        verbose=False,
        memory=False,  # Disabled for mini-crews
        cache=False  # Disabled for mini-crews
    )

    logger.info("GraphSearchCrew created with Pydantic output")
    return crew
```

**Repeat for other mini-crews:**
- `vector_search_crew.py` → VectorSearchResult
- `visual_search_crew.py` → VisualSearchResult
- `judge_crew.py` → JudgmentResult

**Update Task YAMLs** to add `output_pydantic`:

**File:** `ari_crewai_migration/tasks/graph_search.yaml`
```yaml
task:
  description: |
    Search Neo4j graph database for products matching query...
    (keep existing description)

  expected_output: |
    Structured graph search results with products and strategy reasoning

  output_pydantic: GraphSearchResult  # ← ADD THIS

  async_execution: false
```

---

### STEP 4: Wire Flow to Orchestrator (2-3 hours)

**Update:** `ari_crewai_migration/crews/crewai_orchestrator.py`

```python
# Add import
from flows.product_search_flow import create_and_run_flow
from crews.mini_crews.graph_search_crew import create_graph_search_crew
from crews.mini_crews.vector_search_crew import create_vector_search_crew
from crews.mini_crews.visual_search_crew import create_visual_search_crew
from crews.mini_crews.judge_crew import create_judge_crew

class CrewAIOrchestrator:
    def __init__(self, ...):
        # Replace monolithic crew with mini-crews
        self.graph_crew = create_graph_search_crew()
        self.vector_crew = create_vector_search_crew()
        self.visual_crew = create_visual_search_crew()
        self.judge_crew = create_judge_crew()

        logger.info("CrewAI Orchestrator initialized with mini-crews and Flow")

    async def execute_search(self, query, filters, limit, ...):
        # ... intent detection ...

        # Use Flow instead of monolithic crew
        result = await create_and_run_flow(
            query=query,
            filters=merged_filters,
            limit=limit,
            user_context=user_context,
            ml_intelligence=generated_intelligence,
            graph_crew=self.graph_crew,
            vector_crew=self.vector_crew,
            visual_crew=self.visual_crew,
            judge_crew=self.judge_crew
        )

        # Result is already ProductSearchResult (Pydantic)
        # No regex parsing needed!
        return {
            "products": [p.dict() for p in result.products],
            "reasoning": result.reasoning,
            "metadata": result.metadata,
            "execution_time": result.execution_time
        }
```

---

## Testing Strategy

### Unit Tests
- [ ] Test Pydantic model validation
- [ ] Test Flow state transitions
- [ ] Test mini-crew creation
- [ ] Test timeout enforcement

### Integration Tests
- [ ] Test parallel execution
- [ ] Test with real Neo4j/Qdrant
- [ ] Test error handling (one crew fails)
- [ ] Test timeout scenarios

### Performance Tests
- [ ] Measure execution time vs CAMEL-AI
- [ ] Measure timeout accuracy
- [ ] Test under load

---

## Migration Path

### Phase 1: Development (Week 1)
- Implement all code above
- Test with isolated queries
- Verify Pydantic output works
- Verify timeouts work

### Phase 2: Testing (Week 2)
- Integration testing
- Performance benchmarking
- Bug fixes

### Phase 3: Deployment (Week 3)
- Deploy to staging
- Monitor for issues
- Production deployment

---

## Success Criteria

- ✅ No infinite loops (hard timeout works)
- ✅ Parallel execution (like CAMEL-AI)
- ✅ Structured output (no regex)
- ✅ Execution time < 120 seconds
- ✅ All tests passing
- ✅ Production-ready code quality

---

## Next Actions

Starting implementation NOW - tracking progress with TodoWrite.

Ready to begin Phase 1!
