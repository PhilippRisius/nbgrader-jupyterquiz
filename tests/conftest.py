"""Shared pytest fixtures for the test suite."""

import pytest

from nbgrader_jupyterquiz import CreateQuiz


@pytest.fixture
def resources():
    """Minimal nbgrader resources dict."""
    return {"unique_key": "test-nb"}


@pytest.fixture
def preprocessor():
    """A default CreateQuiz instance."""
    return CreateQuiz()
