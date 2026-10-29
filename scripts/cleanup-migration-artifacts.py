#!/usr/bin/env python3
"""Archive explicit inactive build trees, verify bytes, then prune large originals.

No automatic discovery/deletion policy: the coordinator must name inactive roots.
Reports retain their original meaning; archived inode/ctime seals are historical.
Blobs are SHA256-addressed gzip or XZ, shared across runs. Nothing follows symlinks.
"""
import argparse
import gzip
import hashlib
import json
import lzma
import _lzma
import os
from pathlib import Path
import stat
import sys
import time
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source/lab'))
from migration.archive_blobs import resolve_blob, open_blob

CHUNK = 1024 * 1024
# Encoded length is NOT an upper bound on st_blocks. Admit a separate physical
# scratch allowance, then observe it while writing; never infer allocation from
# a gzip byte count or call an estimated saving a guaranteed reclamation.
REPACK_TEMPORARY_RESERVATION_BYTES = 64 * CHUNK


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
        try:
            blob = resolve_blob(archive_root, sha)
        except FileNotFoundError:
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
            with open_blob(archive_root, sha) as source:
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
        with open_blob(archive_root, sha) as source:
            if digest(source) != (sha, entry['size']):
                raise ValueError('archive reconstruction mismatch: ' + sha)
        seen.add(sha)
    print('ARCHIVE_RECONSTRUCTION_PASS', len(manifest['entries']), len(seen))


def allocated_bytes(root):
    """Count blocks once per inode, without hiding unreadable subtrees.

    Direct DirEntry stats avoid repeated Path/lstat work in per-leaf guards.
    This is still a non-atomic observation, not a cached allocation bound; mount
    contents stay included and symlinks are charged without following targets.
    """
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError('allocation root contains an alias or traversal')
    root = os.fspath(root)
    try:
        initial = os.lstat(root)
    except FileNotFoundError:
        return 0
    if not stat.S_ISDIR(initial.st_mode):
        raise ValueError('allocation root must be a physical directory')
    total, seen = 0, set()
    pending = [(root, initial)]
    while pending:
        path, info = pending.pop()
        inode = (info.st_dev, info.st_ino)
        if inode in seen:
            continue
        seen.add(inode)
        total += info.st_blocks * 512
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(path) as entries:
                for entry in entries:
                    pending.append((entry.path, entry.stat(follow_symlinks=False)))
    return total


class EncodedDigest:
    def __init__(self):
        self.hash = hashlib.sha256()
        self.size = 0

    def write(self, block):
        self.hash.update(block)
        self.size += len(block)
        return len(block)


def _repack_paths(repo, manifest, sha, *, require_blob=True):
    archive_root = repo / 'build/migration-evidence-archive'
    relative = Path(manifest)
    if (relative.is_absolute() or '..' in relative.parts or
            relative.parts[:3] != ('build', 'migration-evidence-archive', 'runs') or
            relative.name != 'manifest.json' or len(sha) != 64 or
            any(c not in '0123456789abcdef' for c in sha)):
        raise ValueError('explicit archive manifest and lowercase content hash required')
    source = repo / relative
    blob = archive_root / 'blobs' / sha[:2] / (sha + '.gz')
    for path in ((source, blob) if require_blob else (source,)):
        if path.resolve() != path or not path.is_file():
            raise ValueError('missing/aliased archive input: ' + str(path))
    if blob.parent.resolve() != blob.parent or not blob.parent.is_dir():
        raise ValueError('missing/aliased archive fanout')
    if require_blob and blob.stat().st_nlink != 1:
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
        self.peak_allocated = 0

    def write(self, block):
        if self.size + len(block) > self.limit:
            raise ValueError('temporary encoding exceeds admitted size; original retained')
        written = self.stream.write(block)
        self.size += written
        self.observe_allocation()
        return written

    def observe_allocation(self):
        self.stream.flush()
        allocated = os.fstat(self.stream.fileno()).st_blocks * 512
        self.peak_allocated = max(self.peak_allocated, allocated)
        if allocated > REPACK_TEMPORARY_RESERVATION_BYTES:
            raise ValueError('temporary physical allocation exceeds reservation; original retained')


