"""Build a deterministic SECCA skill archive without local run or dependency folders."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='0.1.0')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?', args.version):
        raise ValueError('Expected a release version')
    subprocess.run([sys.executable, str(ROOT / 'scripts/candidate.py'), 'verify-assets'], check=True, cwd=ROOT)
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    selected = [ROOT / name for name in names if name]
    if not selected or not any(path.name == 'SKILL.md' for path in selected):
        raise ValueError('Stage or commit the public source before packaging it')
    if any(set(path.relative_to(ROOT).parts) & {'node_modules', '.venv', '__pycache__', '.git', 'dist'} for path in selected):
        raise ValueError('Dependency folders and generated output cannot enter the skill archive')
    if subprocess.run(['git', 'diff', '--quiet'], cwd=ROOT).returncode:
        raise ValueError('Stage all tracked changes before packaging the public source')
    tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, text=True).strip()
    source = subprocess.check_output(['git', 'archive', '--format=tar', tree], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(source), mode='r:') as tar:
        payloads = {}
        for member in tar:
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Skill archives cannot contain links or special files')
            payloads[member.name] = tar.extractfile(member).read()
    if set(payloads) != {path.relative_to(ROOT).as_posix() for path in selected}:
        raise ValueError('Git archive differs from the selected public source inventory')
    args.output.mkdir(parents=True, exist_ok=True)
    archive_path = args.output / ('secca-' + args.version + '.zip')
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(payloads.items()):
            info = zipfile.ZipInfo('secca/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError('Skill archive CRC verification failed')
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix('.zip.sha256').write_text(digest + '  ' + archive_path.name + '\n', encoding='ascii')
    print(json.dumps({'archive': str(archive_path), 'files': len(selected), 'sha256': digest,
                      'bytes': archive_path.stat().st_size, 'source_tree': tree}))


if __name__ == '__main__':
    main()
