"""
Per-question-type grading helpers for :mod:`~nbgrader_jupyterquiz.grader.autograde`.

Each ``grade_*`` function takes a parsed question dict plus the
student's recorded response payload and returns ``True`` iff the
response satisfies that question's correctness criteria.  Grading is
all-or-nothing per question — partial credit at the quiz level falls
out of summing per-question outcomes in
:class:`~nbgrader_jupyterquiz.grader.autograde.QuizResult`.

The numeric and string graders mirror the display JS
(``numeric.js`` / ``string.js``): answers are checked in source
order and the *first* matching answer decides correctness, so an
instructor can list a specific wrong answer (with feedback) ahead of
a broader correct range and have both the browser and the autograder
agree on the outcome.
"""

import math
import re
from decimal import ROUND_HALF_UP, Decimal
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
        True iff ``selected`` identifies a ``correct: true`` answer
        (see :func:`resolve_choice`).
    """
    if recorded.get("type") != "multiple_choice":
        return False
    idx = resolve_choice(question, recorded.get("selected"))
    return idx is not None and bool(question["answers"][idx].get("correct"))


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
        True iff every selected entry identifies an answer and the set
        of identified answers equals the set of correct answers.
    """
    if recorded.get("type") != "many_choice":
        return False
    selected = recorded.get("selected")
    if not isinstance(selected, list):
        return False
    picked = [resolve_choice(question, s) for s in selected]
    if any(idx is None for idx in picked):
        return False
    correct = {i for i, a in enumerate(question.get("answers", [])) if a.get("correct")}
    return set(picked) == correct


def picked_choices(question: dict[str, Any], recorded: Any) -> set[int]:
    """
    Return the indices of the answers a recorded choice response selects.

    Parameters
    ----------
    question : dict
        Single- or many-choice question dict.
    recorded : Any
        Raw recorded payload from the sidecar (may be malformed).

    Returns
    -------
    set of int
        Indices into ``question["answers"]``; entries that don't
        identify any answer are dropped.
    """
    if not isinstance(recorded, dict):
        return set()
    selected = recorded.get("selected")
    entries = selected if isinstance(selected, list) else [selected]
    return {idx for idx in (resolve_choice(question, s) for s in entries) if idx is not None}


def resolve_choice(question: dict[str, Any], selected: Any) -> int | None:
    r"""
    Map a recorded choice string to the index of the answer it denotes.

    The display JS records each answer's source text.  Responses
    recorded by nbgrader-jupyterquiz <= 0.5.0 instead carry the
    button's *rendered* text, which differs from the source when the
    answer contains ``$...$`` math (rewritten to ``\(...\)``),
    markdown links, spans multiple lines (whitespace collapsed), or
    carries a code block (its text is appended).  An exact match is
    tried first; failing that, the selection is compared against a
    reconstruction of each answer's rendered text.

    Parameters
    ----------
    question : dict
        Single- or many-choice question dict.
    selected : Any
        One recorded selection.

    Returns
    -------
    int or None
        Index into ``question["answers"]``, or ``None`` when
        ``selected`` is not a string or matches no answer.
    """
    if not isinstance(selected, str):
        return None
    answers = question.get("answers", [])
    for i, a in enumerate(answers):
        if a.get("answer") == selected:
            return i
    target = _collapse_whitespace(selected)
    for i, a in enumerate(answers):
        if target in _rendered_forms(a):
            return i
    return None


def _rendered_forms(answer: dict[str, Any]) -> set[str]:
    r"""
    Reconstruct the whitespace-normalised rendered text(s) of an answer button.

    Parameters
    ----------
    answer : dict
        One choice answer dict.

    Returns
    -------
    set of str
        Candidate ``innerText`` values of the answer's button, with and
        without the ``$`` → ``\(`` rewrite applied by the display JS.
    """
    text = str(answer.get("answer", ""))
    code = answer.get("code")
    forms = set()
    for base in (text, _jaxify(text)):
        forms.add(_collapse_whitespace(base))
        if code:
            forms.add(_collapse_whitespace(f"{base} {code}"))
    return forms


_DISPLAY_MATH = re.compile(r"([^\\]|^)(\$\$)")
_INLINE_MATH = re.compile(r"([^\\]|^)(\$)")
_MD_LINK = re.compile(r"\[(.*?)\]\((.*?)\)")
_AUTOLINK = re.compile(r"<http(.*?)>")