def repack_blob(repo, row):
    """Verify a temporary encoding AND its decoded bytes before atomic replacement."""
    archive_root, source, blob, size = _repack_paths(repo, row['manifest'], row['sha256'])
    if (size != row['rawSize'] or file_digest(source)[0] != row['manifestSha256'] or
            fingerprint(blob) != row['fingerprint'] or
            file_digest(blob) != (row['oldEncodedSha256'], row['oldEncodedSize']) or
            row['python'] != sys.version or row['zlib'] != zlib.ZLIB_RUNTIME_VERSION or
            not 0 < row['newEncodedSize'] < min(row['oldEncodedSize'], 20 * CHUNK)):
        raise ValueError('repack plan/input/codec drift or invalid temporary bound')
    # Logical gzip length underestimated physical allocation on the actual host.
    # The allowance includes scratch storage independently of encoded size; the
    # extra directory margin is not available to the encoded writer.
    bound = REPACK_TEMPORARY_RESERVATION_BYTES + 16384
    if allocated_bytes(archive_root) + bound > 16 * 1024**3:
        raise ValueError('repack temporary would exceed fixed archive cap')
    original = EncodedDigest()
    _repack_stream(blob, row['sha256'], size, 1, original)
    if (original.hash.hexdigest(), original.size) != (row['oldEncodedSha256'], row['oldEncodedSize']):
        raise ValueError('original encoding is not exactly reconstructable gzip-1')
    temp = blob.with_suffix('.repack.tmp')
    with temp.open('xb') as output:
        encoded = BoundedEncoding(output, row['newEncodedSize'])
        _repack_stream(blob, row['sha256'], size, 9, encoded)
        output.flush()
        os.fsync(output.fileno())
        encoded.observe_allocation()
    if allocated_bytes(archive_root) > 16 * 1024**3:
        raise ValueError('observed archive allocation exceeds fixed cap; original retained')
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
                status='RAW_RECONSTRUCTED_BEFORE_ATOMIC_REPACK', fingerprintAfter=fingerprint(blob),
                temporaryPeakAllocatedBytes=encoded.peak_allocated,
                temporaryPhysicalReservationBytes=REPACK_TEMPORARY_RESERVATION_BYTES)


XZ_CODEC = 'XZ-LZMA2-CRC64-preset6-v1'


def _xz_runtime():
    return dict(python=sys.version, zlib=zlib.ZLIB_RUNTIME_VERSION,
                lzmaExtensionSha256=file_digest(Path(_lzma.__file__).resolve())[0],
                toolSha256=file_digest(Path(__file__).resolve())[0],
                readerSha256=file_digest(Path(__file__).resolve().parents[1] /
                    'source/lab/migration/archive_blobs.py')[0])


def _gzip_level(blob):
    with blob.open('rb') as stream:
        header = stream.read(10)
    if len(header) != 10 or header[:3] != b'\x1f\x8b\x08' or header[8] not in (2, 4):
        raise ValueError('unsupported original gzip encoding')
    return 9 if header[8] == 2 else 1


def _xz_stream(blob, sha, size, output):
    encoder = lzma.LZMACompressor(format=lzma.FORMAT_XZ,
                                 check=lzma.CHECK_CRC64, preset=6)
    h, total = hashlib.sha256(), 0
    with gzip.open(blob, 'rb') as source:
        while block := source.read(CHUNK):
            total += len(block)
            if total > size:
                raise ValueError('archive payload exceeds manifest size')
            h.update(block)
            output.write(encoder.compress(block))
    output.write(encoder.flush())
    if (h.hexdigest(), total) != (sha, size):
        raise ValueError('archive raw payload mismatch')


def plan_xz_blob(repo, manifest, sha):
    """Measure a new codec without writes; retain the exact old encoding contract."""
    _, source, blob, size = _repack_paths(repo, manifest, sha)
    if type(size) is not int or not 0 <= size <= 192 * CHUNK:
        raise ValueError('XZ raw payload outside bounded domain')
    if resolve_blob(repo / 'build/migration-evidence-archive', sha) != blob:
        raise ValueError('XZ planning requires one original gzip blob')
    before, old = fingerprint(blob), file_digest(blob)
    level = _gzip_level(blob)
    recovered = EncodedDigest()
    _repack_stream(blob, sha, size, level, recovered)
    if (recovered.hash.hexdigest(), recovered.size) != old:
        raise ValueError('original gzip encoding not exactly reconstructable')
    encoded = EncodedDigest()
    _xz_stream(blob, sha, size, encoded)
    if fingerprint(blob) != before:
        raise ValueError('archive changed during XZ planning')
    if encoded.size >= old[1]:
        return None
    return dict(schema='xz-transcode-plan-v1', codec=XZ_CODEC, manifest=manifest,
                manifestSha256=file_digest(source)[0], sha256=sha, rawSize=size,
                fingerprint=before, oldGzipLevel=level, oldEncodedSha256=old[0],
                oldEncodedSize=old[1], newEncodedSha256=encoded.hash.hexdigest(),
                newEncodedSize=encoded.size, **_xz_runtime())


