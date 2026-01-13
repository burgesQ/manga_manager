import json
from pathlib import Path


from packer.utils import (
    run_packer,
    make_cbz
)


def test_config_json_applies_defaults(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    # put a packer.json config with pattern fma and a batch file
    cfg = {
        'pattern': 'fma'
    }
    (src / 'packer.json').write_text(json.dumps(cfg))

    # create Chapter 16 and extras
    make_cbz(src, 'Chap 16.cbz')
    make_cbz(src, 'Chap 16.1.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'FMAConfig',
        '--volume', '1',
        '--chapter-range', '16',
    ])
    assert res.returncode == 0
    vol = src / 'FMAConfig v01'
    assert vol.exists()
    assert (vol / 'Chap 16.cbz').exists()
    assert (vol / 'Chap 16.1.cbz').exists()
