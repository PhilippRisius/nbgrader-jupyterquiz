"""
Autograder helper for graded quizzes (v0.4.0+).

Reads the ``responses.json`` sidecar file written by the JS recorder
and grades the recorded responses against the quiz definition in the
source notebook.  Intended to be called from a hidden autograded test
cell that the instructor authors alongside the quiz task cell.

Usage (in an autograded test cell)::

    from nbgrader_jupyterquiz import grade_quiz

    result = grade_quiz("quiz-1")
    assert result.passed, result.report

The sidecar path is resolved relative to the current working
directory, which nbgrader autograde sets to the assignment directory.
"""

import dataclasses
import json
import pathlib
from typing import Any

import nbformat

from nbgrader_jupyterquiz.grader import parse


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
    def points(self) -> int:
        """
        Return the maximum points for this question (defaults to 1).

        Returns
        -------
        int
            Positive integer point weight.
        """
        return int(self.question.get("points", 1) or 1)

    @property
    def earned(self) -> int:
        """
        Compute the points earned on this question (all-or-nothing per question).

        Returns
        -------
        int
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
        return _expected_answer(self.question)


@dataclasses.dataclass
class QuizResult:
    """Outcome of grading every question in a quiz region."""

    grade_id: str
    details: list[QuestionResult]

    @property
    def max_score(self) -> int:
        """
        Compute the sum of per-question point values.

        Returns
        -------
        int
            Total points this quiz can yield.
        """
        return sum(d.points for d in self.details)

    @property
    def score(self) -> int:
        """
        Compute the sum of per-question points earned.

        Returns
        -------
        int
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
        lines = [f"Quiz {self.grade_id!r}: {self.score}/{self.max_score}"]
        for d in self.details:
            marker = "PASS" if d.correct else "FAIL"
            lines.append(f"  [{marker}] Q{d.qnum} ({d.question_type}): recorded={d.recorded!r}, expected={d.expected!r}")
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
        display(HTML(self._render_review_html()))

    def _render_review_html(self) -> str:
        """
        Render the full review block as a scoped HTML string.

        Returns
        -------
        str
            Complete ``<style>`` + ``<div>`` block ready for
            :class:`IPython.display.HTML`.
        """
        from html import escape  # noqa: PLC0415

        parts = [_REVIEW_CSS, '<div class="jq-review">']
        parts.append(f'<div class="jq-review-score">Your score: {self.score} / {self.max_score}</div>')
        for d in self.details:
            qtext = escape(d.question.get("question", "") or "")
            header_points = f' <span class="jq-review-ptag">{d.earned}/{d.points} pts</span>'
            parts.append(f'<div class="jq-review-question"><div class="jq-review-qhead">Q{d.qnum + 1}. {qtext}{header_points}</div>')
            qtype = d.question_type
            if qtype in ("multiple_choice", "many_choice"):
                parts.append(_render_review_choice(d))
            elif qtype == "numeric":
                parts.append(_render_review_numeric(d))
            elif qtype == "string":
                parts.append(_render_review_string(d))
            else:
                parts.append(f'<div class="jq-review-row">(unrecognised question type: {escape(qtype)})</div>')
            parts.append("</div>")
        parts.append("</div>")
        return "\n".join(parts)


# -- Review rendering helpers (static HTML, scoped CSS) --------------------


