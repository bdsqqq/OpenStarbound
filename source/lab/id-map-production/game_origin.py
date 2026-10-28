"""Finite IdMap emitted-code witnesses, NOT game/build/source qualification.

Inputs are bytes, never executable paths. This new tool uses the current generic
Mach-O/archive helpers unchanged; historical WeightedPool attestation and owner
selection are deliberately not used. Helper hashes are DATA for future admission,
not source-version substitutions or permission to renew historical receipts.
"""
import importlib.util
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
LAB = Path(__file__).resolve().parents[1]
GENERIC_PATH = LAB / 'weighted-pool-production/game_origin.py'
_spec = importlib.util.spec_from_file_location('id_map_generic_emitted_code', GENERIC_PATH)
_generic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_generic)

NAMES = (b'_sb_idmap_run', b'_sb_idmap_count', b'_rust_eh_personality')
# StarIdMapHost.hpp: Frame::run() directly calls sb_idmap_run. Inlining this
# owner out of a future game is an objection, not permission to fit a new owner.
OWNER = b'__ZN4Star15RustIdMapDetail5Frame3runEv'
MAX_INPUT_BYTES = 128 * 1024 * 1024
require = _generic.require
sha = _generic.sha


def helper_identities():
    """Record actual current imports, including the archive helper's dependency."""
    native = sys.modules['native_artifacts']
    paths = (Path(_generic.__file__), Path(_generic._archive.__file__), Path(native.__file__))
    expected = (GENERIC_PATH, LAB / 'path-embed-replay/archive_identity.py', LAB / 'native_artifacts.py')
    result = {}
    for path, wanted in zip(paths, expected):
        require(path == wanted and path.resolve() == wanted, 'canonical current helper path required')
        result[str(path)] = sha(path.read_bytes())
    return result


def native_edges(image):
    """Only encoded B/BL within the unique exact native function's nlist extent."""
    owner = image.function(OWNER)
    target = image.function(NAMES[0])['start']
    edges = []
    for offset in range(0, len(owner['code']), 4):
        word = struct.unpack_from('<I', owner['code'], offset)[0]
        pc = owner['start'] + offset
        if word & 0x7c000000 == 0x14000000 and _generic.branch_destination(word, pc) == target:
            edges.append(dict(owner_hex=OWNER.hex(), owner_address=owner['start'],
                              owner_end=owner['end'], instruction_address=pc,
                              instruction_word=hex(word), kind='BL' if word & 0x80000000 else 'B',
                              target_name_hex=NAMES[0].hex(), target_address=target))
    require(edges, 'no direct native Star::RustIdMapDetail::Frame::run() to exact sb_idmap_run')
    return edges


def strict_compare(obj, image, name):
    """Preflight before unchanged compare_function, excluding its TLVP waiver.

    The old generic comparer now has an Apple TLVP relaxation rule. IdMap has
    no such admitted rule: type 9, like every other unknown type, remains the
    original generic UnsupportedRelocation with the offending bytes attached.
    """
    original, linked = obj.function(name), image.function(name)
    for reloc in obj.relocations(original):
        if reloc['type'] not in (2, 3, 4, 8):
            offset = reloc['offset']
            require(offset % 4 == 0 and offset + 4 <= len(original['code']),
                    'overlapping/unaligned relocation')
            evidence = dict(reloc, original_word=hex(struct.unpack_from('<I', original['code'], offset)[0]),
                            target_name_hex=(obj.symbols[reloc['target']]['name'].hex()
                                             if reloc['external'] else None))
            if offset + 4 <= len(linked['code']):
                evidence['linked_word'] = hex(struct.unpack_from('<I', linked['code'], offset)[0])
            raise _generic.UnsupportedRelocation(
                'unsupported relocation type ' + str(reloc['type']) + ' (no relaxation waiver)', evidence)
    identity = _generic.compare_function(obj, image, name)
    identity.update(original_address=original['start'], original_end=original['end'],
                    linked_end=linked['end'],
                    member_code_offset=original['section']['offset'] + original['start'] - original['section']['address'],
                    game_code_offset=linked['section']['offset'] + linked['start'] - linked['section']['address'])
    return identity


def attest(game: bytes, archive: bytes) -> dict:
    """Attest only this finite byte relation; malformed/unsupported inputs block.

    A complete result says nothing about original source, compiled headers,
    historical linker choice, selectors, dynamic execution or whole-game origin.
    There is intentionally no path reader/CLI or game-launch capability here.
    """
    result = dict(schema='id-map-emitted-code-origin-v1', complete=False,
                  game_sha256=None, archive_sha256=None, archive_entries=0,
                  functions=[], providers=[], native_call_edges=[], blockers=[],
                  verifier_path=str(Path(__file__).resolve()),
                  verifier_sha256=sha(Path(__file__).read_bytes()), imported_helper_sha256={},
                  relocation_contract='unchanged generic compare_function; only types 2/3/4/8; zero addends; NO TLVP relaxation',
                  limitations=[
                      'finite emitted-code identity only; not semantic equivalence or whole-game qualification',
                      'page relocation data targets are normalized, NOT full data-object provenance',
                      'static encoded native B/BL edge, NOT dynamic execution',
                      'no source, compiled-header, build-selector, SDK, link-admission or original-origin proof',
                      'byte-identical inputs do not prove a unique historical linker choice',
                      'nlist function extents only; no padding trimming, universal architecture or unwind proof'])
    try:
        require(type(game) is bytes and type(archive) is bytes, 'game and archive must be bytes')
        require(len(game) <= MAX_INPUT_BYTES and len(archive) <= MAX_INPUT_BYTES,
                'each input must be at most 128 MiB')
        result.update(game_sha256=sha(game), archive_sha256=sha(archive),
                      imported_helper_sha256=helper_identities())
        image = _generic.MachO(game)
        require(image.kind == 2, 'game must be MH_EXECUTE')
        physical = _generic._archive.members(archive)
        result['archive_entries'] = len(physical)
        providers = {name: [] for name in NAMES}
        for member in physical:
            if member['body'].startswith(b'\xcf\xfa\xed\xfe'):
                definitions = _generic._archive.external_definitions(member['body'])
                for name in NAMES:
                    if name in definitions:
                        providers[name].append(member)
        for name in NAMES:
            owners = providers[name]
            result['providers'].append(dict(name_hex=name.hex(), members=[
                dict(member_header_offset=m['offset'], member_name_hex=m['name'].hex(),
                     member_sha256=m['sha256']) for m in owners]))
            try:
                require(len(owners) == 1, 'unique physical canonical archive provider required: ' + repr(name))
                member = owners[0]
                obj = _generic.MachO(member['body'])
                require(obj.kind == 1, 'provider must be MH_OBJECT')
                # function() separately rejects duplicate definitions and folded
                # aliases in BOTH artifacts, even within a unique member.
                identity = strict_compare(obj, image, name)
                identity.update(member_header_offset=member['offset'], member_sha256=member['sha256'],
                                member_name_hex=member['name'].hex())
                result['functions'].append(identity)
            except ValueError as exc:
                blocker = dict(name_hex=name.hex(), reason=str(exc))
                if isinstance(exc, _generic.UnsupportedRelocation):
                    blocker['unsupported_relocation'] = exc.evidence
                result['blockers'].append(blocker)
        try:
            result['native_call_edges'] = native_edges(image)
        except ValueError as exc:
            result['blockers'].append(dict(stage='native-call-edge', reason=str(exc)))
    except (ValueError, OSError) as exc:
        result['blockers'].append(dict(stage='input', reason=str(exc)))
    result['complete'] = not result['blockers']
    return result
