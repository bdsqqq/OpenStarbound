"""Bounded owned-image release adapter, never a game/native admission.

Callers serialize ownership and retain release-evidence on success AND failure.
A failure can leave the owned mount attached: callers must handle that failure,
not claim a finally-based lifecycle guarantee. The finite logical evidence bound
below is not a physical quota or a complete production resource reservation.
Importing this module launches nothing; only explicit release/run calls execute.
"""
import copy
import importlib.util
import math
import os
from pathlib import Path
import pwd
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load('_sv_release_builder', ROOT / 'scripts/build-static-vector-behavior-lab.py')
er = _load('_sv_release_primitive', Path(__file__).with_name('enclosure_release.py'))
bounded = _load('_sv_release_outputs', Path(__file__).with_name('bounded_outputs.py'))
SCOPE = 'RESOURCE_RELEASE_ONLY_NOT_ADMISSION'
RECORD_BYTES = 256 * 1024
LIMITS = dict(stdoutBytes=er.STDOUT_LIMIT, stderrBytes=er.STDERR_LIMIT,
              readChunkBytes=64 * 1024, overflowBytes=64 * 1024)
# Two fixed stages, two records each (published plus one retained partial), two
# streams and at most one bounded overflow per stream. Directory blocks excluded.
EVIDENCE_LOGICAL_BYTES = 2 * (4 * RECORD_BYTES + er.STDOUT_LIMIT +
                             er.STDERR_LIMIT + 2 * LIMITS['overflowBytes'])


def _fingerprint(path):
    er.physical(str(path))
    info = path.lstat()
    er.need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            'runner unique regular input')
    return bounded._fingerprint(info)


def _read_capture(path, limit):
    """Read only bounded physical bytes, bracketing descriptor/path identity."""
    before = _fingerprint(path)
    er.need(path.stat().st_size <= limit, 'capture byte limit')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        er.need(bounded._fingerprint(os.fstat(fd)) == before, 'capture open drift')
        pieces, size = [], 0
        while True:
            piece = os.read(fd, min(65536, limit - size + 1))
            if not piece:
                break
            size += len(piece)
            er.need(size <= limit, 'capture byte limit')
            pieces.append(piece)
        er.need(bounded._fingerprint(os.fstat(fd)) == before == _fingerprint(path),
                'capture read drift')
        er.need(size == before[4], 'capture size drift')
        return b''.join(pieces)
    finally:
        os.close(fd)


