from __future__ import annotations

import asyncio
import doctest
import time
from pathlib import Path

import pytest
from manga_gui import runner
from manga_gui.commands import StepCommand
from manga_gui.runner import (
    SPAWN_ERROR,
    PipelineResult,
    PipelineRunner,
    StepResult,
    parse_progress,
    run_step,
)


def test_doctests() -> None:
    assert doctest.testmod(runner).failed == 0


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("✅ INFO: [1/3] Extracting chapter 1 — Chapter 1.cbz", (1, 3)),
        ("✅ INFO: [DRY RUN] [12/12] Extracting chapter 16.5 — x.cbz", (12, 12)),
        ("✅ INFO: [info] planned tasks for volume 1:", None),
        ("✅ INFO: [5/0] weird", None),
        ("✅ INFO: [7/3] weird", None),
        ("", None),
    ],
)
def test_parse_progress(line: str, expected: tuple[int, int] | None) -> None:
    assert parse_progress(line) == expected


def test_run_step_streams_merged_output(py_cmd) -> None:
    code = (
        "import sys\n"
        "print('out 1', flush=True)\n"
        "sys.stderr.write('err 2\\n'); sys.stderr.flush()\n"
        "sys.stdout.buffer.write(b'bad \\xff byte\\nno newline')\n"
        "sys.exit(4)\n"
    )
    lines: list[str] = []
    rc = asyncio.run(run_step(py_cmd(code), lines.append))
    assert rc == 4
    assert lines == ["out 1", "err 2", "bad � byte", "no newline"]


def test_run_step_lines_arrive_while_running(py_cmd) -> None:
    code = "import time\nprint('first', flush=True)\ntime.sleep(0.5)\nprint('second')"
    stamps: list[float] = []

    async def go() -> int:
        t0 = time.monotonic()
        return await run_step(
            py_cmd(code), lambda _l: stamps.append(time.monotonic() - t0)
        )

    assert asyncio.run(go()) == 0
    assert len(stamps) == 2
    assert stamps[1] - stamps[0] >= 0.3


def test_run_step_uses_cwd(tmp_path: Path, py_cmd) -> None:
    lines: list[str] = []
    asyncio.run(run_step(py_cmd("import os; print(os.getcwd())"), lines.append))
    assert Path(lines[0]).resolve() == tmp_path.resolve()


def test_run_step_spawn_error(tmp_path: Path) -> None:
    cmd = StepCommand("packer", ["/nonexistent/binary"], tmp_path)
    lines: list[str] = []
    assert asyncio.run(run_step(cmd, lines.append)) == SPAWN_ERROR
    assert lines and "failed to start packer" in lines[0]


def test_pipeline_success(py_cmd) -> None:
    cmds = [
        py_cmd("print('a')", step="packer"),
        py_cmd("print('b')", step="convertor"),
    ]
    lines: list[str] = []
    started: list[str] = []
    ended: list[StepResult] = []
    result = asyncio.run(
        PipelineRunner().run(
            cmds, lines.append, lambda c: started.append(c.step), ended.append
        )
    )
    assert lines == ["a", "b"]
    assert started == ["packer", "convertor"]
    assert [r.step for r in ended] == ["packer", "convertor"]
    assert result.ok and result.exit_code == 0 and not result.cancelled
    assert [s.exit_code for s in result.steps] == [0, 0]
    assert result.steps[0].argv == cmds[0].argv
    assert result.duration >= 0 and result.started_at


def test_pipeline_stops_at_first_failure(py_cmd) -> None:
    cmds = [
        py_cmd("print('a')", step="packer"),
        py_cmd("import sys; print('b'); sys.exit(3)", step="convertor"),
        py_cmd("print('c')", step="editor"),
    ]
    lines: list[str] = []
    started: list[str] = []
    result = asyncio.run(
        PipelineRunner().run(
            cmds, lines.append, on_step_start=lambda c: started.append(c.step)
        )
    )
    assert lines == ["a", "b"]
    assert started == ["packer", "convertor"]
    assert [(s.step, s.exit_code) for s in result.steps] == [
        ("packer", 0),
        ("convertor", 3),
    ]
    assert result.exit_code == 3 and not result.ok


def test_pipeline_cancel(py_cmd) -> None:
    cmds = [
        py_cmd(
            "import time\nprint('started', flush=True)\ntime.sleep(30)",
            step="packer",
        ),
        py_cmd("print('never')", step="convertor"),
    ]
    pipeline = PipelineRunner(kill_timeout=2.0)
    lines: list[str] = []

    def on_line(line: str) -> None:
        lines.append(line)
        if line == "started":
            pipeline.cancel()

    t0 = time.monotonic()
    result = asyncio.run(pipeline.run(cmds, on_line))
    assert time.monotonic() - t0 < 10
    assert lines == ["started"]
    assert result.cancelled and not result.ok
    assert len(result.steps) == 1
    assert result.steps[0].cancelled
    assert result.steps[0].exit_code != 0
    assert not pipeline.running


def test_pipeline_cancel_escalates_to_kill(py_cmd) -> None:
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\n"
        "time.sleep(30)\n"
    )
    pipeline = PipelineRunner(kill_timeout=0.3)

    def on_line(line: str) -> None:
        if line == "ready":
            pipeline.cancel()

    t0 = time.monotonic()
    result = asyncio.run(pipeline.run([py_cmd(code)], on_line))
    assert time.monotonic() - t0 < 10
    assert result.cancelled
    assert result.steps[0].exit_code == -9


def test_cancel_when_idle_is_noop() -> None:
    pipeline = PipelineRunner()
    pipeline.cancel()
    assert not pipeline.cancelled and not pipeline.running


def test_pipeline_rejects_concurrent_runs(py_cmd) -> None:
    pipeline = PipelineRunner()

    async def go() -> None:
        task = asyncio.create_task(
            pipeline.run([py_cmd("import time; time.sleep(0.3)")], lambda _l: None)
        )
        await asyncio.sleep(0.05)
        with pytest.raises(RuntimeError):
            await pipeline.run([], lambda _l: None)
        await task

    asyncio.run(go())


def test_pipeline_records_dry_run(py_cmd) -> None:
    result = asyncio.run(PipelineRunner().run([], lambda _l: None, dry_run=True))
    assert result.dry_run and result.steps == [] and result.ok


def test_result_dict_round_trip() -> None:
    result = PipelineResult(
        steps=[
            StepResult("packer", ["p", "-m", "packer.main"], 0, 1.0),
            StepResult("convertor", ["p"], -15, 2.0, cancelled=True),
        ],
        started_at="2026-11-04T10:00:00+01:00",
        duration=3.0,
        cancelled=True,
    )
    data = result.to_dict()
    assert data["exit_code"] == -15
    assert PipelineResult.from_dict(data) == result
