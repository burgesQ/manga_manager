# Roadmap & Task Backlog

Full workflow: `*.cbz` → **packer** → volume dirs → **editor** (metadata) → **convertor** → `*.kepub.epub`

---

## Packer

### Short-term (high priority)

- [x] **P1** Secure extraction — prevent path traversal attacks in `.cbz` extraction
- [ ] **P2** `ComicInfo.xml` robustness — handle missing, multiple, case-insensitive, and malformed files
      — *partial:* case-insensitive match + missing/BadZip handled (`core.py:198-201`); multiple-entry & malformed-XML parsing still missing
- [ ] **P3** Extraction policy flags: `--flatten` / `--keep-structure`
- [x] **P4** Rework concurrency — main thread parses, workers process per-chapter; prevent I/O races
      (`worker.py:139-201`)
- [ ] **P5** Add `--skip-missing` / `--continue-on-error` flags
- [x] **P6** Unit tests for filename parsing, `--chapter-range` parsing, `ComicInfo.xml` detection
      (`test_core_regex.py`, `test_utils.py`, `test_error_paths.py`)
- [ ] **P7** Edge-case tests: extras-without-main, multi-number filenames
      — *partial:* `extras-without-main` covered; `test_multinumber_filename_parsing` is a non-asserting stub

### Medium-term

- [x] **P8** Integration tests (dry-run, real extraction, concurrency)
- [x] **P9** Standardise exit codes into named constants; improve error messages

### Long-term / Nice-to-have

- [ ] **P10** Merge / consolidate volume-level `ComicInfo.xml`
- [x] **P11** Better logging / progress reporting UI
- [ ] **P12** Additional archive formats and chapter identifier styles (A..Z, chapter 0, etc.)
- [x] **P13** Support for optional volume cover — place `cover.webp` in the volume dir; see **C6** for implementation
              Sometime volume doesn't have cover. User may download one (as `.webp` ?) And attach it to the vols.cvs (work like that ?)