def make_runner(owner, *, now=None):
    """Create a single-use info→detach runner with no caller-selected paths.

    Direct factory users must still positively associate info before detach.
    originalExperiment is deliberately excluded from serializable witnesses.
    """
    now = time.monotonic if now is None else now
    er.validate_owner(owner)
    host_device = er.mounted_state(owner)
    witness = copy.deepcopy({key: owner[key] for key in owner if key != 'originalExperiment'})
    root = er.physical(owner['root']) / 'release-evidence'
    mount = er.physical(owner['mount']['path'])
    er.need(not root.is_relative_to(mount), 'release evidence under mount')
    er.under(root, er.physical(str(er.G)))
    root.mkdir()  # exclusive, fixed name; failures cannot accumulate retry names
    root_info = root.lstat()
    root_id = (root_info.st_dev, root_info.st_ino, root_info.st_mode)
    python = Path(sys.executable).resolve(strict=True)
    inputs = [Path(__file__).resolve(), Path(builder.__file__).resolve(),
              Path(er.__file__).resolve(), Path(bounded.__file__).resolve(),
              builder.GUARDIAN, python, er.physical(owner['tool']['path'])]
    # Detach can flush backing contents. image_state pins inode/device/size,
    # not immutable backing bytes; immutable sources/launcher/tool are stronger.
    pinned = {path: (_fingerprint(path), builder.identity(path)) for path in inputs}
    deadline, last, stage, bound_info = None, None, 0, False
    suffixes = ('.command.json', '.receipt.json', '.stdout', '.stderr',
                '.stdout-overflow.bin', '.stderr-overflow.bin')
    allowed = {root / (stem + suffix) for stem in ('info', 'detach') for suffix in suffixes}

    def clock():
        nonlocal last
        current = now()
        er.need(type(current) in (int, float) and math.isfinite(current), 'finite runner clock')
        er.need(last is None or current >= last, 'runner clock regressed')
        last = current
        return current

    def remaining():
        left = deadline - clock()
        er.need(0 < left <= er.RELEASE_SECONDS, 'release deadline expired or extended')
        return left

    def validate():
        remaining()
        er.need(witness == {key: owner[key] for key in owner if key != 'originalExperiment'},
                'runner owner changed')
        er.validate_owner(owner)
        er.image_state(owner)
        er.tool_state(owner)
        er.need(er.physical(str(root)) == root and root.is_dir(), 'physical evidence root')
        current = root.lstat()
        er.need((current.st_dev, current.st_ino, current.st_mode) == root_id,
                'evidence directory changed')
        er.need(not root.is_relative_to(er.physical(owner['mount']['path'])),
                'release evidence under mount')
        for path, (fingerprint, identity) in pinned.items():
            er.need(_fingerprint(path) == fingerprint and builder.identity(path) == identity,
                    'runner input drift')

    def check_output(path):
        er.need(type(path) is type(root) and path in allowed and path.parent == root,
                'undeclared release output')
        er.need(er.physical(str(root)) == root, 'physical evidence parent')

    def write_record(path, value):
        check_output(path)
        er.need(path.name.endswith(('.command.json', '.receipt.json')), 'release record path')
        return bounded.write_json(path, value, RECORD_BYTES)

    def run(argv, *, deadline_monotonic):
        nonlocal deadline, stage, bound_info
        er.need(type(argv) is list and all(type(word) is str for word in argv), 'exact release argv')
        expected = ([er.TOOL, 'info', '-plist'] if stage == 0 else
                    [er.TOOL, 'detach', witness['device']])
        er.need(stage < 2 and argv == expected, 'release command order/allowlist')
        er.need(type(deadline_monotonic) in (int, float) and math.isfinite(deadline_monotonic),
                'finite absolute release deadline')
        er.need(deadline is None or deadline == deadline_monotonic, 'release deadline changed')
        deadline = deadline_monotonic
        validate()
        if stage == 1:
            er.need(bound_info, 'detach without positive info association')
        er.need(er.mounted_state(owner) == host_device, 'release mount changed')
        stem = 'info' if stage == 0 else 'detach'
        stage += 1  # any failed invocation consumes this fixed stage
        receipt = builder._supervise_command(argv, ROOT / 'source',
            dict(PATH='/usr/bin:/bin', HOME=pwd.getpwuid(os.getuid()).pw_dir),
            root / stem, limits=dict(LIMITS), validate=validate,
            remaining_seconds=remaining, python=python, witness=witness,
            write_record=write_record, check_output=check_output, scope=SCOPE)
        validate()
        er.need(receipt.get('scope') == SCOPE, 'release receipt scope')
        er.need(receipt['outputComplete'] is True and receipt['commandReaped'] is True
                and receipt['guardianReaped'] is True and receipt['reaped'] is True
                and receipt['returncode'] == 0 and type(receipt['returncode']) is int
                and receipt['failure'] is None and receipt['cleanupFailure'] is None,
                'release command not normally completed/reaped')
        captured = {name: _read_capture((root / stem).with_suffix('.' + name), LIMITS[name + 'Bytes'])
                    for name in ('stdout', 'stderr')}
        for name, data in captured.items():
            row = receipt['streams'][name]
            er.need(type(row) is dict and set(row) == {'eof', 'overflow', 'bytesWritten', 'bytesRead'}
                    and all(type(row[key]) is int for key in ('bytesWritten', 'bytesRead'))
                    and row['eof'] is True and row['overflow'] is None
                    and row['bytesWritten'] == row['bytesRead'] == len(data), 'incomplete release capture')
        if stem == 'info':
            er.association(captured['stdout'], owner)
            bound_info = True
        validate()
        return dict(returncode=receipt['returncode'], reaped=True, **captured)

    return run


def release(owner):
    """Explicitly run bounded normal release; retain opaque failed acquisition."""
    return er.release_owned_image(owner, make_runner(owner))
