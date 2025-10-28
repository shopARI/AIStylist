"""
Onboarding Crew

Manages the conversational onboarding flow using specialized agents.
"""

from crewai import Crew, Task, Process
from typing import Dict, List, Any, Optional
import json

from agents.onboarding_agent import (
    create_onboarding_agent,
    create_information_extraction_agent
)
from prompts.onboarding_prompts import (
    get_step_prompt,
    format_conversation_context,
    get_all_step_ids
)


class OnboardingCrew:
    """
    Manages conversational onboarding using AI agents.

    This crew coordinates:
    - Natural conversation flow
    - Information extraction
    - Progress tracking
    - Data validation
    """

    def __init__(self, llm: Optional[object] = None):
        """
        Initialize the onboarding crew.

        Args:
            llm: Optional language model to use for agents
        """
        self.llm = llm
        self.onboarding_agent = create_onboarding_agent(llm)
        self.extraction_agent = create_information_extraction_agent(llm)

        # Track conversation state
        self.current_step_id: Optional[str] = None
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.extracted_data: Dict[str, Any] = {}
        self.step_completion: Dict[str, bool] = {}

    def start_step(self, step_id: str) -> str:
        """
        Start a new onboarding step.

        Args:
            step_id: ID of the step to start

        Returns:
            Opening message from the agent
        """
        self.current_step_id = step_id
        if step_id not in self.conversation_history:
            self.conversation_history[step_id] = []

        prompt = get_step_prompt(step_id)

        # Create task for opening message
        opening_task = Task(
            description=f"""
Start a conversation about: {prompt.get('title', 'this topic')}

{prompt.get('conversation_guide', '')}

IMPORTANT:
- Start with a warm, open-ended question
- Make it feel like a conversation, not an interview
- Show genuine curiosity
- Set the user at ease, especially for sensitive topics
- Don't info-dump or list questions

Give ONLY your opening message to the user. Nothing else.
            """,
            agent=self.onboarding_agent,
            expected_output="A warm, conversational opening message"
        )

        crew = Crew(
            agents=[self.onboarding_agent],
            tasks=[opening_task],
            process=Process.sequential,
            verbose=False
        )

        result = crew.kickoff()
        opening_message = str(result)

        # Store in history
        self.conversation_history[step_id].append({
            "agent_message": opening_message,
            "user_message": None
        })

        return opening_message

    def process_user_response(self, user_message: str) -> Dict[str, Any]:
        """
        Process user response and generate next agent message.

        Args:
            user_message: User's response

        Returns:
            Dict with agent_response, extracted_data, and step_complete flag
        """
        if not self.current_step_id:
            raise ValueError("No active step. Call start_step() first.")

        # Update conversation history
        if self.conversation_history[self.current_step_id]:
            self.conversation_history[self.current_step_id][-1]["user_message"] = user_message

        step_prompt = get_step_prompt(self.current_step_id)
        context = format_conversation_context(
            self.current_step_id,
            user_message,
            self.conversation_history[self.current_step_id]
        )

        # Task 1: Extract information from the response
        extraction_task = Task(
            description=f"""
Analyze the user's response and extract relevant information.

{context}

Based on the user's responses in this conversation, extract:
{json.dumps(step_prompt.get('focus', []), indent=2)}

Output a JSON object with any information you can extract from the conversation.
For items not yet mentioned or unclear, use null.

Example output format:
{{
    "advice_receptiveness": 7,
    "creative_control": 5,
    "risk_tolerance": null,
    "decision_making_style": "curated_options",
    "completeness": 0.65,
    "missing_info": ["risk_tolerance"],
    "confidence": "medium"
}}

Return ONLY valid JSON. No other text.
            """,
            agent=self.extraction_agent,
            expected_output="JSON object with extracted information"
        )

        # Task 2: Generate conversational response
        conversation_task = Task(
            description=f"""
Continue the conversation naturally based on the user's response.

{context}

The user just said: "{user_message}"

Your response should:
- Acknowledge what they shared
- Ask a thoughtful follow-up question if more info is needed
- Explore deeper if they seemed uncertain or hesitant
- Move to summary/transition if this topic feels complete
- Stay warm and conversational

DECISION POINT:
- If you feel you have good understanding of all the focus areas, you can offer to move on
- If there are gaps or the user wants to explore more, keep going
- Never rush them

Give ONLY your next message to the user. Nothing else.
            """,
            agent=self.onboarding_agent,
            expected_output="Next conversational message to the user"
        )

        crew = Crew(
            agents=[self.extraction_agent, self.onboarding_agent],
            tasks=[extraction_task, conversation_task],
            process=Process.sequential,
            verbose=False
        )

        result = crew.kickoff()

        # Parse results
        try:
            # Extraction result is from first task
            extraction_result = extraction_task.output.raw
            extracted_info = json.loads(extraction_result)

            # Update extracted data
            if self.current_step_id not in self.extracted_data:
                self.extracted_data[self.current_step_id] = {}
            self.extracted_data[self.current_step_id].update(extracted_info)

        except json.JSONDecodeError:
            extracted_info = {}

        # Conversation response is from second task
        agent_response = str(conversation_task.output.raw)

        # Store in history
        self.conversation_history[self.current_step_id].append({
            "agent_message": agent_response,
            "user_message": None
        })

        # Check if step is complete
        completeness = extracted_info.get('completeness', 0.0)
        step_complete = completeness >= 0.8  # 80% threshold

        return {
            "agent_response": agent_response,
            "extracted_data": extracted_info,
            "step_complete": step_complete,
            "completeness": completeness
        }

    def complete_step(self) -> bool:
        """
        Mark current step as complete.

        Returns:
            Success boolean
        """
        if self.current_step_id:
            self.step_completion[self.current_step_id] = True
            return True
        return False

    def get_next_step(self) -> Optional[str]:
        """
        Get the next uncompleted step.

        Returns:
            Next step ID or None if all complete
        """
        all_steps = get_all_step_ids()
        for step_id in all_steps:
            if not self.step_completion.get(step_id, False):
                return step_id
        return None

    def get_all_extracted_data(self) -> Dict[str, Any]:
        """
        Get all extracted data from all steps.

        Returns:
            Dictionary of all extracted information
        """
        return self.extracted_data

    def get_completion_percentage(self) -> float:
        """
        Get overall onboarding completion percentage.

        Returns:
            Percentage (0.0 to 1.0)
        """
        all_steps = get_all_step_ids()
        if not all_steps:
            return 0.0

        completed = sum(1 for step in all_steps if self.step_completion.get(step, False))
        return completed / len(all_steps)

    def is_complete(self) -> bool:
        """Check if all onboarding steps are complete."""
        return self.get_completion_percentage() >= 1.0

    def reset(self):
        """Reset the onboarding crew to start fresh."""
        self.current_step_id = None
        self.conversation_history = {}
        self.extracted_data = {}
        self.step_completion = {}


def create_onboarding_crew(llm: Optional[object] = None) -> OnboardingCrew:
    """
    Factory function to create an onboarding crew.

    Args:
        llm: Optional language model

    Returns:
        Configured OnboardingCrew instance
    """
    return OnboardingCrew(llm=llm)
