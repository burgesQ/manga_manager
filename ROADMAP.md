# Roadmap & Task Backlog

Full workflow: `*.cbz` → **packer** → volume dirs → **editor** (metadata) → **convertor** → `*.kepub.epub`

---

## Packer

### Short-term (high priority)

- [x] **P1** Secure extraction — prevent path traversal attacks in `.cbz` extraction
- [ ] **P2** `ComicInfo.xml` robustness — handle missing, multiple, case-insensitive, and malformed files
- [ ] **P3** Extraction policy flags: `--flatten` / `--keep-structure`
- [ ] **P4** Rework concurrency — main thread parses, workers process per-chapter; prevent I/O races
- [ ] **P5** Add `--skip-missing` / `--continue-on-error` flags
- [ ] **P6** Unit tests for filename parsing, `--chapter-range` parsing, `ComicInfo.xml` detection
- [ ] **P7** Edge-case tests: extras-without-main, multi-number filenames

### Medium-term

- [x] **P8** Integration tests (dry-run, real extraction, concurrency)
- [x] **P9** Standardise exit codes into named constants; improve error messages

### Long-term / Nice-to-have

- [ ] **P10** Merge / consolidate volume-level `ComicInfo.xml`
- [x] **P11** Better logging / progress reporting UI
- [ ] **P12** Additional archive formats and chapter identifier styles (A..Z, chapter 0, etc.)
- [x] **P13** Support for optional volume cover — place `cover.webp` in the volume dir; see **C6** for implementation
              Sometime volume doesn't have cover. User may download one (as `.webp` ?) And attach it to the vols.cvs (work like that ?)
- [x] **P14** Rename named regex patterns from series names (`fma`, `mashle`, `animeSama`) to download-source names (`mangadex`, `weebcentral`, etc.) — patterns describe filename conventions from a given source, not a specific series


---

## Editor

- [ ] **E1** Inject Calibre tags: Manga, Seinen, Shonen, Horror, Fiction, Fantasy, etc.
- [ ] **E2** Inject Calibre IDs: ISBN (currently mis-filed as DC id) and Kobo
- [ ] **E3** Kobo library collection support (Manga, Thriller)
- [x] **E4** Refactor `editor_full.py` — split into `epub_metadata.py` (EPUBMetadata class) + `editor_full.py` (operations); `_inject_single` extracted from inject loop; `_dc_scalar` helper added
- [x] **E5** Add tests (comprehensive coverage for inject/dump/clear)
- [x] **E6** Remove legacy `editor.py` (done)

---

## Convertor

- [x] **C1** Remove `--stretch` flag — images were distorted on Kobo Libra Colour
- [ ] **C2** Parallelize workers for multi-volume conversions
- [ ] **C3** Parametrise KCC settings via CLI flags / `packer.json` (profile, cropping, hq)
- [ ] **C4** Integrate conversion into packer via `--convert` flag or `auto_convert` in `packer.json`
             Note: isn't that the /editor purpose ?
- [x] **C5** Remove dead code: commented-out `runpy` block and unused imports in `kcc_adapter.py`
- [x] **C6** Inject cover — packer copies `cover.webp` to volume dir; convertor creates `Chapter 000/` before KCC, cleans up after

---

## Calibre Metadata & Naming Convention

- [ ] **M1** Define and document output filename convention for Calibre auto-discovery
  - Suggested: `<Serie> v{NN} - {VolumeTitle} - {authors}.kepub.epub`
- [ ] **M2** Inject metadata from `packer.json` into EPUB via convertor (serie, volume_title, authors, isbn, date, publisher)
- [ ] **M3** Validate generated EPUB metadata with a unit test

---

## CI / DevOps

- [x] **CI1** Make mypy strict — add `[tool.mypy]` config, enforce in CI (no `|| true`)
- [ ] **CI2** Wire up reviewdog to annotate PRs from ruff / black / isort / mypy
- [ ] **CI3** Multi-Python test matrix: 3.10, 3.11, 3.12
- [ ] **CI4** Optional KCC integration CI job (runs only when KCC is available)
- [ ] **CI5** Enable CodeQL scan (scaffolding already in ci.yml, just commented out)

---

## Web UI

- [x] **W1** Ship with Calibre web? (idea)

---

## Code Quality / Cleanup

Global refactor pass across all three packages to improve readability and maintainability.

- [x] **Q1** Replace anonymous tuples with `NamedTuple` / `TypeAlias` everywhere — `BatchSpecs` TypeAlias added to `packer/types_.py`; all 4 raw `list[tuple[int, list[int]]]` annotations replaced
- [x] **Q2** Eliminate if-forests — packer `cli.py` refactored to use `_CLIError` private exception + early-exit guard clauses; all helpers follow happy-path principle
- [x] **Q3** Break up long functions — `packer/cli.py` main() extracted into 6 focused helpers; `packer/worker.py` process_volume() extracted into `_plan_tasks`, `_copy_cover`, `_run_tasks`; `editor/cli.py` extracted `_add_logging_args`; `convertor/cli.py` extracted `_build_parser`, `_build_settings`, `_process_volumes`
- [ ] **Q4** Remove anonymous lambdas — replace inline `lambda` with named functions or `operator` helpers where intent is non-obvious
- [x] **Q5** Split large modules — `editor/editor_full.py` (607 lines) split into `epub_metadata.py` (EPUBMetadata class + `_dc_scalar`, low-level EPUB I/O) and `editor_full.py` (operations: inject / dump / clear)

### Additional cleanup completed (PRs #13–#14)

- [x] **Q6** Add `exit_codes.py` + `py.typed` to `editor` and `convertor` — named constants (`SUCCESS`, `ERROR`, `CLI_ERROR`) replace bare literals across all three packages
- [x] **Q7** Deduplicate test fixtures — `make_config` in packer conftest; `make_epub`/`make_yaml` in editor conftest; `make_vol`/`run_convertor` fixtures in convertor conftest; local helpers removed from test files
- [x] **Q8** Test coverage — editor: 0% → 99%; packer cli.py: 29% → high; convertor error paths covered; all tests call `main()` directly (not subprocess) for accurate instrumentation
- [x] **Q9** Rewrite package-level READMEs (`packer`, `editor`, `convertor`) — replace stale design notes with clean, current documentation
