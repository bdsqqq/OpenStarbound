"""Finite, read-only TLS data witness; deliberately NOT a general dyld reader.

Format references (not claims about the compiler/linker which made an artifact):
* /Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk/usr/include/
  mach-o/loader.h:546-550 (section types),1653-1661 (thunk/key/offset),
  1380-1540 (dyld_info_command/BIND_OPCODE_*). SHA256:
  5862aeb7fbf183453080bc887c0d502fe25a86ff5bd81291bbcc408bd7fe6e74
* same installed SDK mach-o/arm64/reloc.h:27-89 (UNSIGNED/TLVP), SHA256:
  76d1ba5e3cde0526e2dfb38a5458db3f0405319ed5b65c8bc470d021e6467a6e
* Apple ld64-951.9 src/ld/OutputFile.cpp:520-548,1751-1758: descriptor
  target offsets are relative to the FIRST TLS template section, not pointers.
  https://github.com/apple-oss-distributions/ld64/blob/ld64-951.9/src/ld/OutputFile.cpp
  source SHA256 885ecee52272d46076af3402af032ee578590165c09355b3675ee76a497cbc2a
  (existing read-only source at build/weighted-pool-game-admission-r1/).

Supported subset: descriptor arrays, named nlist-bounded TLS data spans,
external UNSIGNED64 zero-addend object fields, and either one explicit classic
bind or fully enumerated format6 chains (see tls_chained_fixups.py). Template
spans use the next distinct nlist symbol/section end, not an invented atom size.
External N_WEAK_DEF data requires a concrete selected map/index/object witness,
matching reference/provider initial state, and same-provider weak backing. Other
symbol flags and relocations within a backing span reject. Unknown forms fail
closed. This does
not prove runtime dyld resolution or whole-source/game provenance.
"""
import hashlib
import importlib.util
from pathlib import Path
import struct

_chain_spec = importlib.util.spec_from_file_location(
    'tls_origin_chained', Path(__file__).with_name('tls_chained_fixups.py'))
_chain = importlib.util.module_from_spec(_chain_spec)
_chain_spec.loader.exec_module(_chain)
_provider_spec = importlib.util.spec_from_file_location(
    'tls_physical_provider', Path(__file__).with_name('physical_link_map.py'))
_provider = importlib.util.module_from_spec(_provider_spec)
_provider_spec.loader.exec_module(_provider)

_spec = importlib.util.spec_from_file_location(
    'tls_origin_generic', Path(__file__).resolve().parents[1] /
    'weighted-pool-production/game_origin.py')
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
MachO = _base.MachO
require = _base.require
bounded = _base.bounded
BOOTSTRAP = b'__tlv_bootstrap'
LIBSYSTEM = b'/usr/lib/libSystem.B.dylib'


def _commands(m):
    off = 32
    count = struct.unpack_from('<I', m.data, 16)[0]
    for _ in range(count):
        cmd, size = struct.unpack_from('<II', m.data, off)
        yield cmd, off, size
        off += size


def _desc(m, symbol):
    # Generic MachO retains all nlist entries in their original order.
    symcmd = [p for c, p, _ in _commands(m) if c == 2]
    symoff = struct.unpack_from('<I', m.data, symcmd[0] + 8)[0]
    return struct.unpack_from('<H', m.data, symoff + 16 * symbol['index'] + 6)[0]


def _definition(m, name, allow_weak=False):
    matches = m.definitions(name)
    require(len(matches) == 1 and sum(s['name'] == name for s in m.symbols) == 1,
            'unique exact TLS definition/name required')
    symbol = matches[0]
    flags = _desc(m, symbol)
    require(flags == 0 or (allow_weak and flags == 0x80 and symbol['type'] & 1),
            'TLS definition flags unsupported or weak provider unbound')
    return symbol


def _section_bytes(m, sec):
    if sec['flags'] & 0xff == 0x12:
        # No allocation proportional to untrusted zero-fill extent.
        return None
    return bounded(m.data, sec['offset'], sec['size'], 'TLS bytes')


