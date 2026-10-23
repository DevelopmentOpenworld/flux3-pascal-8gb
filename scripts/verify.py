"""Verify stored evidence without running a model; optionally verify external assets."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def png(path):
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    offset = 8
    info = {}
    texts = {}
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        body = data[offset+8:offset+8+length]
        crc = struct.unpack('>I', data[offset+8+length:offset+12+length])[0]
        assert binascii.crc32(kind+body) & 0xffffffff == crc, (path, kind)
        if kind == b'IHDR':
            info['width'], info['height'] = struct.unpack('>II', body[:8])
        elif kind == b'tEXt':
            k, v = body.split(b'\x00', 1)
            texts[k.decode('latin-1')] = v.decode('utf-8', errors='replace')
        elif kind == b'zTXt':
            k, rest = body.split(b'\x00', 1)
            texts[k.decode('latin-1')] = zlib.decompress(rest[1:]).decode('utf-8', errors='replace')
        offset += 12 + length
        if kind == b'IEND':
            assert offset == len(data), 'Trailing PNG data'
            info['texts'] = texts
            return info
    raise AssertionError('PNG has no IEND')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', help='Also read and hash external runtime/model files')
    args = ap.parse_args()
    checks = 0
    cases = {c['id']: c for name in ['cases.json','battle-cases.json','ui-cases.json']
             for c in json.loads((ROOT/name).read_text(encoding='utf-8'))['cases']}
    assert len(cases) == 38
    checks += 1
    for c in cases.values():
        p = (ROOT / c['prompt_file']).resolve()
        assert p.is_relative_to(ROOT.resolve()) and p.is_file()
        assert c['width'] % 16 == 0 and c['height'] % 16 == 0
        assert c['seed'] in [42,7,123]
        checks += 1
    records = [p for p in (ROOT/'results').glob('*/record.json') if not p.parent.name.startswith('local-')]
    assert len(records)==39
    reviews={r['run_id']:r for r in json.loads((ROOT/'visual-review.json').read_text(encoding='utf-8'))['reviews']}
    for path in records:
        r = json.loads(path.read_text(encoding='utf-8'))
        c = cases[r['case_id']]
        assert sha(ROOT / c['prompt_file']) == r['prompt_sha256'], path
        checks += 1
        if r['status'] != 'PASS':
            continue
        image = path.parent / 'image.png'
        assert sha(image) == r['image_sha256'], path
        meta = png(image)
        assert (meta['width'], meta['height']) == (c['width'], c['height']), path
        parameters = meta['texts']['parameters']
        embedded = json.loads(parameters.split('SDCPP: ', 1)[1])
        assert embedded['seed'] == c['seed'] and embedded['sampling']['steps'] == 16, path
        assert embedded['generator']['commit'] == '39bc9d0', path
        assert embedded['models']['diffusion_model'] == 'flux3-image-klein-Q4_0.gguf', path
        assert embedded['prompt']['positive'] == (ROOT / c['prompt_file']).read_bytes().decode('utf-8'), path
        assert r['returncode'] == 0 and r['stop_reason'] is None, path
        assert r['seconds'] > r['sampling_seconds'] > 0, path
        assert reviews[r['run_id']]['image_sha256']==r['image_sha256'],path
        sensors=[json.loads(line) for line in (path.parent/'sensors.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        assert len(sensors)==r['sample_count'],path
        assert max(s['gpu_used_mib'] for s in sensors)==r['peak_gpu_used_mib'],path
        assert min(s['available_mib'] for s in sensors)==r['minimum_available_mib'],path
        assert int(r['command'][r['command'].index('-s')+1])==c['seed'],path
        checks += 12
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
        lock = json.loads((ROOT / 'assets.lock.json').read_text(encoding='utf-8'))
        for key, expected in lock['configured_assets'].items():
            p = Path(config[key])
            p = p if p.is_absolute() else ROOT / p
            assert p.stat().st_size == expected['bytes'] and sha(p) == expected['sha256'], key
            checks += 1
        runner = Path(config['sd_cli'])
        runner = runner if runner.is_absolute() else ROOT / runner
        for item in lock['runtime_files']:
            p = runner.parent / item['file']
            assert p.stat().st_size == item['bytes'] and sha(p) == item['sha256'], p.name
            checks += 1
    manifest = ROOT / 'MANIFEST.json'
    if manifest.exists():
        expected = json.loads(manifest.read_text(encoding='utf-8'))['files']
        names=[e['path'] for e in expected]
        assert len(names)==len(set(n.lower() for n in names))
        for entry in expected:
            p = (ROOT / entry['path']).resolve()
            assert p.is_relative_to(ROOT.resolve()) and p.is_file()
            assert p.stat().st_size == entry['bytes'] and sha(p) == entry['sha256'], entry['path']
            checks += 1
    print(json.dumps({'status':'PASS', 'checks':checks, 'stored_runs':len(records), 'models_run':False}))


if __name__ == '__main__':
    main()
