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
    running ``nbgrader assign``, and grading.

:doc:`display-options`
    Reference for :func:`~nbgrader_jupyterquiz.display_quiz` — layout, shuffling,
    colour customisation, and CSS variables.

Example notebook
----------------

A complete source notebook demonstrating all supported question types is
available as a download:

:download:`quiz_source_example.ipynb <examples/quiz_source_example.ipynb>`

Open it in Jupyter, mark the quiz cells as *Manually Graded Task*, and run
``nbgrader assign`` to see the full pipeline in action.
