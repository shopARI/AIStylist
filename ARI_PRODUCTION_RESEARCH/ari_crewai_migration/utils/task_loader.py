"""
Task Loader Utility for CrewAI Migration
Loads task configurations from YAML files and instantiates CrewAI tasks.
"""
import yaml
import logging
from typing import Dict, List, Optional
from pathlib import Path
from crewai import Task, Agent

logger = logging.getLogger("crewai.utils.task_loader")


def load_task_config(task_file: str) -> Dict:
    """
    Load task configuration from YAML file.

    Args:
        task_file: Path to task YAML file

    Returns:
        Dictionary with task configuration
    """
    try:
        with open(task_file, 'r') as f:
            config = yaml.safe_load(f)

        if 'task' not in config:
            raise ValueError(f"Invalid task file: {task_file} - missing 'task' key")

        return config['task']

    except Exception as e:
        logger.error(f"Failed to load task config from {task_file}: {e}")
        raise


def create_task_from_config(
    config: Dict,
    agent: Agent,
    context_tasks: Optional[List[Task]] = None
) -> Task:
    """
    Create CrewAI task from configuration dictionary.

    Args:
        config: Task configuration dictionary
        agent: Agent assigned to this task
        context_tasks: Optional list of tasks that provide context

    Returns:
        Instantiated CrewAI Task
    """
    try:
        task = Task(
            description=config['description'],
            expected_output=config['expected_output'],
            agent=agent,
            context=context_tasks or [],
            async_execution=config.get('async_execution', False)
        )

        logger.info(f"Created task for agent: {agent.role}")
        return task

    except Exception as e:
        logger.error(f"Failed to create task from config: {e}")
        raise


def load_task(
    task_file: str,
    agent: Agent,
    context_tasks: Optional[List[Task]] = None
) -> Task:
    """
    Load task from YAML file and instantiate.

    Args:
        task_file: Path to task YAML file
        agent: Agent assigned to this task
        context_tasks: Optional list of context tasks

    Returns:
        Instantiated CrewAI Task
    """
    config = load_task_config(task_file)
    return create_task_from_config(config, agent, context_tasks)


def create_product_search_tasks(agents: Dict[str, Agent], tasks_dir: str = None) -> Dict[str, Task]:
    """
    Create all tasks for product search workflow.

    Args:
        agents: Dictionary of agent name to Agent object
        tasks_dir: Path to tasks directory (defaults to ./tasks)

    Returns:
        Dictionary mapping task names to Task objects
    """
    if tasks_dir is None:
        tasks_dir = Path(__file__).parent.parent / 'tasks'
    else:
        tasks_dir = Path(tasks_dir)

    tasks = {}

    # Intelligence generation task (no dependencies)
    intelligence_task_file = tasks_dir / 'intelligence_generation.yaml'
    if intelligence_task_file.exists() and 'intelligence_coordinator' in agents:
        tasks['intelligence'] = load_task(
            str(intelligence_task_file),
            agents['intelligence_coordinator'],
            context_tasks=None
        )
        logger.info("Created intelligence generation task")

    # Graph search task (depends on intelligence)
    graph_task_file = tasks_dir / 'graph_search.yaml'
    if graph_task_file.exists() and 'cypher_bot' in agents:
        context = [tasks['intelligence']] if 'intelligence' in tasks else None
        tasks['graph_search'] = load_task(
            str(graph_task_file),
            agents['cypher_bot'],
            context_tasks=context
        )
        logger.info("Created graph search task")

    # Vector search task (depends on intelligence)
    vector_task_file = tasks_dir / 'vector_search.yaml'
    if vector_task_file.exists() and 'vibe_bot' in agents:
        context = [tasks['intelligence']] if 'intelligence' in tasks else None
        tasks['vector_search'] = load_task(
            str(vector_task_file),
            agents['vibe_bot'],
            context_tasks=context
        )
        logger.info("Created vector search task")

    # Visual search task (depends on intelligence)
    visual_task_file = tasks_dir / 'visual_search.yaml'
    if visual_task_file.exists() and 'vision_bot' in agents:
        context = [tasks['intelligence']] if 'intelligence' in tasks else None
        tasks['visual_search'] = load_task(
            str(visual_task_file),
            agents['vision_bot'],
            context_tasks=context
        )
        logger.info("Created visual search task")

    # Result evaluation task (depends on all search tasks)
    evaluation_task_file = tasks_dir / 'result_evaluation.yaml'
    if evaluation_task_file.exists() and 'judge_ari' in agents:
        context = []
        for task_name in ['graph_search', 'vector_search', 'visual_search']:
            if task_name in tasks:
                context.append(tasks[task_name])

        tasks['evaluation'] = load_task(
            str(evaluation_task_file),
            agents['judge_ari'],
            context_tasks=context if context else None
        )
        logger.info("Created result evaluation task")

    logger.info(f"Created {len(tasks)} tasks total")
    return tasks
