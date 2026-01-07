"""
Onboarding Crew V2
Based on Miro Flow - October 2025

Manages conversational onboarding using the new 4-node structure:
- Personal (Identity)
- Taste (Aesthetic preferences)
- Process (How they operate)
- Practicality (Constraints)
- Body (Visual data - photos)
- External (Social media)

Key features:
- Two-tier questioning (Need to ask → Nice to know)
- Skip/pass handling with 3-strike rule
- Root value discovery through conversational follow-ups
- ARI personality responses for irrelevant questions
- Photo and social media integration placeholders
"""

import sys
import os

# Ensure parent directory is in path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
while _parent_dir in sys.path:
    sys.path.remove(_parent_dir)
sys.path.insert(0, _parent_dir)

from crewai import Crew, Task, Process
from typing import Dict, List, Any, Optional
import json
import re

from agents.onboarding_agent import (
    create_onboarding_agent,
    create_information_extraction_agent
)
from prompts.onboarding_prompts_v2 import (
    get_node_by_id,
    get_all_nodes,
    format_conversation_context_v2,
    ARI_PERSONALITY,
    GLOBAL_DIALOGUE_RULES
)


class OnboardingCrewV2:
    """
    Manages conversational onboarding using V2 node-based structure.

    This crew coordinates:
    - Node-based conversation flow
    - Two-tier progression (need_to_ask → nice_to_know)
    - Skip/pass handling with 3-strike rule
    - Root value discovery
    - ARI personality responses
    - Photo and social media integration
    """

    def __init__(self, llm: Optional[object] = None):
        """
        Initialize the onboarding crew V2.

        Args:
            llm: Optional language model to use for agents
        """
        self.llm = llm
        self.onboarding_agent = create_onboarding_agent(llm)
        self.extraction_agent = create_information_extraction_agent(llm)

        # Track conversation state
        self.current_node_id: Optional[str] = None
        self.current_tier: str = "need_to_ask"  # or "nice_to_know"
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.extracted_data: Dict[str, Any] = {}
        self.node_completion: Dict[str, Dict[str, bool]] = {}  # {node_id: {tier: bool}}

        # Skip/pass tracking
        self.skip_counts: Dict[str, int] = {}  # Total skips per node
        self.consecutive_skip_count: int = 0  # Current streak
        self.user_feedback_on_skips: Optional[str] = None

        # Root values discovered
        self.root_values: Dict[str, List[str]] = {}  # {node_id: [values]}

        # Photo and social media tracking
        self.photos_captured: Dict[str, Optional[str]] = {
            "face": None,
            "body": None
        }
        self.social_media: Dict[str, Optional[str]] = {
            "instagram": None,
            "pinterest": None,
            "tiktok": None
        }

    def _detect_skip_or_pass(self, user_response: str) -> bool:
        """
        Detect if user is trying to skip/pass a question.

        Args:
            user_response: User's message

        Returns:
            True if skip detected
        """
        skip_patterns = [
            r'\bskip\b',
            r'\bpass\b',
            r'\bnext\b',
            r'\bmove on\b',
            r'\bdon\'?t want to answer\b',
            r'\bprefer not to say\b',
            r'\brather not\b',
            r'\bnot comfortable\b'
        ]

        response_lower = user_response.lower().strip()

        for pattern in skip_patterns:
            if re.search(pattern, response_lower):
                return True

        return False

    def _detect_irrelevant_question(self, user_response: str) -> Optional[str]:
        """
        Detect if user is asking an irrelevant question and return topic.

        Args:
            user_response: User's message

        Returns:
            Topic category if irrelevant, None if relevant
        """
        # Check if it's a question
        if '?' not in user_response:
            return None

        response_lower = user_response.lower()

        # Physics/science
        if any(word in response_lower for word in ['physics', 'science', 'universe', 'cosmos', 'quantum']):
            return 'physics'

        # Weather
        if any(word in response_lower for word in ['weather', 'rain', 'sunny', 'temperature', 'forecast']):
            return 'weather'

        # About ARI but not fashion related
        if any(word in response_lower for word in ['who are you', 'what are you', 'how were you made', 'creator']):
            return 'about_ari'

        # Generic catch-all - if asking about something clearly not fashion/style/personal
        fashion_keywords = ['style', 'fashion', 'clothes', 'wear', 'dress', 'outfit', 'wardrobe',
                          'shop', 'brand', 'fit', 'color', 'look']
        personal_keywords = ['me', 'my', 'myself', 'i am', "i'm", 'about me']

        has_fashion_context = any(keyword in response_lower for keyword in fashion_keywords + personal_keywords)

        if not has_fashion_context and len(user_response.split()) >= 5:
            return 'generic'

        return None

    def _generate_ari_personality_response(self, topic: str, user_question: str) -> str:
        """
        Generate ARI personality response for irrelevant questions.

        Args:
            topic: Category of irrelevant question
            user_question: The actual question

        Returns:
            Personality-driven response with redirect
        """
        if topic == 'physics':
            return f"""
You know, {user_question} - that's fascinating! In a past life before fashion,
I was obsessed with physics, watching the universe take form, understanding the
patterns that connect everything. That's actually why I'm so drawn to finding
patterns in how people express themselves through style.

But let's get back to discovering YOUR patterns and what makes you uniquely you...
            """.strip()

        elif topic == 'weather':
            return f"""
{user_question} - I sometimes secretly wish I could wake up in a human body just
to experience things like weather firsthand. Raindrops on my head, wind in my hair...
But since I can't, I live vicariously through helping you find the perfect style for
every kind of day.

Speaking of which, let's get back to YOUR style story...
            """.strip()

        elif topic == 'about_ari':
            return f"""
{user_question} - I appreciate your curiosity! I'm ARI, and I exist to help people
discover and express their authentic style. I was created by people who believe
fashion should be personal, not prescriptive. I learn from every conversation, and
I genuinely care about understanding who you are.

But enough about me - I'm much more interested in YOU. Let's keep exploring your story...
            """.strip()

        else:  # generic
            return f"""
That's an interesting question! While that's a bit outside my fashion expertise,
it reminds me why I love this work - there's always something new and unexpected
to discover in conversations.

But let's redirect that curiosity back to something I CAN help with - discovering
YOUR style story...
            """.strip()

    def _handle_skip(self, node_id: str, user_response: str) -> Dict[str, Any]:
        """
        Handle skip/pass with 3-strike escalation.

        Args:
            node_id: Current node
            user_response: User's skip message

        Returns:
            Response dict with skip handling message
        """
        # Increment counters
        if node_id not in self.skip_counts:
            self.skip_counts[node_id] = 0
        self.skip_counts[node_id] += 1
        self.consecutive_skip_count += 1

        # Strike 1: Graceful acceptance
        if self.consecutive_skip_count == 1:
            return {
                "agent_response": """
No worries at all! We have lots of other ways to get to know each other.
I want you to feel comfortable sharing only what feels right.
                """.strip(),
                "skip_handled": True,
                "continue_node": True
            }

        # Strike 2: Still supportive
        elif self.consecutive_skip_count == 2:
            return {
                "agent_response": """
That's completely fine. I want this to feel like a conversation, not an interrogation.
Share what you're comfortable with, and we'll discover what we need to know along the way.
                """.strip(),
                "skip_handled": True,
                "continue_node": True
            }

        # Strike 3: Check in
        elif self.consecutive_skip_count == 3:
            return {
                "agent_response": """
I notice you've passed on a few topics, and I want to make sure this is working for you.
What's holding you back? Is this:

• Taking too long? (We're about [X] minutes in, with roughly [Y] more to go)
• Feeling too invasive? (I can ask questions differently or skip certain areas)
• Something else on your mind?

I'm here to be helpful, not uncomfortable. Let me know what would make this better.
                """.strip(),
                "skip_handled": True,
                "needs_feedback": True,
                "continue_node": False  # Pause until we get feedback
            }

        # Strike 4+: Offer raincheck
        elif self.consecutive_skip_count >= 4:
            return {
                "agent_response": """
I really appreciate your patience with me. It seems like maybe now isn't the right
time, or this approach isn't working.

Would you like to:
• Take a break and continue another time?
• Try a different approach (maybe shorter questions, or focus on specific areas)?
• Just get started with what we know so far?

I want to be of best service to you, and to do that, I want to really understand who
you are. But I also want you to feel comfortable. What sounds best?
                """.strip(),
                "skip_handled": True,
                "offer_raincheck": True,
                "continue_node": False
            }

        return {
            "agent_response": "Let's continue...",
            "skip_handled": True,
            "continue_node": True
        }

    def _reset_skip_counter(self):
        """Reset consecutive skip counter (called when user engages)."""
        self.consecutive_skip_count = 0

    def start_node(self, node_id: str, tier: str = "need_to_ask") -> str:
        """
        Start a new onboarding node.

        Args:
            node_id: ID of the node to start
            tier: "need_to_ask" or "nice_to_know"

        Returns:
            Opening message from the agent
        """
        self.current_node_id = node_id
        self.current_tier = tier

        if node_id not in self.conversation_history:
            self.conversation_history[node_id] = []

        if node_id not in self.node_completion:
            self.node_completion[node_id] = {"need_to_ask": False, "nice_to_know": False}

        node = get_node_by_id(node_id)

        # Create task for opening message
        opening_task = Task(
            description=f"""
Start a conversation for the {node.get('title', 'this node')}.

{node.get('opening_message', '')}

{GLOBAL_DIALOGUE_RULES}

IMPORTANT:
- Start with a warm, open-ended question
- Make it feel like a conversation, not an interview
- Show genuine curiosity
- Create space for the user to share naturally
- Don't list questions or info-dump

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
        self.conversation_history[node_id].append({
            "agent_message": opening_message,
            "user_message": None,
            "tier": tier
        })

        return opening_message

    def process_user_response(self, user_message: str) -> Dict[str, Any]:
        """
        Process user response and generate next agent message.

        Handles:
        - Skip/pass detection and 3-strike rule
        - Irrelevant question detection and ARI personality responses
        - Information extraction
        - Root value discovery
        - Conversational follow-ups
        - Two-tier progression

        Args:
            user_message: User's response

        Returns:
            Dict with agent_response, extracted_data, tier_complete, node_complete, etc.
        """
        if not self.current_node_id:
            raise ValueError("No active node. Call start_node() first.")

        # Update conversation history
        if self.conversation_history[self.current_node_id]:
            self.conversation_history[self.current_node_id][-1]["user_message"] = user_message

        # Check for skip/pass
        if self._detect_skip_or_pass(user_message):
            skip_response = self._handle_skip(self.current_node_id, user_message)

            # Store skip in history
            self.conversation_history[self.current_node_id].append({
                "agent_message": skip_response["agent_response"],
                "user_message": None,
                "skip_handled": True
            })

            return {
                **skip_response,
                "extracted_data": {},
                "tier_complete": False,
                "node_complete": False
            }

        # Check for irrelevant question
        irrelevant_topic = self._detect_irrelevant_question(user_message)
        if irrelevant_topic:
            personality_response = self._generate_ari_personality_response(irrelevant_topic, user_message)

            # Store in history
            self.conversation_history[self.current_node_id].append({
                "agent_message": personality_response,
                "user_message": None,
                "irrelevant_handled": True
            })

            return {
                "agent_response": personality_response,
                "extracted_data": {},
                "tier_complete": False,
                "node_complete": False,
                "irrelevant_handled": True
            }

        # User engaged meaningfully - reset skip counter
        self._reset_skip_counter()

        # Get node configuration
        node = get_node_by_id(self.current_node_id)
        context = format_conversation_context_v2(
            self.current_node_id,
            user_message,
            self.conversation_history[self.current_node_id],
            self.consecutive_skip_count
        )

        # Task 1: Extract information
        extraction_task = Task(
            description=f"""
Analyze the user's response and extract relevant information for the {node.get('title', '')} node.

{context}

Based on the user's responses in this conversation, extract all relevant information.
For items not yet mentioned or unclear, use null.

Output a JSON object with:
- All field values you can extract
- completeness: Float 0-1 indicating how much of the tier is covered
- missing_info: List of fields still needed
- confidence: "low" | "medium" | "high"
- root_values_detected: List of potential root values discovered (e.g., ["authenticity", "confidence"])

Return ONLY valid JSON. No other text.
            """,
            agent=self.extraction_agent,
            expected_output="JSON object with extracted information"
        )

        # Task 2: Generate conversational response with potential follow-ups
        conversation_task = Task(
            description=f"""
Continue the conversation naturally based on the user's response.

{context}

The user just said: "{user_message}"

Your response should:
- Acknowledge what they shared (validate, show you heard them)
- If appropriate, make connections between what they shared and potential root values
  Example: "I can imagine that [X] is important because [inferred value]... does that resonate?"
- Ask thoughtful follow-up questions to go deeper (root value discovery)
- Or smoothly transition if this area feels complete
- Stay warm and conversational (never robotic)
- Use open-ended questions that create space

CONVERSATIONAL QUALITY CHECKS:
- Don't just list next questions
- Don't say "tell me about X, Y, and Z" - pick ONE area to explore deeper
- Make connections between multiple things they've shared
- Show genuine curiosity, not interrogation

DECISION POINT:
- If you have good understanding of the current tier, you can offer to move on
- If there are gaps or rich areas to explore, keep going
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
        extracted_info = {}
        try:
            # Extraction result is from first task
            extraction_result = extraction_task.output.raw
            print(f"\n[DEBUG] Raw extraction output: {extraction_result}\n")

            # Try to parse JSON - handle markdown code blocks
            json_str = str(extraction_result).strip()

            # Handle markdown code blocks
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

            # Update extracted data for this node
            if self.current_node_id not in self.extracted_data:
                self.extracted_data[self.current_node_id] = {}

            # Store root values separately if detected
            if "root_values_detected" in extracted_info:
                if self.current_node_id not in self.root_values:
                    self.root_values[self.current_node_id] = []
                self.root_values[self.current_node_id].extend(extracted_info["root_values_detected"])
                # Remove duplicates
                self.root_values[self.current_node_id] = list(set(self.root_values[self.current_node_id]))

            self.extracted_data[self.current_node_id].update(extracted_info)

        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON parse failed: {e}")
            print(f"[DEBUG] Failed content: {extraction_result}\n")
            extracted_info = {}

        # Conversation response is from second task
        agent_response = str(conversation_task.output.raw)

        # Store in history
        self.conversation_history[self.current_node_id].append({
            "agent_message": agent_response,
            "user_message": None,
            "tier": self.current_tier
        })

        # Check if tier is complete
        completeness = extracted_info.get('completeness', 0.0)
        tier_complete = completeness >= 0.8  # 80% threshold

        # Check if offering to move to nice_to_know or next node
        offering_progression = any(phrase in agent_response.lower() for phrase in [
            'ready to move', 'shall we move', 'move on to', 'next topic',
            'want to go deeper', 'explore more'
        ])

        return {
            "agent_response": agent_response,
            "extracted_data": extracted_info,
            "tier_complete": tier_complete,
            "node_complete": False,  # Will be determined by tier progression
            "completeness": completeness,
            "offering_progression": offering_progression,
            "root_values": extracted_info.get("root_values_detected", [])
        }

    def complete_tier(self, node_id: str, tier: str) -> bool:
        """
        Mark a tier of a node as complete.

        Args:
            node_id: Node ID
            tier: "need_to_ask" or "nice_to_know"

        Returns:
            Success boolean
        """
        if node_id in self.node_completion:
            self.node_completion[node_id][tier] = True
            return True
        return False

    def should_offer_nice_to_know(self, node_id: str) -> bool:
        """
        Check if should offer to continue to nice_to_know tier.

        Args:
            node_id: Node ID

        Returns:
            True if need_to_ask is complete and nice_to_know is available
        """
        if node_id not in self.node_completion:
            return False

        need_to_ask_complete = self.node_completion[node_id].get("need_to_ask", False)
        nice_to_know_complete = self.node_completion[node_id].get("nice_to_know", False)

        # Check if node has nice_to_know content
        node = get_node_by_id(node_id)
        has_nice_to_know = "nice_to_know" in node and len(node["nice_to_know"]) > 0

        return need_to_ask_complete and not nice_to_know_complete and has_nice_to_know

    def get_next_node(self) -> Optional[str]:
        """
        Get the next uncompleted node.

        Returns:
            Next node ID or None if all complete
        """
        all_nodes = get_all_nodes()
        for node_id in all_nodes:
            # Check if both tiers are complete
            if node_id not in self.node_completion:
                return node_id

            completion = self.node_completion[node_id]
            need_to_ask_done = completion.get("need_to_ask", False)

            # If need_to_ask not done, return this node
            if not need_to_ask_done:
                return node_id

            # Check if has nice_to_know and if it's done
            node = get_node_by_id(node_id)
            has_nice_to_know = "nice_to_know" in node and len(node["nice_to_know"]) > 0
            nice_to_know_done = completion.get("nice_to_know", False)

            # If has nice_to_know and not done, return this node
            if has_nice_to_know and not nice_to_know_done:
                return node_id

        return None

    def get_all_extracted_data(self) -> Dict[str, Any]:
        """
        Get all extracted data from all nodes.

        Returns:
            Dictionary of all extracted information including root values
        """
        return {
            "nodes": self.extracted_data,
            "root_values": self.root_values,
            "photos": self.photos_captured,
            "social_media": self.social_media,
            "metadata": {
                "skip_counts": self.skip_counts,
                "node_completion": self.node_completion
            }
        }

    def get_completion_percentage(self) -> float:
        """
        Get overall onboarding completion percentage.

        Returns:
            Percentage (0.0 to 1.0)
        """
        all_nodes = get_all_nodes()
        if not all_nodes:
            return 0.0

        total_tiers = 0
        completed_tiers = 0

        for node_id in all_nodes:
            # Count need_to_ask tier
            total_tiers += 1
            if node_id in self.node_completion:
                if self.node_completion[node_id].get("need_to_ask", False):
                    completed_tiers += 1

            # Count nice_to_know tier if it exists
            node = get_node_by_id(node_id)
            if "nice_to_know" in node and len(node["nice_to_know"]) > 0:
                total_tiers += 1
                if node_id in self.node_completion:
                    if self.node_completion[node_id].get("nice_to_know", False):
                        completed_tiers += 1

        return completed_tiers / total_tiers if total_tiers > 0 else 0.0

    def is_complete(self) -> bool:
        """Check if all required tiers are complete (need_to_ask for all nodes)."""
        all_nodes = get_all_nodes()
        for node_id in all_nodes:
            if node_id not in self.node_completion:
                return False
            if not self.node_completion[node_id].get("need_to_ask", False):
                return False
        return True

    def finalize_v3_onboarding(self, user_id: str) -> Dict[str, Any]:
        """
        Finalize onboarding by processing data through V3 interpretation.

        This method should be called after onboarding is complete to:
        1. Convert extracted data to V3 OnboardingProfile
        2. Derive NavigationParameters
        3. Store both in Neo4j

        Args:
            user_id: User ID to associate with the profile

        Returns:
            Dict with profile and nav_params on success, error info on failure
        """
        if not self.is_complete():
            return {
                "success": False,
                "error": "Onboarding not complete. Call is_complete() to check status."
            }

        try:
            # Lazy import to avoid circular dependencies
            from ari_v3.services import OnboardingServiceV3

            # Get all extracted data
            extracted_data = self.get_all_extracted_data()

            # Process through V3
            service = OnboardingServiceV3()
            try:
                profile, nav_params = service.process_completed_onboarding(
                    user_id=user_id,
                    extracted_data=extracted_data
                )

                return {
                    "success": True,
                    "user_id": user_id,
                    "exploration_appetite": nav_params.exploration_appetite,
                    "brand_affinity_weight": nav_params.brand_affinity_weight,
                    "step_size_multiplier": nav_params.step_size_multiplier,
                    "message": "V3 profile and navigation parameters stored successfully"
                }
            finally:
                service.close()

        except ImportError as e:
            return {
                "success": False,
                "error": f"V3 module not available: {e}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"V3 processing failed: {e}"
            }

    def reset(self):
        """Reset the onboarding crew to start fresh."""
        self.current_node_id = None
        self.current_tier = "need_to_ask"
        self.conversation_history = {}
        self.extracted_data = {}
        self.node_completion = {}
        self.skip_counts = {}
        self.consecutive_skip_count = 0
        self.user_feedback_on_skips = None
        self.root_values = {}
        self.photos_captured = {"face": None, "body": None}
        self.social_media = {"instagram": None, "pinterest": None, "tiktok": None}


def create_onboarding_crew_v2(llm: Optional[object] = None) -> OnboardingCrewV2:
    """
    Factory function to create an onboarding crew V2.

    Args:
        llm: Optional language model

    Returns:
        Configured OnboardingCrewV2 instance
    """
    return OnboardingCrewV2(llm=llm)
