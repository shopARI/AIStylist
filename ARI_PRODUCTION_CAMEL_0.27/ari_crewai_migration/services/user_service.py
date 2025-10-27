"""
User Service

High-level service for user operations. Handles user authentication,
profile management, and coordinates with the user graph manager.
"""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from services.user_graph_manager import UserGraphManager
from models.user_models import User, UserProfile, PreferenceDriftReport


class UserService:
    """High-level user service."""

    def __init__(self):
        """Initialize user service with graph manager."""
        self.graph_manager = UserGraphManager()

    def close(self):
        """Close database connections."""
        self.graph_manager.close()

    # ======================
    # AUTHENTICATION
    # ======================

    def authenticate_user(self, username: str) -> Optional[User]:
        """
        Authenticate user by username.

        Args:
            username: Username to authenticate

        Returns:
            User object if found, None otherwise
        """
        user_data = self.graph_manager.get_user_by_username(username)

        if user_data:
            # Update last active
            self.graph_manager.update_last_active(user_data['id'])
            return User(**user_data)

        return None

    def user_exists(self, username: str) -> bool:
        """Check if user exists."""
        return self.graph_manager.user_exists(username)

    # ======================
    # USER CREATION
    # ======================

    def create_user(self, username: str, email: str, user_id: Optional[str] = None) -> User:
        """
        Create a new user.

        Args:
            username: Unique username
            email: User email
            user_id: Optional user ID (generates UUID if not provided)

        Returns:
            Created User object
        """
        if self.user_exists(username):
            raise ValueError(f"User '{username}' already exists")

        if user_id is None:
            user_id = str(uuid.uuid4())

        user_data = {
            'id': user_id,
            'username': username,
            'email': email
        }

        created_id = self.graph_manager.create_user_node(user_data)

        # Fetch and return created user
        user_data = self.graph_manager.get_user_by_id(created_id)
        return User(**user_data)

    # ======================
    # PROFILE MANAGEMENT
    # ======================

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        user_data = self.graph_manager.get_user_by_username(username)
        return User(**user_data) if user_data else None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        user_data = self.graph_manager.get_user_by_id(user_id)
        return User(**user_data) if user_data else None

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get complete user profile with relationships."""
        profile_data = self.graph_manager.get_user_style_profile(user_id)

        if not profile_data:
            return None

        return UserProfile(**profile_data)

    def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Optional[User]:
        """
        Update user profile properties.

        Args:
            user_id: User ID
            profile_data: Dictionary of properties to update

        Returns:
            Updated User object
        """
        success = self.graph_manager.update_user_profile(user_id, profile_data)

        if success:
            return self.get_user_by_id(user_id)

        return None

    def mark_onboarding_complete(self, user_id: str) -> bool:
        """Mark user onboarding as complete."""
        return self.graph_manager.mark_onboarding_complete(user_id)

    # ======================
    # BEHAVIORAL TRACKING
    # ======================

    def track_product_view(
        self,
        user_id: str,
        product_id: str,
        session_id: str,
        product_title: str = "",
        product_category: str = ""
    ) -> bool:
        """Track a product view."""
        try:
            self.graph_manager.record_product_view(
                user_id=user_id,
                product_id=product_id,
                session_id=session_id,
                product_title=product_title,
                product_category=product_category
            )
            return True
        except Exception as e:
            print(f"Error tracking product view: {e}")
            return False

    def track_product_save(
        self,
        user_id: str,
        product_id: str,
        collection: str = "",
        product_title: str = "",
        product_category: str = ""
    ) -> bool:
        """Track a product save/favorite."""
        try:
            self.graph_manager.record_product_save(
                user_id=user_id,
                product_id=product_id,
                collection=collection,
                product_title=product_title,
                product_category=product_category
            )
            return True
        except Exception as e:
            print(f"Error tracking product save: {e}")
            return False

    def track_purchase(
        self,
        user_id: str,
        product_id: str,
        price: float,
        occasion: str = "",
        product_title: str = "",
        product_category: str = ""
    ) -> bool:
        """Track a product purchase."""
        try:
            self.graph_manager.record_purchase(
                user_id=user_id,
                product_id=product_id,
                price=price,
                occasion=occasion,
                product_title=product_title,
                product_category=product_category
            )
            return True
        except Exception as e:
            print(f"Error tracking purchase: {e}")
            return False

    def track_search(
        self,
        user_id: str,
        query: str,
        category: str = "",
        result_count: int = 0
    ) -> bool:
        """Track a search query."""
        try:
            self.graph_manager.record_search(
                user_id=user_id,
                query=query,
                category=category,
                result_count=result_count
            )
            return True
        except Exception as e:
            print(f"Error tracking search: {e}")
            return False

    # ======================
    # OBSERVED PREFERENCES
    # ======================

    def update_observed_preferences(self, user_id: str) -> Dict[str, Optional[float]]:
        """
        Calculate and update all observed preferences for a user.

        Returns:
            Dictionary with calculated observed values
        """
        observed_expression = self.graph_manager.calculate_observed_expression_spectrum(user_id)
        observed_risk = self.graph_manager.calculate_observed_risk_tolerance(user_id)
        observed_advice = self.graph_manager.calculate_observed_advice_receptiveness(user_id)
        preference_drift = self.graph_manager.calculate_preference_drift(user_id)

        return {
            'observed_expression_spectrum': observed_expression,
            'observed_risk_tolerance': observed_risk,
            'observed_advice_receptiveness': observed_advice,
            'preference_drift': preference_drift
        }

    def get_preference_drift_report(self, user_id: str) -> Optional[PreferenceDriftReport]:
        """
        Get a detailed report on preference drift.

        Returns:
            PreferenceDriftReport with analysis and recommendations
        """
        user = self.get_user_by_id(user_id)

        if not user:
            return None

        # Calculate individual drifts
        expr_drift = None
        if user.observed_expression_spectrum and user.stated_expression_spectrum:
            expr_drift = abs(user.observed_expression_spectrum - user.stated_expression_spectrum)

        risk_drift = None
        if user.observed_risk_tolerance and user.stated_risk_tolerance:
            risk_drift = abs(user.observed_risk_tolerance - user.stated_risk_tolerance)

        advice_drift = None
        if user.observed_advice_receptiveness and user.stated_advice_receptiveness:
            advice_drift = abs(user.observed_advice_receptiveness - user.stated_advice_receptiveness)

        # Generate recommendation
        overall_drift = user.preference_drift or 0.0
        confidence = user.observation_confidence or 0.0

        if overall_drift < 1.0:
            recommendation = "Your stated and observed preferences align well. Continue exploring!"
        elif overall_drift < 2.0:
            recommendation = "Minor differences between what you said and what you choose. This is normal as you explore."
        elif overall_drift < 3.0:
            recommendation = "Your actual choices differ from your initial preferences. Consider updating your profile."
        else:
            recommendation = "Significant drift detected. Your style may be evolving. Let's update your profile!"

        return PreferenceDriftReport(
            user_id=user_id,
            overall_drift=overall_drift,
            expression_spectrum_drift=expr_drift,
            risk_tolerance_drift=risk_drift,
            advice_receptiveness_drift=advice_drift,
            observation_confidence=confidence,
            recommendation=recommendation
        )

    # ======================
    # USER STATS
    # ======================

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics."""
        user = self.get_user_by_id(user_id)

        if not user:
            return {}

        return {
            'user_id': user_id,
            'username': user.username,
            'created_at': user.created_at,
            'last_active': user.last_active,
            'onboarding_completed': user.onboarding_completed,
            'total_searches': user.total_searches,
            'total_products_viewed': user.total_products_viewed,
            'total_products_saved': user.total_products_saved,
            'total_purchases': user.total_purchases,
            'observation_confidence': user.observation_confidence or 0.0,
            'preference_drift': user.preference_drift or 0.0
        }
