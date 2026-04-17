"""
Per-question-type grading helpers for :mod:`~nbgrader_jupyterquiz.grader.autograde`.

Each ``grade_*`` function takes a parsed question dict plus the
student's recorded response payload and returns ``True`` iff the
response satisfies that question's correctness criteria.  Grading is
all-or-nothing per question — partial credit at the quiz level falls
out of summing per-question outcomes in
:class:`~nbgrader_jupyterquiz.grader.autograde.QuizResult`.
"""

from typing import Any


def grade_multiple_choice(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
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


def grade_many_choice(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
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


def grade_numeric(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
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


def grade_string(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
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


def expected_answer(question: dict[str, Any]) -> Any:
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
        expected: list[Any] = []
        for a in correct_answers:
            if a.get("type") == "value":
                expected.append(a.get("value"))
            elif a.get("type") == "range":
                expected.append(tuple(a.get("range", [])))
        return expected
    return None


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