def _layout(m):
    require(m.kind in (1, 2), 'object/executable required')
    secs = m.sections
    # Metadata must not double as section content or another metadata table.
    # The generic parser already bounds these ranges; this adds disjointness.
    command_end = 32 + struct.unpack_from('<I', m.data, 20)[0]
    ranges = [(0, command_end, 'commands')]
    for cmd, p, _ in _commands(m):
        if cmd == 2:
            so, sn, st, ss = struct.unpack_from('<4I', m.data, p + 8)
            ranges.extend([(so, sn * 16, 'symbols'), (st, ss, 'strings')])
        elif cmd == 0xb:
            io, count = struct.unpack_from('<2I', m.data, p + 56)
            ranges.append((io, count * 4, 'indirect symbols'))
    for sec in secs:
        if sec['flags'] & 0xff not in (1, 0xc, 0x12):
            ranges.append((sec['offset'], sec['size'], 'section data'))
        ranges.append((sec['reloc'], sec['nreloc'] * 8, 'section relocations'))
    for i, (start, size, label) in enumerate(ranges):
        for other, extent, other_label in ranges[i + 1:]:
            require(not (size and extent and max(start, other) < min(start + size, other + extent)),
                    'overlapping ' + label + '/' + other_label)
    for i, a in enumerate(secs):
        require(a['size'] < 1 << 32 and a['address'] + a['size'] <= 1 << 64,
                'finite section extent required')
        for b in secs[i + 1:]:
            require(not (a['size'] and b['size'] and
                         max(a['address'], b['address']) <
                         min(a['address'] + a['size'], b['address'] + b['size'])),
                    'overlapping section virtual extents')
            if a['flags'] & 0xff not in (1, 0xc, 0x12) and b['flags'] & 0xff not in (1, 0xc, 0x12):
                require(not (a['size'] and b['size'] and
                             max(a['offset'], b['offset']) <
                             min(a['offset'] + a['size'], b['offset'] + b['size'])),
                        'overlapping section file extents')
    descriptors = [s for s in secs if s['flags'] & 0xff == 0x13]
    templates = [s for s in secs if s['flags'] & 0xff in (0x11, 0x12)]
    require(descriptors and templates, 'descriptor and TLS template sections required')
    # MH_OBJECT n_addr values are relocatable section coordinates, not loaded
    # pointer addresses. Only the executable's actual descriptor needs runtime
    # alignment; both artifacts retain complete, entry-relative descriptor spans.
    require(all(d['size'] and d['size'] % 24 == 0 and
                (m.kind == 1 or d['address'] % 8 == 0) for d in descriptors),
            'complete runtime-aligned descriptor array required')
    require(all(t['size'] > 0 for t in templates), 'nonempty TLS templates required')
    require([t['address'] for t in templates] == sorted(t['address'] for t in templates),
            'TLS template section order must match VM order')
    if m.kind == 2:
        require(all(s['nreloc'] == 0 for s in secs), 'linked section relocations unsupported')
    return descriptors, templates


def _symbol_span(m, name, kinds, descriptor=False, allow_weak=False):
    s = _definition(m, name, allow_weak=allow_weak)
    sec = m.sections[s['section'] - 1]
    require(sec['flags'] & 255 in kinds and sec['address'] <= s['value'] < sec['address'] + sec['size'],
            'TLS symbol section/address bounds')
    occupants = [x for x in m.symbols if not x['type'] & 0xe0 and
                 x['type'] & 0xe == 0xe and x['section'] == s['section']]
    require(all(sec['address'] <= x['value'] < sec['address'] + sec['size'] for x in occupants),
            'TLS section symbol extent bounds')
    require(sum(x['value'] == s['value'] for x in occupants) == 1, 'aliased TLS symbol')
    ends = [x['value'] for x in occupants if x['value'] > s['value']]
    end = min(ends, default=sec['address'] + sec['size'])
    if descriptor:
        require((s['value'] - sec['address']) % 24 == 0 and s['value'] + 24 <= end,
                'complete unaliased descriptor entry required')
        end = s['value'] + 24
    span = dict(sec, address=s['value'], offset=sec['offset'] + s['value'] - sec['address'],
                size=end - s['value'])
    return s, sec, span


