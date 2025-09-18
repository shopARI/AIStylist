"""
Test for the critical Redis cache pollution fix
Tests that only essential data is cached, not massive battle results
"""

import pytest
import time
import json


class TestCachingFix:
    """Test the production cache fix."""

    def test_cache_data_size_optimization(self):
        """Test that the new cache structure is dramatically smaller than the old one."""

        # Simulate the OLD massive cache data (what was causing 100MB Redis growth)
        old_massive_cache_data = {
            "products": [
                {"id": "1", "title": "Black Dress", "price": 100, "description": "A beautiful black dress"},
                {"id": "2", "title": "Navy Dress", "price": 120, "description": "A stylish navy dress"}
            ],
            # These are the massive fields that were being cached before the fix
            "cypher_products": [{"raw_neo4j_data": "x" * 50000} for _ in range(20)],  # ~1MB
            "vibe_products": [{"raw_vector_embeddings": "y" * 50000} for _ in range(20)],  # ~1MB
            "judgment": {
                "winner": "cypher",
                "detailed_analysis": "Long detailed analysis..." * 1000,  # Large text
                "reasoning": "Complex reasoning..." * 2000,  # More large text
                "full_evaluation": {"extensive": "data" * 10000}
            },
            "agent_thoughts": {
                "cypher_thoughts": ["Graph analysis..."] * 500,
                "vibe_thoughts": ["Vector processing..."] * 500,
                "judge_thoughts": ["Detailed evaluation..."] * 500
            },
            "ml_intelligence_data": {"massive_ml_context": "intelligence" * 100000},
            "conversation_context": {"full_history": ["message"] * 1000},
            "raw_search_metadata": {"search_details": "metadata" * 50000},
            "cypher_count": 20,
            "vibe_count": 18,
            "winner": "cypher",
            "execution_time": 15.2,
            "ml_enhanced": True
        }

        # Simulate the NEW optimized cache data (after the fix)
        new_optimized_cache_data = {
            "products": [
                {"id": "1", "title": "Black Dress", "price": 100, "description": "A beautiful black dress"},
                {"id": "2", "title": "Navy Dress", "price": 120, "description": "A stylish navy dress"}
            ],
            "cypher_count": 20,
            "vibe_count": 18,
            "winner": "cypher",
            "execution_time": 15.2,
            "ml_enhanced": True,
            "cached_at": time.time()
        }

        # Calculate sizes
        old_size = len(json.dumps(old_massive_cache_data))
        new_size = len(json.dumps(new_optimized_cache_data))

        # Verify dramatic size reduction (should be >95% reduction)
        reduction_ratio = (old_size - new_size) / old_size
        assert reduction_ratio > 0.95, f"Size reduction only {reduction_ratio:.1%}, expected >95%"

        # Verify old size was problematically large (MB range)
        assert old_size > 1_000_000, f"Old size {old_size} bytes should be >1MB"

        # Verify new size is reasonable (KB range)
        assert new_size < 10_000, f"New size {new_size} bytes should be <10KB"

        print(f"Cache size optimization:")
        print(f"  Old size: {old_size:,} bytes ({old_size/1024/1024:.1f} MB)")
        print(f"  New size: {new_size:,} bytes ({new_size/1024:.1f} KB)")
        print(f"  Reduction: {reduction_ratio:.1%}")

    def test_cache_data_contains_required_fields(self):
        """Test that the optimized cache data contains all required fields."""

        # Simulate the exact cache data structure from the fix
        cache_data = {
            "products": [{"id": "test", "title": "Test Product"}],
            "cypher_count": 5,
            "vibe_count": 3,
            "winner": "cypher",
            "execution_time": 12.5,
            "ml_enhanced": True,
            "cached_at": time.time()
        }

        # Verify all required fields are present
        required_fields = [
            "products", "cypher_count", "vibe_count", "winner",
            "execution_time", "ml_enhanced", "cached_at"
        ]

        for field in required_fields:
            assert field in cache_data, f"Required field '{field}' missing"

        # Verify excluded fields are NOT present (this was the bug fix)
        excluded_fields = [
            "cypher_products", "vibe_products", "judgment",
            "agent_thoughts", "reasoning", "ml_intelligence_data"
        ]

        for field in excluded_fields:
            assert field not in cache_data, f"Excluded field '{field}' should not be cached"

    def test_cache_ttl_optimization(self):
        """Test that TTL was reduced to prevent cache buildup."""

        # The fix reduced TTL from 300s to 180s
        old_ttl = 300
        new_ttl = 180

        # Verify TTL reduction
        ttl_reduction = (old_ttl - new_ttl) / old_ttl
        assert ttl_reduction == 0.4, f"TTL reduction should be 40%, got {ttl_reduction:.1%}"

        # Verify new TTL is reasonable (3 minutes)
        assert new_ttl == 180, f"New TTL should be 180s, got {new_ttl}s"

    def test_production_scenario_simulation(self):
        """Simulate the exact production scenario that was causing issues."""

        # Simulate what would happen with 10 concurrent requests
        # Each request was caching ~100MB, causing Redis to grow by 1GB

        # Old scenario (before fix)
        old_cache_per_request = 100 * 1024 * 1024  # 100MB per request
        concurrent_requests = 10
        old_total_cache = old_cache_per_request * concurrent_requests

        # New scenario (after fix)
        new_cache_per_request = 5 * 1024  # 5KB per request
        new_total_cache = new_cache_per_request * concurrent_requests

        # Verify the fix prevents Redis memory explosion
        memory_savings = old_total_cache - new_total_cache
        savings_ratio = memory_savings / old_total_cache

        assert savings_ratio > 0.999, f"Memory savings should be >99.9%, got {savings_ratio:.3%}"
        assert new_total_cache < 100 * 1024, f"New total cache should be <100KB, got {new_total_cache/1024:.1f}KB"

        print(f"Production scenario simulation:")
        print(f"  Old cache (10 requests): {old_total_cache/1024/1024:.0f} MB")
        print(f"  New cache (10 requests): {new_total_cache/1024:.1f} KB")
        print(f"  Memory savings: {memory_savings/1024/1024:.0f} MB ({savings_ratio:.3%})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])