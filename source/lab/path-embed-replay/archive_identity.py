"""Physical BSD-ar member witnesses for the captured arm64 Mach-O profile.

Names alone do not identify duplicate archive members. A live external symbol
unique within that duplicate-name group can identify a physical header offset.
This does not attest archive compilation, SDK inputs or execution provenance.
"""
import hashlib
import re
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_artifacts import link_map_objects


def require(value, message):
    if not value:
        raise ValueError(message)


def members(data):
    require(type(data) is bytes and data.startswith(b'!<arch>\n'), 'BSD archive required')
    result, offset = [], 8
    while offset < len(data):
        header = data[offset:offset + 60]
        require(len(header) == 60 and header[58:] == b'`\n', 'archive header')
        size_text = header[48:58].strip()
        require(size_text.isdigit(), 'archive member size')
        size = int(size_text)
        end = offset + 60 + size
        require(end <= len(data), 'truncated archive member')
        name, body = header[:16].rstrip(), data[offset + 60:end]
        if name.startswith(b'#1/'):
            length_text = name[3:]
            require(length_text.isdigit(), 'BSD long name length')
            length = int(length_text)
            require(0 < length <= len(body), 'BSD long name bounds')
            name, body = body[:length].rstrip(b'\0'), body[length:]
        else:
            require(not name.startswith(b'/'), 'GNU archive name table unsupported')
            name = name.removesuffix(b'/')
        require(name and b'\0' not in name and b'/' not in name, 'archive member name')
        result.append({'name': name, 'offset': offset, 'body': body,
                       'sha256': hashlib.sha256(body).hexdigest()})
        if size % 2:
            require(data[end:end + 1] == b'\n', 'archive alignment padding')
        offset = end + size % 2
    require(offset == len(data), 'archive extent')
    return result


def arm64_archive_members(data):
    """Select the exact arm64/subtype-zero slice declared by this link profile.

    Driver-injected compiler-rt is a universal archive, unlike the configured
    third-party archives. Never ask host `ar` to silently choose an architecture.
    Other fat formats or fallback subtypes remain unsupported, not equivalent.
    """
    if type(data) is bytes and data.startswith(b'!<arch>\n'):
        return members(data)
    require(type(data) is bytes and len(data) >= 8, 'fat archive header')
    magic, count = struct.unpack_from('>II', data)
    require(magic == 0xcafebabe and 0 < count <= (len(data) - 8) // 20,
            'bounded big-endian FAT32 archive required')
    extents, chosen = [], []
    for i in range(count):
        cpu, subtype, offset, size, alignment = struct.unpack_from('>iiIII', data, 8 + i * 20)
        require(alignment <= 31 and offset % (1 << alignment) == 0
                and offset >= 8 + count * 20 and size > 0 and offset + size <= len(data),
                'fat archive slice bounds/alignment')
        require(all(offset + size <= start or offset >= end for start, end in extents),
                'overlapping fat archive slices')
        extents.append((offset, offset + size))
        if (cpu, subtype) == (0x0100000c, 0):
            chosen.append((offset, size))
    require(len(chosen) == 1, 'one exact arm64 subtype-zero slice required')
    offset, size = chosen[0]
    result = members(data[offset:offset + size])
    return [dict(m, offset=m['offset'] + offset) for m in result]


def external_definitions(data):
    require(type(data) is bytes and len(data) >= 32, 'Mach-O header')
    magic, cpu, subtype, kind, count, size, _, _ = struct.unpack_from('<IiiIIIII', data)
    require((magic, cpu, subtype, kind) == (0xfeedfacf, 0x0100000c, 0, 1),
            'only thin little-endian arm64 MH_OBJECT is supported')
    end = 32 + size
    require(end <= len(data) and count <= size // 8, 'Mach-O command extent')
    offset, tables = 32, []
    for _ in range(count):
        require(offset + 8 <= end, 'Mach-O command header')
        command, length = struct.unpack_from('<II', data, offset)
        require(length >= 8 and length % 8 == 0 and offset + length <= end,
                'Mach-O command bounds')
        if command == 2:  # LC_SYMTAB
            require(length == 24, 'LC_SYMTAB size')
            tables.append(struct.unpack_from('<IIII', data, offset + 8))
        offset += length
    require(offset == end and len(tables) == 1, 'one bounded symbol table required')
    symbols, count, strings, length = tables[0]
    require(symbols >= end and symbols + count * 16 <= len(data)
            and strings >= symbols + count * 16 and strings + length <= len(data),
            'Mach-O symbol/string table extent')
    result = set()
    for i in range(count):
        index, kind, _, _, _ = struct.unpack_from('<IBBHQ', data, symbols + i * 16)
        require(index < length, 'symbol string index')
        stop = data.find(b'\0', strings + index, strings + length)
        require(stop >= 0, 'unterminated symbol name')
        if not kind & 0xe0 and kind & 1:
            require((kind & 0x0e) != 0x0a, 'indirect definitions unsupported')
            if (kind & 0x0e) in (2, 14):
                name = data[strings + index:stop]
                require(bool(name), 'empty external definition')
                result.add(name)
    return result


def duplicate_witnesses(archive, map_data, archive_path, name):
    """Require a unique live-definition owner for every duplicated map entry."""
    candidates = [m for m in members(archive) if m['name'] == name]
    require(len(candidates) > 1, 'duplicate-name archive group required')
    definitions = {m['offset']: external_definitions(m['body']) for m in candidates}
    link_map_objects(map_data)  # Shared validation; never decode symbol bytes.
    lines = map_data.splitlines()
    begin = lines.index(b'# Object files:') + 1
    origin = archive_path + b'(' + name + b')'
    indices = []
    for line in lines[begin:]:
        if line.startswith(b'#'):
            break
        match = re.fullmatch(rb'\[\s*([0-9]+)\]\s+(.+)', line)
        if match and match[2] == origin:
            indices.append(int(match[1]))
    require(bool(indices), 'duplicate-name map entries required')
    require(lines.count(b'# Symbols:') == 1, 'one live symbol table required')
    observed = {i: set() for i in indices}
    for line in lines[lines.index(b'# Symbols:') + 1:]:
        if line.startswith(b'# Address'):
            continue
        if line.startswith(b'#'):
            break
        match = re.fullmatch(rb'0x[0-9A-Fa-f]+\s+0x[0-9A-Fa-f]+\s+\[\s*([0-9]+)\]\s+(.+)', line)
        require(match is not None or not line.strip(), 'malformed live symbol row')
        if match and int(match[1]) in observed:
            observed[int(match[1])].add(match[2])
    result, assigned = [], set()
    for index, symbols in observed.items():
        witnesses = {}
        for symbol in sorted(symbols):
            owners = [offset for offset, names in definitions.items() if symbol in names]
            if len(owners) == 1:
                witnesses.setdefault(owners[0], symbol)
        require(len(witnesses) == 1, 'missing or contradictory unique symbol witness')
        offset, symbol = next(iter(witnesses.items()))
        require(offset not in assigned, 'physical member assigned twice')
        assigned.add(offset)
        member = next(m for m in candidates if m['offset'] == offset)
        result.append({'object_index': index, 'member_offset': offset,
                       'member_sha256': member['sha256'], 'symbol': symbol})
    return result
