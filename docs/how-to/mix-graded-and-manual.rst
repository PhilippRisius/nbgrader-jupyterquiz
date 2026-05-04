==================================================
Mix graded and manually-graded content in one cell
==================================================

A Manually Graded Task cell often contains both prose / code that an
instructor reads and grades by hand, *and* a self-check quiz the
instructor doesn't want included in the score.  The two coexist in
one cell.

The recipe
==========

Mark the quiz with ``graded=false`` in the quiz header:

.. code-block:: markdown

    Explain in two or three sentences why ``len(s)`` is O(1) for a
    Python ``str`` but ``s.count('x')`` is O(n).  *(2 points,
    instructor-graded.)*

    #### Quiz graded=false
    * (SC) "Self-check: which of these is O(1)?"
      + "len(s)"
      - "s.count('x')"
      - "''.join(s)"
    #### End Quiz

The cell stays marked as a *Manually Graded Task* with whatever
``points`` you set on the cell itself (here, ``2``).  At
``generate_assignment`` time:

* The prose is left untouched.
* The quiz region is replaced with a plain
  ``display_quiz(...)`` cell — no nbgrader metadata, no
  hidden-tests block, no gradebook entry of its own.
* Correctness feedback (green / red) is visible to the student
  during answering — like the v0.3.x self-check mode.

The instructor grades the prose by hand in ``nbgrader formgrader``;
the self-check quiz is purely formative.

Going further
=============

* **Multiple quizzes in one cell, mixed modes.**  ``graded=false``
  is per-quiz, not per-cell.  You can have a graded ``#### Quiz``
  and an ungraded ``#### Quiz graded=false`` in the same task cell.
  Each becomes its own code cell at generation time.
* **Hide correctness even on a self-check.**  Combine
  ``graded=false hide_correctness=true`` for a quiz that neither
  scores nor reveals answers — useful for *study mode* where the
  student should commit to an answer without immediate feedback.
* **Force visible correctness on a graded quiz.**  Combine the
  default graded mode with ``hide_correctness=false`` if you
  don't mind students seeing the answer key in the rendered DOM
  (mostly useful for instructor-side preview).  See
  :doc:`/graded-quizzes` for the security trade-off.

The full mode matrix is in :doc:`/graded-quizzes` under *Mixing
graded and self-check quizzes*.
