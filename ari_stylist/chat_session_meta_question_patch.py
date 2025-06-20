"""
PATCH for chat_session_manager_async.py

Replace the existing _handle_meta_question method with this fixed version
that properly handles CAMEL imports and uses the CompatibilityLayer.

FIXED: Removes direct CAMEL imports and uses compatibility layer.
"""

import json
import logging

# This should be added to the imports at the top of chat_session_manager_async.py
from camel_imports import CompatibilityLayer, CAMEL_AVAILABLE

logger = logging.getLogger("enhanced_chat_session_manager_async")

# Replace the existing _handle_meta_question method with this fixed version:

async def _handle_meta_question(self, session: EnhancedChatSessionAsync, message: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Handle follow-up responses and meta-questions using CAMEL memory
    Enhanced with improved detection of memory-related questions
    
    FIXED: Removed direct CAMEL imports and uses compatibility layer.
    
    Args:
        session: Chat session
        message: User message
        
    Returns:
        Tuple of (response message, additional data) or None if not a meta-question
    """
    # First identify if this is a memory-related question
    memory_keywords = ["remember", "recall", "mentioned", "earlier", "previous", "before", 
                        "last time", "said", "asked", "told", "history", "conversation"]
    is_memory_question = any(keyword in message.lower() for keyword in memory_keywords)
    
    # If it's not a memory-related question, check if it's a follow-up question
    # that doesn't explicitly mention memory but requires context
    pronouns = ["it", "that", "this", "they", "them", "those", "these"]
    has_pronouns = any(f" {pronoun} " in f" {message.lower()} " for pronoun in pronouns)
    
    # Proceed if we have a memory question or a potential follow-up
    if is_memory_question or has_pronouns:
        logger.info(f"Detected potential memory-related question: '{message}'")
        
        try:
            # Get memory context with improved error handling
            memory_context, token_count = await session.get_memory_context()
            
            if not memory_context or len(memory_context) < 2:  # Need at least previous Q&A
                logger.info("Insufficient context in memory for meta-question handling")
                
                if is_memory_question:
                    # If explicitly asking about memory but no context available
                    # Return an honest response about limited context
                    
                    response_text = ("I can see you're asking about our previous conversation, "
                                    "but I don't have enough context from our earlier interaction. "
                                    "Could you help remind me what specifically you're referring to?")
                    
                    await session.add_message(response_text, "agent")
                    
                    return response_text, {
                        "result_type": "meta_response",
                        "is_follow_up": True,
                        "has_memory_context": False
                    }
                return None
            
            # Format memory context for agent
            context_messages = []
            for idx, msg in enumerate(memory_context):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                # Format nicely with clear separation
                context_messages.append(f"[Message {idx+1}] {role.upper()}: {content}")
            
            context_text = "\n\n".join(context_messages)
            
            # Get user preferences for enhanced context
            user_preferences = await session.get_or_fetch_user_preferences()
            
            # Create a meta-question detection prompt with clear instructions to use memory
            meta_question_prompt = f"""
            I need to respond to a question about our conversation history. I HAVE MEMORY and should use it to answer accurately.
            
            CONVERSATION HISTORY:
            {context_text}
            
            USER PREFERENCES:
            {json.dumps(user_preferences, indent=2)}
            
            LATEST QUESTION: {message}
            
            When responding, I should:
            1. Directly acknowledge what I remember from our previous conversation
            2. Reference specific details from our conversation history
            3. Use a natural, conversational tone as the stylist Ari
            4. Connect my response to any fashion advice or products I've previously mentioned
            
            I'll now respond with full awareness of our conversation history.
            """
            
            # Add user message to session
            await session.add_message(message, "user")
            
            try:
                # FIXED: Create agent using AgentFactory if not available
                if not session.stylist_agent:
                    session.stylist_agent = await session.agent_factory.create_stylist_agent(
                        memory=session.memory,
                        enable_mcp=True
                    )
                
                # FIXED: Process message directly with agent using compatibility layer
                if CAMEL_AVAILABLE and CompatibilityLayer:
                    user_message = CompatibilityLayer.create_user_message(
                        content=meta_question_prompt,
                        role_name="User"
                    )
                    
                    if user_message and hasattr(session.stylist_agent, 'step'):
                        response = session.stylist_agent.step(user_message)
                        response_text = response.msg.content if hasattr(response, 'msg') else str(response)
                    else:
                        # Fallback if compatibility layer fails
                        response_text = self._generate_fallback_memory_response(memory_context, message)
                else:
                    # Fallback if CAMEL not available
                    response_text = self._generate_fallback_memory_response(memory_context, message)
                
                # Process the response to ensure it actually uses memory
                # If the response suggests it doesn't have memory, fix it
                no_memory_phrases = [
                    "i don't have the ability to remember", 
                    "i cannot recall", 
                    "i don't have access to",
                    "i don't have memory",
                    "i can't remember"
                ]
                
                if any(phrase in response_text.lower() for phrase in no_memory_phrases):
                    # Response incorrectly claims no memory - override it
                    logger.warning("Agent response incorrectly claims no memory capability - fixing")
                    
                    # Extract a relevant detail from the conversation history
                    relevant_detail = "our previous conversation"
                    for msg in reversed(memory_context):
                        if msg.get("role") == "user" and len(msg.get("content", "")) > 10:
                            # Found a substantive user message
                            content = msg.get("content", "")
                            if len(content) > 50:
                                content = content[:50] + "..."
                            relevant_detail = f"when you asked about '{content}'"
                            break
                    
                    # Create fixed response that acknowledges memory
                    response_text = (
                        f"Yes, I remember {relevant_detail}. Looking at our conversation history, "
                        f"I can see we've been discussing fashion advice. Is there something specific "
                        f"from our previous conversation you'd like me to elaborate on?"
                    )
                
                # Add agent message to session
                await session.add_message(response_text, "agent")
                
                logger.info("Handled meta-question successfully")
                
                return response_text, {
                    "result_type": "meta_response",
                    "is_follow_up": True,
                    "has_memory_context": True,
                    "memory_context_size": len(memory_context)
                }
            except Exception as e:
                logger.error(f"Error handling meta-question with agent: {e}", exc_info=True)
                
                # Fallback response if agent fails
                fallback_response = (
                    "I remember our conversation, but I'm having trouble processing your question. "
                    "Could you please rephrase it or provide more details about what you'd like me to recall?"
                )
                
                await session.add_message(fallback_response, "agent")
                
                return fallback_response, {
                    "result_type": "meta_response",
                    "is_follow_up": True,
                    "has_memory_context": True,
                    "error": str(e)
                }
                
        except Exception as e:
            logger.warning(f"Error in meta-question handling: {e}", exc_info=True)
            
            if is_memory_question:
                # If explicitly asking about memory but handling failed
                # Return a graceful response
                await session.add_message(message, "user")
                
                response_text = ("I'm having trouble accessing our conversation history right now. "
                                "Could you help remind me what you're referring to?")
                
                await session.add_message(response_text, "agent")
                
                return response_text, {
                    "result_type": "meta_response",
                    "is_follow_up": True,
                    "error": str(e)
                }
            
            return None
    
    # Not a memory-related question
    return None

def _generate_fallback_memory_response(self, memory_context: List[Dict[str, str]], message: str) -> str:
    """
    Generate a fallback response when CAMEL agent processing fails.
    
    Args:
        memory_context: List of memory context messages
        message: User's message
        
    Returns:
        Fallback response string
    """
    try:
        # Extract some relevant information from memory context
        recent_topics = []
        for msg in memory_context[-5:]:  # Look at last 5 messages
            content = msg.get("content", "")
            if len(content) > 20:  # Skip very short messages
                # Extract key terms (simple approach)
                words = content.lower().split()
                fashion_terms = ["dress", "style", "outfit", "color", "fashion", "wear", "look", "clothes"]
                for word in words:
                    if word in fashion_terms and word not in recent_topics:
                        recent_topics.append(word)
                        if len(recent_topics) >= 3:
                            break
        
        if recent_topics:
            topics_text = ", ".join(recent_topics)
            return (f"Looking at our conversation, I can see we've been discussing {topics_text}. "
                   f"Could you be more specific about what aspect you'd like me to elaborate on?")
        else:
            return ("I can see we've had a conversation about fashion, but I'd like to make sure "
                   "I understand exactly what you're asking about. Could you provide a bit more detail?")
                   
    except Exception as e:
        logger.error(f"Error generating fallback memory response: {e}")
        return ("I remember we've been chatting about fashion advice. "
               "What specifically would you like me to help you with?")


# INSTRUCTIONS FOR IMPLEMENTATION:
# 
# 1. In chat_session_manager_async.py, add this import at the top:
#    from camel_imports import CompatibilityLayer, CAMEL_AVAILABLE
#
# 2. Replace the existing _handle_meta_question method in the EnhancedChatManagerAsync class
#    with the fixed version above
#
# 3. Make sure the _generate_fallback_memory_response method is also added to the class
#    if it doesn't already exist
#
# This patch resolves the direct BaseMessage import issue and uses the proper
# compatibility layer for CAMEL operations.
