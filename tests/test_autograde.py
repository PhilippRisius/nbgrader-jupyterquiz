"""Tests for grader.autograde and its _scoring / _review submodules."""

import json

import nbformat
import nbformat.v4 as v4
import pytest

from nbgrader_jupyterquiz import grade_quiz
from nbgrader_jupyterquiz.grader._review import fmt_pts, render_review_html
from nbgrader_jupyterquiz.grader._scoring import (
    _levenshtein,
    _round_to_precision,
    expected_answer,
    grade_many_choice,
    grade_multiple_choice,
    grade_numeric,
    grade_string,
)
from nbgrader_jupyterquiz.grader.autograde import (
    SUPPORTED_SCHEMA_VERSIONS,
    GradeQuizError,
    QuestionResult,
    QuizResult,
)


# ---------------------------------------------------------------------------
# Fixtures: minimal question dicts + sidecar helpers
# ---------------------------------------------------------------------------


def q_sc(answer="Paris", points=None):
    """Single-choice question with ``answer`` correct among three options."""
    q = {
        "type": "multiple_choice",
        "question": "Capital of France?",
        "answers": [
            {"correct": True, "answer": answer},
            {"correct": False, "answer": "Berlin"},
            {"correct": False, "answer": "Madrid"},
        ],
    }
    if points is not None:
        q["points"] = points
    return q


def q_mc():
    return {
        "type": "many_choice",
        "question": "Python built-ins?",
        "answers": [
            {"correct": True, "answer": "list"},
            {"correct": True, "answer": "dict"},
            {"correct": False, "answer": "vector"},
        ],
    }


def q_nm_value(value=4.0, precision=None, points=None):
    q = {
        "type": "numeric",
        "question": "2+2?",
        "answers": [{"correct": True, "type": "value", "value": value}],
    }
    if precision is not None:
        q["precision"] = precision
    if points is not None:
        q["points"] = points
    return q


def q_nm_range(lo=0, hi=10):
    return {
        "type": "numeric",
        "question": "Pick a value in range.",
        "answers": [{"correct": True, "type": "range", "range": [lo, hi]}],
    }


def q_string(answer="hello", *, match_case=False, fuzzy=None):
    a = {"correct": True, "answer": answer, "match_case": match_case}
    if fuzzy is not None:
        a["fuzzy_threshold"] = fuzzy
    return {
        "type": "string",
        "question": "Say hello.",
        "answers": [a],
    }


