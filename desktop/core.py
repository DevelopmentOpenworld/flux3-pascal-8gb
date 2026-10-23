"""Pinned downloads and management of exactly one configured local server."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from scripts.i18n import msg, joined

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
CUDA_DLLS = ('cudart64_12.dll', 'cublas64_12.dll', 'cublasLt64_12.dll')


class Cancelled(Exception):
    pass


def checkpoint(cancel):
    if cancel and cancel.is_set():
        raise Cancelled(msg('download_cancelled'))


def sha(path, cancel=None):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            checkpoint(cancel)
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def asset_matches(path, asset, cancel=None):
    return Path(path).is_file() and Path(path).stat().st_size == asset['bytes'] and sha(path, cancel) == asset['sha256']


def cuda_bin(path):
    p = Path(path)
    for candidate in (p, p / 'bin'):
        if all((candidate / n).is_file() for n in CUDA_DLLS):
            return candidate.resolve()
    return None


def detect_cuda(environ=None):
    env = os.environ if environ is None else environ
    candidates = [env[k] for k in sorted(env) if k == 'CUDA_PATH' or k.startswith('CUDA_PATH_V12')]
    base = Path(env.get('ProgramFiles', '')) / 'NVIDIA GPU Computing Toolkit/CUDA'
    if base.is_dir():
        candidates += [str(p) for p in sorted(base.glob('v12.*'), reverse=True)]
    candidates += env.get('PATH', '').split(os.pathsep)
    seen = set()
    for p in candidates:
        if not p or p.casefold() in seen:
            continue
        seen.add(p.casefold())
        found = cuda_bin(p)
        if found:
            return str(found)
    return ''


def download(asset, target, cancel, progress, opener=urllib.request.urlopen):
    """Resume only a partial created for this exact pinned object; never replace user files."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        progress(0, asset['bytes'], msg('checking_existing', file=target.name))
        if not asset_matches(target, asset, cancel):
            raise ValueError(msg('existing_mismatch', file=target.name))
        progress(asset['bytes'], asset['bytes'], msg('reuse_existing', file=target.name))
        return target
    partial = target.with_name(target.name + '.part')
    owner = partial.with_name(partial.name + '.json')
    identity = {k: asset[k] for k in ('url', 'bytes', 'sha256')}
    if partial.exists():
        if not owner.is_file() or json.loads(owner.read_text(encoding='utf-8')) != identity:
            raise ValueError(msg('unknown_partial', file=partial.name))
    else:
        if owner.exists():
            if json.loads(owner.read_text(encoding='utf-8')) != identity:
                raise ValueError(msg('metadata_conflict', file=target.name))
        save(owner, identity)
        partial.touch(exist_ok=False)
    offset = partial.stat().st_size
    if offset > asset['bytes']:
        raise ValueError(msg('partial_large', file=target.name))
    checkpoint(cancel)
    if shutil.disk_usage(target.parent).free < asset['bytes'] - offset + 512 * 1024**2:
        raise ValueError(msg('disk_download', file=target.name))
    if offset < asset['bytes']:
        headers = {'User-Agent': 'FLUX3-Pascal-Manager/3', 'Accept-Encoding': 'identity'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        with opener(urllib.request.Request(asset['url'], headers=headers), timeout=30) as response:
            status = response.status
            if offset and status == 206:
                if not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                    raise ValueError(msg('range_invalid'))
            elif status == 200:
                offset = 0
            else:
                raise ValueError(msg('download_response'))
            with partial.open('ab' if offset else 'wb') as output:
                while True:
                    checkpoint(cancel)
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    if offset + len(chunk) > asset['bytes']:
                        raise ValueError(msg('download_oversize'))
                    output.write(chunk)
                    offset += len(chunk)
                    progress(offset, asset['bytes'], msg('downloading', file=target.name))
    progress(offset, asset['bytes'], msg('checking_sha', file=target.name))
    if not asset_matches(partial, asset, cancel):
        raise ValueError(msg('hash_mismatch', file=target.name))
    checkpoint(cancel)
    # target may have appeared while the network request was in flight.
    if target.exists():
        raise ValueError(msg('target_appeared'))
    partial.rename(target)
    owner.unlink()
    progress(asset['bytes'], asset['bytes'], msg('file_done', file=target.name))
    return target


def zip_members(archive, destination):
    """Reject Windows aliases, links and traversal before writing the first member."""
    base = Path(destination).resolve()
    seen = set()
    total = 0
    members = archive.infolist()
    if len(members) > 20000:
        raise ValueError(msg('zip_count'))
    for m in members:
        p = PurePosixPath(m.filename.replace('\\', '/'))
        if p.is_absolute() or not p.parts or any(x in ('.', '..') or x.rstrip(' .') != x or re.search(r'[<>:"|?*\x00-\x1f]', x) or re.fullmatch(r'(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?', x) for x in p.parts):
            raise ValueError(msg('zip_unsafe'))
        if stat.S_ISLNK(m.external_attr >> 16):
            raise ValueError(msg('zip_links'))
        key = str(p).casefold().rstrip('/')
        if key in seen:
            raise ValueError(msg('zip_duplicate'))
        seen.add(key)
        target = base.joinpath(*p.parts)
        if not target.resolve().is_relative_to(base):
            raise ValueError(msg('zip_escape'))
        total += m.file_size
        if total > 5 * 1024**3:
            raise ValueError(msg('zip_size'))
    return members


def extract_zip(path, destination, cancel):
    import zipfile
    with zipfile.ZipFile(path) as z:
        members = zip_members(z, destination)
        if shutil.disk_usage(Path(destination).parent).free < sum(m.file_size for m in members) + 512 * 1024**2:
            raise ValueError(msg('disk_extract'))
        for m in members:
            checkpoint(cancel)
            z.extract(m, destination)


class Installer:
    def __init__(self, lock=None):
        self.lock = lock or json.loads((ROOT / 'assets.lock.json').read_text(encoding='utf-8'))

    def validate(self, config, cancel=None, progress=lambda *a: None):
        errors = []
        for key in ('sd_cli', 'diffusion_model', 'llm', 'vae'):
            path = Path(config.get(key) or '__missing__')
            progress(0, 1, msg('checking_file', file=self.lock['configured_assets'][key]['file']))
            if not asset_matches(path, self.lock['configured_assets'][key], cancel):
                errors.append(msg('asset_invalid', file=self.lock['configured_assets'][key]['file']))
        engine_dir = Path(config.get('sd_cli') or '__missing__').parent
        for a in self.lock['runtime_files']:
            checkpoint(cancel)
            if not asset_matches(engine_dir / a['file'], a, cancel):
                errors.append(msg('engine_incomplete_file', file=a['file']))
        if not config.get('cuda_bin') or not cuda_bin(config['cuda_bin']):
            errors.append(msg('cuda_select'))
        port = config.get('port', 8440)
        if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
            errors.append(msg('port_range'))
        return errors

    def install(self, config, storage, cancel, progress):
        storage = Path(storage).resolve()
        storage.mkdir(parents=True, exist_ok=True)
        result = dict(config)
        for a in self.lock['downloads']:
            key = 'sd_cli' if a.get('extract_to') else a['role']
            existing = Path(result.get(key) or '__missing__')
            if asset_matches(existing, self.lock['configured_assets'][key], cancel):
                if key != 'sd_cli' or all(asset_matches(existing.parent / f['file'], f, cancel) for f in self.lock['runtime_files']):
                    progress(1, 1, msg('reuse_selected', file=existing.name))
                    continue
                raise ValueError(msg('engine_incomplete'))
            if result.get(key) and existing.exists():
                raise ValueError(msg('selected_mismatch', file=existing.name))
            target = storage / a['target']
            archive = download(a, target, cancel, progress)
            if key == 'sd_cli':
                destination = storage / 'runtime'
                if destination.exists():
                    if not all(asset_matches(destination / f['file'], f, cancel) for f in self.lock['runtime_files']):
                        raise ValueError(msg('runtime_mismatch'))
                else:
                    with tempfile.TemporaryDirectory(prefix='.flux3-unpack-', dir=storage) as tmp:
                        stage = Path(tmp) / 'runtime'
                        stage.mkdir()
                        progress(0, 1, msg('extract_engine'))
                        extract_zip(archive, stage, cancel)
                        if not all(asset_matches(stage / f['file'], f, cancel) for f in self.lock['runtime_files']):
                            raise ValueError(msg('engine_contents'))
                        stage.rename(destination)
                result[key] = str(destination / 'sd-cli.exe')
            else:
                result[key] = str(archive)
        if not result.get('cuda_bin') or not cuda_bin(result['cuda_bin']):
            installed = detect_cuda()
            if installed:
                result['cuda_bin'] = installed
            else:
                result['cuda_bin'] = str(self.install_cuda(storage, cancel, progress))
        errors = self.validate(result, cancel, progress)
        if errors:
            raise ValueError(joined(errors))
        return result

    def install_cuda(self, storage, cancel, progress):
        storage = Path(storage).resolve()
        target_bin = storage / 'cuda/bin'
        for a in self.lock['cuda_downloads']:
            archive = download(a, storage / 'downloads' / a['file'], cancel, progress)
            with tempfile.TemporaryDirectory(prefix='.flux3-cuda-', dir=storage) as tmp:
                stage = Path(tmp) / 'unpack'
                stage.mkdir()
                progress(0, 1, msg('extract_cuda', file=a['name']))
                extract_zip(archive, stage, cancel)
                files = [f for f in stage.rglob('*') if f.is_file() and (f.name in a['dlls'] or f.name.lower().startswith('license'))]
                for name in a['dlls']:
                    if sum(f.name == name for f in files) != 1:
                        raise ValueError(msg('cuda_ambiguous', file=name))
                for f in files:
                    checkpoint(cancel)
                    dest = target_bin / f.name if f.name in a['dlls'] else storage / 'cuda/licenses' / a['id'] / f.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if dest.exists():
                        if sha(dest, cancel) != sha(f, cancel):
                            raise ValueError(msg('cuda_mismatch', file=dest.name))
                    else:
                        with f.open('rb') as src, dest.open('xb') as out:
                            shutil.copyfileobj(src, out)
        if not cuda_bin(target_bin):
            raise ValueError(msg('cuda_check_failed'))
        return target_bin


class ServerController:
    def __init__(self, config_path, timeout=20):
        self.config_path = Path(config_path).resolve()
        self.state_path = self.config_path.parent / 'app-state.json'
        self.process = None
        self.tree = None
        self.timeout = timeout

    def state(self):
        try:
            d = json.loads(self.state_path.read_text(encoding='utf-8'))
            u = urlparse(d['base_url'])
            if u.scheme != 'http' or u.hostname != '127.0.0.1' or u.path or u.username or u.password:
                return None
            if not d['url'].startswith(d['base_url'] + '/#session='):
                return None
            if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', d['url'].split('#session=')[1]):
                return None
            with urllib.request.urlopen(d['base_url'] + '/api/health', timeout=1) as r:
                h = json.load(r)
            return d if h.get('app') == 'flux3-local' and h.get('instance') == d['instance'] else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def start(self):
        current = self.state()
        if current:
            return current
        if self.process and self.process.poll() is None:
            raise ValueError(msg('server_starting'))
        args = [sys.executable, '--server'] if getattr(sys, 'frozen', False) else [sys.executable, str(ROOT / 'desktop/launcher.py'), '--server']
        args += ['--config', str(self.config_path), '--no-browser']
        log_path = self.config_path.parent / 'server.log'
        with log_path.open('w', encoding='utf-8') as log:
            self.process = subprocess.Popen(args, cwd=self.config_path.parent, stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        from app import OwnedProcessTree
        self.tree = OwnedProcessTree(self.process)
        end = time.monotonic() + self.timeout
        while time.monotonic() < end:
            current = self.state()
            if current:
                return current
            if self.process.poll() is not None:
                if self.tree:
                    self.tree.close(); self.tree = None
                raise ValueError(msg('server_start_failed'))
            time.sleep(0.15)
        self.stop()
        raise ValueError(msg('server_timeout'))

    def stop(self):
        current = self.state()
        if current:
            token = current['url'].split('#session=')[1]
            req = urllib.request.Request(current['base_url'] + '/api/shutdown', data=b'{}', headers={'X-Session': token, 'Content-Type': 'application/json'}, method='POST')
            try:
                with urllib.request.urlopen(req, timeout=35) as r:
                    json.load(r)
            except OSError:
                pass
            end = time.monotonic() + self.timeout
            while self.state() and time.monotonic() < end:
                time.sleep(0.15)
        if self.process:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if self.tree:
                    self.tree.close(); self.tree = None
                self.process.wait(timeout=5)
        if self.state():
            raise ValueError(msg('server_stop_failed'))
        if self.tree:
            self.tree.close(); self.tree = None
