"""Validate quiz questions against JSON Schema."""

from enum import Enum
from typing import Any

import jsonschema


class Schema(Enum):
    """JSON Schema definitions for jupyterquiz question types."""

    MC = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/jmshea/jupyterquiz/mc_schema.json",
        "title": "JupyterQuiz Multiple or Many Choice Quiz",
        "description": "Schema for Multiple or Many Choice Questions in JupyterQuiz",
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "points": {"type": "number", "exclusiveMinimum": 0},
            "type": {
                "type": "string",
                "pattern": "multiple_choice|many_choice",
            },
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "correct": {"type": "boolean"},
                        "feedback": {"type": "string"},
                        "answer_cols": {"type": "number"},
                        "hide": {"type": "boolean"},
                    },
                    "required": ["answer", "correct"],
                },
            },
            "code": {"type": "string"},
        },
        "required": ["type", "question", "answers"],
    }
    NUM = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/jmshea/jupyterquiz/num_schema.json",
        "title": "JupyterQuiz Numeric Question",
        "description": "Schema for Numeric Questions in JupyterQuiz",
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "type": {"type": "string", "pattern": "numeric"},
            "precision": {"type": "integer"},
            "points": {"type": "number", "exclusiveMinimum": 0},
            "hide": {"type": "boolean"},
            "answers": {
                "type": "array",
                "items": {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {
                                "value": {"type": "number"},
                                "correct": {"type": "boolean"},
                                "feedback": {"type": "string"},
                            },
                            "required": ["value", "correct"],
                        },
                        {
                            "type": "object",
                            "properties": {
                                "range": {
                                    "type": "array",
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "correct": {"type": "boolean"},
                                "feedback": {"type": "string"},
                            },
                            "required": ["range", "correct"],
                        },
                        {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "pattern": "default"},
                                "feedback": {"type": "string"},
                            },
                            "required": ["type", "feedback"],
                        },
                    ],
                },
            },
        },
    }
    STR = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/jmshea/jupyterquiz/str_schema.json",
        "title": "JupyterQuiz String Question",
        "description": "Schema for String (free-text) Questions in JupyterQuiz",
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "type": {"type": "string", "pattern": "string"},
            "points": {"type": "number", "exclusiveMinimum": 0},
            "hide": {"type": "boolean"},
            "answers": {
                "type": "array",
                "items": {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {
                                "answer": {"type": "string"},
                                "correct": {"type": "boolean"},
                                "match_case": {"type": "boolean"},
                                "fuzzy_threshold": {"type": "number", "minimum": 0, "maximum": 1},
                                "feedback": {"type": "string"},
                            },
                            "required": ["answer", "correct"],
                        },
                        {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "pattern": "default"},
                                "feedback": {"type": "string"},
                            },
                            "required": ["type", "feedback"],
                        },
                    ],
                },
            },
        },
        "required": ["type", "question", "answers"],
    }


SCHEMATA = {
    "many_choice": "MC",
    "multiple_choice": "MC",
    "numeric": "NUM",
    "string": "STR",
}


def validate_question(question: dict[str, Any]) -> None:
    """
    Validate a question dict against the appropriate JSON Schema.

    Parameters
    ----------
    question : dict
        Parsed question dictionary with at least a ``'type'`` key.

    Raises
    ------
    jsonschema.exceptions.ValidationError
        If the question does not conform to its schema.
    """
    schema = Schema[SCHEMATA[question["type"]]].value
    jsonschema.validate(question, schema)
