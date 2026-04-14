"""Tests for the display module — focused on real failure scenarios."""

import pytest

from nbgrader_jupyterquiz.display.dynamic.display import _DEFAULT_COLORS, _FDSP_COLORS, display_quiz
from nbgrader_jupyterquiz.display.dynamic.loader import load_questions_script
from nbgrader_jupyterquiz.display.dynamic.renderer import build_styles


# CSS variable names documented in docs/display-options.rst
_DOCUMENTED_CSS_VARS = {
    "--jq-multiple-choice-bg",
    "--jq-many-choice-bg",
    "--jq-numeric-bg",
    "--jq-mc-button-bg",
    "--jq-mc-button-border",
    "--jq-mc-button-inset-shadow",
    "--jq-numeric-input-bg",
    "--jq-numeric-input-label",
    "--jq-numeric-input-shadow",
    "--jq-string-bg",
    "--jq-correct-color",
    "--jq-incorrect-color",
    "--jq-text-color",
    "--jq-link-color",
}


# ---------------------------------------------------------------------------
# Group 1 — Palette safety
# ---------------------------------------------------------------------------


def test_default_and_fdsp_have_same_keys():
    """Both palettes must define exactly the same set of CSS variables."""
    assert set(_DEFAULT_COLORS) == set(_FDSP_COLORS)


def test_color_dicts_cover_all_documented_variables():
    """Every documented CSS variable must exist in both palette dicts."""
    assert _DOCUMENTED_CSS_VARS == set(_DEFAULT_COLORS)
    assert _DOCUMENTED_CSS_VARS == set(_FDSP_COLORS)


# ---------------------------------------------------------------------------
# Group 2 — display_quiz parameter guards
# ---------------------------------------------------------------------------


def test_shuffle_questions_and_preserve_responses_incompatible():
    with pytest.raises(AssertionError):
        display_quiz([], shuffle_questions=True, preserve_responses=True)


def test_num_and_preserve_responses_incompatible():
    with pytest.raises(AssertionError):
        display_quiz([], num=3, preserve_responses=True)


def test_question_alignment_invalid():
    with pytest.raises(AssertionError):
        display_quiz([], question_alignment="diagonal")


# ---------------------------------------------------------------------------
# Group 3 — build_styles CSS injection
# ---------------------------------------------------------------------------


def test_build_styles_injects_all_color_vars():
    color_dict = {
        "--jq-correct-color": "#00ff00",
        "--jq-incorrect-color": "#ff0000",
    }
    styles = build_styles("testid", color_dict)
    assert "   --jq-correct-color: #00ff00;" in styles
    assert "   --jq-incorrect-color: #ff0000;" in styles


def test_build_styles_includes_shared_css():
    styles = build_styles("testid", {})
    # styles.css always contains the .Answer selector
    assert ".Answer" in styles


# ---------------------------------------------------------------------------
# Group 4 — load_questions_script production path
# ---------------------------------------------------------------------------


def test_load_list_embeds_json():
    script, static, url = load_questions_script([{"type": "multiple_choice"}], "abc")
    assert "var questionsabc=" in script
    assert static is True
    assert url == ""


def test_load_dom_ref_generates_id_and_class_lookup():
    script, static, url = load_questions_script("#test-nb:0.0", "abc")
    assert 'getElementById("test-nb:0.0")' in script
    assert 'getElementsByClassName("test-nb:0.0")' in script
    assert static is True
