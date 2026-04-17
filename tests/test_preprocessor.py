"""Tests for grader.preprocessor (CreateQuiz)."""

import base64
import json
from unittest.mock import patch

import nbformat.v4
import pytest

from nbgrader_jupyterquiz import CreateQuiz
from nbgrader_jupyterquiz.grader.parse import ParseError


def task_cell(source):
    cell = nbformat.v4.new_markdown_cell(source=source)
    cell.metadata["nbgrader"] = {"task": True}
    return cell


def plain_cell(source):
    return nbformat.v4.new_markdown_cell(source=source)


def make_notebook(*cells):
    nb = nbformat.v4.new_notebook()
    nb.cells = list(cells)
    return nb


# ---------------------------------------------------------------------------
# Shared source strings
# ---------------------------------------------------------------------------

QUIZ_SOURCE = """\
Some text.

#### Quiz
* (SC) "What is 2 + 2?"
  + "4"
  - "3"
#### End Quiz

More text."""

TWO_QUIZ_SOURCE = """\
#### Quiz
* (SC) "First question?"
  + "Yes"
  - "No"
#### End Quiz

#### Quiz
* (SC) "Second question?"
  - "Yes"
  + "No"
#### End Quiz"""

PLAIN_SOURCE = "Just a markdown cell.\n\nNo quiz here."

# Option-mode variants (used in Group F)
_BODY = '\n* (SC) "Q?"\n  + "A"\n  - "B"\n#### End Quiz'
QUIZ_INLINE_HIDDEN = f"#### Quiz encoded=false inline=true hidden=true{_BODY}"
QUIZ_INLINE_VISIBLE = f"#### Quiz encoded=false inline=true hidden=false{_BODY}"
QUIZ_NON_INLINE = f"#### Quiz encoded=false inline=false hidden=false{_BODY}"
QUIZ_ENCODED = f"#### Quiz encoded=true inline=true hidden=true{_BODY}"


# ---------------------------------------------------------------------------
# Group A — Happy path: cell structure
# ---------------------------------------------------------------------------


