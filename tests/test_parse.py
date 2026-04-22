"""Tests for grader.parse."""

import jsonschema.exceptions
import pytest

from nbgrader_jupyterquiz.grader.parse import (
    ParseError,
    Quiz,
    find_quiz_regions,
    line_to_mc_answer,
    line_to_numeric_answer,
    line_to_question,
    parse_cell,
    split_questions,
)


# ---------------------------------------------------------------------------
# find_quiz_regions
# ---------------------------------------------------------------------------


def test_find_quiz_regions_no_quiz():
    source = "Just some text.\nNo quiz here."
    quizzes, remaining = find_quiz_regions(source)
    assert quizzes == []
    assert remaining == ["Just some text.", "No quiz here."]


def test_find_quiz_regions_single():
    source = 'Before.\n#### Quiz\n* (SC) "Q?"\n  + "A"\n#### End Quiz\nAfter.'
    quizzes, remaining = find_quiz_regions(source)
    assert len(quizzes) == 1
    assert remaining == ["Before.", "After."]
    options, lines = quizzes[0]
    assert lines == ['* (SC) "Q?"', '  + "A"']


def test_find_quiz_regions_options_captured():
    """Text on the same line as the begin delimiter is returned as the options string."""
    source = '#### Quiz encoded=false hidden=false\n* (SC) "Q?"\n  + "A"\n#### End Quiz'
    quizzes, _ = find_quiz_regions(source)
    options, _ = quizzes[0]
    assert "encoded=false" in options
    assert "hidden=false" in options


def test_find_quiz_regions_multiple():
    source = '#### Quiz\n* (SC) "Q1?"\n  + "A"\n#### End Quiz\nMiddle text.\n#### Quiz\n* (SC) "Q2?"\n  + "B"\n#### End Quiz'
    quizzes, remaining = find_quiz_regions(source)
    assert len(quizzes) == 2
    assert "Middle text." in remaining


def test_find_quiz_regions_nested_raises():
    source = "#### Quiz\n#### Quiz\n#### End Quiz\n#### End Quiz"
    with pytest.raises(RuntimeError, match="nested"):
        find_quiz_regions(source)


def test_find_quiz_regions_end_without_begin_raises():
    source = "Some text.\n#### End Quiz"
    with pytest.raises(RuntimeError, match="without beginning"):
        find_quiz_regions(source)


def test_find_quiz_regions_unclosed_raises():
    source = '#### Quiz\n* (SC) "Q?"\n  + "A"'
    with pytest.raises(RuntimeError, match="end_quiz_delimiter"):
        find_quiz_regions(source)


# ---------------------------------------------------------------------------
# split_questions
# ---------------------------------------------------------------------------


def test_split_questions_single():
    lines = ['* (SC) "Q?"', '  + "A"', '  - "B"']
    result = split_questions(lines)
    assert result == [['* (SC) "Q?"', '  + "A"', '  - "B"']]


def test_split_questions_multiple():
    lines = [
        '* (SC) "Q1?"',
        '  + "A"',
        '* (SC) "Q2?"',
        '  - "B"',
        '  + "C"',
    ]
    result = split_questions(lines)
    assert len(result) == 2
    assert result[0] == ['* (SC) "Q1?"', '  + "A"']
    assert result[1] == ['* (SC) "Q2?"', '  - "B"', '  + "C"']


def test_split_questions_non_answer_lines_ignored():
    """Lines that are not answers (no leading +/-) are silently dropped."""
    lines = ['* (SC) "Q?"', "a comment", '  + "A"']
    result = split_questions(lines)
    assert result == [['* (SC) "Q?"', '  + "A"']]


def test_split_questions_empty():
    assert split_questions([]) == []


# ---------------------------------------------------------------------------
# line_to_question
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shorthand,expected_type",
    [
        ("SC", "multiple_choice"),
        ("MC", "many_choice"),
        ("NM", "numeric"),
    ],
)
def test_line_to_question_types(shorthand, expected_type):
    line = f'* ({shorthand}) "The question text?"'
    result = line_to_question(line)
    assert result["type"] == expected_type
    assert result["question"] == "The question text?"


