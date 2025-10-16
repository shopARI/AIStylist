"""
JudgeCrew - Mini-crew for product evaluation and quality control.
Single agent (Judge Ari), single task, Pydantic output.
"""
import logging
from pathlib import Path
from crewai import Crew, Agent, Task, Process

from models.product_models import JudgmentResult
from utils.agent_loader import load_agent

logger = logging.getLogger("crewai.mini_crews.judge")


def create_judge_crew(agents_dir: str = None, tasks_dir: str = None) -> Crew:
    """
    Create judge evaluation mini-crew with Pydantic output.

    Returns:
        Crew with 1 agent, 1 task, structured output
    """
    # Load Judge Ari agent
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent.parent / 'agents'
    else:
        agents_dir = Path(agents_dir)  # Convert to Path if string

    judge_agent = load_agent(str(agents_dir / 'judge_ari.yaml'))

    # Create task with Pydantic output
    task = Task(
        description="""
        Evaluate products from all search agents and select the best recommendations.

        Strategy:
        1. Review products from graph_results, vector_results, and visual_results
        2. Score each product independently for quality
        3. Detect consensus products (found by multiple agents)
        4. Apply quality threshold filtering
        5. Rank by combined quality and relevance
        6. Generate detailed reasoning

        Input parameters:
        - query: {query}
        - graph_results: Products from GraphSearchCrew
        - vector_results: Products from VectorSearchCrew
        - visual_results: Products from VisualSearchCrew
        - ml_intelligence: {ml_intelligence}
        - user_context: {user_context}
        - limit: {limit}

        You MUST return a structured JudgmentResult with:
        - final_products: Top ranked products after quality control
        - quality_assessments: Quality scores by product ID
        - consensus_products: Product IDs found by multiple agents
        - rejected_products: Products filtered out with rejection reasons
        - judgment_confidence: Overall confidence in recommendations (0.0-1.0)
        - detailed_reasoning: Explanation of selection criteria and decisions
        - execution_time: Time taken
        """,
        expected_output="Structured JudgmentResult with final products, quality scores, consensus detection, and detailed reasoning",
        agent=judge_agent,
        output_pydantic=JudgmentResult  # ← STRUCTURED OUTPUT!
    )

    # Create mini-crew
    crew = Crew(
        agents=[judge_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
        memory=False,
        cache=False
    )

    logger.info("JudgeCrew created with Pydantic output")
    return crew
