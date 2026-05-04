==============================
Write a numeric range question
==============================

A numeric question with a *range* answer accepts any value inside a
closed interval.  Useful for measurements, approximations, and any
case where exact equality is too strict.

The basics
==========

Two variants combine on a single answer line:

.. code-block:: markdown

    #### Quiz
    * (NM) "Pick a value between 0 and 10."
      + [0.0, 10.0]   (Correct.)
    #### End Quiz

The ``+ [min, max]`` line is the *correct* range — both endpoints
are inclusive.  Any number from ``0.0`` through ``10.0`` is graded
right.

Add tolerance bands and a default
=================================

You can chain multiple range answers, mixing ``+`` (correct) and
``-`` (incorrect) entries with feedback.  A bare ``- (...)`` line
is the catch-all for anything not matched by another answer:

.. code-block:: markdown

    #### Quiz
    * (NM) "Speed of light in m/s, to 3 sig. figs.?" [3]
      + <3.00e8>            (Correct!)
      - [2.50e8, 2.99e8]    (A little low — units?)
      - [3.01e8, 3.50e8]    (A little high — double-check.)
      - (Not even close.)
    #### End Quiz

The ``[3]`` after the question is the *precision* marker: the
student's input is rounded to 3 significant figures before
comparison.  Without ``[N]``, exact equality is required for value
answers; ranges always compare on the raw value.

Combining with points
=====================

Range questions accept the ``{N}`` per-question points marker like
any other:

.. code-block:: markdown

    #### Quiz
    * (NM) {2} "Pick a value between 0 and 10."
      + [0.0, 10.0]
    #### End Quiz

The whole question is worth 2 points; partial credit within a
single question is not awarded.  See :doc:`/graded-quizzes` for
how cell-level scores roll up.

Common pitfalls
===============

* **Negative ranges**: `[-1, 1]` is a valid syntax — the parser
  splits on the first comma, so the leading ``-`` is part of the
  number, not an answer-line prefix.
* **Single-value match plus a range** on the same answer line is
  a ``ParseError``.  Use separate answer lines.
* **Open intervals are not supported.**  Both endpoints are
  inclusive; if you need an exclusive bound, narrow the range
  by one ULP or use a separate ``- [..., bound]`` band.
