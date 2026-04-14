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
    assert 'display_quiz("#test-nb:0.0")' in nb.cells[1].source


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
