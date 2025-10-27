"""
Onboarding CLI

Terminal-based user interface for the onboarding flow.
Handles all question types from onboarding_config.json.
"""

from typing import Any, Dict, List
from services.onboarding_service import OnboardingService
from models.onboarding_models import Question, OnboardingStep
from models.user_models import User


class OnboardingCLI:
    """Terminal-based onboarding interface."""

    def __init__(self, onboarding_service: OnboardingService):
        """Initialize with onboarding service."""
        self.service = onboarding_service
        self.config = onboarding_service.config

    # ======================
    # DISPLAY METHODS
    # ======================

    def display_welcome(self):
        """Display welcome message."""
        print("\n" + "="*70)
        print(self.config.welcome.title.upper())
        print("="*70)
        print()
        print(self.config.welcome.message)
        print()
        print(self.config.welcome.hook)
        print()
        print("="*70)
        print()

    def display_step_header(self, step: OnboardingStep, progress: tuple[int, int]):
        """Display step header."""
        current, total = progress
        print("\n" + "="*70)
        print(f"[Step {current}/{total}] {step.title}")
        print("="*70)
        print(f"{step.description}")
        print()

    def display_completion(self):
        """Display completion message."""
        print("\n" + "="*70)
        print(self.config.completion.title.upper())
        print("="*70)
        print()
        print(self.config.completion.message)
        print()
        print("="*70)
        print()

    # ======================
    # QUESTION HANDLERS
    # ======================

    def ask_slider_question(self, question: Question) -> float:
        """Handle slider question."""
        print(f"\nQuestion: {question.question}")

        if question.scale:
            print(f"{question.scale.min} {'-'*20} {question.scale.max}")
            print(f"{question.scale.min_label:<30} {question.scale.max_label:>30}")

            if question.scale.center_label:
                print(f"{'':30} {question.scale.center_label}")

        if question.help_text:
            print(f"  ({question.help_text})")

        default = question.scale.default if question.scale else 5

        while True:
            try:
                response = input(f"\nEnter value ({question.scale.min}-{question.scale.max}) [default: {default}]: ").strip()

                if not response:
                    return float(default)

                value = float(response)

                if question.scale and (value < question.scale.min or value > question.scale.max):
                    print(f"  Value must be between {question.scale.min} and {question.scale.max}")
                    continue

                return value

            except ValueError:
                print("  Please enter a valid number")

    def ask_multiple_choice(self, question: Question) -> str:
        """Handle multiple choice question."""
        print(f"\nQuestion: {question.question}")

        if question.help_text:
            print(f"  ({question.help_text})")

        print()

        if question.options:
            for i, option in enumerate(question.options, 1):
                label = option.label if hasattr(option, 'label') else option
                if hasattr(option, 'description') and option.description:
                    print(f"  {i}. {label}")
                    print(f"     {option.description}")
                else:
                    print(f"  {i}. {label}")

        print()

        while True:
            try:
                response = input("Select option number: ").strip()

                if not response:
                    continue

                index = int(response) - 1

                if 0 <= index < len(question.options):
                    option = question.options[index]
                    return option.value if hasattr(option, 'value') else option.label

                print(f"  Please select a number between 1 and {len(question.options)}")

            except ValueError:
                print("  Please enter a valid number")

    def ask_multi_select(self, question: Question) -> List[str]:
        """Handle multi-select question."""
        print(f"\nQuestion: {question.question}")

        if question.min_selections or question.max_selections:
            range_str = ""
            if question.min_selections and question.max_selections:
                range_str = f"Select {question.min_selections}-{question.max_selections} options"
            elif question.min_selections:
                range_str = f"Select at least {question.min_selections}"
            elif question.max_selections:
                range_str = f"Select up to {question.max_selections}"

            if range_str:
                print(f"  ({range_str})")

        if question.help_text:
            print(f"  ({question.help_text})")

        print()

        if question.options:
            for i, option in enumerate(question.options, 1):
                label = option if isinstance(option, str) else option.label
                print(f"  {i}. {label}")

        print()

        if question.allow_custom:
            print(f"  Or enter custom options (comma-separated)")

        while True:
            response = input("Select numbers (comma-separated, e.g. '1,3,5'): ").strip()

            if not response:
                if not question.required:
                    return []
                continue

            # Check if custom input
            if not response[0].isdigit():
                # Parse as comma-separated custom values
                custom_values = [v.strip() for v in response.split(',')]
                return custom_values

            # Parse as numbers
            try:
                indices = [int(x.strip()) - 1 for x in response.split(',')]

                # Validate indices
                valid_options = []
                for index in indices:
                    if 0 <= index < len(question.options):
                        option = question.options[index]
                        label = option if isinstance(option, str) else option.label
                        valid_options.append(label)
                    else:
                        print(f"  Invalid option number: {index + 1}")
                        break
                else:
                    # Check min/max selections
                    if question.min_selections and len(valid_options) < question.min_selections:
                        print(f"  Please select at least {question.min_selections} options")
                        continue

                    if question.max_selections and len(valid_options) > question.max_selections:
                        print(f"  Please select at most {question.max_selections} options")
                        continue

                    return valid_options

            except ValueError:
                print("  Please enter valid numbers separated by commas")

    def ask_text(self, question: Question) -> str:
        """Handle text question."""
        print(f"\nQuestion: {question.question}")

        if question.help_text:
            print(f"  ({question.help_text})")

        if question.placeholder:
            print(f"  Example: {question.placeholder}")

        if question.multiline:
            print("  (Press Enter twice when done)")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            return '\n'.join(lines)
        else:
            return input("\nYour answer: ").strip()

    def ask_email(self, question: Question) -> str:
        """Handle email question."""
        print(f"\nQuestion: {question.question}")

        while True:
            email = input("Email: ").strip()

            if '@' not in email or '.' not in email:
                print("  Please enter a valid email address")
                continue

            return email

    def ask_range(self, question: Question) -> Dict[str, int]:
        """Handle range question."""
        print(f"\nQuestion: {question.question}")

        if question.help_text:
            print(f"  ({question.help_text})")

        if question.range:
            print(f"  Range: {question.range.min}-{question.range.max}")

            if question.range.currency:
                print(f"  Currency: {question.range.currency}")

        while True:
            try:
                min_val = input(f"Minimum value [{question.range.default_min}]: ").strip()
                min_val = int(min_val) if min_val else question.range.default_min

                max_val = input(f"Maximum value [{question.range.default_max}]: ").strip()
                max_val = int(max_val) if max_val else question.range.default_max

                if min_val > max_val:
                    print("  Minimum cannot exceed maximum")
                    continue

                return {"min": min_val, "max": max_val}

            except ValueError:
                print("  Please enter valid numbers")

    def ask_segmented(self, question: Question) -> Dict[str, str]:
        """Handle segmented question (multiple categories)."""
        print(f"\nQuestion: {question.question}")

        results = {}

        if question.segments:
            for segment in question.segments:
                print(f"\n  Category: {segment.category}")

                for i, option in enumerate(segment.options, 1):
                    print(f"    {i}. {option}")

                while True:
                    try:
                        response = input(f"  Select for {segment.category}: ").strip()
                        index = int(response) - 1

                        if 0 <= index < len(segment.options):
                            results[segment.category] = segment.options[index]
                            break

                        print(f"    Please select 1-{len(segment.options)}")

                    except ValueError:
                        print("    Please enter a valid number")

        return results

    def ask_dropdown(self, question: Question) -> str:
        """Handle dropdown question (same as multiple choice)."""
        return self.ask_multiple_choice(question)

    def ask_composite(self, question: Question) -> Dict[str, str]:
        """Handle composite question (multiple fields)."""
        print(f"\nQuestion: {question.question}")

        if question.help_text:
            print(f"  ({question.help_text})")

        results = {}

        if question.fields:
            for field in question.fields:
                while True:
                    value = input(f"  {field.placeholder}: ").strip()

                    if not value and field.required:
                        print("    This field is required")
                        continue

                    if value or not field.required:
                        results[field.name] = value
                        break

        return results

    # ======================
    # MAIN FLOW
    # ======================

    async def run_full_onboarding(self, username: str, email: str) -> User:
        """
        Run complete onboarding flow.

        Args:
            username: Username
            email: Email

        Returns:
            Completed User object
        """
        # Display welcome
        self.display_welcome()

        # Start onboarding
        user, progress = self.service.start_onboarding(username, email)

        # Process each step
        while not progress.is_complete:
            # Get next step
            step = self.service.get_next_step(progress)

            if not step:
                break

            # Display step header
            self.display_step_header(step, (progress.current_step, progress.total_steps))

            # Collect responses for this step
            step_responses = {}

            for question in step.questions:
                # Route to appropriate handler based on question type
                handler_map = {
                    "slider": self.ask_slider_question,
                    "multiple_choice": self.ask_multiple_choice,
                    "multi_select": self.ask_multi_select,
                    "text": self.ask_text,
                    "email": self.ask_email,
                    "range": self.ask_range,
                    "segmented": self.ask_segmented,
                    "dropdown": self.ask_dropdown,
                    "composite": self.ask_composite
                }

                handler = handler_map.get(question.type)

                if handler:
                    response = handler(question)
                    step_responses[question.id] = response
                else:
                    print(f"\nWarning: Unsupported question type '{question.type}'")
                    step_responses[question.id] = None

            # Process step
            validation, progress = self.service.process_step(
                user_id=user.id,
                step_id=step.step_id,
                responses=step_responses,
                progress=progress
            )

            if not validation.is_valid:
                print("\nValidation errors:")
                for error in validation.errors:
                    print(f"  - {error}")
                print()

            if validation.warnings:
                print("\nWarnings:")
                for warning in validation.warnings:
                    print(f"  - {warning}")
                print()

        # Display completion
        self.display_completion()

        # Return final user profile
        return self.service.complete_onboarding(user.id)
