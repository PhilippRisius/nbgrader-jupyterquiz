"""Tests for the display module — focused on real failure scenarios."""

from unittest.mock import patch

import pytest

from nbgrader_jupyterquiz.display.dynamic.display import _DEFAULT_COLORS, _FDSP_COLORS, display_quiz
from nbgrader_jupyterquiz.display.dynamic.loader import load_questions_script
from nbgrader_jupyterquiz.display.dynamic.renderer import build_styles, render_div


# CSS variable names documented in docs/display-options.rst
_DOCUMENTED_CSS_VARS = {
    "--jq-multiple-choice-bg",
    "--jq-many-choice-bg",
    "--jq-numeric-bg",
    "--jq-mc-button-bg",
    "--jq-mc-button-border",
    "--jq-mc-button-text",
    "--jq-mc-button-inset-shadow",
    "--jq-numeric-input-bg",
    "--jq-numeric-input-label",
    "--jq-numeric-input-shadow",
    "--jq-string-bg",
    "--jq-correct-color",
    "--jq-incorrect-color",
    "--jq-select-color",
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


def test_load_dom_ref_escapes_quotes_in_id():
    script, _, _ = load_questions_script('#week "1" \\ intro:0.0', "abc")
    assert 'getElementById("week \\"1\\" \\\\ intro:0.0")' in script


def test_load_dom_ref_parses_text_content():
    """Parse textContent: innerHTML would re-escape ``<`` / ``&`` inside unencoded JSON strings."""
    script, _, _ = load_questions_script("#test-nb:0.0", "abc")
    assert "JSON.parse(element.textContent)" in script
    assert "innerHTML" not in script


def test_load_filename_starting_with_http_is_a_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "http_status.json").write_text("[]", encoding="utf-8")
    script, static, url = load_questions_script("http_status.json", "abc")
    assert url == ""
    assert static is True


def test_display_quiz_missing_file_shows_notice_instead_of_raising(tmp_path, capsys):
    """
    Graded cells call display_quiz before grading; a missing file must not abort the cell.

    Nor may it write to stderr: nbgrader scores a graded cell with stderr output as zero.
    """
    with patch("nbgrader_jupyterquiz.display.dynamic.display.display") as mock_display:
        display_quiz(str(tmp_path / "missing.json"))
    (shown,), _ = mock_display.call_args
    assert "Could not load quiz data" in shown.data
    assert capsys.readouterr().err == ""


def test_load_file_ref_reads_utf8(tmp_path):
    path = tmp_path / "quiz.json"
    path.write_text('[{"question": "Größe?"}]', encoding="utf-8")
    script, static, _ = load_questions_script(str(path), "abc")
    assert "Größe?" in script
    assert static is True


def test_render_div_escapes_grade_id():
    div = render_div("abc", False, True, False, 5, 600, 10, "left", grade_id='q"1')
    assert 'data-grade-id="q&quot;1"' in div
