"""Captured Apple ld -t / -trace_implicit_libraries profile, not a resolver."""
from collections import Counter
import re


def parse(data, expected_objects, archive_tables):
    """Classify every stdout row; caller must bind files and SDK roots separately.

    ld loads objects concurrently, so trace order is NOT command-line order.
    The independently checked map retains ordered standalone object membership.
    Loaded archive members can be dead-stripped and absent from that map; bind
    whole archives and retain this larger read inventory rather than equate it
    with surviving map entries.
    """
    if type(data) is not bytes or type(expected_objects) is not list or not expected_objects:
        raise ValueError('trace bytes and independent nonempty object list required')
    if any(type(p) is not bytes or not p.startswith(b'/') or not p.endswith(b'.o') for p in expected_objects):
        raise ValueError('absolute byte object paths required')
    if len(set(expected_objects)) != len(expected_objects):
        raise ValueError('duplicate expected standalone object')
    if type(archive_tables) is not dict or any(type(p) is not bytes or type(t) is not bytes
                                              for p, t in archive_tables.items()):
        raise ValueError('byte archive paths/tables required')
    objects, members, stubs, indirect = [], [], [], []
    for line in data.splitlines():
        if line.startswith(b'/'):
            if line.endswith(b'.o'):
                objects.append(line)
            elif line.endswith(b'.tbd'):
                stubs.append(line)
            else:
                match = re.fullmatch(rb'(.+\.a)\(([^()]+)\)', line)
                if match is None:
                    raise ValueError('unsupported loaded file origin')
                archive, member = match.groups()
                if archive not in archive_tables:
                    raise ValueError('undeclared loaded archive')
                members.append((archive, member))
        else:
            match = re.fullmatch(rb"indirect library '([^']+)' from file '([^']+)'", line)
            if match is None or not match[1].startswith(b'/') or not match[2].startswith(b'/'):
                raise ValueError('unsupported linker trace record')
            indirect.append({'install_name': match[1], 'source': match[2]})
    if Counter(objects) != Counter(expected_objects):
        raise ValueError('loaded standalone membership differs')
    counts = {archive: Counter(table.splitlines()) for archive, table in archive_tables.items()}
    for (archive, member), count in Counter(members).items():
        if count > counts[archive][member]:
            raise ValueError('loaded archive member missing or overcounted')
    return {'objects': objects, 'archive_members': members, 'sdk_paths': stubs,
            'indirect_declarations': indirect}
