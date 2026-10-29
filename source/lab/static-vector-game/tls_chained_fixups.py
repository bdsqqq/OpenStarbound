"""Read-only DYLD_CHAINED_PTR_64_OFFSET / DYLD_CHAINED_IMPORT byte reader.

Authoritative format source: installed MacOSX27.0.sdk/usr/include/mach-o/
fixup-chains.h:40-105 (headers/starts),173-182 (rebase),220-229 (bind),
329-341 (imports). SHA256 of that installed header:
64836772232f1a90c5dea06e9592a0e632bf167120612991d4d4a1f4051eb67d.
loader.h:1380-1540 defines classic fixups/library ordinals.
No inference from historical executable contents and no native tool execution.
Unsupported: multi-start pages, other pointer/import formats, compressed symbols,
special ordinals other than loader.h's 0,-1,-2,-3.
The result describes declared prelaunch fixups, not runtime symbol resolution.
"""
import struct


def require(ok, message):
    if not ok:
        raise ValueError(message)


def bounded(data, offset, size, label):
    require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset, label + ' bounds')
    return data[offset:offset + size]


def commands(image):
    data = image.data
    end = 32 + struct.unpack_from('<I', data, 20)[0]
    p = 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        cmd, size = struct.unpack('<II', bounded(data, p, 8, 'command'))
        require(size >= 8 and size % 8 == 0 and p + size <= end, 'command extent')
        yield cmd, p, size
        p += size
    require(p == end, 'command table extent')


def _disjoint(ranges, label):
    ordered = sorted((a, a + n) for a, n in ranges if n)
    require(all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:])), label + ' overlap')


