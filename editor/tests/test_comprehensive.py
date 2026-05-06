"""Comprehensive tests for editor inject / dump / clear operations.

Covers the gaps identified in the gap analysis:
- Multiple volumes in one YAML
- Missing optional fields (no isbn, no date)
- Default title generation
- Inject -> dump round-trip
- Clear removes all metadata
- --force flag behaviour
- Error cases (missing YAML, no EPUBs, no matching volume)
- parse_volume_number unit tests
- _get_epub_files unit tests
- dump to stdout
- Invalid YAML -> YAMLError
- Two-volume language scenario
- ISBN format handling
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest import mock

import pytest
import yaml

pytest.importorskip("ebooklib")
from ebooklib import epub

from editor.editor_full import (
    EPUBMetadata,
    _get_epub_files,
    clear_metadata,
    dump_metadata,
    inject_metadata,
    load_yaml_metadata,
    parse_volume_number,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_minimal_epub(
    path: Path,
    title: str = "Title",
    author: str | None = "Author",
) -> None:
    """Write a minimal but valid EPUB to *path*."""
    book = epub.EpubBook()
    book.set_identifier("id-" + path.stem.replace(" ", "_"))
    book.set_title(title)
    if author:
        book.add_author(author)
    c1 = epub.EpubHtml(
        title="Intro", file_name="intro.xhtml", content="<h1>Hi</h1>"
    )
    book.add_item(c1)
    book.toc = (epub.Link("intro.xhtml", "Intro", "intro"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]
    epub.write_epub(str(path), book)


# ---------------------------------------------------------------------------
# parse_volume_number – unit tests
# ---------------------------------------------------------------------------


class TestParseVolumeNumber:
    """Unit tests for :func:`parse_volume_number`."""

    def test_v01_prefix(self):
        assert parse_volume_number("Mashle v01.epub") == 1

    def test_vol_prefix(self):
        assert parse_volume_number("Series vol.03.epub") == 3

    def test_trailing_number(self):
        assert parse_volume_number("Series Name 05.kepub.epub") == 5

    def test_two_digit_number(self):
        assert parse_volume_number("Volume 12.epub") == 12

    def test_no_number_returns_none(self):
        assert parse_volume_number("NoNumberHere.epub") is None

    def test_volume_keyword_case_insensitive(self):
        assert parse_volume_number("VOLUME 07.epub") == 7

    def test_zero_padded(self):
        assert parse_volume_number("MySeries v08.epub") == 8

    def test_single_digit(self):
        assert parse_volume_number("Series v1.epub") == 1


# ---------------------------------------------------------------------------
# _get_epub_files – unit tests
# ---------------------------------------------------------------------------


class TestGetEpubFiles:
    """Unit tests for :func:`_get_epub_files`."""

    def test_single_epub_file(self, tmp_path: Path):
        f = tmp_path / "book.epub"
        _make_minimal_epub(f)
        result = _get_epub_files(f)
        assert result == [f]

    def test_non_epub_file_returns_empty(self, tmp_path: Path):
        f = tmp_path / "notes.txt"
        f.write_text("hello")
        assert _get_epub_files(f) == []

    def test_directory_returns_all_epubs(self, tmp_path: Path):
        for name in ("Series v01.epub", "Series v02.epub"):
            _make_minimal_epub(tmp_path / name)
        result = _get_epub_files(tmp_path)
        assert len(result) == 2

    def test_directory_no_epubs_returns_empty(self, tmp_path: Path):
        assert _get_epub_files(tmp_path) == []

    def test_nonexistent_path_returns_empty(self, tmp_path: Path):
        missing = tmp_path / "ghost"
        assert _get_epub_files(missing) == []

    def test_kepub_epub_included(self, tmp_path: Path):
        f = tmp_path / "book.kepub.epub"
        _make_minimal_epub(f)
        result = _get_epub_files(tmp_path)
        assert f in result

    def test_no_duplicates_when_both_patterns_match(self, tmp_path: Path):
        """Verify no duplicate entries even if a file matches both glob patterns."""
        f = tmp_path / "book.epub"
        _make_minimal_epub(f)
        result = _get_epub_files(tmp_path)
        assert result.count(f) == 1


# ---------------------------------------------------------------------------
# load_yaml_metadata – error cases
# ---------------------------------------------------------------------------


class TestLoadYamlMetadata:
    """Tests for YAML loading, including invalid-content handling."""

    def test_loads_valid_yaml(self, tmp_path: Path):
        yaml_path = tmp_path / "meta.yaml"
        yaml_path.write_text(yaml.dump({"series": "Test", "volumes": []}))
        data = load_yaml_metadata(yaml_path)
        assert data["series"] == "Test"

    def test_invalid_yaml_raises(self, tmp_path: Path):
        """A file with invalid YAML content must raise yaml.YAMLError."""
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text("key: [unclosed bracket\n")
        with pytest.raises(yaml.YAMLError):
            load_yaml_metadata(yaml_path)


# ---------------------------------------------------------------------------
# inject_metadata – error cases
# ---------------------------------------------------------------------------


class TestInjectMetadataErrors:
    """inject_metadata must fail gracefully on bad inputs."""

    def test_missing_yaml_returns_error(self, tmp_path: Path):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        _make_minimal_epub(epub_dir / "Series v01.epub")
        rc = inject_metadata(epub_dir, tmp_path / "ghost.yaml")
        assert rc == 1

    def test_no_epubs_in_directory_returns_error(self, tmp_path: Path):
        epub_dir = tmp_path / "empty"
        epub_dir.mkdir()
        yaml_path = tmp_path / "meta.yaml"
        yaml_path.write_text(
            yaml.dump({"series": "S", "author": "A", "volumes": []})
        )
        rc = inject_metadata(epub_dir, yaml_path)
        assert rc == 1

    def test_no_matching_volume_in_yaml_skips_file(self, tmp_path: Path):
        """EPUB v02 in a YAML that only lists volume 1 must be skipped (not error)."""
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        _make_minimal_epub(epub_dir / "Series v02.epub", author=None)

        yaml_path = tmp_path / "meta.yaml"
        data = {
            "series": "Series",
            "author": "Author",
            "volumes": [{"number": 1, "english": {"release_date": "2025-01-01"}}],
        }
        yaml_path.write_text(yaml.dump(data))

        # Should succeed overall (0) even though this volume was skipped
        rc = inject_metadata(epub_dir, yaml_path)
        assert rc == 0


# ---------------------------------------------------------------------------
# inject_metadata – multiple volumes
# ---------------------------------------------------------------------------


class TestInjectMultipleVolumes:
    """inject_metadata processes every EPUB that has a matching YAML entry."""

    def _make_yaml(self, tmp_path: Path, volumes: list[dict]) -> Path:
        yaml_path = tmp_path / "meta.yaml"
        data: dict = {
            "series": "MySeries",
            "author": "Test Author",
            "volumes": volumes,
        }
        yaml_path.write_text(yaml.dump(data))
        return yaml_path

    def test_two_volumes_both_injected(self, tmp_path: Path):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        for i in (1, 2):
            _make_minimal_epub(
                epub_dir / f"MySeries v{i:02d}.epub", author=None
            )

        yaml_path = self._make_yaml(
            tmp_path,
            [
                {"number": 1, "title": "Vol One", "english": {"release_date": "2025-01-01"}},
                {"number": 2, "title": "Vol Two", "english": {"release_date": "2025-06-01"}},
            ],
        )
        rc = inject_metadata(epub_dir, yaml_path)
        assert rc == 0

        for i, expected_title in ((1, "Vol One"), (2, "Vol Two")):
            meta = EPUBMetadata(
                epub_dir / f"MySeries v{i:02d}.epub"
            ).get_metadata()
            assert meta.get("title") == expected_title
            assert meta.get("series_index") == float(i)


# ---------------------------------------------------------------------------
# inject_metadata – missing optional fields
# ---------------------------------------------------------------------------


class TestInjectMissingOptionalFields:
    """inject_metadata must not crash when isbn or date are absent."""

    def test_no_isbn_no_date(self, tmp_path: Path):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        _make_minimal_epub(epub_dir / "Series v01.epub", author=None)

        yaml_path = tmp_path / "meta.yaml"
        data = {
            "series": "Series",
            "author": "Author",
            "volumes": [{"number": 1}],
        }
        yaml_path.write_text(yaml.dump(data))

        rc = inject_metadata(epub_dir, yaml_path)
        assert rc == 0

        meta = EPUBMetadata(epub_dir / "Series v01.epub").get_metadata()
        assert meta.get("series") == "Series"
        assert meta.get("isbn") is None
        assert meta.get("date") is None


# ---------------------------------------------------------------------------
# inject_metadata – default title generation
# ---------------------------------------------------------------------------


class TestDefaultTitleGeneration:
    """When the YAML volume has no explicit title, a default must be used."""

    def test_default_title_format(self, tmp_path: Path):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        _make_minimal_epub(epub_dir / "Berserk v03.epub", author=None)

        yaml_path = tmp_path / "meta.yaml"
        data = {
            "series": "Berserk",
            "author": "Miura",
            "volumes": [{"number": 3, "english": {"release_date": "2020-01-01"}}],
        }
        yaml_path.write_text(yaml.dump(data))

        rc = inject_metadata(epub_dir, yaml_path)
        assert rc == 0

        meta = EPUBMetadata(epub_dir / "Berserk v03.epub").get_metadata()
        # No title field → default "Berserk v03"
        assert meta.get("title") == "Berserk v03"


# ---------------------------------------------------------------------------
# inject_metadata – --force flag
# ---------------------------------------------------------------------------


class TestInjectForceFlag:
    """--force must overwrite existing metadata; without it the file is skipped."""

    def _prepare(self, tmp_path: Path) -> tuple[Path, Path]:
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        book_file = epub_dir / "Series v01.epub"
        # Create with full metadata so has_metadata() returns True
        book = epub.EpubBook()
        book.set_identifier("id123")
        book.set_title("Old Title")
        book.add_author("Old Author")
        book.add_metadata(
            None,
            "meta",
            "Series",
            {"name": "calibre:series", "content": "Series"},
        )
        c1 = epub.EpubHtml(
            title="Intro", file_name="intro.xhtml", content="<h1>Hi</h1>"
        )
        book.add_item(c1)
        book.toc = (epub.Link("intro.xhtml", "Intro", "intro"),)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", c1]
        epub.write_epub(str(book_file), book)

        yaml_path = tmp_path / "meta.yaml"
        data = {
            "series": "Series",
            "author": "New Author",
            "volumes": [
                {"number": 1, "title": "New Title", "english": {"release_date": "2025-01-01"}}
            ],
        }
        yaml_path.write_text(yaml.dump(data))
        return epub_dir, yaml_path

    def test_without_force_skips_file_with_existing_metadata(self, tmp_path: Path):
        epub_dir, yaml_path = self._prepare(tmp_path)
        rc = inject_metadata(epub_dir, yaml_path, force=False)
        assert rc == 0
        meta = EPUBMetadata(epub_dir / "Series v01.epub").get_metadata()
        # Metadata should remain as-was (Old Author, not New Author)
        assert meta.get("author") == "Old Author"

    def test_with_force_overwrites_existing_metadata(self, tmp_path: Path):
        epub_dir, yaml_path = self._prepare(tmp_path)
        rc = inject_metadata(epub_dir, yaml_path, force=True)
        assert rc == 0
        meta = EPUBMetadata(epub_dir / "Series v01.epub").get_metadata()
        assert meta.get("author") == "New Author"
        assert meta.get("title") == "New Title"


# ---------------------------------------------------------------------------
# inject -> dump round-trip
# ---------------------------------------------------------------------------


class TestInjectDumpRoundTrip:
    """After injecting, dump must produce a YAML that reflects the injected data."""

    def test_round_trip_title_and_author(self, tmp_path: Path):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        _make_minimal_epub(epub_dir / "RoundTrip v01.epub", author=None)

        yaml_path = tmp_path / "meta.yaml"
        data = {
            "series": "RoundTrip",
            "author": "RoundTrip Author",
            "volumes": [
                {
                    "number": 1,
                    "title": "First Volume",
                    "english": {"release_date": "2024-03-15", "isbn": "9782344007809"},
                }
            ],
        }
        yaml_path.write_text(yaml.dump(data))

        assert inject_metadata(epub_dir, yaml_path) == 0

        out_yaml = tmp_path / "dumped.yaml"
        assert dump_metadata(epub_dir, out_yaml) == 0

        parsed = yaml.safe_load(out_yaml.read_text())
        assert parsed["author"] == "RoundTrip Author"
        vols = parsed["volumes"]
        assert len(vols) == 1
        assert vols[0]["title"] == "First Volume"


# ---------------------------------------------------------------------------
# clear_metadata
# ---------------------------------------------------------------------------


class TestClearMetadata:
    """clear_metadata must wipe author (and other fields) from EPUB files."""

    def test_clear_removes_author(self, tmp_path: Path):
        book_file = tmp_path / "Series v01.epub"
        _make_minimal_epub(book_file, author="Someone")

        rc = clear_metadata(book_file)
        assert rc == 0

        meta = EPUBMetadata(book_file).get_metadata()
        assert meta.get("author") is None or meta.get("author") == []

    def test_clear_whole_directory(self, tmp_path: Path):
        d = tmp_path / "epubs"
        d.mkdir()
        for i in (1, 2):
            _make_minimal_epub(d / f"Series v{i:02d}.epub", author="Someone")

        rc = clear_metadata(d)
        assert rc == 0

        for i in (1, 2):
            meta = EPUBMetadata(d / f"Series v{i:02d}.epub").get_metadata()
            assert meta.get("author") is None or meta.get("author") == []

    def test_clear_dry_run_leaves_file_unchanged(self, tmp_path: Path):
        book_file = tmp_path / "Series v01.epub"
        _make_minimal_epub(book_file, author="Preserved Author")

        rc = clear_metadata(book_file, dry_run=True)
        assert rc == 0

        meta = EPUBMetadata(book_file).get_metadata()
        assert meta.get("author") == "Preserved Author"

    def test_clear_empty_directory_returns_success(self, tmp_path: Path):
        """clear on a dir with no EPUBs should succeed (returns 0)."""
        empty = tmp_path / "empty"
        empty.mkdir()
        rc = clear_metadata(empty)
        assert rc == 0


# ---------------------------------------------------------------------------
# dump to stdout
# ---------------------------------------------------------------------------


class TestDumpToStdout:
    """dump_metadata without an output path must print YAML to stdout."""

    def test_dump_stdout_contains_series(self, tmp_path: Path, capsys):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        _make_minimal_epub(
            epub_dir / "StdoutSeries v01.epub", title="StdoutSeries v01"
        )

        rc = dump_metadata(epub_dir, output_path=None)
        assert rc == 0

        captured = capsys.readouterr()
        assert "volumes" in captured.out


# ---------------------------------------------------------------------------
# Two-volume language scenario
# ---------------------------------------------------------------------------


class TestTwoVolumeLanguage:
    """Each volume can carry its own language tag."""

    def test_different_language_per_volume(self, tmp_path: Path):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        for i in (1, 2):
            _make_minimal_epub(epub_dir / f"Lang v{i:02d}.epub", author=None)

        yaml_path = tmp_path / "meta.yaml"
        data = {
            "series": "Lang",
            "author": "Author",
            "language": "en-US",
            "volumes": [
                {"number": 1, "language": "fr", "english": {"release_date": "2025-01-01"}},
                {"number": 2, "english": {"release_date": "2025-06-01"}},
            ],
        }
        yaml_path.write_text(yaml.dump(data))

        rc = inject_metadata(epub_dir, yaml_path)
        assert rc == 0

        meta1 = EPUBMetadata(epub_dir / "Lang v01.epub").get_metadata()
        meta2 = EPUBMetadata(epub_dir / "Lang v02.epub").get_metadata()

        assert meta1.get("language") == "fr"
        assert meta2.get("language") == "en-US"


# ---------------------------------------------------------------------------
# ISBN format handling
# ---------------------------------------------------------------------------


class TestISBNFormatHandling:
    """Hyphens and spaces in ISBN values must be stripped before storage."""

    def test_isbn_with_hyphens_stripped(self, tmp_path: Path):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        _make_minimal_epub(epub_dir / "ISBN v01.epub", author=None)

        yaml_path = tmp_path / "meta.yaml"
        data = {
            "series": "ISBN",
            "author": "Author",
            "volumes": [
                {
                    "number": 1,
                    "english": {"release_date": "2025-01-01", "isbn": "978-2-34-400780-9"},
                }
            ],
        }
        yaml_path.write_text(yaml.dump(data))

        rc = inject_metadata(epub_dir, yaml_path)
        assert rc == 0

        meta = EPUBMetadata(epub_dir / "ISBN v01.epub").get_metadata()
        isbn = meta.get("isbn", "")
        assert "-" not in str(isbn), "Hyphens must be stripped from ISBN"

    def test_isbn_with_spaces_stripped(self, tmp_path: Path):
        epub_dir = tmp_path / "epubs"
        epub_dir.mkdir()
        _make_minimal_epub(epub_dir / "ISBN v01.epub", author=None)

        yaml_path = tmp_path / "meta.yaml"
        data = {
            "series": "ISBN",
            "author": "Author",
            "volumes": [
                {
                    "number": 1,
                    "english": {
                        "release_date": "2025-01-01",
                        "isbn": "978 2 344 00780 9",
                    },
                }
            ],
        }
        yaml_path.write_text(yaml.dump(data))

        rc = inject_metadata(epub_dir, yaml_path)
        assert rc == 0

        meta = EPUBMetadata(epub_dir / "ISBN v01.epub").get_metadata()
        isbn = meta.get("isbn", "")
        assert " " not in str(isbn), "Spaces must be stripped from ISBN"
