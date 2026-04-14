"""
Display subpackage — forked from jupyterquiz by John M. Shea (MIT).

Provides interactive quiz display for Jupyter notebooks and Jupyter Books.

This subpackage is a fork of jupyterquiz 2.9.6.4
(https://github.com/jmshea/jupyterquiz), authored by John M. Shea.
Original code copyright (c) 2021-2025 John M. Shea, used under the MIT
License.  See LICENSES/jupyterquiz-MIT.txt in the source distribution.
Modifications by Philipp Risius for nbgrader integration and dark-mode
support.
"""

from .dynamic import capture_responses, display_quiz


__all__ = ["capture_responses", "display_quiz"]
