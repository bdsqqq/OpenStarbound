"""Explicit current30 image acquisition, NOT a native/game admission.

The caller serializes lifecycle writers. Failed evidence and images are retained;
only positively identified mounts may be released. Logical capture limits and a
whole-G budget check are not a physical quota or a forecast of native products.
"""
import copy
import datetime as dt
import math
import os
from pathlib import Path
import plistlib
import pwd
import re
import stat
import sys
import time


def _load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
ad = _load('_sv_setup_admission', HERE / 'game_build_admission.py')
runner = _load('_sv_setup_runner', HERE / 'enclosure_runner.py')
er, builder, bounded = runner.er, runner.builder, runner.bounded
SCOPE = 'STORAGE_SETUP_ONLY_NOT_NATIVE_ADMISSION'
SETUP_SECONDS = 35 * 60
RECORD_BYTES = 256 * 1024
LIMITS = dict(stdoutBytes=1024 * 1024, stderrBytes=64 * 1024,
              readChunkBytes=64 * 1024, overflowBytes=64 * 1024)


def _publish_bytes(path, raw):
    """Fixed exclusive partial, durable before exclusive install; retain failures."""
    er.need(type(raw) is bytes and 0 < len(raw) <= LIMITS['stdoutBytes'], 'bounded plist bytes')
    path = bounded._path(path)
    er.need(not os.path.lexists(path), 'info destination exists')
    partial = path.with_name('.' + path.name + '.partial')
    dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(partial.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=dfd)
        try:
            initial = os.fstat(fd)
            bounded._regular(initial)
            offset = 0
            while offset < len(raw):
                piece = raw[offset:offset + 65536]
                count = os.write(fd, piece)
                er.need(0 < count <= len(piece), 'plist write progress')
                offset += count
            os.fsync(fd)
            written = os.fstat(fd)
            bounded._regular(written)
            er.need((written.st_dev, written.st_ino) == (initial.st_dev, initial.st_ino)
                    and written.st_size == len(raw), 'plist descriptor drift')
            er.need(bounded._fingerprint(partial.lstat()) == bounded._fingerprint(written),
                    'plist partial drift')
            bounded._parents(path)
            er.need((path.parent.stat().st_dev, path.parent.stat().st_ino) ==
                    (os.fstat(dfd).st_dev, os.fstat(dfd).st_ino), 'plist parent drift')
            os.link(partial.name, path.name, src_dir_fd=dfd, dst_dir_fd=dfd,
                    follow_symlinks=False)
            os.fsync(dfd)
            linked = partial.lstat()
            er.need((linked.st_dev, linked.st_ino, linked.st_nlink) ==
                    (initial.st_dev, initial.st_ino, 2), 'plist install drift')
            os.unlink(partial.name, dir_fd=dfd)
            os.fsync(dfd)
            identity, _ = bounded._identity(dfd, path.name, path, LIMITS['stdoutBytes'])
            er.need(runner._read_capture(path, LIMITS['stdoutBytes']) == raw, 'published plist drift')
            return identity
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


def _entities(raw):
    er.need(type(raw) is bytes and len(raw) <= LIMITS['stdoutBytes'], 'bounded attach plist')
    try:
        value = plistlib.loads(raw, dict_type=er._PlistDict)
    except Exception as error:
        raise er.ReleaseError('malformed attach plist') from error
    er.need(type(value) is er._PlistDict and type(value.get('system-entities')) is list,
            'attach entities')
    entities = value['system-entities']
    er.need(len(entities) == 2 and all(type(e) is er._PlistDict for e in entities),
            'exact two attach entities')
    return entities


