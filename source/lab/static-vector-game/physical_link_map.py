"""Physical live-map providers, not compiler provenance or weak-definition waivers."""
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

LAB = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves annotations through this entry.
    spec.loader.exec_module(module)
    return module


artifacts = load('_physical_map_artifacts', LAB / 'native_artifacts.py')
_previous = sys.modules.get('native_artifacts')
sys.modules['native_artifacts'] = artifacts
try:
    symbols = load('_physical_map_symbols', LAB / 'native_symbols.py')
    archive = load('_physical_map_archive', LAB / 'path-embed-replay/archive_identity.py')
finally:
    if _previous is None:
        sys.modules.pop('native_artifacts', None)
    else:
        sys.modules['native_artifacts'] = _previous
generic = load('_physical_map_macho', LAB / 'weighted-pool-production/game_origin.py')


def need(value, message):
    if not value:
        raise ValueError(message)


def indexed_objects(map_data: bytes) -> dict[int, bytes]:
    artifacts.link_map_objects(map_data)
    result = {}
    lines = map_data.splitlines()
    for line in lines[lines.index(b'# Object files:') + 1:]:
        if line.startswith(b'#'):
            break
        if line.strip():
            match = re.fullmatch(rb'\[\s*([0-9]+)\]\s+(.+)', line)
            result[int(match[1])] = match[2]
    return result


def resolve_archive_group(archive_data: bytes, map_data: bytes, archive_path: bytes,
                          member_name: bytes) -> dict[int, dict]:
    candidates = [m for m in archive.arm64_archive_members(archive_data) if m['name'] == member_name]
    need(candidates, 'physical archive member required')
    origin = archive_path + b'(' + member_name + b')'
    indices = [i for i, path in indexed_objects(map_data).items() if path == origin]
    need(indices, 'exact archive map entries required')
    live = symbols.live_symbols(map_data)
    definitions = {m['offset']: archive.external_definitions(m['body']) for m in candidates}
    if len(candidates) == 1:
        need(len(indices) == 1, 'single physical member requires one map index')
    result, assigned = {}, set()
    for index in indices:
        names = {s.name for s in live if s.object_index == index}
        unique = {name: [m['offset'] for m in candidates if name in definitions[m['offset']]] for name in names}
        witnesses = {name: owners[0] for name, owners in unique.items() if len(owners) == 1}
        if len(candidates) > 1:
            need(witnesses and len(set(witnesses.values())) == 1,
                 'missing or contradictory unique live external witness')
            offset = next(iter(witnesses.values()))
        else:
            offset = candidates[0]['offset']
        need(offset not in assigned, 'physical archive member assigned twice')
        # Shared external names are constraints too, not just unique witnesses.
        need(all(not owners or offset in owners for owners in unique.values()),
             'live external definition absent from selected member')
        assigned.add(offset)
        member = next(m for m in candidates if m['offset'] == offset)
        result[index] = dict(member_header_offset=offset, member_name_hex=member_name.hex(),
                             member_sha256=member['sha256'], witnesses=sorted(n.hex() for n in witnesses))
    return result


def selected_definition(map_data: bytes, image, objects: dict[int, bytes], name: bytes) -> dict:
    # Reparse concrete bytes: duck-typed definition mocks are not evidence.
    need(type(getattr(image, 'data', None)) is bytes, 'concrete Mach-O image bytes required')
    image = generic.MachO(image.data)
    need(image.kind == 2, 'MH_EXECUTE image required')
    row = symbols.unique_symbol(symbols.live_symbols(map_data), name)
    need(row.object_index in objects and type(objects[row.object_index]) is bytes,
         'selected map index lacks physical object bytes')
    data = objects[row.object_index]
    obj = generic.MachO(data)
    need(obj.kind == 1, 'selected provider must be MH_OBJECT')
    linked, original = image.definitions(name), obj.definitions(name)
    need(len(linked) == len(original) == 1, 'unique image/object N_SECT definition required')
    need(linked[0]['value'] == row.address and row.size > 0, 'map address/positive span differs')
    sections = []
    for artifact, symbol in ((image, linked[0]), (obj, original[0])):
        section = artifact.sections[symbol['section'] - 1]
        start = symbol['value']
        ends = [s['value'] for s in artifact.symbols if not s['type'] & 0xe0
                and s['type'] & 0xe == 0xe and s['section'] == symbol['section'] and s['value'] > start]
        end = min(ends, default=section['address'] + section['size'])
        need(section['address'] <= start < start + row.size <= end <= section['address'] + section['size'],
             'selected symbol span exceeds symbol/section')
        sections.append((section['segment'], section['name'], section['flags'] & 0xff))
    need(sections[0] == sections[1], 'selected object/image section kind differs')
    return dict(object=obj, binding=dict(object_index=row.object_index, object_path_hex=row.object_path.hex(),
        object_sha256=hashlib.sha256(data).hexdigest(), map_sha256=hashlib.sha256(map_data).hexdigest(),
        symbol_name_hex=name.hex(), address=row.address,
        size=row.size, image_sha256=hashlib.sha256(image.data).hexdigest()))
