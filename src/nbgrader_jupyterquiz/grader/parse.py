"""Parse quiz question source from notebook cell markdown."""

import copy
import dataclasses
from typing import Any

import jsonschema.exceptions

from nbgrader_jupyterquiz.grader import validate


class ParseError(Exception):
    """Raised when quiz source cannot be parsed."""


@dataclasses.dataclass
class Quiz:
    """
    A parsed quiz with options, a list of question dicts, and parse-time warnings.

    ``warnings`` collects non-fatal issues the parser spotted (e.g. an
    ``MC`` question with 0 or 1 correct answers).  Fatal issues raise
    :class:`ParseError` instead.  Callers such as the ``CreateQuiz``
    preprocessor surface these through ``nbgrader``'s UI logger.
    """

    options: dict[str, Any]
    questions: list[dict[str, Any]]
    warnings: list[str] = dataclasses.field(default_factory=list)


def parse_cell(
    source: str,
    begin_quiz_delimiter: str = "#### Quiz",
    end_quiz_delimiter: str = "#### End Quiz",
) -> tuple[list[Quiz], list[str]]:
    """
    Parse quiz regions from a notebook cell source string.

    Parameters
    ----------
    source : str
        Full source text of the markdown cell.
    begin_quiz_delimiter : str, optional
        Marker that opens a quiz region.
    end_quiz_delimiter : str, optional
        Marker that closes a quiz region.

    Returns
    -------
    quizzes : list[Quiz]
        Parsed Quiz objects.  Non-fatal parse-time warnings are
        attached to each quiz's ``warnings`` field.
    cell_contents : list[str]
        Remaining cell lines with quiz regions removed.
    """
    quizzes_lines, cell_contents = find_quiz_regions(source, begin_quiz_delimiter, end_quiz_delimiter)

    quizzes = []
    for header, quiz_lines in quizzes_lines:
        quiz_options = parse_quiz_options(header)
        question_lines = split_questions(quiz_lines)
        questions = []
        warnings: list[str] = []

        for lines in question_lines:
            question = parse_question(lines)

            # Propagate the quiz-level hide_correctness option onto the
            # question tree.  MC / many-choice answers consume ``hide``
            # per-answer (see multiple_choice.js ``check_mc``); numeric
            # consumes ``hide`` per-question (see numeric.js
            # ``check_numeric``).
            if quiz_options.get("hide_correctness"):
                if question["type"] in ("multiple_choice", "many_choice"):
                    for answer in question["answers"]:
                        answer.setdefault("hide", True)
                elif question["type"] == "numeric":
                    question.setdefault("hide", True)

            try:
                validate.validate_question(question)
            except jsonschema.exceptions.ValidationError:
                raise

            if warning := _check_choice_cardinality(question):
                warnings.append(warning)

            questions.append(question)

        if not questions:
            raise ParseError("Quiz region without any parsable questions found.")

        # If any question in this quiz carries an explicit ``points`` value
        # (``{N}`` marker), set the default ``points: 1`` on every other
        # question so the rendered quiz displays a badge on every question
        # consistently.  When no question has explicit points, leave the
        # field unset — the quiz is unweighted and the display stays clean.
        if any("points" in q for q in questions):
            for q in questions:
                q.setdefault("points", 1)

        quizzes.append(Quiz(quiz_options, questions, warnings))

    return quizzes, cell_contents