def acquire(image_bytes, *, host_fixture=False):
    """Create one explicitly sized UDRW image and leave its owned mount attached.

    host_fixture selects a separate fixed HOST_ONLY namespace. It never changes
    the default admission namespace, a native argv, or a game experiment epoch.
    A failed attempt consumes its fixed root; conservation belongs to the caller.
    """
    er.need(type(host_fixture) is bool, 'strict fixture boolean')
    er.need(type(image_bytes) is int and 16 * 1024**2 <= image_bytes <=
            ad.CAPS['newRootBytes'] // 2 and image_bytes % 512 == 0,
            'explicit sector-aligned image sanity size')
    start = time.monotonic()
    er.need(type(start) in (int, float) and math.isfinite(start), 'finite setup clock')
    deadline, last = start + SETUP_SECONDS, start
    created = dt.datetime.now(dt.timezone.utc)
    g = er.physical(str(ad.allocation_root()))
    g_id = (g.stat().st_dev, g.stat().st_ino)
    root = g / 'enclosure-setup-host-r1' if host_fixture else ad.enclosure_root()
    er.need(root == g / ('enclosure-setup-host-r1' if host_fixture else 'current30-enclosure'),
            'fixed setup namespace')
    er.need(not os.path.lexists(root), 'setup root already exists')
    mount, image = root / 'products', root / 'image.dmg'
    python = Path(sys.executable).resolve(strict=True)
    inputs = [Path(__file__).resolve(), Path(ad.__file__).resolve(),
              Path(builder.__file__).resolve(), Path(er.__file__).resolve(),
              Path(runner.__file__).resolve(), Path(bounded.__file__).resolve(),
              Path(ad.config.__file__).resolve(), Path(ad.primitives.__file__).resolve(),
              Path(ad.allocation.__file__).resolve(), builder.GUARDIAN, python,
              er.physical(er.TOOL)]
    pins = {p: (runner._fingerprint(p), builder.identity(p)) for p in inputs}
    experiment = dict(type='SourceSetupOnly', createdUTC=created.isoformat(),
                      deadlineUTC=(created + dt.timedelta(seconds=SETUP_SECONDS)).isoformat(),
                      status='IN_PROGRESS', scope=SCOPE,
                      evidence='HOST_ONLY' if host_fixture else 'SOURCE_SETUP_ONLY')
    root_id = None
    mount_id = None
    image_pin = None
    owner = None
    attach_started = False
    created_root = False
    suffixes = ('.command.json', '.receipt.json', '.stdout', '.stderr',
                '.stdout-overflow.bin', '.stderr-overflow.bin')
    allowed = {root / (stem + suffix) for stem in ('create', 'attach', 'info', 'recovery-info')
               for suffix in suffixes}

    def remaining():
        nonlocal last
        current = time.monotonic()
        er.need(type(current) in (int, float) and math.isfinite(current)
                and last <= current < deadline, 'setup deadline expired or clock regressed')
        last = current
        return deadline - current

    def stable():
        for path, pin in pins.items():
            er.need((runner._fingerprint(path), builder.identity(path)) == pin, 'setup input drift')
        er.need(er.physical(str(g)) == g and
                (g.stat().st_dev, g.stat().st_ino) == g_id, 'physical allocation root drift')
        if root_id is not None:
            er.need(er.physical(str(root)) == root and
                    (root.stat().st_dev, root.stat().st_ino) == root_id, 'setup root drift')
        if mount_id is not None and not attach_started:
            er.need(er.physical(str(mount)) == mount and
                    (mount.stat().st_dev, mount.stat().st_ino) == mount_id
                    and not list(mount.iterdir()), 'fresh mountpoint drift')
        if image_pin is not None:
            current = image.lstat()
            er.need(stat.S_ISREG(current.st_mode) and current.st_nlink == 1 and
                    (current.st_dev, current.st_ino, current.st_size) == image_pin,
                    'setup image drift')
        if owner is not None:
            er.validate_owner(owner)
            er.mounted_state(owner)
            er.tool_state(owner)

    def validate():
        remaining()
        stable()
        ad.check_budget()
        remaining()
        stable()

    def check_output(path):
        er.need(type(path) is type(root) and path in allowed and path.parent == root,
                'undeclared setup output')
        er.need(er.physical(str(root)) == root, 'physical setup evidence root')

    def write_record(path, value):
        check_output(path)
        er.need(path.name.endswith(('.command.json', '.receipt.json')), 'setup record path')
        return bounded.write_json(path, value, RECORD_BYTES)

    def command(stem, argv, *, recovering=False):
        # Recovery has an independent finite reserve, never a renewed setup epoch.
        if recovering:
            reserve = time.monotonic() + er.RELEASE_SECONDS

            def recovery_remaining():
                left = reserve - time.monotonic()
                er.need(0 < left <= er.RELEASE_SECONDS, 'recovery deadline expired')
                return left

            def recovery_validate():
                recovery_remaining()
                stable()  # deliberately no whole-allocation walk or setup clock

            check, left = recovery_validate, recovery_remaining
        else:
            check, left = validate, remaining
        check()
        receipt = builder._supervise_command(argv, ad.ROOT / 'source',
            dict(PATH='/usr/bin:/bin', HOME=pwd.getpwuid(os.getuid()).pw_dir),
            root / stem, limits=dict(LIMITS), validate=check, remaining_seconds=left,
            python=python, witness=dict(originalExperiment=copy.deepcopy(experiment),
                inputs={str(p): dict(physical=list(pin[0]), identity=pin[1])
                        for p, pin in pins.items()}, rootIdentity=root_id,
                imageIdentity=image_pin), write_record=write_record,
            check_output=check_output, scope=SCOPE)
        check()
        er.need(receipt.get('scope') == SCOPE and
                all(receipt.get(k) is True for k in
                    ('outputComplete', 'commandReaped', 'guardianReaped', 'reaped')) and
                type(receipt.get('returncode')) is int and receipt['returncode'] == 0 and
                receipt.get('failure') is None and receipt.get('cleanupFailure') is None,
                'setup command not normally completed/reaped')
        captures = {}
        for name in ('stdout', 'stderr'):
            raw = runner._read_capture(root / (stem + '.' + name), LIMITS[name + 'Bytes'])
            row = receipt['streams'][name]
            er.need(type(row) is dict and set(row) == {'eof', 'overflow', 'bytesWritten', 'bytesRead'}
                    and row['eof'] is True and row['overflow'] is None
                    and type(row['bytesWritten']) is int and type(row['bytesRead']) is int
                    and row['bytesWritten'] == row['bytesRead'] == len(raw), 'setup capture incomplete')
            captures[name] = raw
        return captures['stdout']

    def bind(entities):
        er.need(image_pin is not None and type(entities) is list and len(entities) == 2
                and all(type(e) is er._PlistDict for e in entities), 'typed owned image entities')
        whole = [e for e in entities if type(e.get('dev-entry')) is str and
                 re.fullmatch(r'/dev/disk[0-9]+', e['dev-entry'])]
        volume = [e for e in entities if type(e.get('dev-entry')) is str and
                  re.fullmatch(r'/dev/disk[0-9]+s[0-9]+', e['dev-entry'])]
        er.need(len(whole) == len(volume) == 1 and 'mount-point' not in whole[0]
                and volume[0].get('mount-point') == str(mount), 'exact owned attach devices')
        candidate = dict(root=str(root), image=dict(path=str(image), st_dev=image_pin[0],
            st_ino=image_pin[1], size=image_pin[2], maxBytes=image_bytes),
            mount=dict(path=str(mount), st_dev=er.physical(str(mount)).stat().st_dev),
            device=whole[0]['dev-entry'], volumeDevice=volume[0]['dev-entry'],
            tool=dict(path=er.TOOL, sha256=pins[Path(er.TOOL)][1]['sha256']),
            originalExperiment=experiment)
        er.validate_owner(candidate)
        er.mounted_state(candidate)
        er.tool_state(candidate)
        stable()
        return candidate

    try:
        validate()  # before any allocation, not a forecast of later physical bytes
        root.mkdir(mode=0o700)
        created_root = True
        root_id = (root.stat().st_dev, root.stat().st_ino)
        # Ownership may be published before a final check fails. Keep the lease
        # uncommitted through every fallible check, including interrupted cleanup.
        pending = root / '.setup-in-progress'
        pending_identity = bounded.write_json(pending, dict(scope=SCOPE, state='PENDING'), 1024)
        mount.mkdir()
        mount_id = (mount.stat().st_dev, mount.stat().st_ino)
        er.need(er.physical(str(mount)) == mount and not list(mount.iterdir())
                and mount.stat().st_dev == root.stat().st_dev, 'fresh physical host mountpoint')
        validate()
        command('create', [er.TOOL, 'create', '-sectors', str(image_bytes // 512),
                          '-fs', 'HFS+', '-type', 'UDIF', '-volname',
                          'openstarbound-current30', str(image)])
        er.physical(str(image))
        state = image.lstat()
        er.need(stat.S_ISREG(state.st_mode) and state.st_nlink == 1 and
                state.st_ino > 0 and state.st_size == image_bytes, 'exact created image size/type')
        image_pin = (state.st_dev, state.st_ino, state.st_size)
        validate()
        er.need(not list(mount.iterdir()) and mount.stat().st_dev == root.stat().st_dev,
                'mountpoint changed before attach')
        attach_started = True
        raw = command('attach', [er.TOOL, 'attach', '-nobrowse', '-noautoopen', '-owners',
                                 'off', '-mountpoint', str(mount), '-plist', str(image)])
        owner = bind(_entities(raw))
        validate()
        info = command('info', [er.TOOL, 'info', '-plist'])
        er.association(info, owner)
        validate()
        info_identity = _publish_bytes(root / 'ownership-info.plist', info)
        validate()
        er.need(ad._bounded_owner_file(root / 'ownership-info.plist')[1]['identity'] == info_identity,
                'ownership info publication drift')
        experiment['status'] = 'ACQUIRED'
        bounded.write_json(root / 'owner.json', owner, 1024**2)  # publish LAST
        validate()
        raw_owner, _ = ad._bounded_owner_file(root / 'owner.json')
        er.need(ad._owner_json(raw_owner) == owner, 'owner publication drift')
        er.validate_owner(owner)
        er.mounted_state(owner)
        er.association(ad._bounded_owner_file(root / 'ownership-info.plist')[0], owner)
        remaining()
        stable()
        er.need(ad._bounded_owner_file(pending)[1]['identity'] == pending_identity,
                'setup commit marker drift')
        # Commit is the final operation: a crash may conservatively retain this
        # marker, but no later validation can leave a failed lease looking armed.
        os.unlink(pending)
        return owner
    except BaseException as original:
        experiment['status'] = 'FAILED'
        cleanup = 'NOT_MOUNTED'
        secondary = []
        if attach_started:
            cleanup = 'UNAVAILABLE'
            try:
                stable()
                if owner is None:
                    # A reaped failed attach may still have mounted. Never infer a
                    # device from a name alone: live info must bind this exact image.
                    info = command('recovery-info', [er.TOOL, 'info', '-plist'], recovering=True)
                    parsed = plistlib.loads(info, dict_type=er._PlistDict)
                    er.need(type(parsed) is er._PlistDict and type(parsed.get('images')) is list,
                            'recovery info images')
                    selected = [r for r in parsed['images'] if type(r) is er._PlistDict
                                and r.get('image-path') == str(image)]
                    er.need(len(selected) == 1, 'unique recovery image')
                    owner = bind(selected[0].get('system-entities', []))
                    er.association(info, owner)
                stable()
                runner.release(owner)  # public independent 30-second release clock
                cleanup = 'RELEASED'
            except BaseException as error:
                secondary.append(type(error).__name__ + ': ' + str(error)[:4096])
        if created_root:
            try:
                bounded.write_json(root / 'setup-failure.json', dict(scope=SCOPE,
                    originalExperiment=experiment, errorType=type(original).__name__,
                    error=str(original)[:8192], cleanup=cleanup, secondary=secondary), 64 * 1024)
            except BaseException as error:
                secondary.append('failure evidence unavailable: ' + str(error)[:4096])
        # Preserve original exception on pre-3.11 Python as well.
        try:
            original.setup_cleanup = dict(status=cleanup, secondary=secondary)
        except Exception:
            pass  # custom exception attributes cannot replace the original error
        raise
