"""Build the GUI from a Windows Python with the pinned build requirements installed."""
import argparse
import json
from importlib.metadata import distribution
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def include_notices(bundle):
    bundle = Path(bundle)
    licenses = bundle / 'licenses'
    licenses.mkdir(exist_ok=True)
    sources = {
        'Project-MIT.txt': ROOT / 'LICENSE',
        'Python.txt': Path(sys.base_prefix) / 'LICENSE.txt',
        'Tcl.txt': ROOT / 'desktop/licenses/Tcl-license.terms',
        'OpenSSL-3.0.19.txt': ROOT / 'desktop/licenses/OpenSSL-3.0.19.txt',
        'zlib-1.3.1.txt': ROOT / 'desktop/licenses/zlib-1.3.1.txt',
        'RUNTIME_NOTICES.md': ROOT / 'desktop/licenses/RUNTIME_NOTICES.md',
        'Tk.txt': Path(sys.base_prefix) / 'tcl/tk8.6/license.terms',
    }
    dist = distribution('pyinstaller')
    sources['PyInstaller.txt'] = dist.locate_file(next(p for p in dist.files if str(p).replace('\\','/').endswith('/licenses/COPYING.txt')))
    for name, path in sources.items():
        if not path.is_file():
            raise RuntimeError('Missing required license: ' + name)
        shutil.copyfile(path, licenses / name)
    shutil.copyfile(ROOT / 'desktop/START_HERE.txt', bundle / 'START_HERE.txt')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--work', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed', '--name', 'FLUX3-Manager',
               '--distpath', str(args.output.resolve()), '--workpath', str(args.work.resolve()), '--specpath', str(args.work.resolve()),
               '--paths', str(ROOT / 'scripts'), '--paths', str(ROOT), '--hidden-import', 'app', '--hidden-import', 'generate']
    for name in ['ui', 'prompts', 'assets.lock.json', 'config.example.json', 'cases.json', 'battle-cases.json']:
        command += ['--add-data', str(ROOT / name) + ';' + name if (ROOT / name).is_dir() else str(ROOT / name) + ';.']
    command += [str(ROOT / 'desktop/launcher.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    include_notices(args.output / 'FLUX3-Manager')
    print(json.dumps(dict(status='PASS', directory=str(args.output / 'FLUX3-Manager'))))


if __name__ == '__main__':
    main()
