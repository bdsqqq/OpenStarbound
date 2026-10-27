#!/usr/bin/env python3
"""Exact-byte retention proof for the immutable accepted LRU certificate.

NOT a new semantic replay or renewal of old inode/ctime/current-origin seals.
Additional archive manifests require an explicit externally trusted SHA256 pin.
No restore, subprocess, source waiver, hash-only fallback or receipt rewrite.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'build/migration-evidence-archive'
CERTIFICATE = ROOT / 'build/lru-final-qualification-r3/qualification.json'
CERT_SHA = '7b22bb0d323d85282aa958cb68054d119d5ad035a0bf5eb175901cc6eee40635'
VERIFIER_SHA = '6a824fed7a72c752875b0079ac66d3982f2fa6f1a62c677bfc45a756e7964ae5'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def stream_hash(stream):
    h = hashlib.sha256()
    size = 0
    while block := stream.read(1048576):
        h.update(block)
        size += len(block)
    return h.hexdigest(), size


def physical_hash(path):
    with path.open('rb') as stream:
        return stream_hash(stream)


def verify(successors):
    need(physical_hash(CERTIFICATE)[0] == CERT_SHA, 'original certificate pin')
    certificate = json.loads(CERTIFICATE.read_bytes())
    need(physical_hash(ROOT / 'source/lab/lru-qualification/verify.py')[0] == VERIFIER_SHA,
         'original semantic verifier pin')
    pins = {str(ARCHIVE / 'runs' / run / 'manifest.json'): sha
            for run, sha in certificate['archiveManifestPins'].items()}
    for path, sha in successors:
        path = str(Path(path).absolute())
        need(path not in pins, 'duplicate successor manifest')
        need(Path(path).is_relative_to(ARCHIVE / 'runs'), 'successor outside archive runs')
        pins[path] = sha
    index = {}
    for path, sha in pins.items():
        p = Path(path)
        need(p.resolve() == p.absolute() and physical_hash(p)[0] == sha, 'manifest physical pin')
        m = json.loads(p.read_bytes())
        need(m['status'] == 'ARCHIVED_VERIFIED_PRUNED', 'manifest not fully verified/pruned')
        for row in m['entries']:
            original = ROOT / row['path']
            need(not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts
                 and Path(row['path']).parts[0] == 'build', 'manifest member outside build')
            key = str(original)
            need(key not in index, 'duplicate original archive membership')
            index[key] = (row, path)
    current = 0
    archived = []
    for name, old in certificate['physicalBindings'].items():
        p = Path(name)
        expected = (old['sha256'], old['size'])
        if p.exists():
            canonical = p.resolve(strict=True)
            need(stat.S_ISREG(canonical.stat().st_mode), 'current regular input')
            need(old['kind'] == 'current-regular' and str(canonical) == old['canonical'],
                 'original current canonical origin changed: ' + name)
            need(physical_hash(canonical) == expected, 'current byte integrity: ' + name)
            current += 1
        else:
            need(not p.is_symlink(), 'dangling original alias: ' + name)
            need(name in index, 'missing exact archive membership: ' + name)
            row, manifest = index[name]
            need((row['sha256'], row['size']) == expected, 'archive member hash/size: ' + name)
            blob = ARCHIVE / 'blobs' / old['sha256'][:2] / (old['sha256'] + '.gz')
            need(blob.resolve() == blob.absolute() and stat.S_ISREG(blob.lstat().st_mode),
                 'regular archive blob')
            with gzip.open(blob, 'rb') as stream:
                need(stream_hash(stream) == expected, 'archive reconstructed byte integrity: ' + name)
            archived.append(dict(path=name, sha256=old['sha256'], size=old['size'],
                                 manifest=manifest, originalOrigin=old['kind']))
    # Selected captures/storage/auxiliary remain live and have EXACT membership;
    # cleanup may archive historical lab inputs, not silently drop game products.
    members = set()
    for tree in certificate['productTrees']:
        root = Path(tree)
        need(root.is_dir() and root.resolve() == root.absolute(), 'selected product tree')
        for p in root.rglob('*'):
            s = p.lstat()
            need(not stat.S_ISLNK(s.st_mode), 'selected product symlink')
            if stat.S_ISDIR(s.st_mode):
                continue
            need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'selected product ownership')
            members.add(str(p))
    need(members == set(certificate['products']), 'exact selected product membership')
    for name, sha in certificate['products'].items():
        need(physical_hash(Path(name))[0] == sha, 'selected product bytes')
    return dict(status='ACCEPTED_LRU_CERTIFICATE_EXACT_BYTES_RETAINED',
                originalCertificateSha256=CERT_SHA, originalVerifierSha256=VERIFIER_SHA,
                originalQualificationRemainsHistorical=True,
                originalCurrentOriginReplayAvailable=not any(r['originalOrigin'] == 'current-regular' for r in archived),
                currentBindings=current, archivedBindings=archived,
                totalBindings=len(certificate['physicalBindings']),
                selectedLiveProducts=len(members), archiveManifestPins=pins,
                limits=['retention proof only, NOT a new semantic/game acquisition or old live-origin/inode/ctime seal renewal',
                        'original accepted certificate and verifier are unchanged; retired lab paths resolve only through exact pinned successor membership',
                        'selected game/storage/auxiliary products remain live; original finite qualification limits remain unchanged'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', nargs=2, action='append', default=[], metavar=('PATH', 'SHA256'))
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
