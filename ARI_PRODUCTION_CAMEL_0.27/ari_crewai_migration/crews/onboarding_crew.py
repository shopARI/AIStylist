"""
Onboarding Crew

Manages the conversational onboarding flow using specialized agents.
"""

import sys
import os

# Ensure parent directory is in path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Remove from path if present, then add at front to avoid conflicts
while _parent_dir in sys.path:
    sys.path.remove(_parent_dir)
sys.path.insert(0, _parent_dir)

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

        # Conversation adaptation
        self.conversation_style: Optional[str] = None  # "directive" | "exploratory" | "balanced"

    def _determine_conversation_style(self) -> str:
        """
        Determine conversation style based on user's autonomy preferences.

        Returns:
            "directive", "exploratory", or "balanced"
        """
        # Check if we have autonomy data from first step
        if 'style_autonomy' not in self.extracted_data:
            return "balanced"  # Default for first step

        autonomy_data = self.extracted_data['style_autonomy']

        # Extract key indicators
        advice_receptiveness = autonomy_data.get('advice_receptiveness', 5)
        creative_control = autonomy_data.get('creative_control', 5)
        decision_style = autonomy_data.get('decision_making_style', 'curated_options')

        # Calculate autonomy score (1-10, lower = wants more guidance)
        autonomy_score = (advice_receptiveness + creative_control) / 2

        # Determine style
        if autonomy_score <= 4 or decision_style == 'tell_me':
            return "directive"  # User wants guidance
        elif autonomy_score >= 7 or decision_style == 'many_options':
            return "exploratory"  # User wants to explore
        else:
            return "balanced"  # Moderate approach

    def _get_style_guidance(self) -> str:
        """
        Get conversation style guidance for the agent.

        Returns:
            Style guidance string
        """
        style = self.conversation_style or self._determine_conversation_style()

        if style == "directive":
            return """
CONVERSATION STYLE ADAPTATION:
Based on this user's preferences, they want more guidance and direction.

Adjust your approach:
- Be more direct and specific in your questions
- Offer concrete examples and suggestions
- Guide them toward decisions with your expertise
- Don't overwhelm with too many options
- Be reassuring and confident in your recommendations
- Example: "Based on what you've shared, I'd recommend focusing on..."
            """
        elif style == "exploratory":
            return """
CONVERSATION STYLE ADAPTATION:
Based on this user's preferences, they want creative freedom and exploration.

Adjust your approach:
- Ask more open-ended questions
- Let them lead the conversation
- Encourage exploration and experimentation
- Present multiple perspectives and options
- Be curious about their unique vision
- Example: "Tell me more about what draws you to that style..."
            """
        else:  # balanced
            return """
CONVERSATION STYLE ADAPTATION:
This user prefers a balanced approach - some guidance with room for input.

Adjust your approach:
- Mix directed questions with open exploration
- Offer curated options (not too many, not just one)
- Guide while respecting their preferences
- Be collaborative in tone
- Example: "Here are a few directions we could explore, which resonates with you?"
            """

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
        # Inject style guidance based on user's autonomy level
        style_guidance = self._get_style_guidance()

        conversation_task = Task(
            description=f"""
Continue the conversation naturally based on the user's response.

{context}

{style_guidance}

The user just said: "{user_message}"

Your response should:
- Acknowledge what they shared
- Ask a thoughtful follow-up question if more info is needed
- Explore deeper if they seemed uncertain or hesitant
- Move to summary/transition if this topic feels complete
- Stay warm and conversational
- IMPORTANT: Adapt your questioning style based on the style guidance above

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
            print(f"\n[DEBUG] Raw extraction output: {extraction_result}\n")

            # Try to parse JSON - handle markdown code blocks
            json_str = str(extraction_result).strip()

            # Handle markdown code blocks (```json ... ``` or ``` ... ```)
            if "```json" in json_str:
                start = json_str.find("```json") + 7
                end = json_str.find("```", start)
                json_str = json_str[start:end].strip()
            elif "```" in json_str:
                start = json_str.find("```") + 3
                end = json_str.rfind("```")
                json_str = json_str[start:end].strip()

            extracted_info = json.loads(json_str)
            print(f"[DEBUG] Successfully parsed extraction: {extracted_info}\n")

            # Update extracted data
            if self.current_step_id not in self.extracted_data:
                self.extracted_data[self.current_step_id] = {}
            self.extracted_data[self.current_step_id].update(extracted_info)

        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON parse failed: {e}")
            print(f"[DEBUG] Failed content: {extraction_result}\n")
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
