"""
ARI V3 Onboarding Service

Extends the existing onboarding service with V3 interpretation.
After onboarding completes, this service:
1. Converts extracted data to V3 OnboardingProfile
2. Derives NavigationParameters deterministically
3. Stores both in Neo4j

Date: January 2026
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from ari_v3.interpretation import (
    interpret_onboarding,
    convert_extracted_to_v3_profile,
    OnboardingInterpreter,
)
from ari_v3.core import (
    OnboardingProfile,
    NavigationParameters,
    serialize_onboarding_profile,
    serialize_navigation_params,
)
from ari_v3.services import UserGraphManager

logger = logging.getLogger("ari_v3.services.onboarding")


class OnboardingServiceV3:
    """
    V3 Onboarding Service.

    Integrates with existing OnboardingCrewV2 to add V3 interpretation.

    Usage:
        service = OnboardingServiceV3()

        # After OnboardingCrewV2 completes
        extracted_data = crew.get_all_extracted_data()

        # Process through V3
        profile, nav_params = service.process_completed_onboarding(
            user_id="user123",
            extracted_data=extracted_data
        )
    """

    def __init__(self):
        """Initialize V3 onboarding service."""
        self.graph_manager = UserGraphManager()
        self.interpreter = OnboardingInterpreter()

    def close(self):
        """Close database connections."""
        self.graph_manager.close()

    def process_completed_onboarding(
        self,
        user_id: str,
        extracted_data: Dict[str, Any]
    ) -> Tuple[OnboardingProfile, NavigationParameters]:
        """
        Process completed onboarding through V3 interpretation.

        This is the main entry point after OnboardingCrewV2 finishes.

        Args:
            user_id: User ID
            extracted_data: Output from OnboardingCrewV2.get_all_extracted_data()

        Returns:
            Tuple of (OnboardingProfile, NavigationParameters)
        """
        logger.info(f"Processing V3 onboarding for user: {user_id}")

        # Interpret to V3 structures
        profile, nav_params = interpret_onboarding(extracted_data)

        # Store in Neo4j
        self._store_v3_data(user_id, profile, nav_params)

        logger.info(
            f"V3 onboarding complete for {user_id}: "
            f"exploration_appetite={nav_params.exploration_appetite:.2f}, "
            f"brand_affinity={nav_params.brand_affinity_weight:.2f}"
        )

        return profile, nav_params

    def _store_v3_data(
        self,
        user_id: str,
        profile: OnboardingProfile,
        nav_params: NavigationParameters
    ) -> bool:
        """
        Store V3 profile and navigation parameters in Neo4j.

        Args:
            user_id: User ID
            profile: V3 OnboardingProfile
            nav_params: V3 NavigationParameters

        Returns:
            Success boolean
        """
        try:
            # Serialize dataclasses to dicts
            profile_data = serialize_onboarding_profile(profile)
            nav_params_data = serialize_navigation_params(nav_params)

            # Store in Neo4j
            profile_stored = self.graph_manager.store_v3_onboarding_profile(
                user_id, profile_data
            )
            nav_stored = self.graph_manager.store_navigation_parameters(
                user_id, nav_params_data
            )

            if profile_stored and nav_stored:
                logger.info(f"Stored V3 data for user {user_id}")
                return True
            else:
                logger.error(f"Failed to store V3 data for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"Error storing V3 data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_user_navigation_params(self, user_id: str) -> Optional[NavigationParameters]:
        """
        Get V3 NavigationParameters for a user.

        Args:
            user_id: User ID

        Returns:
            NavigationParameters or None
        """
        from ari_v3.core import deserialize_to_navigation_params

        data = self.graph_manager.get_navigation_parameters(user_id)
        if data:
            return deserialize_to_navigation_params(data)
        return None

    def get_user_v3_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get V3 OnboardingProfile data for a user.

        Args:
            user_id: User ID

        Returns:
            Profile data dict or None
        """
        return self.graph_manager.get_v3_onboarding_profile(user_id)

    async def reinterpret_profile(
        self,
        user_id: str,
        raw_conversations: list,
        behavioral_summary: Dict[str, Any]
    ) -> Tuple[OnboardingProfile, NavigationParameters]:
        """
        Re-interpret user profile based on behavioral drift.

        Called when user behavior significantly diverges from stated preferences.

        Args:
            user_id: User ID
            raw_conversations: Original onboarding conversations
            behavioral_summary: Observed behavior data

        Returns:
            Updated (OnboardingProfile, NavigationParameters)
        """
        # Get existing profile
        existing_data = self.get_user_v3_profile(user_id)
        if not existing_data:
            raise ValueError(f"No V3 profile found for user {user_id}")

        # Convert to OnboardingProfile (simplified - would need full deserialization)
        existing_profile = convert_extracted_to_v3_profile({
            "nodes": existing_data,
            "root_values": {},
            "photos": {},
            "social_media": {},
        })

        # Re-interpret with behavioral context
        updated_profile, updated_params = await self.interpreter.reinterpret(
            original_profile=existing_profile,
            raw_conversations=raw_conversations,
            behavioral_summary=behavioral_summary,
        )

        # Store updated data
        self._store_v3_data(user_id, updated_profile, updated_params)

        logger.info(f"Re-interpreted profile for user {user_id}")

        return updated_profile, updated_params


def create_onboarding_service_v3() -> OnboardingServiceV3:
    """Factory function to create V3 onboarding service."""
    return OnboardingServiceV3()
