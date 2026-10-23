"""Causal setup/transfer/lifecycle tests. No model inference or GPU job."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from desktop import core


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.payload = b'fixed-payload-' * 400000
        self.requests = []
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                request_range = self.headers.get('Range')
                outer.requests.append(request_range)
                start = int(request_range.split('=')[1].split('-')[0]) if request_range and self.path != '/ignore-range' else 0
                body = outer.payload[start:]
                self.send_response(206 if start else 200)
                self.send_header('Content-Length', str(len(body)))
                if start:
                    self.send_header('Content-Range', f'bytes {start}-{len(outer.payload)-1}/{len(outer.payload)}')
                self.end_headers()
                try: self.wfile.write(body)
                except (ConnectionError, OSError): pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.asset = dict(url=f'http://127.0.0.1:{self.server.server_port}/data', bytes=len(self.payload), sha256=hashlib.sha256(self.payload).hexdigest())
        self.target = self.base / 'test.bin'
        self.cancel = threading.Event()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(3); self.tmp.cleanup()

    def download(self, progress=lambda *a: None):
        return core.download(self.asset, self.target, self.cancel, progress)

    def test_real_http_transfer_then_reuses_verified_file_without_network(self):
        self.download()
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.download()
        self.assertEqual(len(self.requests), 1)

    def test_cancelled_transfer_resumes_exact_range_and_matches_original(self):
        def stop(done, total, text):
            if done >= 1024**2 and text.startswith('Скачивание'):
                self.cancel.set()
        with self.assertRaises(core.Cancelled): self.download(stop)
        self.assertFalse(self.target.exists())
        partial = self.target.with_name('test.bin.part')
        offset = partial.stat().st_size
        self.assertGreater(offset, 0)
        self.cancel.clear(); self.download()
        self.assertEqual(self.requests[-1], f'bytes={offset}-')
        self.assertEqual(self.target.read_bytes(), self.payload)

    def test_ignored_range_restarts_only_owned_partial(self):
        self.asset['url'] = self.asset['url'].replace('/data', '/ignore-range')
        partial = self.target.with_name('test.bin.part')
        partial.write_bytes(self.payload[:100])
        core.save(partial.with_name(partial.name + '.json'), self.asset)
        self.download()
        self.assertEqual(self.target.read_bytes(), self.payload)

    def test_different_target_and_unknown_partial_are_not_replaced(self):
        self.target.write_bytes(b'personal-file')
        with self.assertRaises(ValueError): self.download()
        self.assertEqual(self.target.read_bytes(), b'personal-file')
        self.assertEqual(self.requests, [])
        self.target.unlink()
        partial = self.target.with_name('test.bin.part'); partial.write_bytes(b'unknown')
        with self.assertRaises(ValueError): self.download()
        self.assertEqual(partial.read_bytes(), b'unknown')
        self.assertEqual(self.requests, [])

    def test_corrupted_transfer_is_never_published_as_complete(self):
        self.asset['sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.download()
        self.assertFalse(self.target.exists())
        self.assertTrue(self.target.with_name('test.bin.part').exists())

    def test_insufficient_disk_space_never_contacts_remote(self):
        with patch.object(core.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 0})()):
            with self.assertRaises(ValueError): self.download()
        self.assertEqual(self.requests, [])


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def test_zip_rejects_traversal_windows_aliases_duplicates_and_symlinks_before_extract(self):
        for names in [['../outside'], ['C'+':/outside'], ['/outside'], ['ok.', 'else'], ['CON.txt'], ['name', 'NAME']]:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w') as z:
                for name in names: z.writestr(name, b'x')
            with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z, self.subTest(names=names):
                with self.assertRaises(ValueError): core.zip_members(z, self.base / 'destination')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            info = zipfile.ZipInfo('link'); info.external_attr = (stat.S_IFLNK | 0o777) << 16; z.writestr(info, '../outside')
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
            with self.assertRaises(ValueError): core.zip_members(z, self.base / 'destination')
        self.assertFalse((self.base / 'destination').exists())

    def test_cuda_detection_accepts_root_or_bin_and_ignores_incomplete_folder(self):
        fake = self.base / 'cuda'; (fake / 'bin').mkdir(parents=True)
        for name in core.CUDA_DLLS: (fake / 'bin' / name).write_bytes(b'dll')
        self.assertEqual(core.cuda_bin(fake), fake / 'bin')
        env = dict(CUDA_PATH=str(fake), PATH='', ProgramFiles=str(self.base / 'empty'))
        self.assertEqual(core.detect_cuda(env), str(fake / 'bin'))
        (fake / 'bin' / core.CUDA_DLLS[0]).unlink()
        self.assertEqual(core.detect_cuda(env), '')

    def test_existing_models_and_runtime_are_reused_without_download(self):
        assets = {}; downloads = []
        config = dict(port=8442)
        for key in ('sd_cli', 'diffusion_model', 'llm', 'vae'):
            p = self.base / (key + '.bin'); p.write_bytes(key.encode())
            config[key] = str(p)
            assets[key] = dict(file=p.name, bytes=p.stat().st_size, sha256=core.sha(p))
            downloads.append(dict(role=key, target='models/' + p.name, **assets[key], **({'extract_to': 'runtime'} if key == 'sd_cli' else {})))
        cuda = self.base / 'cuda'; cuda.mkdir()
        for name in core.CUDA_DLLS: (cuda / name).write_bytes(b'dll')
        config['cuda_bin'] = str(cuda)
        installer = core.Installer(dict(configured_assets=assets, runtime_files=[assets['sd_cli']], downloads=downloads))
        with patch.object(core, 'download') as download:
            result = installer.install(config, self.base / 'data', threading.Event(), lambda *a: None)
        download.assert_not_called(); self.assertEqual(config, result)
        self.assertEqual(installer.validate(result), [])

    def test_cuda_install_uses_pinned_archives_and_keeps_existing_dlls(self):
        package = self.base / 'cuda.zip'
        with zipfile.ZipFile(package, 'w') as z:
            for name in core.CUDA_DLLS: z.writestr('cuda/bin/' + name, name.encode())
            z.writestr('cuda/LICENSE', b'test license')
        a = dict(id='test', name='test', file='cuda.zip', dlls=list(core.CUDA_DLLS))
        installer = core.Installer(dict(cuda_downloads=[a]))
        storage = self.base / 'data'; storage.mkdir()
        with patch.object(core, 'download', return_value=package):
            folder = installer.install_cuda(storage, threading.Event(), lambda *a: None)
            self.assertEqual(core.cuda_bin(folder), folder)
            self.assertTrue((storage / 'cuda/licenses/test/LICENSE').is_file())
            (folder / core.CUDA_DLLS[0]).write_bytes(b'personal')
            with self.assertRaises(ValueError): installer.install_cuda(storage, threading.Event(), lambda *a: None)
            self.assertEqual((folder / core.CUDA_DLLS[0]).read_bytes(), b'personal')

    @unittest.skipUnless(os.name == 'nt', 'Windows application lifecycle')
    def test_real_server_start_reuse_stop_restart_and_reject_foreign_state(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        config = self.base / 'config.local.json'
        core.save(config, dict(port=port))
        control = core.ServerController(config)
        try:
            first = control.start()
            self.assertEqual(control.start()['instance'], first['instance'])
            with urllib.request.urlopen(first['base_url'] + '/api/health') as r: self.assertEqual(json.load(r)['instance'], first['instance'])
            control.stop(); self.assertIsNone(control.state())
            second = control.start()
            self.assertEqual(first['url'], second['url'])
            self.assertNotEqual(first['instance'], second['instance'])
            state = json.loads(control.state_path.read_text(encoding='utf-8'))
            core.save(control.state_path, dict(state, instance='foreign'))
            self.assertIsNone(control.state())
            with urllib.request.urlopen(first['base_url'] + '/api/health') as r: self.assertEqual(json.load(r)['instance'], second['instance'])
            core.save(control.state_path, state)
        finally: control.stop()
        self.assertIsNotNone(control.process.poll())


if __name__ == '__main__': unittest.main()
