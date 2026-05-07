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

---

## Editor

- [ ] **E1** Inject Calibre tags: Manga, Seinen, Shonen, Horror, Fiction, Fantasy, etc.
- [ ] **E2** Inject Calibre IDs: ISBN (currently mis-filed as DC id) and Kobo
- [ ] **E3** Kobo library collection support (Manga, Thriller)
- [ ] **E4** Refactor `editor_full.py` — extract helpers, clean up module structure
- [x] **E5** Add tests (comprehensive coverage for inject/dump/clear)
- [x] **E6** Remove legacy `editor.py` (done)

---

## Convertor

- [x] **C1** Remove `--stretch` flag — images were distorted on Kobo Libra Colour
- [ ] **C2** Parallelize workers for multi-volume conversions
- [ ] **C3** Parametrise KCC settings via CLI flags / `packer.json` (profile, cropping, hq)
- [ ] **C4** Integrate conversion into packer via `--convert` flag or `auto_convert` in `packer.json`
- [x] **C5** Remove dead code: commented-out `runpy` block and unused imports in `kcc_adapter.py`
- [ ] **C6** Inject cover if none?

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

- [ ] **W1** Ship with Calibre web? (idea)
