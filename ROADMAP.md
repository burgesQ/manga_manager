# Roadmap & Task Backlog

Full workflow: `*.cbz` → **packer** → volume dirs → **editor** (metadata) → **convertor** → `*.kepub.epub`

---

## Packer

### Short-term (high priority)

- [ ] **P1** Secure extraction — prevent path traversal attacks in `.cbz` extraction
- [ ] **P2** `ComicInfo.xml` robustness — handle missing, multiple, case-insensitive, and malformed files
- [ ] **P3** Extraction policy flags: `--flatten` / `--keep-structure`
- [ ] **P4** Rework concurrency — main thread parses, workers process per-chapter; prevent I/O races
- [ ] **P5** Add `--skip-missing` / `--continue-on-error` flags
- [ ] **P6** Unit tests for filename parsing, `--chapter-range` parsing, `ComicInfo.xml` detection
- [ ] **P7** Edge-case tests: extras-without-main, multi-number filenames

### Medium-term

- [ ] **P8** Integration tests (dry-run, real extraction, concurrency)
- [ ] **P9** Standardize exit codes into named constants; improve error messages

### Long-term / Nice-to-have

- [ ] **P10** Merge / consolidate volume-level `ComicInfo.xml`
- [ ] **P11** Better logging / progress reporting UI
- [ ] **P12** Additional archive formats and chapter identifier styles (A..Z, chapter 0, etc.)

---

## Editor

- [ ] **E1** Inject Calibre tags: Manga, Seinen, Shonen, Horror, Fiction, Fantasy, etc.
- [ ] **E2** Inject Calibre IDs: ISBN (currently mis-filed as DC id) and Kobo
- [ ] **E3** Kobo library collection support (Manga, Thriller)
- [ ] **E4** Refactor `editor_full.py` — extract helpers, clean up module structure
- [ ] **E5** Add tests (currently near-zero coverage for editor)
- [ ] **E6** Decide fate of `editor.py` (legacy reference impl) — remove or document

---

## Convertor

- [ ] **C2** Parallelize workers for multi-volume conversions
- [ ] **C3** Parametrize KCC settings via CLI flags / `packer.json` (profile, cropping, hq)
- [ ] **C4** Integrate conversion into packer via `--convert` flag or `auto_convert` in `packer.json`
- [ ] **C5** Remove dead code: commented-out `runpy` block in `kcc_adapter.py:107-113`

---

## Calibre Metadata & Naming Convention

- [ ] **M1** Define and document output filename convention for Calibre auto-discovery
  - Suggested: `<Serie> v{NN} - {VolumeTitle} - {authors}.kepub.epub`
- [ ] **M2** Inject metadata from `packer.json` into EPUB via convertor (serie, volume_title, authors, isbn, date, publisher)
- [ ] **M3** Validate generated EPUB metadata with a unit test

---

## CI / DevOps

- [ ] **CI1** Make mypy strict — remove `|| true` from ci.yml, add `mypy.ini` / pyproject config
- [ ] **CI2** Wire up reviewdog to annotate PRs from ruff / black / isort / mypy
- [ ] **CI3** Multi-Python test matrix: 3.10, 3.11, 3.12
- [ ] **CI4** Optional KCC integration CI job (runs only when KCC is available)
- [ ] **CI5** Enable CodeQL scan (scaffolding already in ci.yml, just commented out)
