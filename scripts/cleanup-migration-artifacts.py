#!/usr/bin/env python3
"""Archive explicit inactive build trees, verify bytes, then prune large originals.

No automatic discovery/deletion policy: the coordinator must name inactive roots.
Reports retain their original meaning; archived inode/ctime seals are historical.
Blobs are SHA256-addressed gzip, shared across runs. Nothing follows symlinks.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import zlib

CHUNK = 1024 * 1024


def digest(stream):
    h = hashlib.sha256()
    size = 0
    while block := stream.read(CHUNK):
        h.update(block)
        size += len(block)
    return h.hexdigest(), size


def file_digest(path):
    with path.open('rb') as stream:
        return digest(stream)


def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fingerprint(path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode):
        raise ValueError('not a regular file: ' + str(path))
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_nlink]


def validate_root(repo, relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or len(p.parts) < 2 or p.parts[0] != 'build':
        raise ValueError('explicit directory below build/ required')
    root = repo / p
    if root.resolve() != root or not root.is_dir():
        raise ValueError('missing/aliased root: ' + str(root))
    if 'migration-evidence-archive' in p.parts:
        raise ValueError('cannot archive the archive')
    return root


def archive(repo, roots, archive_root, run, min_bytes):
    selected = [validate_root(repo, r) for r in roots]
    dest = archive_root / 'runs' / run
    if dest.exists():
        if any(dest.iterdir()):
            raise ValueError('run already has evidence; inspect it instead of overwriting')
    else:
        dest.mkdir(parents=True, exist_ok=False)
    entries = []
    for root in selected:
        for parent, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(parent) / d).is_symlink())
            for name in sorted(files):
                path = Path(parent) / name
                s = path.lstat()
                if stat.S_ISREG(s.st_mode) and s.st_size >= min_bytes:
                    before = fingerprint(path)
                    sha, size = file_digest(path)
                    if fingerprint(path) != before:
                        raise ValueError('source changed while hashing: ' + str(path))
                    entries.append(dict(path=str(path.relative_to(repo)), sha256=sha,
                                        size=size, fingerprint=before, mode=stat.S_IMODE(s.st_mode),
                                        mtime_ns=s.st_mtime_ns))
    if len({e['path'] for e in entries}) != len(entries):
        raise ValueError('overlapping roots')
    manifest = dict(version=1, roots=roots, min_bytes=min_bytes, created_ns=time.time_ns(),
                    entries=entries, status='PLANNED_NOT_PRUNED',
                    limitation='Bytes/mode/mtime recoverable; original inode/ctime seals become historical. No old receipts rewritten.')
    atomic_json(dest / 'manifest.json', manifest)
    # Complete and decompress-verify every unique blob BEFORE removing any input.
    verified = set()
    for entry in entries:
        sha = entry['sha256']
        blob = archive_root / 'blobs' / sha[:2] / (sha + '.gz')
        if sha in verified:
            continue
        blob.parent.mkdir(parents=True, exist_ok=True)
        if not blob.exists():
            temp = blob.with_suffix('.tmp')
            with temp.open('xb') as raw:
                with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=1, mtime=0) as out:
                    with (repo / entry['path']).open('rb') as source:
                        while block := source.read(CHUNK):
                            out.write(block)
                raw.flush()
                os.fsync(raw.fileno())
            with gzip.open(temp, 'rb') as source:
                if digest(source) != (sha, entry['size']):
                    raise ValueError('new archive reconstruction mismatch')
            os.replace(temp, blob)
            fd = os.open(blob.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        else:
            with gzip.open(blob, 'rb') as source:
                if digest(source) != (sha, entry['size']):
                    raise ValueError('existing archive reconstruction mismatch')
        verified.add(sha)
    manifest.update(status='ALL_BLOBS_RECONSTRUCTED_BEFORE_PRUNE', unique_blobs=len(verified))
    atomic_json(dest / 'manifest.json', manifest)
    # Hardlinked generated outputs occur in historical labs. Verify the complete
    # selected inode group before unlinking ANY member (unlink changes ctime and
    # nlink on siblings). Never open an original for writing, including external
    # links: only the explicitly selected directory entries are removed.
    groups = {}
    for entry in entries:
        groups.setdefault(tuple(entry['fingerprint'][:2]), []).append(entry)
    removed = 0
    with (dest / 'pruned.jsonl').open('x') as journal:
        for group in groups.values():
            for entry in group:
                path = repo / entry['path']
                if fingerprint(path) != entry['fingerprint'] or file_digest(path) != (entry['sha256'], entry['size']):
                    raise ValueError('source changed before prune: ' + str(path))
            for entry in group:
                (repo / entry['path']).unlink()
                journal.write(json.dumps(dict(path=entry['path'], sha256=entry['sha256'], size=entry['size'])) + '\n')
                journal.flush()
                os.fsync(journal.fileno())
                removed += entry['size']
    manifest.update(status='ARCHIVED_VERIFIED_PRUNED', removed_bytes=removed)
    atomic_json(dest / 'manifest.json', manifest)
    print(json.dumps(dict(run=run, files=len(entries), unique_blobs=len(verified), removed_bytes=removed)), flush=True)


def verify(archive_root, manifest_path):
    manifest = json.loads(manifest_path.read_bytes())
    seen = set()
    for entry in manifest['entries']:
        sha = entry['sha256']
        if sha in seen:
            continue
        with gzip.open(archive_root / 'blobs' / sha[:2] / (sha + '.gz'), 'rb') as source:
            if digest(source) != (sha, entry['size']):
                raise ValueError('archive reconstruction mismatch: ' + sha)
        seen.add(sha)
    print('ARCHIVE_RECONSTRUCTION_PASS', len(manifest['entries']), len(seen))


def allocated_bytes(root):
    """Like du: count allocated blocks once per inode; never follow links."""
    total = 0
    seen = set()
    for parent, dirs, files in os.walk(root, followlinks=False):
        paths = [Path(parent), *(Path(parent) / name for name in files),
                 *(Path(parent) / name for name in dirs if (Path(parent) / name).is_symlink())]
        for path in paths:
            s = path.lstat()
            inode = (s.st_dev, s.st_ino)
            if inode not in seen:
                seen.add(inode)
                total += s.st_blocks * 512
    return total


class EncodedDigest:
    def __init__(self):
        self.hash = hashlib.sha256()
        self.size = 0

    def write(self, block):
        self.hash.update(block)
        self.size += len(block)
        return len(block)


def _repack_paths(repo, manifest, sha):
    archive_root = repo / 'build/migration-evidence-archive'
    relative = Path(manifest)
    if (relative.is_absolute() or '..' in relative.parts or
            relative.parts[:3] != ('build', 'migration-evidence-archive', 'runs') or
            relative.name != 'manifest.json' or len(sha) != 64 or
            any(c not in '0123456789abcdef' for c in sha)):
        raise ValueError('explicit archive manifest and lowercase content hash required')
    source = repo / relative
    blob = archive_root / 'blobs' / sha[:2] / (sha + '.gz')
    for path in (source, blob):
        if path.resolve() != path or not path.is_file():
            raise ValueError('missing/aliased archive input: ' + str(path))
    if blob.stat().st_nlink != 1:
        raise ValueError('repack cannot change external hardlink identities')
    manifest_data = json.loads(source.read_bytes())
    if manifest_data['status'] != 'ARCHIVED_VERIFIED_PRUNED':
        raise ValueError('only completed archive manifests can be repacked')
    sizes = {e['size'] for e in manifest_data['entries'] if e['sha256'] == sha}
    if len(sizes) != 1:
        raise ValueError('manifest must identify one raw payload size')
    return archive_root, source, blob, sizes.pop()


def _repack_stream(blob, sha, size, level, output):
    raw_hash = hashlib.sha256()
    total = 0
    with gzip.open(blob, 'rb') as source:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output,
                           compresslevel=level, mtime=0) as encoded:
            while block := source.read(CHUNK):
                total += len(block)
                if total > size:
                    raise ValueError('archive payload exceeds manifest size')
                raw_hash.update(block)
                encoded.write(block)
    if (raw_hash.hexdigest(), total) != (sha, size):
        raise ValueError('archive raw payload mismatch')


def plan_repack_blob(repo, manifest, sha):
    """Measure gzip-9 without writes; prove the old gzip-1 encoding recoverable.

    CAS names/manifests describe RAW bytes. Repacking never changes that contract
    and records both encodings instead of rewriting historical receipts.
    """
    _, source, blob, size = _repack_paths(repo, manifest, sha)
    before = fingerprint(blob)
    old_hash, old_size = file_digest(blob)
    original = EncodedDigest()
    _repack_stream(blob, sha, size, 1, original)
    if (original.hash.hexdigest(), original.size) != (old_hash, old_size):
        raise ValueError('original encoding is not exactly reconstructable gzip-1')
    new = EncodedDigest()
    _repack_stream(blob, sha, size, 9, new)
    if fingerprint(blob) != before:
        raise ValueError('archive changed during repack planning')
    if new.size >= old_size:
        return None
    return dict(manifest=manifest, manifestSha256=file_digest(source)[0], sha256=sha,
                rawSize=size, fingerprint=before, oldEncodedSha256=old_hash,
                oldEncodedSize=old_size, newEncodedSha256=new.hash.hexdigest(),
                newEncodedSize=new.size, python=sys.version, zlib=zlib.ZLIB_RUNTIME_VERSION)


class BoundedEncoding:
    """Enforce the admitted encoded size BEFORE each write, including gzip headers."""
    def __init__(self, stream, limit):
        self.stream = stream
        self.limit = limit
        self.size = 0

    def write(self, block):
        if self.size + len(block) > self.limit:
            raise ValueError('temporary encoding exceeds admitted size; original retained')
        written = self.stream.write(block)
        self.size += written
        return written


def repack_blob(repo, row):
    """Verify a temporary encoding AND its decoded bytes before atomic replacement."""
    archive_root, source, blob, size = _repack_paths(repo, row['manifest'], row['sha256'])
    if (size != row['rawSize'] or file_digest(source)[0] != row['manifestSha256'] or
            fingerprint(blob) != row['fingerprint'] or
            file_digest(blob) != (row['oldEncodedSha256'], row['oldEncodedSize']) or
            row['python'] != sys.version or row['zlib'] != zlib.ZLIB_RUNTIME_VERSION or
            not 0 < row['newEncodedSize'] < min(row['oldEncodedSize'], 20 * CHUNK)):
        raise ValueError('repack plan/input/codec drift or invalid temporary bound')
    # Temporary allocation is inside the SAME 16-GiB archive budget, not waived.
    bound = ((row['newEncodedSize'] + 4095) // 4096) * 4096 + 16384
    if allocated_bytes(archive_root) + bound > 16 * 1024**3:
        raise ValueError('repack temporary would exceed fixed archive cap')
    original = EncodedDigest()
    _repack_stream(blob, row['sha256'], size, 1, original)
    if (original.hash.hexdigest(), original.size) != (row['oldEncodedSha256'], row['oldEncodedSize']):
        raise ValueError('original encoding is not exactly reconstructable gzip-1')
    temp = blob.with_suffix('.repack.tmp')
    with temp.open('xb') as output:
        _repack_stream(blob, row['sha256'], size, 9, BoundedEncoding(output, row['newEncodedSize']))
        output.flush()
        os.fsync(output.fileno())
    if file_digest(temp) != (row['newEncodedSha256'], row['newEncodedSize']):
        raise ValueError('temporary encoded bytes mismatch; original retained')
    with gzip.open(temp, 'rb') as decoded:
        if digest(decoded) != (row['sha256'], size):
            raise ValueError('temporary reconstruction mismatch; original retained')
    if fingerprint(blob) != row['fingerprint'] or file_digest(source)[0] != row['manifestSha256']:
        raise ValueError('input changed before repack replacement; original retained')
    os.chmod(temp, stat.S_IMODE(row['fingerprint'][5]))
    os.replace(temp, blob)
    fd = os.open(blob.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return dict(sha256=row['sha256'], rawSize=size,
                oldEncodedSha256=row['oldEncodedSha256'], newEncodedSha256=row['newEncodedSha256'],
                oldEncodedSize=row['oldEncodedSize'], newEncodedSize=row['newEncodedSize'],
                status='RAW_RECONSTRUCTED_BEFORE_ATOMIC_REPACK', fingerprintAfter=fingerprint(blob))


def budget(repo, max_live_gib, max_archive_gib):
    build = repo / 'build'
    archive_size = allocated_bytes(build / 'migration-evidence-archive')
    live_size = allocated_bytes(build) - archive_size
    result = dict(live_build_bytes=live_size, archive_bytes=archive_size,
                  max_live_bytes=int(max_live_gib * 1024**3),
                  max_archive_bytes=int(max_archive_gib * 1024**3))
    result['passed'] = live_size <= result['max_live_bytes'] and archive_size <= result['max_archive_bytes']
    print(json.dumps(result, sort_keys=True))
    return result['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('archive')
    a.add_argument('--run', required=True)
    a.add_argument('--min-bytes', type=int, default=1024 * 1024)
    a.add_argument('roots', nargs='+')
    v = sub.add_parser('verify')
    v.add_argument('manifest', type=Path)
    b = sub.add_parser('budget')
    b.add_argument('--max-live-gib', type=float, default=4)
    b.add_argument('--max-archive-gib', type=float, default=16)
    args = parser.parse_args()
    repo = args.repo.resolve()
    archive_root = repo / 'build/migration-evidence-archive'
    if args.command == 'budget':
        if args.max_live_gib < 0 or args.max_archive_gib < 0:
            parser.error('nonnegative budgets required')
        sys.exit(0 if budget(repo, args.max_live_gib, args.max_archive_gib) else 1)
    if args.command == 'verify':
        verify(archive_root, args.manifest)
        return
    if not args.run or Path(args.run).name != args.run or args.run in ('.', '..') or args.min_bytes < 0:
        parser.error('safe single-component run name and nonnegative minimum required')
    lock = repo / 'build/.migration-cleanup.lock'
    with lock.open('x') as stream:
        stream.write(str(os.getpid()) + '\n')
    try:
        archive(repo, args.roots, archive_root, args.run, args.min_bytes)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
