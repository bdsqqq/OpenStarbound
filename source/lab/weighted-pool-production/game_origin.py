"""Read-only, finite arm64 code-identity witnesses; never executes a native tool.

Relocation contract: Apple's mach-o/arm64/reloc.h (SDK) and A64 instruction
encodings. Only immediate bits for BRANCH26, PAGE21 and PAGEOFF12 are variable.
Local TLVP LDR-to-ADD uses the independently sourced Apple ld64 rule below.
Other GOT relaxation, subtractors and pointer fixups remain unsupported.
This is emitted-code identity, not compilation provenance or semantic equivalence.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
_spec = importlib.util.spec_from_file_location('game_origin_archive', LAB / 'path-embed-replay/archive_identity.py')
_archive = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_archive)


def require(ok, message):
    if not ok:
        raise ValueError(message)


class UnsupportedRelocation(ValueError):
    """Preserve the offending bytes without counting them as a successful witness."""
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bounded(data, offset, size, label):
    require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset, label + ' bounds')
    return data[offset:offset + size]


class MachO:
    """Strict thin arm64/subtype-zero object or executable, byte names preserved."""
    def __init__(self, data):
        self.data = data
        bounded(data, 0, 32, 'Mach-O header')
        magic, cpu, sub, self.kind, count, size, flags, reserved = struct.unpack_from('<IiiIIIII', data)
        require((magic, cpu, sub) == (0xfeedfacf, 0x100000c, 0) and self.kind in (1, 2), 'thin arm64 object/executable required')
        end = 32 + size
        bounded(data, 32, size, 'load commands')
        require(count <= size // 8, 'command count')
        self.sections, tables, dynamic_tables = [], [], []
        off = 32
        for _ in range(count):
            require(off + 8 <= end, 'command header bounds')
            cmd, length = struct.unpack_from('<II', data, off)
            require(length >= 8 and length % 8 == 0 and off + length <= end, 'command bounds')
            if cmd == 0x19:  # LC_SEGMENT_64
                require(length >= 72, 'segment size')
                nsects = struct.unpack_from('<I', data, off + 64)[0]
                require(length == 72 + nsects * 80, 'section table size')
                for i in range(nsects):
                    p = off + 72 + i * 80
                    name, seg, addr, extent, fileoff, align, reloc, nr, sf, r1, r2, r3 = struct.unpack_from('<16s16sQQIIIIIIII', data, p)
                    require(align <= 31, 'section alignment')
                    if sf & 0xff not in (1, 0xc, 0x12):
                        require(extent == 0 or fileoff >= end, 'section overlaps Mach-O commands')
                        bounded(data, fileoff, extent, 'section data')
                    require(nr == 0 or reloc >= end, 'relocations overlap Mach-O commands')
                    bounded(data, reloc, nr * 8, 'relocations')
                    self.sections.append(dict(name=name.rstrip(b'\0'), segment=seg.rstrip(b'\0'), address=addr,
                                              size=extent, offset=fileoff, reloc=reloc, nreloc=nr, flags=sf,
                                              reserved1=r1, reserved2=r2))
            elif cmd == 0xb:  # LC_DYSYMTAB: indirect symbols bind stubs to names.
                require(length == 80, 'dynamic symbol command size')
                dynamic_tables.append(struct.unpack_from('<II', data, off + 56))
            elif cmd == 2:
                require(length == 24, 'symbol command size')
                tables.append(struct.unpack_from('<IIII', data, off + 8))
            off += length
        require(off == end and len(tables) == 1, 'one symbol table required')
        symoff, nsym, stroff, strsize = tables[0]
        require(symoff >= end and stroff >= symoff + nsym * 16, 'symbol table ordering')
        bounded(data, symoff, nsym * 16, 'symbols')
        strings = bounded(data, stroff, strsize, 'strings')
        self.symbols = []
        for i in range(nsym):
            index, typ, sect, desc, value = struct.unpack_from('<IBBHQ', data, symoff + i * 16)
            require(index < strsize, 'symbol string index')
            stop = strings.find(b'\0', index)
            require(stop >= 0, 'symbol termination')
            if not typ & 0xe0 and typ & 0xe == 0xe:
                require(0 < sect <= len(self.sections), 'symbol section')
                # Linker-created header symbols need not lie inside their n_sect.
                # Validate address ownership only when consuming a code symbol.
            self.symbols.append(dict(name=strings[index:stop], type=typ, section=sect, value=value, index=i))
        require(len(dynamic_tables) <= 1, 'duplicate dynamic symbol table')
        self.stubs = {}
        if dynamic_tables:
            indirectoff, indirectcount = dynamic_tables[0]
            bounded(data, indirectoff, indirectcount * 4, 'indirect symbols')
            for sec in self.sections:
                if sec['flags'] & 0xff != 8:  # S_SYMBOL_STUBS
                    continue
                stride, first = sec['reserved2'], sec['reserved1']
                require(stride > 0 and sec['size'] % stride == 0, 'stub stride')
                count = sec['size'] // stride
                require(first + count <= indirectcount, 'stub indirect bounds')
                for i in range(count):
                    index = struct.unpack_from('<I', data, indirectoff + 4 * (first + i))[0]
                    require(index < len(self.symbols), 'stub symbol index')
                    self.stubs.setdefault(self.symbols[index]['name'], []).append(sec['address'] + i * stride)

    def branch_target(self, name):
        values = [s['value'] for s in self.definitions(name)] + self.stubs.get(name, [])
        require(len(values) == 1, 'one direct or indirect-stub branch target required: ' + repr(name))
        return values[0]

    def definitions(self, name):
        return [s for s in self.symbols if s['name'] == name and not s['type'] & 0xe0 and s['type'] & 0xe == 0xe]

    def function(self, name):
        matches = self.definitions(name)
        require(len(matches) == 1, 'one exact function definition required: ' + repr(name))
        symbol = matches[0]
        sec = self.sections[symbol['section'] - 1]
        require(sec['name'] == b'__text' and sec['flags'] & 0x80000000, 'instruction text required')
        start = symbol['value']
        require(sec['address'] <= start < sec['address'] + sec['size'], 'function symbol address bounds')
        aliases = [s for s in self.symbols if not s['type'] & 0xe0 and s['type'] & 0xe == 0xe
                   and s['section'] == symbol['section'] and s['value'] == start]
        require(len(aliases) == 1, 'ambiguous folded/aliased function')
        ends = [s['value'] for s in self.symbols if not s['type'] & 0xe0 and s['type'] & 0xe == 0xe
                and s['section'] == symbol['section'] and s['value'] > start]
        end = min(ends, default=sec['address'] + sec['size'])
        require(start % 4 == 0 and start < end <= sec['address'] + sec['size'] and (end - start) % 4 == 0, 'function extent/alignment')
        begin = start - sec['address']
        return dict(symbol=symbol, section=sec, start=start, end=end,
                    code=bounded(self.data, sec['offset'] + begin, end - start, 'function'))

    def relocations(self, function):
        sec = function['section']
        result = []
        for i in range(sec['nreloc']):
            address, word = struct.unpack_from('<iI', self.data, sec['reloc'] + i * 8)
            require(0 <= address < sec['size'], 'relocation section bounds/scattered unsupported')
            symbol, pcrel, length, external, typ = word & 0xffffff, (word >> 24) & 1, (word >> 25) & 3, (word >> 27) & 1, word >> 28
            require((external and symbol < len(self.symbols)) or (not external and (typ == 10 or 0 < symbol <= len(self.sections))), 'relocation target bounds')
            if function['start'] - sec['address'] <= address < function['end'] - sec['address']:
                result.append(dict(offset=address - (function['start'] - sec['address']), type=typ,
                                   pcrel=pcrel, length=length, external=external, target=symbol))
        return result


def relocation_mask(word, reloc):
    """Mask only A64 immediate fields; retain opcode, registers and addressing mode."""
    typ = reloc['type']
    require(reloc['length'] == 2 and reloc['external'] == 1, 'unsupported relocation width/local target')
    if typ == 2:
        require(reloc['pcrel'] == 1 and word & 0x7c000000 == 0x14000000, 'BRANCH26 encoding')
        return 0x03ffffff
    if typ in (3, 8):
        require(reloc['pcrel'] == 1 and word & 0x9f000000 == 0x90000000, 'PAGE21 ADRP encoding')
        return 0x60ffffe0
    if typ == 4:
        # ADD (immediate, unshifted) or unsigned-immediate scalar/vector load/store.
        add = word & 0x7fc00000 == 0x11000000
        load_store = word & 0x3b000000 == 0x39000000
        require(reloc['pcrel'] == 0 and (add or load_store), 'PAGEOFF12 encoding')
        return 0x003ffc00
    raise ValueError('unsupported relocation type ' + str(typ) + ' (no relaxation waiver)')


def local_tlvp_lea(obj, image, original, linked, reloc):
    """Apple ld64-951.9 OutputFile.cpp:2185–2200, not a fitted opcode mask.

    https://github.com/apple-oss-distributions/ld64/blob/ld64-951.9/src/ld/OutputFile.cpp
    Source SHA256 885ecee52272d46076af3402af032ee578590165c09355b3675ee76a497cbc2a.
    The same-linkage TLV thunk becomes ADD with the target's byte page offset;
    registers are preserved. Require actual defined TLV descriptors in BOTH
    artifacts and the exact linked instruction, rather than ignoring its opcode.
    """
    require(reloc['length'] == 2 and reloc['external'] == 1 and reloc['pcrel'] == 0,
            'unsupported TLVP relocation width/target')
    require(original & 0xbfc00000 == 0xb9400000 and original & 0x003ffc00 == 0,
            'TLVP zero-addend LDR required')
    target = obj.symbols[reloc['target']]
    require(target['type'] & 0xe == 0xe and target['section'] > 0 and
            obj.sections[target['section'] - 1]['flags'] & 0xff == 0x13,
            'local object TLV descriptor required')
    matches = image.definitions(target['name'])
    require(len(matches) == 1 and matches[0]['section'] > 0 and
            image.sections[matches[0]['section'] - 1]['flags'] & 0xff == 0x13,
            'local linked TLV descriptor required')
    for artifact, symbol in ((obj, target), (image, matches[0])):
        section = artifact.sections[symbol['section'] - 1]
        require(section['address'] <= symbol['value'] and
                symbol['value'] + 24 <= section['address'] + section['size'],
                'complete 24-byte TLV descriptor address bounds')
    expected = 0x91000000 | ((matches[0]['value'] & 0xfff) << 10) | (original & 0x3ff)
    require(linked == expected, 'TLVP ADD target/register/encoding differs')
    return 0x91000000 | (original & 0x3ff)


def compare_function(obj, image, name):
    original, linked = obj.function(name), image.function(name)
    require(len(original['code']) == len(linked['code']), 'function extent differs: ' + repr(name))
    left, right = bytearray(original['code']), bytearray(linked['code'])
    records, seen = [], set()
    for reloc in obj.relocations(original):
        offset = reloc['offset']
        require(offset % 4 == 0 and offset + 4 <= len(left) and offset not in seen, 'overlapping/unaligned relocation')
        seen.add(offset)
        a, b = struct.unpack_from('<I', left, offset)[0], struct.unpack_from('<I', right, offset)[0]
        if reloc['type'] == 9:
            converted = local_tlvp_lea(obj, image, a, b, reloc)
            mask = 0x003ffc00
            struct.pack_into('<I', left, offset, converted)
            struct.pack_into('<I', right, offset, b & ~mask)
            target = obj.symbols[reloc['target']]['name']
            records.append(dict(reloc, target_name_hex=target.hex(), mask=hex(mask),
                                original_word=hex(a), linked_word=hex(b),
                                rule='Apple ld64 local TLVP LDR-to-ADD; exact descriptor page offset/registers',
                                masked_byte_offsets=[offset + i for i in range(4) if mask & (255 << (8 * i))]))
            continue
        if reloc['type'] not in (2, 3, 4, 8):
            raise UnsupportedRelocation('unsupported relocation type ' + str(reloc['type']) + ' (no relaxation waiver)',
                                        dict(reloc, original_word=hex(a), linked_word=hex(b),
                                             target_name_hex=(obj.symbols[reloc['target']]['name'].hex() if reloc['external'] else None)))
        mask = relocation_mask(a, reloc)
        require(a & mask == 0, 'encoded relocation addend unsupported')
        # Validate the linked encoding too: even opcode changes allowed by a linker
        # optimization are a blocker until a separate ABI-derived rule exists.
        require(relocation_mask(b, reloc) == mask, 'linked relocation encoding differs')
        struct.pack_into('<I', left, offset, a & ~mask)
        struct.pack_into('<I', right, offset, b & ~mask)
        target = obj.symbols[reloc['target']]['name']
        if reloc['type'] == 2:
            require(branch_destination(b, linked['start'] + offset) == image.branch_target(target), 'relocated branch target differs: ' + repr(target))
        records.append(dict(reloc, target_name_hex=target.hex(), mask=hex(mask),
                            original_word=hex(a), linked_word=hex(b), masked_byte_offsets=[offset + i for i in range(4) if mask & (255 << (8 * i))]))
    require(left == right, 'nonrelocated instruction/code bytes differ: ' + repr(name))
    return dict(name_hex=name.hex(), address=linked['start'], size=len(left),
                original_code_sha256=sha(original['code']), linked_code_sha256=sha(linked['code']),
                normalized_sha256=sha(left), relocations=records,
                extent_contract='next distinct section nlist symbol, or section end; no padding trimming')


def branch_destination(word, pc):
    require(word & 0x7c000000 == 0x14000000, 'B/BL encoding required')
    imm = word & 0x3ffffff
    if imm & 0x2000000:
        imm -= 1 << 26
    return pc + imm * 4


def call_edges(image, target_name):
    owner_name = b'__ZN4Star22RustWeightedPoolDetail5Frame3runEjj'
    target = image.function(target_name)['start']
    edges = []
    # Exact Itanium C++ spelling from the production Frame::run(uint32_t,uint32_t)
    # contract; do not accept a Rust self-call or arbitrary substring/cold label.
    for symbol in image.definitions(owner_name):
        fun = image.function(symbol['name'])
        for offset in range(0, len(fun['code']), 4):
            word = struct.unpack_from('<I', fun['code'], offset)[0]
            if word & 0x7c000000 != 0x14000000:
                continue
            pc = fun['start'] + offset
            if branch_destination(word, pc) == target:
                edges.append(dict(owner_hex=symbol['name'].hex(), owner_address=fun['start'],
                                  instruction_address=pc, instruction_word=hex(word),
                                  kind='BL' if word & 0x80000000 else 'B', target_address=target))
    require(edges, 'no direct native Star::RustWeightedPoolDetail::Frame::run to exact Rust target')
    return edges


def pinned(path, expected):
    require(len(expected) == 64 and all(c in '0123456789abcdef' for c in expected), 'external lowercase SHA256 required')
    data = Path(path).read_bytes()
    require(sha(data) == expected, 'artifact SHA256 differs: ' + str(path))
    return data


def attest(game, archive):
    names = (b'_sb_wp_run', b'_sb_wp_count', b'_rust_eh_personality')
    image = MachO(game)
    require(image.kind == 2, 'game must be MH_EXECUTE')
    physical = _archive.members(archive)
    providers = {}
    for member in physical:
        if member['body'].startswith(b'\xcf\xfa\xed\xfe'):
            defs = _archive.external_definitions(member['body'])
            for name in names:
                if name in defs:
                    providers.setdefault(name, []).append(member)
    result = dict(schema='weighted-pool-game-origin-v1', game_sha256=sha(game), archive_sha256=sha(archive),
                  archive_entries=len(physical), functions=[], blockers=[],
                  verifier_sha256=sha(Path(__file__).read_bytes()),
                  imported_parser_sha256={str(p.relative_to(LAB)): sha(p.read_bytes()) for p in
                                          (LAB / 'path-embed-replay/archive_identity.py', LAB / 'native_artifacts.py')},
                  relocation_contract='Apple SDK mach-o/arm64/reloc.h; A64 B/BL imm26, ADRP immlo/immhi, ADD/unsigned-load-store imm12; zero addends; Apple ld64-951.9 same-unit TLVP LDR-to-ADD with exact linked descriptor address/registers',
                  limitations=['finite emitted-code identity, not semantic universality',
                               'page relocation target immediates are normalized, not data-object provenance proofs',
                               'native call edges are static encoded B/BL instructions, not dynamic execution traces',
                               'no original link map: code identity does not prove a unique historical linker choice among byte-identical inputs',
                               'nlist extent only; no unwind, inode, alias or universal architecture attestation'])
    for name in names:
        owners = providers.get(name, [])
        try:
            require(len(owners) == 1, 'unique physical canonical archive provider required: ' + repr(name))
            member = owners[0]
            identity = compare_function(MachO(member['body']), image, name)
            identity.update(member_header_offset=member['offset'], member_sha256=member['sha256'], member_name_hex=member['name'].hex())
            result['functions'].append(identity)
        except ValueError as exc:
            blocker = dict(name_hex=name.hex(), reason=str(exc))
            if len(owners) == 1:
                blocker.update(member_header_offset=owners[0]['offset'], member_sha256=owners[0]['sha256'])
            if isinstance(exc, UnsupportedRelocation):
                blocker['unsupported_relocation'] = exc.evidence
            result['blockers'].append(blocker)
    try:
        result['native_call_edges'] = call_edges(image, b'_sb_wp_run')
    except ValueError as exc:
        result['native_call_edges'] = []
        result['blockers'].append(dict(stage='native-call-edge', reason=str(exc)))
    result['complete'] = not result['blockers']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True)
    parser.add_argument('--game-sha256', required=True)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--archive-sha256', required=True)
    args = parser.parse_args()
    def forbid_process(event, args):
        if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.forkpty', 'os.exec', 'pty.spawn'}:
            raise ValueError('read-only game-origin verifier forbids process creation')
    sys.addaudithook(forbid_process)
    result = attest(pinned(args.game, args.game_sha256), pinned(args.archive, args.archive_sha256))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
