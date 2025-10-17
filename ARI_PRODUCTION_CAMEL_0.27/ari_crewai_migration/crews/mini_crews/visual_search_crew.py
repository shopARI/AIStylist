"""
VisualSearchCrew - Mini-crew for FashionSigLIP visual search.
Single agent (VisionBot), single task, Pydantic output.
"""
import logging
from pathlib import Path
from crewai import Crew, Agent, Task, Process

from models.product_models import VisualSearchResult
from utils.agent_loader import load_agent

logger = logging.getLogger("crewai.mini_crews.visual_search")


def create_visual_search_crew(agents_dir: str = None, tasks_dir: str = None) -> Crew:
    """
    Create visual search mini-crew with Pydantic output.

    Returns:
        Crew with 1 agent, 1 task, structured output
    """
    # Load VisionBot agent
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent.parent / 'agents'
    else:
        agents_dir = Path(agents_dir)  # Convert to Path if string

    vision_agent = load_agent(str(agents_dir / 'vision_bot.yaml'))

    # Create task with Pydantic output
    task = Task(
        description="""
        Search FashionSigLIP visual database for visually similar products.

        Strategy:
        1. Analyze query for visual characteristics
        2. Choose search strategy (VISUAL_SIMILARITY, COLOR_BASED_VISUAL, STYLE_VISUAL, TEXTURE_VISUAL, or GENERAL_VISUAL)
        3. Execute FashionSigLIP visual embedding search
        4. Enrich each product with metadata scores
        5. Return structured products with visual scores

        Input parameters:
        - query: {query}
        - filters: {filters}
        - ml_intelligence: {ml_intelligence}
        - limit: {limit}

        IMPORTANT: For each Product object you return, you MUST populate these metadata fields:
        - visual_score: Visual similarity score (0.0-1.0) from FashionSigLIP search
        - agent_source: Set to "VisionBot"
        - search_method: The strategy name you chose (e.g., "VISUAL_SIMILARITY")
        - reasoning: Brief explanation of why this product matches the query visually (1 sentence)

        You MUST return a structured VisualSearchResult with:
        - products: List of Product objects (with metadata fields populated!)
        - search_strategy: The strategy name you chose
        - reasoning: Why you chose this strategy
        - execution_time: Time taken
        - products_found: Number of products found
        """,
        expected_output="Structured VisualSearchResult with enriched products (metadata populated), strategy, and reasoning",
        agent=vision_agent,
        output_pydantic=VisualSearchResult  # ← STRUCTURED OUTPUT!
    )

    # Create mini-crew
    crew = Crew(
        agents=[vision_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
        memory=False,
        cache=False
    )

    logger.info("VisualSearchCrew created with Pydantic output")
    return crew
