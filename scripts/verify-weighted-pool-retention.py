#!/usr/bin/env python3
"""Read-only, externally pinned WeightedPool byte conservation audit.

No restore, runtime source/executable substitution, semantic replay, or historical live-origin
renewal. Optional source epochs conserve exact historical first-party bytes only. The closure is a retention snapshot, not retroactive producer evidence.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source/lab'))
from migration.archive_blobs import resolve_blob, open_blob

CHUNK = 1024 * 1024
MAX_JSON = 64 * CHUNK
MIN_BYTES = 2 * CHUNK
ARCHIVE_CAP = 16 * 1024**3
LIVE_CAP = 4 * 1024**3
SOURCE_COPY_CAP = 64 * CHUNK
SOURCE_TOTAL_CAP = 128 * CHUNK
SOURCE_EXTENSIONS = {'.cpp', '.hpp', '.cc', '.hh', '.c', '.h', '.mm', '.rs',
                     '.toml', '.lock', '.cmake', '.in', '.inc', '.S'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(value):
    need(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'invalid SHA256')
    return value


def integer(value):
    need(type(value) is int and 0 <= value < 2**64, 'invalid nonnegative integer')
    return value


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def relative(value):
    need(isinstance(value, str) and 0 < len(value) <= 4096, 'invalid relative path')
    p = Path(value)
    need(not p.is_absolute() and str(p) == value and
         all(x not in ('', '.', '..') for x in value.split('/')), 'unsafe relative path')
    return p


def physical(path, kind='file'):
    need(path.resolve(strict=True) == path, 'aliased physical path: ' + str(path))
    mode = path.lstat().st_mode
    need(stat.S_ISREG(mode) if kind == 'file' else stat.S_ISDIR(mode),
         'wrong physical path kind: ' + str(path))
    return path


def fingerprint(path):
    s = path.lstat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_nlink]


def digest(stream, max_size=None):
    h = hashlib.sha256()
    size = 0
    while block := stream.read(CHUNK):
        size += len(block)
        need(max_size is None or size <= max_size, 'reconstructed bytes exceed bound')
        h.update(block)
    return h.hexdigest(), size


def file_digest(path):
    before = fingerprint(path)
    physical(path)
    with path.open('rb') as stream:
        result = digest(stream)
    need(fingerprint(path) == before, 'file changed during hashing: ' + str(path))
    return result


def pinned(path, pin):
    sha(pin)
    physical(path)
    need(path.stat().st_size <= MAX_JSON, 'JSON size bound')
    before = fingerprint(path)
    raw = path.read_bytes()
    need(fingerprint(path) == before and hashlib.sha256(raw).hexdigest() == pin,
         'external manifest pin mismatch: ' + str(path))
    result = json.loads(raw, object_pairs_hook=unique)
    need(type(result) is dict, 'JSON object required')
    return result


def row_contract(row):
    relative(row['path'])
    sha(row['sha256'])
    integer(row['size'])
    fp = row['fingerprint']
    need(type(fp) is list and len(fp) == 7, 'fingerprint schema')
    for value in fp:
        integer(value)
    need(fp[2] == row['size'] and stat.S_ISREG(fp[5]) and fp[6] >= 1,
         'regular file fingerprint contract')


def inventory(repo, roots):
    files, aliases = set(), set()
    for root in roots:
        physical(repo / root, 'directory')
        for parent, dirs, names in os.walk(repo / root, followlinks=False):
            for name in dirs[:] + names:
                p = Path(parent) / name
                mode = p.lstat().st_mode
                key = str(p.relative_to(repo))
                if stat.S_ISLNK(mode):
                    aliases.add(key)
                    if name in dirs:
                        dirs.remove(name)
                elif stat.S_ISREG(mode):
                    files.add(key)
                else:
                    need(stat.S_ISDIR(mode), 'special observed member: ' + key)
    return files, aliases


class Counter(io.RawIOBase):
    def __init__(self):
        self.size = 0

    def write(self, data):
        self.size += len(data)
        return len(data)


def codec_size(path):
    counter = Counter()
    with gzip.GzipFile(filename='', mode='wb', fileobj=counter, compresslevel=1, mtime=0) as out:
        with path.open('rb') as source:
            while block := source.read(CHUNK):
                out.write(block)
    return counter.size


def source_bindings(repo, specification, closure_sha, certificate_sha, protected):
    """Resolve retained bytes, never renew the original source's live origin.

    Validate every declared copy, including currently unchanged originals. The
    fixed owned store and first-party allowlist cannot resolve tools or products.
    Historical verifier snapshots are metadata, not protected-source mappings.
    """
    if specification is None:
        return {}, None
    need(isinstance(specification, (tuple, list)) and len(specification) == 2,
         'source versions require path and SHA256')
    path, pin = specification
    manifest = pinned(Path(path).absolute(), pin)
    need(type(manifest['version']) is int and manifest['version'] == 1 and
         manifest['closureSha256'] == closure_sha and
         manifest['certificateSha256'] == certificate_sha, 'source versions identity')
    entries = manifest['entries']
    need(type(entries) is list and len(entries) <= 200000, 'source versions entry bound')
    bindings, copies, total = {}, set(), 0
    for row in entries:
        name = row['path']
        need(isinstance(name, str), 'source original path')
        original = Path(name)
        need(original.is_absolute() and str(original) == name and
             '..' not in original.parts and original.is_relative_to(repo), 'source original scope')
        rel = original.relative_to(repo)
        need(len(rel.parts) >= 2 and rel.parts[0] in {'source', 'cmake'} and
             not any(part.lower() in {'scripts', 'lib', 'sdk', 'tools', 'build', 'products'}
                     for part in rel.parts[:-1]) and
             (rel.suffix in SOURCE_EXTENSIONS or rel.name == 'CMakeLists.txt' or
              # This noncompiled inventory changes as migration members are added.
              # Its ORIGINAL protected hash still binds the retained copy; this
              # is not permission for arbitrary JSON, tools or generated products.
              rel == Path('source/lab/migration/modules.json')),
             'first-party source required')
        physical(original)
        expected = sha(row['sha256'])
        need(original not in bindings, 'duplicate source original')
        need(original in protected and protected[original] == expected,
             'unbound/conflicting source pin')
        size = integer(row['size'])
        total += size
        need(size <= SOURCE_COPY_CAP and total <= SOURCE_TOTAL_CAP, 'source copy size bound')
        retained = repo / 'build/weighted-pool-source-epoch-r1/bytes' / expected / rel
        need(row['copy'] == str(retained) and retained not in copies, 'source copy layout/alias')
        physical(retained)
        before = fingerprint(retained)
        need(before[6] == 1, 'source copy hardlink alias')
        need(before[2] == size, 'source copy size mismatch')
        with retained.open('rb') as stream:
            need(digest(stream, size) == (expected, size), 'source copy bytes mismatch')
        need(fingerprint(retained) == before, 'source copy changed during hashing')
        copies.add(retained)
        bindings[original] = dict(path=name, copy=str(retained), sha256=expected, size=size)
    return bindings, pin


def retired_product_bindings(repo, specification, protected):
    """Conserve ONLY the two historical game outputs, never substitute live tools.

    This is an opt-in successor archive contract, separate from source epochs.
    A missing original's inode/ctime/execution origin is explicitly unavailable.
    """
    if specification is None:
        return {}, None
    need(isinstance(specification, (tuple, list)) and len(specification) == 2,
         'retired products require manifest and SHA256')
    path, pin = specification
    path = Path(path).absolute()
    runs = repo / 'build/migration-evidence-archive/runs'
    need(path.name == 'manifest.json' and path.parent.parent == runs and
         re.fullmatch('[A-Za-z0-9_-]{1,128}', path.parent.name), 'retired product manifest scope')
    m = pinned(path, pin)
    base = Path('build/behavior/weighted-pool-combined-r1')
    names = [base / backend / 'bin/starbound' for backend in ('reference', 'candidate')]
    roots = [str(name.parent) for name in names]
    need(m['version'] == 1 and type(m['version']) is int and
         m['status'] == 'ARCHIVED_VERIFIED_PRUNED' and m['roots'] == roots and
         m['min_bytes'] == MIN_BYTES, 'retired product archive contract')
    entries = m['entries']
    need(type(entries) is list and len(entries) == 2 and
         {row['path'] for row in entries} == {str(p) for p in names},
         'exact two historical game products required')
    bindings = {}
    for row in entries:
        row_contract(row)
        original = repo / relative(row['path'])
        need(original in protected and protected[original] == row['sha256'],
             'retired product original protected pin')
        need(MIN_BYTES <= row['size'] <= 128 * CHUNK and row['fingerprint'][6] == 1,
             'retired product size/link bound')
        physical(original.parent, 'directory')
        need(not os.path.lexists(original), 'retired product must be absent, never replace a live input')
        archive = repo / 'build/migration-evidence-archive'
        blob = resolve_blob(archive, row['sha256'])
        before = fingerprint(blob)
        with open_blob(archive, row['sha256']) as stream:
            need(digest(stream, row['size']) == (row['sha256'], row['size']),
                 'retired product reconstructed bytes mismatch')
        need(fingerprint(blob) == before, 'retired product blob changed')
        bindings[original] = dict(path=str(original), sha256=row['sha256'], size=row['size'])
    need(m['removed_bytes'] == sum(row['size'] for row in entries), 'retired product removed total')
    return bindings, pin


def verify(closure_path, closure_sha, repo=None, archive_manifest=None, archive_manifest_sha=None,
           source_versions=None, retired_products=None):
    repo = Path(repo if repo is not None else Path(__file__).resolve().parents[1]).absolute()
    physical(repo, 'directory')
    closure_path = Path(closure_path).absolute()
    c = pinned(closure_path, closure_sha)
    need(c['version'] == 1 and type(c['version']) is int and c['repoRoot'] == str(repo), 'closure identity')
    need(c['minBytes'] == MIN_BYTES and type(c['minBytes']) is int, 'fixed selection threshold')
    run = c['archiveRun']
    need(isinstance(run, str) and re.fullmatch('[A-Za-z0-9_-]{1,128}', run), 'archive run')
    roots, observed = c['roots'], c['observedRoots']
    need(type(roots) is list and len(roots) == 11 and type(observed) is list and
         len(observed) == len(roots) + 1, 'root bounds')
    for collection in (roots, observed):
        need(len(set(collection)) == len(collection), 'duplicate roots')
        for name in collection:
            p = relative(name)
            need(len(p.parts) == 2 and p.parts[0] == 'build' and
                 p.parts[1].startswith('weighted-pool-'), 'explicit WeightedPool root required')
        for a in collection:
            for b in collection:
                need(a == b or not (repo / a).is_relative_to(repo / b), 'overlapping roots')
    need(set(roots) < set(observed), 'observed roots must include excluded root')
    rows = {}
    need(type(c['entries']) is list and len(c['entries']) <= 200000, 'entry bound')
    for row in c['entries']:
        row_contract(row)
        key = row['path']
        need(key not in rows and any(relative(key).is_relative_to(relative(r)) for r in observed),
             'duplicate/out-of-scope entry')
        rows[key] = row
    selected = c['selected']
    need(type(selected) is list and len(selected) <= len(rows) and
         all(isinstance(key, str) for key in selected) and len(selected) == len(set(selected)), 'selected schema')
    expected = {key for key, row in rows.items() if row['size'] >= MIN_BYTES and
                any(relative(key).is_relative_to(relative(r)) for r in roots)}
    need(set(selected) == expected, 'incomplete threshold selection')
    need(type(c['aliases']) is list and len(c['aliases']) <= 200000, 'alias bound')
    aliases = {}
    for row in c['aliases']:
        key = row['path']
        relative(key)
        need(key not in aliases and key not in rows and
             any(relative(key).is_relative_to(relative(r)) for r in observed), 'alias scope/uniqueness')
        need(isinstance(row['target'], str) and type(row['fingerprint']) is list and
             len(row['fingerprint']) == 7, 'alias schema')
        for value in row['fingerprint']:
            integer(value)
        need(stat.S_ISLNK(row['fingerprint'][5]), 'alias fingerprint kind')
        aliases[key] = row
    need(type(c['limits']) is list and all(isinstance(x, str) for x in c['limits']), 'limits schema')

    protection = c['protection']
    cert_path = repo / relative(protection['certificatePath'])
    aux_path = repo / relative(protection['auxiliaryAdmissionPath'])
    cert = pinned(cert_path, protection['certificateSha256'])
    aux = pinned(aux_path, protection['auxiliaryAdmissionSha256'])
    protected = {cert_path: protection['certificateSha256'], aux_path: protection['auxiliaryAdmissionSha256']}
    need(type(cert['bindings']) is dict and type(aux['witness']['files']) is dict and
         type(aux['witness']['aliases']) is dict and
         all(len(mapping) <= 200000 for mapping in
             (cert['bindings'], aux['witness']['files'], aux['witness']['aliases'])), 'protected maps')
    for name, pin in cert['bindings'].items():
        p = repo / relative(name)
        sha(pin)
        need(p not in protected or protected[p] == pin, 'conflicting protected pins')
        protected[p] = pin
    for name, pin in aux['witness']['files'].items():
        p = Path(name)
        need(p.is_absolute() and str(p) == name and '..' not in p.parts, 'absolute protected path')
        sha(pin)
        need(p not in protected or protected[p] == pin, 'conflicting protected pins')
        protected[p] = pin
    versions, source_versions_sha = source_bindings(
        repo, source_versions, closure_sha, protection['certificateSha256'], protected)
    retired, retired_sha = retired_product_bindings(repo, retired_products, protected)
    versioned = []
    protected_inodes, protected_paths, cache = set(), set(), {}
    for p, pin in protected.items():
        if p in retired:
            # Only exact archived bytes survive. Do not invent a current inode,
            # resolve a restored executable, or renew its former execution proof.
            protected_paths.add(p)
            continue
        canonical = p.resolve(strict=True)
        protected_paths.update((p, canonical))
        stamp = tuple(fingerprint(canonical))
        if stamp not in cache:
            cache[stamp] = file_digest(canonical)[0]
        if cache[stamp] != pin:
            need(p in versions, 'protected bytes changed: ' + str(p))
            # The validated retained bytes match this SAME original pin. Keep
            # protecting the current original path/inode, not the copy's inode.
            need(versions[p]['sha256'] == pin, 'source original pin mismatch')
            versioned.append(versions[p])
        protected_inodes.add(stamp[:2])
    for name, target in aux['witness']['aliases'].items():
        p, target_path = Path(name), Path(target)
        need(p.is_absolute() and target_path.is_absolute() and '..' not in p.parts and
             '..' not in target_path.parts, 'protected alias schema')
        need(p not in retired and target_path not in retired,
             'retired product cannot stand in for a protected live alias')
        need(p.resolve(strict=True) == target_path, 'protected alias resolution changed')
        protected_paths.update((p, target_path))
        protected_inodes.add(tuple(fingerprint(target_path)[:2]))
    selected_inodes = {tuple(rows[key]['fingerprint'][:2]) for key in selected}
    need(not (selected_inodes & protected_inodes) and
         not any(repo / key in protected_paths for key in selected), 'protected selection overlap')
    need(not any(tuple(row['fingerprint'][:2]) in selected_inodes
                 for key, row in rows.items() if key not in expected), 'selected/complement inode overlap')

    after = archive_manifest is not None
    need(after == (archive_manifest_sha is not None), 'archive flags must be paired')
    manifest = None
    if after:
        manifest_path = Path(archive_manifest).absolute()
        need(manifest_path == repo / 'build/migration-evidence-archive/runs' / run / 'manifest.json',
             'archive run manifest path')
        manifest = pinned(manifest_path, archive_manifest_sha)
        need(manifest['status'] == 'ARCHIVED_VERIFIED_PRUNED' and manifest['roots'] == roots and
             manifest['min_bytes'] == MIN_BYTES, 'archive status/roots/threshold')
        archived = {}
        for row in manifest['entries']:
            row_contract(row)
            need(row['path'] not in archived, 'duplicate archive membership')
            archived[row['path']] = row
        need(set(archived) == expected, 'exact archive selection membership')
        for key, row in archived.items():
            need(all(row[field] == rows[key][field] for field in ('sha256', 'size', 'fingerprint')),
                 'archive entry contract mismatch')
        need(manifest['removed_bytes'] == sum(rows[key]['size'] for key in selected), 'removed byte total')

    current_files, current_aliases = inventory(repo, observed)
    need(current_files == set(rows) - (expected if after else set()), 'observed file inventory changed')
    need(current_aliases == set(aliases), 'observed alias inventory changed')
    for key, row in aliases.items():
        p = repo / key
        need(p.parent.resolve(strict=True) == p.parent and p.is_symlink() and
             os.readlink(p) == row['target'] and fingerprint(p) == row['fingerprint'], 'alias changed: ' + key)
    for key, row in rows.items():
        p = repo / key
        if after and key in expected:
            need(not os.path.lexists(p), 'selected path remains live: ' + key)
            continue
        need(fingerprint(p) == row['fingerprint'] and file_digest(p) == (row['sha256'], row['size']) and
             fingerprint(p) == row['fingerprint'], 'live snapshot changed: ' + key)

    projection = c['projection']
    need(projection['archiveCap'] == ARCHIVE_CAP and projection['liveCap'] == LIVE_CAP, 'fixed budget caps')
    for field in ('archiveAllocatedBefore', 'liveAllocatedBefore', 'archiveGrowthBound', 'archiveCap', 'liveCap'):
        integer(projection[field])
    need(projection['liveAllocatedBefore'] <= LIVE_CAP and
         projection['archiveAllocatedBefore'] + projection['archiveGrowthBound'] <= ARCHIVE_CAP,
         'projected allocation exceeds fixed caps')
    new = projection['exactCodecNewBlobBytes']
    old = projection['verifiedExistingBlobs']
    need(type(new) is dict and type(old) is list and len(new) <= len(selected) and
         len(old) <= len(selected) and all(isinstance(pin, str) for pin in old) and
         len(old) == len(set(old)), 'projection blob schema')
    sizes = {}
    for key in selected:
        row = rows[key]
        need(row['sha256'] not in sizes or sizes[row['sha256']] == row['size'], 'inconsistent SHA size')
        sizes[row['sha256']] = row['size']
    need(not (set(new) & set(old)) and set(new) | set(old) == set(sizes), 'exact projected blob partition')
    for pin in old:
        sha(pin)
    for pin, size in new.items():
        sha(pin)
        integer(size)
    need(sum(((size + 4095) // 4096) * 4096 for size in new.values()) <= projection['archiveGrowthBound'],
         'growth bound below blob allocation')
    verified_blobs = set()
    for pin, size in sizes.items():
        archive = repo / 'build/migration-evidence-archive'
        if after or pin in old:
            blob = resolve_blob(archive, pin)
            before = fingerprint(blob)
            with open_blob(archive, pin) as stream:
                need(digest(stream, size) == (pin, size), 'archive reconstructed bytes mismatch')
            need(fingerprint(blob) == before, 'blob changed during reconstruction')
            if pin in new:
                need(blob.stat().st_size == new[pin], 'exact codec blob size mismatch')
            verified_blobs.add(pin)
        else:
            try:
                resolve_blob(archive, pin)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('projected new blob already exists')
            key = next(key for key in selected if rows[key]['sha256'] == pin)
            need(codec_size(repo / key) == new[pin] and fingerprint(repo / key) == rows[key]['fingerprint'],
                 'exact codec projection mismatch')
    return dict(status='PASS', mode='ARCHIVED_BYTES_RETAINED_NO_LIVE_ORIGIN_RENEWAL' if after else 'LIVE_BEFORE_PRUNE',
                closureSha256=closure_sha, archiveManifestSha256=archive_manifest_sha,
                selectedFiles=len(selected), selectedBytes=sum(rows[key]['size'] for key in selected),
                complementFiles=len(rows) - len(selected), observedAliases=len(aliases),
                protectedPaths=len(protected), reconstructedBlobs=len(verified_blobs),
                sourceVersions=source_versions_sha, versionedSourceBindings=versioned,
                retiredProductsManifest=retired_sha, retiredProducts=list(retired.values()),
                retiredProductOriginState='UNAVAILABLE_ARCHIVED' if retired else 'NONE_RETIRED',
                projectionChecked=True, currentGlobalAllocationMeasured=False,
                historicalClosureLimits=c['limits'],
                limits=['original closure limits are historical metadata, not renewed current live-origin assertions',
                        'retention only; exact historical source bytes are not live-source qualification; no semantic replay, runtime source/executable substitution, restore, or old live-origin/inode/ctime renewal',
                                      'allocation projection checked against fixed caps; current global allocation is not measured'])


def forbid_process(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.forkpty', 'os.exec', 'pty.spawn'}:
        raise ValueError('retention audit forbids process creation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--closure', required=True, type=Path)
    parser.add_argument('--closure-sha', required=True)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--archive-manifest', type=Path)
    parser.add_argument('--archive-manifest-sha')
    parser.add_argument('--source-versions', nargs=2, metavar=('PATH', 'SHA256'))
    parser.add_argument('--retired-products', nargs=2, metavar=('MANIFEST', 'SHA256'),
                        help='exact historical game outputs only; never current runtime/tool substitution')
    args = parser.parse_args()
    sys.addaudithook(forbid_process)
    print(json.dumps(verify(args.closure, args.closure_sha, args.repo,
                            args.archive_manifest, args.archive_manifest_sha,
                            args.source_versions, args.retired_products), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
