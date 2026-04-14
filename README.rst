======================
nbgrader-jupyterquiz
======================

+----------------------------+-----------------------------------------------------+
| Open Source                | |license| |ossf-score|                              |
+----------------------------+-----------------------------------------------------+
| Coding Standards           | |ruff| |pre-commit|                                 |
+----------------------------+-----------------------------------------------------+
| Development Status         | |status| |build|                                    |
+----------------------------+-----------------------------------------------------+

**nbgrader-jupyterquiz** lets instructors embed interactive, gradeable quizzes
directly inside Jupyter notebooks using a simple Markdown syntax.  During
``nbgrader assign`` the quiz source is transformed into interactive quiz cells
(powered by a fork of `jupyterquiz`_); correct answers are hidden from students
before the assignment is released.

* Free software: MIT license

Installation
------------

.. code-block:: console

    pip install nbgrader-jupyterquiz

Quiz authoring syntax
---------------------

Write quizzes in Markdown cells using ``#### Quiz`` / ``#### End Quiz``
delimiters.  Each question begins with ``* (TYPE) "question text"`` and its
answers follow on indented lines: ``+`` for correct, ``-`` for incorrect.

**Question types**

+--------+-------------------+-------------------------------------------+
| Type   | Name              | Notes                                     |
+========+===================+===========================================+
| ``SC`` | Single choice     | Exactly one correct answer                |
+--------+-------------------+-------------------------------------------+
| ``MC`` | Many choice       | One or more correct answers               |
+--------+-------------------+-------------------------------------------+
| ``NM`` | Numeric           | Accepts a value, range, or default catch  |
+--------+-------------------+-------------------------------------------+

**Example cell**

.. code-block:: markdown

    Some introductory text for the exercise.

    #### Quiz
    * (SC) "What is the capital of France?"
      + (Correct!) "Paris"
      - "London"
      - "Berlin"

    * (NM) "What is the square root of 144?" [0]
      + <12.0>
      - (Not quite.) [1.0, 200.0]

    * (MC) "Which of the following are prime numbers?"
      + "2"
      + "3"
      - "4"
      + "5"
    #### End Quiz

**Answer syntax**

- ``(feedback text)`` — optional feedback shown after the student answers
- ``"answer text"`` — the answer label (required for SC/MC)
- ``<value>`` — exact numeric answer
- ``[min, max]`` — accepted numeric range
- ``[precision]`` — number of decimal places to display (NM questions)

nbgrader integration
--------------------

Register ``CreateQuiz`` as a preprocessor in your ``nbgrader_config.py``:

.. code-block:: python

    c.GenerateAssignment.preprocessors = [
        "nbgrader_jupyterquiz.CreateQuiz",
    ]

During ``nbgrader assign``, quiz regions are extracted from each Markdown cell
and replaced with interactive ``display_quiz()`` code cells.  Correct answers
are base64-encoded and embedded in a hidden ``<span>`` so they are not visible
to students in the released notebook.

The quiz cells must be inside **Manually Graded Task** cells in nbgrader's
cell toolbar to participate in the grading pipeline.

Credits
-------

This package incorporates a fork of `jupyterquiz`_ (v2.9.6.4) by
John M. Shea, copyright 2021–2025, used under the MIT License.
See ``LICENSES/jupyterquiz-MIT.txt``.

This package was scaffolded with Cookiecutter_ and the
`Ouranosinc/cookiecutter-pypackage`_ project template.

.. _jupyterquiz: https://github.com/jmshea/jupyterquiz
.. _Cookiecutter: https://github.com/cookiecutter/cookiecutter
.. _`Ouranosinc/cookiecutter-pypackage`: https://github.com/Ouranosinc/cookiecutter-pypackage

.. |build| image:: https://github.com/PhilippRisius/nbgrader-jupyterquiz/actions/workflows/main.yml/badge.svg
        :target: https://github.com/PhilippRisius/nbgrader-jupyterquiz/actions
        :alt: Build Status

.. |license| image:: https://img.shields.io/github/license/PhilippRisius/nbgrader-jupyterquiz.svg
        :target: https://github.com/PhilippRisius/nbgrader-jupyterquiz/blob/main/LICENSE
        :alt: License

..
    .. |ossf-bp| image:: https://bestpractices.coreinfrastructure.org/projects/9945/badge
            :target: https://bestpractices.coreinfrastructure.org/projects/9945
            :alt: Open Source Security Foundation Best Practices

.. |ossf-score| image:: https://api.securityscorecards.dev/projects/github.com/PhilippRisius/nbgrader-jupyterquiz/badge
        :target: https://securityscorecards.dev/viewer/?uri=github.com/PhilippRisius/nbgrader-jupyterquiz
        :alt: OpenSSF Scorecard

.. |pre-commit| image:: https://results.pre-commit.ci/badge/github/PhilippRisius/nbgrader-jupyterquiz/main.svg
        :target: https://results.pre-commit.ci/latest/github/PhilippRisius/nbgrader-jupyterquiz/main
        :alt: pre-commit.ci status

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
        :target: https://github.com/astral-sh/ruff
        :alt: Ruff

.. |status| image:: https://www.repostatus.org/badges/latest/wip.svg
        :target: https://www.repostatus.org/#wip
        :alt: Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.
