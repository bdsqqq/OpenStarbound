"""Bound logical output bytes at one declared path; not an allocation/native quota.

Callers must prohibit concurrent writers and assign finite paths/budgets. Failed
partials are deliberately retained: retry requires explicit conservation, not
another temporary name. Replacement is a checked single-writer protocol, NOT a
race-free compare-and-swap against hostile concurrent writers.
"""
import hashlib
import json
import os
from pathlib import Path
import stat


PIECE_BYTES = 64 * 1024


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _fingerprint(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def _regular(s):
    _need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1,
          'unique ordinary regular file required')


def _path(path):
    raw = os.fspath(path)
    _need(isinstance(raw, str), 'text path required')
    p = Path(raw)
    _need(p.is_absolute() and bool(p.name) and '..' not in p.parts and raw == str(p),
          'absolute canonical path required')
    _parents(p)
    return p


def _parents(p):
    for parent in reversed(p.parents):
        s = parent.lstat()
        _need(stat.S_ISDIR(s.st_mode), 'physical directory required')
    _need(p.parent.resolve(strict=True) == p.parent, 'physical canonical parent required')


def _identity(dfd, name, path, limit):
    """Hash actual bounded bytes, rejecting path/descriptor drift while reading."""
    before = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    _regular(before)
    _need(before.st_size <= limit, 'identity exceeds byte limit')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
    try:
        _need(_fingerprint(os.fstat(fd)) == _fingerprint(before), 'identity open drift')
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(fd, min(PIECE_BYTES, limit - size + 1))
            if not chunk:
                break
            size += len(chunk)
            _need(size <= limit, 'identity exceeds byte limit')
            digest.update(chunk)
        _need(_fingerprint(os.fstat(fd)) == _fingerprint(before), 'identity read drift')
        _need(_fingerprint(os.stat(name, dir_fd=dfd, follow_symlinks=False)) ==
              _fingerprint(before), 'identity path drift')
        _need(size == before.st_size, 'identity size drift')
        return dict(path=str(path), sha256=digest.hexdigest(), size=size), _fingerprint(before)
    finally:
        os.close(fd)


def write_json(path, value, limit_bytes, *, indent=2, separators=None,
               replace_expected=None, newline=True):
    """Write exact legacy JSON bytes within a strict positive integer cap.

    Legacy admission.dump uses indent=2, sort_keys=True and a final newline.
    JSONEncoder may allocate a large string chunk; this bounds disk bytes, NOT
    encoder/object RAM. Every chunk (including newline) is checked before its
    first write. Unbuffered os.write has no userspace buffer to flush; fsync
    persists output before publication. Errors propagate, never imply success.
    """
    _need(type(limit_bytes) is int and limit_bytes > 0, 'positive integer byte limit required')
    _need(type(newline) is bool, 'boolean newline required')

    def chunks():
        encoder = json.JSONEncoder(indent=indent, separators=separators,
                                   sort_keys=True, ensure_ascii=True, allow_nan=False)
        yield from encoder.iterencode(value)
        if newline:
            yield '\n'

    return _write_chunks(path, chunks(), limit_bytes, replace_expected=replace_expected)


def write_bytes(path, raw: bytes, limit_bytes: int):
    """Publish exact bytes exclusively; reject oversize before touching any path.

    The input already occupies RAM; this is a logical disk-byte bound, not a
    bound on producing/encoding the input. Failed partials block fresh retries.
    """
    _need(type(raw) is bytes, 'bytes required')
    _need(type(limit_bytes) is int and limit_bytes > 0, 'positive integer byte limit required')
    _need(len(raw) <= limit_bytes, 'output byte limit exceeded')
    return _write_chunks(path, (raw,), limit_bytes)


