import doctest

from packer import cli, core


def test_core_doctests():
    res_core = doctest.testmod(core)
    res_cli = doctest.testmod(cli)
    failed = res_core.failed + res_cli.failed
    attempted = res_core.attempted + res_cli.attempted
    assert failed == 0, f"Doctests failed: {failed} failures, {attempted} attempted"
