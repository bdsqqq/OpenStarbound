"""Physical multi-descriptor/template Mach-O fixtures; no core-verifier mocks."""
import struct
import unittest

import tls_data_origin as tls
import tls_chained_fixups as chains
from test_tls_data_origin import fixture as classic_fixture

BASE = 0x100000000
TEXT, DESC, DATA, BSS, EXTRA = 0x1000, 0x2010, 0x2080, 0x2090, 0x20a0
SYMS, STRINGS, RELOCS, DRELOCS, PAYLOAD = 0x3000, 0x3080, 0x3100, 0x3120, 0x3400
SECTIONS = 104
CHAIN_COMMAND = 504
SEGMENT_STARTS = 40


def fixture(linked=False, zero=False):
    buf = bytearray(0x4000)
    base = BASE if linked else 0
    segment_size = 72 + 4 * 80
    commands_size = segment_size + 24 + (56 + 16 if linked else 0)
    struct.pack_into('<IiiIIIII', buf, 0, 0xfeedfacf, 0x100000c, 0, 2 if linked else 1,
                     4 if linked else 2, commands_size, 0x80 if linked else 0, 0)
    struct.pack_into('<II16sQQQQiiII', buf, 32, 0x19, segment_size, b'__DATA', base,
                     0x4000, 0, 0x4000, 7, 7, 4, 0)
    for i, (name, off, size, flags, rel, nr) in enumerate([
            (b'__text', TEXT, 8, 0x80000000, RELOCS, 2),
            (b'__thread_vars', DESC, 48, 0x13, DRELOCS, 4),
            (b'__thread_data', DATA, 8, 0x11, 0, 0),
            (b'__thread_bss', BSS, 8, 0x12, 0, 0)]):
        struct.pack_into('<16s16sQQIIIIIIII', buf, SECTIONS + i * 80,
                         name, b'__DATA', base + off, size, off, 3,
                         0 if linked else rel, 0 if linked else nr, flags, 0, 0, 0)
    names = [b'_entry', b'_tls_other', b'_tls', b'_data_first', b'_backing', b'_bss',
             b'__tlv_bootstrap', b'_other']
    strings, indices = b'\0', []
    for name in names:
        indices.append(len(strings))
        strings += name + b'\0'
    p = 32 + segment_size
    struct.pack_into('<6I', buf, p, 2, 24, SYMS, len(names), STRINGS, len(strings))
    buf[STRINGS:STRINGS + len(strings)] = strings
    positions = [(TEXT, 1), (DESC, 2), (DESC + 24, 2), (DATA, 3), (DATA + 4, 3), (BSS, 4), (0, 0), (0, 0)]
    for i, (off, sec) in enumerate(positions):
        struct.pack_into('<IBBHQ', buf, SYMS + 16 * i, indices[i], 0xe if sec else 1, sec,
                         256 if linked and not sec else 0, base + off if sec else 0)
    struct.pack_into('<II', buf, TEXT, 0xb0000000 if linked else 0x90000000,
                     0x9100a000 if linked else 0xf9400000)
    buf[DATA:DATA + 8] = b'abcdefgh'
    if not linked:
        for p, offset, target, typ, width, pc in [
                (RELOCS, 0, 2, 8, 2, 1), (RELOCS + 8, 4, 2, 9, 2, 0),
                (DRELOCS, 0, 6, 0, 3, 0), (DRELOCS + 8, 16, 3, 0, 3, 0),
                (DRELOCS + 16, 24, 6, 0, 3, 0), (DRELOCS + 24, 40, 5 if zero else 4, 0, 3, 0)]:
            struct.pack_into('<iI', buf, p, offset, target | pc << 24 | width << 25 | 1 << 27 | typ << 28)
    else:
        p += 24
        struct.pack_into('<6I', buf, p, 0xc, 56, 24, 0, 0, 0)
        buf[p + 24:p + 24 + len(tls.LIBSYSTEM) + 1] = tls.LIBSYSTEM + b'\0'
        blob = bytearray(80)
        symbols = b'__tlv_bootstrap\0_other\0'
        struct.pack_into('<7I', blob, 0, 0, 32, 72, 80, 2, 1, 0)
        struct.pack_into('<II', blob, 32, 1, 8)
        struct.pack_into('<IHHQIH4H', blob, SEGMENT_STARTS, 30, 4096, 6, 0, 0, 4,
                         0xffff, 0xffff, DESC % 4096, 0xffff)
        struct.pack_into('<II', blob, 72, 1, 1 | len(b'__tlv_bootstrap\0') << 9)
        blob += symbols
        struct.pack_into('<4I', buf, CHAIN_COMMAND, 0x80000034, 16, PAYLOAD, len(blob))
        buf[PAYLOAD:PAYLOAD + len(blob)] = blob
        struct.pack_into('<Q', buf, DESC, 1 << 63 | 6 << 51)
        struct.pack_into('<Q', buf, DESC + 24, 1 << 63 | ((EXTRA - DESC - 24) // 4) << 51)
        struct.pack_into('<Q', buf, DESC + 40, BSS - DATA if zero else 4)
        struct.pack_into('<Q', buf, EXTRA, TEXT | 2 << 51)
        struct.pack_into('<Q', buf, EXTRA + 8, 1 << 63 | 1 | 3 << 24)
    return buf


def parse(buf):
    return chains.parse_chained_fixups(tls.MachO(bytes(buf)))


def attest(obj=None, image=None):
    obj = tls.MachO(bytes(fixture() if obj is None else obj))
    image = tls.MachO(bytes(fixture(True) if image is None else image))
    of, lf = obj.function(b'_entry'), image.function(b'_entry')
    return tls.attest_tlvp(obj, image, of, lf, obj.relocations(of)[0])


class ChainedTests(unittest.TestCase):
    def bad(self, b, parser=False, obj=None):
        with self.assertRaises(ValueError):
            parse(b) if parser else attest(obj=obj, image=b)

    def test_all_chain_entries_and_unrelated_bind_rebase(self):
        r = parse(fixture(True))
        self.assertEqual(set(r['by_address']), {BASE + DESC, BASE + DESC + 24, BASE + EXTRA, BASE + EXTRA + 8})
        self.assertEqual(r['by_address'][BASE + EXTRA]['target'], BASE + TEXT)
        self.assertEqual(r['by_address'][BASE + EXTRA + 8]['addend'], 3)
        self.assertEqual(r['imports'][1]['name'], b'_other')

    def test_chains_in_two_independent_segments(self):
        b = fixture(True)
        count, size = struct.unpack_from('<II', b, 16)
        struct.pack_into('<II16sQQQQiiII', b, 32 + size, 0x19, 72, b'__EXTRA',
                         BASE + 0x4000, 4096, 0x4000, 4096, 3, 3, 0, 0)
        struct.pack_into('<II', b, 16, count + 1, size + 72)
        b += bytes(4096)
        struct.pack_into('<Q', b, 0x4000, TEXT)
        blob = bytearray(108)
        struct.pack_into('<7I', blob, 0, 0, 32, 100, 108, 2, 1, 0)
        struct.pack_into('<III', blob, 32, 2, 12, 42)
        struct.pack_into('<IHHQIH4H', blob, 44, 30, 4096, 6, 0, 0, 4,
                         0xffff, 0xffff, DESC % 4096, 0xffff)
        struct.pack_into('<IHHQIHH', blob, 74, 24, 4096, 6, 0x4000, 0, 1, 0)
        struct.pack_into('<II', blob, 100, 1, 1 | len(b'__tlv_bootstrap\0') << 9)
        blob += b'__tlv_bootstrap\0_other\0'
        struct.pack_into('<I', b, CHAIN_COMMAND + 12, len(blob))
        b[PAYLOAD:PAYLOAD + len(blob)] = blob
        result = parse(b)
        self.assertEqual(len(result['by_address']), 5)
        self.assertEqual(result['by_address'][BASE + 0x4000]['target'], BASE + TEXT)
        self.assertEqual(attest(image=b)['template_relative_offset'], 4)

    def test_rebase_high8_is_preserved_before_slide_not_masked(self):
        b = fixture(True)
        struct.pack_into('<Q', b, EXTRA, TEXT | 0xab << 36 | 2 << 51)
        r = parse(b)['by_address'][BASE + EXTRA]
        self.assertEqual(r['target_offset'], 0xab00000000001000)
        self.assertEqual(r['target'], 0xab00000100001000)
        self.assertEqual(r['image_target'], BASE + TEXT)
        self.assertEqual(r['high8'], 0xab)

    def test_multi_descriptor_initial_data_and_zero_fill_nonzero_offsets(self):
        for zero in (False, True):
            r = attest(fixture(zero=zero), fixture(True, zero=zero))
            self.assertEqual(r['descriptor_address'], BASE + DESC + 24)
            self.assertEqual(r['template_relative_offset'], 16 if zero else 4)
            self.assertEqual(r['backing_extent'], 8 if zero else 4)
            self.assertEqual(r['bootstrap_fixup']['kind'], 'chained-format6-bind')

    def test_wrong_offset_key_pointer_and_bootstrap_destination(self):
        for p, value in ((DESC + 32, 1), (DESC + 40, BASE + DATA + 4),
                         (DESC + 24, 1 << 63 | 1), (DESC + 24, TEXT)):
            b = fixture(True)
            struct.pack_into('<Q', b, p, value)
            self.bad(b)

    def test_bootstrap_ordinal_weak_name_and_pointer_addend(self):
        for word in (2, 0, 1 | 1 << 8, 1 | 15 << 9):
            b = fixture(True)
            struct.pack_into('<I', b, PAYLOAD + 72, word)
            self.bad(b)
        b = fixture(True)
        word = struct.unpack_from('<Q', b, DESC + 24)[0]
        struct.pack_into('<Q', b, DESC + 24, word | 1 << 24)
        self.bad(b)
        b = fixture(True)
        struct.pack_into('<H', b, SYMS + 6 * 16 + 6, 512)
        self.bad(b)

    def test_unknown_header_pointer_formats_compression_and_reserved_bits(self):
        for p, fmt, value in ((PAYLOAD, '<I', 1), (PAYLOAD + 20, '<I', 2),
                              (PAYLOAD + 24, '<I', 1), (PAYLOAD + SEGMENT_STARTS + 6, '<H', 1),
                              (DESC + 24, '<Q', 1 << 63 | 1 << 32),
                              (EXTRA, '<Q', TEXT | 1 << 44)):
            b = fixture(True)
            struct.pack_into(fmt, b, p, value)
            self.bad(b, parser=True)

    def test_start_pages_next_windows_and_import_bounds(self):
        for p, fmt, value in ((PAYLOAD + SEGMENT_STARTS + 26, '<H', 0x8000),
                              (PAYLOAD + SEGMENT_STARTS + 26, '<H', 0xffc),
                              (PAYLOAD + SEGMENT_STARTS + 26, '<H', 0x11),
                              (PAYLOAD + SEGMENT_STARTS + 8, '<Q', 4096),
                              (PAYLOAD + SEGMENT_STARTS + 20, '<H', 5),
                              (DESC, '<Q', 1 << 63 | 1 << 51),
                              (DESC, '<Q', 1 << 63 | 0xfff << 51),
                              (DESC, '<Q', 1 << 63 | 2),
                              (EXTRA, '<Q', 0xfffffffff)):
            b = fixture(True)
            struct.pack_into(fmt, b, p, value)
            self.bad(b, parser=True)

    def test_metadata_overlap_and_truncation(self):
        for p, value in ((PAYLOAD + 8, 48), (PAYLOAD + 12, 72),
                          (PAYLOAD + 36, 0), (CHAIN_COMMAND + 8, SYMS)):
            b = fixture(True)
            struct.pack_into('<I', b, p, value)
            self.bad(b)
        for end in (PAYLOAD + 12, PAYLOAD + 80, 300):
            self.bad(fixture(True)[:end], parser=True)

    def test_fixups_cannot_modify_any_descriptor_key_offset_or_tls_template(self):
        for destination in (DESC + 8, DESC + 16, DATA, DATA + 4, BSS):
            b = fixture(True)
            # Redirect first pointer's chain to protected state. Decoder must
            # enumerate this entry rather than skip it as unrelated to _tls.
            struct.pack_into('<Q', b, DESC, 1 << 63 | ((destination - DESC) // 4) << 51)
            struct.pack_into('<Q', b, destination, TEXT)
            self.bad(b)

    def test_weak_alias_stripped_or_relocated_backing_span(self):
        for field, fmt, value in ((SYMS + 4 * 16 + 6, '<H', 0x80),
                                   (SYMS + 3 * 16 + 8, '<Q', DATA + 4),
                                   (SYMS + 4 * 16, '<I', 1),
                                   (SYMS + 4 * 16 + 4, '<B', 1)):
            obj = fixture()
            struct.pack_into(fmt, obj, field, value)
            self.bad(fixture(True), obj=obj)
        obj = fixture()
        struct.pack_into('<II', obj, SECTIONS + 160 + 56, 0x3180, 1)
        struct.pack_into('<iI', obj, 0x3180, 4, 2 << 25 | 1 << 27)
        self.bad(fixture(True), obj=obj)

    def test_duplicate_chained_command_and_classic_coexistence(self):
        for command in (fixture(True)[CHAIN_COMMAND:CHAIN_COMMAND + 16],
                        classic_fixture(True)[424:472]):
            b = fixture(True)
            count, size = struct.unpack_from('<II', b, 16)
            b[32 + size:32 + size + len(command)] = command
            struct.pack_into('<II', b, 16, count + 1, size + len(command))
            self.bad(b, parser=True)


if __name__ == '__main__':
    unittest.main()
