"""
Product Search Crew Implementation
Assembles agents and tasks into hierarchical crew for product search workflow.
"""
import logging
from typing import Dict, Any, Optional, List
from crewai import Crew, Process
from pathlib import Path

logger = logging.getLogger("crewai.crews.product_search")


def create_product_search_crew(
    agents: Dict[str, Any],
    tasks: Dict[str, Any],
    process_type: str = "hierarchical",
    manager_llm_model: str = "gpt-5",
    verbose: bool = False
) -> Crew:
    """
    Create product search crew with specified configuration.

    Args:
        agents: Dictionary of agent name to Agent object
        tasks: Dictionary of task name to Task object
        process_type: "hierarchical" or "sequential"
        manager_llm_model: LLM model for hierarchical manager
        verbose: Enable verbose logging

    Returns:
        Configured CrewAI Crew
    """
    try:
        # Select process type
        if process_type.lower() == "hierarchical":
            process = Process.hierarchical
        elif process_type.lower() == "sequential":
            process = Process.sequential
        else:
            raise ValueError(f"Invalid process type: {process_type}")

        # Build agent list (order matters for sequential)
        agent_list = []
        agent_order = ['cypher_bot', 'vibe_bot', 'vision_bot', 'judge_ari']

        for agent_name in agent_order:
            if agent_name in agents:
                agent_list.append(agents[agent_name])

        # Build task list (order matters)
        task_list = []
        task_order = ['intelligence', 'graph_search', 'vector_search', 'visual_search', 'evaluation']

        for task_name in task_order:
            if task_name in tasks:
                task_list.append(tasks[task_name])

        # Step callback for debugging - logs each step
        def step_callback(step_output):
            logger.info(f"[CREW STEP] {step_output}")

        # Create crew configuration (ONLY VALID CREW PARAMETERS)
        # max_iter and max_execution_time belong on AGENTS, not CREW
        crew_config = {
            "agents": agent_list,
            "tasks": task_list,
            "process": process,
            "memory": False,  # DISABLED to prevent unbounded context growth
            "verbose": True,  # ENABLED for full debugging visibility
            "cache": False,  # DISABLED to prevent stale data loops
            "max_rpm": 60,  # Rate limiting
            "step_callback": step_callback,  # Log every step in real-time
            "output_log_file": "crew_execution.log"  # Log to file for analysis
        }

        # Add manager LLM for hierarchical process
        if process == Process.hierarchical:
            crew_config["manager_llm"] = manager_llm_model

        # Create crew
        crew = Crew(**crew_config)

        logger.info(f"Created {process_type} product search crew with {len(agent_list)} agents and {len(task_list)} tasks")
        return crew

    except Exception as e:
        logger.error(f"Failed to create product search crew: {e}")
        raise


def load_and_create_crew(
    agents_dir: Optional[str] = None,
    tasks_dir: Optional[str] = None,
    process_type: str = "hierarchical",
    verbose: bool = False
) -> Crew:
    """
    Load agents and tasks, then create configured crew.
    Convenience function that handles full crew initialization.

    Args:
        agents_dir: Path to agents directory
        tasks_dir: Path to tasks directory
        process_type: "hierarchical" or "sequential"
        verbose: Enable verbose logging

    Returns:
        Fully configured CrewAI Crew
    """
    from utils.agent_loader import load_all_agents
    from utils.task_loader import create_product_search_tasks

    # Load agents
    agents = load_all_agents(agents_dir)

    # Create tasks with agents
    tasks = create_product_search_tasks(agents, tasks_dir)

    # Create crew
    crew = create_product_search_crew(
        agents=agents,
        tasks=tasks,
        process_type=process_type,
        verbose=verbose
    )

    return crew


