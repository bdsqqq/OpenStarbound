"""Normal release of one positively bound image; NEVER native admission.

Owner schema (exact keys): root; image={path,st_dev,st_ino,size,maxBytes};
mount={path,st_dev}; device; volumeDevice; tool={path,sha256}; originalExperiment.
Paths are canonical absolute strings below the existing physical G/root. Integers
are non-bool. The image is a single-link regular file, size <= maxBytes. This
minimal protocol supports exactly whole-device and mounted-volume info entities;
other layouts fail closed rather than guessing which resource to detach.

The caller supplies a trusted bounded owned-process runner, not arbitrary shell
execution: run(argv, *, deadline_monotonic) returns EXACTLY returncode (int),
stdout (bytes <= 1MiB), stderr (bytes <= 64KiB), reaped (True). It must enforce
these bounds during capture, use the supplied absolute monotonic deadline and
reap on every outcome, including timeout exceptions, and retain bounded command
receipts before returning or raising. This primitive does not persist failure
logs. Validation here cannot retroactively bound an untrusted runner's allocation
or process lifetime.

Caller serializes lifecycle ownership (no concurrent writer/detacher). These
before/after checks are not hostile-writer CAS and cannot detect reverted changes.
No original acquisition clock, source/SDK epoch or failed result is renewed.
"""
import hashlib
import math
from pathlib import Path
import plistlib
import re
import stat
import time

G = Path(__file__).resolve().parents[3] / 'build/behavior/static-vector-combined-r1'
TOOL = '/usr/bin/hdiutil'
STDOUT_LIMIT = 1024 * 1024
STDERR_LIMIT = 64 * 1024
RELEASE_SECONDS = 30


class ReleaseError(ValueError):
    """Release unqualified; caller must retain failure and must not force cleanup."""


def need(condition, message):
    if not condition:
        raise ReleaseError(message)


def keys(value, expected, label):
    need(type(value) is dict and set(value) == set(expected), label + ' schema')


def integer(value, label, minimum=0):
    need(type(value) is int and value >= minimum, label + ' integer')


def physical(value):
    need(type(value) is str, 'path string')
    path = Path(value)
    need(path.is_absolute() and str(path) == value and '..' not in path.parts,
         'canonical absolute path')
    for part in (path, *path.parents):
        need(not part.is_symlink(), 'symlink path')
    need(path.resolve(strict=True) == path, 'physical path')
    return path


def under(path, root):
    need(path != root and path.is_relative_to(root), 'path outside owned root')


def image_state(owner):
    image = owner['image']
    path = physical(image['path'])
    under(path, physical(owner['root']))
    current = path.lstat()
    need(stat.S_ISREG(current.st_mode) and current.st_nlink == 1,
         'image regular single link')
    need((current.st_dev, current.st_ino, current.st_size) ==
         (image['st_dev'], image['st_ino'], image['size']), 'image identity changed')
    need(current.st_size <= image['maxBytes'], 'image bound')


def tool_state(owner):
    path = physical(owner['tool']['path'])
    current = path.lstat()
    need(stat.S_ISREG(current.st_mode) and current.st_nlink == 1,
         'tool regular single link')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    need(digest.hexdigest() == owner['tool']['sha256'], 'tool digest changed')


def mounted_state(owner):
    image_state(owner)
    tool_state(owner)
    mount = physical(owner['mount']['path'])
    under(mount, physical(owner['root']))
    need(mount.is_dir(), 'mount directory')
    volume = physical(owner['volumeDevice']).stat()
    need(stat.S_ISBLK(volume.st_mode), 'volume block device')
    need(mount.stat().st_dev == owner['mount']['st_dev'] == volume.st_rdev,
         'mount volume association')
    need(mount.parent.stat().st_dev != owner['mount']['st_dev'], 'mount host device')
    return mount.parent.stat().st_dev


def validate_owner(owner):
    keys(owner, ('root', 'image', 'mount', 'device', 'volumeDevice', 'tool',
                 'originalExperiment'), 'owner')
    keys(owner['image'], ('path', 'st_dev', 'st_ino', 'size', 'maxBytes'), 'image')
    keys(owner['mount'], ('path', 'st_dev'), 'mount')
    keys(owner['tool'], ('path', 'sha256'), 'tool')
    for name in ('st_dev', 'st_ino', 'size', 'maxBytes'):
        integer(owner['image'][name], name, 1 if name in ('st_ino', 'maxBytes') else 0)
    integer(owner['mount']['st_dev'], 'mount device', 1)
    for name, pattern in (('device', r'/dev/disk[0-9]+'),
                          ('volumeDevice', r'/dev/disk[0-9]+s[0-9]+')):
        need(type(owner[name]) is str and re.fullmatch(pattern, owner[name]), name)
    need(owner['volumeDevice'].startswith(owner['device'] + 's'), 'volume prefix')
    need(owner['tool']['path'] == TOOL and type(owner['tool']['sha256']) is str
         and re.fullmatch(r'[0-9a-f]{64}', owner['tool']['sha256']), 'tool pin')
    root = physical(owner['root'])
    under(root, physical(str(G)))
    need(root.is_dir(), 'owned root directory')
    image = physical(owner['image']['path'])
    mount = physical(owner['mount']['path'])
    need(image != mount and not image.is_relative_to(mount), 'image under mount')