def _verify_xz_encoding(path, row):
    """Prove raw bytes AND original gzip bytes before either encoding is pruned."""
    if file_digest(path) != (row['newEncodedSha256'], row['newEncodedSize']):
        raise ValueError('new XZ encoded bytes mismatch; original retained')
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=64 * CHUNK)
    h, total, recovered = hashlib.sha256(), 0, EncodedDigest()
    with path.open('rb') as source:
        with gzip.GzipFile(filename='', mode='wb', fileobj=recovered,
                           compresslevel=row['oldGzipLevel'], mtime=0) as old:
            while not decoder.eof:
                block = source.read(CHUNK) if decoder.needs_input else b''
                if decoder.needs_input and not block:
                    raise ValueError('truncated new XZ stream; original retained')
                raw = decoder.decompress(block, max_length=CHUNK)
                total += len(raw)
                if total > row['rawSize']:
                    raise ValueError('XZ raw size exceeds admission; original retained')
                h.update(raw)
                old.write(raw)
            if decoder.check != lzma.CHECK_CRC64 or decoder.unused_data or source.read(1):
                raise ValueError('unexpected XZ framing; original retained')
    if (h.hexdigest(), total) != (row['sha256'], row['rawSize']):
        raise ValueError('new XZ raw reconstruction mismatch; original retained')
    if (recovered.hash.hexdigest(), recovered.size) != (row['oldEncodedSha256'], row['oldEncodedSize']):
        raise ValueError('old gzip reconstruction mismatch; original retained')


