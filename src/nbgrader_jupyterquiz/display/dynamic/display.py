"""Entry point for displaying quizzes in Jupyter environments."""

import random
import string

from IPython.display import HTML, Javascript, display

from .loader import load_questions_script
from .renderer import build_script, build_styles, render_div


_DEFAULT_COLORS = {
    "--jq-multiple-choice-bg": "#392061",
    "--jq-mc-button-bg": "#fafafa",
    "--jq-mc-button-border": "#e0e0e0e0",
    "--jq-mc-button-text": "#333333",
    "--jq-mc-button-inset-shadow": "#555555",
    "--jq-many-choice-bg": "#f75c03ff",
    "--jq-numeric-bg": "#392061ff",
    "--jq-numeric-input-bg": "#c0c0c0",
    "--jq-numeric-input-label": "#101010",
    "--jq-numeric-input-shadow": "#999999",
    "--jq-string-bg": "#4c1a57",
    "--jq-incorrect-color": "#c80202",
    "--jq-select-color": "#6f78ff",
    "--jq-correct-color": "#009113",
    "--jq-text-color": "#fafafa",
    "--jq-link-color": "#9abafa",
}

_FDSP_COLORS = {
    "--jq-multiple-choice-bg": "#345995",
    "--jq-mc-button-bg": "#fafafa",
    "--jq-mc-button-border": "#e0e0e0e0",
    "--jq-mc-button-text": "#333333",
    "--jq-mc-button-inset-shadow": "#555555",
    "--jq-many-choice-bg": "#e26d5a",
    "--jq-numeric-bg": "#5bc0eb",
    "--jq-numeric-input-bg": "#c0c0c0",
    "--jq-numeric-input-label": "#101010",
    "--jq-numeric-input-shadow": "#999999",
    "--jq-string-bg": "#861657",
    "--jq-incorrect-color": "#666666",
    "--jq-select-color": "#6f78ff",
    "--jq-correct-color": "#87a878",
    "--jq-text-color": "#fafafa",
    "--jq-link-color": "#9abafa",
}


def display_quiz(
    ref,
    num=1_000_000,
    shuffle_questions=False,
    shuffle_answers=True,
    preserve_responses=False,
    border_radius=10,
    question_alignment="left",
    max_width=600,
    colors=None,
    load_js=True,
    grade_id=None,
):
    """
    Display an interactive quiz in a Jupyter notebook.

    Parameters
    ----------
    ref : list or str
        Question list, DOM element id (``#name:tag``), URL, or file path.
    num : int, optional
        Maximum number of questions to show.
    shuffle_questions : bool, optional
        Randomise question order on each display.
    shuffle_answers : bool, optional
        Randomise answer order on each display.
    preserve_responses : bool, optional
        Keep student responses visible after answering.
    border_radius : int, optional
        CSS border-radius in pixels.
    question_alignment : str, optional
        One of ``'left'``, ``'center'``, ``'right'``.
    max_width : int, optional
        Maximum quiz width in pixels.
    colors : dict or str, optional
        CSS variable overrides, or ``'fdsp'`` for the alternate palette.
    load_js : bool, optional
        Whether to inline the JavaScript source.
    grade_id : str, optional
        Nbgrader ``grade_id`` of the host task cell.  When set, the JS
        recorder persists student responses to a ``responses.json``
        sidecar file so an autograded test cell can read them via
        :func:`nbgrader_jupyterquiz.autograde.grade_quiz`.  When
        ``None`` (the default for non-nbgrader callers), the recorder
        is a no-op.
    """
    assert not (shuffle_questions and preserve_responses), "Preserving responses not supported when shuffling questions."
    assert num == 1_000_000 or (not preserve_responses), "Preserving responses not supported when num is set."
    assert question_alignment in ["left", "right", "center"], "question_alignment must be 'left', 'center', or 'right'"

    div_id = "".join(random.choice(string.ascii_letters) for _ in range(12))

    color_dict = dict(_DEFAULT_COLORS)
    if colors == "fdsp":
        color_dict = dict(_FDSP_COLORS)
    elif isinstance(colors, dict):
        color_dict.update(colors)

    prefix_script, static, url = load_questions_script(ref, div_id)

    mydiv = render_div(div_id, shuffle_questions, shuffle_answers, preserve_responses, num, max_width, border_radius, question_alignment, grade_id)
    styles = build_styles(div_id, color_dict)
    javascript = build_script(prefix_script, static, url, div_id, load_js)

    display(HTML(mydiv + styles))
    display(Javascript(javascript))
