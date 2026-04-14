"""Parse quiz question source from notebook cell markdown."""

import dataclasses
from typing import Any

import jsonschema.exceptions

from nbgrader_jupyterquiz.grader import validate


class ParseError(Exception):
    """Raised when quiz source cannot be parsed."""


@dataclasses.dataclass
class Quiz:
    """A parsed quiz with options and a list of question dicts."""

    options: dict[str, Any]
    questions: list[dict[str, Any]]


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
        Parsed Quiz objects.
    cell_contents : list[str]
        Remaining cell lines with quiz regions removed.
    """
    quizzes_lines, cell_contents = find_quiz_regions(source, begin_quiz_delimiter, end_quiz_delimiter)

    quizzes = []
    for header, quiz_lines in quizzes_lines:
        quiz_options = parse_quiz_options(header)
        question_lines = split_questions(quiz_lines)
        questions = []

        for lines in question_lines:
            question = parse_question(lines)
            try:
                validate.validate_question(question)
            except jsonschema.exceptions.ValidationError:
                raise

            questions.append(question)

        if not questions:
            raise ParseError("Quiz region without any parsable questions found.")

        quizzes.append(Quiz(quiz_options, questions))

    return quizzes, cell_contents


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

    Returns
    -------
    dict
        Quiz options dict.
    """
    # TODO: Actually parse quiz options from the header line.
    return {
        "encoded": True,
        "inline": True,
        "hidden": True,
        "filename": None,
    }


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

    components = {
        "type": ("(", ")", lambda t: question_types.get(t)),
        "question": ('"', '"', str),
        "code": ("```", "```", lambda code: code.replace(r"\n", "\n")),
        "precision": ("[", "]", int),
        "answer_cols": ("<", ">", int),
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
