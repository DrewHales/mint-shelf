#!/usr/bin/env python3
"""Build the downloadable installer from an explicit list of project files."""
import hashlib
from pathlib import Path
import re
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = sys.argv[1] if len(sys.argv) == 2 else ''
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise SystemExit('Usage: python3 scripts/build_release.py MAJOR.MINOR.PATCH')
    app_source = (ROOT / 'shelf/app.py').read_text()
    if f"version='{version}'" not in app_source:
        raise SystemExit('Release version must match the About dialog version.')
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    name = f'mint-shelf-{version}'
    archive = output / f'{name}-linux-mint.tar.gz'
    files = [ROOT / p for p in ('install.sh', 'install.py', 'mint-shelf', 'README.md', 'LICENSE', 'CONTRIBUTING.md')]
    files += sorted((ROOT / 'shelf').glob('*.py'))
    with tarfile.open(archive, 'w:gz') as bundle:
        for path in files:
            info = bundle.gettarinfo(str(path), arcname=f'{name}/{path.relative_to(ROOT)}')
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mode = 0o755 if path.name in ('install.sh', 'mint-shelf') else 0o644
            with path.open('rb') as source:
                bundle.addfile(info, source)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n')
    print(archive)


if __name__ == '__main__':
    main()
