"""NiceGUI pages of manga-gui."""

from __future__ import annotations

from ..store import Store
from . import project, projects


def register_pages(store: Store) -> None:
    """Register every page route, all backed by ``store``."""
    projects.register(store)
    project.register(store)


__all__ = ["register_pages"]
