===============
Display Options
===============

In student notebooks, quizzes are rendered by
:func:`~nbgrader_jupyterquiz.display_quiz`.  This function is called
automatically by the code cells that :class:`~nbgrader_jupyterquiz.CreateQuiz`
generates during ``nbgrader generate_assignment``, but you can also call it
directly when working with quizzes outside the nbgrader pipeline.

.. autofunction:: nbgrader_jupyterquiz.display_quiz
   :no-index:

Reference source
----------------

The ``ref`` argument determines where question data is loaded from.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Type
     - Description
   * - ``list``
     - A Python list of question dictionaries (see :doc:`quiz-syntax`).
   * - ``"#name:tag"``
     - A CSS identifier.  The element is looked up first by ``id``, then by
       ``class`` name.  Its ``innerHTML`` is parsed as JSON (plain or
       base64-encoded).  This is the format ``CreateQuiz``-generated cells use
       to reference hidden answer spans (e.g. ``"#unique_key:0.0"``).
   * - ``"https://..."``
     - An HTTP/HTTPS URL pointing to a JSON file.
   * - ``"path/to/file.json"``
     - A local file path to a JSON file.

Display parameters
------------------

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Default
     - Description
   * - ``num``
     - ``int``
     - all
     - Maximum number of questions to show.  A random subset is chosen each
       time the cell is executed.  Incompatible with ``preserve_responses``.
   * - ``shuffle_questions``
     - ``bool``
     - ``False``
     - Randomise question order each time the cell is executed.  Incompatible
       with ``preserve_responses``.
   * - ``shuffle_answers``
     - ``bool``
     - ``True``
     - Randomise answer option order each time the cell is executed.
   * - ``preserve_responses``
     - ``bool``
     - ``False``
     - Keep student responses visible after answering.  Requires fixed question
       order (``shuffle_questions=False``) and all questions displayed
       (``num`` unset).
   * - ``border_radius``
     - ``int``
     - ``10``
     - CSS ``border-radius`` of the question boxes, in pixels.
   * - ``question_alignment``
     - ``str``
     - ``"left"``
     - Text alignment inside question boxes.  One of ``"left"``,
       ``"center"``, ``"right"``.
   * - ``max_width``
     - ``int``
     - ``600``
     - Maximum width of the quiz widget, in pixels.
   * - ``colors``
     - ``dict`` or ``str``
     - default palette
     - Colour customisation.  Pass ``"fdsp"`` for the alternate palette, or a
       ``dict`` of CSS variable overrides (see :ref:`display-options:Colour customisation`).
   * - ``load_js``
     - ``bool``
     - ``True``
     - Whether to inline the JavaScript source.  Set to ``False`` only if the
       jupyterquiz JavaScript is already loaded on the page.

Colour customisation
--------------------

Pass a dictionary to ``colors`` to override individual CSS variables.  Any
variables not included in the dictionary retain their default values.

.. code-block:: python

    from nbgrader_jupyterquiz import display_quiz

    display_quiz(questions, colors={
        "--jq-multiple-choice-bg": "#1a1a2e",
        "--jq-correct-color": "#00b894",
    })

Pass ``colors="fdsp"`` to switch to the alternate *fdsp* palette entirely.

Available CSS variables:

.. list-table::
   :header-rows: 1
   :widths: 40 20 40

   * - Variable
     - Default
     - Description
   * - ``--jq-multiple-choice-bg``
     - ``#392061``
     - Background of single-choice question boxes
   * - ``--jq-many-choice-bg``
     - ``#f75c03``
     - Background of many-choice question boxes
   * - ``--jq-numeric-bg``
     - ``#392061``
     - Background of numeric question boxes
   * - ``--jq-mc-button-bg``
     - ``#fafafa``
     - Answer button background
   * - ``--jq-mc-button-border``
     - ``#e0e0e0e0``
     - Answer button border colour (88 % opacity)
   * - ``--jq-mc-button-inset-shadow``
     - ``#555555``
     - Answer button inset shadow colour
   * - ``--jq-numeric-input-bg``
     - ``#c0c0c0``
     - Numeric input field background
   * - ``--jq-numeric-input-label``
     - ``#101010``
     - Numeric input field label colour
   * - ``--jq-numeric-input-shadow``
     - ``#999999``
     - Numeric input field shadow colour
   * - ``--jq-string-bg``
     - ``#4c1a57``
     - Background of string-type question boxes
   * - ``--jq-correct-color``
     - ``#009113``
     - Highlight colour for correct answers
   * - ``--jq-incorrect-color``
     - ``#c80202``
     - Highlight colour for incorrect answers
   * - ``--jq-text-color``
     - ``#fafafa``
     - Question and answer text colour
   * - ``--jq-link-color``
     - ``#9abafa``
     - Link colour inside questions

Capturing responses
-------------------

Persistent answer capture for graded quizzes is handled automatically by
placing the quiz inside a Manually Graded Task cell — the preprocessor
wires up the recorder and autograder for you.  See
:doc:`graded-quizzes`.