def test_line_to_question_precision():
    result = line_to_question('* (NM) "What is pi?" [2]')
    assert result["precision"] == 2


def test_line_to_question_answer_cols():
    result = line_to_question('* (SC) "Pick one." <2>')
    assert result["answer_cols"] == 2


def test_line_to_question_malformed_raises():
    """A line with an unparsable segment raises ParseError."""
    with pytest.raises(ParseError):
        line_to_question("* (SC) unparsable garbage")


# ---------------------------------------------------------------------------
# line_to_mc_answer
# ---------------------------------------------------------------------------


def test_mc_answer_correct_flag():
    assert line_to_mc_answer('  + "Right"')["correct"] is True
    assert line_to_mc_answer('  - "Wrong"')["correct"] is False


def test_mc_answer_text():
    result = line_to_mc_answer('  + "Paris"')
    assert result["answer"] == "Paris"


def test_mc_answer_with_feedback():
    result = line_to_mc_answer('  + (Well done!) "Paris"')
    assert result["answer"] == "Paris"
    assert result["feedback"] == "Well done!"


def test_mc_answer_feedback_order_independent():
    """Feedback may appear before or after the answer text."""
    a = line_to_mc_answer('  + (feedback) "answer"')
    b = line_to_mc_answer('  + "answer" (feedback)')
    assert a["answer"] == b["answer"] == "answer"
    assert a["feedback"] == b["feedback"] == "feedback"


# ---------------------------------------------------------------------------
# line_to_numeric_answer
# ---------------------------------------------------------------------------


def test_numeric_answer_value():
    result = line_to_numeric_answer("  + <3.14>")
    assert result == {"correct": True, "value": 3.14, "type": "value"}


def test_numeric_answer_range():
    result = line_to_numeric_answer("  + [0.0, 10.0]")
    assert result == {"correct": True, "range": [0.0, 10.0], "type": "range"}


def test_numeric_answer_default():
    """An answer with only feedback and no value/range is a 'default' catch-all."""
    result = line_to_numeric_answer("  - (Not quite right.)")
    assert result["type"] == "default"
    assert result["feedback"] == "Not quite right."
    assert result["correct"] is False


def test_numeric_answer_value_with_feedback():
    result = line_to_numeric_answer("  - (Too small) <1.0>")
    assert result["correct"] is False
    assert result["feedback"] == "Too small"
    assert result["value"] == 1.0
    assert result["type"] == "value"


def test_numeric_answer_value_and_range_raises():
    with pytest.raises(ParseError, match="both value and range"):
        line_to_numeric_answer("  + <3.0> [0.0, 5.0]")


# ---------------------------------------------------------------------------
# parse_cell — end-to-end
# ---------------------------------------------------------------------------

CELL_NO_QUIZ = "Just a markdown cell.\n\nNo quiz here."

CELL_SINGLE_QUIZ = """\
Introductory text.

#### Quiz
* (SC) "What is 2 + 2?"
  + "4"
  - "3"
  - "5"
#### End Quiz

Concluding text."""

CELL_MULTIPLE_QUIZZES = """\
#### Quiz
* (SC) "First question?"
  + "Yes"
  - "No"
#### End Quiz

#### Quiz
* (NM) "What is the answer?" [0]
  + <42.0>
  - (Too bad.)
#### End Quiz"""


def test_parse_cell_no_quiz():
    quizzes, cell_contents = parse_cell(CELL_NO_QUIZ)
    assert quizzes == []
    assert cell_contents == CELL_NO_QUIZ.split("\n")


def test_parse_cell_single_quiz_structure():
    quizzes, cell_contents = parse_cell(CELL_SINGLE_QUIZ)
    assert len(quizzes) == 1
    assert isinstance(quizzes[0], Quiz)
    assert len(quizzes[0].questions) == 1
    q = quizzes[0].questions[0]
    assert q["type"] == "multiple_choice"
    assert q["question"] == "What is 2 + 2?"
    assert len(q["answers"]) == 3


