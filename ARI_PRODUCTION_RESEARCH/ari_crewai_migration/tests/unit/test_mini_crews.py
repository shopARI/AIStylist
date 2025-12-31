"""
Unit tests for mini-crew creation and configuration.
Tests that crews can be instantiated with correct agents and tasks.
"""
import pytest
from pathlib import Path
from crewai import Crew, Agent, Task
from crews.mini_crews import (
    create_graph_search_crew,
    create_vector_search_crew,
    create_visual_search_crew,
    create_judge_crew
)


class TestGraphSearchCrew:
    """Test GraphSearchCrew creation."""

    def test_crew_creation(self):
        """Test graph search crew can be created."""
        crew = create_graph_search_crew()
        assert isinstance(crew, Crew)
        assert crew is not None

    def test_crew_has_one_agent(self):
        """Test crew has exactly 1 agent (CypherBot)."""
        crew = create_graph_search_crew()
        assert len(crew.agents) == 1
        agent = crew.agents[0]
        assert isinstance(agent, Agent)
        # Check agent name contains expected keywords
        assert agent.role is not None

    def test_crew_has_one_task(self):
        """Test crew has exactly 1 task."""
        crew = create_graph_search_crew()
        assert len(crew.tasks) == 1
        task = crew.tasks[0]
        assert isinstance(task, Task)

    def test_crew_task_has_pydantic_output(self):
        """Test task is configured for Pydantic output."""
        crew = create_graph_search_crew()
        task = crew.tasks[0]
        # Check that output_pydantic is set (GraphSearchResult)
        assert task.output_pydantic is not None
        assert task.output_pydantic.__name__ == "GraphSearchResult"

    def test_crew_configuration(self):
        """Test crew configuration settings."""
        crew = create_graph_search_crew()
        assert crew.verbose is True
        assert crew.memory is False  # Disabled for mini-crews
        assert crew.cache is False  # Disabled for mini-crews

    def test_crew_with_custom_agents_dir(self):
        """Test crew creation with custom agents directory."""
        agents_dir = Path(__file__).parent.parent.parent / 'agents'
        crew = create_graph_search_crew(agents_dir=str(agents_dir))
        assert crew is not None
        assert len(crew.agents) == 1


class TestVectorSearchCrew:
    """Test VectorSearchCrew creation."""

    def test_crew_creation(self):
        """Test vector search crew can be created."""
        crew = create_vector_search_crew()
        assert isinstance(crew, Crew)
        assert crew is not None

    def test_crew_has_one_agent(self):
        """Test crew has exactly 1 agent (VibeBot)."""
        crew = create_vector_search_crew()
        assert len(crew.agents) == 1

    def test_crew_has_one_task(self):
        """Test crew has exactly 1 task."""
        crew = create_vector_search_crew()
        assert len(crew.tasks) == 1

    def test_crew_task_has_pydantic_output(self):
        """Test task is configured for Pydantic output."""
        crew = create_vector_search_crew()
        task = crew.tasks[0]
        assert task.output_pydantic is not None
        assert task.output_pydantic.__name__ == "VectorSearchResult"

    def test_crew_configuration(self):
        """Test crew configuration settings."""
        crew = create_vector_search_crew()
        assert crew.verbose is True
        assert crew.memory is False
        assert crew.cache is False


class TestVisualSearchCrew:
    """Test VisualSearchCrew creation."""

    def test_crew_creation(self):
        """Test visual search crew can be created."""
        crew = create_visual_search_crew()
        assert isinstance(crew, Crew)
        assert crew is not None

    def test_crew_has_one_agent(self):
        """Test crew has exactly 1 agent (VisionBot)."""
        crew = create_visual_search_crew()
        assert len(crew.agents) == 1

    def test_crew_has_one_task(self):
        """Test crew has exactly 1 task."""
        crew = create_visual_search_crew()
        assert len(crew.tasks) == 1

    def test_crew_task_has_pydantic_output(self):
        """Test task is configured for Pydantic output."""
        crew = create_visual_search_crew()
        task = crew.tasks[0]
        assert task.output_pydantic is not None
        assert task.output_pydantic.__name__ == "VisualSearchResult"

    def test_crew_configuration(self):
        """Test crew configuration settings."""
        crew = create_visual_search_crew()
        assert crew.verbose is True
        assert crew.memory is False
        assert crew.cache is False


class TestJudgeCrew:
    """Test JudgeCrew creation."""

    def test_crew_creation(self):
        """Test judge crew can be created."""
        crew = create_judge_crew()
        assert isinstance(crew, Crew)
        assert crew is not None

    def test_crew_has_one_agent(self):
        """Test crew has exactly 1 agent (Judge Ari)."""
        crew = create_judge_crew()
        assert len(crew.agents) == 1

    def test_crew_has_one_task(self):
        """Test crew has exactly 1 task."""
        crew = create_judge_crew()
        assert len(crew.tasks) == 1

    def test_crew_task_has_pydantic_output(self):
        """Test task is configured for Pydantic output."""
        crew = create_judge_crew()
        task = crew.tasks[0]
        assert task.output_pydantic is not None
        assert task.output_pydantic.__name__ == "JudgmentResult"

    def test_crew_configuration(self):
        """Test crew configuration settings."""
        crew = create_judge_crew()
        assert crew.verbose is True
        assert crew.memory is False
        assert crew.cache is False


class TestMiniCrewIsolation:
    """Test that mini-crews are isolated from each other."""

    def test_different_crew_instances(self):
        """Test each create function returns new instance."""
        crew1 = create_graph_search_crew()
        crew2 = create_graph_search_crew()
        assert crew1 is not crew2  # Different instances

    def test_different_agent_types(self):
        """Test each crew has different agent."""
        graph_crew = create_graph_search_crew()
        vector_crew = create_vector_search_crew()
        visual_crew = create_visual_search_crew()
        judge_crew = create_judge_crew()

        # All should have different agents
        graph_agent = graph_crew.agents[0]
        vector_agent = vector_crew.agents[0]
        visual_agent = visual_crew.agents[0]
        judge_agent = judge_crew.agents[0]

        # Roles should be different
        roles = {graph_agent.role, vector_agent.role, visual_agent.role, judge_agent.role}
        assert len(roles) == 4  # All unique

    def test_different_output_types(self):
        """Test each crew has different Pydantic output type."""
        graph_crew = create_graph_search_crew()
        vector_crew = create_vector_search_crew()
        visual_crew = create_visual_search_crew()
        judge_crew = create_judge_crew()

        output_types = {
            graph_crew.tasks[0].output_pydantic.__name__,
            vector_crew.tasks[0].output_pydantic.__name__,
            visual_crew.tasks[0].output_pydantic.__name__,
            judge_crew.tasks[0].output_pydantic.__name__
        }
        assert len(output_types) == 4  # All unique
        assert "GraphSearchResult" in output_types
        assert "VectorSearchResult" in output_types
        assert "VisualSearchResult" in output_types
        assert "JudgmentResult" in output_types
