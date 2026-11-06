"""Live run output: per-step status chips, progress bar and log view."""

from __future__ import annotations

from nicegui import ui

from ..forms import STATUS_COLORS, StepStatus
from ..runner import parse_progress

DEFAULT_MAX_LINES = 5000


class LogPanel:
    """Status chips + ``ui.linear_progress`` + ``ui.log`` for one pipeline run.

    The full text of the run is kept (even past ``max_lines``) so it can be stored
    with the run history.
    """

    def __init__(self, *, max_lines: int = DEFAULT_MAX_LINES) -> None:
        self._lines: list[str] = []
        self._chips: dict[str, ui.chip] = {}
        with ui.column().classes("w-full gap-2") as self.container:
            self._chips_row = ui.row().classes("gap-1")
            self.progress = ui.linear_progress(value=0, show_value=False).mark(
                "run-progress"
            )
            self.log = (
                ui.log(max_lines=max_lines)
                .classes("w-full h-80 font-mono text-xs")
                .mark("run-log")
            )

    @property
    def alive(self) -> bool:
        """False once the page holding the panel has been closed."""
        return not self.log.is_deleted

    def reset(self, steps: list[str]) -> None:
        """Clear the previous run and show ``steps`` as pending."""
        self._lines.clear()
        self.log.clear()
        self.progress.value = 0
        self._chips_row.clear()
        self._chips.clear()
        with self._chips_row:
            for step in steps:
                self._chips[step] = ui.chip(step).mark(f"status-{step}")
                self.set_status(step, StepStatus.PENDING)

    def set_status(self, step: str, status: StepStatus) -> None:
        chip = self._chips.get(step)
        if chip is None:
            return
        chip.text = f"{step}: {status.value}"
        chip.props(f'color="{STATUS_COLORS[status]}" text-color="white"')

    def status_text(self, step: str) -> str:
        chip = self._chips.get(step)
        return chip.text if chip is not None else ""

    def mark_pending_as(self, status: StepStatus) -> None:
        """Give every step still pending (never started) the final ``status``."""
        for step, chip in self._chips.items():
            if chip.text.endswith(StepStatus.PENDING.value):
                self.set_status(step, status)

    def push(self, line: str) -> None:
        """Append one output line and advance the progress bar on ``[i/n]``."""
        self._lines.append(line)
        self.log.push(line)
        progress = parse_progress(line)
        if progress is not None:
            idx, total = progress
            self.progress.value = idx / total

    def text(self) -> str:
        """Full log of the run (newline terminated)."""
        return "".join(f"{line}\n" for line in self._lines)
