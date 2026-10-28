"""Disjoint allocated-byte observation; NEVER a filesystem snapshot or resolver.

Independent global-minus-active walks can attribute deleted active temporaries to
outside storage. Classify each inode directly instead. Concurrent changes remain
possible, so report the observation interval and fail closed on traversal errors.
"""
import datetime as dt
import os
from pathlib import Path
import stat

GIB = 1024 ** 3
CAPS = dict(liveBytes=4 * GIB, archiveBytes=16 * GIB, newRootBytes=1536 * 1024 ** 2)


class AllocationError(ValueError):
    def __init__(self, message, observation):
        super().__init__(message)
        self.observation = observation


def _utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _physical(path):
    if not path.is_absolute() or '..' in path.parts or path.resolve() != path:
        raise ValueError('physical absolute allocation path required: ' + str(path))


def _entries(root):
    """One lstat per observed entry; never traverse symbolic links."""
    stack = [root]
    while stack:
        path = stack.pop()
        info = path.lstat()
        yield path, info
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(path) as children:
                stack.extend(sorted((Path(e.path) for e in children), reverse=True))


def _partition(entries, active, archive):
    counts = dict(archiveBytes=0, activeRootBytes=0, outsideBytes=0,
                  observedEntries=0, uniqueInodes=0, symbolicLinks=0, namedPipes=0)
    seen = {}
    for path, info in entries:
        category = ('archiveBytes' if path.is_relative_to(archive) else
                    'activeRootBytes' if path.is_relative_to(active) else 'outsideBytes')
        counts['observedEntries'] += 1
        kind = stat.S_IFMT(info.st_mode)
        if kind not in (stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK, stat.S_IFIFO):
            raise AllocationError('unsupported allocation entry: ' + str(path), dict(counts, path=str(path)))
        if not hasattr(info, 'st_blocks') or type(info.st_blocks) is not int or info.st_blocks < 0:
            raise AllocationError('allocated block observation unavailable: ' + str(path), counts)
        key = info.st_dev, info.st_ino
        prior = seen.get(key)
        if prior is not None:
            if prior[0] != category:
                raise AllocationError('inode crosses allocation categories',
                                      dict(counts, paths=[str(prior[1]), str(path)], categories=[prior[0], category]))
            continue
        seen[key] = category, path
        counts['uniqueInodes'] += 1
        counts['symbolicLinks'] += int(kind == stat.S_IFLNK)
        # Historical path fixtures include FIFOs. Charge inode blocks without
        # opening/reading them; an allocation observer must never consume IPC.
        counts['namedPipes'] += int(kind == stat.S_IFIFO)
        counts[category] += info.st_blocks * 512
    return counts


def measure(repo, active_root):
    repo, active = Path(repo), Path(active_root)
    _physical(repo); _physical(active)
    build, archive = repo / 'build', repo / 'build/migration-evidence-archive'
    _physical(build); _physical(archive)
    if archive.exists() and not archive.is_dir():
        raise ValueError('archive allocation root is not a directory')
    if not repo.is_dir() or not build.is_dir() or not active.is_relative_to(build) or active == build:
        raise ValueError('active root must be a proper descendant of physical build/')
    if active.is_relative_to(archive) or archive.is_relative_to(active):
        raise ValueError('active and archive categories overlap')
    if active.exists() and not active.is_dir():
        raise ValueError('active allocation root is not a directory')
    started = _utc()
    try:
        counts = _partition(_entries(build), active, archive)
    except (OSError, AllocationError) as error:
        detail = getattr(error, 'observation', {})
        raise AllocationError(str(error), dict(detail, startedUTC=started, finishedUTC=_utc(),
                              complete=False, activeRoot=str(active))) from error
    return dict(counts, startedUTC=started, finishedUTC=_utc(), complete=True,
                activeRoot=str(active), archiveRoot=str(archive),
                liveBytes=counts['outsideBytes'] + counts['activeRootBytes'],
                reservedLiveBytes=counts['outsideBytes'] + CAPS['newRootBytes'],
                limitations=['one direct disjoint traversal, NOT an atomic filesystem snapshot',
                             'symlinks charged as entries; targets never followed',
                             'allocated blocks, not logical sizes; same-category inodes counted once'])


def check(observation):
    """Fixed caps are not caller options. Return evidence or raise with totals."""
    keys = ('archiveBytes', 'activeRootBytes', 'outsideBytes')
    if observation.get('complete') is not True or any(type(observation.get(k)) is not int or observation[k] < 0 for k in keys):
        raise AllocationError('complete nonnegative disjoint observation required', observation)
    archive, active, outside = (observation[k] for k in keys)
    for valid, why in ((archive <= CAPS['archiveBytes'], 'fixed 16 GiB archive cap'),
                       (active <= CAPS['newRootBytes'], 'fixed 1536 MiB active-root cap'),
                       (outside + active <= CAPS['liveBytes'], 'fixed 4 GiB live cap'),
                       (outside + CAPS['newRootBytes'] <= CAPS['liveBytes'], 'unchanged 1536 MiB reservation exceeds live cap')):
        if not valid:
            raise AllocationError(why, observation)
    return observation


def enforce(repo, active_root):
    return check(measure(repo, active_root))