_REVIEW_CSS = """<style>
.jq-review { font-family: sans-serif; margin: 10px 0; padding: 10px 14px;
             border: 1px solid #ccc; border-radius: 6px;
             background: #fafafa; color: #222; max-width: 720px; }
.jq-review-score { font-weight: bold; font-size: 1.05em; margin-bottom: 8px; }
.jq-review-question { margin: 12px 0; padding-top: 6px;
                      border-top: 1px solid #e5e5e5; }
.jq-review-qhead { font-weight: 600; margin-bottom: 6px; }
.jq-review-row { margin: 4px 0; }
.jq-review-choice { display: inline-block; padding: 5px 10px; margin: 3px 4px 3px 0;
                    border-radius: 4px; border: 1px solid #ccc;
                    background: #f0f0f0; font-size: 0.95em; }
.jq-review-choice.correct-picked { background: #d1e7dd; border-color: #a3cfbb;
                                   color: #0a3622; }
.jq-review-choice.correct-missed { background: #fff3cd; border-color: #e7cf88;
                                   color: #664d03; }
.jq-review-choice.wrong-picked { background: #f8d7da; border-color: #eba5ab;
                                 color: #58151c; }
.jq-review-tag { font-size: 0.8em; opacity: 0.85; margin-left: 6px;
                 font-style: italic; }
.jq-review-numeric code { background: #eee; padding: 1px 5px; border-radius: 3px; }
.jq-review-ok { color: #0a7c2f; font-weight: 600; }
.jq-review-bad { color: #b02a37; font-weight: 600; }
.jq-review-muted { color: #666; font-style: italic; }
.jq-review-ptag { font-size: 0.85em; font-weight: 500; margin-left: 8px;
                  padding: 1px 8px; border-radius: 10px;
                  background: #e7e9ec; color: #333; }
</style>"""


def _extract_picked(recorded: Any) -> list[str]:
    """
    Normalise the student's recorded MC response to a list of strings.

    Parameters
    ----------
    recorded : Any
        Raw recorded payload from the sidecar.

    Returns
    -------
    list of str
        Possibly empty list of selected answer texts.
    """
    if not isinstance(recorded, dict):
        return []
    selected = recorded.get("selected")
    if isinstance(selected, list):
        return [s for s in selected if isinstance(s, str)]
    if isinstance(selected, str):
        return [selected]
    return []


def _render_review_choice(detail: "QuestionResult") -> str:
    """
    Render the review row for a single-choice / many-choice question.

    Parameters
    ----------
    detail : QuestionResult
        Per-question grading outcome.

    Returns
    -------
    str
        HTML fragment listing each answer option with correctness markers.
    """
    from html import escape  # noqa: PLC0415

    picked = _extract_picked(detail.recorded)
    rows = []
    for answer in detail.question.get("answers", []):
        text = answer.get("answer", "")
        is_correct = bool(answer.get("correct"))
        is_picked = text in picked
        cls = "jq-review-choice"
        tag = ""
        if is_correct and is_picked:
            cls += " correct-picked"
            tag = '<span class="jq-review-tag">✓ your choice — correct</span>'
        elif is_correct and not is_picked:
            cls += " correct-missed"
            tag = '<span class="jq-review-tag">correct answer — not selected</span>'
        elif (not is_correct) and is_picked:
            cls += " wrong-picked"
            tag = '<span class="jq-review-tag">✗ your choice — incorrect</span>'
        rows.append(f'<span class="{cls}">{escape(str(text))}</span>{tag}')
    if not picked:
        rows.insert(0, '<div class="jq-review-row jq-review-muted">No answer recorded.</div>')
    return '<div class="jq-review-row">' + " ".join(rows) + "</div>"


def _render_review_numeric(detail: "QuestionResult") -> str:
    """
    Render the review row for a numeric question.

    Parameters
    ----------
    detail : QuestionResult
        Per-question grading outcome.

    Returns
    -------
    str
        HTML fragment showing the student's numeric answer and the expected value.
    """
    from html import escape  # noqa: PLC0415

    expected = detail.expected
    expected_fmt = ", ".join(_fmt_numeric_expected(e) for e in (expected or []))
    if not isinstance(detail.recorded, dict):
        return (
            f'<div class="jq-review-row jq-review-numeric jq-review-muted">No answer recorded (expected <code>{escape(expected_fmt)}</code>).</div>'
        )
    raw = detail.recorded.get("raw", "")
    parsed = detail.recorded.get("parsed", "")
    raw_show = escape(str(raw))
    parsed_show = escape(str(parsed))
    extra = f" (parsed as <code>{parsed_show}</code>)" if str(raw) != str(parsed) else ""
    mark = '<span class="jq-review-ok">✓ correct</span>' if detail.correct else '<span class="jq-review-bad">✗ incorrect</span>'
    return (
        f'<div class="jq-review-row jq-review-numeric">'
        f"You answered: <code>{raw_show}</code>{extra}. "
        f"{mark} (expected <code>{escape(expected_fmt)}</code>)."
        f"</div>"
    )


