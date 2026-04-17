"""Tests for grader.validate."""

import jsonschema.exceptions
import pytest

from nbgrader_jupyterquiz.grader.validate import validate_question


# --- Valid questions pass without raising ---


def test_valid_multiple_choice():
    validate_question(
        {
            "type": "multiple_choice",
            "question": "What is the capital of France?",
            "answers": [
                {"answer": "Paris", "correct": True},
                {"answer": "London", "correct": False},
            ],
        }
    )


def test_valid_many_choice():
    validate_question(
        {
            "type": "many_choice",
            "question": "Which of these are prime?",
            "answers": [
                {"answer": "2", "correct": True},
                {"answer": "3", "correct": True},
                {"answer": "4", "correct": False},
            ],
        }
    )


def test_valid_numeric_value():
    validate_question(
        {
            "type": "numeric",
            "question": "What is pi, to two decimal places?",
            "precision": 2,
            "answers": [
                {"value": 3.14, "correct": True, "feedback": "Correct!"},
                {"type": "default", "feedback": "Not quite."},
            ],
        }
    )


def test_valid_numeric_range():
    validate_question(
        {
            "type": "numeric",
            "question": "Estimate the answer.",
            "answers": [
                {"range": [3.0, 4.0], "correct": True},
                {"type": "default", "feedback": "Outside the accepted range."},
            ],
        }
    )


def test_valid_string_exact():
    validate_question(
        {
            "type": "string",
            "question": "Capital of France?",
            "answers": [
                {"answer": "Paris", "correct": True},
                {"type": "default", "feedback": "Nope."},
            ],
        }
    )


def test_valid_string_fuzzy_and_case():
    """Optional ``match_case`` and ``fuzzy_threshold`` are accepted."""
    validate_question(
        {
            "type": "string",
            "question": "Spell mousse.",
            "points": 0.5,
            "answers": [
                {
                    "answer": "mousse",
                    "correct": True,
                    "match_case": False,
                    "fuzzy_threshold": 0.8,
                },
            ],
        }
    )


# --- Invalid questions raise ---


def test_missing_answers_raises():
    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_question(
            {
                "type": "multiple_choice",
                "question": "A question with no answers field.",
            }
        )


def test_unknown_type_raises():
    """An unrecognised type string raises KeyError before schema validation."""
    with pytest.raises(KeyError):
        validate_question({"type": "essay", "question": "...", "answers": []})
