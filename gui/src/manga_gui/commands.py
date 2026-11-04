"""Pure command builder: :class:`~manga_gui.models.Project` → CLI invocations.

No I/O happens here. Each enabled step becomes a :class:`StepCommand` whose ``argv``
runs the step as ``python -m <pkg>.main …`` (so the GUI's own interpreter and
environment are used), while :meth:`StepCommand.shell` renders the equivalent
console-script command line for display / copy-paste.

Paths are emitted exactly as stored in the project; store absolute paths in the
project to get commands that work from any directory.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import NamedTuple

from .models import EditorOptions, KCCOptions, Project

STEP_MODULES: dict[str, str] = {
    "packer": "packer.main",
    "convertor": "convertor.main",
    "editor": "editor.main",
}
"""Module run with ``python -m`` for each step (execution order)."""

PACKER_LOGLEVEL = "INFO"
"""Log level forced on packer so its ``[idx/total]`` progress lines are emitted."""

# KCC boolean overrides, in the order the convertor parser declares them.
_KCC_BOOL_FLAGS: tuple[tuple[str, str], ...] = (
    ("manga_style", "manga-style"),
    ("hq", "hq"),
    ("forcecolor", "forcecolor"),
)
_KCC_BOOL_FLAGS_TAIL: tuple[tuple[str, str], ...] = (
    ("upscale", "upscale"),
    ("blackborders", "blackborders"),
)


class StepCommand(NamedTuple):
    """One pipeline step ready to be spawned."""

    step: str
    argv: list[str]
    cwd: Path

    def shell(self) -> str:
        """Equivalent shell command using the console script (``packer`` …).

        The ``python -m <module>`` prefix is replaced by the step's console-script
        name, so the result can be pasted into a terminal where the workspace is
        installed.
        """
        args = self.argv
        if len(args) >= 3 and args[1] == "-m":
            args = [self.step, *args[3:]]
        return shlex.join(args)


def _packer_argv(project: Project, *, dry_run: bool) -> list[str]:
    opts = project.packer
    argv = ["--path", str(project.source), "--dest", str(project.effective_dest)]
    if opts.config is not None:
        argv += ["--config", str(opts.config)]
    if opts.serie:
        argv += ["--serie", opts.serie]
    if opts.pattern and opts.pattern != "default":
        argv += ["--pattern", opts.pattern]
    if opts.chapter_regex:
        argv += ["--chapter-regex", opts.chapter_regex]
    if opts.extra_regex:
        argv += ["--extra-regex", opts.extra_regex]
    if opts.nb_worker != 1:
        argv += ["--nb-worker", str(opts.nb_worker)]
    # Volume selection precedence mirrors packer: batch > batch file > single volume.
    if opts.batch:
        argv += ["--batch", opts.batch]
    elif opts.batch_file is not None:
        argv += ["--batch-file", str(opts.batch_file)]
    else:
        if opts.volume is not None:
            argv += ["--volume", str(opts.volume)]
        if opts.chapter_range:
            argv += ["--chapter-range", opts.chapter_range]
    if opts.force:
        argv.append("--force")
    if dry_run:
        argv.append("--dry-run")
    argv += ["--loglevel", PACKER_LOGLEVEL]
    return argv


def _bool_flag(name: str, value: bool) -> str:
    return f"--{name}" if value else f"--no-{name}"


def _convertor_argv(project: Project, *, dry_run: bool) -> list[str]:
    opts: KCCOptions = project.convertor
    argv = [str(project.effective_dest), "--preset", project.kind.value]
    if opts.profile:
        argv += ["--profile", opts.profile]
    for attr, flag in _KCC_BOOL_FLAGS:
        value = getattr(opts, attr)
        if value is not None:
            argv.append(_bool_flag(flag, value))
    if opts.rotation is not None:
        argv += ["--rotation", str(opts.rotation)]
    if opts.cropping is not None:
        argv += ["--cropping", str(opts.cropping)]
    for attr, flag in _KCC_BOOL_FLAGS_TAIL:
        value = getattr(opts, attr)
        if value is not None:
            argv.append(_bool_flag(flag, value))
    if opts.force_regen:
        argv.append("--force-regen")
    if dry_run:
        argv.append("--dry-run")
    return argv


def _editor_argv(project: Project, metadata: Path, *, dry_run: bool) -> list[str]:
    opts: EditorOptions = project.editor
    argv = ["inject", str(project.effective_dest), str(metadata)]
    argv += ["--locale", opts.locale]
    if opts.chapters is not None:
        argv += ["--chapters", str(opts.chapters)]
    if opts.force:
        argv.append("--force")
    if dry_run:
        argv.append("--dry-run")
    return argv


def build_command(
    project: Project,
    step: str,
    *,
    dry_run: bool = False,
    python: str = sys.executable,
) -> StepCommand | None:
    """Build the command for a single ``step``, ignoring whether it is enabled.

    Returns ``None`` for the editor step when no metadata YAML is configured
    (``editor inject`` cannot run without one). Raises ``ValueError`` for an
    unknown step name.
    """
    if step not in STEP_MODULES:
        raise ValueError(f"unknown step: {step!r}")
    if step == "packer":
        args = _packer_argv(project, dry_run=dry_run)
    elif step == "convertor":
        args = _convertor_argv(project, dry_run=dry_run)
    else:
        if project.editor.metadata is None:
            return None
        args = _editor_argv(project, project.editor.metadata, dry_run=dry_run)
    argv = [python, "-m", STEP_MODULES[step], *args]
    return StepCommand(step=step, argv=argv, cwd=project.source)


def build_commands(
    project: Project,
    *,
    dry_run: bool = False,
    python: str = sys.executable,
) -> list[StepCommand]:
    """Build the commands of all enabled steps, in order packer → convertor → editor.

    The editor step is **skipped** (not an error) when ``project.editor.metadata``
    is ``None``; :func:`manga_gui.validation.validate_project` reports it as a
    warning so the UI can explain why.
    """
    commands: list[StepCommand] = []
    for step in STEP_MODULES:
        if not project.step_enabled(step):
            continue
        cmd = build_command(project, step, dry_run=dry_run, python=python)
        if cmd is not None:
            commands.append(cmd)
    return commands
