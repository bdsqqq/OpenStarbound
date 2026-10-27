"""Offline object/archive inventory only; unresolved origins are NOT accepted."""
from collections import Counter
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_artifacts import link_map_objects
from archive_identity import duplicate_witnesses, members as physical_members


def reconcile(data, expected_objects, archive_tables, archive_blobs=None):
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
    if archive_blobs is None:
        archive_blobs = {}
    if (type(archive_blobs) is not dict
            or any(p not in archive_tables or type(blob) is not bytes
                   for p, blob in archive_blobs.items())):
        raise ValueError('physical bytes must belong to declared archives')
    entries = link_map_objects(data)
    if entries[0] != b'linker synthesized' or entries.count(b'linker synthesized') != 1:
        raise ValueError('one initial linker synthesized entry required')
    objects = [p for p in entries if p.endswith(b'.o')]
    if objects != expected_objects:
        raise ValueError('ordered standalone object membership differs')
    used, unresolved, identities = [], [], {}
    members = {p: Counter(table.splitlines()) for p, table in archive_tables.items()}
    for entry in entries[1:]:
        if entry in objects:
            continue
        archive_member = re.fullmatch(rb'(.+\.a)\(([^()]+)\)', entry)
        if archive_member:
            archive, member = archive_member.groups()
            if archive not in members:
                raise ValueError('undeclared archive')
            count = members[archive][member]
            if count != 1:
                if count == 0 or archive not in archive_blobs:
                    raise ValueError('missing or ambiguous archive member')
                key = (archive, member)
                if key not in identities:
                    blob = archive_blobs[archive]
                    if Counter(m['name'] for m in physical_members(blob)) != members[archive]:
                        raise ValueError('physical archive table differs')
                    identities[key] = duplicate_witnesses(blob, data, archive, member)
            used.append((archive, member))
        else:
            unresolved.append(entry)
    return {'objects': objects, 'used_archive_members': used, 'unresolved_origins': unresolved,
            'physical_member_identities': [dict(archive=archive, name=name, **witness)
                                           for (archive, name), witnesses in identities.items()
                                           for witness in witnesses]}
