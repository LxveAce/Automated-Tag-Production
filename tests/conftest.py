"""Shared test fixtures.

The application lives in a single source file whose name contains spaces, so it
is loaded by path via importlib rather than a normal import.
"""
import importlib.util
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "Automated Tag Creator V5 by LxveAce -Source Code.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("tag_core_under_test", _SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def tag():
    """The application module, loaded once per test session."""
    return _load_module()
