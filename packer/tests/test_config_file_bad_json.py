import subprocess
import sys
from pathlib import Path


def run_packer(tmp_path: Path, args):
    script = Path(__file__).resolve().parents[1] / 'src' / 'packer' / 'main.py'
    cmd = [sys.executable, str(script)] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res


def test_invalid_packer_json_causes_error(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    # write an invalid JSON file
    (src / 'packer.json').write_text('{ not: valid, }')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'Broken',
        '--volume', '1',
        '--chapter-range', '1',
    ])
    # Expect CLI to error out with code 2 and an explanatory message that includes the file path
    assert res.returncode == 2
    out = (res.stderr or res.stdout)
    assert 'Invalid packer.json' in out
    assert str(src / 'packer.json') in out


def test_non_object_packer_json_causes_error(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    # write a valid JSON that is not an object (e.g., a list)
    (src / 'packer.json').write_text('[]')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'Broken',
        '--volume', '1',
        '--chapter-range', '1',
    ])
    # Expect CLI to error out with code 2 and mention packer.json path
    assert res.returncode == 2
    out = (res.stderr or res.stdout)
    assert 'Invalid packer.json' in out
    assert str(src / 'packer.json') in out
