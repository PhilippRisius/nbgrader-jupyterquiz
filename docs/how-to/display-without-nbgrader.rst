===============================
Display a quiz without nbgrader
===============================

The :func:`~nbgrader_jupyterquiz.display_quiz` function works
standalone — you don't need nbgrader to render an interactive quiz.
This is useful for self-check exercises in a teaching notebook,
slides, or a JupyterBook where no grading pipeline exists.

Inline question list
====================

Pass a list of question dicts directly:

.. code-block:: python

    from nbgrader_jupyterquiz import display_quiz

    questions = [
        {
            "type": "multiple_choice",
            "question": "Which planet is closest to the Sun?",
            "answers": [
                {"answer": "Mercury", "correct": True, "feedback": "Right!"},
                {"answer": "Venus",   "correct": False},
                {"answer": "Earth",   "correct": False},
            ],
        },
    ]
    display_quiz(questions)

Run the cell — the quiz renders with green / red correctness feedback
on click.  No nbgrader, no sidecar, no autograder.

Loading from a JSON file
========================

For longer quiz banks, keep the questions in a separate file:

.. code-block:: python

    display_quiz("warmup_questions.json")

The JSON file is a list of question objects in the same shape as the
inline list above.  Loading from a URL works too — pass any
``http(s)://...`` string.

Display options
===============

A few options are commonly useful in standalone mode:

.. code-block:: python

    display_quiz(
        questions,
        shuffle_questions=True,
        shuffle_answers=True,
        num=3,                    # show 3 random questions out of N
        max_width=800,            # widen the quiz container
        colors="fdsp",            # alternate palette
    )

See :doc:`/display-options` for the full parameter list and the
CSS variables you can override.

What you don't get
==================

Without nbgrader's preprocessor pipeline, you opt out of:

* Markdown ``#### Quiz`` syntax — you write the question dicts
  directly.
* Auto-generated autograder cells.
* Answer-key redaction (graded mode is an nbgrader-only concept).
* The ``responses.json`` sidecar — student responses live only in
  the rendered DOM and are lost when the page reloads.

If you want responses persisted for later marking, set
``preserve_responses=True`` and instruct the student to copy the
text that appears below the quiz.  For real graded assessments use
the full nbgrader pipeline — see :doc:`/graded-quizzes`.
