"""Tests for KCCSettings configurability.

Verify that:
- Default settings produce the exact same args as the original hardcoded behaviour.
- Each setting is correctly reflected in the built invocation.
- CLI flags parse correctly and are threaded through to the invocation.
"""

from pathlib import Path

import pytest

from convertor.kcc_adapter import KCCAdapter, KCCInvocation, KCCSettings


_DEFAULT = KCCSettings()


def _build(tmp_path: Path, **overrides) -> list[str]:
    adapter = KCCAdapter()
    settings = _DEFAULT._replace(**overrides) if overrides else _DEFAULT
    inv = adapter.build_invocation(tmp_path / "vol", tmp_path / "out.kepub.epub", settings)
    assert isinstance(inv, KCCInvocation)
    return inv.args


class TestDefaultSettingsUnchanged:
    """Ensure defaults exactly match the original hardcoded invocation."""

    def test_profile(self, tmp_path):
        args = _build(tmp_path)
        assert "--profile" in args
        assert args[args.index("--profile") + 1] == "KoLC"

    def test_hq_enabled(self, tmp_path):
        assert "--hq" in _build(tmp_path)

    def test_rotation(self, tmp_path):
        args = _build(tmp_path)
        assert "-r" in args
        assert args[args.index("-r") + 1] == "2"

    def test_manga_style_enabled(self, tmp_path):
        assert "--manga-style" in _build(tmp_path)

    def test_forcecolor_enabled(self, tmp_path):
        assert "--forcecolor" in _build(tmp_path)

    def test_cropping(self, tmp_path):
        args = _build(tmp_path)
        assert "--cropping" in args
        assert args[args.index("--cropping") + 1] == "2"


class TestOverrides:
    def test_custom_profile(self, tmp_path):
        args = _build(tmp_path, profile="KoF")
        assert args[args.index("--profile") + 1] == "KoF"

    def test_hq_disabled(self, tmp_path):
        assert "--hq" not in _build(tmp_path, hq=False)

    def test_custom_rotation(self, tmp_path):
        args = _build(tmp_path, rotation=0)
        assert args[args.index("-r") + 1] == "0"

    def test_manga_style_disabled(self, tmp_path):
        assert "--manga-style" not in _build(tmp_path, manga_style=False)

    def test_forcecolor_disabled(self, tmp_path):
        assert "--forcecolor" not in _build(tmp_path, forcecolor=False)

    def test_cropping_off(self, tmp_path):
        args = _build(tmp_path, cropping=0)
        assert args[args.index("--cropping") + 1] == "0"


class TestCLIFlags:
    """Verify CLI args are parsed and thread through to the invocation."""

    def _run_main_dry(self, tmp_path: Path, extra_args: list[str]) -> list[str]:
        """Run the CLI in dry-run mode and capture the KCC invocation args."""
        import convertor.cli  # ensure module is imported before patching
        from unittest.mock import patch

        vol = tmp_path / "Serie v01"
        vol.mkdir()

        captured: list[list[str]] = []

        def fake_convert(volume_dir, out_path, dry_run=False, settings=KCCSettings()):
            captured.append(
                KCCAdapter().build_invocation(volume_dir, out_path, settings).args
            )
            return out_path

        with patch("convertor.cli.convert_volume", side_effect=fake_convert):
            convertor.cli.main([str(tmp_path)] + extra_args)

        assert captured, "convert_volume was not called"
        return captured[0]

    def test_default_cli_profile(self, tmp_path):
        args = self._run_main_dry(tmp_path, [])
        assert args[args.index("--profile") + 1] == "KoLC"

    def test_cli_custom_profile(self, tmp_path):
        args = self._run_main_dry(tmp_path, ["--profile", "KoF"])
        assert args[args.index("--profile") + 1] == "KoF"

    def test_cli_no_manga_style(self, tmp_path):
        args = self._run_main_dry(tmp_path, ["--no-manga-style"])
        assert "--manga-style" not in args

    def test_cli_no_hq(self, tmp_path):
        args = self._run_main_dry(tmp_path, ["--no-hq"])
        assert "--hq" not in args

    def test_cli_cropping_off(self, tmp_path):
        args = self._run_main_dry(tmp_path, ["--cropping", "0"])
        assert args[args.index("--cropping") + 1] == "0"
