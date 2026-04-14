======================
nbgrader-jupyterquiz
======================

+----------------------------+-----------------------------------------------------+
| Versions                   | |pypi|                                              |
+----------------------------+-----------------------------------------------------+
| Documentation and Support  | |docs| |versions|                                   |
+----------------------------+-----------------------------------------------------+
| Open Source                | |license| |ossf-score|                              |
+----------------------------+-----------------------------------------------------+
| Coding Standards           | |ruff| |pre-commit|                                 |
+----------------------------+-----------------------------------------------------+
| Development Status         | |status| |build| |coveralls|                        |
+----------------------------+-----------------------------------------------------+

**nbgrader-jupyterquiz** lets instructors embed interactive, gradeable quizzes
directly inside Jupyter notebooks using a simple Markdown syntax.  During
``nbgrader assign`` the quiz source is transformed into interactive quiz cells
(powered by a fork of `jupyterquiz`_); correct answers are hidden from students
before the assignment is released.

* Free software: MIT license
* Documentation: https://nbgrader-jupyterquiz.readthedocs.io

Installation
------------

.. code-block:: console

    pip install nbgrader-jupyterquiz

Quick start
-----------

Register the preprocessor in ``nbgrader_config.py``:

.. code-block:: python

    c.GenerateAssignment.preprocessors = [
        "nbgrader_jupyterquiz.CreateQuiz",
    ]

Write quizzes in **Manually Graded Task** cells using ``#### Quiz`` /
``#### End Quiz`` delimiters:

.. code-block:: markdown

    #### Quiz
    * (SC) "What is the capital of France?"
      + (Correct!) "Paris"
      - "London"
      - "Berlin"
    #### End Quiz

Run ``nbgrader assign`` — quiz regions are replaced with interactive widgets
and correct answers are hidden from students.

See the `documentation <https://nbgrader-jupyterquiz.readthedocs.io>`_ for the
full `quiz syntax <https://nbgrader-jupyterquiz.readthedocs.io/en/latest/quiz-syntax.html>`_,
`nbgrader pipeline <https://nbgrader-jupyterquiz.readthedocs.io/en/latest/nbgrader-pipeline.html>`_,
and `display options <https://nbgrader-jupyterquiz.readthedocs.io/en/latest/display-options.html>`_.

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

.. |pypi| image:: https://img.shields.io/pypi/v/nbgrader-jupyterquiz.svg
        :target: https://pypi.org/project/nbgrader-jupyterquiz/
        :alt: PyPI

.. |docs| image:: https://readthedocs.org/projects/nbgrader-jupyterquiz/badge/?version=latest
        :target: https://nbgrader-jupyterquiz.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status

.. |versions| image:: https://img.shields.io/pypi/pyversions/nbgrader-jupyterquiz.svg
        :target: https://pypi.org/project/nbgrader-jupyterquiz/
        :alt: Supported Python Versions

.. |coveralls| image:: https://coveralls.io/repos/github/PhilippRisius/nbgrader-jupyterquiz/badge.svg
        :target: https://coveralls.io/github/PhilippRisius/nbgrader-jupyterquiz
        :alt: Coveralls

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
