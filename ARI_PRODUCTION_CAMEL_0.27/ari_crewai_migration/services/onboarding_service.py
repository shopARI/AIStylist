"""
Onboarding Service

Orchestrates the entire user onboarding flow. Manages step progression,
stores responses in Neo4j, and coordinates with user service.
"""

import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from services.user_service import UserService
from services.user_graph_manager import UserGraphManager
from models.onboarding_models import (
    OnboardingConfig,
    OnboardingStep,
    OnboardingProgress,
    OnboardingResponse,
    ValidationResult
)
from models.user_models import User
from utils.onboarding_loader import (
    load_onboarding_config,
    get_step_by_id,
    get_step_by_order,
    validate_step_responses
)


class OnboardingService:
    """Service for managing user onboarding."""

    def __init__(self):
        """Initialize onboarding service."""
        self.config = load_onboarding_config()
        self.user_service = UserService()
        self.graph_manager = UserGraphManager()

    def close(self):
        """Close database connections."""
        self.user_service.close()
        self.graph_manager.close()

    # ======================
    # ONBOARDING FLOW
    # ======================

    def start_onboarding(self, username: str, email: str) -> tuple[User, OnboardingProgress]:
        """
        Start onboarding for a new user.

        Args:
            username: Unique username
            email: User email

        Returns:
            Tuple of (User, OnboardingProgress)
        """
        # Create user
        user = self.user_service.create_user(username, email)

        # Initialize progress
        progress = OnboardingProgress(
            user_id=user.id,
            total_steps=len(self.config.steps),
            completed_steps=0,
            current_step=1,
            is_complete=False,
            started_at=datetime.now()
        )

        return user, progress

    def get_next_step(self, progress: OnboardingProgress) -> Optional[OnboardingStep]:
        """
        Get the next onboarding step.

        Args:
            progress: Current onboarding progress

        Returns:
            OnboardingStep or None if complete
        """
        if progress.is_complete:
            return None

        return get_step_by_order(self.config, progress.current_step)

    def process_step(
        self,
        user_id: str,
        step_id: str,
        responses: Dict[str, Any],
        progress: OnboardingProgress
    ) -> tuple[ValidationResult, OnboardingProgress]:
        """
        Process responses for a single step.

        Args:
            user_id: User ID
            step_id: Step ID
            responses: User responses (question_id -> answer)
            progress: Current progress

        Returns:
            Tuple of (ValidationResult, updated OnboardingProgress)
        """
        # Get step
        step = get_step_by_id(self.config, step_id)
        if not step:
            return ValidationResult(is_valid=False, errors=[f"Step '{step_id}' not found"]), progress

        # Validate responses
        validation = validate_step_responses(step, responses)

        if not validation.is_valid:
            return validation, progress

        # Store responses
        progress.responses[step_id] = responses

        # Store in Neo4j based on step
        self._store_step_data(user_id, step_id, responses)

        # Update progress
        progress.completed_steps += 1
        progress.current_step += 1
        progress.is_complete = (progress.completed_steps >= progress.total_steps)

        if progress.is_complete:
            progress.completed_at = datetime.now()
            # Mark onboarding complete
            self.user_service.mark_onboarding_complete(user_id)

        return validation, progress

    def _store_step_data(self, user_id: str, step_id: str, responses: Dict[str, Any]):
        """
        Store step data in Neo4j.

        Maps responses to appropriate User properties and relationships.
        """
        # Map step IDs to storage strategies
        if step_id == "style_autonomy":
            self._store_style_autonomy(user_id, responses)
        elif step_id == "gender_expression":
            self._store_gender_expression(user_id, responses)
        elif step_id == "self_expression":
            self._store_self_expression(user_id, responses)
        elif step_id == "lifestyle_context":
            self._store_lifestyle_context(user_id, responses)
        elif step_id == "values_shopping":
            self._store_values_shopping(user_id, responses)
        elif step_id == "budget":
            self._store_budget(user_id, responses)
        elif step_id == "demographics_contact":
            self._store_demographics(user_id, responses)

    def _store_style_autonomy(self, user_id: str, responses: Dict[str, Any]):
        """Store style autonomy responses."""
        profile_data = {}

        if 'advice_receptiveness' in responses:
            profile_data['stated_advice_receptiveness'] = float(responses['advice_receptiveness'])

        if 'creative_control' in responses:
            profile_data['stated_creative_control'] = float(responses['creative_control'])

        if 'risk_tolerance' in responses:
            profile_data['stated_risk_tolerance'] = float(responses['risk_tolerance'])

        if 'decision_making_style' in responses:
            profile_data['decision_making_style'] = responses['decision_making_style']

        self.user_service.update_user_profile(user_id, profile_data)

    def _store_gender_expression(self, user_id: str, responses: Dict[str, Any]):
        """Store gender expression and style identity responses."""
        profile_data = {}

        if 'expression_spectrum' in responses:
            profile_data['stated_expression_spectrum'] = float(responses['expression_spectrum'])

        if 'occasion_flexibility' in responses:
            profile_data['occasion_flexibility'] = float(responses['occasion_flexibility'])

        if 'inspiration_sources' in responses:
            profile_data['inspiration_sources'] = responses['inspiration_sources']

        self.user_service.update_user_profile(user_id, profile_data)

        # Add style adjectives
        if 'style_adjectives' in responses:
            adjectives = responses['style_adjectives']
            if isinstance(adjectives, list):
                self.graph_manager.add_style_adjectives(user_id, adjectives)

        # Add fit preferences
        if 'fit_preferences' in responses:
            fits = responses['fit_preferences']
            if isinstance(fits, list):
                self.graph_manager.add_fit_preferences(user_id, fits)

    def _store_self_expression(self, user_id: str, responses: Dict[str, Any]):
        """Store self expression responses."""
        profile_data = {}

        if 'statement_level' in responses:
            profile_data['statement_level'] = float(responses['statement_level'])

        if 'change_readiness' in responses:
            profile_data['change_readiness'] = responses['change_readiness']

        if 'confidence_areas' in responses:
            profile_data['confidence_areas'] = responses['confidence_areas']

        if 'pain_points' in responses:
            profile_data['pain_points'] = responses['pain_points']

        if 'aspiration_mapping' in responses:
            profile_data['aspiration_text'] = responses['aspiration_mapping']

        self.user_service.update_user_profile(user_id, profile_data)

    def _store_lifestyle_context(self, user_id: str, responses: Dict[str, Any]):
        """Store lifestyle context responses."""
        profile_data = {}

        if 'workplace_context' in responses:
            profile_data['workplace_context'] = responses['workplace_context']

        self.user_service.update_user_profile(user_id, profile_data)

        # Add life stages
        if 'life_stage' in responses:
            life_stages = responses['life_stage']
            if isinstance(life_stages, list):
                self.graph_manager.add_life_stages(user_id, life_stages)

        # Add occasions
        if 'social_occasions' in responses:
            occasions = responses['social_occasions']
            if isinstance(occasions, list):
                self.graph_manager.add_occasions(user_id, occasions)

        # Add motivations
        if 'style_motivation' in responses:
            motivations = responses['style_motivation']
            if isinstance(motivations, list):
                self.graph_manager.add_motivations(user_id, motivations)

    def _store_values_shopping(self, user_id: str, responses: Dict[str, Any]):
        """Store values and shopping behavior responses."""
        profile_data = {}

        if 'shopping_behavior' in responses:
            profile_data['shopping_behavior'] = responses['shopping_behavior']

        if 'brand_loyalty' in responses:
            profile_data['brand_loyalty'] = float(responses['brand_loyalty'])

        if 'shopping_frequency' in responses:
            profile_data['shopping_frequency'] = responses['shopping_frequency']

        self.user_service.update_user_profile(user_id, profile_data)

        # Add values
        if 'values_alignment' in responses:
            values = responses['values_alignment']
            if isinstance(values, list):
                self.graph_manager.add_values(user_id, values)

    def _store_budget(self, user_id: str, responses: Dict[str, Any]):
        """Store budget responses."""
        profile_data = {}

        if 'monthly_budget' in responses:
            budget = responses['monthly_budget']
            if isinstance(budget, dict):
                profile_data['monthly_budget_min'] = budget.get('min', 0)
                profile_data['monthly_budget_max'] = budget.get('max', 500)

        if 'value_perception' in responses:
            profile_data['value_perception'] = float(responses['value_perception'])

        if 'splurge_save_preference' in responses:
            profile_data['splurge_save_preference'] = responses['splurge_save_preference']

        self.user_service.update_user_profile(user_id, profile_data)

        # Add budget categories
        if 'item_investment' in responses:
            item_budgets = responses['item_investment']
            if isinstance(item_budgets, dict):
                budgets = []
                for category, price_range in item_budgets.items():
                    # Parse price range (e.g., "$30-75" or "<$30")
                    min_price, max_price = self._parse_price_range(price_range)
                    budgets.append({
                        'category': category,
                        'min_price': min_price,
                        'max_price': max_price
                    })

                if budgets:
                    self.graph_manager.add_budget_categories(user_id, budgets)

    def _store_demographics(self, user_id: str, responses: Dict[str, Any]):
        """Store demographics and contact information."""
        profile_data = {}

        if 'age_range' in responses:
            profile_data['age_range'] = responses['age_range']

        if 'location' in responses:
            profile_data['location'] = responses['location']

        if 'social_handles' in responses:
            handles = responses['social_handles']
            if isinstance(handles, dict):
                if 'instagram' in handles:
                    profile_data['instagram_handle'] = handles['instagram']
                if 'pinterest' in handles:
                    profile_data['pinterest_handle'] = handles['pinterest']
                if 'tiktok' in handles:
                    profile_data['tiktok_handle'] = handles['tiktok']

        self.user_service.update_user_profile(user_id, profile_data)

    def _parse_price_range(self, price_str: str) -> tuple[int, int]:
        """
        Parse price range string.

        Examples:
            "<$30" -> (0, 30)
            "$30-75" -> (30, 75)
            "$75-150" -> (75, 150)
            "$300+" -> (300, 10000)
        """
        # Remove $ and spaces
        price_str = price_str.replace('$', '').replace(' ', '')

        if '<' in price_str:
            # Less than format: "<30"
            max_price = int(price_str.replace('<', ''))
            return (0, max_price)
        elif '+' in price_str:
            # Greater than format: "300+"
            min_price = int(price_str.replace('+', ''))
            return (min_price, 10000)
        elif '-' in price_str:
            # Range format: "30-75"
            parts = price_str.split('-')
            return (int(parts[0]), int(parts[1]))
        else:
            # Single value
            value = int(price_str)
            return (value, value)

    # ======================
    # PROGRESS MANAGEMENT
    # ======================

    def resume_onboarding(self, user_id: str) -> tuple[Optional[OnboardingStep], OnboardingProgress]:
        """
        Resume onboarding for a user.

        Args:
            user_id: User ID

        Returns:
            Tuple of (next OnboardingStep, OnboardingProgress)
        """
        # Get user
        user = self.user_service.get_user_by_id(user_id)

        if not user:
            return None, None

        if user.onboarding_completed:
            # Already complete
            progress = OnboardingProgress(
                user_id=user_id,
                total_steps=len(self.config.steps),
                completed_steps=len(self.config.steps),
                current_step=len(self.config.steps),
                is_complete=True,
                started_at=user.created_at,
                completed_at=user.onboarding_completed_at
            )
            return None, progress

        # Calculate progress (simplified - would need to track actual completed steps)
        # For now, assume we need to restart from beginning
        progress = OnboardingProgress(
            user_id=user_id,
            total_steps=len(self.config.steps),
            completed_steps=0,
            current_step=1,
            is_complete=False,
            started_at=user.created_at
        )

        next_step = self.get_next_step(progress)

        return next_step, progress

    def complete_onboarding(self, user_id: str) -> Optional[User]:
        """
        Complete onboarding and return final user profile.

        Args:
            user_id: User ID

        Returns:
            Updated User object
        """
        success = self.user_service.mark_onboarding_complete(user_id)

        if success:
            return self.user_service.get_user_by_id(user_id)

        return None