def _write_chunks(path, chunks, limit_bytes, *, replace_expected=None):
    """Publish text/byte chunks through one descriptor-checked protocol."""
    p = _path(path)
    partial = '.' + p.name + '.partial'
    dfd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        # Reject even dangling symlinks; do not create a partial for default
        # attempts to overwrite an existing output.
        try:
            current = os.stat(p.name, dir_fd=dfd, follow_symlinks=False)
        except FileNotFoundError:
            current = None
        original = None
        if replace_expected is None:
            _need(current is None, 'destination already exists')
        else:
            _need(type(replace_expected) is dict and set(replace_expected) == {'path', 'sha256', 'size'},
                  'exact replacement identity required')
            _need(replace_expected['path'] == str(p) and
                  type(replace_expected['size']) is int and replace_expected['size'] >= 0 and
                  isinstance(replace_expected['sha256'], str) and
                  len(replace_expected['sha256']) == 64 and
                  all(c in '0123456789abcdef' for c in replace_expected['sha256']),
                  'invalid replacement identity')
            _need(current is not None, 'replacement destination missing')
            observed, original = _identity(dfd, p.name, p, replace_expected['size'])
            _need(observed == replace_expected, 'replacement identity mismatch')
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
        try:
            _regular(os.fstat(fd))
            owner = (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
            size = 0
            digest = hashlib.sha256()

            for chunk in chunks:
                # Scalar JSON is ASCII. Custom indent/separators can contain
                # Unicode: character length is still a safe early rejection,
                # then check exact UTF-8 bytes before any part of this chunk.
                _need(len(chunk) <= limit_bytes - size, 'JSON byte limit exceeded')
                data = chunk.encode('utf-8') if isinstance(chunk, str) else chunk
                _need(len(data) <= limit_bytes - size, 'JSON byte limit exceeded')
                offset = 0
                while offset < len(data):
                    piece = data[offset:offset + PIECE_BYTES]
                    count = os.write(fd, piece)
                    if not 0 < count <= len(piece):
                        raise OSError('invalid/zero write progress')
                    digest.update(piece[:count])
                    size += count
                    offset += count

            os.fsync(fd)
            written = os.fstat(fd)
            _regular(written)
            _need((written.st_dev, written.st_ino) == owner and written.st_size == size,
                  'partial descriptor drift')
            _need(_fingerprint(os.stat(partial, dir_fd=dfd, follow_symlinks=False)) ==
                  _fingerprint(written), 'partial path drift')
            _parents(p)
            _need((p.parent.stat().st_dev, p.parent.stat().st_ino) ==
                  (os.fstat(dfd).st_dev, os.fstat(dfd).st_ino), 'parent directory drift')
            if original is not None:
                observed, fingerprint = _identity(dfd, p.name, p, replace_expected['size'])
                _need(observed == replace_expected and fingerprint == original,
                      'replacement original changed')
                os.replace(partial, p.name, src_dir_fd=dfd, dst_dir_fd=dfd)
            else:
                # link is exclusive: a destination appearing after preflight
                # is preserved, unlike rename/replace.
                os.link(partial, p.name, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)
                os.fsync(dfd)
                linked = os.stat(partial, dir_fd=dfd, follow_symlinks=False)
                _need((linked.st_dev, linked.st_ino) == owner and linked.st_nlink == 2,
                      'published partial ownership drift')
                os.unlink(partial, dir_fd=dfd)
            os.fsync(dfd)
            actual, _ = _identity(dfd, p.name, p, limit_bytes)
            _need(actual == dict(path=str(p), sha256=digest.hexdigest(), size=size),
                  'published bytes differ')
            final = os.stat(p.name, dir_fd=dfd, follow_symlinks=False)
            _need((final.st_dev, final.st_ino) == owner, 'published inode drift')
            _parents(p)
            _need((p.parent.stat().st_dev, p.parent.stat().st_ino) ==
                  (os.fstat(dfd).st_dev, os.fstat(dfd).st_ino), 'published parent drift')
            return actual
        finally:
            os.close(fd)
    finally:
        os.close(dfd)