- [x] **P14** Rename named regex patterns from series names (`fma`, `mashle`, `animeSama`) to download-source names (`mangafox`, `weebcentral`, etc.) — patterns describe filename conventions from a given source, not a specific series
- [ ] **P15** (M) Atomic per-chapter processing — `process_one` moves the archive then extracts; on a bad zip the archive is already moved out of source. Extract to temp, commit on success (distinct from P5's batch continuation)
- [ ] **P16** (S) De-duplicate chapter-mapping logic — `worker.process_volume` re-implements chapter→file mapping inline instead of reusing `core.map_chapters_to_files`; refactor the latter to accept custom patterns
- [ ] **P17** (M) Write a per-run `packer-manifest.json` (volume, chapters, source→dest, cover) as a structured hand-off to editor/convertor; supports **M2**


---

## Editor

- [x] **E1** Inject Calibre tags: read `genre` list from YAML, inject as `dc:subject`
- [ ] **E2** Inject Calibre IDs: ISBN (currently mis-filed as DC id) and Kobo
      — *partial:* ISBN injected as DC identifier `id="isbn"` (`epub_metadata.py:156-163`); Kobo ID not injected
- [ ] **E3** Kobo library collection support (Manga, Thriller)
- [x] **E4** Refactor `editor_full.py` — split into `epub_metadata.py` (EPUBMetadata class) + `editor_full.py` (operations); `_inject_single` extracted from inject loop; `_dc_scalar` helper added
- [x] **E5** Add tests (comprehensive coverage for inject/dump/clear)
- [x] **E6** Remove legacy `editor.py` (done)
- [x] **E7** Inject chapter titles into the EPUB TOC — `inject --chapters chapters.yaml` relabels
      `Chapter NNN` navLabels to `Chapter NNN - <title>` via `EPUBMetadata.set_chapter_titles` +
      `load_chapters_yaml`; matched by chapter number, volume-agnostic, honours `--dry-run`
- [ ] **E8** 🐞 (S) Fix `dump` → `inject` round-trip: `dump_metadata` writes ISBN/date under a `metadata:` sub-key (`editor_full.py:255-260`) but `_inject_single` reads the locale sub-key (`english:`/`japanese:`); `dump` also never emits `genre`/`language`. Result: dump-then-inject silently loses ISBN, date, tags, language
- [ ] **E9** (M) `editor validate` subcommand / `--validate`: check required keys, ISBN-10/13 checksums, BCP-47 language tags, `release_date` formats before touching EPUBs
- [ ] **E10** (M) Support `illustrator` / multi-role creators — real files (`boruto.yaml`) carry `illustrator:`, currently ignored; map to `dc:creator opf:role="art"`
- [ ] **E11** (M) Selective / merge injection (`--only-missing`) — top up missing fields without overwriting everything (current inject is all-or-nothing gated on `has_metadata()`+`--force`)
- [ ] **E12** (M) Embed EPUB cover from YAML/file (`book.set_cover`) — complements the convertor `Chapter 000/` cover hack (**C6**)

---

## Convertor

- [x] **C1** Remove `--stretch` flag — images were distorted on Kobo Libra Colour
- [ ] **C2** Parallelize workers for multi-volume conversions
- [ ] **C3** Parametrise KCC settings via CLI flags / `packer.json` (profile, cropping, hq)
      — *partial:* full CLI flags done (`convertor/cli.py:55-104`); `packer.json` wiring absent
- [ ] **C4** Integrate conversion into packer via `--convert` flag or `auto_convert` in `packer.json`
             Note: isn't that the /editor purpose ?
- [x] **C5** Remove dead code: commented-out `runpy` block and unused imports in `kcc_adapter.py`
- [x] **C6** Inject cover — packer copies `cover.webp` to volume dir; convertor creates `Chapter 000/` before KCC, cleans up after
- [x] **C7** 🐞 (S) Propagate conversion failures: `_convert_one` swallows exceptions and `_process_volumes` unconditionally returns `SUCCESS` (`convertor/cli.py:145-158`), so a run where every volume fails still exits 0. Track success/fail counts, print a summary, return `CLI_ERROR` on any failure
- [ ] **C8** (S) Preflight KCC availability check (`shutil.which("kcc-c2e")`) with an actionable install message instead of N per-volume `CalledProcessError`s; also fix the stale `kcc_adapter` docstring (mentions removed `runpy`/`POSSIBLE_MODULE_NAMES`)
- [ ] **C9** (S) Real volume-dir detection — `find_volume_dirs` treats every subdir as a volume; add a `[Serie] vNN` name filter / `--volume-glob` so pointing one level too deep doesn't convert `Chapter NNN/` dirs

---

## Calibre Metadata & Naming Convention

- [ ] **M1** Define and document output filename convention for Calibre auto-discovery
  - Suggested: `<Serie> v{NN} - {VolumeTitle} - {authors}.kepub.epub`
- [x] ~~**M2** Inject metadata from `packer.json` into EPUB via convertor~~ → **superseded by editor (E1–E7)** — the editor already injects all volume/chapter metadata from YAML; a second convertor-side path is redundant
- [ ] **M3** Validate generated EPUB metadata with a unit test
      — *partial:* `EPUBMetadata` set/get roundtrip tested; no test on a convertor-generated EPUB

---

## CI / DevOps

- [x] **CI1** Make mypy strict — add `[tool.mypy]` config, enforce in CI (no `|| true`)
- [ ] **CI2** Wire up reviewdog to annotate PRs from ruff / black / isort / mypy
- [ ] **CI3** Multi-Python test matrix: 3.10, 3.11, 3.12
- [ ] **CI4** Optional KCC integration CI job (runs only when KCC is available)
- [ ] **CI5** Enable CodeQL scan (scaffolding already in ci.yml, just commented out)
- [ ] **CI6** (S) Expand ruff ruleset (`I`, `B`, `UP`) + drop `|| true` so lint is a real gate (distinct from **CI2**'s reviewdog annotation)
- [ ] **CI7** (S) Coverage-threshold gate (`--cov-fail-under=N`) so the high coverage can't silently regress
- [ ] **CI8** (M) End-to-end pipeline integration test (packer → editor → convertor, KCC mocked) to catch cross-package contract breaks like **E8**

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
- [x] **Q10** (S) `--version` flag on all three CLIs (all 3 CLIs, importlib.metadata)
- [ ] **Q11** (M) Unified `manga pack|edit|convert …` entry point — one dispatcher over the three console scripts; natural home for a future `manga run` full-pipeline command
- [x] **Q12** (S) Shell completion generation (`--completion bash|zsh|fish`, e.g. via `shtab`) — (shtab)

### Additional cleanup completed (PRs #13–#14)

- [x] **Q6** Add `exit_codes.py` + `py.typed` to `editor` and `convertor` — named constants (`SUCCESS`, `ERROR`, `CLI_ERROR`) replace bare literals across all three packages
- [x] **Q7** Deduplicate test fixtures — `make_config` in packer conftest; `make_epub`/`make_yaml` in editor conftest; `make_vol`/`run_convertor` fixtures in convertor conftest; local helpers removed from test files
- [x] **Q8** Test coverage — editor: 0% → 99%; packer cli.py: 29% → high; convertor error paths covered; all tests call `main()` directly (not subprocess) for accurate instrumentation
- [x] **Q9** Rewrite package-level READMEs (`packer`, `editor`, `convertor`) — replace stale design notes with clean, current documentation
