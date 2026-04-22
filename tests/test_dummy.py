# tests/test_dummy.py
# This is a dummy test module.

import warnings


def test_placeholder():
    warnings.warn("This is a dummy test.", UserWarning)
    assert True