def _span_relocs(m, sec, span):
    rs = m.relocations(dict(section=sec, start=sec['address'], end=sec['address'] + sec['size']))
    selected = []
    lo, hi = span['address'] - sec['address'], span['address'] - sec['address'] + span['size']
    for r in rs:
        start, end = r['offset'], r['offset'] + (1 << r['length'])
        if max(start, lo) < min(end, hi):
            require(lo <= start and end <= hi, 'relocation straddles TLS span')
            selected.append(dict(r, offset=start - lo))
    return selected


def _object_fields(m, d, sec):
    rs = _span_relocs(m, sec, d)
    require(len(rs) == 2 and sorted(r['offset'] for r in rs) == [0, 16],
            'descriptor needs exactly thunk and offset relocations; key must have none')
    fields = {}
    for r in rs:
        require((r['type'], r['pcrel'], r['length'], r['external']) == (0, 0, 3, 1),
                'only external UNSIGNED64 descriptor fields supported')
        fields[r['offset']] = m.symbols[r['target']]
    require(_section_bytes(m, d) == bytes(24), 'descriptor zero-addend/key prelaunch state required')
    thunk = fields[0]
    require(thunk['name'] == BOOTSTRAP and thunk['type'] == 1 and thunk['section'] == 0 and
            thunk['value'] == 0 and _desc(m, thunk) == 0,
            'object bootstrap must be plain undefined external')
    require(sum(s['name'] == BOOTSTRAP for s in m.symbols) == 1, 'duplicate bootstrap symbol')
    return fields[16]


def _uleb(data, p):
    start, value = p, 0
    for shift in range(0, 70, 7):
        require(p < len(data), 'truncated ULEB')
        byte = data[p]
        p += 1
        require(shift < 63 or byte <= 1, 'ULEB overflow')
        value |= (byte & 127) << shift
        if not byte & 128:
            require(p == start + 1 or byte != 0, 'noncanonical ULEB')
            return value, p
    raise ValueError('ULEB overflow')


