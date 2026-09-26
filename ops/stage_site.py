#!/usr/bin/env python3
"""Stage committed, explicitly selected public files for exactly one site."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def stage(site, output, files):
    config = json.loads((ROOT / 'sites.json').read_text())[site]
    source = ROOT / config['source']
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Stage outside the repository in a new directory.')
    if output.exists():
        raise ValueError('Output already exists; use a new empty destination path.')
    selected = []
    for name in files:
        if name not in config['files']:
            raise ValueError(f'{name}: not in the {site} public allowlist')
        path = source / name
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError(f'{name}: symlinks and alternate paths are forbidden')
        relative = path.relative_to(ROOT).as_posix()
        committed = subprocess.check_output(['git', 'show', f'HEAD:{relative}'], cwd=ROOT)
        if path.read_bytes() != committed:
            raise ValueError(f'{name}: commit the reviewed changes before staging')
        if path.suffix == '.html':
            text = committed.decode()
            title = text.split('<title>', 1)[-1].split('</title>', 1)[0]
            brand = 'River Cruise Network' if site == 'rcn' else 'Discount Coach Tours'
            if brand not in title:
                raise ValueError(f'{name}: title does not identify {brand}')
            forbidden = ('book.discountcoachtours.ca', 'X-DCT-Token', 'DCT-') if site == 'rcn' else ('GTM-5B2VFP82', 'AW-10929471967', 'RCN-')
            if any(marker in text for marker in forbidden):
                raise ValueError(f'{name}: contains identifiers belonging to the other site')
        selected.append((name, path, committed))
    # Validate everything before writing anything.
    output.mkdir(parents=True, mode=0o755)
    for name, path, committed in selected:
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        if dest.read_bytes() != committed:
            raise ValueError(f'{name}: source changed while staging; do not deploy')
        print(hashlib.sha256(committed).hexdigest(), name)
    for path in [output, *output.rglob('*')]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    print(f'SITE: {site}; DOMAIN: {config["url"]}; DESTINATION: {config["destination"]}')
    print(f'Staged {len(selected)} files in {output}. Push the commit before uploading.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True, choices=['rcn', 'dct'])
    parser.add_argument('--output', required=True)
    parser.add_argument('files', nargs='+', help='Public file names relative to the selected site source')
    args = parser.parse_args()
    try:
        stage(args.site, args.output, args.files)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'STAGING REFUSED: {exc}\n')
