"""Shared pytest fixtures for the test suite."""

import itertools

import pytest

from nbgrader_jupyterquiz import CreateQuiz


@pytest.fixture(autouse=True)
def reset_quiz_counter():
    """Reset the class-level counter before each test for deterministic tag values."""
    CreateQuiz.quiz_cell_counter = itertools.count()


@pytest.fixture
def resources():
    """Minimal nbgrader resources dict."""
    return {"unique_key": "test-nb"}


@pytest.fixture
def preprocessor():
    """A default CreateQuiz instance."""
    return CreateQuiz()
