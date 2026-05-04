================
Worked examples
================

Four source notebooks shipped as downloads.  Each is a complete,
self-contained instructor source notebook — open it in JupyterLab,
register :class:`~nbgrader_jupyterquiz.CreateQuiz` in your
``nbgrader_config.py``, place the notebook under
``source/<assignment>/``, and run ``nbgrader generate_assignment`` to
produce a student release.

:download:`quiz_source_example.ipynb <quiz_source_example.ipynb>`
    Minimal walkthrough of the Markdown syntax: single-choice,
    many-choice, and numeric (exact + range + precision) questions.
    Self-check only — no auto-grading.

:download:`nb1-geography.ipynb <nb1-geography.ipynb>`
    A graded quiz demonstrating every mode the preprocessor
    supports: the default (graded, hide-correctness),
    ``hide_correctness=false``, ``graded=false`` (self-check inside
    a task cell), and ``graded=false hide_correctness=true`` (study
    mode).  Also exercises per-question points via ``{N}``,
    including fractional points, and shows how the task cell's own
    ``points`` field is preserved for manual grading of surrounding
    prose.

:download:`nb2-python.ipynb <nb2-python.ipynb>`
    Companion to ``nb1-geography`` that additionally covers numeric
    questions with range answers, code-block question text, and a
    mix of integer and fractional weights.

:download:`nb3-physics-rich-content.ipynb <nb3-physics-rich-content.ipynb>`
    A worked example combining every feature in one notebook,
    framed as a short physics problem set.  Annotated cell-by-cell
    with what's being demonstrated and why each combination is
    interesting.  Covers MathJax in question and answer labels,
    numeric value and range matching with precision, code-block
    questions, per-question points, and a self-check warm-up
    inside a graded task.
