"""Optional pinned downloads. Reuses matching files; never installs CUDA or Python packages."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--list', action='store_true', help='Print URLs and hashes without downloading')
    args = ap.parse_args()
    lock = json.loads((ROOT / 'assets.lock.json').read_text(encoding='utf-8'))
    if args.list:
        print(json.dumps(lock, ensure_ascii=False, indent=2))
        return
    for asset in lock['downloads']:
        target = ROOT / asset['target']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.stat().st_size != asset['bytes'] or sha(target) != asset['sha256']:
                raise SystemExit(f'Different existing file: {target}; choose its disposition manually')
            print('REUSE ' + asset['target'], flush=True)
        else:
            if shutil.disk_usage(target.parent).free < asset['bytes'] + 2 * 1024**3:
                raise SystemExit('Not enough disk headroom')
            partial = target.with_name(target.name + '.part')
            if partial.exists():
                raise SystemExit(f'Existing incomplete download: {partial}; inspect before retrying')
            request = urllib.request.Request(asset['url'], headers={'User-Agent': 'flux3-pascal-reproduction'})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open('xb') as output:
                shutil.copyfileobj(response, output, length=4 * 1024 * 1024)
            if partial.stat().st_size != asset['bytes'] or sha(partial) != asset['sha256']:
                raise SystemExit('Download checksum mismatch: ' + asset['target'])
            partial.replace(target)
            print('VERIFIED ' + asset['target'], flush=True)
        if asset.get('extract_to'):
            destination = ROOT / asset['extract_to']
            if destination.exists():
                print('PRESERVE existing runtime; use verify.py --config to check its files')
                continue
            with zipfile.ZipFile(target) as archive:
                seen = set()
                for member in archive.infolist():
                    p = PurePosixPath(member.filename.replace('\\', '/'))
                    if p.is_absolute() or '..' in p.parts or any(':' in x for x in p.parts):
                        raise SystemExit('Unsafe archive entry')
                    key = str(p).casefold()
                    if key in seen:
                        raise SystemExit('Duplicate archive entry')
                    seen.add(key)
                    if not (destination / Path(*p.parts)).resolve().is_relative_to(destination.resolve()):
                        raise SystemExit('Archive entry escapes runtime directory')
                destination.mkdir()
                archive.extractall(destination)


if __name__ == '__main__':
    main()
