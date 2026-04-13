"""Smoke tests — verify the package imports and exposes its public API."""

import nbgrader_jupyterquiz


def test_version():
    assert isinstance(nbgrader_jupyterquiz.__version__, str)
    assert nbgrader_jupyterquiz.__version__ != ""


def test_all_exports_importable():
    for name in nbgrader_jupyterquiz.__all__:
        assert hasattr(nbgrader_jupyterquiz, name), f"{name!r} listed in __all__ but not importable"