def test_parse_cell_text_preserved():
    """Lines outside quiz delimiters are returned unchanged."""
    _, cell_contents = parse_cell(CELL_SINGLE_QUIZ)
    assert "Introductory text." in cell_contents
    assert "Concluding text." in cell_contents


def test_parse_cell_multiple_quizzes():
    quizzes, _ = parse_cell(CELL_MULTIPLE_QUIZZES)
    assert len(quizzes) == 2
    assert quizzes[0].questions[0]["type"] == "multiple_choice"
    assert quizzes[1].questions[0]["type"] == "numeric"


def test_parse_cell_empty_quiz_region_raises():
    source = "#### Quiz\n#### End Quiz"
    with pytest.raises(ParseError, match="without any parsable questions"):
        parse_cell(source)


def test_parse_cell_validation_error_propagates():
    """An answer missing its required 'answer' text fails schema validation."""
    # line_to_mc_answer parses this as {correct: True, feedback: "..."} —
    # the MC schema requires both 'answer' and 'correct', so validation fails.
    source = '#### Quiz\n* (SC) "A question?"\n  + (Feedback but no answer text)\n#### End Quiz'
    with pytest.raises(jsonschema.exceptions.ValidationError):
        parse_cell(source)


def test_parse_cell_sc_with_multiple_correct_raises():
    """SC declared with >1 correct answer is a hard parse error."""
    source = '#### Quiz\n* (SC) "Which are primes?"\n  + "2"\n  + "3"\n  - "4"\n#### End Quiz'
    with pytest.raises(ParseError, match="exactly one correct answer"):
        parse_cell(source)


def test_parse_cell_sc_with_zero_correct_raises():
    """SC declared with 0 correct answers is a hard parse error."""
    source = '#### Quiz\n* (SC) "Pick one."\n  - "A"\n  - "B"\n#### End Quiz'
    with pytest.raises(ParseError, match="exactly one correct answer"):
        parse_cell(source)


def test_parse_cell_mc_with_one_correct_warns(caplog):
    """MC declared with exactly 1 correct answer is allowed but warns."""
    import logging

    source = '#### Quiz\n* (MC) "Which is prime?"\n  + "2"\n  - "4"\n#### End Quiz'
    with caplog.at_level(logging.WARNING, logger="nbgrader_jupyterquiz.grader.parse"):
        quizzes, _ = parse_cell(source)
    assert quizzes[0].questions[0]["type"] == "many_choice"
    assert any("1 correct answer" in rec.message for rec in caplog.records)


def test_parse_cell_mc_with_zero_correct_warns(caplog):
    """MC declared with 0 correct answers is allowed but warns."""
    import logging

    source = '#### Quiz\n* (MC) "Which of these apply?"\n  - "A"\n  - "B"\n#### End Quiz'
    with caplog.at_level(logging.WARNING, logger="nbgrader_jupyterquiz.grader.parse"):
        quizzes, _ = parse_cell(source)
    assert quizzes[0].questions[0]["type"] == "many_choice"
    assert any("0 correct answer" in rec.message for rec in caplog.records)


def test_parse_cell_mc_with_multiple_correct_ok(caplog):
    """MC with 2+ correct answers is the happy path — no warning."""
    import logging

    source = '#### Quiz\n* (MC) "Which are primes?"\n  + "2"\n  + "3"\n  - "4"\n#### End Quiz'
    with caplog.at_level(logging.WARNING, logger="nbgrader_jupyterquiz.grader.parse"):
        quizzes, _ = parse_cell(source)
    assert quizzes[0].questions[0]["type"] == "many_choice"
    assert not any("correct answer" in rec.message for rec in caplog.records)


