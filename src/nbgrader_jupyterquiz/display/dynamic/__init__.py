"""Dynamic subpackage — display and response-capture entry points."""

from .capture import capture_responses
from .display import display_quiz


__all__ = ["capture_responses", "display_quiz"]