@pytest.fixture
def cwd(tmp_path, monkeypatch):
    """Temp dir as CWD; cleaned up after the test."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_sidecar(cwd, grade_id, qnum_to_payload, *, schema_version=1):
    (cwd / "responses.json").write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "responses": {grade_id: {str(k): v for k, v in qnum_to_payload.items()}},
            }
        )
    )


# ---------------------------------------------------------------------------
# _scoring — per-type grading
# ---------------------------------------------------------------------------


class TestGradeMultipleChoice:
    def test_correct_pick_returns_true(self):
        assert grade_multiple_choice(q_sc(), {"type": "multiple_choice", "selected": "Paris"})

    def test_wrong_pick_returns_false(self):
        assert not grade_multiple_choice(q_sc(), {"type": "multiple_choice", "selected": "Berlin"})

    def test_wrong_payload_type_returns_false(self):
        assert not grade_multiple_choice(q_sc(), {"type": "many_choice", "selected": ["Paris"]})

    def test_null_selected_returns_false(self):
        assert not grade_multiple_choice(q_sc(), {"type": "multiple_choice", "selected": None})


class TestGradeManyChoice:
    def test_exact_match_returns_true(self):
        assert grade_many_choice(q_mc(), {"type": "many_choice", "selected": ["list", "dict"]})

    def test_subset_returns_false(self):
        """Partial set not accepted — full correct set required."""
        assert not grade_many_choice(q_mc(), {"type": "many_choice", "selected": ["list"]})

    def test_superset_with_wrong_returns_false(self):
        assert not grade_many_choice(q_mc(), {"type": "many_choice", "selected": ["list", "dict", "vector"]})

    def test_empty_list_returns_false(self):
        assert not grade_many_choice(q_mc(), {"type": "many_choice", "selected": []})

    def test_order_independent(self):
        assert grade_many_choice(q_mc(), {"type": "many_choice", "selected": ["dict", "list"]})


class TestGradeNumeric:
    def test_exact_value_returns_true(self):
        assert grade_numeric(q_nm_value(4.0), {"type": "numeric", "parsed": 4.0})

    def test_wrong_value_returns_false(self):
        assert not grade_numeric(q_nm_value(4.0), {"type": "numeric", "parsed": 5.0})

    def test_precision_rounded_match(self):
        """Parsed 3.14159 rounds to 3.14 at precision=3."""
        assert grade_numeric(
            q_nm_value(3.14, precision=3),
            {"type": "numeric", "parsed": 3.14159},
        )

    def test_precision_rounded_mismatch(self):
        assert not grade_numeric(
            q_nm_value(3.14, precision=3),
            {"type": "numeric", "parsed": 3.25},
        )

    def test_range_inclusive_both_ends(self):
        assert grade_numeric(q_nm_range(0, 10), {"type": "numeric", "parsed": 0})
        assert grade_numeric(q_nm_range(0, 10), {"type": "numeric", "parsed": 10})
        assert grade_numeric(q_nm_range(0, 10), {"type": "numeric", "parsed": 5})

    def test_range_outside_returns_false(self):
        assert not grade_numeric(q_nm_range(0, 10), {"type": "numeric", "parsed": -0.01})
        assert not grade_numeric(q_nm_range(0, 10), {"type": "numeric", "parsed": 10.01})

    def test_non_numeric_parsed_returns_false(self):
        assert not grade_numeric(q_nm_value(4.0), {"type": "numeric", "parsed": "four"})


class TestGradeString:
    def test_exact_match_case_insensitive_default(self):
        assert grade_string(q_string("Hello"), {"type": "string", "value": "hello"})

    def test_match_case_true_strict(self):
        assert not grade_string(
            q_string("Hello", match_case=True),
            {"type": "string", "value": "hello"},
        )
        assert grade_string(
            q_string("Hello", match_case=True),
            {"type": "string", "value": "Hello"},
        )

    def test_fuzzy_threshold_allows_typo(self):
        """One-edit typo "helo" vs "hello" → similarity = 4/5 = 0.8."""
        assert grade_string(
            q_string("hello", fuzzy=0.75),
            {"type": "string", "value": "helo"},
        )

    def test_fuzzy_threshold_rejects_too_different(self):
        assert not grade_string(
            q_string("hello", fuzzy=0.9),
            {"type": "string", "value": "world"},
        )

    def test_non_string_value_returns_false(self):
        assert not grade_string(q_string(), {"type": "string", "value": 42})


class TestExpectedAnswer:
    def test_mc_returns_correct_answer_list(self):
        assert expected_answer(q_sc("Paris")) == ["Paris"]

    def test_many_returns_all_correct(self):
        assert expected_answer(q_mc()) == ["list", "dict"]

    def test_numeric_value_returns_list_of_values(self):
        assert expected_answer(q_nm_value(4.0)) == [4.0]

    def test_numeric_range_returns_tuple(self):
        assert expected_answer(q_nm_range(0, 10)) == [(0, 10)]

    def test_unknown_type_returns_none(self):
        assert expected_answer({"type": "essay", "answers": []}) is None


class TestRoundToPrecision:
    def test_zero_returns_zero(self):
        assert _round_to_precision(0, 3) == 0.0

    def test_matches_toprecision(self):
        """Mirrors JS Number.toPrecision: 3.14159 at precision 3 → 3.14."""
        assert _round_to_precision(3.14159, 3) == 3.14


class TestLevenshtein:
    @pytest.mark.parametrize(
        "a,b,expected",
        [
            ("", "", 0),
            ("abc", "", 3),
            ("", "abc", 3),
            ("kitten", "sitting", 3),
            ("hello", "hello", 0),
            ("helo", "hello", 1),
        ],
    )
    def test_pairs(self, a, b, expected):
        assert _levenshtein(a, b) == expected


# ---------------------------------------------------------------------------
# QuestionResult / QuizResult dataclasses
# ---------------------------------------------------------------------------


class TestQuestionResult:
    def test_points_default_is_1(self):
        qr = QuestionResult(qnum=0, question=q_sc(), recorded=None, correct=False)
        assert qr.points == 1

    def test_points_from_question_field(self):
        qr = QuestionResult(qnum=0, question=q_sc(points=3), recorded=None, correct=False)
        assert qr.points == 3

    def test_points_fractional(self):
        qr = QuestionResult(qnum=0, question=q_sc(points=0.5), recorded=None, correct=False)
        assert qr.points == 0.5

    def test_earned_is_points_when_correct(self):
        qr = QuestionResult(qnum=0, question=q_sc(points=3), recorded=None, correct=True)
        assert qr.earned == 3

    def test_earned_is_zero_when_wrong(self):
        qr = QuestionResult(qnum=0, question=q_sc(points=3), recorded=None, correct=False)
        assert qr.earned == 0

    def test_question_type_falls_back_to_unknown(self):
        qr = QuestionResult(qnum=0, question={}, recorded=None, correct=False)
        assert qr.question_type == "unknown"


class TestQuizResult:
    def _r(self, *details):
        return QuizResult(grade_id="q1", details=list(details))

    def test_empty_quiz_is_0_of_0(self):
        r = self._r()
        assert r.score == 0
        assert r.max_score == 0

    def test_all_correct(self):
        r = self._r(
            QuestionResult(0, q_sc(points=2), None, True),
            QuestionResult(1, q_sc(points=3), None, True),
        )
        assert r.score == 5
        assert r.max_score == 5
        assert r.passed is True

    def test_partial(self):
        r = self._r(
            QuestionResult(0, q_sc(points=2), None, True),
            QuestionResult(1, q_sc(points=3), None, False),
        )
        assert r.score == 2
        assert r.max_score == 5
        assert r.passed is False

    def test_report_uses_fmt_pts_no_float_noise(self):
        r = self._r(
            QuestionResult(0, q_sc(points=0.3), None, True),
            QuestionResult(1, q_sc(points=0.3), None, True),
            QuestionResult(2, q_sc(points=0.4), None, True),
        )
        # Without fmt_pts, score=0.9999999999999999; ensure the report's
        # top line collapses the noise.
        first_line = r.report.splitlines()[0]
        assert "1/1" in first_line

    def test_display_review_returns_without_error(self):
        r = self._r(QuestionResult(0, q_sc(), None, False))
        # display_review swallows a missing IPython.display; just verify it
        # doesn't raise.  The actual HTML generation is covered below.
        r.display_review()


# ---------------------------------------------------------------------------
# grade_quiz — public API
# ---------------------------------------------------------------------------


class TestGradeQuizWithQuestionsKwarg:
    def test_all_correct_partial_credit_sums_to_max(self, cwd):
        questions = [q_sc(points=2), q_nm_value(4.0, points=3)]
        write_sidecar(
            cwd,
            "q1",
            {
                0: {"type": "multiple_choice", "selected": "Paris"},
                1: {"type": "numeric", "parsed": 4.0},
            },
        )
        r = grade_quiz("q1", questions=questions)
        assert r.score == 5
        assert r.max_score == 5

    def test_one_wrong_partial_credit(self, cwd):
        questions = [q_sc(points=2), q_nm_value(4.0, points=3)]
        write_sidecar(
            cwd,
            "q1",
            {
                0: {"type": "multiple_choice", "selected": "Berlin"},  # wrong
                1: {"type": "numeric", "parsed": 4.0},  # right
            },
        )
        r = grade_quiz("q1", questions=questions)
        assert r.score == 3
        assert r.max_score == 5

    def test_missing_response_graded_as_wrong(self, cwd):
        questions = [q_sc(), q_sc()]
        write_sidecar(cwd, "q1", {0: {"type": "multiple_choice", "selected": "Paris"}})
        r = grade_quiz("q1", questions=questions)
        # q0 correct (1 pt), q1 no response (0 pt)
        assert r.score == 1
        assert r.max_score == 2

    def test_malformed_response_graded_as_wrong(self, cwd):
        questions = [q_sc()]
        write_sidecar(cwd, "q1", {0: "not a dict"})
        r = grade_quiz("q1", questions=questions)
        assert r.score == 0
        assert r.details[0].correct is False

    def test_no_sidecar_at_all_returns_zero(self, cwd):
        questions = [q_sc(), q_sc()]
        # Don't write responses.json — every question is "no response".
        r = grade_quiz("q1", questions=questions)
        assert r.score == 0
        assert r.max_score == 2

    def test_sidecar_missing_grade_id_returns_zero(self, cwd):
        questions = [q_sc()]
        write_sidecar(cwd, "other-quiz", {0: {"type": "multiple_choice", "selected": "Paris"}})
        r = grade_quiz("q1", questions=questions)
        assert r.score == 0

    def test_unsupported_schema_version_raises(self, cwd):
        write_sidecar(cwd, "q1", {}, schema_version=99)
        with pytest.raises(GradeQuizError, match="schema_version"):
            grade_quiz("q1", questions=[q_sc()])

    def test_malformed_json_raises(self, cwd):
        (cwd / "responses.json").write_text("{not json")
        with pytest.raises(GradeQuizError, match="Cannot read"):
            grade_quiz("q1", questions=[q_sc()])


class TestGradeQuizFromNotebook:
    def _write_nb(self, cwd, grade_id, quiz_source):
        cell = v4.new_markdown_cell(source=quiz_source)
        cell.metadata["nbgrader"] = {"task": True, "grade_id": grade_id}
        nb = v4.new_notebook()
        nb.cells = [cell]
        path = cwd / "quiz.ipynb"
        nbformat.write(nb, path)
        return path

    def test_reads_questions_from_the_notebook(self, cwd):
        self._write_nb(cwd, "q1", '#### Quiz\n* (SC) "Capital?"\n  + "Paris"\n  - "Berlin"\n#### End Quiz')
        write_sidecar(cwd, "q1", {0: {"type": "multiple_choice", "selected": "Paris"}})
        r = grade_quiz("q1")
        assert r.score == 1

    def test_unknown_grade_id_raises(self, cwd):
        self._write_nb(cwd, "other", '#### Quiz\n* (SC) "Q?"\n  + "A"\n  - "B"\n#### End Quiz')
        with pytest.raises(GradeQuizError, match="No cell with nbgrader.grade_id"):
            grade_quiz("q1")

    def test_no_ipynb_in_cwd_raises(self, cwd):
        with pytest.raises(GradeQuizError, match="No .ipynb found in CWD"):
            grade_quiz("q1")

    def test_multiple_ipynb_ambiguous_raises(self, cwd):
        # Two .ipynb files → helper can't pick.
        (cwd / "one.ipynb").write_text(json.dumps(v4.new_notebook()))
        (cwd / "two.ipynb").write_text(json.dumps(v4.new_notebook()))
        with pytest.raises(GradeQuizError, match="Multiple .ipynb"):
            grade_quiz("q1")

    def test_explicit_notebook_path_skips_cwd_glob(self, cwd, tmp_path):
        # Another notebook sits in cwd; passing notebook_path takes precedence.
        (cwd / "decoy.ipynb").write_text(json.dumps(v4.new_notebook()))
        target = self._write_nb(tmp_path, "q1", '#### Quiz\n* (SC) "Q?"\n  + "A"\n  - "B"\n#### End Quiz')
        write_sidecar(cwd, "q1", {0: {"type": "multiple_choice", "selected": "A"}})
        r = grade_quiz("q1", notebook_path=target)
        assert r.score == 1


# ---------------------------------------------------------------------------
# Review rendering (_review.py)
# ---------------------------------------------------------------------------


class TestFmtPts:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "0"),
            (1, "1"),
            (1.0, "1"),
            (0.5, "0.5"),
            (0.25, "0.25"),
            (0.125, "0.125"),  # preserved at 3 decimals
            (0.1, "0.1"),
            (2.5, "2.5"),
            (0.3 + 0.3 + 0.4, "1"),  # float accumulation collapses
            (0.333333, "0.333"),
        ],
    )
    def test_formats(self, value, expected):
        assert fmt_pts(value) == expected


class TestRenderReviewHtml:
    def _result(self, details):
        return QuizResult(grade_id="q1", details=details)

    def test_contains_score_header(self):
        html = render_review_html(
            self._result(
                [
                    QuestionResult(0, q_sc(), {"type": "multiple_choice", "selected": "Paris"}, True),
                ]
            )
        )
        assert "Your score: 1 / 1" in html

    def test_mc_picked_correct_labelled(self):
        html = render_review_html(
            self._result(
                [
                    QuestionResult(0, q_sc(), {"type": "multiple_choice", "selected": "Paris"}, True),
                ]
            )
        )
        assert "correct-picked" in html
        assert "your choice — correct" in html

    def test_mc_missed_answer_labelled(self):
        html = render_review_html(
            self._result(
                [
                    QuestionResult(
                        0,
                        q_mc(),
                        {"type": "many_choice", "selected": ["list"]},
                        False,
                    ),
                ]
            )
        )
        assert "correct-missed" in html
        # dict is correct-but-not-selected
        assert "dict" in html

    def test_mc_no_response_shows_muted_row(self):
        html = render_review_html(
            self._result(
                [
                    QuestionResult(0, q_sc(), None, False),
                ]
            )
        )
        assert "No answer recorded" in html

    def test_numeric_correct_shows_ok_mark(self):
        html = render_review_html(
            self._result(
                [
                    QuestionResult(
                        0,
                        q_nm_value(4.0),
                        {"type": "numeric", "raw": "4", "parsed": 4.0},
                        True,
                    ),
                ]
            )
        )
        assert "jq-review-ok" in html
        assert "4" in html

    def test_numeric_raw_and_parsed_both_shown_when_different(self):
        html = render_review_html(
            self._result(
                [
                    QuestionResult(
                        0,
                        q_nm_value(0.5),
                        {"type": "numeric", "raw": "1/2", "parsed": 0.5},
                        True,
                    ),
                ]
            )
        )
        # Both "1/2" (raw) and "0.5" (parsed) should appear.
        assert "1/2" in html
        assert "0.5" in html

    def test_string_correct_shows_ok_mark(self):
        html = render_review_html(
            self._result(
                [
                    QuestionResult(
                        0,
                        q_string("hello"),
                        {"type": "string", "value": "hello"},
                        True,
                    ),
                ]
            )
        )
        assert "jq-review-ok" in html

    def test_unknown_question_type_does_not_crash(self):
        html = render_review_html(
            self._result(
                [
                    QuestionResult(
                        0,
                        {"type": "essay", "question": "Discuss.", "answers": []},
                        {"type": "essay"},
                        False,
                    ),
                ]
            )
        )
        assert "unrecognised question type" in html

    def test_html_escaping_on_question_text(self):
        """Angle brackets in question text are escaped, not interpreted."""
        q = {
            "type": "multiple_choice",
            "question": "What is <b>bold</b>?",
            "answers": [{"correct": True, "answer": "A"}],
        }
        html = render_review_html(
            self._result(
                [
                    QuestionResult(0, q, {"type": "multiple_choice", "selected": "A"}, True),
                ]
            )
        )
        assert "&lt;b&gt;bold&lt;/b&gt;" in html
        assert "<b>bold</b>" not in html  # raw HTML not leaked


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_supported_schema_versions_is_a_tuple_of_ints():
    assert isinstance(SUPPORTED_SCHEMA_VERSIONS, tuple)
    assert all(isinstance(v, int) for v in SUPPORTED_SCHEMA_VERSIONS)
    assert 1 in SUPPORTED_SCHEMA_VERSIONS