def _xz_capacity(repo, archive_root, *, reserve=False):
    allocated = allocated_bytes(archive_root)
    extra = REPACK_TEMPORARY_RESERVATION_BYTES + 16384 if reserve else 0
    if allocated + extra > 16 * 1024**3:
        raise ValueError('XZ temporary/archive allocation exceeds fixed cap')
    if allocated_bytes(repo / 'build') - allocated > 4 * 1024**3:
        raise ValueError('XZ live allocation exceeds fixed cap')


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def recode_xz_blob(repo, row, *, resume=False):
    """Convert only admitted names; interruption is fail-closed, never fallback.

    The brief two-codec state is deliberately unreadable by the resolver. An
    explicit resume verifies both retained byte contracts before finishing it;
    it cannot renew the historical gzip inode/ctime or any native origin.
    """
    runtime = _xz_runtime()
    fields = {'schema', 'codec', 'manifest', 'manifestSha256', 'sha256', 'rawSize',
              'fingerprint', 'oldGzipLevel', 'oldEncodedSha256', 'oldEncodedSize',
              'newEncodedSha256', 'newEncodedSize'} | set(runtime)
    if (type(resume) is not bool or set(row) != fields or row['schema'] != 'xz-transcode-plan-v1' or
            row['codec'] != XZ_CODEC or any(row[k] != v for k, v in runtime.items()) or
            any(type(row[k]) is not int for k in ('rawSize', 'oldEncodedSize', 'newEncodedSize', 'oldGzipLevel')) or
            type(row['fingerprint']) is not list or len(row['fingerprint']) != 7 or
            any(type(v) is not int for v in row['fingerprint']) or row['fingerprint'][6] != 1 or
            any(type(row[k]) is not str or len(row[k]) != 64 or
                any(c not in '0123456789abcdef' for c in row[k])
                for k in ('sha256', 'manifestSha256', 'oldEncodedSha256', 'newEncodedSha256')) or
            not 0 < row['rawSize'] <= 192 * CHUNK or row['oldGzipLevel'] not in (1, 9) or
            not 0 < row['newEncodedSize'] < min(row['oldEncodedSize'], 20 * CHUNK)):
        raise ValueError('XZ plan/schema/codec drift or invalid bound')
    archive_root, manifest, blob, size = _repack_paths(repo, row['manifest'], row['sha256'], require_blob=False)
    destination, temp = blob.with_suffix('.xz'), blob.with_suffix('.xz-transcode.tmp')

    def check_manifest():
        if type(size) is not int or size != row['rawSize'] or file_digest(manifest)[0] != row['manifestSha256']:
            raise ValueError('XZ manifest drift')

    def check_old():
        if (fingerprint(blob) != row['fingerprint'] or
                file_digest(blob) != (row['oldEncodedSha256'], row['oldEncodedSize'])):
            raise ValueError('original gzip identity drift')

    check_manifest()
    old_exists = os.path.lexists(blob)
    generated = [p for p in (temp, destination) if os.path.lexists(p)]
    if generated and not resume:
        raise ValueError('interrupted XZ conversion requires explicit resume')
    if resume and not generated:
        raise ValueError('no interrupted XZ conversion to resume')
    if old_exists:
        check_old()
    elif not (resume and generated == [destination]):
        raise ValueError('missing original gzip input')
    _xz_capacity(repo, archive_root, reserve=not generated)
    peak = 0
    if not generated:
        if resolve_blob(archive_root, row['sha256']) != blob:
            raise ValueError('unexpected original codec')
        recovered = EncodedDigest()
        _repack_stream(blob, row['sha256'], size, row['oldGzipLevel'], recovered)
        if (recovered.hash.hexdigest(), recovered.size) != (row['oldEncodedSha256'], row['oldEncodedSize']):
            raise ValueError('original gzip not exactly reconstructable')
        with temp.open('xb') as output:
            encoded = BoundedEncoding(output, row['newEncodedSize'])
            _xz_stream(blob, row['sha256'], size, encoded)
            os.chmod(temp, stat.S_IMODE(row['fingerprint'][5]))
            output.flush()
            os.fsync(output.fileno())
            encoded.observe_allocation()
            peak = encoded.peak_allocated
        generated = [temp]
    stamps = [fingerprint(p) for p in generated]
    if (any(p.resolve() != p for p in generated) or
            any(s[6] != len(generated) for s in stamps) or
            len({tuple(s[:2]) for s in stamps}) != 1):
        raise ValueError('XZ generated alias/hardlink group outside admitted names')
    # A resume did not pass through BoundedEncoding in this invocation. Global
    # headroom cannot substitute for the independent per-inode scratch bound.
    observed = max(p.lstat().st_blocks * 512 for p in generated)
    peak = max(peak, observed)
    if observed > REPACK_TEMPORARY_RESERVATION_BYTES:
        raise ValueError('resumed XZ physical allocation exceeds reservation; original retained')
    _verify_xz_encoding(generated[0], row)
    _xz_capacity(repo, archive_root)
    check_manifest()
    if old_exists:
        check_old()
    if temp in generated:
        if destination not in generated:
            os.link(temp, destination)  # Exclusive install; never replace a late destination.
        os.unlink(temp)
    _fsync_directory(blob.parent)
    if (fingerprint(destination)[6] != 1 or
            file_digest(destination) != (row['newEncodedSha256'], row['newEncodedSize'])):
        raise ValueError('installed XZ changed; original retained')
    _xz_capacity(repo, archive_root)
    check_manifest()
    if old_exists:
        check_old()
        os.unlink(blob)
    _fsync_directory(blob.parent)
    if resolve_blob(archive_root, row['sha256']) != destination:
        raise ValueError('XZ installation did not resolve uniquely')
    return dict(sha256=row['sha256'], rawSize=size, oldEncodedSha256=row['oldEncodedSha256'],
                newEncodedSha256=row['newEncodedSha256'], oldEncodedSize=row['oldEncodedSize'],
                newEncodedSize=row['newEncodedSize'], fingerprintAfter=fingerprint(destination),
                temporaryPeakAllocatedBytes=peak,
                temporaryPhysicalReservationBytes=REPACK_TEMPORARY_RESERVATION_BYTES,
                resumed=resume, originalEncodingLiveReplayAvailable=False,
                allocationObservationScope='current invocation only; pre-interruption peak unavailable',
                status='RAW_AND_OLD_GZIP_RECONSTRUCTED_BEFORE_XZ_CONVERSION')


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
