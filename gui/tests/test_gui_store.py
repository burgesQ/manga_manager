from __future__ import annotations

from pathlib import Path

import pytest
from manga_gui.models import Kind, PackerOptions
from manga_gui.runner import PipelineResult, StepResult
from manga_gui.store import Store


def _result(rc: int = 0) -> PipelineResult:
    return PipelineResult(
        steps=[
            StepResult("packer", ["python", "-m", "packer.main"], 0, 1.5),
            StepResult("convertor", ["python", "-m", "convertor.main"], rc, 2.0),
        ],
        started_at="2026-11-04T10:00:00+01:00",
        duration=3.5,
        dry_run=True,
    )


def test_data_dir_layout(tmp_path: Path) -> None:
    store = Store(tmp_path)
    assert store.projects_dir == tmp_path / "projects"
    assert store.runs_dir == tmp_path / "runs"


def test_xdg_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    store = Store()
    assert store.projects_dir == tmp_path / "cfg" / "manga_manager" / "projects"
    assert store.runs_dir == tmp_path / "state" / "manga_manager" / "runs"


def test_xdg_fallback_to_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    store = Store()
    assert store.projects_dir == tmp_path / ".config/manga_manager/projects"
    assert store.runs_dir == tmp_path / ".local/state/manga_manager/runs"


def test_project_round_trip(tmp_path: Path, make_project) -> None:
    store = Store(tmp_path / "data")
    assert store.list_projects() == []
    p = make_project(
        tmp_path / "lib",
        name="Saga",
        kind=Kind.COMIC,
        packer=PackerOptions(serie="Saga", batch="v01:1..6"),
    )
    path = store.save_project(p)
    assert path == tmp_path / "data" / "projects" / "saga.json"
    assert store.has_project("saga")
    assert store.load_project("saga") == p
    other = make_project(tmp_path / "lib2", name="Akira")
    store.save_project(other)
    assert [x.slug for x in store.list_projects()] == ["akira", "saga"]


def test_list_projects_skips_corrupt(tmp_path: Path, make_project) -> None:
    store = Store(tmp_path)
    store.save_project(make_project(tmp_path, name="Good"))
    (store.projects_dir / "bad.json").write_text("{not json")
    (store.projects_dir / "list.json").write_text("[]")
    assert [p.slug for p in store.list_projects()] == ["good"]


def test_load_missing_project(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Store(tmp_path).load_project("nope")


@pytest.mark.parametrize("slug", ["../evil", "Upper", "", "a/b"])
def test_invalid_slug_rejected(tmp_path: Path, slug: str) -> None:
    with pytest.raises(ValueError):
        Store(tmp_path).project_path(slug)


def test_delete_project(tmp_path: Path, make_project) -> None:
    store = Store(tmp_path)
    p = make_project(tmp_path, name="X")
    store.save_project(p)
    store.save_run("x", _result(), "log")
    assert store.delete_project("x") is True
    assert store.delete_project("x") is False
    assert len(store.list_runs("x")) == 1
    store.delete_project("x", purge_runs=True)
    assert store.list_runs("x") == []


def test_run_round_trip(tmp_path: Path) -> None:
    store = Store(tmp_path)
    assert store.list_runs("saga") == []
    rec1 = store.save_run("saga", _result(0), "line 1\nline 2\n")
    rec2 = store.save_run("saga", _result(3), "boom\n")
    assert rec1.log_path == tmp_path / "runs" / "saga" / f"{rec1.run_id}.log"
    assert (tmp_path / "runs" / "saga" / f"{rec1.run_id}.json").is_file()

    loaded = store.load_run("saga", rec1.run_id)
    assert loaded == rec1
    assert loaded.result.ok and loaded.result.dry_run
    assert store.read_run_log("saga", rec1.run_id) == "line 1\nline 2\n"

    runs = store.list_runs("saga")
    assert [r.run_id for r in runs] == [rec2.run_id, rec1.run_id]
    assert runs[0].result.exit_code == 3
    assert not runs[0].result.ok

    store.delete_run("saga", rec2.run_id)
    assert [r.run_id for r in store.list_runs("saga")] == [rec1.run_id]


def test_invalid_run_id_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Store(tmp_path).load_run("saga", "../../etc/passwd")


def test_read_missing_log(tmp_path: Path) -> None:
    store = Store(tmp_path)
    rec = store.save_run("saga", _result(), "x")
    rec.log_path.unlink()
    assert store.read_run_log("saga", rec.run_id) == ""
