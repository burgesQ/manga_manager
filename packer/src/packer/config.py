from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Config:
    """Runtime configuration for a packer invocation.

    This dataclass centralizes CLI options and compiled regex patterns used by
    worker code.
    """

    path: str
    dest: str
    serie: str
    volume: int
    chapter_range: List[int]
    nb_worker: int = 1
    dry_run: bool = False
    verbose: bool = False
    force: bool = False
    chapter_pat: Optional[re.Pattern] = None
    extra_pat: Optional[re.Pattern] = None

    # convenience helper for worker module
    def has_comicinfo(self, path: str) -> bool:
        from .core import has_comicinfo

        return has_comicinfo(path)
