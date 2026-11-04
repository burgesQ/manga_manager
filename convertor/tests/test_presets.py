"""Tests for ``convertor --preset {manga,comic}`` (roadmap item K1).

Verify that:
- the ``comic`` preset turns ``manga_style`` off (left-to-right) and keeps colour;
- the default (no ``--preset``) is unchanged from the historical manga defaults;
- explicit KCC flags always override the preset;
- ``--help`` lists the preset choices.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from convertor.cli import _build_parser, _build_settings, main
from convertor.kcc_adapter import PRESETS, KCCAdapter, KCCSettings


def _settings(argv: list[str]) -> KCCSettings:
    """Parse ``argv`` (root is prepended) and build the effective settings."""
    args = _build_parser().parse_args(["root", *argv])
    return _build_settings(args)


def _kcc_args(tmp_path: Path, extra_args: list[str]) -> list[str]:
    """Run ``main()`` with convert_volume mocked; return the KCC argv built."""
    (tmp_path / "Serie v01").mkdir()
    captured: list[list[str]] = []

    def fake_convert(volume_dir, out_path, dry_run=False, settings=KCCSettings()):
        captured.append(
            KCCAdapter().build_invocation(volume_dir, out_path, settings).args
        )
        return out_path

    with patch("convertor.cli.convert_volume", side_effect=fake_convert):
        rc = main([str(tmp_path), *extra_args])

    assert rc == 0
    assert captured, "convert_volume was not called"
    return captured[0]


class TestPresetsMapping:
    def test_manga_preset_is_historical_default(self):
        assert PRESETS["manga"] == KCCSettings()

    def test_comic_preset_only_differs_by_reading_direction(self):
        assert PRESETS["comic"] == KCCSettings()._replace(manga_style=False)
        assert PRESETS["comic"].forcecolor is True

    def test_preset_names(self):
        assert sorted(PRESETS) == ["comic", "manga"]


class TestBuildSettings:
    def test_default_is_manga(self):
        assert _settings([]) == KCCSettings()

    def test_explicit_manga_preset(self):
        assert _settings(["--preset", "manga"]) == KCCSettings()

    def test_comic_preset_is_left_to_right(self):
        settings = _settings(["--preset", "comic"])
        assert settings.manga_style is False
        assert settings.forcecolor is True

    def test_explicit_manga_style_beats_comic_preset(self):
        assert _settings(["--preset", "comic", "--manga-style"]).manga_style is True

    def test_explicit_no_manga_style_beats_manga_preset(self):
        assert _settings(["--preset", "manga", "--no-manga-style"]).manga_style is False

    def test_other_overrides_apply_on_top_of_preset(self):
        settings = _settings(
            ["--preset", "comic", "--profile", "KoF", "--rotation", "0", "--no-hq"]
        )
        assert settings == PRESETS["comic"]._replace(
            profile="KoF", rotation=0, hq=False
        )

    def test_unset_flags_parse_as_none(self):
        args = _build_parser().parse_args(["root"])
        assert args.preset == "manga"
        for field in KCCSettings._fields:
            assert getattr(args, field) is None, field

    def test_namespace_without_preset_falls_back_to_manga(self):
        # Defensive: a hand-built Namespace (e.g. from another caller) with no
        # preset attribute must still yield the manga defaults.
        assert _build_settings(argparse.Namespace()) == KCCSettings()

    def test_rejects_unknown_preset(self):
        with pytest.raises(SystemExit):
            _build_parser().parse_args(["root", "--preset", "webtoon"])


class TestMainWithPreset:
    def test_comic_preset_drops_manga_style_arg(self, tmp_path):
        args = _kcc_args(tmp_path, ["--preset", "comic"])
        assert "--manga-style" not in args
        assert "--forcecolor" in args

    def test_default_keeps_manga_style_arg(self, tmp_path):
        args = _kcc_args(tmp_path, [])
        assert "--manga-style" in args
        assert "--forcecolor" in args
        assert args[args.index("--profile") + 1] == "KoLC"

    def test_override_beats_preset_in_kcc_args(self, tmp_path):
        args = _kcc_args(tmp_path, ["--preset", "comic", "--manga-style"])
        assert "--manga-style" in args

    def test_logs_reading_direction_comic(self, tmp_path, capsys):
        _kcc_args(tmp_path, ["--preset", "comic"])
        assert "Reading direction: left-to-right (comic preset)" in (
            capsys.readouterr().err
        )

    def test_logs_reading_direction_manga(self, tmp_path, capsys):
        _kcc_args(tmp_path, [])
        assert "Reading direction: right-to-left (manga preset)" in (
            capsys.readouterr().err
        )


def test_help_lists_preset_choices(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--preset {comic,manga}" in out
