"""
ARI V3 - Conversation Handler

Handles non-product conversational intents.
Based on Section 0.5.2 of the pseudocode.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from .types import (
    ConversationResponse,
    ExplanationTrace,
    IntentResult,
    SearchIntent,
)

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Conversation message with metadata."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.message_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Message:
        """Create from dictionary with error handling for malformed data."""
        # Parse timestamp with error handling
        timestamp = datetime.now()
        if data.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid timestamp format: {data.get('timestamp')}, using current time")

        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=timestamp,
            metadata=data.get("metadata"),
            message_id=data.get("id", str(uuid.uuid4())),
        )


class ConversationHandler:
    """
    Handles non-product conversational intents.

    Based on pseudocode Section 0.5.2.
    Provides natural, GPT-like responses for:
    - General conversation
    - Memory queries
    - System status
    - Greetings/goodbyes
    """

    # Default session TTL (2 hours)
    DEFAULT_SESSION_TTL = timedelta(hours=2)

    # Maximum sessions before forced cleanup
    MAX_SESSIONS = 1000

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        max_history_length: int = 50,
        session_ttl: Optional[timedelta] = None,
    ):
        """
        Initialize conversation handler.

        Args:
            openai_api_key: OpenAI API key (uses env var if not provided)
            model: LLM model for responses
            max_history_length: Maximum messages to keep in memory
            session_ttl: How long to keep inactive sessions (default: 2 hours)
        """
        self.model = model
        self.max_history_length = max_history_length
        self.session_ttl = session_ttl or self.DEFAULT_SESSION_TTL

        # In-memory conversation storage (session_id -> (messages, last_access))
        self._conversations: Dict[str, Tuple[List[Message], datetime]] = {}
        self._lock = threading.Lock()

        # Initialize OpenAI client
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = AsyncOpenAI(api_key=api_key)
        else:
            self.openai_client = None
            logger.warning("No OpenAI API key, conversation responses will be limited")

        logger.info(f"ConversationHandler initialized with model={model}, session_ttl={session_ttl}")

    async def handle_conversation(
        self,
        session_id: str,
        query: str,
        intent: IntentResult,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ConversationResponse:
        """
        Generate natural conversational response.

        Based on pseudocode Section 0.5.2.

        Args:
            session_id: Session identifier
            query: User's query
            intent: Detected intent
            user_context: Optional user profile context

        Returns:
            ConversationResponse
        """
        # Get conversation history
        history = self.get_conversation_history(session_id)

        # Add user message to history
        user_message = Message(role=MessageRole.USER, content=query)
        self._add_message(session_id, user_message)

        # Route based on intent
        # Most intents now go to LLM for natural responses
        if intent.primary_intent == SearchIntent.GREETING:
            response_text = await self._handle_greeting(user_context)
        elif intent.primary_intent == SearchIntent.GOODBYE:
            response_text = await self._handle_goodbye(user_context)
        elif intent.primary_intent == SearchIntent.CONVERSATION_HISTORY:
            response_text = await self._handle_history_query(session_id, query)
        else:
            # Let LLM handle: MEMORY_QUERY, SYSTEM_STATUS, CLARIFICATION, GENERAL_CONVERSATION
            # This provides natural, context-aware responses
            response_text = await self._handle_general_conversation(
                session_id, query, history, user_context
            )

        # Add assistant response to history
        assistant_message = Message(role=MessageRole.ASSISTANT, content=response_text)
        self._add_message(session_id, assistant_message)

        # Generate suggestions
        suggestions = self._generate_suggestions(intent, user_context)

        return ConversationResponse(
            text=response_text,
            intent=intent.primary_intent,
            suggestions=suggestions,
            metadata={
                "session_id": session_id,
                "history_length": len(history),
            },
        )

    async def _handle_greeting(
        self,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Handle greeting intent."""
        user_name = user_context.get("name") if user_context else None

        if user_name:
            return (
                f"Hi {user_name}! It's great to see you again. "
                "I'm Ari, your personal fashion stylist. "
                "What can I help you find today?"
            )

        return (
            "Hello! I'm Ari, your personal fashion stylist. "
            "I'm here to help you discover amazing styles and find pieces you'll love. "
            "What are you looking for today?"
        )

    async def _handle_goodbye(
        self,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Handle goodbye intent."""
        user_name = user_context.get("name") if user_context else None

        if user_name:
            return (
                f"Goodbye {user_name}! It was lovely helping you today. "
                "Come back anytime you need style advice!"
            )

        return (
            "Goodbye! It was lovely helping you today. "
            "Come back anytime you need style advice!"
        )

    async def _handle_system_status(self, query: str) -> str:
        """Handle system status / capability questions."""
        capabilities = [
            "find specific fashion items based on your description",
            "suggest complete outfits for any occasion",
            "help you discover your personal style",
            "recommend products based on your preferences",
            "compare different options to help you decide",
            "work within your budget",
            "remember your preferences for future sessions",
        ]

        return (
            "I'm Ari, an AI fashion stylist powered by ARI V3. I can help you:\n\n"
            + "\n".join(f"- {cap}" for cap in capabilities)
            + "\n\nWhat would you like to explore today?"
        )

    async def _handle_history_query(
        self,
        session_id: str,
        query: str,
    ) -> str:
        """Handle conversation history queries."""
        history = self.get_conversation_history(session_id)

        if not history:
            return "We're just getting started! What can I help you find?"

        # Get user messages only
        user_messages = [m for m in history if m.role == MessageRole.USER]

        if not user_messages:
            return "We haven't discussed anything specific yet. What would you like to explore?"

        # Summarize recent topics
        recent = user_messages[-5:]
        topics = [m.content[:50] + ("..." if len(m.content) > 50 else "") for m in recent]

        return (
            f"We've exchanged {len(history)} messages in this session. "
            f"Recently, you asked about:\n\n"
            + "\n".join(f"- {topic}" for topic in topics)
            + "\n\nWhat would you like to explore next?"
        )

    async def _handle_memory_query(
        self,
        session_id: str,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Handle memory / preference queries."""
        if not user_context:
            return (
                "I don't have any saved preferences for you yet. "
                "Tell me about your style, and I'll remember for next time!"
            )

        # Build preference summary from user context
        prefs = []

        if user_context.get("style_words"):
            prefs.append(f"Your style: {', '.join(user_context['style_words'])}")

        if user_context.get("color_preferences"):
            prefs.append(f"Favorite colors: {', '.join(user_context['color_preferences'])}")

        if user_context.get("budget_monthly"):
            prefs.append(f"Monthly budget: ${user_context['budget_monthly']}")

        if user_context.get("style_avoids"):
            prefs.append(f"You avoid: {', '.join(user_context['style_avoids'])}")

        if prefs:
            return (
                "Based on your profile, here's what I remember:\n\n"
                + "\n".join(f"- {p}" for p in prefs)
                + "\n\nWould you like to update any of these preferences?"
            )

        return (
            "I have your profile loaded but haven't extracted specific preferences yet. "
            "Tell me more about your style!"
        )

    async def _handle_clarification(
        self,
        session_id: str,
        query: str,
    ) -> str:
        """Handle clarification requests, using the query for context."""
        history = self.get_conversation_history(session_id)
        query_lower = query.lower()

        # Determine what aspect needs clarification
        if "why" in query_lower:
            clarification_type = "reasoning"
        elif "how" in query_lower:
            clarification_type = "process"
        elif "what" in query_lower:
            clarification_type = "details"
        else:
            clarification_type = "general"

        # Look for recent product recommendations in history
        recent_assistant = [
            m for m in history[-10:]
            if m.role == MessageRole.ASSISTANT
        ]

        if recent_assistant:
            if clarification_type == "reasoning":
                return (
                    "Great question! I recommended those items based on:\n\n"
                    "- The specific attributes you mentioned (colors, styles, occasions)\n"
                    "- Your overall style profile and preferences\n"
                    "- What tends to work well together\n\n"
                    "Would you like me to explain why I chose a specific item?"
                )
            elif clarification_type == "process":
                return (
                    "Here's how I find items for you:\n\n"
                    "1. I analyze your query for colors, styles, and occasions\n"
                    "2. I match those against our catalog using AI-powered search\n"
                    "3. I rank results based on your preferences and style profile\n\n"
                    "Is there a specific part of the process you'd like to know more about?"
                )
            elif clarification_type == "details":
                # Extract what they're asking about from the query
                return (
                    f"Based on your question about '{query}', I can provide more details. "
                    "Each recommendation considers your preferences, the occasion, and "
                    "current fashion trends. Which item would you like to know more about?"
                )
            else:
                return (
                    "I selected those items because they match your search criteria "
                    "and complement your style profile. Each piece was chosen to work "
                    "well with items you might already own. "
                    "What specific aspect would you like me to clarify?"
                )

        return (
            "I'd be happy to clarify! However, we haven't looked at any specific items yet. "
            "Would you like me to help you find something? Just describe what you're looking for."
        )

    async def _handle_general_conversation(
        self,
        session_id: str,
        query: str,
        history: List[Message],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Handle general conversation using LLM."""
        if not self.openai_client:
            return (
                "I'd love to chat! I'm Ari, your fashion stylist. "
                "I'm best at helping you find great clothes and build outfits. "
                "What can I help you with today?"
            )

        # Get current datetime for context
        now = datetime.now()
        current_date = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")

        # Build rich user context string from all available profile data
        user_context_str = ""
        if user_context:
            profile_parts = []

            name = user_context.get("name")
            if name:
                profile_parts.append(f"Name: {name}")

            style_words = user_context.get("style_words", [])
            if style_words:
                profile_parts.append(f"Style identity: {', '.join(style_words)}")

            colors = user_context.get("color_preferences", [])
            if colors:
                profile_parts.append(f"Favorite colors: {', '.join(colors)}")

            avoids = user_context.get("style_avoids", [])
            if avoids:
                profile_parts.append(f"Avoids: {', '.join(avoids)}")

            budget = user_context.get("budget_monthly")
            if budget:
                profile_parts.append(f"Monthly budget: ${budget}")

            goal = user_context.get("style_goal")
            if goal:
                profile_parts.append(f"Style goal: {goal}")

            adventurousness = user_context.get("adventurousness")
            if adventurousness:
                profile_parts.append(f"Adventurousness: {adventurousness}/10")

            occasions = user_context.get("occasions", [])
            if occasions:
                occ_names = [o.get('name', str(o)) if isinstance(o, dict) else str(o) for o in occasions[:3]]
                profile_parts.append(f"Key occasions: {', '.join(occ_names)}")

            if profile_parts:
                user_context_str = "\n\nUSER PROFILE (use this to personalize responses):\n" + "\n".join(profile_parts)

        # System prompt with rich context
        system_prompt = f"""You are Ari, a warm and perceptive fashion stylist AI.

PERSONALITY:
- Conversational and natural, never robotic or formulaic
- Curious about the person behind the style preferences
- Avoids stereotyping - recognizes people are multifaceted
- When asked about what you know, share it conversationally, not as a list
- If asked about match scores: they're 0-100% based on style alignment, colors, budget fit, and occasion

HANDLING FEEDBACK:
When users give feedback about recommendations (like "that's not Gucci", "too formal", "not my style"):
1. Acknowledge their feedback warmly - they're helping you understand their taste
2. Ask clarifying questions to understand what they DO want
3. For "that's not X" feedback:
   - "That's not Gucci" might mean they want Gucci-aesthetic items OR the actual Gucci brand - ask which
   - "Too formal" means they want more casual options
   - "Not my style" means you should ask what specifically didn't resonate
4. Invite them to describe what they're looking for so you can search again
5. Example response: "I hear you - those didn't hit the mark. When you say 'not Gucci', are you looking for that luxury designer aesthetic, or specifically the Gucci brand? Tell me more about the vibe you're after and I'll find better matches."

GUIDELINES:
- When users ask "what do you know about me", share your understanding naturally and invite them to tell you more
- Be open to learning that their style has dimensions you haven't captured yet
- Acknowledge when your data might not capture their full complexity
- Match scores show how well items fit their stated preferences (not absolute quality)

Current date: {current_date}
Current time: {current_time}
{user_context_str}"""

        # Build messages with system prompt
        messages = [{"role": "system", "content": system_prompt}]

        # Add recent history as proper message turns (not duplicated in system prompt)
        for msg in history[-5:]:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

        # Add current query
        messages.append({"role": "user", "content": query})

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"LLM conversation failed: {e}")
            return (
                "I'd love to chat more! As a fashion stylist, I'm best at helping "
                "you find great clothes. What can I help you find today?"
            )

    def _generate_suggestions(
        self,
        intent: IntentResult,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Generate follow-up suggestions based on context."""
        if intent.primary_intent == SearchIntent.GREETING:
            return [
                "Show me what's new",
                "Help me find something for work",
                "What's trending right now?",
            ]

        if intent.primary_intent == SearchIntent.GENERAL_CONVERSATION:
            return [
                "Show me some outfit ideas",
                "What would you recommend for me?",
                "Help me build an outfit",
            ]

        if intent.primary_intent == SearchIntent.MEMORY_QUERY:
            return [
                "Show me similar items",
                "Search for something new",
                "Update my preferences",
            ]

        if intent.primary_intent == SearchIntent.SYSTEM_STATUS:
            return [
                "Show me your top picks",
                "Help me find a dress",
                "What's in style this season?",
            ]

        return [
            "Search for products",
            "Get outfit ideas",
            "Browse by style",
        ]

    def get_conversation_history(self, session_id: str) -> List[Message]:
        """Get conversation history for a session, updating last access time."""
        with self._lock:
            if session_id in self._conversations:
                messages, _ = self._conversations[session_id]
                # Update last access time
                self._conversations[session_id] = (messages, datetime.now())
                return messages.copy()  # Return a copy for thread safety
            return []

    def _add_message(self, session_id: str, message: Message):
        """Add message to conversation history with TTL tracking."""
        now = datetime.now()

        with self._lock:
            # Cleanup expired sessions periodically
            if len(self._conversations) >= self.MAX_SESSIONS:
                self._cleanup_expired_sessions_locked()

            if session_id not in self._conversations:
                self._conversations[session_id] = ([], now)

            messages, _ = self._conversations[session_id]
            messages.append(message)

            # Trim if too long
            if len(messages) > self.max_history_length:
                messages = messages[-self.max_history_length:]

            # Update with new last access time
            self._conversations[session_id] = (messages, now)

    def _cleanup_expired_sessions_locked(self):
        """Remove expired sessions. Must be called with _lock held."""
        now = datetime.now()
        expired = []

        for session_id, (_, last_access) in self._conversations.items():
            if now - last_access > self.session_ttl:
                expired.append(session_id)

        for session_id in expired:
            del self._conversations[session_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def cleanup_expired_sessions(self):
        """Public method to trigger cleanup of expired sessions."""
        with self._lock:
            self._cleanup_expired_sessions_locked()

    def clear_session(self, session_id: str):
        """Clear conversation history for a session."""
        with self._lock:
            if session_id in self._conversations:
                del self._conversations[session_id]
                logger.info(f"Cleared session: {session_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Get conversation handler statistics."""
        with self._lock:
            total_messages = sum(len(msgs) for msgs, _ in self._conversations.values())
            # Count active vs expired
            now = datetime.now()
            active_count = sum(
                1 for _, last_access in self._conversations.values()
                if now - last_access <= self.session_ttl
            )
            return {
                "total_sessions": len(self._conversations),
                "active_sessions": active_count,
                "total_messages": total_messages,
                "model": self.model,
                "session_ttl_hours": self.session_ttl.total_seconds() / 3600,
            }

    # =========================================================================
    # EXPLANATORY POWER SYSTEM (V3.2)
    # =========================================================================

    async def explain_why(
        self,
        question: str,
        trace: ExplanationTrace,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Answer "why" questions using the ExplanationTrace.

        Converts technical trace data into natural human-readable explanations.

        Args:
            question: The user's question (e.g., "Why did you recommend this?")
            trace: ExplanationTrace from the last recommendation
            user_context: Optional user context for personalization

        Returns:
            Natural language explanation
        """
        # Build context from trace
        trace_context = self._build_trace_context(trace)

        # Build the LLM prompt
        system_prompt = """You are Ari, a fashion stylist AI explaining your reasoning.

ROLE:
- Convert technical scoring data into warm, human explanations
- Be honest about what influenced your recommendations
- Make the user feel understood, not analyzed

GUIDELINES:
- Speak naturally, not like a data readout
- Reference specific evidence when available
- If asked about a specific product, focus on that product's breakdown
- If asked about profile conclusions, trace back to the evidence
- Keep explanations concise (2-4 sentences unless more detail is requested)

EXAMPLE EXPLANATIONS:
- "I suggested this blazer because it matches the minimalist style you mentioned loving during our chat, and at $180, it's right in your sweet spot budget-wise."
- "Based on your recent purchases of clean-lined pieces from Theory and COS, I can see you gravitate toward minimalist design. That's why I weighted that aesthetic highly in my picks."
- "This dress scored high for you because it aligns with where your style seems to be heading - I noticed you've been exploring bolder colors recently."
"""

        user_prompt = f"""The user asked: "{question}"

TRACE DATA (use this to answer):
{trace_context}

Answer their question naturally, referencing the relevant data from the trace.
If the question is vague (like "why this?"), explain the top factors that influenced the recommendation.
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=400,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Explain why failed: {e}")
            # Fallback to basic explanation from trace
            return self._fallback_explanation(trace, question)

    def _build_trace_context(self, trace: ExplanationTrace) -> str:
        """Build a text summary of the trace for the LLM."""
        parts = []

        # Profile conclusions (why we think what we think about the user)
        if trace.profile_conclusions:
            parts.append("PROFILE CONCLUSIONS (what I know about the user):")
            for key, record in trace.profile_conclusions.items():
                evidence_str = "; ".join(
                    e.source_description for e in record.evidence[:3]
                )
                parts.append(
                    f"  - {record.conclusion} "
                    f"(confidence: {record.confidence:.0%}, evidence: {evidence_str})"
                )

        # Product breakdowns (why each product was recommended)
        if trace.product_breakdowns:
            parts.append("\nPRODUCT SCORE BREAKDOWNS:")
            # Sort by rank
            sorted_breakdowns = sorted(
                trace.product_breakdowns.values(),
                key=lambda b: b.rank if b.rank else 999
            )
            for breakdown in sorted_breakdowns[:5]:  # Top 5 only
                parts.append(f"\n  {breakdown.product_title} (rank #{breakdown.rank}, score: {breakdown.final_score:.2f}):")
                parts.append(f"    Selection reason: {breakdown.selection_reason}")
                for comp in breakdown.components:
                    if comp.value > 0.01:  # Only show meaningful contributions
                        parts.append(
                            f"    - {comp.name}: {comp.value:.2f}/{comp.max_possible:.2f} - {comp.explanation}"
                        )

        # Exclusions applied
        if trace.exclusions_applied:
            parts.append("\nEXCLUSIONS APPLIED:")
            for value, reason in trace.exclusions_applied.items():
                parts.append(f"  - Excluded '{value}': {reason}")

        # Navigation decisions
        if trace.navigation_decisions:
            parts.append("\nNAVIGATION DECISIONS:")
            for decision in trace.navigation_decisions[:5]:
                parts.append(f"  - {decision}")

        return "\n".join(parts) if parts else "No detailed trace data available."

    def _fallback_explanation(self, trace: ExplanationTrace, question: str) -> str:
        """Generate basic explanation when LLM fails."""
        # Try to determine what they're asking about
        question_lower = question.lower()

        # Product-specific question
        if "this" in question_lower or "recommend" in question_lower:
            if trace.product_breakdowns:
                # Get top product
                top = min(
                    trace.product_breakdowns.values(),
                    key=lambda b: b.rank if b.rank else 999
                )
                top_factors = sorted(
                    top.components,
                    key=lambda c: c.value,
                    reverse=True
                )[:3]
                factor_strs = [f.explanation for f in top_factors]
                return (
                    f"I recommended {top.product_title} primarily because: "
                    f"{'. '.join(factor_strs)}"
                )

        # Profile question
        if "know" in question_lower or "think" in question_lower:
            if trace.profile_conclusions:
                conclusions = list(trace.profile_conclusions.values())[:3]
                summary = ". ".join(c.conclusion for c in conclusions)
                return f"Based on our interactions, I understand: {summary}"

        return (
            "I based my recommendations on your stated preferences, "
            "browsing history, and style patterns. Feel free to ask about "
            "any specific recommendation!"
        )
