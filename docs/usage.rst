=====
Usage
=====

**nbgrader-jupyterquiz** has two main audiences: *instructors* who author and
release quizzes, and *students* who answer them.  The pages below cover both
perspectives.

:doc:`quiz-syntax`
    How to write quiz questions in Markdown inside a Jupyter notebook cell —
    question types, answer lines, feedback, numeric ranges, and code blocks.

:doc:`nbgrader-pipeline`
    The full instructor workflow: registering the preprocessor, marking cells,
    running ``nbgrader generate_assignment``, and grading.

:doc:`graded-quizzes`
    How quizzes embedded in Manually Graded Task cells are auto-graded end-to-end —
    the ``responses.json`` sidecar, per-question points, graded / self-check modes,
    and the :func:`~nbgrader_jupyterquiz.grade_quiz` helper.

:doc:`display-options`
    Reference for :func:`~nbgrader_jupyterquiz.display_quiz` — layout, shuffling,
    colour customisation, and CSS variables.

Example notebooks
-----------------

Three source notebooks are included as downloads.  Each is a complete,
self-contained instructor source notebook — open it in JupyterLab,
register :class:`~nbgrader_jupyterquiz.CreateQuiz` in your
``nbgrader_config.py``, place the notebooks under
``source/<assignment>/``, and run ``nbgrader generate_assignment`` to
produce a student release.

:download:`quiz_source_example.ipynb <examples/quiz_source_example.ipynb>`
    Minimal walkthrough of the Markdown syntax: single-choice, many-choice,
    and numeric (exact + range + precision) questions.  Self-check only —
    no auto-grading.

:download:`nb1-geography.ipynb <examples/nb1-geography.ipynb>`
    A graded quiz demonstrating every mode the preprocessor supports:
    the default (graded, hide-correctness), ``hide_correctness=false``,
    ``graded=false`` (self-check inside a task cell), and
    ``graded=false hide_correctness=true`` (study mode).  Also exercises
    per-question points via ``{N}``, including fractional points, and
    shows how the task cell's own ``points`` field is preserved for
    manual grading of surrounding prose.

:download:`nb2-python.ipynb <examples/nb2-python.ipynb>`
    Companion to ``nb1-geography`` that additionally covers numeric
    questions with range answers, code-block question text, and a mix
    of integer and fractional weights.
