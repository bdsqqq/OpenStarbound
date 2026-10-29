"""Finite current StaticVector AND IdMap archive/code/native-edge relations.

These byte-only primitives never execute a tool or infer dynamic adoption. Native
owners are declared from the ordinary WorldClient/TileSectorArray source route,
not selected retrospectively to make a binary pass. Inlined-away evidence blocks.
"""
import importlib.util
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
LAB = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('_sv_code_primitives', LAB / 'id-map-production/game_origin.py')
tls = load('_sv_tls_data_origin', Path(__file__).with_name('tls_data_origin.py'))
generic = base._generic
MachO = generic.MachO
archive_identity = generic._archive
sha = base.sha
need = base.require
MAX_INPUT_BYTES = base.MAX_INPUT_BYTES
NAMES = (b'_sb_static_vector_run', b'_sb_static_vector_count', b'_sb_idmap_run', b'_sb_idmap_count', b'_rust_eh_personality')
# Itanium fragments from source-defined namespace/classes. Generic unrelated
# StaticVector instantiations are NOT ordinary-consumer evidence.
WORLD_RENDER = b'__ZN4Star11WorldClient6render'
TILE = b'TileSectorArray'
SPLIT = b'SplitRect'
OBSERVER = b'TileSectorArrayObserver'
IDMAP_OWNER = base.OWNER


def strict_compare(obj, image, name, *, map_data=None, physical_objects=None):
    """Retain exact generic code checks AND bind direct page data destinations.

    The generic primitive normalizes PAGE immediates. That alone does not prove
    data origin. TLVP needs the independent descriptor/template/fixup witness;
    unsupported forms and weak data without a selected physical provider fail closed.
    """
    result = base.strict_compare(obj, image, name)
    original, linked = obj.function(name), image.function(name)
    tls_origins = []
    for reloc in obj.relocations(original):
        typ = reloc['type']
        if typ in (8, 9):
            try:
                proof = tls.attest_tlvp(obj, image, original, linked, reloc,
                                        map_data=map_data, physical_objects=physical_objects)
            except ValueError as exc:
                raise ValueError('UNAVAILABLE_TLVP_DATA_ORIGIN: ' + str(exc)) from exc
            tls_origins.append(dict(instruction_offset=reloc['offset'], relocation_type=typ, proof=proof))
            continue
        if typ not in (3, 4):
            continue
        need(reloc['external'] == 1, 'direct page data target required')
        symbol = obj.symbols[reloc['target']]
        targets = image.definitions(symbol['name'])
        need(len(targets) == 1, 'unique linked page data target')
        target = targets[0]['value']
        offset = reloc['offset']
        word = struct.unpack_from('<I', linked['code'], offset)[0]
        if typ == 3:
            immediate = ((word >> 5) & 0x7ffff) << 2 | ((word >> 29) & 3)
            if immediate & (1 << 20):
                immediate -= 1 << 21
            actual = ((linked['start'] + offset) & ~0xfff) + (immediate << 12)
            need(actual == target & ~0xfff, 'linked PAGE21 actual data target differs')
        else:
            immediate = (word >> 10) & 0xfff
            if word & 0x7fc00000 == 0x11000000:
                actual = immediate
            else:
                need(word & 0x04000000 == 0, 'vector page load requires a separate exact encoding contract')
                actual = immediate << ((word >> 30) & 3)
            need(actual == target & 0xfff, 'linked PAGEOFF12 actual data target differs')
    result['tls_data_origins'] = tls_origins
    return result


def native_symbols(image):
    return [s['name'] for s in image.symbols if s['name'].startswith(b'__ZN')]


def allowed_owner(name, target):
    if target == b'_sb_idmap_run':
        return name == IDMAP_OWNER
    if target == b'_sb_static_vector_run':
        return (name.startswith(WORLD_RENDER) or
                (TILE in name and b'ClientTile' in name and
                 (b'splitRect' in name or b'StaticVector' in name or b'StaticVectorFrames' in name)))
    if target == b'_sb_static_vector_count':
        return name.startswith(WORLD_RENDER) or (OBSERVER in name and any(x in name for x in (b'snapshot', b'Split')))
    return False


