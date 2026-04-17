==================
nbgrader Pipeline
==================

This page walks through the full instructor workflow: writing quiz source cells,
generating the student release, and grading.

Prerequisites
-------------

* nbgrader >= 0.9 is installed and a course directory is initialised
  (``nbgrader quickstart`` or equivalent).
* **nbgrader-jupyterquiz** is installed in the same environment.
* The :class:`~nbgrader_jupyterquiz.CreateQuiz` preprocessor is registered in
  ``nbgrader_config.py`` (see :ref:`nbgrader-pipeline:Configuration`).

Writing quiz cells
------------------

In your source notebook (under ``source/<assignment>/``), add quiz content inside
a **Manually Graded Task** cell.  The cell type must be set to *Manually Graded
Task* in the nbgrader cell toolbar — ``CreateQuiz`` will raise an error if a quiz
region is found in a plain cell (unless ``enforce_metadata`` is disabled).

Inside the cell, wrap questions in ``#### Quiz`` / ``#### End Quiz`` delimiters.
Any text outside the delimiters is preserved verbatim.  See :doc:`quiz-syntax` for
the full authoring syntax.

.. code-block:: markdown

    Use the quiz below to check your understanding.

    #### Quiz
    * (SC) "Which statement about Python lists is true?"
      + "Lists are ordered and mutable."
      - "Lists are ordered and immutable."
      - "Lists are unordered and mutable."
    #### End Quiz

Running ``nbgrader assign``
---------------------------

Run the standard nbgrader assignment generation command:

.. code-block:: console

    nbgrader assign <assignment-name>

``CreateQuiz`` runs as part of the ``GenerateAssignment`` preprocessor pipeline.
For each quiz region it:

1. Parses the Markdown quiz source into a list of question dictionaries.
2. Validates each question against the JSON schema.
3. Base64-encodes the question data and injects it as a hidden ``<span>`` in the
   cell source (``display:none``), so the correct answers are not visible to
   students.
4. Appends a new code cell that calls
   :func:`~nbgrader_jupyterquiz.display_quiz` with a reference to the hidden span.

The released notebook contains no plaintext answer data.  Students see only the
interactive widget.

Distributing to students
------------------------

Distribute the release as usual (``nbgrader release_assignment``,
``nbgrader zip_collect``, or your LMS).  No additional steps are required.

Collecting and grading
----------------------

Collect submissions as usual.  At this stage, quizzes are **self-checking
only** — student answers are displayed in the browser but are not saved to the
notebook file.  There is currently no mechanism to collect or grade quiz
answers through nbgrader.  Grading support is planned for a future release.

Configuration
-------------

Register ``CreateQuiz`` at the **front** of your ``GenerateAssignment``
preprocessor list in ``nbgrader_config.py``:

.. code-block:: python

    c.GenerateAssignment.preprocessors.insert(0, "nbgrader_jupyterquiz.CreateQuiz")

It must run before ``SaveCells`` so the auto-generated autograder cells
are registered in the gradebook, and before ``ClearHiddenTests`` so the
grading body is properly stripped from the release.  Appending to the end
of the list (``.append(...)``) causes autograde to fail with checksum and
grade_id validation errors.

When the host Manually Graded Task cell has an nbgrader ``grade_id``,
``CreateQuiz`` promotes the quiz to graded mode: correctness feedback
is hidden, responses are persisted to a sidecar file, and the cell is
autograded at submission time.  See :doc:`graded-quizzes` for the full
workflow.

The preprocessor exposes three configurable traitlets:

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Option
     - Default
     - Description
   * - ``begin_quiz_delimiter``
     - ``"#### Quiz"``
     - The string that opens a quiz region.
   * - ``end_quiz_delimiter``
     - ``"#### End Quiz"``
     - The string that closes a quiz region.
   * - ``enforce_metadata``
     - ``True``
     - Raise an error if a quiz region is found outside a *Manually Graded Task*
       cell.  Disable only if you are using ``nbgrader assign`` without the full
       grading pipeline.

To override a traitlet, add it to ``nbgrader_config.py``:

.. code-block:: python

    c.CreateQuiz.begin_quiz_delimiter = "### BEGIN QUIZ"
    c.CreateQuiz.end_quiz_delimiter   = "### END QUIZ"
    c.CreateQuiz.enforce_metadata     = False