def _render_review_string(detail: "QuestionResult") -> str:
    """
    Render the review row for a string question.

    Parameters
    ----------
    detail : QuestionResult
        Per-question grading outcome.

    Returns
    -------
    str
        HTML fragment showing the student's string answer and the expected value.
    """
    from html import escape  # noqa: PLC0415

    expected = detail.expected or []
    expected_fmt = ", ".join(escape(str(e)) for e in expected) if expected else "—"
    if not isinstance(detail.recorded, dict):
        return f'<div class="jq-review-row jq-review-muted">No answer recorded (expected <code>{expected_fmt}</code>).</div>'
    value = detail.recorded.get("value", "")
    mark = '<span class="jq-review-ok">✓ correct</span>' if detail.correct else '<span class="jq-review-bad">✗ incorrect</span>'
    return f'<div class="jq-review-row">You answered: <code>{escape(str(value))}</code>. {mark} (expected <code>{expected_fmt}</code>).</div>'


def _fmt_numeric_expected(e: Any) -> str:
    """
    Format a single expected numeric value or range for display.

    Parameters
    ----------
    e : Any
        Either a scalar value or a ``(min, max)`` tuple.

    Returns
    -------
    str
        ``"[min, max)"`` for a range, ``str(value)`` otherwise.
    """
    if isinstance(e, tuple):
        return f"[{e[0]}, {e[1]})"
    return str(e)


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
        :meth:`CreateQuiz.preprocess`), which embed the answer key directly
        in their ``### BEGIN HIDDEN TESTS`` block.
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

    if qtype == "multiple_choice":
        correct = _grade_multiple_choice(question, recorded)
    elif qtype == "many_choice":
        correct = _grade_many_choice(question, recorded)
    elif qtype == "numeric":
        correct = _grade_numeric(question, recorded)
    elif qtype == "string":
        correct = _grade_string(question, recorded)
    else:
        correct = False

    return QuestionResult(qnum=qnum, question=question, recorded=recorded, correct=correct)


def _expected_answer(question: dict[str, Any]) -> Any:
    """
    Derive a human-readable representation of a question's expected answer.

    Parameters
    ----------
    question : dict
        Question dict as produced by :mod:`~nbgrader_jupyterquiz.grader.parse`.

    Returns
    -------
    list or None
        A list of expected answer texts (choice/string) or values/ranges
        (numeric).  ``None`` for unsupported question types.
    """
    qtype = question.get("type")
    answers = question.get("answers", [])
    correct_answers = [a for a in answers if a.get("correct")]
    if qtype in ("multiple_choice", "many_choice", "string"):
        return [a.get("answer") for a in correct_answers]
    if qtype == "numeric":
        expected = []
        for a in correct_answers:
            if a.get("type") == "value":
                expected.append(a.get("value"))
            elif a.get("type") == "range":
                expected.append(tuple(a.get("range", [])))
        return expected
    return None


