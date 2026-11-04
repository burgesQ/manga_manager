"""Asyncio subprocess runner: line streaming, progress parsing and cancellation.

Steps run as subprocesses (never in-process): every CLI ``main()`` resets the root
logging handlers, packer uses threads, and only a subprocess can be cancelled.
stdout and stderr are merged and decoded as UTF-8 with ``errors="replace"``. Logs
arrive without ANSI colours because packer's ``ColorFormatter`` disables colour when
the stream is not a tty.

Each step is started in its own session (process group) so that cancelling also
stops grandchildren such as ``kcc-c2e``.
"""

from __future__ import annotations

import asyncio
import codecs
import logging
import os
import re
import signal
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, NamedTuple

from .commands import StepCommand

logger = logging.getLogger(__name__)

SPAWN_ERROR = 127
"""Exit code reported when a step cannot be started (missing cwd, interpreter …)."""

DEFAULT_KILL_TIMEOUT = 5.0
"""Seconds between ``terminate`` (SIGTERM) and ``kill`` (SIGKILL) on cancel."""

_CHUNK_SIZE = 4096
_PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]")

LineCallback = Callable[[str], None]


class StepResult(NamedTuple):
    """Outcome of one step."""

    step: str
    argv: list[str]
    exit_code: int
    duration: float
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**self._asdict(), "argv": list(self.argv)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepResult:
        return cls(
            step=str(data["step"]),
            argv=[str(a) for a in data.get("argv", [])],
            exit_code=int(data["exit_code"]),
            duration=float(data.get("duration", 0.0)),
            cancelled=bool(data.get("cancelled", False)),
        )


class PipelineResult(NamedTuple):
    """Outcome of a pipeline run (steps that actually started, in order)."""

    steps: list[StepResult]
    started_at: str
    duration: float
    cancelled: bool = False
    dry_run: bool = False

    @property
    def exit_code(self) -> int:
        """First non-zero step exit code, or 0 when every step succeeded."""
        for s in self.steps:
            if s.exit_code != 0:
                return s.exit_code
        return 0

    @property
    def ok(self) -> bool:
        """True when the run was not cancelled and every step exited with 0."""
        return not self.cancelled and self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "started_at": self.started_at,
            "duration": self.duration,
            "cancelled": self.cancelled,
            "dry_run": self.dry_run,
            "exit_code": self.exit_code,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineResult:
        return cls(
            steps=[StepResult.from_dict(s) for s in data.get("steps", [])],
            started_at=str(data.get("started_at", "")),
            duration=float(data.get("duration", 0.0)),
            cancelled=bool(data.get("cancelled", False)),
            dry_run=bool(data.get("dry_run", False)),
        )


def parse_progress(line: str) -> tuple[int, int] | None:
    """Parse packer's ``[idx/total]`` progress marker.

    >>> parse_progress("✅ INFO: [DRY RUN] [3/12] Extracting chapter 3 — c3.cbz")
    (3, 12)
    >>> parse_progress("✅ INFO: [info] planned tasks for volume 1:") is None
    True
    """
    m = _PROGRESS_RE.search(line)
    if not m:
        return None
    idx, total = int(m.group(1)), int(m.group(2))
    if total <= 0 or idx > total:
        return None
    return idx, total


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


async def _pump_lines(stream: asyncio.StreamReader, on_line: LineCallback) -> None:
    """Read ``stream`` to EOF, calling ``on_line`` for each decoded line."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    pending = ""
    while True:
        chunk = await stream.read(_CHUNK_SIZE)
        if not chunk:
            break
        pending += decoder.decode(chunk)
        *lines, pending = pending.split("\n")
        for line in lines:
            on_line(line.rstrip("\r"))
    pending += decoder.decode(b"", final=True)
    if pending:
        on_line(pending.rstrip("\r"))


async def run_step(
    cmd: StepCommand,
    on_line: LineCallback,
    *,
    on_spawn: Callable[[asyncio.subprocess.Process], None] | None = None,
) -> int:
    """Run ``cmd``, streaming merged stdout+stderr to ``on_line`` line by line.

    Returns the process exit code (negative signal number when killed), or
    :data:`SPAWN_ERROR` when the process could not be started (the reason is sent
    to ``on_line``). ``on_spawn`` receives the process right after it starts, which
    is how :class:`PipelineRunner` gets a handle to cancel it.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd.argv,
            cwd=cmd.cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=_child_env(),
            start_new_session=True,
        )
    except OSError as e:
        on_line(f"failed to start {cmd.step}: {e}")
        return SPAWN_ERROR
    if on_spawn is not None:
        on_spawn(proc)
    assert proc.stdout is not None
    await _pump_lines(proc.stdout, on_line)
    return await proc.wait()


