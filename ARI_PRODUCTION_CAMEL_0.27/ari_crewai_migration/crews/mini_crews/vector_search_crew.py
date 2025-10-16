"""
VectorSearchCrew - Mini-crew for Qdrant vector search.
Single agent (VibeBot), single task, Pydantic output.
"""
import logging
from pathlib import Path
from crewai import Crew, Agent, Task, Process

from models.product_models import VectorSearchResult
from utils.agent_loader import load_agent

logger = logging.getLogger("crewai.mini_crews.vector_search")


def create_vector_search_crew(agents_dir: str = None, tasks_dir: str = None) -> Crew:
    """
    Create vector search mini-crew with Pydantic output.

    Returns:
        Crew with 1 agent, 1 task, structured output
    """
    # Load VibeBot agent
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent.parent / 'agents'

    vibe_agent = load_agent(str(agents_dir / 'vibe_bot.yaml'))

    # Create task with Pydantic output
    task = Task(
        description="""
        Search Qdrant vector database for products using semantic similarity.

        Strategy:
        1. Analyze query for aesthetic and style cues
        2. Choose search strategy (SEMANTIC, VISUAL, COLOR, STYLE, or GENERAL)
        3. Execute Qdrant embedding search
        4. Return structured products with vibe scores

        Input parameters:
        - query: {query}
        - filters: {filters}
        - ml_intelligence: {ml_intelligence}
        - limit: {limit}

        You MUST return a structured VectorSearchResult with:
        - products: List of Product objects
        - search_strategy: The strategy name you chose
        - reasoning: Why you chose this strategy
        - execution_time: Time taken
        - products_found: Number of products found
        """,
        expected_output="Structured VectorSearchResult with products list, strategy, and reasoning",
        agent=vibe_agent,
        output_pydantic=VectorSearchResult  # ← STRUCTURED OUTPUT!
    )

    # Create mini-crew
    crew = Crew(
        agents=[vibe_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
        memory=False,
        cache=False
    )

    logger.info("VectorSearchCrew created with Pydantic output")
    return crew
