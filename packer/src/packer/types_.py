from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional, Tuple, TypeAlias


class ChapterMatch(NamedTuple):
    """Represents a chapter match extracted from a filename.

    `base` is the chapter base number (int) and `extra` is the optional
    extra suffix (e.g. '5' for chapter 16.5) or None for mains.
    """

    base: int
    extra: Optional[str]


# Type alias for chapter-to-files mapping: base -> {mains, extras}
ChapterMapping: TypeAlias = Dict[int, Dict[str, List[Tuple[Optional[str], str]]]]


class Task(NamedTuple):
    """Task to process: chapter ID and source file path."""

    chapter_id: str
    src: str


class ProcessResult(NamedTuple):
    """Result of processing a chapter: chapter ID and destination archive path."""

    chapter_id: str
    dest_archive: str


class ProcessVolumeResult(NamedTuple):
    """Result of processing a volume: exit code and remaining available files."""

    exit_code: int
    remaining_files: List[str]


# Type alias for simplified mapping used in worker
ChapterToFilesMapping: TypeAlias = Dict[int, Dict[str, List[Tuple[Optional[str], str]]]]