def _jaxify(text: str) -> str:
    r"""
    Apply the text rewrites of the display JS ``jaxify()`` helper.

    Parameters
    ----------
    text : str
        Answer source text.

    Returns
    -------
    str
        Text with unescaped ``$$`` / ``$`` delimiters replaced by
        ``\[`` ``\]`` / ``\(`` ``\)`` (alternating open / close)
        and markdown links reduced to their link text.
    """
    n_inline = n_display = 0
    while True:
        if _DISPLAY_MATH.search(text):
            delim = "\\]" if n_display % 2 else "\\["
            text = _DISPLAY_MATH.sub(lambda m, d=delim: m.group(1) + d, text, count=1)
            n_display += 1
        elif _INLINE_MATH.search(text):
            delim = "\\)" if n_inline % 2 else "\\("
            text = _INLINE_MATH.sub(lambda m, d=delim: m.group(1) + d, text, count=1)
            n_inline += 1
        else:
            break
    text = _AUTOLINK.sub(r"http\1", text)
    return _MD_LINK.sub(r"\1", text)


def _collapse_whitespace(text: str) -> str:
    """
    Collapse whitespace runs to single spaces and strip the ends.

    Parameters
    ----------
    text : str
        Text to normalise.

    Returns
    -------
    str
        Normalised text.
    """
    return " ".join(text.split())


def grade_numeric(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
    """
    Grade a numeric question (value or range, optional precision).

    Answers are checked in order and the first one whose ``value``
    (at the configured precision) or closed ``range`` contains the
    submission decides the outcome — mirroring ``check_numeric`` in
    ``numeric.js``.

    Parameters
    ----------
    question : dict
        Question dict with its answer list (values and/or ranges).
    recorded : dict
        Student's recorded response with a ``parsed`` numeric field.

    Returns
    -------
    bool
        True iff the first matching answer is marked ``correct``.
    """
    if recorded.get("type") != "numeric":
        return False
    parsed = recorded.get("parsed")
    if isinstance(parsed, bool) or not isinstance(parsed, (int, float)) or not math.isfinite(parsed):
        return False

    precision = question.get("precision")
    rounded = isinstance(precision, int) and not isinstance(precision, bool) and precision > 0
    if rounded:
        parsed = _round_to_precision(parsed, precision)
    for a in question.get("answers", []):
        if "value" in a:
            expected = float(a["value"])
            match = parsed == (_round_to_precision(expected, precision) if rounded else expected)
        elif "range" in a:
            lo, hi = a["range"]
            match = lo <= parsed <= hi
        else:
            continue  # ``default`` catch-all: feedback only
        if match:
            return bool(a.get("correct"))
    return False


def grade_string(question: dict[str, Any], recorded: dict[str, Any]) -> bool:
    """
    Grade a string question (exact or fuzzy match).

    Answers are checked in order and the first exact or fuzzy match
    decides the outcome — mirroring ``check_string`` in ``string.js``.

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
        True iff the first answer that ``value`` matches (honouring
        ``match_case`` and ``fuzzy_threshold`` using Levenshtein
        similarity) is marked ``correct``.
    """
    if recorded.get("type") != "string":
        return False
    value = recorded.get("value")
    if not isinstance(value, str):
        return False
    value = value.strip()
    for a in question.get("answers", []):
        if a.get("type") == "default":
            continue
        expected = str(a.get("answer", ""))
        submitted = value
        if not a.get("match_case"):
            submitted, expected = submitted.lower(), expected.lower()
        match = submitted == expected
        threshold = a.get("fuzzy_threshold")
        if not match and threshold:
            max_len = max(len(submitted), len(expected), 1)
            match = 1 - _levenshtein(submitted, expected) / max_len >= threshold
        if match:
            return bool(a.get("correct"))
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
            if "value" in a:
                expected.append(a["value"])
            elif "range" in a:
                expected.append(tuple(a["range"]))
        return expected
    return None


def _round_to_precision(x: float, precision: int) -> float:
    """
    Round a float to a given number of significant digits.

    Mirrors JavaScript's ``Number.prototype.toPrecision`` so numeric
    questions with a ``[N]`` precision marker score the same way the
    display JS evaluates them in the browser.  ``toPrecision`` rounds
    the exact binary value half away from zero (``(2.5).toPrecision(1)
    == "3"``), unlike Python's ``format`` which rounds half to even.

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
    if x == 0 or not math.isfinite(x):
        return float(x)
    exact = Decimal(x)
    quantum = Decimal(1).scaleb(exact.adjusted() - precision + 1)
    return float(exact.quantize(quantum, rounding=ROUND_HALF_UP))


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
