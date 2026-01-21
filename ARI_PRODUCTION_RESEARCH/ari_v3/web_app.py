"""
ARI V3 - Streamlit Web Demo

A web-based interface for the ARI fashion recommendation system.
Displays product images and provides chat-based interaction.

Run with: streamlit run ari_v3/demo_web.py
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ari_v3.interface.orchestrator import ARIOrchestrator
from ari_v3.interface.intent_detector import DetectionStrategy
from ari_v3.interface.types import ResponseType


# Demo user profiles (same structure as CLI)
DEMO_USERS = {
    "emma": {
        "id": "demo_emma_creative",
        "name": "Emma",
        "description": "Creative professional, loves bold colors and unique pieces",
        "taste": {
            "style_words": ["creative", "bold", "artistic", "eclectic"],
            "color_preferences": ["red", "orange", "purple"],
            "adventurousness": 8,
        },
        "body": {
            "body_type": "hourglass",
        },
        "practicality": {
            "budget_preference": "mid-range",
            "budget_monthly": 500,
        },
        "personal": {
            "style_goal": "Express creativity through fashion",
            "occasions": ["work", "gallery openings", "creative events"],
        },
    },
    "marcus": {
        "id": "demo_marcus_finance",
        "name": "Marcus",
        "description": "Finance professional, prefers timeless quality pieces",
        "taste": {
            "style_words": ["classic", "professional", "timeless", "quality"],
            "color_preferences": ["navy", "gray", "white"],
            "adventurousness": 3,
        },
        "body": {
            "body_type": "athletic",
        },
        "practicality": {
            "budget_preference": "premium",
            "budget_monthly": 1000,
        },
        "personal": {
            "style_goal": "Look polished and professional",
            "occasions": ["office", "business meetings", "networking events"],
        },
    },
    "sophia": {
        "id": "demo_sophia_tech",
        "name": "Sophia",
        "description": "Tech founder, loves minimalist Scandinavian style",
        "taste": {
            "style_words": ["minimalist", "clean", "modern", "scandinavian"],
            "color_preferences": ["white", "beige", "black"],
            "adventurousness": 5,
        },
        "body": {
            "body_type": "apple",
        },
        "practicality": {
            "budget_preference": "mid-range",
            "budget_monthly": 600,
        },
        "personal": {
            "style_goal": "Effortless chic for busy lifestyle",
            "occasions": ["startup office", "investor meetings", "tech conferences"],
        },
    },
}


def build_onboarding_profile(profile_data: dict):
    """Build an OnboardingProfile-like object from profile data."""
    class ProfileSection:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

    class SimpleProfile:
        def __init__(self, data):
            self.taste = ProfileSection(data.get("taste", {})) if "taste" in data else None
            self.personal = ProfileSection(data.get("personal", {})) if "personal" in data else None
            self.practicality = ProfileSection(data.get("practicality", {})) if "practicality" in data else None
            self.body = ProfileSection(data.get("body", {})) if "body" in data else None
            self.process = ProfileSection(data.get("process", {})) if "process" in data else None

    return SimpleProfile(profile_data)


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = None
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = None
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"web_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if "initialized" not in st.session_state:
        st.session_state.initialized = False


@st.cache_resource
def get_orchestrator():
    """Create and cache the ARIOrchestrator instance."""
    try:
        orchestrator = ARIOrchestrator(
            enable_neo4j=True,
            detection_strategy=DetectionStrategy.LLM_FIRST,
        )
        return orchestrator
    except Exception as e:
        st.error(f"Failed to initialize ARI: {e}")
        return None


def display_product_grid(products: list, columns: int = 3):
    """Display products in a grid with images."""
    if not products:
        st.info("No products found.")
        return

    # Create columns
    cols = st.columns(columns)

    for idx, product in enumerate(products):
        col = cols[idx % columns]

        with col:
            # Product card container
            with st.container():
                # Get image URL
                images = product.get("images", [])
                image_url = None
                if images:
                    if isinstance(images, list) and len(images) > 0:
                        image_url = images[0]
                    elif isinstance(images, str):
                        image_url = images

                # Display image
                if image_url:
                    try:
                        st.image(image_url, use_container_width=True)
                    except Exception:
                        st.image("https://via.placeholder.com/200x250?text=No+Image", use_container_width=True)
                else:
                    st.image("https://via.placeholder.com/200x250?text=No+Image", use_container_width=True)

                # Product info
                title = product.get("title", "Unknown Product")
                if len(title) > 50:
                    title = title[:47] + "..."
                st.markdown(f"**{title}**")

                # Brand and price
                brand = product.get("brand") or product.get("vendor") or ""
                price = product.get("price")

                info_parts = []
                if brand:
                    info_parts.append(brand)
                if price:
                    info_parts.append(f"${price}")

                if info_parts:
                    st.caption(" | ".join(info_parts))

                # Match score if available
                score = product.get("final_score") or product.get("score")
                if score:
                    percentage = int(score * 100) if score <= 1 else int(score)
                    st.progress(percentage / 100, text=f"Match: {percentage}%")

                st.divider()


async def process_message(query: str, orchestrator: ARIOrchestrator, user_profile_data: dict) -> dict:
    """Process a user message through the orchestrator."""
    # Build the profile object from the dict
    profile = build_onboarding_profile(user_profile_data)

    response = await orchestrator.process_input(
        session_id=st.session_state.session_id,
        user_id=user_profile_data["id"],
        query=query,
        user_profile=profile,
    )
    return response


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="ARI - Fashion Stylist",
        page_icon="👗",
        layout="wide",
    )

    # Initialize session state
    init_session_state()

    # Sidebar - User selection
    with st.sidebar:
        st.title("ARI Fashion Stylist")
        st.markdown("---")

        # User profile selection
        st.subheader("Select Profile")

        user_options = {
            "Emma - Creative Professional": "emma",
            "Marcus - Finance Professional": "marcus",
            "Sophia - Tech Founder": "sophia",
        }

        selected_display = st.selectbox(
            "Choose a user profile:",
            options=list(user_options.keys()),
            index=2,  # Default to Sophia
        )

        selected_user = user_options[selected_display]
        user_profile = DEMO_USERS[selected_user]

        # Update session state if user changed
        if st.session_state.user_profile != user_profile:
            st.session_state.user_profile = user_profile
            st.session_state.messages = []
            st.session_state.session_id = f"web_{selected_user}_{datetime.now().strftime('%H%M%S')}"

        st.markdown(f"**{user_profile['name']}**")
        st.caption(user_profile["description"])
        style_words = user_profile.get("taste", {}).get("style_words", [])
        st.markdown(f"Style: {', '.join(style_words)}")

        st.markdown("---")

        # Clear chat button
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = f"web_{selected_user}_{datetime.now().strftime('%H%M%S')}"
            st.rerun()

        st.markdown("---")
        st.caption("ARI V3 - Navigation Intelligence")

    # Main content area
    st.header(f"Hey {user_profile['name']}! What are you looking for today?")

    # Initialize orchestrator
    orchestrator = get_orchestrator()
    if not orchestrator:
        st.error("Failed to initialize ARI. Please check the configuration.")
        return

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Display products if this was a product response
            if message["role"] == "assistant" and "products" in message:
                display_product_grid(message["products"])

    # Chat input
    if prompt := st.chat_input("Ask me anything about fashion..."):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # Process with ARI
        with st.chat_message("assistant"):
            with st.spinner("Finding perfect pieces for you..."):
                try:
                    # Run async function
                    response = asyncio.run(
                        process_message(prompt, orchestrator, user_profile)
                    )

                    # Display response text
                    response_text = response.text or "Here's what I found for you:"
                    st.markdown(response_text)

                    # Store message
                    message_data = {"role": "assistant", "content": response_text}

                    # Display products if available
                    if response.response_type == ResponseType.PRODUCTS and response.products:
                        display_product_grid(response.products)
                        message_data["products"] = response.products

                    # Display suggestions
                    if response.suggestions:
                        st.markdown("**Suggestions:**")
                        suggestion_cols = st.columns(len(response.suggestions))
                        for i, suggestion in enumerate(response.suggestions):
                            with suggestion_cols[i]:
                                if st.button(suggestion, key=f"sug_{len(st.session_state.messages)}_{i}"):
                                    # This will trigger on next rerun
                                    st.session_state.pending_suggestion = suggestion

                    st.session_state.messages.append(message_data)

                except Exception as e:
                    st.error(f"Error: {e}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Sorry, I encountered an error: {e}"
                    })


if __name__ == "__main__":
    main()