def native_edges(image, world_object, *, map_data=None, physical_objects=None):
    """Require actual encoded run/count edges owned by the admitted WorldClient.o.

    Strict comparison also binds the native owner's emitted code, not merely a
    matching symbol string elsewhere. Runtime TLS/callsite association is later.
    """
    result = []
    for target in (NAMES[0], NAMES[1]):
        address = image.function(target)['start']
        found = []
        for name in native_symbols(world_object):
            if not allowed_owner(name, target):
                continue
            owner = image.function(name)
            for offset in range(0, len(owner['code']) - 3, 4):
                word = struct.unpack_from('<I', owner['code'], offset)[0]
                pc = owner['start'] + offset
                if word & 0x7c000000 == 0x14000000 and generic.branch_destination(word, pc) == address:
                    found.append(dict(owner_hex=name.hex(), target_name_hex=target.hex(),
                        instruction_address=pc, instruction_word=hex(word), target_address=address,
                        native_code=strict_compare(world_object, image, name,
                            map_data=map_data, physical_objects=physical_objects)))
        need(found, 'missing ordinary WorldClient object native edge: ' + repr(target))
        result.extend(found)
    # Preserve IdMap's additional exact owner, without invoking its old attest.
    owner = image.function(IDMAP_OWNER)
    target = image.function(b'_sb_idmap_run')['start']
    found = []
    for offset in range(0, len(owner['code']) - 3, 4):
        word = struct.unpack_from('<I', owner['code'], offset)[0]
        pc = owner['start'] + offset
        if word & 0x7c000000 == 0x14000000 and generic.branch_destination(word, pc) == target:
            found.append(dict(owner_hex=IDMAP_OWNER.hex(), target_name_hex=b'_sb_idmap_run'.hex(), instruction_address=pc, instruction_word=hex(word)))
    need(found, 'missing retained IdMap native edge')
    return result + found


def providers(archive):
    """Physical archive enumeration rejects duplicate runtime/export providers."""
    need(type(archive) is bytes and len(archive) <= MAX_INPUT_BYTES, 'bounded archive bytes')
    members = archive_identity.members(archive)
    result = {}
    for name in NAMES:
        owners = [m for m in members if m['body'].startswith(b'\xcf\xfa\xed\xfe') and name in archive_identity.external_definitions(m['body'])]
        need(len(owners) == 1, 'unique physical archive provider: ' + repr(name))
        result[name] = owners[0]
    return result


def seal_archive(archive):
    members = providers(archive)
    return dict(schema='static-vector-prelink-archive-v1', sha256=sha(archive), size=len(archive),
        imported_helper_sha256=base.helper_identities(),
        providers={name.hex(): dict(member_header_offset=m['offset'], member_name_hex=m['name'].hex(), member_sha256=m['sha256']) for name, m in members.items()})


def attest(game, archive, world_object, *, map_data=None, physical_objects=None):
    need(all(type(value) is bytes and len(value) <= MAX_INPUT_BYTES for value in (game, archive, world_object)), 'bounded byte inputs')
    image, world = MachO(game), MachO(world_object)
    need(image.kind == 2 and world.kind == 1, 'MH_EXECUTE game and MH_OBJECT actual WorldClient required')
    owners = providers(archive)
    functions = []
    for name, member in owners.items():
        obj = MachO(member['body'])
        need(obj.kind == 1, 'archive provider must be MH_OBJECT')
        functions.append(dict(strict_compare(obj, image, name, map_data=map_data,
                            physical_objects=physical_objects), member_header_offset=member['offset'], member_sha256=member['sha256']))
    return dict(schema='static-vector-emitted-code-origin-v1', complete=True,
        game_sha256=sha(game), archive=seal_archive(archive), world_object_sha256=sha(world_object),
        functions=functions, native_call_edges=native_edges(image, world, map_data=map_data,
            physical_objects=physical_objects),
        limitations=['finite linked code and static edges; NOT runtime calling-scope adoption',
                     'strict relocation comparison; missing/inlined owners block, no owner fitting'])
