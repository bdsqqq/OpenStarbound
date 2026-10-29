#!/usr/bin/env python3
"""Opt-in bounded publication for current30 common provenance, not game admission."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ad = _load('_sv_provenance_admission', Path(__file__).with_name('game_build_admission.py'))
bp = ad.load('_sv_common_provenance', ad.ROOT / 'source/lab/behavior/build_provenance.py')


def _canonical(path):
    path = Path(path)
    ad.need(path.is_absolute() and '..' not in path.parts and path.resolve() == path,
            'absolute physical canonical path required')
    for part in (path, *path.parents):
        ad.need(not part.is_symlink(), 'provenance path alias forbidden')
    return path


def _physical(path):
    _canonical(path)
    info = path.lstat()
    ad.need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            'unique regular provenance input required')
    return {key: getattr(info, key) for key in
            ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')}


def bounded_input(path):
    """check size before shared identity helpers, which themselves hash the file."""
    limit = ad.controller_limit(path)
    before = _physical(path)
    ad.need(before['st_size'] <= limit, 'provenance input exceeds byte limit')
    state = ad.file_state(path)
    identity = ad.identity(path)
    ad.need(before == state == _physical(path) and identity['size'] == before['st_size'],
            'provenance input changed while pinning')
    return identity, state


def _unchanged(path, original):
    ad.need(bounded_input(path) == original, 'original provenance input changed')


def _payload(value, root, side):
    ad.need(value.get('source_root') == str(root) and value.get('build_dir') == str(side / 'cmake'),
            'exact common provenance source/build paths required')


def run(args):
    root = _canonical(args.source_root)
    ad.need(root == ad.ROOT and root.resolve(strict=True) == root, 'current source root required')
    required = {
        'begin': {'snapshot', 'build_dir'}, 'configured': {'snapshot'},
        'seal': {'snapshot', 'binary'}, 'verify': {'binary'},
    }[args.phase]
    ad.need({key for key in ('snapshot', 'build_dir', 'binary') if getattr(args, key) is not None} == required,
            'exact phase arguments required')
    for key in required:
        _canonical(getattr(args, key))
    side = args.snapshot.parent if args.snapshot is not None else args.binary.parent.parent
    ad.need(side in {ad.build_root() / role for role in ('reference', 'candidate')}, 'exact role path required')
    if args.snapshot is not None:
        ad.need(args.snapshot == side / 'build-inputs.json', 'exact snapshot path required')
    if args.build_dir is not None:
        ad.need(args.build_dir == side / 'cmake', 'exact CMake path required')
    if args.binary is not None:
        ad.need(args.binary == side / 'bin/starbound', 'exact binary path required')
        binary_state = _physical(args.binary)

    if args.phase == 'begin':
        ad.write_common(args.snapshot, bp.begin(root, args.build_dir))
        return
    if args.phase in ('configured', 'seal'):
        original = bounded_input(args.snapshot)
        snapshot = bp._read(args.snapshot)
        _payload(snapshot, root, side)
        if args.phase == 'configured':
            value = bp.configured(snapshot, root)
            # content alone misses same-byte inode replacement during computation.
            _unchanged(args.snapshot, original)
            ad.write_common(args.snapshot, value, original[0])
            return
        published = False

        def publish(path, value):
            nonlocal published
            ad.need(not published and path == bp.sidecar(args.binary), 'one exact sidecar publication required')
            _unchanged(args.snapshot, original)
            ad.need(_physical(args.binary) == binary_state, 'binary changed during sealing')
            ad.write_common(path, value)
            published = True

        proof = bp.seal(args.binary, snapshot, root, write=publish)
        ad.need(published, 'seal did not publish through bounded writer')
        _unchanged(args.snapshot, original)
    else:
        sidecar = bp.sidecar(args.binary)
        original = bounded_input(sidecar)
        _payload(bp._read(sidecar), root, side)
        proof = bp.verify(args.binary, root)
        _unchanged(sidecar, original)
    ad.need(_physical(args.binary) == binary_state, 'binary changed during provenance operation')
    print(json.dumps(proof, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('begin', 'configured', 'seal', 'verify'))
    parser.add_argument('--source-root', type=Path, default=ad.ROOT)
    parser.add_argument('--build-dir', type=Path)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--binary', type=Path)
    args = parser.parse_args(argv)
    try:
        run(args)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'build provenance: {exc}\n')


if __name__ == '__main__':
    main()
