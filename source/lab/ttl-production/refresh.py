#!/usr/bin/env python3
"""Retain pre-friend object evidence before final coordinated acquisition."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import run


def main():
    release = run.OUT / 'lru-source-release.json'
    run.need(release.exists(), 'explicit LRU writer release required')
    admitted = json.loads(release.read_text())
    header = run.ROOT / 'source/core/StarLruCache.hpp'
    run.need(admitted['stable'] is True and run.sha(header) == admitted['sha256'], 'released LRU source pin')
    archive = run.OUT / 'pre-friend-objects.tar.gz'
    run.need(not archive.exists(), 'one historical retirement only')
    selected = sorted(p for p in run.OUT.iterdir() if p.is_file() and
        (p.name.startswith(('native-', 'native.', 'ttl-', 'ttl.', 'combined-', 'combined.'))
         or p.name in ['verification.stdout', 'verification.stderr']))
    run.need(len(selected) > 20, 'historical product selection incomplete')
    # Checkpoint bytes are retrieved read-only, NEVER restored over live files.
    before = subprocess.check_output(['/usr/bin/git', 'show', '6630f39c:source/core/StarLruCache.hpp'], cwd=run.ROOT)
    expected = json.loads((run.OUT / 'native-artifact.json').read_text())['dependencies'][str(header)]
    run.need(hashlib.sha256(before).hexdigest() == expected, 'exact pre-friend LRU byte recovery')
    members = {p.name: p.read_bytes() for p in selected}
    members['historical-source/StarLruCache.hpp'] = before
    for path in [*run.OWNED, run.HERE / 'probe.cpp', run.HERE / 'run.py']:
        members['historical-source/' + path.name] = path.read_bytes()
    manifest = {name: dict(sha256=hashlib.sha256(data).hexdigest(), size=len(data)) for name, data in members.items()}
    with tarfile.open(archive, 'w:gz') as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    with tarfile.open(archive, 'r:gz') as tar:
        run.need(set(tar.getnames()) == set(manifest), 'archive exact membership')
        for item in tar:
            data = tar.extractfile(item).read()
            run.need(dict(sha256=hashlib.sha256(data).hexdigest(), size=len(data)) == manifest[item.name], 'reconstruction BEFORE prune')
    run.dump(run.OUT / 'pre-friend-manifest.json', dict(archiveSha256=run.sha(archive), members=manifest,
        disposition='historical successful compile-only acquisition BEFORE coordinated LRU friend edit; not fresh final input closure'))
    for path in selected:
        run.need(run.sha(path) == manifest[path.name]['sha256'], 'changed original blocks prune')
        path.unlink()
    # Existing CMake-only profiles are independent of LRU header byte contents.
    run.objects()
    run.need(run.sha(header) == admitted['sha256'], 'LRU release drift during final probes')


if __name__ == '__main__':
    main()
