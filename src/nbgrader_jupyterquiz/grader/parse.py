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


def _open_delim(text: str) -> str | None:
    r"""
    Return the delimiter currently open at the end of ``text``, or ``None`` if balanced.

    Used by :func:`split_questions` to decide whether a multi-line
    field has been completed.  Recognises the same delimiters
    :func:`_scan_field` does: triple-backtick code blocks,
    same-character ``"..."`` (with ``\\`` and ``\"`` escapes), and
    paired ``(...)``, ``[...]``, ``{...}``, ``<...>`` with depth
    tracking on the field's own pair (other delimiter characters
    inside are inert).

    Parameters
    ----------
    text : str
        A buffer of accumulated quiz source — typically the
        ``\n``-joined physical lines of an in-progress logical line.

    Returns
    -------
    str or None
        The opening delimiter still awaiting its closer, or ``None``
        if the buffer is balanced.  Useful for both flow control and
        error messages.
    """
    pairs = {"(": ")", "[": "]", "{": "}", "<": ">"}
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("```", i):
            j = _skip_code_block(text, i)
            if j is None:
                return "```"
            i = j
        elif text[i] == '"':
            j = _skip_quoted(text, i)
            if j is None:
                return '"'
            i = j
        elif text[i] in pairs:
            j = _skip_paired(text, i, text[i], pairs[text[i]])
            if j is None:
                return text[i]
            i = j
        else:
            i += 1
    return None


def _skip_code_block(text: str, start: int) -> int | None:
    """
    Skip past a triple-backtick code block in :func:`_open_delim`.

    Parameters
    ----------
    text : str
        Buffer being scanned.
    start : int
        Index of the opening triple-backtick in ``text``.

    Returns
    -------
    int or None
        Index just past the closing triple-backtick, or ``None`` if
        the block is unterminated.
    """
    j = start + 3
    n = len(text)
    while j < n and not text.startswith("```", j):
        j += 1
    return None if j >= n else j + 3


def _skip_quoted(text: str, start: int) -> int | None:
    r"""
    Skip past a same-character ``"..."`` field in :func:`_open_delim`.

    Recognises ``\\`` and ``\"`` as escape sequences.

    Parameters
    ----------
    text : str
        Buffer being scanned.
    start : int
        Index of the opening ``"`` in ``text``.

    Returns
    -------
    int or None
        Index just past the closing ``"``, or ``None`` if the field
        is unterminated.
    """
    j = start + 1
    n = len(text)
    while j < n:
        if text[j] == "\\" and j + 1 < n and text[j + 1] in '\\"':
            j += 2
            continue
        if text[j] == '"':
            return j + 1
        j += 1
    return None


def _skip_paired(text: str, start: int, left: str, right: str) -> int | None:
    r"""
    Skip past a paired delimited field in :func:`_open_delim`.

    Tracks depth on the field's own ``left``/``right`` pair; other
    delimiter characters are inert.  Recognises ``\<left>``,
    ``\<right>``, and ``\\`` as escape sequences.

    Parameters
    ----------
    text : str
        Buffer being scanned.
    start : int
        Index of the opening ``left`` in ``text``.
    left : str
        Opening delimiter character.
    right : str
        Closing delimiter character.

    Returns
    -------
    int or None
        Index just past the matching closing delimiter, or ``None``
        if the field is unterminated.
    """
    depth = 1
    j = start + 1
    n = len(text)
    while j < n and depth > 0:
        if text[j] == "\\" and j + 1 < n and text[j + 1] in (left, right, "\\"):
            j += 2
            continue
        if text[j] == left:
            depth += 1
        elif text[j] == right:
            depth -= 1
        j += 1
    return None if depth > 0 else j


