"""Read-only CAS codecs; callers still verify decoded SHA256 and size.

A codec extension is not an origin proof. Ambiguity fails closed even when one
of the two encodings is corrupt; no decoder fallback is permitted.
"""
import contextlib
import gzip
import io
import lzma
import os
from pathlib import Path
import re
import stat


def _stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def _directory(path):
    if path.resolve() != path or not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError('archive directory must be canonical: ' + str(path))


def resolve_blob(archive_root: Path, sha: str) -> Path:
    """Require exactly one canonical, regular, single-link gzip or XZ blob."""
    if not isinstance(sha, str) or re.fullmatch('[0-9a-f]{64}', sha) is None:
        raise ValueError('invalid lowercase SHA256')
    root = Path(archive_root)
    if not root.is_absolute() or root.resolve() != root:
        raise ValueError('archive root must be canonical and absolute')
    for directory in (root, root / 'blobs', root / 'blobs' / sha[:2]):
        _directory(directory)
    found = []
    for suffix in ('.gz', '.xz'):
        path = root / 'blobs' / sha[:2] / (sha + suffix)
        try:
            s = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
            raise ValueError('aliased physical or nonregular archive blob (requires single link): ' + str(path))
        found.append(path)
    if len(found) > 1:
        raise ValueError('ambiguous archive codec: ' + sha)
    if not found:
        raise FileNotFoundError('missing archive blob: ' + sha)
    return found[0]


class _XZReader(io.RawIOBase):
    """Incremental XZ with a fixed dictionary budget and strict trailing bytes.

    LZMAFile silently ignores non-XZ trailing junk. Here every stream must
    decode, including concatenated streams; XZ's four-byte zero padding is legal.
    The 64 MiB dictionary budget accommodates the admitted preset-6 codec.
    """
    def __init__(self, raw):
        super().__init__()
        self.raw = raw
        self.decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=64 * 1024**2)
        self.finished = False

    def readable(self):
        return True

    def readinto(self, target):
        if self.closed:
            raise ValueError('read of closed archive stream')
        if not target or self.finished:
            return 0
        while True:
            if self.decoder.eof:
                data = self.decoder.unused_data
                padding = 0
                while True:
                    if not data:
                        data = self.raw.read(65536)
                        if not data:
                            if padding % 4:
                                raise lzma.LZMAError('invalid XZ stream padding')
                            self.finished = True
                            return 0
                    stripped = data.lstrip(b'\x00')
                    padding += len(data) - len(stripped)
                    data = stripped
                    if data:
                        break
                if padding % 4:
                    raise lzma.LZMAError('invalid XZ stream padding')
                self.decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ,
                                                   memlimit=64 * 1024**2)
            elif self.decoder.needs_input:
                data = self.raw.read(65536)
                if not data:
                    raise EOFError('truncated XZ stream')
            else:
                data = b''
            block = self.decoder.decompress(data, max_length=len(target))
            if self.decoder.check not in (lzma.CHECK_UNKNOWN, lzma.CHECK_CRC64):
                raise lzma.LZMAError('archive XZ stream requires CRC64')
            if block:
                target[:len(block)] = block
                return len(block)


@contextlib.contextmanager
def open_blob(archive_root: Path, sha: str):
    """Yield a streaming binary decoder, owning all descriptors until exit.

    Walk from / using directory descriptors: a parent swap cannot redirect the
    open through a symlink between validation and opening the final member.
    Decoder errors propagate; complete raw identity remains the caller's job.
    """
    path = resolve_blob(archive_root, sha)
    checked = path.lstat()
    if not stat.S_ISREG(checked.st_mode) or checked.st_nlink != 1:
        raise ValueError('archive blob changed to a nonregular or aliased input')
    with contextlib.ExitStack() as stack:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        stack.callback(os.close, fd)
        for part in path.parts[1:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            stack.callback(os.close, fd)
        raw_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        stack.callback(os.close, raw_fd)
        if (resolve_blob(archive_root, sha) != path
                or _stamp(os.fstat(raw_fd)) != _stamp(checked)
                or _stamp(path.lstat()) != _stamp(checked)):
            raise ValueError('archive blob changed before open')
        # ExitStack owns the descriptor even if construction of the buffer fails.
        raw = stack.enter_context(os.fdopen(raw_fd, 'rb', closefd=False))
        magic = raw.read(6)
        raw.seek(0)
        if path.suffix == '.gz' and magic.startswith(b'\x1f\x8b\x08'):
            decoded = gzip.GzipFile(fileobj=raw, mode='rb')
        elif path.suffix == '.xz' and magic == b'\xfd7zXZ\x00':
            decoded = io.BufferedReader(_XZReader(raw))
        else:
            raise ValueError('archive suffix/magic mismatch')
        yield stack.enter_context(decoded)
