from pathlib import Path


def test_skips_existing_output(tmp_path: Path, make_vol, run_convertor):
    root = tmp_path / "root"
    root.mkdir()
    vol = make_vol(root, "Series v01")
    out = vol.with_suffix(vol.suffix + ".kepub.epub")
    out.write_text("existing")

    res = run_convertor(root)
    assert res.returncode == 0
    assert "skipping existing output" in (res.stdout + res.stderr)


def test_dry_run_shows_actions(tmp_path: Path, make_vol, run_convertor):
    root = tmp_path / "root"
    root.mkdir()
    make_vol(root, "Series v01")

    res = run_convertor(root, ["--dry-run"])
    assert res.returncode == 0
    assert "generated" in res.stderr
    assert "Series v01.kepub.epub" in res.stderr
