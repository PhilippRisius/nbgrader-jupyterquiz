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
    idx = resolve_choice(question, recorded.get("selected"), recorded.get("selected_index"))
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
    picked = [resolve_choice(question, s, i) for s, i in zip(selected, _indices(recorded, len(selected)), strict=True)]
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
    picked = (resolve_choice(question, s, i) for s, i in zip(entries, _indices(recorded, len(entries)), strict=True))
    return {idx for idx in picked if idx is not None}


def _indices(recorded: dict[str, Any], count: int) -> list[Any]:
    """
    Return the recorded answer indices aligned with the ``selected`` entries.

    Parameters
    ----------
    recorded : dict
        Recorded choice payload.
    count : int
        Number of ``selected`` entries.

    Returns
    -------
    list
        ``selected_index`` (single choice) or ``selected_indices``
        (many choice) as a list of length ``count``, padded with
        ``None`` when absent or malformed (sidecars written by
        nbgrader-jupyterquiz <= 0.5.0 carry no indices).
    """
    raw = recorded.get("selected_indices", [recorded.get("selected_index")])
    if not isinstance(raw, list) or len(raw) != count:
        return [None] * count
    return raw


def resolve_choice(question: dict[str, Any], selected: Any, index: Any = None) -> int | None:
    r"""
    Map a recorded choice to the index of the answer it denotes.

    The display JS records each answer's source text and its position
    in the source answer list.  The position is used when it agrees
    with the text; it disambiguates answers whose text is identical
    (e.g. code-only answers written as ``"" ```code``` ``).

    Responses recorded by nbgrader-jupyterquiz <= 0.5.0 carry no
    position and the button's *rendered* text, which differs from the
    source when the answer contains ``$...$`` math (rewritten to
    ``\(...\)``), markdown links, spans multiple lines (whitespace
    collapsed), or carries a code block (its text is appended).  For
    those, an exact source match is tried first; failing that, the
    selection is compared against a reconstruction of each answer's
    rendered text.  A selection matching more than one answer is
    ambiguous and resolves to ``None``.

    Parameters
    ----------
    question : dict
        Single- or many-choice question dict.
    selected : Any
        One recorded selection text.
    index : Any, optional
        Recorded position of the selection in the source answer list.

    Returns
    -------
    int or None
        Index into ``question["answers"]``, or ``None`` when
        ``selected`` is not a string or does not identify exactly one
        answer.
    """
    if not isinstance(selected, str):
        return None
    answers = question.get("answers", [])
    if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(answers) and answers[index].get("answer") == selected:
        return index
    exact = [i for i, a in enumerate(answers) if a.get("answer") == selected]
    if exact:
        return exact[0] if len(exact) == 1 else None
    target = _collapse_whitespace(selected)
    rendered = [i for i, a in enumerate(answers) if target in _rendered_forms(a)]
    return rendered[0] if len(rendered) == 1 else None


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
    forms: set[str] = set()
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
            text = _sub_first(_DISPLAY_MATH, text, "\\]" if n_display % 2 else "\\[")
            n_display += 1
        elif _INLINE_MATH.search(text):
            text = _sub_first(_INLINE_MATH, text, "\\)" if n_inline % 2 else "\\(")
            n_inline += 1
        else:
            break
    text = _AUTOLINK.sub(r"http\1", text)
    return _MD_LINK.sub(r"\1", text)


def _sub_first(pattern: re.Pattern[str], text: str, delim: str) -> str:
    r"""
    Replace the first ``$`` / ``$$`` delimiter matched by ``pattern`` with ``delim``.

    Parameters
    ----------
    pattern : re.Pattern
        ``_DISPLAY_MATH`` or ``_INLINE_MATH``; group 1 is the character
        preceding the delimiter (kept).
    text : str
        Text to rewrite.
    delim : str
        Replacement, e.g. ``\(``.

    Returns
    -------
    str
        ``text`` with its first match replaced.
    """
    return pattern.sub(lambda m: m.group(1) + delim, text, count=1)


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
    parsed = _as_number(recorded.get("parsed"))
    if parsed is None:
        return False

    # JS reads ``data-precision`` as a number and ``toPrecision``
    # truncates it, so a hand-written ``3.0`` behaves like ``3``.
    raw_precision = _as_number(question.get("precision"))
    precision = int(raw_precision) if raw_precision is not None and raw_precision >= 1 else 0
    if precision:
        parsed = _round_to_precision(parsed, precision)
    for a in question.get("answers", []):
        if "value" in a:
            expected = _as_number(a["value"])
            if expected is None:
                continue
            match = parsed == (_round_to_precision(expected, precision) if precision else expected)
        elif "range" in a:
            bounds = a["range"] if isinstance(a["range"], (list, tuple)) and len(a["range"]) == 2 else (None, None)
            lo, hi = (_as_number(b) for b in bounds)
            if lo is None or hi is None:
                continue
            match = lo <= parsed <= hi
        else:
            continue  # ``default`` catch-all: feedback only
        if match:
            return bool(a.get("correct"))
    return False


def _as_number(value: Any) -> float | None:
    """
    Coerce a JSON number to a finite float.

    Parameters
    ----------
    value : Any
        Candidate number from the answer key or the sidecar.

    Returns
    -------
    float or None
        The value as a finite ``float``; ``None`` for booleans,
        non-numbers, NaN, infinities, and integers too large for a
        float.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


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
    if x == 0 or not math.isfinite(x) or precision >= 17:
        # 17 significant digits identify every double uniquely, so
        # ``Number(x.toPrecision(p))`` is ``x`` itself for p >= 17.
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
