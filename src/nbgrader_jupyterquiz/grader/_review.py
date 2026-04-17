"""
Static HTML review rendering for graded quizzes.

The rendered output is scoped, self-contained HTML + inline CSS —
suitable for display in any browser without a running Jupyter server
or kernel.  Emitted by
:meth:`~nbgrader_jupyterquiz.grader.autograde.QuizResult.display_review`
from within the auto-generated hidden-tests block; ``nbgrader
generate_feedback`` propagates it into the per-student feedback HTML.
"""

from __future__ import annotations
from html import escape
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .autograde import QuestionResult, QuizResult


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


def fmt_pts(value: float) -> str:
    """
    Format a point value for display, collapsing binary-float noise.

    Rounds to three decimal places and strips trailing zeros so that
    accumulation artefacts such as ``0.3 + 0.3 + 0.4 ==
    0.9999999999999999`` don't bleed into the visible review text.
    Three decimals preserve common fractional weights exactly —
    halves (0.5), quarters (0.25), eighths (0.125), tenths (0.1) —
    which a two-decimal rounding would mangle (``round(0.125, 2) ==
    0.12`` under banker's rounding).

    Parameters
    ----------
    value : float
        Point value to format.

    Returns
    -------
    str
        Canonical short textual form, e.g. ``"1"``, ``"0.5"``, ``"0.125"``.
    """
    rounded = round(float(value), 3)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def render_review_html(result: QuizResult) -> str:
    """
    Render a full quiz review as a scoped HTML string.

    Parameters
    ----------
    result : QuizResult
        Grading outcome to render.

    Returns
    -------
    str
        Complete ``<style>`` + ``<div>`` block ready for
        :class:`IPython.display.HTML`.
    """
    parts = [_REVIEW_CSS, '<div class="jq-review">']
    parts.append(f'<div class="jq-review-score">Your score: {fmt_pts(result.score)} / {fmt_pts(result.max_score)}</div>')
    for d in result.details:
        qtext = escape(d.question.get("question", "") or "")
        header_points = f' <span class="jq-review-ptag">{fmt_pts(d.earned)}/{fmt_pts(d.points)} pts</span>'
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


def _render_review_choice(detail: QuestionResult) -> str:
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


def _render_review_numeric(detail: QuestionResult) -> str:
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


def _render_review_string(detail: QuestionResult) -> str:
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