def test_single_quiz_appends_code_cell(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert len(nb.cells) == 2
    assert nb.cells[1].cell_type == "code"


def test_code_cell_import_and_display_call(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    src = nb.cells[1].source
    assert src.startswith("from nbgrader_jupyterquiz.display import display_quiz")
    assert "display_quiz(" in src


def test_code_cell_has_remove_input_tag(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert nb.cells[1].metadata["tags"] == ["remove-input"]


# ---------------------------------------------------------------------------
# Group B — Cell source transformation
# ---------------------------------------------------------------------------


def test_quiz_region_removed_from_cell_source(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    src = nb.cells[0].source
    assert "Some text." in src
    assert "More text." in src
    assert "#### Quiz" not in src
    assert "#### End Quiz" not in src


def test_no_quiz_cell_source_unchanged(preprocessor, resources):
    nb = make_notebook(plain_cell(PLAIN_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert len(nb.cells) == 1
    assert nb.cells[0].source == PLAIN_SOURCE


# ---------------------------------------------------------------------------
# Group C — Multiple quizzes
# ---------------------------------------------------------------------------


def test_multiple_quizzes_in_one_cell(preprocessor, resources):
    nb = make_notebook(task_cell(TWO_QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert len(nb.cells) == 3
    assert "0.0" in nb.cells[1].source
    assert "0.1" in nb.cells[2].source


def test_import_only_in_first_code_cell(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_SOURCE), task_cell(QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    # cells: [md0, code0, md1, code1]
    assert "import display_quiz" in nb.cells[1].source
    assert "import display_quiz" not in nb.cells[3].source


# ---------------------------------------------------------------------------
# Group D — enforce_metadata
# ---------------------------------------------------------------------------


def test_quiz_in_plain_cell_enforce_true_raises(preprocessor, resources):
    nb = make_notebook(plain_cell(QUIZ_SOURCE))
    with pytest.raises(RuntimeError):
        preprocessor.preprocess(nb, resources)


def test_quiz_in_plain_cell_enforce_false_ok(resources):
    pp = CreateQuiz()
    pp.enforce_metadata = False
    nb = make_notebook(plain_cell(QUIZ_SOURCE))
    nb, _ = pp.preprocess(nb, resources)
    assert len(nb.cells) == 2


def test_quiz_in_task_cell_always_ok(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert len(nb.cells) == 2


# ---------------------------------------------------------------------------
# Group E — ParseError handling (mocked parse_cell)
# ---------------------------------------------------------------------------


def test_parse_error_in_task_cell_reraises(preprocessor, resources):
    nb = make_notebook(task_cell("dummy"))
    with patch("nbgrader_jupyterquiz.grader.preprocessor.parse.parse_cell", side_effect=ParseError("bad")):
        with pytest.raises(ParseError):
            preprocessor.preprocess(nb, resources)


def test_parse_error_in_plain_cell_enforce_true_skips(preprocessor, resources):
    original = "original content"
    nb = make_notebook(plain_cell(original))
    with patch("nbgrader_jupyterquiz.grader.preprocessor.parse.parse_cell", side_effect=ParseError("bad")):
        nb, _ = preprocessor.preprocess(nb, resources)
    assert len(nb.cells) == 1
    assert nb.cells[0].source == original


def test_parse_error_in_plain_cell_enforce_false_logs_warning(resources, caplog):
    pp = CreateQuiz()
    pp.enforce_metadata = False
    nb = make_notebook(plain_cell("dummy"))
    with patch("nbgrader_jupyterquiz.grader.preprocessor.parse.parse_cell", side_effect=ParseError("bad")):
        import logging

        with caplog.at_level(logging.WARNING):
            pp.preprocess(nb, resources)
    assert any("could not be parsed" in r.message for r in caplog.records)


def test_celltoolbar_metadata_removed(preprocessor, resources):
    nb = make_notebook(plain_cell("no quiz"))
    nb.metadata["celltoolbar"] = "Create Assignment"
    nb, _ = preprocessor.preprocess(nb, resources)
    assert "celltoolbar" not in nb.metadata


def test_filename_mode(resources, tmp_path):
    quiz_file = tmp_path / "quiz.json"
    source = f'#### Quiz filename={quiz_file} inline=false encoded=false\n* (SC) "Q?"\n  + "A"\n  - "B"\n#### End Quiz'
    pp = CreateQuiz()
    nb = make_notebook(task_cell(source))
    nb, _ = pp.preprocess(nb, resources)
    assert quiz_file.exists()
    assert '"type"' in quiz_file.read_text()
    assert str(quiz_file) in nb.cells[1].source


def test_filename_oserror_is_logged(resources, caplog):
    source = '#### Quiz filename=/no/such/dir/quiz.json inline=false\n* (SC) "Q?"\n  + "A"\n  - "B"\n#### End Quiz'
    pp = CreateQuiz()
    nb = make_notebook(task_cell(source))
    import logging

    with caplog.at_level(logging.ERROR):
        nb, _ = pp.preprocess(nb, resources)
    assert any("Cannot open" in r.message for r in caplog.records)
    assert len(nb.cells) == 2  # code cell still appended despite the error


# ---------------------------------------------------------------------------
# Group F — Option modes (real parse path via parse_quiz_options)
# ---------------------------------------------------------------------------


def test_inline_hidden_mode(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_INLINE_HIDDEN))
    nb, _ = preprocessor.preprocess(nb, resources)
    src = nb.cells[0].source
    assert '<span style="display:none"' in src
    # span must carry the quiz JSON (plaintext, not base64)
    assert '"type"' in src


def test_inline_visible_mode(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_INLINE_VISIBLE))
    nb, _ = preprocessor.preprocess(nb, resources)
    src = nb.cells[0].source
    assert "0.0=" in src
    assert '"type"' in src


def test_non_inline_mode(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_NON_INLINE))
    nb, _ = preprocessor.preprocess(nb, resources)
    # nothing extra injected into the markdown cell
    assert "<span" not in nb.cells[0].source
    assert "0.0=" not in nb.cells[0].source
    # display_quiz references the notebook name
    assert 'display_quiz("#test-nb:0.0"' in nb.cells[1].source


def test_encoded_content_is_valid_base64(preprocessor, resources):
    nb = make_notebook(task_cell(QUIZ_ENCODED))
    nb, _ = preprocessor.preprocess(nb, resources)
    src = nb.cells[0].source
    # Extract content from hidden span
    start = src.index(">", src.index('<span style="display:none"')) + 1
    end = src.index("</span>", start)
    encoded = src[start:end]
    decoded = base64.b64decode(encoded).decode("utf-8")
    questions = json.loads(decoded)
    assert questions[0]["type"] == "multiple_choice"


# ---------------------------------------------------------------------------
# Group G — grade_id propagation (v0.4.0+)
# ---------------------------------------------------------------------------


def _graded_task_cell(source, grade_id):
    cell = nbformat.v4.new_markdown_cell(source=source)
    cell.metadata["nbgrader"] = {"task": True, "grade_id": grade_id}
    return cell


def test_grade_id_passed_into_display_quiz(preprocessor, resources):
    nb = make_notebook(_graded_task_cell(QUIZ_SOURCE, "quiz-cell-1"))
    nb, _ = preprocessor.preprocess(nb, resources)
    # The merged graded cell carries a suffixed grade_id so it doesn't
    # collide with the task cell's grade_id.
    assert "grade_id='quiz-cell-1-autograded'" in nb.cells[1].source


def test_grade_id_none_when_host_has_no_grade_id(preprocessor, resources):
    # task_cell() helper sets only {"task": True} — no grade_id.
    nb = make_notebook(task_cell(QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert "grade_id=None" in nb.cells[1].source


def test_grade_id_shared_across_multi_quiz_cell(preprocessor, resources):
    # Two quiz regions in one task cell → two merged cells, each with its
    # own suffixed grade_id (uniquified per region).
    nb = make_notebook(_graded_task_cell(TWO_QUIZ_SOURCE, "quiz-twin"))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert "grade_id='quiz-twin-autograded-0'" in nb.cells[1].source
    assert "grade_id='quiz-twin-autograded-1'" in nb.cells[2].source


# ---------------------------------------------------------------------------
# Group H — Auto-generated autograder test cells (v0.4.0+)
# ---------------------------------------------------------------------------


def test_graded_cell_merges_display_and_hidden_tests(preprocessor, resources):
    """
    In graded mode, the single code cell carries both display_quiz() and
    a ### BEGIN HIDDEN TESTS block that invokes grade_quiz with an embedded
    answer key.
    """
    nb = make_notebook(_graded_task_cell(QUIZ_SOURCE, "quiz-1"))
    nb, _ = preprocessor.preprocess(nb, resources)
    # cells: [task_md, merged_graded_cell]
    assert len(nb.cells) == 2
    merged = nb.cells[1]
    assert merged.cell_type == "code"
    # display_quiz at the top of the cell (visible in the release)
    assert "display_quiz(" in merged.source
    # hidden tests at the bottom (stripped in release, restored at autograde)
    assert "### BEGIN HIDDEN TESTS" in merged.source
    assert "### END HIDDEN TESTS" in merged.source
    # answer key embedded inline; grade_quiz invoked with it
    assert "_questions = [" in merged.source
    assert "grade_quiz('quiz-1-autograded', questions=_questions)" in merged.source
    # Partial credit: bare ``_result.score`` at the end makes the cell's
    # execute_result feed nbgrader's determine_grade().
    assert merged.source.rstrip().endswith("### END HIDDEN TESTS")
    assert "_result.score\n" in merged.source
    # Feedback-time review is emitted so the student sees their answers
    # and the correct ones in the autograded / feedback notebook.
    assert "_result.display_review()" in merged.source
    # cell is now the nbgrader-tracked graded cell itself
    assert merged.metadata["nbgrader"]["grade"] is True
    assert merged.metadata["nbgrader"]["solution"] is False
    assert merged.metadata["nbgrader"]["grade_id"] == "quiz-1-autograded"
    assert merged.metadata["nbgrader"]["locked"] is True


def test_no_hidden_tests_when_host_has_no_grade_id(preprocessor, resources):
    # task_cell() helper sets only {"task": True} — no grade_id → no grading.
    nb = make_notebook(task_cell(QUIZ_SOURCE))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert len(nb.cells) == 2
    # plain display cell, no hidden tests
    assert "### BEGIN HIDDEN TESTS" not in nb.cells[1].source
    assert "nbgrader" not in nb.cells[1].metadata


def test_merged_cell_points_equal_question_count(preprocessor, resources):
    """
    Cell points = one per question regardless of task-cell points.
    Partial credit (via bare ``_result.score``) falls out naturally.
    """
    cell = _graded_task_cell(QUIZ_SOURCE, "quiz-points")
    # Even if the instructor put a task_points value, the cell's points
    # come from len(questions) (QUIZ_SOURCE has 1 question).
    cell.metadata["nbgrader"]["points"] = 5
    nb = make_notebook(cell)
    nb, _ = preprocessor.preprocess(nb, resources)
    merged = nb.cells[1]
    assert merged.metadata["nbgrader"]["points"] == 1
    # Task cell points forced to 0 to avoid double-counting.
    assert nb.cells[0].metadata["nbgrader"]["points"] == 0


def test_merged_cell_points_multiple_regions(preprocessor, resources):
    """
    Two regions → each cell's points = number of questions in its region.
    TWO_QUIZ_SOURCE has one question per region → 1 pt each.
    """
    nb = make_notebook(_graded_task_cell(TWO_QUIZ_SOURCE, "quiz-multi-pts"))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert nb.cells[1].metadata["nbgrader"]["points"] == 1
    assert nb.cells[2].metadata["nbgrader"]["points"] == 1


def test_auto_generate_tests_can_be_disabled(resources):
    pp = CreateQuiz()
    pp.auto_generate_tests = False
    nb = make_notebook(_graded_task_cell(QUIZ_SOURCE, "quiz-no-auto"))
    nb, _ = pp.preprocess(nb, resources)
    # cells: [task_md, plain_display_quiz] — no hidden tests, no graded cell
    assert len(nb.cells) == 2
    assert "### BEGIN HIDDEN TESTS" not in nb.cells[1].source
    assert "nbgrader" not in nb.cells[1].metadata


def test_multiple_quiz_regions_each_get_own_graded_cell(preprocessor, resources):
    nb = make_notebook(_graded_task_cell(TWO_QUIZ_SOURCE, "quiz-multi"))
    nb, _ = preprocessor.preprocess(nb, resources)
    # cells: [task_md, merged_0, merged_1] — one merged cell per region
    assert len(nb.cells) == 3
    # Each merged cell has its own uniquified grade_id and hidden tests.
    assert "grade_quiz('quiz-multi-autograded-0'" in nb.cells[1].source
    assert "grade_quiz('quiz-multi-autograded-1'" in nb.cells[2].source
    assert nb.cells[1].metadata["nbgrader"]["grade_id"] == "quiz-multi-autograded-0"
    assert nb.cells[2].metadata["nbgrader"]["grade_id"] == "quiz-multi-autograded-1"


# ---------------------------------------------------------------------------
# Group J — Per-question points ({N} syntax) (v0.4.0+)
# ---------------------------------------------------------------------------


def test_cell_points_sum_of_per_question_points(preprocessor, resources):
    """Cell max_points = sum of each question's ``points`` field (default 1)."""
    source = (
        "#### Quiz encoded=false\n"
        '* (SC) {3} "First, worth 3"\n'
        '  + "A"\n'
        '  - "B"\n'
        '* (SC) "Second, default 1"\n'
        '  + "X"\n'
        '  - "Y"\n'
        '* (NM) {5} "Third, worth 5"\n'
        "  + <42>\n"
        "#### End Quiz"
    )
    nb = make_notebook(_graded_task_cell(source, "quiz-weighted"))
    nb, _ = preprocessor.preprocess(nb, resources)
    merged = nb.cells[1]
    assert merged.metadata["nbgrader"]["points"] == 9  # 3 + 1 + 5


def test_cell_points_all_default_when_no_markers(preprocessor, resources):
    """No {N} marker on any question → cell points = len(questions)."""
    source = '#### Quiz\n* (SC) "Q1"\n  + "A"\n  - "B"\n* (SC) "Q2"\n  + "A"\n  - "B"\n#### End Quiz'
    nb = make_notebook(_graded_task_cell(source, "quiz-unweighted"))
    nb, _ = preprocessor.preprocess(nb, resources)
    assert nb.cells[1].metadata["nbgrader"]["points"] == 2


# ---------------------------------------------------------------------------
# Group I — hide_correctness auto-enabled for graded quizzes (v0.4.0+)
# ---------------------------------------------------------------------------


def test_graded_quiz_auto_enables_hide_correctness(preprocessor, resources):
    """Task cell with grade_id → every MC answer gets hide:true in the rendered JSON."""
    source = '#### Quiz encoded=false\n* (SC) "What is 2+2?"\n  + "4"\n  - "5"\n#### End Quiz'
    nb = make_notebook(_graded_task_cell(source, "graded-hide"))
    nb, _ = preprocessor.preprocess(nb, resources)
    # The hidden span in the task cell carries the rendered JSON.
    task_src = nb.cells[0].source
    assert '"hide": true' in task_src


def test_non_graded_quiz_does_not_auto_enable_hide_correctness(preprocessor, resources):
    """Task cell without grade_id → no hide: true in the rendered JSON."""
    source = '#### Quiz encoded=false\n* (SC) "What is 2+2?"\n  + "4"\n  - "5"\n#### End Quiz'
    nb = make_notebook(task_cell(source))
    nb, _ = preprocessor.preprocess(nb, resources)
    task_src = nb.cells[0].source
    assert '"hide"' not in task_src


def test_graded_quiz_explicit_opt_out_preserved(preprocessor, resources):
    """Instructor can force ``hide_correctness=false`` on a graded quiz."""
    source = '#### Quiz encoded=false hide_correctness=false\n* (SC) "What is 2+2?"\n  + "4"\n  - "5"\n#### End Quiz'
    nb = make_notebook(_graded_task_cell(source, "graded-opt-out"))
    nb, _ = preprocessor.preprocess(nb, resources)
    task_src = nb.cells[0].source
    assert '"hide"' not in task_src
