"""Inspect native artifact tables without decoding arbitrary linker symbol bytes."""
import re


def link_map_objects(data: bytes) -> list[bytes]:
    """Read Apple's object table only; symbol names need not be valid UTF-8."""
    if type(data) is not bytes:
        raise TypeError('link map must be bytes')
    lines = data.splitlines()
    if lines.count(b'# Object files:') != 1:
        raise ValueError('one object table required')
    start = lines.index(b'# Object files:') + 1
    objects = []
    indices = set()
    ended = False
    for line in lines[start:]:
        if line.startswith(b'#'):
            ended = True
            break
        if not line.strip():
            continue
        match = re.fullmatch(rb'\[\s*([0-9]+)\]\s+(.+)', line)
        if not match:
            raise ValueError('malformed object entry')
        index = int(match[1])
        if index in indices:
            raise ValueError('duplicate object index')
        indices.add(index)
        objects.append(match[2])
    if not ended or not objects:
        raise ValueError('unterminated or empty object table')
    return objects


def has_archive_member(data: bytes, archive: bytes, member: bytes) -> bool:
    """Match exact basenames, not similarly named archives or loose substrings."""
    for value in (archive, member):
        if type(value) is not bytes or not value or any(c in value for c in (b'/', b'\n', b'\r', b'(', b')')):
            raise ValueError('archive and member must be byte basenames')
    suffix = b'(' + member + b')'
    return any(path.endswith(suffix) and path[:-len(suffix)].rsplit(b'/', 1)[-1] == archive
               for path in link_map_objects(data))


def check_archive_members(table: bytes, expected: list[bytes]) -> None:
    """Compare `ar t` to configured objects, not a provenance binding count.

    Apple's symbol index is metadata, not a native object. Keep its treatment
    explicit so a build profile's headers/libraries cannot become object credit.
    """
    if type(table) is not bytes or type(expected) is not list or not expected:
        raise ValueError('byte archive table and nonempty object list required')
    if any(type(name) is not bytes or not name or b'/' in name or b'\n' in name for name in expected):
        raise ValueError('expected byte object basenames required')
    members = table.splitlines()
    if members and members[0] in (b'__.SYMDEF', b'__.SYMDEF SORTED', b'__.SYMDEF_64', b'__.SYMDEF_64 SORTED'):
        members = members[1:]
    if members != expected:
        raise ValueError('archive object order/content differs from configured objects')
