"""
CrewAI Flows for product search.
Uses 2025 Flow patterns with state management and parallel execution.
"""
from .product_search_flow import ProductSearchFlow, create_and_run_flow

__all__ = ['ProductSearchFlow', 'create_and_run_flow']