def _check_choice_cardinality(question: dict[str, Any]) -> str | None:
    """
    Enforce SC/MC correct-answer counts declared by the instructor.

    Single-choice (``SC`` → ``multiple_choice``) must have exactly one
    correct answer — raises :class:`ParseError` otherwise.  Many-choice
    (``MC`` → ``many_choice``) may have any count, but 0 or 1 correct
    answers return a warning string since the instructor likely meant
    ``SC`` (for exactly 1) or a numeric/string question (for 0).

    Parameters
    ----------
    question : dict
        Parsed question dict (already schema-validated).  Non-choice
        types are silently ignored.

    Returns
    -------
    str or None
        A warning message for the caller to surface, or ``None`` when
        the question is fine (or unhandled).
    """
    if question.get("type") not in ("multiple_choice", "many_choice"):
        return None
    n_correct = sum(1 for a in question.get("answers", []) if a.get("correct"))
    qtext = question.get("question", "")
    if question["type"] == "multiple_choice" and n_correct != 1:
        raise ParseError(
            f"Single-choice (SC) question must have exactly one correct answer, found {n_correct}: {qtext!r}. Use (MC) for multi-answer questions.",
        )
    if question["type"] == "many_choice" and n_correct <= 1:
        return f"Many-choice (MC) question has {n_correct} correct answer(s): {qtext!r}. Consider (SC) for single-answer questions."
    return None


