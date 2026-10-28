#!/usr/bin/env python3
"""Read-only conservation gate around cleanup-migration-artifacts.py.

Archive JSON is data, never a source/tool resolver or renewed native admission.
The parent alone runs the existing archiver; this gate never archives or restores.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat

from cache_retention import row

ROOT = Path(__file__).resolve().parents[3]
ROOTS = ['build/id-map-' + s for s in (
    'native-r1', 'edges-r1', 'abi-r1', 'boundary-r1', 'rust-bridge-r1',
    'production-r2', 'scene-r1')]
MIN_BYTES = 2 * 1024**2
RUN = '20261028-id-map-native-products-r1'
GAME = 'build/behavior/weighted-pool-combined-r1/'
CANONICAL = 'build/id-map-rust-r1/target/aarch64-apple-darwin/release/libstar_engine_ffi.a'
BINS = [GAME + role + '/bin/starbound' for role in ('reference', 'candidate')]
REFERENCE_OBJECTS = GAME + 'reference/cmake/core/CMakeFiles/star_core.dir/'
REFERENCE_OBJECT_ROOTS = [GAME + 'reference/cmake/' + name + '/' for name in ('core', 'extern')]
ARCHIVE = 'build/migration-evidence-archive'
MANIFEST = ARCHIVE + '/runs/' + RUN + '/manifest.json'
MAX_ARCHIVE = 16 * 1024**3
MAX_PRODUCT = 128 * 1024**2
# These two actual accounting members are not a license to archive arbitrary logs.
SPECIAL_PRODUCTS = {
    'build/id-map-rust-bridge-r1/links-r2/disassemble.stdout',
    'build/id-map-rust-bridge-r1/origins.typed',
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def relative(name):
    need(isinstance(name, str), 'relative path string')
    p = Path(name)
    need(not p.is_absolute() and '..' not in p.parts and str(p) == name
         and name not in ('', '.'), 'canonical relative path')
    return p


def physical(repo, name, directory=False):
    path = repo / relative(name)
    need(path.resolve() == path, 'physical path, no aliases: ' + name)
    s = path.lstat()
    need(stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode),
         'physical directory' if directory else 'physical regular file')
    return path


def repository(repo):
    repo = Path(repo)
    need(repo.is_absolute() and repo.resolve() == repo and repo.is_dir(),
         'physical repository root')
    return repo


def inventory(repo):
    """Every regular physical member, including the small live complement."""
    repo = repository(repo)
    result = {}
    inodes = set()
    for name in ROOTS:
        root = physical(repo, name, directory=True)
        for parent, dirs, files in os.walk(root, followlinks=False):
            for child in dirs:
                physical(repo, str((Path(parent) / child).relative_to(repo)), True)
            for child in files:
                path = Path(parent) / child
                name = str(path.relative_to(repo))
                r = row(physical(repo, name))
                inode = tuple(r['fingerprint'][:2])
                need(inode not in inodes, 'inventory inode alias')
                inodes.add(inode)
                result[name] = r
    return result


def validate_row(r):
    need(isinstance(r, dict) and set(r) == {'sha256', 'size', 'fingerprint', 'allocated'},
         'exact row schema')
    h, f = r['sha256'], r['fingerprint']
    need(isinstance(h, str) and len(h) == 64 and all(c in '0123456789abcdef' for c in h),
         'sha256 row')
    need(isinstance(f, list) and len(f) == 7 and all(type(n) is int and n >= 0 for n in f),
         'fingerprint row')
    need(type(r['size']) is int and 0 <= r['size'] == f[2]
         and type(r['allocated']) is int and r['allocated'] >= 0
         and stat.S_ISREG(f[5]) and f[6] >= 1, 'regular consistent row')


def validate_selection(rows):
    need(isinstance(rows, dict), 'inventory mapping')
    for name, r in rows.items():
        relative(name)
        need(any(name.startswith(root + '/') for root in ROOTS), 'fixed product roots')
        validate_row(r)
    selected = sorted(name for name, r in rows.items() if r['size'] >= MIN_BYTES)
    need(1 <= len(selected) <= 64, 'bounded selected count')
    for name in selected:
        r = rows[name]
        need(r['fingerprint'][6] == 1, 'selected external hardlink exclusion')
        suffix = Path(name).suffix
        executable = bool(r['fingerprint'][5] & 0o111)
        need(suffix in ('.map', '.json', '.o') or (not suffix and executable)
             or name in SPECIAL_PRODUCTS, 'known generated product type: ' + name)
        need(r['size'] <= MAX_PRODUCT, 'bounded individual product')
    return selected


def archive_allocated(repo):
    """Same allocated-byte accounting as the existing tool, without invoking it."""
    root = repo / ARCHIVE
    if not root.exists():
        need(not root.is_symlink(), 'no archive alias')
        return 0
    physical(repo, ARCHIVE, True)
    total, seen = 0, set()
    for parent, dirs, files in os.walk(root, followlinks=False):
        for path in [Path(parent), *(Path(parent) / n for n in files)]:
            name = str(path.relative_to(repo))
            physical(repo, name, path == Path(parent))
            s = path.lstat()
            inode = (s.st_dev, s.st_ino)
            if inode not in seen:
                seen.add(inode)
                total += s.st_blocks * 512
        for name in dirs:
            physical(repo, str((Path(parent) / name).relative_to(repo)), True)
    return total


def reconstructed(repo, expected):
    h = expected['sha256']
    blob = physical(repo, ARCHIVE + '/blobs/' + h[:2] + '/' + h + '.gz')
    # Limit both compressed input and decompressed output; do not trust gzip ISIZE.
    need(blob.stat().st_size <= expected['size'] + 1024**2, 'bounded compressed blob')
    digest, size = hashlib.sha256(), 0
    with gzip.open(blob, 'rb') as source:
        while block := source.read(min(1024**2, expected['size'] - size + 1)):
            size += len(block)
            need(size <= expected['size'], 'bounded reconstruction size')
            digest.update(block)
    need((digest.hexdigest(), size) == (h, expected['size']), 'exact reconstructed bytes')


def verify(repo, closure, manifest=None):
    """Verify a pinned original closure before or after the parent archives it."""
    repo = repository(repo)
    need(set(closure) == {'version', 'roots', 'minBytes', 'archiveRun', 'inventory',
                         'protected', 'selected', 'archiveGrowthBound', 'archiveBeforeBytes'},
         'exact closure schema')
    need(type(closure['version']) is int and closure['version'] == 1
         and closure['roots'] == ROOTS and closure['minBytes'] == MIN_BYTES
         and closure['archiveRun'] == RUN, 'fixed product scope')
    growth, before = closure['archiveGrowthBound'], closure['archiveBeforeBytes']
    need(type(growth) is int and 0 < growth <= 128 * 1024**2
         and type(before) is int and 0 <= before <= MAX_ARCHIVE
         and before + growth <= MAX_ARCHIVE, 'fixed archive bounds')
    original = closure['inventory']
    selected = validate_selection(original)
    need(closure['selected'] == selected, 'exact closure selection')
    protected = closure['protected']
    need(isinstance(protected, dict) and CANONICAL in protected
         and all(p in protected for p in BINS), 'required canonical and both old bins')
    # Match game_build_admission.retained_objects(): Core AND extern, including
    # nested scripting/Lua objects. The closure preserves their original identities.
    need(sum(any(p.startswith(root) for root in REFERENCE_OBJECT_ROOTS) and p.endswith('.o')
             for p in protected) >= 113, 'at least 113 original reference Core/extern objects')
    protected_inodes = set()
    for name, r in protected.items():
        relative(name)
        need(name.startswith(GAME) or name == CANONICAL, 'fixed protection scope')
        validate_row(r)
        protected_inodes.add(tuple(r['fingerprint'][:2]))
    need(not set(selected).intersection(protected)
         and all(tuple(original[p]['fingerprint'][:2]) not in protected_inodes for p in selected),
         'selected protected path/inode overlap')
    for name, r in protected.items():
        need(row(physical(repo, name)) == r, 'unchanged protected bytes: ' + name)
    now = inventory(repo)
    after = manifest is not None
    need(set(now) == set(original) - (set(selected) if after else set()),
         'exact live complement membership')
    for name, r in now.items():
        need(r == original[name], 'unchanged live complement: ' + name)
    current_archive = archive_allocated(repo)
    need(current_archive <= MAX_ARCHIVE, 'archive cap')
    need(before <= current_archive <= before + growth if after else current_archive == before,
         'archive growth accounting')
    if after:
        need(manifest['version'] == 1 and manifest['status'] == 'ARCHIVED_VERIFIED_PRUNED'
             and manifest['roots'] == ROOTS and manifest['min_bytes'] == MIN_BYTES,
             'exact verified archive state/scope')
        entries = manifest['entries']
        need(isinstance(entries, list) and len(entries) == len(selected)
             and sorted(e['path'] for e in entries) == selected, 'exact manifest selection')
        need(manifest['removed_bytes'] == sum(original[p]['size'] for p in selected),
             'exact removed bytes')
        unique = set()
        for e in entries:
            r = original[e['path']]
            need(all(e[k] == r[k] for k in ('sha256', 'size', 'fingerprint'))
                 and e['mode'] == stat.S_IMODE(r['fingerprint'][5])
                 and e['mtime_ns'] == r['fingerprint'][3], 'original manifest source pin')
            path = repo / e['path']
            need(not path.exists() and not path.is_symlink(), 'archived original absent')
            if r['sha256'] not in unique:
                reconstructed(repo, r)
                unique.add(r['sha256'])
        need(manifest['unique_blobs'] == len(unique), 'exact unique blobs')
    return dict(status='ARCHIVED_PRODUCT_BYTES_NO_LIVE_ORIGIN_RENEWAL' if after else 'LIVE_PRODUCT_PREFLIGHT',
                selected=len(selected), complement=len(original) - len(selected), protected=len(protected),
                archivedLogicalBytes=sum(original[p]['size'] for p in selected),
                liveOriginState='UNAVAILABLE_ARCHIVED' if after else 'LIVE_ORIGINAL',
                limits=['byte conservation only; no semantic/native qualification renewal',
                        'archived original live-path/inode/ctime/native-origin replay unavailable'])


def pinned_json(repo, name, pin, expected=None):
    path = Path(name)
    if not path.is_absolute():
        path = repo / path
    need(path.is_relative_to(repo), 'metadata inside physical repository')
    rel = str(path.relative_to(repo))
    if expected is not None:
        need(rel == expected, 'fixed archive run manifest path')
    path = physical(repo, rel)
    need(path.stat().st_size <= 16 * 1024**2, 'bounded JSON metadata')
    data = path.read_bytes()
    need(isinstance(pin, str) and hashlib.sha256(data).hexdigest() == pin, 'external metadata pin')
    # Duplicate JSON members must not silently change a pinned closure's meaning.
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON member')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--closure', required=True)
    parser.add_argument('--closure-sha', required=True)
    parser.add_argument('--manifest')
    parser.add_argument('--manifest-sha')
    args = parser.parse_args(argv)
    need(bool(args.manifest) == bool(args.manifest_sha), 'manifest and external pin together')
    c = pinned_json(ROOT, args.closure, args.closure_sha)
    m = pinned_json(ROOT, args.manifest, args.manifest_sha, MANIFEST) if args.manifest else None
    print(json.dumps(verify(ROOT, c, m), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
