from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from manga_gui import main as gui_main
from manga_gui.exit_codes import CLI_ERROR, SUCCESS


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
