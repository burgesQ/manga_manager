# Copilot Summary & Action Plan

This file is an aggregated dump of the instructions, README content, design decisions and refactor directives we've worked through while developing and improving this repository. Below you will find:

- A consolidated list of the user-provided instructions and feature requests
- The repository README(s) (copied verbatim)
- An analysis of the codebase with concrete directions for simplifying and reducing code surface

---

## 1) Consolidated Instructions / Requirements (history of requests)

- Rework `packer` so the main thread orchestrates workers and workers perform per-chapter tasks (move -> mkdir -> unpack).
- Add support for extras (e.g., 16.1 then 16.2) and ensure correct ordering (main first, extras numeric order).
- Add named filename patterns (e.g., `--pattern mashle/fma`) with regex overrides (`--chapter-regex`, `--extra-regex`).
- Add batch mode: `--batch` / `--batch-file` and discover `.batch` per-path files.
- Per-path config file: discover & parse `packer.json`; fail early on invalid JSON; CLI args override config values.
- Split `main` into modules: `cli.py`, `core.py`, `worker.py`, `main.py` shim.
- Improve logging: colored outputs, emoji prefixes, `--loglevel` and `--verbose` flags.
- Add tests: unit tests, doctests, and worker integration-like tests; ensure test suite is green.
- Add CI (GitHub Actions): lint (ruff/black/isort/mypy), tests, and CodeQL.
- Add `Makefile` or `uv` tasks for `lint`, `test`, `coverage`.
- Create `convertor` package that converts volume directories to `.kepub.epub` using KindleComicConverter (KCC).
  - Ensure module-only execution for KCC (no subprocess fallback) per later request.
  - Provide CLI options for `--force-regen`, `--dry-run` and safe defaults for KCC arguments.
  - Convertor to be class-based with a `KCCAdapter` and use a `NamedTuple` for invocation (`KCCInvocation`).
  - Public `convert_volume()` should not accept an `options` parameter; keep a `dry_run` flag.
- Use `NamedTuple`s (or small dataclasses) instead of anonymous tuples for structured data (`ChapterMatch`, `Task`, `ProcessResult`, `ProcessVolumeResult`, `KCCInvocation`).
- Use `pathlib.Path` instead of `os.path` for filesystem ops.
- DRY up `core.py`, `worker.py`, `main.py`, and `utils.py` to reduce repetition and complexity.
- Add type hints and ensure `mypy` is progressively improved; fix type issues when reasonable and keep tests passing.
- Fix doctests and maintain readable docstrings; keep line length under configured limit.
- Ensure tests and linter are run and fixed iteratively until green.

---

## 2) Repository README(s) (dump)

### Root README.md

```
# manga_creator

A collection of small scripts to help manage a manga library (target: Kobo).

This repository currently contains a `packer` utility that groups chapter
archives into volume directories.

Overview
- Language: Python (standard library only for now)
- Target platform: Linux (tested on Linux Mint 22.3 / Debian 13)

All package are managed with `uv` (TODO: add link & few example)

## TODO

- [x] finish packer v1.0
- [ ] packer v1.1
  - [x] DRY things up
  - [ ] DRY things up (again)
  - [ ] simplify the code
  - [ ] get ride of the LLM' "foret de 'if'"
  - [ ] Inject ISBN, author and others ?
- [ ] convertor v1.0
  - [ ] convert to epub, take meta info somewhere
  - [x] epub builder (kindle comic convertor <3 aka https://github.com/ciromattia/kcc#usage)
  - [x] no GUI
- [ ] epub meta
  - [ ] edit meta from epub

- [ ] calibre sync !?
- [ ] update root readme for process (dl from Tachiyomi, move to host, run manga_creator script suites)
```

### packer/README.md

(See packer README: the packer README describes design decisions, CLI options, examples, TODOs and test instructions.)

### convertor/README.md

(See convertor README: describes the purpose and usage of convertor, KCC options and invocation behavior.)

---

## 3) Current repo structure (high level)

- packer/
  - src/packer/
    - cli.py
    - core.py
    - worker.py
    - main.py (shim)
    - utils.py (test helpers)
  - tests/
- convertor/
  - src/convertor/
    - kcc_adapter.py
    - cli.py
    - __init__.py
    - tests/
- pyproject.toml & dev-tools configured (ruff, mypy, pytest, black)

---

## 4) Repo Analysis & Simplification Recommendations

Summary: The codebase is already well-factored into a small set of modules with reasonable tests, logging, and CI. However, there are opportunities to simplify further, reduce duplication, make type-checking smoother and reduce the cognitive burden for contributors.

Priority suggestions (ordered):

