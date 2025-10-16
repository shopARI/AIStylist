"""
GraphSearchCrew - Mini-crew for Neo4j graph search.
Single agent (CypherBot), single task, Pydantic output.
"""
import logging
from pathlib import Path
from crewai import Crew, Agent, Task, Process

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
        2. Choose search strategy (COLLABORATIVE, CATEGORY_FOCUSED, BRAND_RELATIONSHIPS, OCCASION_PATTERNS, or GENERAL)
        3. Execute optimized Cypher query using semantic expansion
        4. Return structured products with graph scores

        Input parameters:
        - query: {query}
        - filters: {filters}
        - ml_intelligence: {ml_intelligence}
        - limit: {limit}

        You MUST return a structured GraphSearchResult with:
        - products: List of Product objects
        - search_strategy: The strategy name you chose
        - reasoning: Why you chose this strategy
        - execution_time: Time taken
        - products_found: Number of products found
        """,
        expected_output="Structured GraphSearchResult with products list, strategy, and reasoning",
        agent=cypher_agent,
        output_pydantic=GraphSearchResult  # ← STRUCTURED OUTPUT!
    )

    # Create mini-crew (sequential process for single task)
    crew = Crew(
        agents=[cypher_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,  # Enable for debugging
        memory=False,  # Disabled for mini-crews
        cache=False  # Disabled to prevent stale data
    )

    logger.info("GraphSearchCrew created with Pydantic output")
    return crew
