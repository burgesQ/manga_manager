"""Header shared by every page: app link and the Auto / Light / Dark theme switch.

The theme is a GUI setting (:attr:`~manga_gui.models.Settings.theme`, saved in
``settings.json`` by :meth:`~manga_gui.store.Store.save_theme`), applied on page
load with ``ui.dark_mode``. The page CSS added here keeps the grey helper texts,
placeholders and multi-line notifications readable in both themes.
"""

from __future__ import annotations

import logging
from typing import Any

from nicegui import ui

from ..help_texts import field_help
from ..models import theme_dark_value
from ..store import Store

logger = logging.getLogger(__name__)

APP_TITLE = "manga-gui"
THEME_OPTIONS = {"auto": "Auto", "light": "Light", "dark": "Dark"}
MULTILINE_NOTIFY = "mg-multiline"
"""``classes`` of ``ui.notify`` calls whose message holds newlines."""

PAGE_CSS = f"""
.{MULTILINE_NOTIFY} .q-notification__message {{ white-space: pre-line; }}
body.body--dark .text-grey-6 {{ color: #9e9e9e !important; }}
body.body--dark .text-grey-7 {{ color: #bdbdbd !important; }}
body.body--dark .bg-grey-3 {{ background: #424242 !important; }}
"""


class PageHeader:
    """``ui.header`` with the app link and the theme toggle (one per page)."""

    def __init__(self, store: Store) -> None:
        self.store = store
        theme = store.load_settings().theme
        ui.add_css(PAGE_CSS)
        self.dark = ui.dark_mode(theme_dark_value(theme))
        with ui.header().classes("items-center py-1 px-4"):
            ui.link(APP_TITLE, "/").classes("text-h6 text-white no-underline")
            ui.space()
            ui.icon("contrast").classes("text-white")
            self.switch = (
                ui.toggle(THEME_OPTIONS, value=theme, on_change=self._on_theme)
                .props(
                    "dense no-caps unelevated color=primary text-color=white "
                    "toggle-color=white toggle-text-color=primary"
                )
                .mark("theme-switch")
            )
            self.switch.tooltip(field_help("gui.theme"))

    def _on_theme(self, e: Any) -> None:
        theme = str(e.value or "auto")
        self.dark.value = theme_dark_value(theme)
        try:
            self.store.save_theme(theme)
        except OSError as err:
            ui.notify(f"Theme not saved: {err}", type="warning")
            return
        logger.info("theme set to %s", theme)
