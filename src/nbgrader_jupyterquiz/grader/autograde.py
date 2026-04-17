"""
Autograder helper for graded quizzes (v0.4.0+).

Reads the ``responses.json`` sidecar file written by the JS recorder
and grades the recorded responses against the quiz definition.
Intended to be called from the auto-generated hidden-tests block of a
graded-quiz cell — see
:class:`~nbgrader_jupyterquiz.grader.preprocessor.CreateQuiz`.

Usage (inside an autograder cell)::

    from nbgrader_jupyterquiz import grade_quiz

    result = grade_quiz("quiz-1-autograded", questions=[...])
    result.display_review()
    _result.score  # bare expression → nbgrader partial credit

The sidecar path is resolved relative to the current working
directory, which nbgrader autograde sets to the assignment directory.
Per-question grading is all-or-nothing; partial credit at the quiz
level falls out of summing ``QuestionResult.earned`` across the
quiz's questions.
"""

import dataclasses
import json
import pathlib
from typing import Any

import nbformat

from nbgrader_jupyterquiz.grader import parse
from nbgrader_jupyterquiz.grader._review import fmt_pts, render_review_html
from nbgrader_jupyterquiz.grader._scoring import (
    expected_answer,
    grade_many_choice,
    grade_multiple_choice,
    grade_numeric,
    grade_string,
)


SIDECAR_FILENAME = "responses.json"
SUPPORTED_SCHEMA_VERSIONS = (1,)


class GradeQuizError(Exception):
    """Raised when the helper cannot locate or interpret required inputs."""


@dataclasses.dataclass
class QuestionResult:
    """Outcome of grading a single question."""

    qnum: int
    question: dict[str, Any]
    recorded: Any
    correct: bool

    @property
    def question_type(self) -> str:
        """
        Return the canonical type string of the underlying question.

        Returns
        -------
        str
            ``"multiple_choice"``, ``"many_choice"``, ``"numeric"``,
            ``"string"``, or ``"unknown"``.
        """
        return str(self.question.get("type", "unknown"))

    @property
    def points(self) -> float:
        """
        Return the maximum points for this question (defaults to 1).

        Returns
        -------
        float
            Positive point weight.  Integer values (from ``{N}``) come
            through as ``int``; fractional values (``{0.5}``) as ``float``.
        """
        return self.question.get("points", 1) or 1

    @property
    def earned(self) -> float:
        """
        Compute the points earned on this question (all-or-nothing per question).

        Returns
        -------
        float
            ``self.points`` if correct, else 0.
        """
        return self.points if self.correct else 0

    @property
    def expected(self) -> Any:
        """
        Return a human-readable representation of the expected answer.

        Returns
        -------
        Any
            List of expected answer texts or numeric values/ranges.
        """
        return expected_answer(self.question)


@dataclasses.dataclass
class QuizResult:
    """Outcome of grading every question in a quiz region."""

    grade_id: str
    details: list[QuestionResult]

    @property
    def max_score(self) -> float:
        """
        Compute the sum of per-question point values.

        Returns
        -------
        float
            Total points this quiz can yield.
        """
        return sum(d.points for d in self.details)

    @property
    def score(self) -> float:
        """
        Compute the sum of per-question points earned.

        Returns
        -------
        float
            Total points the student earned on this quiz.
        """
        return sum(d.earned for d in self.details)

    @property
    def passed(self) -> bool:
        """
        Return True when every question in the quiz was answered correctly.

        Returns
        -------
        bool
            True iff ``score == max_score``.
        """
        return self.score == self.max_score

    @property
    def report(self) -> str:
        """
        Return a multi-line textual summary of the grade.

        Returns
        -------
        str
            Human-readable breakdown of per-question outcomes.
        """
        lines = [f"Quiz {self.grade_id!r}: {fmt_pts(self.score)}/{fmt_pts(self.max_score)}"]
        for d in self.details:
            marker = "PASS" if d.correct else "FAIL"
            lines.append(
                f"  [{marker}] Q{d.qnum} ({d.question_type}, "
                f"{fmt_pts(d.earned)}/{fmt_pts(d.points)} pts): "
                f"recorded={d.recorded!r}, expected={d.expected!r}"
            )
        return "\n".join(lines)

    def display_review(self) -> None:
        """
        Emit an HTML review of the quiz into the current cell output.

        Intended to be called from the auto-generated hidden-tests block
        of a graded-quiz cell.  When ``nbgrader generate_feedback``
        converts the autograded notebook to HTML, the review appears
        inline with the score so students can see which answers were
        correct, which they picked, and which they missed.

        The output is pure static HTML with scoped inline CSS — it
        renders correctly in any browser without a running Jupyter
        server or kernel.
        """
        try:
            from IPython.display import HTML, display  # noqa: PLC0415
        except ImportError:
            return
        display(HTML(render_review_html(self)))


