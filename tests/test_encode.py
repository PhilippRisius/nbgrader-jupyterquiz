"""Tests for grader.encode."""

import base64

from nbgrader_jupyterquiz.grader.encode import to_base64


def test_round_trip():
    """Encoded output decodes back to the original string, including non-ASCII."""
    payload = '[{"type": "multiple_choice", "question": "What is 2+2? (Hélas!)"}]'
    assert base64.b64decode(to_base64(payload)).decode("utf-8") == payload
