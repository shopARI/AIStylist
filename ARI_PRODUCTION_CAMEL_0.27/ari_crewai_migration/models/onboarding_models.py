"""
Onboarding Models

Pydantic models for the onboarding flow, questions, and responses.
Maps to onboarding_config.json structure.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class QuestionType(str, Enum):
    """Question types supported in onboarding."""
    SLIDER = "slider"
    MULTIPLE_CHOICE = "multiple_choice"
    MULTI_SELECT = "multi_select"
    TEXT = "text"
    EMAIL = "email"
    RANGE = "range"
    SEGMENTED = "segmented"
    COMPOSITE = "composite"
    DROPDOWN = "dropdown"


class QuestionScale(BaseModel):
    """Scale configuration for slider questions."""
    min: int
    max: int
    min_label: str
    max_label: str
    center_label: Optional[str] = None
    default: int


class QuestionOption(BaseModel):
    """Option for multiple choice questions."""
    value: str
    label: str
    weight: Optional[int] = None
    description: Optional[str] = None


class QuestionRange(BaseModel):
    """Range configuration for range questions."""
    min: int
    max: int
    step: int
    currency: Optional[str] = None
    default_min: int
    default_max: int


class SegmentedOption(BaseModel):
    """Segmented question category."""
    category: str
    options: List[str]


class CompositeField(BaseModel):
    """Field for composite questions."""
    name: str
    placeholder: str
    required: bool = False


class Question(BaseModel):
    """Individual onboarding question."""
    id: str
    type: QuestionType
    question: str
    required: bool

    # Type-specific fields
    scale: Optional[QuestionScale] = None
    options: Optional[List[QuestionOption]] = None
    range: Optional[QuestionRange] = None
    segments: Optional[List[SegmentedOption]] = None
    fields: Optional[List[CompositeField]] = None

    # Common optional fields
    help_text: Optional[str] = None
    placeholder: Optional[str] = None
    allow_skip: Optional[bool] = None
    skip_label: Optional[str] = None
    allow_custom: Optional[bool] = None
    custom_placeholder: Optional[str] = None
    min_selections: Optional[int] = None
    max_selections: Optional[int] = None
    multiline: Optional[bool] = None
    validation: Optional[str] = None
    visual_aids: Optional[bool] = None
    track_as: Optional[str] = None

    class Config:
        use_enum_values = True


class OnboardingStep(BaseModel):
    """Single step in the onboarding flow."""
    step_id: str
    title: str
    description: str
    order: int
    questions: List[Question]


class OnboardingWelcome(BaseModel):
    """Welcome message configuration."""
    title: str
    message: str
    hook: str


class OnboardingCompletion(BaseModel):
    """Completion message configuration."""
    title: str
    message: str
    cta: str


class OnboardingMetadata(BaseModel):
    """Metadata about the onboarding config."""
    created_by: str
    last_updated: str
    estimated_duration_minutes: int
    description: str


class OnboardingConfig(BaseModel):
    """Complete onboarding configuration."""
    version: str
    metadata: OnboardingMetadata
    welcome: OnboardingWelcome
    steps: List[OnboardingStep]
    completion: OnboardingCompletion
    data_model: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    personalization_rules: Optional[Dict[str, Any]] = None


class OnboardingResponse(BaseModel):
    """Response to a single onboarding step."""
    user_id: str
    step_id: str
    responses: Dict[str, Any]
    completed_at: datetime = Field(default_factory=datetime.now)


class OnboardingProgress(BaseModel):
    """User's progress through onboarding."""
    user_id: str
    total_steps: int
    completed_steps: int
    current_step: int
    is_complete: bool
    responses: Dict[str, Dict[str, Any]] = {}  # step_id -> responses
    started_at: datetime
    completed_at: Optional[datetime] = None


class ValidationResult(BaseModel):
    """Result of validating onboarding responses."""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class OnboardingSubmission(BaseModel):
    """Complete onboarding submission."""
    username: str
    email: EmailStr
    step_responses: Dict[str, Dict[str, Any]]
    submitted_at: datetime = Field(default_factory=datetime.now)
