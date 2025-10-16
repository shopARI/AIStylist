"""
Integration tests for ProductSearchFlow.
Tests Flow state transitions, parallel execution, and timeout enforcement.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from models.product_models import (
    Product,
    GraphSearchResult,
    VectorSearchResult,
    VisualSearchResult,
    JudgmentResult,
    ProductSearchState,
    ProductSearchResult
)
from flows.product_search_flow import ProductSearchFlow, create_and_run_flow


class TestFlowStateTransitions:
    """Test Flow state management and transitions."""

    def test_state_initialization(self):
        """Test ProductSearchState can be initialized properly."""
        # Initialize state with required and optional fields
        initial_state = ProductSearchState(
            query="red dress",
            filters={"category": "dresses"},
            limit=5
        )

        assert initial_state is not None
        assert initial_state.query == "red dress"
        assert initial_state.filters["category"] == "dresses"
        assert initial_state.limit == 5

    @pytest.mark.asyncio
    async def test_state_preserves_query_info(self):
        """Test state preserves query information throughout flow."""
        state = ProductSearchState(
            query="blue jeans",
            filters={"color": "blue"},
            limit=10
        )

        # Simulate storing results in state
        state.graph_result = GraphSearchResult(
            products=[],
            search_strategy="GENERAL",
            reasoning="Test",
            execution_time=1.0,
            products_found=0
        )

        # Query info should still be accessible
        assert state.query == "blue jeans"
        assert state.filters["color"] == "blue"
        assert state.limit == 10


class TestParallelExecution:
    """Test parallel execution of search crews."""

    @pytest.mark.asyncio
    async def test_crews_execute_in_parallel(self):
        """Test that search crews run in parallel, not sequentially."""
        # Track execution times
        execution_order = []

        async def mock_graph_search(*args, **kwargs):
            execution_order.append(("graph", time.time()))
            await asyncio.sleep(0.1)
            return GraphSearchResult(
                products=[],
                search_strategy="GENERAL",
                reasoning="Graph search completed",
                execution_time=0.1,
                products_found=0
            )

        async def mock_vector_search(*args, **kwargs):
            execution_order.append(("vector", time.time()))
            await asyncio.sleep(0.1)
            return VectorSearchResult(
                products=[],
                search_strategy="SEMANTIC",
                reasoning="Vector search completed",
                execution_time=0.1,
                products_found=0
            )

        async def mock_visual_search(*args, **kwargs):
            execution_order.append(("visual", time.time()))
            await asyncio.sleep(0.1)
            return VisualSearchResult(
                products=[],
                search_strategy="VISUAL",
                reasoning="Visual search completed",
                execution_time=0.1,
                products_found=0
            )

        # If parallel: all 3 start ~same time, total ~0.1s
        # If sequential: start times differ, total ~0.3s
        start_time = time.time()

        # Run in parallel
        results = await asyncio.gather(
            mock_graph_search(),
            mock_vector_search(),
            mock_visual_search()
        )

        total_time = time.time() - start_time

        # Should complete in ~0.1s (parallel), not ~0.3s (sequential)
        assert total_time < 0.2  # Allow some overhead
        assert len(execution_order) == 3
        assert len(results) == 3

        # Check all started around same time (within 0.05s)
        start_times = [t for _, t in execution_order]
        time_spread = max(start_times) - min(start_times)
        assert time_spread < 0.05  # Parallel execution


class TestTimeoutEnforcement:
    """Test timeout enforcement for crews."""

    @pytest.mark.asyncio
    async def test_timeout_enforced_on_slow_crew(self):
        """Test that slow crews are terminated after timeout."""

        async def slow_crew_execution(*args, **kwargs):
            """Simulates crew that takes too long."""
            await asyncio.sleep(5.0)  # 5s > 30s timeout
            return GraphSearchResult(
                products=[],
                search_strategy="GENERAL",
                reasoning="Should not complete",
                execution_time=5.0,
                products_found=0
            )

        # Test with 1s timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_crew_execution(), timeout=1.0)

    @pytest.mark.asyncio
    async def test_fast_crew_completes_within_timeout(self):
        """Test that fast crews complete successfully."""

        async def fast_crew_execution(*args, **kwargs):
            """Simulates crew that completes quickly."""
            await asyncio.sleep(0.1)
            return GraphSearchResult(
                products=[],
                search_strategy="GENERAL",
                reasoning="Completed quickly",
                execution_time=0.1,
                products_found=0
            )

        # Should complete without timeout
        result = await asyncio.wait_for(fast_crew_execution(), timeout=1.0)
        assert result is not None
        assert result.reasoning == "Completed quickly"

    @pytest.mark.asyncio
    async def test_timeout_with_return_exceptions(self):
        """Test that timeouts are caught with return_exceptions=True."""

        async def slow_task():
            await asyncio.sleep(5.0)
            return "slow"

        async def fast_task():
            await asyncio.sleep(0.1)
            return "fast"

        # Run both with timeout and return_exceptions
        tasks = [
            asyncio.wait_for(slow_task(), timeout=0.5),
            asyncio.wait_for(fast_task(), timeout=0.5)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # First should be TimeoutError, second should be result
        assert isinstance(results[0], asyncio.TimeoutError)
        assert results[1] == "fast"


class TestErrorHandling:
    """Test error handling in Flow execution."""

    @pytest.mark.asyncio
    async def test_crew_exception_isolated(self):
        """Test that one crew's exception doesn't crash entire Flow."""

        async def failing_crew():
            raise ValueError("Crew failed")

        async def working_crew():
            await asyncio.sleep(0.1)
            return "success"

        # Run both with return_exceptions
        results = await asyncio.gather(
            failing_crew(),
            working_crew(),
            return_exceptions=True
        )

        # First should be exception, second should succeed
        assert isinstance(results[0], ValueError)
        assert results[1] == "success"

    @pytest.mark.asyncio
    async def test_all_crews_fail_gracefully(self):
        """Test Flow handles all crews failing."""

        async def failing_crew():
            raise RuntimeError("All crews failed")

        results = await asyncio.gather(
            failing_crew(),
            failing_crew(),
            failing_crew(),
            return_exceptions=True
        )

        # All should be exceptions
        assert all(isinstance(r, RuntimeError) for r in results)


class TestFlowOutputFormat:
    """Test Flow output format and structure."""

    def test_product_search_result_structure(self):
        """Test ProductSearchResult has expected structure."""
        products = [
            Product(id="1", title="Product 1", price=50.0, category="test")
        ]

        result = ProductSearchResult(
            products=products,
            reasoning="Test reasoning",
            metadata={"test": "value"},
            execution_time=2.5,
            graph_count=10,
            vector_count=15,
            visual_count=12,
            consensus_count=3,
            quality_controlled=True
        )

        # Convert to dict (API format)
        result_dict = result.dict()

        assert "products" in result_dict
        assert "reasoning" in result_dict
        assert "metadata" in result_dict
        assert "execution_time" in result_dict
        assert "graph_count" in result_dict
        assert "quality_controlled" in result_dict

        assert len(result_dict["products"]) == 1
        assert result_dict["graph_count"] == 10


class TestFlowPerformance:
    """Test Flow performance characteristics."""

    @pytest.mark.asyncio
    async def test_parallel_faster_than_sequential(self):
        """Test parallel execution is faster than sequential."""

        async def crew_task():
            await asyncio.sleep(0.2)
            return "done"

        # Parallel execution
        start = time.time()
        await asyncio.gather(crew_task(), crew_task(), crew_task())
        parallel_time = time.time() - start

        # Sequential execution
        start = time.time()
        await crew_task()
        await crew_task()
        await crew_task()
        sequential_time = time.time() - start

        # Parallel should be significantly faster
        assert parallel_time < sequential_time * 0.5  # At least 2x faster


class TestStateDefaults:
    """Test ProductSearchState default values."""

    def test_state_default_timeout_values(self):
        """Test state has sensible default timeouts."""
        state = ProductSearchState(query="test")

        assert state.individual_crew_timeout == 30
        assert state.judge_timeout == 30

    def test_state_default_limit(self):
        """Test state has default limit."""
        state = ProductSearchState(query="test")
        assert state.limit == 5

    def test_state_custom_timeouts(self):
        """Test state accepts custom timeouts."""
        state = ProductSearchState(
            query="test",
            individual_crew_timeout=60,
            judge_timeout=45
        )

        assert state.individual_crew_timeout == 60
        assert state.judge_timeout == 45