def _signal_group(proc: asyncio.subprocess.Process, sig: signal.Signals) -> None:
    """Send ``sig`` to the process group of ``proc`` (falls back to the process)."""
    if proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError, AttributeError):
        try:
            proc.send_signal(sig)
        except ProcessLookupError:
            pass


class PipelineRunner:
    """Run step commands in order, stopping at the first non-zero exit.

    A runner executes one pipeline at a time; :meth:`cancel` may be called from any
    callback or UI handler running in the same event loop.
    """

    def __init__(self, *, kill_timeout: float = DEFAULT_KILL_TIMEOUT) -> None:
        self.kill_timeout = kill_timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._cancelled = False
        self._running = False

    @property
    def running(self) -> bool:
        """True while :meth:`run` is in progress."""
        return self._running

    @property
    def cancelled(self) -> bool:
        """True once :meth:`cancel` has been requested for the current run."""
        return self._cancelled

    def _on_spawn(self, proc: asyncio.subprocess.Process) -> None:
        self._proc = proc
        if self._cancelled:  # cancel() raced with the spawn
            self._terminate(proc)

    def _terminate(self, proc: asyncio.subprocess.Process) -> None:
        _signal_group(proc, signal.SIGTERM)
        loop = asyncio.get_running_loop()
        loop.call_later(self.kill_timeout, _signal_group, proc, signal.SIGKILL)

    def cancel(self) -> None:
        """Stop the current step: SIGTERM now, SIGKILL after ``kill_timeout``.

        Remaining steps are not started. Safe to call when nothing is running.
        """
        if not self._running:
            return
        self._cancelled = True
        proc = self._proc
        if proc is not None and proc.returncode is None:
            logger.info("cancelling pid %s", proc.pid)
            self._terminate(proc)

    async def run(
        self,
        commands: list[StepCommand],
        on_line: LineCallback,
        on_step_start: Callable[[StepCommand], None] | None = None,
        on_step_end: Callable[[StepResult], None] | None = None,
        *,
        dry_run: bool = False,
    ) -> PipelineResult:
        """Run ``commands`` sequentially and return the aggregated result.

        ``dry_run`` is only recorded in the result (the commands themselves carry
        ``--dry-run``). Raises ``RuntimeError`` if the runner is already busy.
        """
        if self._running:
            raise RuntimeError("pipeline already running")
        self._running = True
        self._cancelled = False
        started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        t0 = time.monotonic()
        results: list[StepResult] = []
        try:
            for cmd in commands:
                if self._cancelled:
                    break
                if on_step_start is not None:
                    on_step_start(cmd)
                s0 = time.monotonic()
                rc = await run_step(cmd, on_line, on_spawn=self._on_spawn)
                self._proc = None
                result = StepResult(
                    step=cmd.step,
                    argv=list(cmd.argv),
                    exit_code=rc,
                    duration=round(time.monotonic() - s0, 3),
                    cancelled=self._cancelled,
                )
                results.append(result)
                if on_step_end is not None:
                    on_step_end(result)
                if rc != 0 or self._cancelled:
                    break
        finally:
            self._running = False
            self._proc = None
        return PipelineResult(
            steps=results,
            started_at=started_at,
            duration=round(time.monotonic() - t0, 3),
            cancelled=self._cancelled,
            dry_run=dry_run,
        )
