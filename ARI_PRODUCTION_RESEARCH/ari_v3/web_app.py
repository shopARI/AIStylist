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


# Demo user profiles (same as CLI)
DEMO_USERS = {
    "emma": {
        "id": "demo_emma_creative",
        "name": "Emma",
        "description": "Creative professional, loves bold colors and unique pieces",
        "style_words": ["creative", "bold", "artistic", "eclectic"],
        "body_type": "hourglass",
        "budget_preference": "mid-range",
    },
    "marcus": {
        "id": "demo_marcus_finance",
        "name": "Marcus",
        "description": "Finance professional, prefers timeless quality pieces",
        "style_words": ["classic", "professional", "timeless", "quality"],
        "body_type": "athletic",
        "budget_preference": "premium",
    },
    "sophia": {
        "id": "demo_sophia_tech",
        "name": "Sophia",
        "description": "Tech founder, loves minimalist Scandinavian style",
        "style_words": ["minimalist", "clean", "modern", "scandinavian"],
        "body_type": "apple",
        "budget_preference": "mid-range",
    },
}


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


async def process_message(query: str, orchestrator: ARIOrchestrator, user_profile: dict) -> dict:
    """Process a user message through the orchestrator."""
    response = await orchestrator.process_input(
        user_input=query,
        session_id=st.session_state.session_id,
        user_id=user_profile["id"],
        user_context={
            "name": user_profile["name"],
            "style_words": user_profile.get("style_words", []),
            "body_type": user_profile.get("body_type"),
            "budget_preference": user_profile.get("budget_preference"),
        },
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
        st.markdown(f"Style: {', '.join(user_profile.get('style_words', []))}")

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