def parse_chained_fixups(image):
    """Decode EVERY declared chain; return address -> bind/rebase records.

    Every chain window is file-backed, within its declared page and segment,
    four-byte aligned (the format's stride), and nonoverlapping with every
    other eight-byte window or structural metadata. No partial enumeration.
    """
    require(image.kind == 2, 'chained reader requires executable')
    data = image.data
    flags = struct.unpack_from('<I', data, 24)[0]
    require(flags & 0x80 and not flags & 0x100, 'two-level non-flat image required')
    chain_commands, segments, libraries, structural = [], [], [], []
    structural.append((0, 32 + struct.unpack_from('<I', data, 20)[0]))
    symtable = None
    for cmd, p, size in commands(image):
        if cmd == 0x19:
            require(size >= 72, 'segment size')
            name, vm, extent, off, filesz = struct.unpack_from('<16sQQQQ', data, p + 8)
            require(filesz <= extent and vm + extent <= 1 << 64, 'segment extent')
            bounded(data, off, filesz, 'segment')
            segments.append(dict(name=name.rstrip(b'\0'), vm=vm, size=extent,
                                 fileoff=off, filesize=filesz))
        elif cmd in (0xc, 0x80000018, 0x8000001f, 0x20, 0x80000023):
            require(size >= 24, 'dylib command size')
            no = struct.unpack_from('<I', data, p + 8)[0]
            require(24 <= no < size, 'dylib name offset')
            raw = bounded(data, p + no, size - no, 'dylib name')
            require(b'\0' in raw, 'dylib name termination')
            libraries.append((cmd, raw.split(b'\0', 1)[0]))
        elif cmd == 0x80000034:
            require(size == 16, 'chained command size')
            chain_commands.append(struct.unpack_from('<II', data, p + 8))
        elif cmd in (0x22, 0x80000022):
            # Even an empty parallel classic command is outside this contract.
            raise ValueError('simultaneous classic/chained commands unsupported')
        elif cmd in (0x21, 0x2c):
            raise ValueError('encrypted image unsupported')
        elif cmd == 2:
            require(size == 24 and symtable is None, 'unique symbol table')
            symtable = struct.unpack_from('<4I', data, p + 8)
            so, sn, st, ss = symtable
            structural.extend([(so, sn * 16), (st, ss)])
        elif cmd == 0xb:
            require(size == 80, 'dynamic symbol table size')
            # TOC/module/external-reference tables are distinct structural byte
            # ranges, not covered by the indirect table below. No consumer for
            # them exists in this narrow modern-image contract.
            require(all(struct.unpack_from('<I', data, p + n)[0] == 0 for n in (36, 44, 52)),
                    'dynamic TOC/module/reference side tables unsupported')
            require(struct.unpack_from('<4I', data, p + 64) == (0, 0, 0, 0),
                    'external/local dynamic relocations unsupported')
            io, count = struct.unpack_from('<II', data, p + 56)
            structural.append((io, count * 4))
        elif cmd in (0x1d, 0x1e, 0x26, 0x29, 0x2b, 0x2e, 0x80000033, 0x36):
            require(size == 16, 'linkedit data command size')
            structural.append(struct.unpack_from('<II', data, p + 8))
    require(len(chain_commands) == 1 and symtable is not None, 'one chained command and symbol table required')
    require(all(s['nreloc'] == 0 for s in image.sections), 'linked section relocations unsupported')
    require(all(s['name'] != b'__chain_starts' for s in image.sections),
            'parallel firmware section chains unsupported')
    _disjoint([(s['vm'], s['size']) for s in segments], 'segment VM')
    _disjoint([(s['fileoff'], s['filesize']) for s in segments], 'segment file')
    anchors = [s for s in segments if s['fileoff'] == 0 and s['filesize'] >= 32]
    require(len(anchors) == 1, 'unique file-header image base required')
    base = anchors[0]['vm']
    for sec in image.sections:
        owners = [s for s in segments if s['name'] == sec['segment'] and
                  s['vm'] <= sec['address'] and sec['address'] + sec['size'] <= s['vm'] + s['size']]
        require(len(owners) == 1, 'unique section segment mapping')
        s = owners[0]
        if sec['flags'] & 255 not in (1, 0xc, 0x12):
            require(sec['offset'] == s['fileoff'] + sec['address'] - s['vm'] and
                    sec['offset'] + sec['size'] <= s['fileoff'] + s['filesize'], 'section file mapping')
    off, size = chain_commands[0]
    blob = bounded(data, off, size, 'chained payload')
    require(len([s for s in segments if s['fileoff'] <= off and off + size <=
                 s['fileoff'] + s['filesize']]) == 1, 'chained payload segment ownership')
    for start, extent in structural:
        bounded(data, start, extent, 'structural metadata')
        require(not (extent and max(start, off) < min(start + extent, off + size)),
                'chained payload aliases metadata')
    for sec in image.sections:
        if sec['flags'] & 255 not in (1, 0xc, 0x12):
            require(not (sec['size'] and max(sec['offset'], off) <
                         min(sec['offset'] + sec['size'], off + size)), 'chained payload aliases section')
    structural.append((off, size))
    _disjoint(structural, 'structural metadata')
    section_ranges = [(s['offset'], s['size']) for s in image.sections
                      if s['flags'] & 255 not in (1, 0xc, 0x12)]
    for start, extent in structural:
        for so, ss in section_ranges:
            require(not (extent and ss and max(start, so) < min(start + extent, so + ss)),
                    'structural metadata aliases section data')
    _disjoint(section_ranges, 'section file extents')
    _disjoint([(s['address'], s['size']) for s in image.sections], 'section VM extents')
    version, starts, imports, symbols, count, fmt, sfmt = struct.unpack(
        '<7I', bounded(blob, 0, 28, 'chained header'))
    require((version, fmt, sfmt) == (0, 1, 0), 'unsupported chained header/import/string format')
    require(28 <= starts < imports <= symbols <= len(blob), 'chained table ordering')
    require(imports + count * 4 <= symbols, 'imports overlap strings')
    nseg = struct.unpack('<I', bounded(blob, starts, 4, 'starts header'))[0]
    require(nseg == len(segments), 'starts segment count must match load commands')
    bounded(blob, starts + 4, nseg * 4, 'starts segment offsets')
    ranges = [(0, 28), (starts, 4 + nseg * 4), (imports, count * 4), (symbols, len(blob) - symbols)]
    decoded_imports = []
    for i in range(count):
        word = struct.unpack_from('<I', blob, imports + 4 * i)[0]
        ordinal = word & 255
        if ordinal > 240:
            ordinal -= 256
        require(ordinal in (0, -1, -2, -3) or 0 < ordinal <= len(libraries), 'import library ordinal bounds')
        no = symbols + (word >> 9)
        require(symbols <= no < len(blob), 'import name offset')
        end = blob.find(b'\0', no)
        require(end > no, 'import name termination/nonempty')
        decoded_imports.append(dict(index=i, ordinal=ordinal, weak=(word >> 8) & 1,
                                    name=blob[no:end], library=(libraries[ordinal - 1] if ordinal > 0 else None)))
    by_address, windows = {}, []
    for index, segment in enumerate(segments):
        relative = struct.unpack_from('<I', blob, starts + 4 + 4 * index)[0]
        if not relative:
            continue
        p = starts + relative
        raw = bounded(blob, p, 22, 'segment starts')
        extent, page_size, pointer_format, segment_offset, maximum, pages = struct.unpack('<IHHQIH', raw)
        require(pointer_format == 6 and maximum == 0, 'only format6/no max_valid_pointer supported')
        require(page_size in (4096, 16384) and extent == 22 + pages * 2, 'page starts extent/size; multi-start unsupported')
        bounded(blob, p, extent, 'segment starts extent')
        require(p >= starts + 4 + nseg * 4 and p + extent <= imports, 'segment starts ordering')
        ranges.append((p, extent))
        require(segment['vm'] >= base and segment_offset == segment['vm'] - base,
                'starts segment VM offset differs')
        require(pages <= (segment['size'] + page_size - 1) // page_size, 'page count beyond segment')
        for page in range(pages):
            first = struct.unpack_from('<H', blob, p + 22 + page * 2)[0]
            if first == 0xffff:
                continue
            require(not first & 0x8000, 'multi-start pages unsupported')
            require(first % 4 == 0 and first + 8 <= page_size, 'page start alignment/window')
            location = page * page_size + first
            page_end = (page + 1) * page_size
            while True:
                require(location % 4 == 0 and location + 8 <= page_end and
                        location + 8 <= segment['filesize'], 'chain page/file window')
                address = segment['vm'] + location
                fileoff = segment['fileoff'] + location
                require(address not in by_address, 'duplicate/cyclic chain pointer')
                for start, length in structural:
                    require(not (length and max(fileoff, start) < min(fileoff + 8, start + length)),
                            'chain pointer aliases metadata')
                word = struct.unpack('<Q', bounded(data, fileoff, 8, 'chain pointer'))[0]
                nxt = (word >> 51) & 0xfff
                record = dict(address=address, fileoff=fileoff, raw_word=word, next_stride4=nxt)
                if word >> 63:
                    require((word >> 32) & 0x7ffff == 0, 'bind reserved bits')
                    imp = word & 0xffffff
                    require(imp < len(decoded_imports), 'chain import index')
                    record.update(kind='bind', import_index=imp, import_record=decoded_imports[imp],
                                  addend=(word >> 24) & 255)
                else:
                    require((word >> 44) & 127 == 0, 'rebase reserved bits')
                    high8 = (word >> 36) & 255
                    low = word & ((1 << 36) - 1)
                    # fixup-chains.h dyld_chained_ptr_64_rebase explicitly says
                    # high8 is set BEFORE slide for OFFSET. Retain the tag in
                    # the declared value; validate image ownership using the
                    # separately recorded low image-relative destination.
                    image_target = base + low
                    unpacked_offset = low | (high8 << 56)
                    target = base + unpacked_offset
                    require(image_target < 1 << 56 and target < 1 << 64 and
                            any(s['vm'] <= image_target < s['vm'] + s['size'] for s in segments),
                            'rebase target image bounds/high8 overflow')
                    record.update(kind='rebase', target=target, target_offset=unpacked_offset,
                                  high8=high8, image_target=image_target)
                by_address[address] = record
                windows.append((address, 8))
                if nxt == 0:
                    break
                require(nxt * 4 >= 8, 'overlapping chain windows')
                location += nxt * 4
    _disjoint(ranges, 'chained tables')
    _disjoint(windows, 'chain windows')
    return dict(schema='chained-format6-v1', image_base=base, by_address=by_address,
                imports=decoded_imports, libraries=libraries, payload_offset=off, payload_size=size)


def bootstrap_binding(image, decoded, address):
    """Bind descriptor thunk to a unique explicit normal libSystem import."""
    name, library = b'__tlv_bootstrap', (0xc, b'/usr/lib/libSystem.B.dylib')
    require(decoded['libraries'].count(library) == 1, 'unique normal libSystem dependency required')
    ordinal = decoded['libraries'].index(library) + 1
    imports = [i for i in decoded['imports'] if i['name'] == name]
    require(len(imports) == 1 and imports[0]['ordinal'] == ordinal and
            imports[0]['library'] == library and imports[0]['weak'] == 0,
            'bootstrap chained import name/library/ordinal/weakness')
    fixup = decoded['by_address'].get(address)
    require(fixup is not None and fixup['kind'] == 'bind' and fixup['import_index'] == imports[0]['index']
            and fixup['addend'] == 0, 'descriptor thunk bootstrap bind/addend required')
    matches = [s for s in image.symbols if s['name'] == name]
    require(len(matches) == 1 and matches[0]['type'] == 1 and matches[0]['section'] == 0 and
            matches[0]['value'] == 0, 'unique undefined bootstrap nlist import required')
    symcmd = [p for c, p, _ in commands(image) if c == 2][0]
    symoff = struct.unpack_from('<I', image.data, symcmd + 8)[0]
    desc = struct.unpack_from('<H', image.data, symoff + matches[0]['index'] * 16 + 6)[0]
    require(desc == ordinal << 8, 'bootstrap nlist ordinal/flags differ')
    return dict(kind='chained-format6-bind', address=address, ordinal=ordinal,
                symbol_hex=name.hex(), library_hex=library[1].hex(), addend=0)
