"""Offline object/archive inventory only; unresolved origins are NOT accepted."""
from collections import Counter
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_artifacts import link_map_objects


def reconcile(data, expected_objects, archive_tables):
    """Keep SDK reconciliation separate from exact native object membership.

    Callers must derive expected objects and declared archives from the frozen
    link recipe, not the map being checked. Returning an unresolved origin is
    evidence for the next stage, never authorization to ignore it.
    """
    if (type(expected_objects) is not list or not expected_objects
            or any(type(p) is not bytes or not p.endswith(b'.o') for p in expected_objects)
            or len(set(expected_objects)) != len(expected_objects)):
        raise ValueError('nonempty unique byte object paths required')
    if (type(archive_tables) is not dict
            or any(type(p) is not bytes or not p.endswith(b'.a')
                   or type(table) is not bytes for p, table in archive_tables.items())):
        raise ValueError('declared byte archive paths and tables required')
    entries = link_map_objects(data)
    if entries[0] != b'linker synthesized' or entries.count(b'linker synthesized') != 1:
        raise ValueError('one initial linker synthesized entry required')
    objects = [p for p in entries if p.endswith(b'.o')]
    if objects != expected_objects:
        raise ValueError('ordered standalone object membership differs')
    used, unresolved = [], []
    members = {p: Counter(table.splitlines()) for p, table in archive_tables.items()}
    for entry in entries[1:]:
        if entry in objects:
            continue
        archive_member = re.fullmatch(rb'(.+\.a)\(([^()]+)\)', entry)
        if archive_member:
            archive, member = archive_member.groups()
            if archive not in members:
                raise ValueError('undeclared archive')
            if members[archive][member] != 1:
                raise ValueError('missing or ambiguous archive member')
            used.append((archive, member))
        else:
            unresolved.append(entry)
    return {'objects': objects, 'used_archive_members': used, 'unresolved_origins': unresolved}
