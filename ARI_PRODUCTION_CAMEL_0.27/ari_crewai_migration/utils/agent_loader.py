"""
Agent Loader Utility for CrewAI Migration
Loads agent configurations from YAML files and instantiates CrewAI agents.
"""
import os
import yaml
import logging
from typing import Dict, List
from pathlib import Path
from crewai import Agent
from crewai.llm import LLM

logger = logging.getLogger("crewai.utils.agent_loader")


def load_agent_config(agent_file: str) -> Dict:
    """
    Load agent configuration from YAML file.

    Args:
        agent_file: Path to agent YAML file

    Returns:
        Dictionary with agent configuration
    """
    try:
        with open(agent_file, 'r') as f:
            config = yaml.safe_load(f)

        if 'agent' not in config:
            raise ValueError(f"Invalid agent file: {agent_file} - missing 'agent' key")

        return config['agent']

    except Exception as e:
        logger.error(f"Failed to load agent config from {agent_file}: {e}")
        raise


def load_tools_for_agent(tool_names: List[str]) -> List:
    """
    Load and instantiate tools for an agent.

    Args:
        tool_names: List of tool names to load

    Returns:
        List of instantiated tool objects
    """
    tools = []

    # Import all available tools
    try:
        # Sync tools (legacy)
        from tools.neo4j_tools import neo4j_query_tool, semantic_expansion_tool, neo4j_fulltext_search_tool
        from tools.qdrant_tools import qdrant_search_tool, embedding_generation_tool, qdrant_hybrid_search_tool
        from tools.fashionsig_tools import fashionsig_embedding_tool, visual_similarity_search_tool, multi_image_search_tool
        from tools.quality_tools import quality_scoring_tool, consensus_detection_tool, learning_analysis_tool
        from tools.cache_tools import cache_lookup_tool, cache_store_tool

        # Async tools (Phase 2 - non-blocking)
        from tools.async_tools.async_neo4j_tools import (
            async_neo4j_query_tool,
            async_semantic_expansion_tool,
            async_neo4j_fulltext_search_tool
        )
        from tools.async_tools.async_qdrant_tools import (
            async_qdrant_search_tool,
            async_embedding_generation_tool,
            async_qdrant_hybrid_search_tool,
            async_qdrant_filter_search_tool
        )
        from tools.async_tools.async_fashionsig_tools import (
            async_fashionsig_embedding_tool,
            async_visual_similarity_search_tool,
            async_multi_image_search_tool,
            async_fashionsig_multimodal_search_tool
        )

        # Map tool names to tool objects
        tool_map = {
            # Sync tools (legacy)
            'neo4j_query_tool': neo4j_query_tool,
            'semantic_expansion_tool': semantic_expansion_tool,
            'neo4j_fulltext_search_tool': neo4j_fulltext_search_tool,
            'qdrant_search_tool': qdrant_search_tool,
            'embedding_generation_tool': embedding_generation_tool,
            'qdrant_hybrid_search_tool': qdrant_hybrid_search_tool,
            'fashionsig_embedding_tool': fashionsig_embedding_tool,
            'visual_similarity_search_tool': visual_similarity_search_tool,
            'multi_image_search_tool': multi_image_search_tool,
            'quality_scoring_tool': quality_scoring_tool,
            'consensus_detection_tool': consensus_detection_tool,
            'learning_analysis_tool': learning_analysis_tool,
            'cache_lookup_tool': cache_lookup_tool,
            'cache_store_tool': cache_store_tool,

            # Async tools (Phase 2 - recommended for production)
            'async_neo4j_query_tool': async_neo4j_query_tool,
            'async_semantic_expansion_tool': async_semantic_expansion_tool,
            'async_neo4j_fulltext_search_tool': async_neo4j_fulltext_search_tool,
            'async_qdrant_search_tool': async_qdrant_search_tool,
            'async_embedding_generation_tool': async_embedding_generation_tool,
            'async_qdrant_hybrid_search_tool': async_qdrant_hybrid_search_tool,
            'async_qdrant_filter_search_tool': async_qdrant_filter_search_tool,
            'async_fashionsig_embedding_tool': async_fashionsig_embedding_tool,
            'async_visual_similarity_search_tool': async_visual_similarity_search_tool,
            'async_multi_image_search_tool': async_multi_image_search_tool,
            'async_fashionsig_multimodal_search_tool': async_fashionsig_multimodal_search_tool,
        }

        # Load requested tools
        for tool_name in tool_names:
            if tool_name in tool_map:
                tools.append(tool_map[tool_name])
            else:
                logger.warning(f"Tool not found: {tool_name}")

        logger.info(f"Loaded {len(tools)} tools: {tool_names}")
        return tools

    except Exception as e:
        logger.error(f"Failed to load tools: {e}")
        return []


def create_agent_from_config(config: Dict) -> Agent:
    """
    Create CrewAI agent from configuration dictionary.

    Args:
        config: Agent configuration dictionary

    Returns:
        Instantiated CrewAI Agent
    """
    try:
        # Create LLM configuration
        llm_config = config.get('llm', {})
        llm = LLM(
            model=llm_config.get('model', 'gpt-5'),
            temperature=llm_config.get('temperature', 0.7),
            max_tokens=llm_config.get('max_tokens', 2000)
        )

        # Load tools
        tool_names = config.get('tools', [])
        tools = load_tools_for_agent(tool_names)

        # Create agent
        agent = Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            llm=llm,
            tools=tools,
            memory=config.get('memory', True),
            verbose=config.get('verbose', True),
            allow_delegation=config.get('allow_delegation', False)
        )

        logger.info(f"Created agent: {config['role']}")
        return agent

    except Exception as e:
        logger.error(f"Failed to create agent from config: {e}")
        raise


def load_agent(agent_file: str) -> Agent:
    """
    Load agent from YAML file and instantiate.

    Args:
        agent_file: Path to agent YAML file

    Returns:
        Instantiated CrewAI Agent
    """
    config = load_agent_config(agent_file)
    return create_agent_from_config(config)


def load_all_agents(agents_dir: str = None) -> Dict[str, Agent]:
    """
    Load all agents from agents directory.

    Args:
        agents_dir: Path to agents directory (defaults to ./agents)

    Returns:
        Dictionary mapping agent names to Agent objects
    """
    if agents_dir is None:
        # Default to agents directory in migration folder
        agents_dir = Path(__file__).parent.parent / 'agents'
    else:
        agents_dir = Path(agents_dir)

    agents = {}

    # Load each agent YAML file
    agent_files = {
        'cypher_bot': agents_dir / 'cypher_bot.yaml',
        'vibe_bot': agents_dir / 'vibe_bot.yaml',
        'vision_bot': agents_dir / 'vision_bot.yaml',
        'judge_ari': agents_dir / 'judge_ari.yaml'
    }

    for agent_name, agent_file in agent_files.items():
        if agent_file.exists():
            try:
                agents[agent_name] = load_agent(str(agent_file))
                logger.info(f"Loaded agent: {agent_name}")
            except Exception as e:
                logger.error(f"Failed to load agent {agent_name}: {e}")
        else:
            logger.warning(f"Agent file not found: {agent_file}")

    logger.info(f"Loaded {len(agents)} agents total")
    return agents
