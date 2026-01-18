"""
Prompt Sanitization Utility

Provides functions to sanitize user input before including it in LLM prompts.
Prevents prompt injection attacks where malicious users attempt to manipulate
LLM behavior by including instructions in their input.

Usage:
    from ari_v3.core.prompt_sanitizer import sanitize_user_input, sanitize_for_prompt

    # For single values
    safe_query = sanitize_user_input(user_query)

    # For building prompts with multiple user values
    safe_prompt = sanitize_for_prompt(
        template="User query: {query}\nStyle: {style}",
        query=user_query,
        style=user_style
    )
"""

import re
import html
from typing import Any, Dict, List, Optional, Union


# Patterns that might indicate injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
    r"forget\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
    r"override\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
    r"you\s+are\s+now\s+",
    r"new\s+instruction[s]?:",
    r"system\s*prompt:",
    r"<\s*system\s*>",
    r"<\s*/?\s*instruction[s]?\s*>",
    r"```\s*(system|instruction|prompt)",
    r"\[\s*INST\s*\]",
    r"\[\s*/?\s*SYS\s*\]",
    r"human:\s*$",
    r"assistant:\s*$",
    r"user:\s*$",
]

# Compile patterns for efficiency
COMPILED_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in INJECTION_PATTERNS
]

# Characters that could be used to break out of quoted strings
ESCAPE_CHARS = {
    '"': '\\"',
    "'": "\\'",
    "\\": "\\\\",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def sanitize_user_input(
    text: Optional[str],
    max_length: int = 2000,
    strip_injection_attempts: bool = True,
    escape_quotes: bool = True,
) -> str:
    """
    Sanitize user input for safe inclusion in LLM prompts.

    Args:
        text: The user-provided text to sanitize
        max_length: Maximum allowed length (truncates if exceeded)
        strip_injection_attempts: If True, removes detected injection patterns
        escape_quotes: If True, escapes quote characters

    Returns:
        Sanitized string safe for prompt inclusion
    """
    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length] + "..."

    # Strip leading/trailing whitespace
    text = text.strip()

    # Remove or flag injection attempts
    if strip_injection_attempts:
        for pattern in COMPILED_INJECTION_PATTERNS:
            text = pattern.sub("[FILTERED]", text)

    # Escape quote characters to prevent breaking out of string contexts
    if escape_quotes:
        for char, escape in ESCAPE_CHARS.items():
            text = text.replace(char, escape)

    return text


def sanitize_list(
    items: Optional[List[str]],
    max_items: int = 50,
    max_item_length: int = 200,
) -> List[str]:
    """
    Sanitize a list of user-provided strings.

    Args:
        items: List of strings to sanitize
        max_items: Maximum number of items to include
        max_item_length: Maximum length per item

    Returns:
        List of sanitized strings
    """
    if not items:
        return []

    sanitized = []
    for item in items[:max_items]:
        if item:
            sanitized.append(sanitize_user_input(item, max_length=max_item_length))

    return sanitized


def sanitize_dict(
    data: Optional[Dict[str, Any]],
    allowed_keys: Optional[set] = None,
    max_value_length: int = 500,
) -> Dict[str, str]:
    """
    Sanitize a dictionary of user-provided values.

    Args:
        data: Dictionary to sanitize
        allowed_keys: If provided, only include these keys
        max_value_length: Maximum length per value

    Returns:
        Dictionary with sanitized string values
    """
    if not data:
        return {}

    sanitized = {}
    for key, value in data.items():
        # Only include allowed keys if whitelist provided
        if allowed_keys and key not in allowed_keys:
            continue

        # Sanitize the key itself
        safe_key = sanitize_user_input(str(key), max_length=100, escape_quotes=False)

        # Sanitize the value
        if value is None:
            sanitized[safe_key] = ""
        elif isinstance(value, (list, tuple)):
            sanitized[safe_key] = ", ".join(sanitize_list(list(value)))
        elif isinstance(value, dict):
            sanitized[safe_key] = str(sanitize_dict(value, max_value_length=max_value_length))
        else:
            sanitized[safe_key] = sanitize_user_input(str(value), max_length=max_value_length)

    return sanitized


def sanitize_for_prompt(template: str, **kwargs) -> str:
    """
    Safely format a prompt template with user-provided values.

    All values are sanitized before insertion into the template.

    Args:
        template: The prompt template with {placeholders}
        **kwargs: Values to substitute into the template

    Returns:
        Formatted prompt with sanitized values

    Example:
        prompt = sanitize_for_prompt(
            "Find products matching: {query}\\nStyle: {style}",
            query=user_query,
            style=user_style_preference
        )
    """
    sanitized_kwargs = {}
    for key, value in kwargs.items():
        if value is None:
            sanitized_kwargs[key] = ""
        elif isinstance(value, (list, tuple)):
            sanitized_kwargs[key] = ", ".join(sanitize_list(list(value)))
        elif isinstance(value, dict):
            sanitized_kwargs[key] = str(sanitize_dict(value))
        else:
            sanitized_kwargs[key] = sanitize_user_input(str(value))

    return template.format(**sanitized_kwargs)


def wrap_user_content(text: str, label: str = "USER INPUT") -> str:
    """
    Wrap user content with clear delimiters to help LLM distinguish
    between instructions and user content.

    Args:
        text: The user content to wrap
        label: Label for the content block

    Returns:
        Wrapped content with delimiters
    """
    sanitized = sanitize_user_input(text)
    return f"<{label}>\n{sanitized}\n</{label}>"


def detect_injection_attempt(text: str) -> bool:
    """
    Check if text contains potential injection patterns.

    Args:
        text: Text to check

    Returns:
        True if potential injection detected, False otherwise
    """
    if not text:
        return False

    for pattern in COMPILED_INJECTION_PATTERNS:
        if pattern.search(text):
            return True

    return False


def get_injection_warnings(text: str) -> List[str]:
    """
    Get list of detected injection patterns in text.

    Args:
        text: Text to analyze

    Returns:
        List of pattern descriptions that matched
    """
    if not text:
        return []

    warnings = []
    for i, pattern in enumerate(COMPILED_INJECTION_PATTERNS):
        if pattern.search(text):
            warnings.append(f"Detected pattern: {INJECTION_PATTERNS[i]}")

    return warnings