def test_parse_cell_sc_with_exactly_one_correct_ok():
    """SC with exactly 1 correct answer is the happy path."""
    source = '#### Quiz\n* (SC) "Capital of France?"\n  + "Paris"\n  - "London"\n#### End Quiz'
    quizzes, _ = parse_cell(source)
    assert quizzes[0].questions[0]["type"] == "multiple_choice"


# ---------------------------------------------------------------------------
# parse_quiz_options
# ---------------------------------------------------------------------------


def test_parse_quiz_options_empty_returns_defaults():
    from nbgrader_jupyterquiz.grader.parse import parse_quiz_options

    result = parse_quiz_options("")
    assert result == {
        "encoded": True,
        "inline": True,
        "hidden": True,
        "filename": None,
        "hide_correctness": None,
        "graded": None,
    }


def test_parse_quiz_options_graded_false():
    from nbgrader_jupyterquiz.grader.parse import parse_quiz_options

    assert parse_quiz_options("graded=false")["graded"] is False


def test_parse_quiz_options_graded_true():
    from nbgrader_jupyterquiz.grader.parse import parse_quiz_options

    assert parse_quiz_options("graded=true")["graded"] is True


def test_hide_correctness_propagates_to_mc_answers():
    from nbgrader_jupyterquiz.grader.parse import parse_cell

    source = '#### Quiz hide_correctness=true\n* (SC) "What is 2+2?"\n  + "4"\n  - "5"\n#### End Quiz'
    quizzes, _ = parse_cell(source)
    assert quizzes[0].options["hide_correctness"] is True
    for answer in quizzes[0].questions[0]["answers"]:
        assert answer.get("hide") is True


def test_hide_correctness_default_does_not_touch_answers():
    from nbgrader_jupyterquiz.grader.parse import parse_cell

    source = '#### Quiz\n* (SC) "What is 2+2?"\n  + "4"\n  - "5"\n#### End Quiz'
    quizzes, _ = parse_cell(source)
    assert quizzes[0].options["hide_correctness"] is None
    for answer in quizzes[0].questions[0]["answers"]:
        assert "hide" not in answer


def test_hide_correctness_skips_numeric_answers():
    from nbgrader_jupyterquiz.grader.parse import parse_cell

    source = '#### Quiz hide_correctness=true\n* (NM) "What is 2+2?"\n  + <4>\n#### End Quiz'
    quizzes, _ = parse_cell(source)
    # Numeric answers don't have hide semantics; the field should not be set.
    for answer in quizzes[0].questions[0]["answers"]:
        assert "hide" not in answer


def test_question_points_parsed_from_braces():
    from nbgrader_jupyterquiz.grader.parse import parse_cell

    source = '#### Quiz\n* (SC) {3} "Capital of France?"\n  + "Paris"\n  - "Berlin"\n* (NM) {5} "Pi to 2 decimals?"\n  + <3.14>\n#### End Quiz'
    quizzes, _ = parse_cell(source)
    assert quizzes[0].questions[0]["points"] == 3
    assert quizzes[0].questions[1]["points"] == 5


def test_question_points_unweighted_quiz_has_no_points_field():
    """
    When no question in a quiz carries a ``{N}`` marker, no ``points``
    field is set on any question (the quiz is unweighted and the display
    should render no badges).
    """
    from nbgrader_jupyterquiz.grader.parse import parse_cell

    source = '#### Quiz\n* (SC) "No points marker here"\n  + "Yes"\n  - "No"\n* (SC) "And none here"\n  + "Yes"\n  - "No"\n#### End Quiz'
    quizzes, _ = parse_cell(source)
    for q in quizzes[0].questions:
        assert "points" not in q


def test_question_points_propagate_default_to_siblings():
    """
    When any question in a quiz has an explicit ``{N}`` marker, every
    other question in the same quiz gets ``points: 1`` so the UI renders
    badges consistently on every question in the quiz.
    """
    from nbgrader_jupyterquiz.grader.parse import parse_cell

    source = '#### Quiz\n* (SC) {3} "Worth three"\n  + "A"\n  - "B"\n* (SC) "Default weight"\n  + "A"\n  - "B"\n#### End Quiz'
    quizzes, _ = parse_cell(source)
    assert quizzes[0].questions[0]["points"] == 3
    assert quizzes[0].questions[1]["points"] == 1


