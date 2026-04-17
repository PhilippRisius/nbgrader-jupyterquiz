===============
Graded Quizzes
===============

.. contents::
   :local:

Starting with v0.4.0, quizzes embedded in nbgrader **Manually Graded Task**
cells can be graded automatically.  Student responses are recorded into a
``responses.json`` sidecar file as the student answers, and ``nbgrader
autograde`` evaluates them against the instructor's answer key with
partial-credit support.

The instructor only needs to:

1. Register :class:`~nbgrader_jupyterquiz.CreateQuiz` at the front of the
   ``GenerateAssignment`` preprocessor list (see
   :doc:`nbgrader-pipeline`).
2. Write a quiz inside a Manually Graded Task cell with an
   ``nbgrader.grade_id`` set — exactly the same authoring flow as the
   self-checking quiz in :doc:`quiz-syntax`.

The preprocessor detects the ``grade_id`` and promotes the quiz to
graded mode: correctness feedback is hidden (so students can't guess
their way through), each answer click is persisted to the sidecar, and
an autograder cell is auto-generated.  **No separate test cell needs
to be written by hand.**


How it works
============

At ``generate_assignment`` time, ``CreateQuiz`` emits one code cell
per quiz region.  The cell's visible source (in the release) is just
the usual ``display_quiz(...)`` call.  The cell's hidden-tests block —
stripped from the release by nbgrader's ``ClearHiddenTests`` and
restored at autograde time by ``OverwriteCells`` — embeds the answer
key as a Python literal and invokes :func:`grade_quiz`.  A bare
``_result.score`` at the end of the cell feeds nbgrader's partial-credit
machinery (``utils.determine_grade``):

.. code-block:: python

    from nbgrader_jupyterquiz.display import display_quiz
    display_quiz("#notebook:0.0", grade_id="quiz-1-autograded")
    ### BEGIN HIDDEN TESTS
    from nbgrader_jupyterquiz import grade_quiz
    _questions = [...]  # answer key, embedded by the preprocessor
    _result = grade_quiz("quiz-1-autograded", questions=_questions)
    _result.display_review()
    print(f"Score: {_result.score}/{_result.max_score}")
    _result.score
    ### END HIDDEN TESTS

When the student answers a question in the browser, the rendered JS
recorder writes (or updates) ``responses.json`` in the same directory
as the notebook via the Jupyter server's contents API.  Entries are
keyed by grade_id, so multiple quizzes in the same assignment
coexist in one file.

At autograde time, nbgrader restores the hidden-tests block from the
gradebook master, re-executes the cell, and reads the sidecar.
``grade_quiz`` grades per-question (all-or-nothing per question) and
returns a ``QuizResult`` whose ``.score`` — the final bare expression
— becomes the cell's partial-credit grade.


Mixing graded and self-check quizzes
====================================

Sometimes a Manually Graded Task cell contains both work that is
graded by hand (prose, code) and a self-check quiz that shouldn't
contribute to the score.  Mark the quiz with ``graded=false``:

.. code-block:: markdown

    #### Quiz graded=false
    * (SC) "Self-check — not graded"
      + "A"
      - "B"
    #### End Quiz

An ungraded quiz:

* emits a plain ``display_quiz(...)`` cell — no nbgrader metadata on
  the generated cell, no hidden-tests block, no gradebook entry;
* shows correctness feedback (green / red), as in v0.3.x
  self-checking mode;
* does **not** render points badges unless a question carries an
  explicit ``{N}`` marker (in which case the badge is shown
  per the usual rule);
* leaves the task cell's own ``points`` untouched — those remain
  available for manual grading of whatever the task cell actually
  grades.

``graded=false`` and ``hide_correctness`` are independent.  The
interesting combinations:

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Configuration
     - Correctness feedback
     - Auto-graded
   * - Task cell w/ ``grade_id`` (default)
     - Hidden (Selected/Deselected)
     - Yes
   * - Task cell w/ ``grade_id`` + ``hide_correctness=false``
     - Visible (green / red)
     - Yes (but leaky)
   * - Task cell w/ ``grade_id`` + ``graded=false``
     - Visible (green / red)
     - No
   * - Task cell w/ ``grade_id`` + ``graded=false hide_correctness=true``
     - Hidden (Selected/Deselected)
     - No (study mode)


Per-question points
===================

Questions can carry individual point weights via the ``{N}`` marker on
the question line.  ``N`` is any positive number, including fractions
like ``{0.5}``:

.. code-block:: markdown

    #### Quiz
    * (SC) {3} "Worth three points"
      + "A"
      - "B"
    * (SC) {0.5} "Half-point warm-up"
      + "A"
      - "B"
    * (NM) {2} "Two-point numeric"
      + <42>
    #### End Quiz

Points display as a small badge next to each question.  The cell's
total ``nbgrader.points`` is the sum across questions (in the example
above: ``3 + 0.5 + 2 = 5.5``).  Unweighted quizzes — where no question
carries a ``{N}`` marker — render without badges and implicitly treat
each question as worth 1 point.

When at least one question in a quiz has ``{N}``, the preprocessor
propagates the default ``{1}`` onto all siblings so the visual is
consistent.  Mix freely.


The feedback view
=================

After ``nbgrader autograde``, the autograder cell's output contains a
static HTML review showing, per question:

* the student's selection(s),
* the correct answer(s),
* which were picked / which were missed,
* per-question points earned / maximum.

This review is preserved in the cell output, so ``nbgrader
generate_feedback`` includes it in the per-student feedback HTML.


API
===

.. autofunction:: nbgrader_jupyterquiz.grade_quiz

.. autoclass:: nbgrader_jupyterquiz.grader.autograde.QuizResult
   :members:

.. autoclass:: nbgrader_jupyterquiz.grader.autograde.QuestionResult
   :members:


Limitations
===========

* **Jupyter server required.**  The response recorder persists answers
  via ``fetch('/api/contents/...')``.  Any client that routes through a
  standard ``jupyter_server`` works: JupyterLab 4, Notebook 7, classic
  Notebook.  **The VS Code Jupyter extension is not supported** — it
  uses a kernel-direct protocol and does not expose the contents API.
  Students who must use VS Code will see the quiz render but their
  answers will not persist; instructors running graded assessments
  should require JupyterLab or Notebook.
* **Points are all-or-nothing per question.**  Students earn the full
  per-question points iff the answer is fully correct.  Partial
  credit within a single question (e.g., "selected 2 of 3 correct MC
  options") is not awarded — that would require splitting a
  many-choice question into separately-graded atoms.
* **Manual edits to `responses.json` are not detected.**  The grading
  code trusts the sidecar.  If the sidecar is tampered with between
  submission and autograde, the altered responses will be graded.  For
  high-stakes assessments, rely on nbgrader's secure exchange rather
  than student-local editing.