def split_questions(quiz_source: list[str]) -> list[list[str]]:
    r"""
    Split lines of a quiz region into individual question blocks.

    Each returned question is a list of *logical* lines — one for the
    question itself, followed by one per answer.  A logical line may
    span multiple physical source lines when its content extends
    across them, joined with ``\n``.  Continuation is driven by
    markdown-list indentation: a physical line is a continuation of
    the active logical line iff its first-non-whitespace column is
    strictly greater than the opener's column (``0`` for questions,
    ``2`` for answers).  Code blocks delimited by triple-backticks
    are an exception — physical lines inside an open code block are
    appended regardless of indentation, matching markdown's
    fenced-code semantics.

    Parameters
    ----------
    quiz_source : list[str]
        Physical lines within a quiz delimiter region.

    Returns
    -------
    list[list[str]]
        Each inner list contains the question logical line followed
        by its answer logical lines.  Each logical line is a single
        ``str`` (possibly containing ``\n``).

    Raises
    ------
    ParseError
        If a logical line ends with an unclosed delimited field —
        i.e. indentation drops back to the opener's level (or
        beyond) while the field is still expecting its closer.
    """
    questions: list[list[str]] = []
    current_question: list[str] | None = None
    current_logical: list[str] | None = None
    current_base_indent: int | None = None

    def flush_logical() -> None:
        """Close the active logical line, validating its delimiters."""
        nonlocal current_logical, current_base_indent
        if current_logical is None:
            return
        logical_text = "\n".join(current_logical)
        open_delim = _open_delim(logical_text)
        if open_delim is not None:
            raise ParseError(
                f"Unterminated {open_delim!r} delimiter in quiz logical line: {logical_text!r}",
            )
        # current_question must already exist if we reached here;
        # the opener handlers ensure that.
        if current_question is None:  # pragma: no cover
            raise ParseError("internal: flush_logical called without active question")
        current_question.append(logical_text)
        current_logical = None
        current_base_indent = None

    for line in quiz_source:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Inside a code block currently open in the active logical
        # buffer? — ignore indentation rules and append.
        if current_logical is not None:
            buffer_so_far = "\n".join(current_logical)
            if _open_delim(buffer_so_far) == "```":
                current_logical.append(line)
                continue

        # Pure-blank line: append to active logical if one exists,
        # otherwise drop.  A trailing blank is fine; a blank in the
        # middle of a multi-line field is preserved.
        if not stripped:
            if current_logical is not None:
                current_logical.append(line)
            continue

        # Question opener: `* ` at column 0.
        if indent == 0 and stripped.startswith("* "):
            flush_logical()
            if current_question is not None:
                questions.append(current_question)
            current_question = []
            current_logical = [line]
            current_base_indent = 0
            continue

        # Answer opener: `+` or `-` at column 2.
        if indent == 2 and (stripped.startswith("+") or stripped.startswith("-")) and current_question is not None:
            flush_logical()
            current_logical = [line]
            current_base_indent = 2
            continue

        # Continuation of the active logical line: indented strictly
        # deeper than the opener.
        if current_logical is not None and current_base_indent is not None and indent > current_base_indent:
            current_logical.append(line)
            continue

        # Otherwise: outside content (e.g. comment between quizzes).
        # Close any active logical and ignore.
        flush_logical()

    flush_logical()
    if current_question is not None:
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


