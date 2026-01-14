"""
ARI V3 Navigation Module

Contains:
- SynthesisLLM: LLM #3 that combines three pillars into style descriptors
- NavigationContext: Complete context for navigation-aware search
- NavigationPath: Calculated path with step constraints
- Path calculation utilities
"""

from .synthesis_llm import (
    SynthesisLLM,
    SynthesisOutput,
    ThreePillarsInput,
    BudgetInterpretation,
)

from .navigation_context import (
    NavigationContext,
    NavigationPath,
    BehavioralProfile,
    DriftAnalysis,
    calculate_navigation_path,
    create_cold_start_context,
)

__all__ = [
    # Synthesis LLM
    "SynthesisLLM",
    "SynthesisOutput",
    "ThreePillarsInput",
    "BudgetInterpretation",
    # Navigation Context
    "NavigationContext",
    "NavigationPath",
    "BehavioralProfile",
    "DriftAnalysis",
    "calculate_navigation_path",
    "create_cold_start_context",
]