def test_question_points_fractional():
    """
    Fractional point values like {0.5} are preserved as floats; whole
    numbers stay as ints to keep the embedded JSON tidy.
    """
    from nbgrader_jupyterquiz.grader.parse import parse_cell

    source = '#### Quiz\n* (SC) {0.5} "Half point"\n  + "A"\n  - "B"\n* (SC) {2} "Two points"\n  + "A"\n  - "B"\n#### End Quiz'
    quizzes, _ = parse_cell(source)
    half = quizzes[0].questions[0]["points"]
    two = quizzes[0].questions[1]["points"]
    assert half == 0.5
    assert isinstance(half, float)
    assert two == 2
    assert isinstance(two, int)


def test_question_points_propagation_is_per_quiz_not_per_notebook():
    """
    Two quiz regions in one cell — propagation only affects the quiz
    that has an explicit marker; the unweighted quiz keeps no points.
    """
    from nbgrader_jupyterquiz.grader.parse import parse_cell

    source = (
        "#### Quiz\n"
        '* (SC) {5} "Region 0 — weighted"\n'
        '  + "A"\n'
        '  - "B"\n'
        '* (SC) "Region 0 — default 1"\n'
        '  + "A"\n'
        '  - "B"\n'
        "#### End Quiz\n"
        "#### Quiz\n"
        '* (SC) "Region 1 — unweighted"\n'
        '  + "A"\n'
        '  - "B"\n'
        "#### End Quiz"
    )
    quizzes, _ = parse_cell(source)
    # Region 0: weighted (propagation applies)
    assert quizzes[0].questions[0]["points"] == 5
    assert quizzes[0].questions[1]["points"] == 1
    # Region 1: unweighted (no propagation)
    assert "points" not in quizzes[1].questions[0]


def test_parse_quiz_options_key_value_pairs():
    from nbgrader_jupyterquiz.grader.parse import parse_quiz_options

    result = parse_quiz_options("encoded=false hidden=false")
    assert result["encoded"] is False
    assert result["hidden"] is False
    assert result["inline"] is True  # default preserved


def test_parse_quiz_options_filename():
    from nbgrader_jupyterquiz.grader.parse import parse_quiz_options

    result = parse_quiz_options("filename=quiz.json inline=false")
    assert result["filename"] == "quiz.json"
    assert result["inline"] is False


def test_parse_quiz_options_ignores_unknown_keys():
    from nbgrader_jupyterquiz.grader.parse import parse_quiz_options

    result = parse_quiz_options("unknown_key=value encoded=false")
    assert result["encoded"] is False


def test_parse_quiz_options_token_without_equals_ignored():
    from nbgrader_jupyterquiz.grader.parse import parse_quiz_options

    result = parse_quiz_options("bareword encoded=false")
    assert result["encoded"] is False


# ---------------------------------------------------------------------------
# parse_cell — custom delimiters
# ---------------------------------------------------------------------------


def test_parse_cell_custom_delimiters():
    source = '## START\n* (SC) "Q?"\n  + "A"\n  - "B"\n## END'
    quizzes, remaining = parse_cell(source, begin_quiz_delimiter="## START", end_quiz_delimiter="## END")
    assert len(quizzes) == 1
    assert remaining == []


def test_parse_cell_default_delimiter_ignored_when_custom_set():
    """Default '#### Quiz' delimiter not matched when custom delimiters are used."""
    source = '#### Quiz\n* (SC) "Q?"\n  + "A"\n#### End Quiz'
    quizzes, remaining = parse_cell(source, begin_quiz_delimiter="## START", end_quiz_delimiter="## END")
    assert quizzes == []
    assert "#### Quiz" in remaining