def _grade_multiple_choice(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
    """
    Grade a single-choice question.

    Parameters
    ----------
    question : dict
        Question dict with its answer list.
    recorded : dict
        Student's recorded response with a ``selected`` string.

    Returns
    -------
    bool
        True iff ``selected`` matches a ``correct: true`` answer.
    """
    if recorded.get("type") != "multiple_choice":
        return False
    selected = recorded.get("selected")
    if not isinstance(selected, str):
        return False
    for a in question.get("answers", []):
        if a.get("correct") and a.get("answer") == selected:
            return True
    return False


def _grade_many_choice(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
    """
    Grade a many-choice question (set equality).

    Parameters
    ----------
    question : dict
        Question dict with its answer list.
    recorded : dict
        Student's recorded response with a ``selected`` list.

    Returns
    -------
    bool
        True iff the set of selected answers equals the set of correct
        answers.
    """
    if recorded.get("type") != "many_choice":
        return False
    selected = recorded.get("selected")
    if not isinstance(selected, list):
        return False
    correct_set = {a.get("answer") for a in question.get("answers", []) if a.get("correct")}
    return set(selected) == correct_set


def _grade_numeric(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
    """
    Grade a numeric question (value or range, optional precision).

    Parameters
    ----------
    question : dict
        Question dict with its answer list (values and/or ranges).
    recorded : dict
        Student's recorded response with a ``parsed`` numeric field.

    Returns
    -------
    bool
        True iff ``parsed`` matches a ``correct`` value (at the
        configured precision) or falls inside a ``correct`` range.
    """
    if recorded.get("type") != "numeric":
        return False
    parsed = recorded.get("parsed")
    if not isinstance(parsed, (int, float)):
        return False

    precision = question.get("precision")
    for a in question.get("answers", []):
        if not a.get("correct"):
            continue
        atype = a.get("type")
        if atype == "value":
            expected = float(a.get("value"))
            if precision and precision > 0:
                if _round_to_precision(parsed, precision) == _round_to_precision(expected, precision):
                    return True
            elif parsed == expected:
                return True
        elif atype == "range":
            lo, hi = a.get("range", [None, None])
            if lo is not None and hi is not None and lo <= parsed <= hi:
                return True
    return False


def _grade_string(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
    """
    Grade a string question (exact or fuzzy match).

    Parameters
    ----------
    question : dict
        Question dict with its answer list; each answer may set
        ``match_case`` and ``fuzzy_threshold``.
    recorded : dict
        Student's recorded response with a ``value`` string.

    Returns
    -------
    bool
        True iff ``value`` matches any correct answer (honouring
        ``match_case`` and ``fuzzy_threshold`` using Levenshtein
        similarity).
    """
    if recorded.get("type") != "string":
        return False
    value = recorded.get("value")
    if not isinstance(value, str):
        return False
    for a in question.get("answers", []):
        if not a.get("correct"):
            continue
        expected = a.get("answer", "")
        if a.get("match_case"):
            match = value == expected
        else:
            match = value.lower() == expected.lower()
        if match:
            return True
        threshold = a.get("fuzzy_threshold")
        if threshold:
            distance = _levenshtein(
                value if a.get("match_case") else value.lower(),
                expected if a.get("match_case") else expected.lower(),
            )
            max_len = max(len(value), len(expected), 1)
            if 1 - (distance / max_len) >= threshold:
                return True
    return False


def _round_to_precision(x: float, precision: int) -> float:
    """
    Round a float to a given number of significant digits.

    Mirrors JavaScript's ``Number.prototype.toPrecision`` so numeric
    questions with a ``[N]`` precision marker score the same way the
    display JS evaluates them in the browser.

    Parameters
    ----------
    x : float
        Value to round.
    precision : int
        Number of significant digits.

    Returns
    -------
    float
        Rounded value.
    """
    if x == 0:
        return 0.0
    return float(f"{x:.{precision}g}")


def _levenshtein(a: str, b: str) -> int:
    """
    Compute the Levenshtein (edit) distance between two strings.

    Parameters
    ----------
    a : str
        First string.
    b : str
        Second string.

    Returns
    -------
    int
        Minimum number of single-character insertions, deletions, or
        substitutions required to transform ``a`` into ``b``.
    """
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]
