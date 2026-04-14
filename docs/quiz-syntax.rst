===========
Quiz Syntax
===========

**nbgrader-jupyterquiz** uses a lightweight Markdown syntax to define quizzes
inside notebook cells.  During ``nbgrader assign``, the :class:`~nbgrader_jupyterquiz.CreateQuiz`
preprocessor converts these regions into interactive quiz cells powered by the
bundled jupyterquiz display layer.

Quiz regions
------------

Wrap one or more questions between ``#### Quiz`` and ``#### End Quiz`` delimiters.
Any text outside these delimiters is left in the cell unchanged.

.. code-block:: markdown

    Some introductory prose.

    #### Quiz
    * (SC) "Which planet is closest to the Sun?"
      + "Mercury"
      - "Venus"
      - "Earth"
    #### End Quiz

    Some concluding prose.

A cell may contain multiple quiz regions; each becomes its own quiz widget.
Delimiters may not be nested.

Quiz-level options
------------------

Text placed on the same line as ``#### Quiz``, after the delimiter, is reserved
for quiz-level options (e.g. ``#### Quiz encoded=false hidden=false``).  Parsing
of these options is **not yet implemented** — they are accepted but ignored.  The
default behaviour (encoded, inline, hidden) applies regardless.

Question types
--------------

Every question line begins with ``*`` followed by a type code in parentheses
and the question text in double quotes.

+--------+------------------+-------------------------------------------+
| Code   | Type             | Description                               |
+========+==================+===========================================+
| ``SC`` | Single choice    | Exactly one correct answer; radio buttons |
+--------+------------------+-------------------------------------------+
| ``MC`` | Many choice      | One or more correct answers; checkboxes   |
+--------+------------------+-------------------------------------------+
| ``NM`` | Numeric          | Student enters a number                   |
+--------+------------------+-------------------------------------------+

Question options
~~~~~~~~~~~~~~~~

Additional options may appear in any order after the type code on the question
line.

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Syntax
     - Applies to
     - Description
   * - ``"question text"``
     - all
     - The question text displayed to the student.
   * - \`\`\`code\`\`\`
     - all
     - A code block displayed as (or instead of) the question text.
   * - ``[N]``
     - ``NM`` only
     - Precision: the answer is rounded to *N* significant digits before
       comparison.  If omitted, exact equality is required.
   * - ``<N>``
     - all
     - Number of columns for the answer layout (default: 1).

Answer lines
------------

Answer lines immediately follow the question line and must be indented with two
spaces.  A ``+`` prefix marks a correct answer; ``-`` marks an incorrect one.

Single choice and many choice answers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each answer line may contain, in any order:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Syntax
     - Description
   * - ``"answer text"``
     - The answer option shown to the student.
   * - `` ```code``` ``
     - A code block shown as (or instead of) the answer text.
   * - ``(feedback text)``
     - Message shown to the student after they select this answer.

Numeric answers
~~~~~~~~~~~~~~~

Each answer line for a numeric question specifies one of three forms:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Syntax
     - Description
   * - ``<value>``
     - Matches the student's input exactly (subject to ``[precision]``).
   * - ``[min, max]``
     - Matches any value in the closed interval ``[min, max]``.
   * - *(neither)*
     - A *default* catch-all that matches any input not covered by another
       answer.  At most one default answer should be present per question.
   * - ``(feedback text)``
     - May be combined with any of the above forms.

Examples
--------

Single-choice question
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: markdown

    #### Quiz
    * (SC) "What is 2 + 2?" <2>
      + "4"             (Correct!)
      - "3"             (Close, but not quite.)
      - "5"
    #### End Quiz

Many-choice question
~~~~~~~~~~~~~~~~~~~~

.. code-block:: markdown

    #### Quiz
    * (MC) "Which of the following are prime numbers?"
      + "2"
      + "3"
      - "4"             (4 = 2 × 2)
      + "5"
    #### End Quiz

Numeric question
~~~~~~~~~~~~~~~~

.. code-block:: markdown

    #### Quiz
    * (NM) "What is the speed of light in m/s? (Enter as a float, 3 sig. figs.)" [3]
      + <3.00e8>        (Correct!)
      - [2.50e8, 2.99e8] (A little low — did you use the right units?)
      - [3.01e8, 3.50e8] (A little high — double-check your source.)
      - (Neither of the above.)
    #### End Quiz

Code-block question
~~~~~~~~~~~~~~~~~~~

.. code-block:: markdown

    #### Quiz
    * (SC) ```def f(x):
        return x ** 2```
      + "It squares its argument."
      - "It doubles its argument."
      - "It returns the absolute value."
    #### End Quiz
