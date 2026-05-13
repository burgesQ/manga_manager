import logging

from packer.cli import setup_logging


def test_color_enabled_shows_emoji_and_ansi(capsys):
    # Force colour output and log an INFO message
    setup_logging(verbose=False, force_color=True)
    logger = logging.getLogger("test_color_enabled")
    logger.info("hello color")
    captured = capsys.readouterr()
    err = captured.err
    assert "✅ INFO:" in err
    assert "\x1b[" in err  # ANSI escape sequences present when coloured


def test_color_disabled_no_ansi_but_emoji_present(capsys):
    # Force colour off: expect emoji but no ANSI escapes
    setup_logging(verbose=False, force_color=False)
    logger = logging.getLogger("test_color_disabled")
    logger.info("hello plain")
    err = capsys.readouterr().err
    assert "✅ INFO:" in err
    assert "\x1b[" not in err


def test_debug_level_shows_debug_emoji(capsys):
    # Verbose enables DEBUG level
    setup_logging(verbose=True, force_color=False)
    logger = logging.getLogger("test_debug")
    logger.debug("debugging")
    err = capsys.readouterr().err
    assert "🔧 DEBUG:" in err


def test_cli_loglevel_debug_shows_processing(tmp_path):
    import subprocess
    import sys
    import zipfile
    from pathlib import Path

    src = tmp_path / "src"
    src.mkdir()
    # create a chapter archive
    p = src / "Chapter 1.cbz"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("ComicInfo.xml", "<ComicInfo></ComicInfo>")
        z.writestr("001.jpg", "img")

    script = Path(__file__).resolve().parents[1] / "src" / "packer" / "main.py"
    cmd = [
        sys.executable,
        str(script),
        "--path",
        str(src),
        "--serie",
        "DebugSerie",
        "--volume",
        "1",
        "--chapter-range",
        "1",
        "--loglevel",
        "DEBUG",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert (
        res.returncode == 0
    ), f"packer failed: stdout={res.stdout} stderr={res.stderr}"
    assert "🔧 DEBUG:" in res.stderr
    assert "Extracting chapter 1" in res.stderr
