=========
Changelog
=========

..
    `Unreleased <https://github.com/PhilippRisius/nbgrader-jupyterquiz>`_ (latest)
    ------------------------------------------------------------------------------

    Contributors: Philipp Emmo Tobias Risius (:user:`PhilippRisius`)

    Developed with assistance from Claude (Anthropic) — see commit trailers
    for per-commit attribution.

    Changes
    ^^^^^^^
    * Added **graded-quiz mode**: quizzes inside nbgrader Manually Graded
      Task cells are now auto-graded end-to-end.  Student responses are
      persisted to a ``responses.json`` sidecar as they answer;
      ``nbgrader autograde`` reads the sidecar and awards partial
      credit.  Introduces :func:`~nbgrader_jupyterquiz.grade_quiz`, the
      ``QuizResult`` / ``QuestionResult`` dataclasses, and a static HTML
      review rendered into the autograded cell output (visible in
      ``generate_feedback``).  Cross-frontend (JupyterLab 4, Notebook 7,
      classic Notebook); VS Code's Jupyter extension is not supported.
    * Added the ``{N}`` question-line marker for per-question points,
      supporting fractional weights (e.g. ``{0.5}``).  Points render as a
      badge next to each question; the badge-display rule is "show on
      every question iff at least one question in the quiz carries an
      explicit ``{N}``".
    * Added quiz-level ``graded=false`` option to opt a single quiz out
      of auto-grading inside a task cell (self-check mode) while leaving
      the task cell's own ``points`` intact for any manual grading of
      surrounding content.  Added quiz-level ``hide_correctness``
      override, independently toggleable from ``graded``.
    * Added hide-correctness feedback mode (auto-enabled for graded
      quizzes) — MC/many-choice/numeric questions show a neutral
      "Selected: … / Deselected: …" state instead of green/red so
      students can't guess their way to the right answer.
    * Replaced ``<label>``+hidden ``<input type=radio>`` with a plain
      ``<button type=button>`` for MC answers.  Eliminates the
      label→radio click synthesis that otherwise double-fired the click
      handler in hide-mode toggles.
    * Added a dedicated :doc:`graded-quizzes <graded-quizzes>`
      documentation page covering the workflow end-to-end.
    * Instructor config changed: register ``CreateQuiz`` with
      ``c.GenerateAssignment.preprocessors.insert(0, ...)`` (not
      ``.append(...)``).  The new auto-generated autograder cells must
      run before nbgrader's ``SaveCells`` and ``ClearHiddenTests``.
    * Added string question schema (``validate.Schema.STR``).  The
      previous ``SCHEMATA`` dispatch was missing the string type —
      constructing a string-type question dict raised ``KeyError``
      before schema validation.

    Fixes
    ^^^^^
    * ``nbgrader-pipeline.rst`` no longer refers to the deprecated
      ``nbgrader assign`` command — it's ``generate_assignment`` in
      nbgrader ≥ 0.9.
    * Numeric range display bug: ``+ [0, 10]`` now includes the upper
      bound (``10`` was previously rejected due to a strict ``<``
      comparison) and the match is no longer gated on
      ``answer.feedback`` being set.  Reported during v0.3.0
      end-to-end validation.

.. _changes_0.3.0:

`v0.3.0 <https://github.com/PhilippRisius/nbgrader-jupyterquiz/tree/v0.3.0>`_ (2026-04-14)
--------------------------------------------------------------------------------------------------------------

Contributors: Philipp Emmo Tobias Risius (:user:`PhilippRisius`)

Developed with assistance from Claude (Anthropic) — see commit trailers for
per-commit attribution.

Changes
^^^^^^^
* Implemented quiz-level option parsing (``parse_quiz_options``) — the
  ``#### Quiz`` header now accepts ``encoded``, ``inline``, ``hidden``, and
  ``filename`` options as space-separated ``key=value`` pairs
  (:pull:`12`).
* Added a preprocessor test suite covering the happy path, cell
  transformation, multi-quiz notebooks, ``enforce_metadata``, ``ParseError``
  handling, all four option modes, and filesystem edge cases — 21 tests,
  100 % line coverage of ``grader/preprocessor.py`` (:pull:`12`).
* Added a display-module test suite covering colour-palette key symmetry,
  ``display_quiz`` parameter guards, ``build_styles`` CSS injection, and
  ``load_questions_script`` loader paths — 9 tests (:pull:`12`).
* Added a ``docs`` CI job (``tox -e docs`` with ``-W --keep-going``) so
  Sphinx build failures are caught on every PR, not only after ReadTheDocs
  runs (:pull:`13`).
* Refactored the display colour palettes ``_DEFAULT_COLORS`` and
  ``_FDSP_COLORS`` to module-level constants (no behaviour change; enables
  palette-symmetry tests) (:pull:`12`).
* Added the initial public documentation set: quiz-syntax reference,
  nbgrader-pipeline integration guide, and display-options reference; plus
  a Diataxis-guided correction pass against the actual code behaviour
  (:pull:`11`).
* Documented quiz-level options with a reference table in
  ``docs/quiz-syntax.rst`` (:pull:`12`).

Fixes
^^^^^
* Registered an ``autodoc-skip-member`` handler in ``docs/conf.py`` to
  prevent duplicate-object-description warnings for symbols re-exported
  via ``__init__.__all__``; the ReadTheDocs build now passes under
  ``fail_on_warning: true`` (:pull:`13`).
* Resolved all outstanding Sphinx build warnings in the initial docs set
  (:pull:`11`).
* Dropped ``Exception.add_note()`` from ``grader/preprocessor.py`` — the
  call required Python 3.11+ (PEP 678) but the project targets 3.10+
  (:pull:`12`).
* Widened the ``sphinx`` version constraint from ``<8.2`` to ``>=8.1.3``
  so the ``tox -e docs`` environment installs the same major version as
  ReadTheDocs (:pull:`13`).
* Bumped ``pip`` to 26.0 to address
  `GHSA-4xh5-x5gv-qwph <https://github.com/advisories/GHSA-4xh5-x5gv-qwph>`_
  and
  `GHSA-6vgw-5pg2-w6jp <https://github.com/advisories/GHSA-6vgw-5pg2-w6jp>`_
  (:pull:`9`).

.. _changes_0.2.0:

`v0.2.0 <https://github.com/PhilippRisius/nbgrader-jupyterquiz/tree/v0.2.0>`_ (2026-04-13)
------------------------------------------------------------------------------------------

Contributors: Philipp Emmo Tobias Risius (:user:`PhilippRisius`)

Changes
^^^^^^^
* Merged fork of `jupyterquiz`_ (v2.9.6.4) as ``nbgrader_jupyterquiz.display``
  subpackage, removing the external dependency.
* Ported nbgrader preprocessor and quiz parsing from the legacy plugin into
  ``nbgrader_jupyterquiz.grader``.
* Added unit tests for quiz parsing, schema validation, and encoding.

.. _jupyterquiz: https://github.com/jmshea/jupyterquiz