def _classic_bind(m, d):
    """Accept one explicit bind tuple, not partially interpreted arbitrary opcodes.

    loader.h dyld_info_command defines (segment,offset,type,ordinal,name,addend).
    Every column is explicit here. Other streams must be empty, so an ignored
    rebase/weak/lazy/chained fixup cannot overwrite key, offset or backing data.
    """
    infos, segments, libraries = [], [], []
    for cmd, p, size in _commands(m):
        # This finite classic subset has no side-table/export-trie contract.
        # Reject such commands rather than treating their byte ranges as free
        # space for a bind stream or TLS template.
        require(cmd in (0x19, 2, 0xc, 0x80000018, 0x8000001f, 0x20, 0x80000023,
                        0x22, 0x80000022), 'unsupported classic load-command metadata')
        if cmd == 0x19:
            name, vm, extent, fileoff, filesz = struct.unpack_from('<16sQQQQ', m.data, p + 8)
            bounded(m.data, fileoff, filesz, 'segment file range')
            require(filesz <= extent and vm + extent <= 1 << 64, 'segment file extent')
            segments.append((name.rstrip(b'\0'), vm, extent, fileoff, filesz))
        elif cmd in (0xc, 0x18 | 0x80000000, 0x1f | 0x80000000, 0x20, 0x23 | 0x80000000):
            require(size >= 24, 'dylib command size')
            n = struct.unpack_from('<I', m.data, p + 8)[0]
            require(24 <= n < size, 'dylib name bounds')
            raw = bounded(m.data, p + n, size - n, 'dylib name')
            require(b'\0' in raw, 'unterminated dylib name')
            libraries.append((cmd, raw.split(b'\0', 1)[0]))
        elif cmd in (0x22, 0x80000022):
            require(size == 48, 'dyld info size')
            infos.append(struct.unpack_from('<10I', m.data, p + 8))
    require(len(infos) == 1, 'exactly one classic dyld info required')
    require(struct.unpack_from('<I', m.data, 24)[0] & 0x100 == 0,
            'forced flat namespace unsupported')
    for i, a in enumerate(segments):
        for b in segments[i + 1:]:
            require(not (a[2] and b[2] and max(a[1], b[1]) < min(a[1] + a[2], b[1] + b[2])),
                    'overlapping segments')
    for sec in m.sections:
        owners = [s for s in segments if s[0] == sec['segment'] and
                  s[1] <= sec['address'] and sec['address'] + sec['size'] <= s[1] + s[2]]
        require(len(owners) == 1, 'unique section segment owner required')
        s = owners[0]
        if sec['flags'] & 0xff not in (1, 0xc, 0x12):
            require(sec['offset'] == s[3] + sec['address'] - s[1] and
                    sec['offset'] + sec['size'] <= s[3] + s[4], 'section segment file mapping')
    ro, rz, bo, bz, wo, wz, lo, lz, eo, ez = infos[0]
    require((rz, wz, lz, ez) == (0, 0, 0, 0), 'rebase/weak/lazy/export streams unsupported')
    bounded(m.data, eo, ez, 'export stream')
    stream = bounded(m.data, bo, bz, 'bind stream')
    command_end = 32 + struct.unpack_from('<I', m.data, 20)[0]
    require(bo >= command_end, 'bind stream overlaps commands')
    symcmd = [p for c, p, _ in _commands(m) if c == 2][0]
    so, sn, st, ss = struct.unpack_from('<4I', m.data, symcmd + 8)
    for start, size in ((so, sn * 16), (st, ss), (eo, ez)):
        require(not (bz and size and max(bo, start) < min(bo + bz, start + size)),
                'bind stream overlaps metadata')
    for sec in m.sections:
        if sec['flags'] & 0xff not in (1, 0xc, 0x12):
            require(not (bz and sec['size'] and max(bo, sec['offset']) <
                         min(bo + bz, sec['offset'] + sec['size'])), 'bind stream overlaps section')
    require(len(stream) >= 2 and stream[0] & 0xf0 == 0x10,
            'explicit immediate positive dylib ordinal required')
    ordinal, p = stream[0] & 15, 1
    require(0 < ordinal <= len(libraries) and libraries[ordinal - 1] == (0xc, LIBSYSTEM),
            'bootstrap ordinal must declare normal libSystem dependency')
    require(libraries.count((0xc, LIBSYSTEM)) == 1, 'duplicate libSystem dependency')
    expected = b'\x40' + BOOTSTRAP + b'\0\x51\x60\x00'
    require(stream[p:p + len(expected)] == expected, 'bootstrap name/flags/type/addend bind tuple')
    p += len(expected)
    require(p < len(stream) and stream[p] & 0xf0 == 0x70, 'bind segment opcode required')
    segment = stream[p] & 15
    offset, p = _uleb(stream, p + 1)
    require(stream[p:] == b'\x90\x00', 'single bind plus DONE required; duplicate/unknown/trailing fixup')
    require(segment < len(segments), 'bind segment index')
    s = segments[segment]
    require(offset % 8 == 0 and offset + 8 <= s[4] and s[1] + offset == d['address'],
            'bootstrap fixup must target descriptor thunk field')
    imports = [s for s in m.symbols if s['name'] == BOOTSTRAP]
    require(len(imports) == 1 and imports[0]['type'] == 1 and imports[0]['section'] == 0 and
            imports[0]['value'] == 0 and _desc(m, imports[0]) == ordinal << 8,
            'bootstrap nlist import/ordinal must agree with bind')
    require(struct.unpack_from('<I', m.data, 24)[0] & 0x80, 'two-level namespace required')
    return dict(kind='classic-single-explicit-bind', ordinal=ordinal,
                library_hex=LIBSYSTEM.hex(), symbol_hex=BOOTSTRAP.hex(), address=d['address'])


def _data_definition(obj, name, allow_weak):
    _, ds, descriptor = _symbol_span(obj, name, (0x13,), descriptor=True, allow_weak=allow_weak)
    backing = _object_fields(obj, descriptor, ds)
    symbol, section, span = _symbol_span(obj, backing['name'], (0x11, 0x12), allow_weak=allow_weak)
    require(symbol == backing, 'object backing relocation target')
    require(not _span_relocs(obj, section, span), 'object backing data relocations unsupported')
    return backing, span


