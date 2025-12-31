"""
Onboarding Loader

Utilities for loading and parsing the onboarding_config.json file.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from models.onboarding_models import (
    OnboardingConfig,
    OnboardingStep,
    Question,
    ValidationResult
)


def load_onboarding_config() -> OnboardingConfig:
    """
    Load onboarding configuration from JSON file.

    Returns:
        OnboardingConfig object
    """
    config_path = Path(__file__).parent.parent / "config" / "onboarding_config.json"

    with open(config_path, 'r') as f:
        config_data = json.load(f)

    return OnboardingConfig(**config_data)


def get_step_by_id(config: OnboardingConfig, step_id: str) -> Optional[OnboardingStep]:
    """
    Get a specific onboarding step by ID.

    Args:
        config: Onboarding configuration
        step_id: Step ID to find

    Returns:
        OnboardingStep if found, None otherwise
    """
    for step in config.steps:
        if step.step_id == step_id:
            return step

    return None


def get_step_by_order(config: OnboardingConfig, order: int) -> Optional[OnboardingStep]:
    """
    Get a specific onboarding step by order number.

    Args:
        config: Onboarding configuration
        order: Order number (1-based)

    Returns:
        OnboardingStep if found, None otherwise
    """
    for step in config.steps:
        if step.order == order:
            return step

    return None


def get_question_by_id(step: OnboardingStep, question_id: str) -> Optional[Question]:
    """
    Get a specific question from a step.

    Args:
        step: Onboarding step
        question_id: Question ID to find

    Returns:
        Question if found, None otherwise
    """
    for question in step.questions:
        if question.id == question_id:
            return question

    return None


def validate_step_responses(step: OnboardingStep, responses: Dict[str, Any]) -> ValidationResult:
    """
    Validate responses for a given step.

    Args:
        step: Onboarding step
        responses: User responses (question_id -> answer)

    Returns:
        ValidationResult with validity status and any errors
    """
    errors = []
    warnings = []

    for question in step.questions:
        # Check required questions
        if question.required and question.id not in responses:
            # Check if question allows skip
            if not question.allow_skip:
                errors.append(f"Required question '{question.id}' not answered")
                continue

        # Skip validation if question not answered (and it's optional)
        if question.id not in responses:
            continue

        response = responses[question.id]

        # Type-specific validation
        if question.type == "slider":
            if not isinstance(response, (int, float)):
                errors.append(f"Question '{question.id}': Expected number, got {type(response)}")
            elif question.scale:
                if response < question.scale.min or response > question.scale.max:
                    errors.append(
                        f"Question '{question.id}': Value {response} outside valid range "
                        f"[{question.scale.min}-{question.scale.max}]"
                    )

        elif question.type == "multiple_choice":
            if not isinstance(response, str):
                errors.append(f"Question '{question.id}': Expected string, got {type(response)}")
            elif question.options:
                # Extract valid values from options (can be str, dict, or object)
                valid_values = []
                for opt in question.options:
                    if isinstance(opt, str):
                        valid_values.append(opt)
                    elif isinstance(opt, dict):
                        valid_values.append(opt.get('value', opt.get('label', str(opt))))
                    elif hasattr(opt, 'value'):
                        valid_values.append(opt.value)
                    elif hasattr(opt, 'label'):
                        valid_values.append(opt.label)

                if response not in valid_values:
                    errors.append(
                        f"Question '{question.id}': Invalid option '{response}'. "
                        f"Valid options: {valid_values}"
                    )

        elif question.type == "multi_select":
            if not isinstance(response, list):
                errors.append(f"Question '{question.id}': Expected list, got {type(response)}")
            else:
                # Check min/max selections
                if question.min_selections and len(response) < question.min_selections:
                    errors.append(
                        f"Question '{question.id}': Minimum {question.min_selections} selections required, "
                        f"got {len(response)}"
                    )
                if question.max_selections and len(response) > question.max_selections:
                    errors.append(
                        f"Question '{question.id}': Maximum {question.max_selections} selections allowed, "
                        f"got {len(response)}"
                    )

                # Check valid options
                if question.options:
                    # Extract valid values from options (can be str, dict, or object)
                    valid_values = []
                    for opt in question.options:
                        if isinstance(opt, str):
                            valid_values.append(opt)
                        elif isinstance(opt, dict):
                            valid_values.append(opt.get('label', opt.get('value', str(opt))))
                        elif hasattr(opt, 'label'):
                            valid_values.append(opt.label)
                        else:
                            valid_values.append(str(opt))

                    for item in response:
                        if item not in valid_values:
                            warnings.append(
                                f"Question '{question.id}': '{item}' not in predefined options. "
                                f"Assuming custom input."
                            )

        elif question.type == "text":
            if not isinstance(response, str):
                errors.append(f"Question '{question.id}': Expected string, got {type(response)}")

        elif question.type == "email":
            if not isinstance(response, str):
                errors.append(f"Question '{question.id}': Expected string, got {type(response)}")
            elif '@' not in response:
                errors.append(f"Question '{question.id}': Invalid email format")

        elif question.type == "range":
            if not isinstance(response, dict):
                errors.append(f"Question '{question.id}': Expected dict with min/max, got {type(response)}")
            elif 'min' not in response or 'max' not in response:
                errors.append(f"Question '{question.id}': Range must have 'min' and 'max' keys")
            elif response['min'] > response['max']:
                errors.append(f"Question '{question.id}': Min value cannot exceed max value")

        elif question.type == "segmented":
            if not isinstance(response, dict):
                errors.append(f"Question '{question.id}': Expected dict, got {type(response)}")

        elif question.type == "composite":
            if not isinstance(response, dict):
                errors.append(f"Question '{question.id}': Expected dict, got {type(response)}")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def get_total_questions(config: OnboardingConfig) -> int:
    """Get total number of questions in onboarding."""
    return sum(len(step.questions) for step in config.steps)


def get_required_questions(config: OnboardingConfig) -> int:
    """Get number of required questions in onboarding."""
    return sum(
        len([q for q in step.questions if q.required])
        for step in config.steps
    )


def estimate_completion_time(config: OnboardingConfig) -> int:
    """
    Estimate completion time in minutes.

    Returns:
        Estimated minutes from config metadata
    """
    return config.metadata.estimated_duration_minutes


def get_progress_summary(config: OnboardingConfig, completed_steps: List[str]) -> Dict[str, Any]:
    """
    Get progress summary.

    Args:
        config: Onboarding configuration
        completed_steps: List of completed step IDs

    Returns:
        Dictionary with progress information
    """
    total_steps = len(config.steps)
    completed_count = len(completed_steps)
    percentage = (completed_count / total_steps * 100) if total_steps > 0 else 0

    # Find current step
    current_step_order = None
    for step in sorted(config.steps, key=lambda s: s.order):
        if step.step_id not in completed_steps:
            current_step_order = step.order
            break

    return {
        'total_steps': total_steps,
        'completed_steps': completed_count,
        'remaining_steps': total_steps - completed_count,
        'percentage_complete': percentage,
        'current_step_order': current_step_order,
        'is_complete': completed_count == total_steps
    }