class ProductSearchCrew:
    """
    Wrapper class for product search crew with execution interface.
    """

    def __init__(self, crew: Crew):
        """
        Initialize with configured crew.

        Args:
            crew: CrewAI Crew instance
        """
        self.crew = crew

    def _parse_text_output(self, text: str) -> Dict[str, Any]:
        """
        Parse text output from crew into structured format.
        Handles multiple output formats from CrewAI agents.

        Args:
            text: Raw text output from crew

        Returns:
            Dictionary with parsed products and metadata
        """
        import re

        products = []

        # Find numbered product list (1. **...)
        product_sections = re.split(r'\n\s*\d+\.\s*\*\*([^\*]+)\*\*', text)

        # Process pairs (header, details_block)
        for i in range(1, len(product_sections), 2):
            if i + 1 >= len(product_sections):
                break

            header = product_sections[i].strip()
            details_block = product_sections[i + 1]

            try:
                product = {}

                # Check if header is "Product ID" or actual product name
                if header.lower() == "product id":
                    # Format: 1. **Product ID**: 12345\n   - **Title**: Name
                    # ID is in the header line
                    id_match = re.search(r':\s*(\d+)', details_block.split('\n')[0])
                    if id_match:
                        product['id'] = id_match.group(1)
                else:
                    # Format: 1. **Product Name**\n   - `product_id`: 123
                    product['name'] = header

                # Extract all fields (try both **Field**: and `field`: formats)

                # Title/Name
                if not product.get('name'):
                    title_match = re.search(r'-\s*\*\*Title\*\*:\s*([^\n]+)', details_block)
                    if not title_match:
                        title_match = re.search(r'-\s*`title`:\s*([^\n]+)', details_block)
                    if title_match:
                        product['name'] = title_match.group(1).strip()

                # Product ID
                if not product.get('id'):
                    id_match = re.search(r'-\s*\*\*Product ID\*\*:\s*(\d+)', details_block)
                    if not id_match:
                        id_match = re.search(r'-\s*`product_id`:\s*(\d+)', details_block)
                    if id_match:
                        product['id'] = id_match.group(1)

                # Price
                price_match = re.search(r'-\s*\*\*Price\*\*:\s*\$?([\d,.]+)', details_block)
                if not price_match:
                    price_match = re.search(r'-\s*`price`:\s*\$?([\d,.]+)', details_block)
                if price_match:
                    try:
                        product['price'] = float(price_match.group(1).replace(',', ''))
                    except:
                        pass

                # Category
                category_match = re.search(r'-\s*\*\*Category\*\*:\s*([^\n]+)', details_block)
                if not category_match:
                    category_match = re.search(r'-\s*`category`:\s*([^\n]+)', details_block)
                if category_match:
                    product['category'] = category_match.group(1).strip()

                # Images
                images_match = re.search(r'-\s*\*\*Images\*\*:\s*\[([^\]]+)\]', details_block)
                if not images_match:
                    images_match = re.search(r'-\s*`images?`:\s*\[([^\]]+)\]', details_block)
                if images_match:
                    images_str = images_match.group(1)
                    product['images'] = [img.strip(' "\'') for img in images_str.split(',')]

                # Quality Score
                quality_match = re.search(r'-\s*\*\*Quality Score\*\*:\s*([\d.]+)', details_block)
                if not quality_match:
                    quality_match = re.search(r'-\s*`quality[_\s]?score`:\s*([\d.]+)', details_block)
                if quality_match:
                    try:
                        product['quality_score'] = float(quality_match.group(1))
                    except:
                        pass

                # Only add if we have at least ID or name
                if product.get('id') or product.get('name'):
                    products.append(product)

            except Exception as e:
                logger.warning(f"Failed to parse product section: {e}")
                continue

        logger.info(f"Parsed {len(products)} products from text output")

        return {
            "final_products": products,
            "quality_assessments": {},
            "raw_text": text
        }

    async def execute(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute product search using crew.

        Args:
            query: User search query
            filters: Search filters (category, price, etc.)
            limit: Maximum products to return
            user_context: User preferences and history
            ml_intelligence: ML-generated context
            conversation_context: Current conversation state

        Returns:
            Dictionary with products and metadata
        """
        try:
            # Prepare crew inputs
            inputs = {
                "query": query,
                "filters": filters or {},
                "limit": limit,
                "user_context": user_context or {},
                "ml_intelligence": ml_intelligence or {},
                "conversation_context": conversation_context or {}
            }

            logger.info(f"Executing crew for query: '{query[:50]}...'")

            # Execute crew asynchronously with timeout
            import asyncio
            try:
                result = await asyncio.wait_for(
                    self.crew.kickoff_async(inputs=inputs),
                    timeout=120  # 2 minute hard timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Crew execution timed out after 120s")
                raise TimeoutError("Product search crew execution exceeded 2 minute timeout")

            # Extract output from CrewOutput object
            # CrewAI returns CrewOutput with raw, pydantic, json_dict, or tasks_output
            output_data = {}
            raw_text = ""

            if hasattr(result, 'json_dict') and result.json_dict:
                output_data = result.json_dict if isinstance(result.json_dict, dict) else {}
            elif hasattr(result, 'pydantic') and result.pydantic:
                output_data = result.pydantic.dict() if hasattr(result.pydantic, 'dict') else {}
            elif hasattr(result, 'raw'):
                raw_text = str(result.raw)
                # Try to parse raw output as JSON if it's a string
                import json as json_module
                if isinstance(result.raw, str):
                    try:
                        output_data = json_module.loads(result.raw)
                    except:
                        # Not JSON - parse as text
                        output_data = self._parse_text_output(result.raw)
                elif isinstance(result.raw, dict):
                    output_data = result.raw

            # Format response
            response = {
                "products": output_data.get("final_products", []),
                "reasoning": output_data.get("detailed_reasoning", str(getattr(result, 'raw', ''))),
                "metadata": {
                    "graph_count": output_data.get("graph_count", 0),
                    "vector_count": output_data.get("vector_count", 0),
                    "visual_count": output_data.get("visual_count", 0),
                    "consensus_products": output_data.get("consensus_products", []),
                    "quality_assessments": output_data.get("quality_assessments", {}),
                    "execution_time": getattr(result, 'execution_time', 0),
                    "quality_controlled": True,
                    "crew_output_type": type(result).__name__
                }
            }

            logger.info(f"Crew execution complete: {len(response['products'])} products")
            return response

        except Exception as e:
            logger.error(f"Crew execution failed: {e}")
            return {
                "products": [],
                "reasoning": f"Search failed: {str(e)}",
                "metadata": {"error": str(e)}
            }