def attest_tlvp(obj, image, original_function, linked_function, reloc, *,
                map_data=None, physical_objects=None):
    """Return a finite artifact-bound descriptor/template witness or ValueError.

    Inputs are the unchanged generic MachO parser's objects/function/relocation
    records. Re-derive the consumed relocation pair and instruction bytes; never
    trust a caller-supplied decoded destination or merely masked code equality.
    """
    require(obj.kind == 1 and image.kind == 2, 'object then executable required')
    _layout(obj)
    _, linked_templates = _layout(image)
    require(reloc['type'] in (8, 9), 'TLVP relocation required')
    # Re-read functions by exact symbol; supplied dictionaries cannot substitute bytes.
    of = obj.function(original_function['symbol']['name'])
    lf = image.function(linked_function['symbol']['name'])
    require(of == original_function and lf == linked_function and
            of['symbol']['name'] == lf['symbol']['name'], 'function records differ from artifact')
    rs = obj.relocations(of)
    require(sum(r == reloc for r in rs) == 1, 'unique actual TLVP relocation required')
    pageoff = reloc['offset'] - (4 if reloc['type'] == 9 else 0)
    pair = [r for r in rs if r['offset'] in (pageoff, pageoff + 4)]
    require(len(pair) == 2, 'adjacent unique TLVP pair required')
    pair.sort(key=lambda r: r['offset'])
    a, b = pair
    require((a['offset'], b['offset']) == (pageoff, pageoff + 4) and
            a['type'] == 8 and b['type'] == 9 and a['target'] == b['target'] and
            (a['length'], a['external'], a['pcrel']) == (2, 1, 1), 'TLVP pair target/encoding')
    target = obj.symbols[a['target']]
    linked_symbols = image.definitions(target['name'])
    require(len(linked_symbols) == 1, 'unique linked descriptor required')
    weak = _desc(obj, target) == 0x80 or _desc(image, linked_symbols[0]) == 0x80
    provider_obj, provider_binding = obj, None
    if weak:
        require(type(map_data) is bytes and type(physical_objects) is dict,
                'weak/coalesced TLS requires physical selected-provider context')
        selected = _provider.selected_definition(map_data, image, physical_objects, target['name'])
        provider_obj, provider_binding = selected['object'], selected['binding']
        _layout(provider_obj)  # A selected object is a third artifact, not the already-checked reference.
        require(provider_binding['size'] == 24, 'selected descriptor atom must cover all three fields')
        provider_symbol = _definition(provider_obj, target['name'], allow_weak=True)
        require(all(_desc(m, s) == 0x80 and s['type'] & 1 for m, s in
                    ((obj, target), (image, linked_symbols[0]), (provider_obj, provider_symbol))),
                'weak descriptor flags must agree across reference, selected provider and image')
    os, _, _ = _symbol_span(obj, target['name'], (0x13,), descriptor=True, allow_weak=weak)
    require(os == target, 'actual object descriptor required')
    _, _, ld = _symbol_span(image, target['name'], (0x13,), descriptor=True, allow_weak=weak)
    require(pageoff >= 0 and pageoff % 4 == 0, 'TLVP instruction alignment')
    aw, bw = struct.unpack('<II', bounded(of['code'], pageoff, 8, 'original TLVP pair'))
    al, bl = struct.unpack('<II', bounded(lf['code'], pageoff, 8, 'linked TLVP pair'))
    mask = _base.relocation_mask(aw, a)
    require(aw & mask == 0 and al & ~mask == aw, 'ADRP zero addend/opcode/register required')
    imm = ((al >> 29) & 3) | (((al >> 5) & 0x7ffff) << 2)
    if imm & (1 << 20):
        imm -= 1 << 21
    require(((lf['start'] + pageoff) & ~0xfff) + imm * 4096 == ld['address'] & ~0xfff,
            'ADRP descriptor page destination differs')
    require(aw & 31 != 31 and bw & 31 != 31 and bw & 0xffc00000 == 0xf9400000,
            '64-bit TLVP pointer load with ordinary registers required')
    require((bw >> 5) & 31 == aw & 31, 'TLVP LDR base must be ADRP destination')
    _base.local_tlvp_lea(obj, image, bw, bl, b)
    backing, ot = _data_definition(provider_obj, target['name'], weak)
    if weak:
        reference_backing, reference_span = _data_definition(obj, target['name'], True)
        require(reference_backing['name'] == backing['name'] and
                (reference_span['flags'] & 255, reference_span['size']) == (ot['flags'] & 255, ot['size']) and
                _section_bytes(obj, reference_span) == _section_bytes(provider_obj, ot),
                'coalesced reference and selected-provider initial state differ')
        if _desc(provider_obj, backing) == 0x80:
            backing_provider = _provider.selected_definition(map_data, image, physical_objects, backing['name'])
            require(backing_provider['binding']['object_index'] == provider_binding['object_index'] and
                    backing_provider['object'].data == provider_obj.data and
                    backing_provider['binding']['size'] == ot['size'],
                    'coalesced descriptor/backing must share the selected physical provider')
    linked_backing, _, lt = _symbol_span(image, backing['name'], (0x11, 0x12), allow_weak=weak)
    if weak:
        require(_desc(obj, reference_backing) == _desc(provider_obj, backing) == _desc(image, linked_backing),
                'coalesced backing flags differ across reference, selected provider and image')
    require(ot['flags'] & 255 == lt['flags'] & 255 and lt['size'] >= ot['size'],
            'TLS backing kind/extent differs')
    lt = dict(lt, size=ot['size'])
    require(_section_bytes(provider_obj, ot) == _section_bytes(image, lt), 'TLS initial bytes differ')
    # ld64 OutputFile.cpp:520-548: offset from FIRST template section, not a pointer.
    expected_offset = lt['address'] - linked_templates[0]['address']
    thunk, key, offset = struct.unpack('<QQQ', _section_bytes(image, ld))
    require(key == 0 and offset == expected_offset, 'linked descriptor key/template-relative offset differs')
    if any(c == 0x80000034 for c, _, _ in _commands(image)):
        decoded = _chain.parse_chained_fixups(image)
        for address in decoded['by_address']:
            for sec in image.sections:
                kind = sec['flags'] & 255
                if kind in (0x11, 0x12):
                    require(not (max(address, sec['address']) <
                                 min(address + 8, sec['address'] + sec['size'])),
                            'chain fixup modifies TLS template bytes')
                elif kind == 0x13 and max(address, sec['address']) < min(address + 8, sec['address'] + sec['size']):
                    require(sec['address'] <= address and address + 8 <= sec['address'] + sec['size'] and
                            (address - sec['address']) % 24 == 0,
                            'chain fixup modifies descriptor key/offset or straddles descriptor')
        fixup = _chain.bootstrap_binding(image, decoded, ld['address'])
    else:
        require(thunk == 0, 'classic descriptor thunk prelaunch state differs')
        fixup = _classic_bind(image, ld)
    return dict(schema='finite-tlvp-data-origin-v1', descriptor_name_hex=target['name'].hex(),
                descriptor_address=ld['address'], backing_name_hex=backing['name'].hex(),
                backing_address=lt['address'], backing_extent=lt['size'],
                backing_kind='zerofill' if lt['flags'] & 0xff == 0x12 else 'initial-data',
                backing_sha256=(None if lt['flags'] & 0xff == 0x12 else
                                hashlib.sha256(_section_bytes(image, lt)).hexdigest()),
                template_relative_offset=expected_offset,
                template_origin_address=linked_templates[0]['address'],
                extent_contract='object next distinct section nlist symbol or section end; linked span must cover it',
                key_prelaunch=0, bootstrap_fixup=fixup,
                object_sha256=hashlib.sha256(obj.data).hexdigest(),
                selected_data_provider=provider_binding,
                data_provider_sha256=hashlib.sha256(provider_obj.data).hexdigest(),
                image_sha256=hashlib.sha256(image.data).hexdigest())