def _scan_field(s: str, left: str, right: str) -> tuple[str, str]:
    r"""
    Extract a delimited field's content from ``s``, returning the content and remainder.

    The string ``s`` must start with ``left``.  Walks forward to find the
    matching closing delimiter and returns the captured inner content plus
    whatever remains after the closing delimiter.

    The exact tokenisation rule depends on the delimiters:

    - **Paired delimiters** (``left != right``, e.g. ``"("`` / ``")"``)
      track depth on the field's *own* pair only.  A nested ``left``
      increments depth; a ``right`` at depth 0 closes the field.
      Other delimiter characters inside (``{``, ``[``, ``"``, etc.) are
      inert text.  This lets ``(Correct (with caveats))`` parse as one
      feedback field with content ``Correct (with caveats)``, and
      ``(feedback { )`` parse as ``feedback { `` (the unmatched ``{``
      is just content).

    - **Same-character delimiters** (``left == right``, e.g. ``"\""`` /
      ``"\""``) recognise backslash escapes: ``\\`` is a literal ``\``,
      and ``\<right>`` is a literal of the closing delimiter character.
      Other backslash sequences (``\int``, ``\alpha``, etc.) pass
      through unchanged so LaTeX content survives.

    - **Multi-character delimiters** (e.g. triple-backtick ``"```"``)
      are treated like same-character delimiters but without escape
      support — the scanner walks character-by-character looking for
      the literal closing sequence.  ``"``, ``(``, ``)``, ``\``, etc.
      inside are all inert.  This matches markdown's fenced-code
      semantics.

    Parameters
    ----------
    s : str
        Input string starting with ``left``.
    left : str
        Opening delimiter.  May be one or more characters.
    right : str
        Closing delimiter.  May be one or more characters.

    Returns
    -------
    extracted : str
        The content between the opening and closing delimiters
        (exclusive on both sides), with escapes resolved.
    remainder : str
        Whatever follows the closing delimiter in ``s``.

    Raises
    ------
    ParseError
        If the closing delimiter is never found.
    """
    if not s.startswith(left):
        raise ParseError(f"_scan_field called on string not starting with {left!r}: {s!r}")

    i = len(left)
    n = len(s)
    paired = left != right and len(left) == 1 and len(right) == 1
    same_char_single = left == right and len(left) == 1
    depth = 1  # opening `left` already consumed
    out_chars: list[str] = []

    while i < n:
        ch = s[i]

        # Single-char delimiters honour backslash escapes.  ``\<right>``
        # and ``\\`` are unescaped; ``\<left>`` is also unescaped on
        # paired delimiters so an unmatched ``(`` (e.g. an emoticon
        # ``:(`` inside feedback) can be written as ``\(``.  Any other
        # ``\X`` passes through unchanged so LaTeX commands (``\int``,
        # ``\alpha``) survive.
        if (paired or same_char_single) and ch == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == right or nxt == "\\" or (paired and nxt == left):
                out_chars.append(nxt)
                i += 2
                continue
            # fall through: literal backslash, then handle nxt next iteration

        # Paired delimiters: track depth on `left`/`right`.
        if paired:
            if ch == left:
                depth += 1
                out_chars.append(ch)
                i += 1
                continue
            if ch == right:
                depth -= 1
                if depth == 0:
                    return "".join(out_chars), s[i + 1 :]
                out_chars.append(ch)
                i += 1
                continue
            out_chars.append(ch)
            i += 1
            continue

        # Multi-character or same-character delimiters: look for the
        # literal closing sequence at the current position.
        if s.startswith(right, i):
            return "".join(out_chars), s[i + len(right) :]

        out_chars.append(ch)
        i += 1

    raise ParseError(f"Unterminated field: missing closing {right!r} after {left!r}: {s!r}")


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
        If a duplicate component is found, the line ends with an
        unparsable segment, or a delimited field is not closed.
    """
    parsed = {}

    while line:
        line = line.strip()
        if not line:
            break
        for component, (left, right, typecast) in components.items():
            if line.startswith(left):
                if component in parsed:
                    raise ParseError(f"Duplicate component {component} found.")
                extracted, line = _scan_field(line, left, right)
                parsed[component] = typecast(extracted)
                break
        else:
            raise ParseError(f"Non-parsable component found. Left to parse: {line!r}")

    return parsed


def _normalise_code_block(code: str) -> str:
    r"""
    Normalise a captured code-block string for downstream display.

    Two transformations are applied:

    - Literal ``\n`` (the two-character sequence backslash + ``n``) is
      replaced with a real newline.  This preserves the v0.4.x
      authoring convention of writing single-line code blocks with
      embedded ``\n`` markers.
    - Leading and trailing newline whitespace is stripped.  Multi-line
      fenced code (`` \`\`\` ``-on-its-own-line opening / closing)
      naturally surrounds its content with newlines; users expect
      those to vanish, matching markdown's fenced-code semantics.

    Parameters
    ----------
    code : str
        Raw captured content from the ``\`\`\`...\`\`\``` field.

    Returns
    -------
    str
        Normalised code suitable for display.
    """
    return code.replace(r"\n", "\n").strip("\n")


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
        "code": ("```", "```", _normalise_code_block),
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
        "code": ("```", "```", _normalise_code_block),
    }

    answer |= parse_line(line, **components)
    return answer