def grade_quiz(
    grade_id: str,
    *,
    questions: list[dict[str, Any]] | None = None,
    notebook_path: str | pathlib.Path | None = None,
) -> QuizResult:
    """
    Grade the quiz identified by ``grade_id`` against recorded responses.

    Parameters
    ----------
    grade_id : str
        The sidecar key under which student responses are recorded.  The
        auto-generated test cells use ``"<task_grade_id>-autograded"``.
    questions : list of dict, optional
        Answer key — the list of question dicts (as produced by the parser)
        for this quiz.  When provided, the notebook is not read.  This is
        the path taken by auto-generated test cells (see
        :class:`~nbgrader_jupyterquiz.grader.preprocessor.CreateQuiz`),
        which embed the answer key directly in their
        ``### BEGIN HIDDEN TESTS`` block.
    notebook_path : str or Path, optional
        Path to the notebook containing the quiz task cell, for the
        fallback case where ``questions`` is ``None``.  Defaults to the
        only ``.ipynb`` file in the current working directory.

    Returns
    -------
    QuizResult
        Grading result with per-question details.  If the sidecar is
        missing or the quiz has no recorded responses, every question
        is reported as incorrect (score 0/max).
    """
    if questions is None:
        nb_path = _resolve_notebook_path(notebook_path)
        questions = _parse_quiz_from_notebook(nb_path, grade_id)

    responses = _load_sidecar_responses(grade_id)

    details = []
    for qnum, question in enumerate(questions):
        recorded = responses.get(str(qnum)) if responses else None
        details.append(_grade_question(qnum, question, recorded))

    return QuizResult(grade_id=grade_id, details=details)


def _resolve_notebook_path(notebook_path: str | pathlib.Path | None) -> pathlib.Path:
    """
    Return the path of the notebook to read, falling back to the sole ``.ipynb`` in CWD.

    Parameters
    ----------
    notebook_path : str, Path, or None
        Explicit path, or ``None`` to auto-detect.

    Returns
    -------
    pathlib.Path
        Resolved notebook path.
    """
    if notebook_path is not None:
        path = pathlib.Path(notebook_path)
        if not path.exists():
            raise GradeQuizError(f"notebook_path does not exist: {path}")
        return path
    matches = list(pathlib.Path().glob("*.ipynb"))
    if len(matches) == 0:
        raise GradeQuizError("No .ipynb found in CWD; pass notebook_path explicitly.")
    if len(matches) > 1:
        raise GradeQuizError(f"Multiple .ipynb files in CWD ({[p.name for p in matches]}); pass notebook_path explicitly.")
    return matches[0]


def _parse_quiz_from_notebook(nb_path: pathlib.Path, grade_id: str) -> list[dict[str, Any]]:
    """
    Read the notebook and parse the quiz region of the cell with the given grade_id.

    Parameters
    ----------
    nb_path : pathlib.Path
        Notebook file to parse.
    grade_id : str
        ``nbgrader.grade_id`` of the task cell to locate.

    Returns
    -------
    list of dict
        Parsed question dicts.
    """
    nb = nbformat.read(nb_path, as_version=4)
    for cell in nb.cells:
        nbg = cell.metadata.get("nbgrader") or {}
        if nbg.get("grade_id") == grade_id:
            break
    else:
        raise GradeQuizError(f"No cell with nbgrader.grade_id == {grade_id!r} in {nb_path}.")

    quizzes, _ = parse.parse_cell(cell.source)
    if not quizzes:
        raise GradeQuizError(
            f"Cell {grade_id!r} has no parsable quiz region.  "
            "Note: nbgrader autograde reverts locked task cells to source-notebook "
            "form, so the #### Quiz syntax must be present."
        )
    if len(quizzes) > 1:
        raise GradeQuizError(f"Cell {grade_id!r} has {len(quizzes)} quiz regions; only one is supported.")
    return quizzes[0].questions


def _load_sidecar_responses(grade_id: str) -> dict[str, Any] | None:
    """
    Load the responses sidecar from CWD and return the entry for the given grade_id.

    Parameters
    ----------
    grade_id : str
        Sidecar key whose responses dict to return.

    Returns
    -------
    dict or None
        The qnum-keyed response dict, or ``None`` if the sidecar is
        missing or has no entry for this grade_id.
    """
    sidecar = pathlib.Path.cwd() / SIDECAR_FILENAME
    if not sidecar.exists():
        return None
    try:
        data = json.loads(sidecar.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise GradeQuizError(f"Cannot read {sidecar}: {exc}") from exc
    if data.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        raise GradeQuizError(f"Unsupported schema_version in {sidecar}: {data.get('schema_version')!r}. Supported: {SUPPORTED_SCHEMA_VERSIONS}.")
    return (data.get("responses") or {}).get(grade_id)


def _grade_question(qnum: int, question: dict[str, Any], recorded: Any) -> QuestionResult:
    """
    Grade a single question against the student's recorded response.

    Parameters
    ----------
    qnum : int
        Zero-based question index within the quiz.
    question : dict
        Question dict as produced by the parser.
    recorded : Any
        Student's recorded response payload, or ``None``.

    Returns
    -------
    QuestionResult
        Grading outcome.
    """
    qtype = question.get("type", "unknown")

    if recorded is None or not isinstance(recorded, dict) or "type" not in recorded:
        return QuestionResult(qnum=qnum, question=question, recorded=recorded, correct=False)

    dispatch = {
        "multiple_choice": grade_multiple_choice,
        "many_choice": grade_many_choice,
        "numeric": grade_numeric,
        "string": grade_string,
    }
    grader = dispatch.get(qtype)
    correct = grader(question, recorded) if grader else False
    return QuestionResult(qnum=qnum, question=question, recorded=recorded, correct=correct)
