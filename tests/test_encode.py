"""Tests for grader.encode."""

import base64

from nbgrader_jupyterquiz.grader.encode import to_base64


def test_round_trip():
    """Encoded output decodes back to the original string, including non-ASCII."""
    payload = '[{"type": "multiple_choice", "question": "What is 2+2? (Hélas!)"}]'
    assert base64.b64decode(to_base64(payload)).decode("utf-8") == payload


def test_empty_string():
    assert base64.b64decode(to_base64("")).decode("utf-8") == ""


def test_unicode_extended():
    """CJK and other non-Latin characters round-trip correctly."""
    payload = '{"question": "日本語テスト"}'
    assert base64.b64decode(to_base64(payload)).decode("utf-8") == payload
