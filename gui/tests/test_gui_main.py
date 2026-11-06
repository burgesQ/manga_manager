from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from manga_gui import main as gui_main
from manga_gui.exit_codes import CLI_ERROR, PROCESSING_ERROR, SUCCESS
from manga_gui.models import Project, Settings
from manga_gui.store import Store


@pytest.fixture
def fake_run(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(gui_main.ui, "run", lambda **kw: calls.append(kw))
    monkeypatch.setattr(gui_main, "register_pages", lambda store: None)
    return calls


def test_defaults(fake_run, tmp_path: Path) -> None:
    assert gui_main.main(["--data-dir", str(tmp_path)]) == SUCCESS
    assert fake_run == [
        {
            "host": "127.0.0.1",
            "port": 8080,
            "title": "manga-gui",
            "reload": False,
            "show": False,
        }
    ]


def test_host_port(fake_run, tmp_path: Path) -> None:
    argv = ["--host", "0.0.0.0", "--port", "9000", "--data-dir", str(tmp_path)]
    assert gui_main.main(argv) == SUCCESS
    assert fake_run[0]["host"] == "0.0.0.0" and fake_run[0]["port"] == 9000


@pytest.mark.parametrize("port", ["0", "70000"])
def test_bad_port(fake_run, port: str, capsys) -> None:
    assert gui_main.main(["--port", port]) == CLI_ERROR
    assert fake_run == []
    assert "--port" in capsys.readouterr().err


def test_data_dir_is_a_file(fake_run, tmp_path: Path, capsys) -> None:
    f = tmp_path / "file"
    f.write_text("x")
    assert gui_main.main(["--data-dir", str(f)]) == CLI_ERROR
    assert "not a directory" in capsys.readouterr().err


def test_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        gui_main.main(["--version"])
    assert exc.value.code == 0
    assert "manga-gui" in capsys.readouterr().out


def test_module_help_smoke() -> None:
    res = subprocess.run(
        [sys.executable, "-m", "manga_gui.main", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0
    assert "--data-dir" in res.stdout


# -- serve: library settings -----------------------------------------------------


def test_serve_library_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stores: list[Store] = []
    monkeypatch.setattr(gui_main.ui, "run", lambda **kw: None)
    monkeypatch.setattr(gui_main, "register_pages", stores.append)
    store = Store(tmp_path / "data")
    store.save_settings(Settings(library_root=tmp_path / "saved"))
    argv = ["--data-dir", str(tmp_path / "data"), "--metadata-dir", str(tmp_path)]
    assert gui_main.main(argv) == SUCCESS
    assert stores[0].effective_settings() == Settings(
        library_root=tmp_path / "saved", metadata_dir=tmp_path
    )
    assert stores[0].load_settings().metadata_dir is None  # not saved


def test_serve_library_root_not_a_dir(fake_run, tmp_path: Path, capsys) -> None:
    argv = ["--data-dir", str(tmp_path), "--library-root", str(tmp_path / "nope")]
    assert gui_main.main(argv) == CLI_ERROR
    assert "--library-root is not a directory" in capsys.readouterr().err


# -- import ----------------------------------------------------------------------


def _import(fake_shelf, data: Path, *extra: str) -> int:
    return gui_main.main(
        [
            "import",
            "--library-root",
            str(fake_shelf.root),
            "--metadata-dir",
            str(fake_shelf.meta),
            "--data-dir",
            str(data),
            *extra,
        ]
    )


def test_import_dry_run_writes_nothing(fake_shelf, tmp_path: Path, capsys) -> None:
    data = tmp_path / "data"
    assert _import(fake_shelf, data, "--dry-run", "--save-settings") == SUCCESS
    assert not data.exists()
    err = capsys.readouterr().err
    assert "status" in err and "reason" in err
    assert "key 'boruto_bv' matches the initials of 'BorutoBlueVortex'" in err
    assert "no source" in err and "Vinland Saga" in err
    assert "dry-run: 9 project(s) would be written" in err


def test_import_writes_profiles(fake_shelf, tmp_path: Path, capsys) -> None:
    data = tmp_path / "data"
    assert _import(fake_shelf, data, "--save-settings") == SUCCESS
    store = Store(data)
    assert len(store.list_projects()) == 9
    assert store.load_project("boruto").editor.locale == "french"
    assert store.load_settings() == Settings(
        library_root=fake_shelf.root, metadata_dir=fake_shelf.meta
    )
    assert "9 created, 0 overwritten, 0 skipped (exists), 0 failed" in (
        capsys.readouterr().err
    )


def test_import_skips_existing_unless_overwrite(
    fake_shelf, tmp_path: Path, capsys
) -> None:
    data = tmp_path / "data"
    store = Store(data)
    store.save_project(Project(name="Berserk", source=tmp_path / "elsewhere"))
    assert _import(fake_shelf, data) == SUCCESS
    assert store.load_project("berserk").source == tmp_path / "elsewhere"
    assert "8 created, 0 overwritten, 1 skipped (exists)" in capsys.readouterr().err

    assert _import(fake_shelf, data, "--overwrite") == SUCCESS
    assert store.load_project("berserk").source == fake_shelf.root / "EN" / "Berserk"
    assert "0 created, 9 overwritten" in capsys.readouterr().err


def test_import_uses_saved_settings(fake_shelf, tmp_path: Path, capsys) -> None:
    data = tmp_path / "data"
    Store(data).save_settings(Settings(metadata_dir=fake_shelf.meta))
    argv = ["import", "--data-dir", str(data), "--dry-run"]
    assert gui_main.main(argv) == SUCCESS
    err = capsys.readouterr().err
    assert "dry-run: 0 project(s) would be written" in err  # no library root


def test_import_needs_a_source(tmp_path: Path, capsys) -> None:
    assert gui_main.main(["import", "--data-dir", str(tmp_path)]) == CLI_ERROR
    assert "nothing to import" in capsys.readouterr().err
    argv = ["import", "--data-dir", str(tmp_path), "--metadata-dir", "/nope/x"]
    assert gui_main.main(argv) == CLI_ERROR


def test_import_write_failure(fake_shelf, tmp_path: Path, capsys) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "projects").write_text("not a dir")
    assert _import(fake_shelf, data) == PROCESSING_ERROR
    assert "failed to import" in capsys.readouterr().err


def test_import_options_before_subcommand(fake_shelf, tmp_path: Path) -> None:
    data = tmp_path / "data"
    argv = ["--data-dir", str(data), "import", "--library-root", str(fake_shelf.root)]
    assert gui_main.main(argv) == SUCCESS
    assert len(Store(data).list_projects()) == 9
