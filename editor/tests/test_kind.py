"""Tests for the top-level ``kind: manga|comic`` metadata key (roadmap item K4)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("ebooklib")

from editor.cli import main
from editor.editor_full import (
    EPUBMetadata,
    _apply_kind_tag,
    _kind_from_tags,
    dump_metadata,
    inject_metadata,
)
from editor.exit_codes import ERROR, SUCCESS

KIND_TAG = {"comic": "Comic", "manga": "Manga"}


def _meta(**extra) -> dict:
    data = {
        "series": "Saga",
        "author": "Brian K. Vaughan",
        "volumes": [{"number": 1, "title": "Volume One"}],
    }
    data.update(extra)
    return data


def _setup(tmp_path: Path, make_epub, make_yaml, **extra) -> tuple[Path, Path, Path]:
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    book = make_epub(epub_dir / "Saga v01.epub", author=None)
    yaml_path = make_yaml(tmp_path / "meta.yaml", _meta(**extra))
    return epub_dir, book, yaml_path


def _tags(book: Path) -> list[str] | None:
    return EPUBMetadata(book).get_metadata().get("tags")


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestApplyKindTag:
    def test_no_kind_returns_tags_unchanged(self):
        tags = ["Seinen"]
        assert _apply_kind_tag(tags, None) is tags
        assert _apply_kind_tag(None, None) is None

    def test_comic_appends_tag(self):
        assert _apply_kind_tag(["Sci-Fi"], "comic") == ["Sci-Fi", "Comic"]

    def test_manga_appends_tag(self):
        assert _apply_kind_tag(None, "manga") == ["Manga"]

    def test_existing_tag_is_not_duplicated_case_insensitive(self):
        assert _apply_kind_tag(["comic", "Sci-Fi"], "comic") == ["comic", "Sci-Fi"]

    def test_does_not_mutate_input(self):
        tags = ["Sci-Fi"]
        _apply_kind_tag(tags, "comic")
        assert tags == ["Sci-Fi"]


class TestKindFromTags:
    @pytest.mark.parametrize(
        ("tags", "expected"),
        [
            (None, None),
            ([], None),
            (["Shonen"], None),
            (["Sci-Fi", "Comic"], "comic"),
            (["manga", "Shonen"], "manga"),
            (["Comic", "Manga"], "comic"),  # first matching tag wins
        ],
    )
    def test_detects_kind(self, tags, expected):
        assert _kind_from_tags(tags) == expected


# ---------------------------------------------------------------------------
# inject
# ---------------------------------------------------------------------------


class TestInjectKind:
    def test_comic_adds_comic_tag(self, tmp_path, make_epub, make_yaml):
        epub_dir, book, yaml_path = _setup(
            tmp_path, make_epub, make_yaml, kind="comic", genre=["Sci-Fi"]
        )
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        assert _tags(book) == ["Sci-Fi", "Comic"]

    def test_comic_without_genre(self, tmp_path, make_epub, make_yaml):
        epub_dir, book, yaml_path = _setup(tmp_path, make_epub, make_yaml, kind="comic")
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        assert _tags(book) == ["Comic"]

    def test_comic_tag_deduplicated_with_genre(self, tmp_path, make_epub, make_yaml):
        epub_dir, book, yaml_path = _setup(
            tmp_path, make_epub, make_yaml, kind="comic", genre=["Comic", "Sci-Fi"]
        )
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        assert _tags(book) == ["Comic", "Sci-Fi"]

    def test_manga_adds_manga_tag(self, tmp_path, make_epub, make_yaml):
        epub_dir, book, yaml_path = _setup(
            tmp_path, make_epub, make_yaml, kind="manga", genre=["Seinen"]
        )
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        assert _tags(book) == ["Seinen", "Manga"]

    def test_absent_kind_keeps_genre_only(self, tmp_path, make_epub, make_yaml):
        epub_dir, book, yaml_path = _setup(
            tmp_path, make_epub, make_yaml, genre=["Seinen"]
        )
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        assert _tags(book) == ["Seinen"]

    def test_absent_kind_and_genre_writes_no_tags(self, tmp_path, make_epub, make_yaml):
        epub_dir, book, yaml_path = _setup(tmp_path, make_epub, make_yaml)
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        assert _tags(book) is None

    def test_invalid_kind_is_error_and_file_untouched(
        self, tmp_path, make_epub, make_yaml
    ):
        epub_dir, book, yaml_path = _setup(
            tmp_path, make_epub, make_yaml, kind="webtoon"
        )
        before = book.read_bytes()
        assert inject_metadata(epub_dir, yaml_path) == ERROR
        assert book.read_bytes() == before

    def test_dry_run_does_not_write_tag(self, tmp_path, make_epub, make_yaml):
        epub_dir, book, yaml_path = _setup(tmp_path, make_epub, make_yaml, kind="comic")
        assert inject_metadata(epub_dir, yaml_path, dry_run=True) == SUCCESS
        assert _tags(book) is None

    def test_cli_inject_logs_kind(self, tmp_path, make_epub, make_yaml, capsys):
        epub_dir, book, yaml_path = _setup(tmp_path, make_epub, make_yaml, kind="comic")
        assert main(["inject", str(epub_dir), str(yaml_path)]) == SUCCESS
        assert "Kind: comic" in capsys.readouterr().err
        assert _tags(book) == ["Comic"]

    def test_cli_inject_invalid_kind(self, tmp_path, make_epub, make_yaml, capsys):
        epub_dir, _, yaml_path = _setup(tmp_path, make_epub, make_yaml, kind="nope")
        assert main(["inject", str(epub_dir), str(yaml_path)]) == ERROR
        assert "Invalid kind 'nope'" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# dump + round-trip
# ---------------------------------------------------------------------------


class TestDumpKind:
    def _dump(self, epub_dir: Path, tmp_path: Path) -> dict:
        out_yaml = tmp_path / "dumped.yaml"
        assert dump_metadata(epub_dir, out_yaml) == SUCCESS
        return yaml.safe_load(out_yaml.read_text())

    def test_dump_emits_kind_comic(self, tmp_path, make_epub, make_yaml):
        epub_dir, _, yaml_path = _setup(
            tmp_path, make_epub, make_yaml, kind="comic", genre=["Sci-Fi"]
        )
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        parsed = self._dump(epub_dir, tmp_path)
        assert parsed["kind"] == "comic"
        assert parsed["genre"] == ["Sci-Fi", "Comic"]
        # kind is placed right after series / author for readability.
        assert list(parsed)[:3] == ["series", "author", "kind"]

    def test_dump_without_kind_tag_omits_kind(self, tmp_path, make_epub, make_yaml):
        epub_dir, _, yaml_path = _setup(
            tmp_path, make_epub, make_yaml, genre=["Seinen"]
        )
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        assert "kind" not in self._dump(epub_dir, tmp_path)

    @pytest.mark.parametrize("kind", ["comic", "manga"])
    def test_round_trip_kind(self, tmp_path, make_epub, make_yaml, kind):
        epub_dir, book, yaml_path = _setup(
            tmp_path, make_epub, make_yaml, kind=kind, genre=["Action"]
        )
        assert inject_metadata(epub_dir, yaml_path) == SUCCESS
        first = self._dump(epub_dir, tmp_path)
        assert first["kind"] == kind

        # Re-inject the dump into a fresh EPUB: same tags, no duplicate kind tag.
        fresh_dir = tmp_path / "fresh"
        fresh_dir.mkdir()
        fresh = make_epub(fresh_dir / "Saga v01.epub", author=None)
        dumped_yaml = make_yaml(tmp_path / "redump.yaml", first)
        assert inject_metadata(fresh_dir, dumped_yaml) == SUCCESS
        assert _tags(fresh) == _tags(book) == ["Action", KIND_TAG[kind]]

        second = self._dump(fresh_dir, tmp_path)
        assert second["kind"] == kind
        assert second["genre"] == first["genre"]
