import doctest
from packer import core


def test_core_doctests():
    res = doctest.testmod(core)
    assert res.failed == 0, f"Doctests failed: {res.failed} failures, {res.attempted} attempted"