def redact_answer_key(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Return a deep copy of ``questions`` with answer-key fields stripped.

    The release notebook embeds question JSON into a hidden span the
    student's browser loads.  Without redaction, the student can read
    the answer key out of the DOM.  Stripping the matching fields makes
    ``hide_correctness`` mode actually withhold the key, not just the
    visual feedback.

    The redaction is keyed off question ``type``:

    - ``multiple_choice`` / ``many_choice``: drop ``correct`` from each
      answer.  Keep ``answer``, ``code``, ``feedback``, ``hide``.
    - ``numeric``: drop ``value``, ``range``, ``correct`` from each
      answer.  Keep ``feedback`` and ``type=default`` entries so
      fall-through "Incorrect, try again" feedback still works.
    - ``string``: replace ``answers`` with an empty list.  String
      questions are server-graded; the JS path only runs in self-check
      mode (no hide-correctness), so an empty list is sufficient when
      this function is called.

    Per-answer ``feedback`` strings are intentionally preserved — they
    are pedagogically valuable, and instructors who want them hidden
    can omit them from the question source.

    Parameters
    ----------
    questions : list[dict]
        The full parsed-question list (typically ``Quiz.questions``).
        Not mutated.

    Returns
    -------
    list[dict]
        Deep copy of ``questions`` with answer-key fields removed.
        Safe to serialise into the release notebook's display JSON.
    """
    redacted = copy.deepcopy(questions)
    for question in redacted:
        qtype = question.get("type")
        if qtype in ("multiple_choice", "many_choice"):
            for answer in question.get("answers", []):
                answer.pop("correct", None)
        elif qtype == "numeric":
            for answer in question.get("answers", []):
                answer.pop("value", None)
                answer.pop("range", None)
                answer.pop("correct", None)
                # The ``type`` field tags the parser's match style
                # ("value" / "range" / "default"); stripping the matching
                # fields above leaves any non-default tag dangling and
                # leaks "there was a value match here".  Only the
                # ``default`` tag is consumed by numeric.js.
                if answer.get("type") != "default":
                    answer.pop("type", None)
        elif qtype == "string":
            question["answers"] = []
    return redacted


def find_quiz_regions(
    source: str,
    begin_quiz_delimiter: str = "#### Quiz",
    end_quiz_delimiter: str = "#### End Quiz",
) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """
    Extract regions within quiz delimiters.

    Parameters
    ----------
    source : str
        Full source text of the markdown cell.
    begin_quiz_delimiter : str, optional
        Marker that opens a quiz region.
    end_quiz_delimiter : str, optional
        Marker that closes a quiz region.

    Returns
    -------
    quizzes : list[tuple[str, list[str]]]
        Each entry is ``(options_header, quiz_lines)``.
    remaining_lines : list[str]
        Lines that fall outside any quiz region.
    """
    quizzes: list[tuple[str, list[str]]] = []
    remaining_lines: list[str] = []
    quiz_options = ""
    quiz_lines: list[str] = []
    in_quiz_region = False

    for line in source.split("\n"):
        if line.strip().startswith(begin_quiz_delimiter):
            if in_quiz_region:
                raise RuntimeError("Encountered nested quiz delimiters")
            in_quiz_region = True
            quiz_options = line.strip().removeprefix(begin_quiz_delimiter)
            quiz_lines = []

        elif line.strip().startswith(end_quiz_delimiter):
            if not in_quiz_region:
                raise RuntimeError("Encountered quiz end without beginning")
            in_quiz_region = False
            quizzes.append((quiz_options, quiz_lines))

        elif in_quiz_region:
            quiz_lines.append(line)

        else:
            remaining_lines.append(line)

    if in_quiz_region:
        raise RuntimeError(f"Cell ended without {end_quiz_delimiter = }")

    return quizzes, remaining_lines


def split_questions(quiz_source: list[str]) -> list[list[str]]:
    """
    Split lines of a quiz region into individual question blocks.

    Parameters
    ----------
    quiz_source : list[str]
        Lines within a quiz delimiter region.

    Returns
    -------
    list[list[str]]
        Each inner list contains the question line followed by its answer lines.
    """
    questions = []
    current_question: list[str] = []

    for line in quiz_source:
        if line.startswith("* "):
            if current_question:
                questions.append(current_question)
            current_question = [line]
        elif current_question:
            if line.startswith("  +") or line.startswith("  -"):
                current_question.append(line)
        # else: comment or blank line — ignore

    if current_question:
        questions.append(current_question)

    return questions


def parse_quiz_options(header: str) -> dict[str, Any]:
    """
    Parse quiz options from the header line following the begin delimiter.

    Parameters
    ----------
    header : str
        Text on the same line as the begin delimiter, after the delimiter itself.
        Expected format: space-separated ``key=value`` pairs.
        Boolean values are ``true`` or ``false`` (case-insensitive).
        ``filename`` takes a string value.
        Unrecognised keys are ignored.

    Returns
    -------
    dict
        Quiz options dict with keys ``encoded``, ``inline``, ``hidden``,
        ``filename``, ``hide_correctness``, ``graded``.  Omitted keys
        retain their defaults.

        - ``hide_correctness=true`` propagates ``hide: true`` to every
          MC / many-choice answer so the display hides correctness
          feedback and shows a neutral Selected / Deselected state
          instead.  Default ``None`` — the preprocessor treats ``None``
          as "off unless the host cell is graded" and ``True``/``False``
          as explicit opt-in/opt-out.
        - ``graded=false`` opts a single quiz out of auto-grading
          inside a task cell — the generated cell is a plain
          ``display_quiz(...)`` code cell with no nbgrader metadata,
          no hidden tests, and correctness feedback visible.  Default
          ``None`` — the preprocessor treats ``None`` as "graded iff
          the host task cell has a ``grade_id`` and
          ``auto_generate_tests`` is on".
    """
    result: dict[str, Any] = {
        "encoded": True,
        "inline": True,
        "hidden": True,
        "filename": None,
        "hide_correctness": None,
        "graded": None,
    }
    for token in header.split():
        if "=" not in token:
            continue
        key, _, val = token.partition("=")
        if key == "filename":
            result["filename"] = val
        elif val.lower() == "true":
            result[key] = True
        elif val.lower() == "false":
            result[key] = False
    return result


def parse_question(lines: list[str]) -> dict[str, Any]:
    """
    Parse a question block into a question dict.

    Parameters
    ----------
    lines : list[str]
        First line is the question line; remaining lines are answer lines.

    Returns
    -------
    dict
        Question dict matching the jupyterquiz schema.
    """
    question = line_to_question(lines[0])

    if question["type"] == "numeric":
        line_to_answer = line_to_numeric_answer
    else:
        line_to_answer = line_to_mc_answer

    question["answers"] = [line_to_answer(line) for line in lines[1:]]
    return question


def parse_line(line: str, **components: tuple[str, str, Any]) -> dict[str, Any]:
    r"""
    Parse delimited components from a line and typecast them.

    Parameters
    ----------
    line : str
        Text to parse.
    \*\*components : tuple[str, str, Any]
        Each keyword is a component name mapped to a
        ``(left_delim, right_delim, typecast)`` triple.

    Returns
    -------
    dict
        Parsed components.

    Raises
    ------
    ParseError
        If a duplicate component is found or an unparsable segment remains.
    """
    parsed = {}

    while line:
        line = line.strip()
        for component, (left, right, typecast) in components.items():
            if line.startswith(left):
                if component in parsed:
                    raise ParseError(f"Duplicate component {component} found.")
                extracted, line = line.removeprefix(left).split(sep=right, maxsplit=1)
                parsed[component] = typecast(extracted)
                break
        else:
            raise ParseError(f"Non-parsable component found. Left to parse: {line!r}")

    return parsed


def line_to_question(line: str) -> dict[str, Any]:
    """
    Parse a question line into a partial question dict (without answers).

    Parameters
    ----------
    line : str
        Question line starting with ``*``.

    Returns
    -------
    dict
        Partial question dict with ``type``, ``question``, and optional fields.
    """
    question_types = {"NM": "numeric", "SC": "multiple_choice", "MC": "many_choice"}

    def _parse_points(raw: str) -> int | float:
        """
        Parse a ``{N}`` points marker, preserving integers when possible.

        Parameters
        ----------
        raw : str
            Contents between the ``{`` and ``}`` delimiters.

        Returns
        -------
        int or float
            ``int`` for whole-number markers (``{3}``); ``float`` for
            fractional markers (``{0.5}``).
        """
        value = float(raw)
        return int(value) if value.is_integer() else value

    components = {
        "type": ("(", ")", lambda t: question_types.get(t)),
        "question": ('"', '"', str),
        "code": ("```", "```", lambda code: code.replace(r"\n", "\n")),
        "precision": ("[", "]", int),
        "answer_cols": ("<", ">", int),
        "points": ("{", "}", _parse_points),
    }

    return parse_line(line.lstrip(" *"), **components)


def line_to_numeric_answer(line: str) -> dict[str, Any]:
    """
    Parse a numeric answer line.

    Parameters
    ----------
    line : str
        Answer line starting with ``+`` (correct) or ``-`` (incorrect).

    Returns
    -------
    dict
        Answer dict with ``correct``, ``type``, and value/range/feedback.
    """
    line = line.strip()
    answer: dict[str, Any] = {"correct": line.startswith("+")}
    line = line.lstrip("-+ ")

    components = {
        "feedback": ("(", ")", str),
        "value": ("<", ">", float),
        "range": ("[", "]", lambda r: list(map(float, r.split(",", maxsplit=1)))),
    }

    answer |= parse_line(line, **components)

    if "value" in answer and "range" in answer:
        raise ParseError(f"Answer to numeric question has both value and range: {line!r}")
    elif "value" in answer:
        answer["type"] = "value"
    elif "range" in answer:
        answer["type"] = "range"
    else:
        answer["type"] = "default"

    return answer


def line_to_mc_answer(line: str) -> dict[str, Any]:
    """
    Parse a multiple/many-choice answer line.

    Parameters
    ----------
    line : str
        Answer line starting with ``+`` (correct) or ``-`` (incorrect).

    Returns
    -------
    dict
        Answer dict with ``correct``, ``answer``, and optional fields.
    """
    line = line.lstrip()
    answer: dict[str, Any] = {"correct": line.startswith("+")}
    line = line.lstrip("-+ ")

    components = {
        "feedback": ("(", ")", str),
        "answer": ('"', '"', str),
        "code": ("```", "```", lambda code: code.replace(r"\n", "\n")),
    }

    answer |= parse_line(line, **components)
    return answer
