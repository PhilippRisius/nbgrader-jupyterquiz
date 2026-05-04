===========
Quiz Syntax
===========

**nbgrader-jupyterquiz** uses a lightweight Markdown syntax to define quizzes
inside notebook cells.  During ``nbgrader generate_assignment``, the
:class:`~nbgrader_jupyterquiz.CreateQuiz`
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

Text placed on the same line as ``#### Quiz``, after the delimiter, configures
how the quiz data is embedded.  Options are space-separated ``key=value`` pairs;
boolean values are ``true`` or ``false`` (case-insensitive).  Unrecognised keys
are silently ignored.

.. list-table::
   :header-rows: 1
   :widths: 20 10 70

   * - Option
     - Default
     - Description
   * - ``encoded``
     - ``true``
     - Base64-encode the question data before embedding it in the notebook.
   * - ``inline``
     - ``true``
     - Embed the question data directly in the markdown cell source.
       When ``false``, the data is referenced by notebook name instead.
   * - ``hidden``
     - ``true``
     - When ``inline=true``, wrap the embedded data in a
       ``<span style="display:none">`` so it is not visible to students.
       Has no effect when ``inline=false``.
   * - ``filename``
     - *(none)*
     - Write question data to this file path instead of embedding it inline.
       Overrides the ``inline`` option.

Example — plain JSON written to a file::

    #### Quiz encoded=false filename=quiz_data.json

Question types
--------------

Every question line begins with ``*`` followed by a type code in parentheses
and the question text in double quotes.

+--------+------------------+------------------------------------+
| Code   | Type             | Description                        |
+========+==================+====================================+
| ``SC`` | Single choice    | Exactly one correct answer         |
|        |                  | (enforced — any other count is a   |
|        |                  | ``ParseError``)                    |
+--------+------------------+------------------------------------+
| ``MC`` | Many choice      | Any number of correct answers;     |
|        |                  | 0 or 1 correct answers logs a      |
|        |                  | warning (likely meant ``SC``)      |
+--------+------------------+------------------------------------+
| ``NM`` | Numeric          | Student enters a number            |
+--------+------------------+------------------------------------+

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
     - Number of columns for the answer layout.  Default: 2 (CSS default;
       reduced to 1 automatically on narrow screens).
   * - ``{N}``
     - all (graded quizzes)
     - Points the question is worth.  ``N`` may be any positive number,
       including fractions (``{0.5}``).  Default: 1.  Shown to the
       student as a small badge next to the question text; when at least
       one question in a quiz carries an explicit ``{N}`` marker, every
       sibling gets a badge too (unweighted questions as ``1 pt``).  The
       autograder awards ``N`` points on a correct answer and zero
       otherwise; the cell's total max_score is the sum over its
       questions.  See :doc:`graded-quizzes`.

Quiz-level options
~~~~~~~~~~~~~~~~~~

Options appear on the ``#### Quiz`` opening line as space-separated
``key=value`` pairs.  In addition to the display options (``encoded``,
``inline``, ``hidden``, ``filename``) documented in the JupyterQuiz
fork, nbgrader-jupyterquiz adds two options that control grading:

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Option
     - Default
     - Description
   * - ``graded=true`` / ``graded=false``
     - ``true``
     - Opt this quiz out of auto-grading.  Default is ``true``: a quiz
       inside a Manually Graded Task cell is auto-graded.  Use
       ``graded=false`` to keep the quiz as a plain self-check
       (correctness feedback visible, no points awarded by the quiz)
       while the surrounding task is still manually graded via the
       task cell's own ``points`` field.
   * - ``hide_correctness=true`` / ``hide_correctness=false``
     - matches ``graded``
     - Whether to hide correctness feedback during answering.  Default
       tracks ``graded``: hidden when graded, visible when not.
       Override in either direction (e.g. ``graded=false
       hide_correctness=true`` for a quiz that neither grades nor
       reveals answers — useful for study mode).  When hide mode is
       on, the answer key (``correct`` flags, numeric ``value`` /
       ``range`` matches) is stripped from the embedded display JSON
       — students cannot recover the key from the DOM.  The autograder
       reads its own copy from a separate hidden-tests block.

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

Code blocks (`` ```...``` ``) may span multiple physical source lines —
write them as you would a markdown fenced-code block.  Leading and
trailing newlines around the content are stripped automatically.  The
older single-line convention with literal ``\n`` continues to work.

.. code-block:: markdown

    #### Quiz
    * (SC) "What does this Python function do?" ```
    def f(x):
        return x ** 2
    ```
      + "It squares its argument."
      - "It doubles its argument."
      - "It returns the absolute value."
    #### End Quiz

Special characters in fields
----------------------------

The parser uses surrounding characters as field delimiters: ``"..."`` for
text and answer content, ``(...)`` for feedback, ``[...]`` for numeric
ranges and precision, ``<...>`` for numeric values and answer-column
counts, ``{...}`` for points, and `` ```...``` `` for code blocks.
Each field type accepts the special characters that would otherwise
collide with its delimiters:

* **Paired delimiters** (``(...)``, ``[...]``, ``{...}``, ``<...>``)
  balance their own pair.  ``(Correct (with caveats))`` is one
  feedback field with content ``Correct (with caveats)``; the inner
  ``()`` is just text.  Other delimiter characters (``{``, ``[``,
  ``"``, etc.) inside are inert: ``(feedback { )`` parses cleanly
  even though the ``{`` has no matching ``}``.  An *unmatched*
  same-pair character (like an emoticon ``:(``) needs a backslash
  escape: ``(Sad face :\(.)`` parses as ``Sad face :(.``.  Same
  rule for ``\)``, ``\\``, and the equivalents in other paired
  delimiters.
* **Quoted text** (``"..."``) accepts ``\"`` for a literal ``"`` and
  ``\\`` for a literal ``\``.  Other backslash sequences pass through
  unchanged, so LaTeX commands like ``$\int$``, ``$\alpha$``, and
  ``$\tfrac{1}{2}$`` work without doubling.
* **Code blocks** (`` ```...``` ``) tolerate ``"``, ``(``, ``)``,
  ``\``, etc. freely — the parser only stops at the closing
  triple-backtick.

Multi-line fields
-----------------

Any delimited field may span multiple physical source lines.  The
continuation rule follows markdown-list indentation: continuation
lines must be indented strictly more than the opening line's first
non-whitespace column (column ``0`` for question lines, column ``2``
for answer lines).  Code blocks are an exception — indentation is
not checked, and any subsequent line is part of the block until the
closing triple-backtick is reached, matching markdown's fenced-code
semantics.

.. code-block:: markdown

    #### Quiz
    * (SC) "Long question text
        that wraps across two lines"
      + "Answer with multi-line
        feedback" (this feedback
        also spans
        multiple lines)
    #### End Quiz

A field that doesn't close before indentation drops back to the
opener's column — or before the quiz region ends — raises a
``ParseError`` naming the unclosed delimiter.

Remaining limitations
---------------------

* **Embedded triple-backticks inside a code block** — the parser
  stops at the first triple-backtick it sees.  Showing literal
  triple-backtick syntax in a quiz prompt is not supported.
