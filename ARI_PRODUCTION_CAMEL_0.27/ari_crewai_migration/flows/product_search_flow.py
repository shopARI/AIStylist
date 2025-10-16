"""
ProductSearchFlow - CrewAI Flow implementation for product search.
Uses 2025 Flow patterns with state management and parallel execution.

Architecture:
1. parallel_search_step: Launch 3 mini-crews in parallel (graph, vector, visual)
2. judge_evaluation_step: Judge evaluates all results
3. finalize_results_step: Package final output

Key Features:
- Parallel execution like CAMEL-AI (asyncio.gather)
- Individual timeouts per mini-crew (30s each)
- Pydantic structured output (no regex!)
- State visibility at each step
- Error isolation and graceful degradation
"""
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

try:
    from crewai.flow.flow import Flow, listen, start
except ImportError:
    # Fallback if Flow is in different location
    from crewai import Flow, listen, start

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

    Timeout Strategy:
    - Each mini-crew: 30 seconds max
    - Parallel search total: 90 seconds max (3 crews in parallel)
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
            str: Next step name ('judge_evaluation' or 'finalize_results')
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
                    timeout=self.state.individual_crew_timeout
                ),
                asyncio.wait_for(
                    self._run_vector_search(search_inputs),
                    timeout=self.state.individual_crew_timeout
                ),
                asyncio.wait_for(
                    self._run_visual_search(search_inputs),
                    timeout=self.state.individual_crew_timeout
                )
            ]

            # Execute in parallel with error isolation
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results (handle exceptions gracefully)
            self.state.graph_result = results[0] if not isinstance(results[0], Exception) else None
            self.state.vector_result = results[1] if not isinstance(results[1], Exception) else None
            self.state.visual_result = results[2] if not isinstance(results[2], Exception) else None

            # Log errors but don't fail
            crew_names = ["Graph", "Vector", "Visual"]
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"{crew_names[idx]} search failed: {result}"
                    logger.error(error_msg)
                    self.state.errors.append(error_msg)
                else:
                    logger.info(
                        f"{crew_names[idx]} search: {result.products_found} products "
                        f"in {result.execution_time:.2f}s"
                    )

            step_time = time.time() - step_start
            logger.info(f"=== PARALLEL SEARCH COMPLETE: {step_time:.2f}s ===")

            # Route to judge if we have any results
            has_results = any([
                self.state.graph_result,
                self.state.vector_result,
                self.state.visual_result
            ])

            if has_results:
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
            logger.info(
                f"=== JUDGE EVALUATION COMPLETE: {len(result.final_products)} products "
                f"in {step_time:.2f}s ==="
            )

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
            quality_controlled = True

            # Calculate average quality score
            if self.state.judgment_result.quality_assessments:
                avg_quality = sum(self.state.judgment_result.quality_assessments.values()) / \
                             len(self.state.judgment_result.quality_assessments)
            else:
                avg_quality = None

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
            quality_controlled = False
            avg_quality = None

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
            "flow_implementation": "ProductSearchFlow_2025",
            "timeout_strategy": {
                "individual_crew_timeout": self.state.individual_crew_timeout,
                "judge_timeout": self.state.judge_timeout,
                "parallel_search_timeout": self.state.parallel_search_timeout
            }
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
            consensus_count=consensus_count,
            quality_controlled=quality_controlled,
            average_quality_score=avg_quality
        )

        logger.info(f"=== FLOW COMPLETE: {len(final_products)} products in {total_time:.2f}s ===")

        return result


async def create_and_run_flow(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 5,
    user_context: Optional[Dict[str, Any]] = None,
    ml_intelligence: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
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
        conversation_context: Conversation state
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
        ml_intelligence=ml_intelligence or {},
        conversation_context=conversation_context or {}
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
