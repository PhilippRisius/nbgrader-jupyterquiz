========
Tutorial
========

A guided first walk-through: install **nbgrader-jupyterquiz**, write a
small quiz, release it as an assignment, answer it as a student, and
let nbgrader autograde the result.  The whole loop takes about ten
minutes and produces a working graded assignment you can use as a
template.

This tutorial assumes you have Python 3.10+ and ``pip`` available.
Familiarity with nbgrader's basic concepts (course directory, source /
release / autograded folders) helps but is not required.

.. contents::
   :local:


1. Install
==========

In a fresh virtual environment, install the package together with
its nbgrader and JupyterLab dependencies:

.. code-block:: console

    pip install nbgrader-jupyterquiz jupyterlab

This pulls in nbgrader (≥ 0.9), nbformat, traitlets, and JupyterLab.


2. Initialise a course directory
================================

If you don't already have one, create an nbgrader course skeleton:

.. code-block:: console

    mkdir tutorial-course && cd tutorial-course
    nbgrader quickstart .

That produces a ``source/``, ``release/``, ``submitted/``,
``autograded/``, and ``feedback/`` layout, a ``gradebook.db``, and a
default ``nbgrader_config.py`` file.

Open ``nbgrader_config.py`` and add **one line** at the top of the
``GenerateAssignment`` preprocessor list:

.. code-block:: python

    c.GenerateAssignment.preprocessors.insert(0, "nbgrader_jupyterquiz.CreateQuiz")

The ``insert(0, ...)`` matters — if you ``.append(...)``, autograde
will fail with checksum mismatches because the auto-generated
autograder cells won't be picked up by nbgrader's ``SaveCells`` step.
See :doc:`nbgrader-pipeline` for why.


3. Write a quiz
===============

Replace the contents of ``source/ps1/problem1.ipynb`` (created by
``quickstart``) with a single Manually Graded Task cell carrying this
markdown:

.. code-block:: markdown

    ## Warm-up quiz

    #### Quiz
    * (SC) "What is the capital of France?"
      + "Paris"
      - "Berlin"
      - "Madrid"
    * (NM) "How many days are in a leap year?"
      + <366>
    #### End Quiz

To mark the cell as a Manually Graded Task: open the notebook in
JupyterLab, enable the nbgrader cell toolbar (*View → Activate
Command Palette → Enable nbgrader Cell Toolbar*), select the cell,
then choose *Manually Graded Task* in the dropdown that appears.
Give it a ``grade_id`` like ``warmup-quiz``.

Save the notebook.


4. Generate the release
=======================

Build the student-facing release:

.. code-block:: console

    nbgrader generate_assignment ps1 --force

You should see one info line per converted notebook.  The result
lives in ``release/ps1/problem1.ipynb``.  Open it — the markdown
cell looks the same to the reader, but nbgrader has appended a code
cell that calls :func:`~nbgrader_jupyterquiz.display_quiz`.  When
JupyterLab renders the notebook, that code cell produces the
interactive quiz widget.

The hidden span in the markdown source carries the question data
needed to render the widget; the answer key itself has been
**stripped** from that span and lives instead in a hidden-tests
block on the autograder cell.  See :doc:`graded-quizzes` for the
two-track storage model.


5. Answer the quiz
==================

Pretend you're a student.  Copy the release into the submitted
folder under a fake student id:

.. code-block:: console

    mkdir -p submitted/alice/ps1
    cp release/ps1/problem1.ipynb submitted/alice/ps1/

Open ``submitted/alice/ps1/problem1.ipynb`` in JupyterLab.  Run the
quiz cell — the widget appears.  Click *Paris*, then type ``366``
and press Enter on the numeric question.

You'll see neutral *Selected: "Paris".* and *Answer recorded: 366.*
feedback — the green / red colouring is hidden in graded mode so
students can't guess their way through.  In the same directory, a
``responses.json`` file appears containing your selections, keyed by
the cell's ``grade_id``.


6. Autograde
============

Back to instructor mode:

.. code-block:: console

    nbgrader autograde ps1 --force

nbgrader restores the hidden-tests block, re-executes the
autograder cell, and reads ``responses.json``.  The cell output now
shows a per-question review (your selection, the correct answer,
points earned), and the cell's bare ``_result.score`` expression
becomes the cell's grade in the gradebook.

Confirm:

.. code-block:: console

    nbgrader db assignment list
    nbgrader db student list

The score is recorded against the ``warmup-quiz`` grade_id.


7. Generate per-student feedback
================================

Optional, but it closes the loop:

.. code-block:: console

    nbgrader generate_feedback ps1

``feedback/alice/ps1/problem1.html`` now contains the cell output
(including the per-question review HTML), ready to hand back.


Where to go next
================

* :doc:`quiz-syntax` — the full authoring reference, including
  many-choice (``MC``), numeric ranges (``+ [min, max]``),
  per-question points (``{N}``), and code blocks.
* :doc:`graded-quizzes` — the design behind the auto-grading
  pipeline, the two-track storage of the answer key, and how to mix
  graded with self-check quizzes inside one task cell.
* :doc:`how-to/index` — focused recipes for common tasks.
* :doc:`display-options` — visual customisation, colour palettes,
  layout overrides.
