# manga-gui

Local web UI ([NiceGUI](https://nicegui.io)) to set up and run the
`packer → convertor → editor` pipeline per series ("project").

> Status: UI-free core only. The wizard pages are not built yet; `manga-gui`
> serves a placeholder index page.

## Usage

```bash
uv run manga-gui                      # http://127.0.0.1:8080
uv run manga-gui --host 0.0.0.0 --port 8080 --data-dir ./gui-data
```

| Option | Default | Purpose |
|---|---|---|
| `--host` | `127.0.0.1` | interface to bind (`0.0.0.0` in Docker) |
| `--port` | `8080` | port |
| `--data-dir` | XDG dirs | store projects and runs under `<dir>/projects` and `<dir>/runs` |
| `--loglevel` / `--verbose` | `INFO` | log level |

Data locations without `--data-dir`:

- projects: `$XDG_CONFIG_HOME/manga_manager/projects/<slug>.json` (`~/.config/...`)
- runs: `$XDG_STATE_HOME/manga_manager/runs/<slug>/<run_id>.{json,log}` (`~/.local/state/...`)

## Design

- The real config files (`packer.json`, batch CSV, metadata / chapters YAML) remain the
  source of truth; a project only points to them and stores paths, KCC overrides,
  editor locale and enabled steps.
- Steps run as subprocesses (`python -m packer.main …`), never in-process, so they can
  be cancelled and their logs streamed. Each step also has an equivalent shell command
  (`StepCommand.shell()`).

## Modules

| Module | Role |
|---|---|
| `models.py` | `Project`, `PackerOptions`, `KCCOptions`, `EditorOptions`, `Kind`, `slugify` |
| `commands.py` | pure `Project` → `list[StepCommand]` builder |
| `runner.py` | asyncio runner: line streaming, `parse_progress`, cancel (SIGTERM then SIGKILL) |
| `store.py` | JSON persistence of projects and run history |
| `validation.py` | pre-flight checks reusing the packer / editor loaders |
| `scan.py` | `.cbz` → chapter detection preview, volume folders, EPUB listing |
| `main.py` | argparse entry point → `ui.run()` |

## Tests

```bash
uv run pytest gui -q
cd gui && uv run mypy --package manga_gui
```
