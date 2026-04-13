=========
Changelog
=========

`Unreleased <https://github.com/PhilippRisius/nbgrader-jupyterquiz>`_ (latest)
-------------------------------------------------------------------------

Contributors:

Changes
^^^^^^^
* No change.

Fixes
^^^^^
* No change.

.. _changes_0.2.0:

`v0.2.0 <https://github.com/PhilippRisius/nbgrader-jupyterquiz/tree/v0.2.0>`_ (2026-04-13)
----------------------------------------------------------------------------------------

Contributors: Philipp Emmo Tobias Risius (:user:`PhilippRisius`)

Changes
^^^^^^^
* Merged fork of `jupyterquiz`_ (v2.9.6.4) as ``nbgrader_jupyterquiz.display``
  subpackage, removing the external dependency.
* Ported nbgrader preprocessor and quiz parsing from the legacy plugin into
  ``nbgrader_jupyterquiz.grader``.
* Added unit tests for quiz parsing, schema validation, and encoding.

.. _jupyterquiz: https://github.com/jmshea/jupyterquiz