1) Consolidate configuration & types (Low effort, high payoff) ✅
   - Create a small `Config` dataclass in `packer` that centralizes CLI options, derived fields (e.g., `volume_dir` builder, `nb_worker` defaults, `chapter_pat`, `extra_pat`) and helper methods (e.g., `has_comicinfo`). This replaces reliance on a loose `cfg` object and removes repeated parameter passing.
   - Export commonly used TypeAliases & NamedTuples from a single module (e.g., `packer/types.py`) so all modules import the same definitions and type-checking becomes consistent.

2) Reduce duplication in patterns & regex definitions (Low effort)
   - Centralize named filename patterns (default/mashle/fma) in one place (`packer/patterns.py` or `core.py`). Tests, CLI and worker code should reference this single source of truth.

3) Small modules consolidation (Low-medium effort)
   - `utils.py` is small and only used for tests: either move helpers into `tests/conftest.py` or split test-only utilities into `packer/tests/helpers.py`. This reduces top-level surface area.
   - Consider merging very small modules, e.g., if `main.py` is mostly a shim, keep it minimal or remove it and make CLI the canonical entrypoint (expose console_scripts entry if packaging).

4) Simplify worker concurrency model (Medium effort)
   - Current model uses `ThreadPoolExecutor` with `process_one` tasks. If `process_one` is CPU-bound (zipping/IO), switching to process pool or serial execution is a non-trivial decision. If concurrency adds complexity in tests, consider keeping `nb_worker` configurable but default to 1 and document that concurrency is optional; add simpler integration tests that use `nb_worker=1`.
   - Reduce concurrency-specific branching by encapsulating executor logic in a tiny helper (e.g., `with_executor(cfg.nb_worker) as submit: ...`) to keep `process_volume` logic straight-line.

5) Clean up KCC convertor surface (Low effort)
   - `KCCAdapter` is small and good. Consider moving `convert_volume()` into `KCCAdapter` as a convenience method and keep `cli.py` as a thin wrapper. Keep the module-only policy, but provide a limited adapter interface to allow mocking for tests.

6) Make typing & mypy smoother (Low-medium effort)
   - Add a `py.typed` file in packages if runtime typing is desired. Fix a few `TypeAlias` initializations and avoid `# type: ignore` everywhere by adding narrow asserts / checks. Consider adding minimal stub for third-party modules used in tests.

7) Reduce equivalent logic across core/worker (Medium effort)
   - Some logic for building volume dir and chapter folder names is repeated; centralize into small, well-documented helpers (e.g., `format_volume_dir()` already exists; add `format_chapter_dir()` and reuse it everywhere).

8) Tests: parametrize and remove duplication (Low effort)
   - Where tests repeat for multiple named patterns, parametrize them with `pytest.mark.parametrize`.
   - Move shared test fixtures into `tests/conftest.py`.

9) Documentation cleanup (Low effort)
   - Consolidate README TODOs into a `ROADMAP.md` and add a `CONTRIBUTING.md` with dev setup & `uv` commands.

10) Consider removing or consolidating small orphan files (Low effort)
    - Check for small modules that only exist for minor functionality and consider merging them. E.g., `packer/main.py` can be a minimal shim and documented as such (no need for more). If an `editor` package in workspace is empty or unused, consider removing it from `pyproject` members until real code lands.

11) Keep API surface minimal (Medium-high effort)
    - Prefer module-only, testable, public functions with small clearly documented signatures. Remove or change public functions that accept opaque `options` objects in favor of explicit arguments or a `Config` instance.

12) Add meta-tests & integration tests (Medium effort)
    - Add a small integration test that runs a minimal scenario end-to-end (create fake CBZs, run CLI with `--dry-run`, assert logs and planned actions). This guards refactors.

---

## 5) Concrete next tasks (actionable)

- Create `packer/types.py` with `ChapterMatch`, `Task`, `ProcessResult`, `ProcessVolumeResult` and `ChapterMapping` TypeAlias.
- Create a `Config` dataclass (in `cli.py` or a new `config.py`) and use it across `core` and `worker`.
- Move test helpers from `utils.py` to `tests/conftest.py` and remove `utils.py` (or keep only runtime helpers if needed).
- Add `format_chapter_dir()` helper to `core.py` and replace replicated logic in `worker.py`.
- Parametrize tests where possible to reduce duplication across pattern variants.
- Run `uv run mypy` and iterate on typing fixes (goal: reduce `type: ignore` usage and avoid missing-imports where possible).

---

## 6) Contact / how to proceed

If you want, I can:
- Implement the quick wins immediately (create `types.py`, `config.py`, move test helpers and update imports). ✅
- Then run the test suite and linter after each change and open a PR-like series of commits.
- Or produce a prioritized, time-estimated plan for the medium/large refactors.

Tell me which next step you'd like me to take and I will prepare the patches and run tests/lint continuously until everything is green.

---

*End of copilot.md*