class _PlistDict(dict):
    def __setitem__(self, key, value):
        need(key not in self, 'duplicate plist key')
        super().__setitem__(key, value)


def association(raw, owner):
    try:
        info = plistlib.loads(raw, dict_type=_PlistDict)
    except Exception as error:
        raise ReleaseError('malformed info plist') from error
    need(type(info) is _PlistDict and type(info.get('images')) is list, 'info images')
    selected = []
    for record in info['images']:
        need(type(record) is _PlistDict and type(record.get('image-path')) is str
             and type(record.get('system-entities')) is list, 'image record')
        record_path = Path(record['image-path'])
        need(record_path.is_absolute() and str(record_path) == record['image-path']
             and '..' not in record_path.parts, 'canonical info image path')
        entities = record['system-entities']
        need(all(type(e) is _PlistDict and type(e.get('dev-entry')) is str for e in entities),
             'entity record')
        matching = record['image-path'] == owner['image']['path']
        overlapping = any(e['dev-entry'] in (owner['device'], owner['volumeDevice'])
                          or e.get('mount-point') == owner['mount']['path'] for e in entities)
        if matching:
            selected.append(record)
        else:
            need(not overlapping, 'reused device or mount')
    need(len(selected) == 1, 'unique image association')
    record = selected[0]
    need(str(physical(record['image-path'])) == owner['image']['path'], 'info image path')
    entities = record['system-entities']
    need(len(entities) == 2, 'exact two owned entities required')
    whole = [e for e in entities if e['dev-entry'] == owner['device']]
    volume = [e for e in entities if e['dev-entry'] == owner['volumeDevice']]
    need(len(whole) == len(volume) == 1 and 'mount-point' not in whole[0],
         'whole and volume devices')
    need(volume[0].get('mount-point') == owner['mount']['path'], 'owned mountpoint')
    physical(volume[0]['mount-point'])


def release_owned_image(owner, run, *, now=time.monotonic):
    """Return RESOURCE_RELEASE_ONLY_NOT_ADMISSION, or raise without forced cleanup.

    originalExperiment is retained by identity/type, wholly opaque. Successful
    detach does not change its result or deadline. No command runner is supplied
    implicitly; this module imports no subprocess/native execution mechanism.
    """
    def clock():
        value = now()
        need(type(value) in (int, float) and math.isfinite(value), 'finite release clock')
        return value

    start = clock()
    deadline = start + RELEASE_SECONDS
    need(math.isfinite(deadline) and deadline > start, 'finite release deadline')
    last = start

    def check():
        nonlocal last
        current = clock()
        need(last <= current < deadline, 'release deadline expired or clock regressed')
        last = current

    def invoke(argv):
        check()
        result = run(argv, deadline_monotonic=deadline)
        check()
        keys(result, ('returncode', 'stdout', 'stderr', 'reaped'), 'runner result')
        need(type(result['returncode']) is int, 'returncode integer')
        need(result['reaped'] is True, 'command not reaped')
        for name, limit in (('stdout', STDOUT_LIMIT), ('stderr', STDERR_LIMIT)):
            need(type(result[name]) is bytes and len(result[name]) <= limit, 'bounded ' + name)
        need(result['returncode'] == 0, 'command failed')
        return result

    check()
    validate_owner(owner)
    host_device = mounted_state(owner)
    check()
    info = invoke([TOOL, 'info', '-plist'])
    association(info['stdout'], owner)
    check()
    need(mounted_state(owner) == host_device, 'host parent changed')
    check()
    detached = invoke([TOOL, 'detach', owner['device']])
    image_state(owner)
    tool_state(owner)
    mount = physical(owner['mount']['path'])
    need(mount.is_dir() and mount.stat().st_dev == mount.parent.stat().st_dev == host_device
         and mount.stat().st_dev != owner['mount']['st_dev'], 'post-detach still mounted')
    check()
    return {'scope': 'RESOURCE_RELEASE_ONLY_NOT_ADMISSION',
            'originalExperiment': owner['originalExperiment'],
            'deadline_monotonic': deadline, 'info': info, 'detach': detached,
            'device': owner['device'], 'image': dict(owner['image'])}
