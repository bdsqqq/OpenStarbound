"""Physical synthetic arm64 Mach-O bytes; no native tools, files or verifier mocks."""
import struct
import unittest

import tls_data_origin as tls


BASE = 0x100000000
TEXT, DESC, DATA = 0x1000, 0x2010, 0x2030
SYMS, STRINGS, RELOCS, DRELOCS, BIND = 0x3000, 0x3080, 0x3100, 0x3120, 0x3300
SECTIONS = 32 + 72
INFO = 32 + 72 + 3 * 80 + 24 + 56
STREAM = b'\x11\x40__tlv_bootstrap\0\x51\x60\x00\x70\x90\x40\x90\x00'


def fixture(linked=False, zero=False, stream=STREAM, info_cmd=0x80000022):
    """One actual segment, three sections, nlists, raw relocations and bind stream."""
    buf = bytearray(0x4000)
    base = BASE if linked else 0
    sc = 72 + 3 * 80
    commands = sc + 24 + (56 + 48 if linked else 0)
    struct.pack_into('<IiiIIIII', buf, 0, 0xfeedfacf, 0x100000c, 0,
                     2 if linked else 1, 4 if linked else 2, commands, 0x80 if linked else 0, 0)
    struct.pack_into('<II16sQQQQiiII', buf, 32, 0x19, sc, b'__DATA', base,
                     0x4000, 0, 0x4000, 7, 7, 3, 0)
    for i, (name, off, size, flags, ro, nr) in enumerate([
            (b'__text', TEXT, 8, 0x80000000, RELOCS, 2),
            (b'__thread_vars', DESC, 24, 0x13, DRELOCS, 2),
            (b'__thread_bss' if zero else b'__thread_data', DATA, 4,
             0x12 if zero else 0x11, 0, 0)]):
        struct.pack_into('<16s16sQQIIIIIIII', buf, SECTIONS + 80 * i,
                         name, b'__DATA', base + off, size, off, 3,
                         0 if linked else ro, 0 if linked else nr, flags, 0, 0, 0)
    p = 32 + sc
    names = [b'_entry', b'_tls', b'_backing', b'__tlv_bootstrap']
    strings, indices = b'\0', []
    for name in names:
        indices.append(len(strings))
        strings += name + b'\0'
    struct.pack_into('<6I', buf, p, 2, 24, SYMS, 4, STRINGS, len(strings))
    buf[STRINGS:STRINGS + len(strings)] = strings
    for i, off in enumerate([TEXT, DESC, DATA, 0]):
        struct.pack_into('<IBBHQ', buf, SYMS + 16 * i, indices[i],
                         1 if i == 3 else 0xe, 0 if i == 3 else i + 1,
                         256 if linked and i == 3 else 0, base + off if i != 3 else 0)
    struct.pack_into('<II', buf, TEXT, 0xb0000000 if linked else 0x90000000,
                     0x91004000 if linked else 0xf9400000)
    if not zero:
        buf[DATA:DATA + 4] = b'abcd'
    if linked:
        p += 24
        struct.pack_into('<6I', buf, p, 0xc, 56, 24, 0, 0, 0)
        buf[p + 24:p + 24 + len(tls.LIBSYSTEM) + 1] = tls.LIBSYSTEM + b'\0'
        p += 56
        struct.pack_into('<12I', buf, p, info_cmd, 48, 0, 0, BIND, len(stream), 0, 0, 0, 0, 0, 0)
        buf[BIND:BIND + len(stream)] = stream
    else:
        for p, offset, target, typ, width, pc in [
                (RELOCS, 0, 1, 8, 2, 1), (RELOCS + 8, 4, 1, 9, 2, 0),
                (DRELOCS, 0, 3, 0, 3, 0), (DRELOCS + 8, 16, 2, 0, 3, 0)]:
            struct.pack_into('<iI', buf, p, offset,
                             target | pc << 24 | width << 25 | 1 << 27 | typ << 28)
    return buf


def weak_fixture():
    obj, image = fixture(), fixture(True)
    for data in (obj, image):
        for index in (1, 2):
            data[SYMS + 16 * index + 4] = 0xf  # N_SECT|N_EXT, not local weak flags.
            struct.pack_into('<H', data, SYMS + 16 * index + 6, 0x80)
    provider = bytearray(obj)
    provider[-1] = 1  # A distinct physical TU with the same TLS initializer.
    map_data = (b'# Object files:\n[0] linker synthesized\n[7] /owned/reference.o\n'
                b'[19] /owned/selected.o\n# Symbols:\n# Address Size File Name\n'
                b'0x100002010 0x18 [19] _tls\n0x100002030 0x4 [19] _backing\n')
    return obj, image, provider, map_data


def attest(obj=None, image=None, which=0):
    obj = tls.MachO(bytes(fixture() if obj is None else obj))
    image = tls.MachO(bytes(fixture(True) if image is None else image))
    of, lf = obj.function(b'_entry'), image.function(b'_entry')
    return tls.attest_tlvp(obj, image, of, lf, obj.relocations(of)[which])


class TLSOriginTests(unittest.TestCase):
    def bad(self, obj=None, image=None):
        with self.assertRaises(ValueError):
            attest(obj, image)

    def test_initial_data_both_relocations_and_info_commands(self):
        for cmd in (0x22, 0x80000022):
            for which in (0, 1):
                with self.subTest(cmd=cmd, which=which):
                    r = attest(image=fixture(True, info_cmd=cmd), which=which)
                    self.assertEqual(r['backing_extent'], 4)
                    self.assertEqual(r['backing_kind'], 'initial-data')
                    self.assertEqual(r['template_relative_offset'], 0)
                    self.assertEqual(r['bootstrap_fixup']['ordinal'], 1)
                    self.assertEqual(r['descriptor_address'], BASE + DESC)
                    self.assertEqual(len(r['image_sha256']), 64)

    def test_object_section_coordinates_are_not_runtime_pointer_addresses(self):
        obj = fixture()
        for i in range(3):
            p = SECTIONS + 80 * i + 32
            value = struct.unpack_from('<Q', obj, p)[0]
            struct.pack_into('<Q', obj, p, value + 4)
            p = SYMS + 16 * i + 8
            value = struct.unpack_from('<Q', obj, p)[0]
            struct.pack_into('<Q', obj, p, value + 4)
        self.assertEqual(attest(obj=obj)['descriptor_address'], BASE + DESC)
        image = fixture(True)
        struct.pack_into('<Q', image, SECTIONS + 80 + 32, BASE + DESC + 4)
        self.bad(image=image)

    def test_weak_definition_requires_selected_physical_data_provider(self):
        obj, image, provider, map_data = weak_fixture()
        original = tls.MachO(bytes(obj)); linked = tls.MachO(bytes(image))
        of, lf = original.function(b'_entry'), linked.function(b'_entry')
        reloc = original.relocations(of)[0]
        with self.assertRaisesRegex(ValueError, 'selected-provider context'):
            tls.attest_tlvp(original, linked, of, lf, reloc)
        result = tls.attest_tlvp(original, linked, of, lf, reloc,
            map_data=map_data, physical_objects={7: bytes(obj), 19: bytes(provider)})
        self.assertEqual(result['selected_data_provider']['object_index'], 19)
        self.assertNotEqual(result['object_sha256'], result['data_provider_sha256'])
        self.assertEqual(result['selected_data_provider']['symbol_name_hex'], b'_tls'.hex())

    def test_weak_provider_missing_wrong_address_flags_and_backing_owner_fail(self):
        obj, image, provider, map_data = weak_fixture()
        def check(source, linked, data, objects):
            source, linked = tls.MachO(bytes(source)), tls.MachO(bytes(linked))
            of, lf = source.function(b'_entry'), linked.function(b'_entry')
            with self.assertRaises(ValueError):
                tls.attest_tlvp(source, linked, of, lf, source.relocations(of)[0],
                    map_data=data, physical_objects=objects)
        check(obj, image, map_data, {7: bytes(obj)})
        check(obj, image, map_data.replace(b'0x100002010', b'0x100002018'), {19: bytes(provider)})
        check(obj, image, map_data.replace(b'0x18 [19] _tls', b'0x8 [19] _tls'), {19: bytes(provider)})
        check(obj, image, map_data.replace(b'0x4 [19] _backing', b'0x1 [19] _backing'), {19: bytes(provider)})
        check(obj, image, map_data.replace(b'[19] _backing', b'[7] _backing'),
              {7: bytes(obj), 19: bytes(provider)})
        for flags in (0, 0xc0):
            changed = bytearray(provider)
            struct.pack_into('<H', changed, SYMS + 16 + 6, flags)
            check(obj, image, map_data, {19: bytes(changed)})
        changed = bytearray(image)
        struct.pack_into('<H', changed, SYMS + 2 * 16 + 6, 0)
        check(obj, changed, map_data, {19: bytes(provider)})
        local = bytearray(obj); local[SYMS + 16 + 4] = 0xe
        check(local, image, map_data, {19: bytes(provider)})

    def test_selected_provider_layout_cannot_alias_text_and_descriptor(self):
        obj, image, provider, map_data = weak_fixture()
        struct.pack_into('<I', provider, SECTIONS + 48, DESC)
        original, linked = tls.MachO(bytes(obj)), tls.MachO(bytes(image))
        of, lf = original.function(b'_entry'), linked.function(b'_entry')
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            tls.attest_tlvp(original, linked, of, lf, original.relocations(of)[0],
                map_data=map_data, physical_objects={19: bytes(provider)})

    def test_coalesced_reference_initializer_must_equal_selected_provider(self):
        obj, image, provider, map_data = weak_fixture()
        provider[DATA] ^= 1
        image[DATA] ^= 1  # Matching the selected provider alone is insufficient.
        original, linked = tls.MachO(bytes(obj)), tls.MachO(bytes(image))
        of, lf = original.function(b'_entry'), linked.function(b'_entry')
        with self.assertRaisesRegex(ValueError, 'reference and selected-provider initial state'):
            tls.attest_tlvp(original, linked, of, lf, original.relocations(of)[0],
                map_data=map_data, physical_objects={19: bytes(provider)})

    def test_zerofill(self):
        r = attest(fixture(zero=True), fixture(True, zero=True))
        self.assertEqual(r['backing_kind'], 'zerofill')
        self.assertIsNone(r['backing_sha256'])

    def test_wrong_descriptor_page(self):
        b = fixture(True)
        struct.pack_into('<I', b, TEXT, 0xd0000000)
        self.bad(image=b)

    def test_wrong_descriptor_page_offset(self):
        b = fixture(True)
        struct.pack_into('<I', b, TEXT + 4, 0x91008000)
        self.bad(image=b)

    def test_wrong_register_and_opcode(self):
        for word in (0x91004020, 0xf9400800):
            b = fixture(True)
            struct.pack_into('<I', b, TEXT + 4, word)
            self.bad(image=b)

    def test_pointer_width_and_sp_zero_register_are_not_equivalent(self):
        for adrp, load, linked_adrp, add in (
                (0x90000000, 0xb9400000, 0xb0000000, 0x91004000),
                (0x9000001f, 0xf94003e0, 0xb000001f, 0x910043e0),
                (0x90000000, 0xf940001f, 0xb0000000, 0x9100401f)):
            obj, image = fixture(), fixture(True)
            struct.pack_into('<II', obj, TEXT, adrp, load)
            struct.pack_into('<II', image, TEXT, linked_adrp, add)
            self.bad(obj=obj, image=image)

    def test_pair_different_base_or_target(self):
        for p, value in ((TEXT + 4, 0xf9400020), (RELOCS + 12, 2 | 2 << 25 | 1 << 27 | 9 << 28)):
            b = fixture()
            struct.pack_into('<I', b, p, value)
            self.bad(obj=b)

    def test_wrong_backing_destination(self):
        b = fixture()
        struct.pack_into('<I', b, DRELOCS + 12, 1 | 3 << 25 | 1 << 27)
        self.bad(obj=b)

    def test_wrong_data_and_extent_or_kind(self):
        for field, value, fmt in ((DATA, 0, '<B'), (SECTIONS + 160 + 40, 2, '<Q'),
                                  (SECTIONS + 160 + 64, 0x12, '<I')):
            b = fixture(True)
            struct.pack_into(fmt, b, field, value)
            self.bad(image=b)

    def test_key_thunk_offset_state(self):
        for linked in (False, True):
            for offset in (0, 8, 16):
                b = fixture(linked)
                struct.pack_into('<Q', b, DESC + offset, 1)
                self.bad(image=b) if linked else self.bad(obj=b)

    def test_wrong_field_offset(self):
        b = fixture()
        struct.pack_into('<i', b, DRELOCS + 8, 8)
        self.bad(obj=b)

    def test_descriptor_wrong_width_type_or_addend(self):
        for word in (3 | 2 << 25 | 1 << 27, 3 | 3 << 25 | 1 << 27 | 1 << 28,
                     3 | 3 << 25):
            b = fixture()
            struct.pack_into('<I', b, DRELOCS + 4, word)
            self.bad(obj=b)

    def test_wrong_bootstrap_name_ordinal_library(self):
        for stream in (STREAM.replace(b'bootstrap', b'bootstraq'), b'\x12' + STREAM[1:],
                       STREAM.replace(b'\x40', b'\x41', 1)):
            self.bad(image=fixture(True, stream=stream))
        b = fixture(True)
        b[32 + 72 + 240 + 24 + 24] = ord('x')
        self.bad(image=b)
        b = fixture(True)
        struct.pack_into('<H', b, SYMS + 3 * 16 + 6, 512)
        self.bad(image=b)

    def test_bind_wrong_field_duplicate_unknown_truncated(self):
        for stream in (STREAM[:-1], STREAM[:-2] + b'\x90\x90\x00',
                       STREAM[:-2] + b'\xd0\x00', STREAM.replace(b'\x90\x40', b'\x98\x40'),
                       STREAM.replace(b'\x60\x00', b'\x60\x01'),
                       STREAM.replace(b'\x51', b'\x52')):
            self.bad(image=fixture(True, stream=stream))

    def test_uleb_overflow_noncanonical_and_truncation(self):
        prefix = STREAM[:STREAM.index(b'\x70') + 1]
        for tail in (b'\x80', b'\x90\xc0\x00\x90\x00', b'\xff' * 10 + b'\x00\x90\x00'):
            self.bad(image=fixture(True, stream=prefix + tail))

    def test_unsupported_chained_rebase_weak_lazy(self):
        b = fixture(True)
        struct.pack_into('<I', b, INFO, 0x80000034)
        self.bad(image=b)
        for offset in (12, 28, 36):
            b = fixture(True)
            struct.pack_into('<I', b, INFO + offset, 1)
            self.bad(image=b)

    def test_duplicate_descriptor_definition_and_wrong_section(self):
        for p, fmt, value in ((SYMS + 2 * 16, '<I', 8),  # _tls string offset
                              (SYMS + 2 * 16 + 5, '<B', 2),
                              (SECTIONS + 80 + 64, '<I', 0)):
            b = fixture()
            struct.pack_into(fmt, b, p, value)
            self.bad(obj=b)

    def test_section_overlap_and_truncated_descriptor(self):
        for p, fmt, value in ((SECTIONS + 160 + 32, '<Q', DESC),
                              (SECTIONS + 160 + 48, '<I', DESC),
                              (SECTIONS + 80 + 40, '<Q', 16)):
            b = fixture(True)
            struct.pack_into(fmt, b, p, value)
            self.bad(image=b)

    def test_bind_stream_overlap_and_segment_mapping(self):
        b = fixture(True)
        struct.pack_into('<I', b, INFO + 16, DESC)
        self.bad(image=b)
        b = fixture(True)
        struct.pack_into('<Q', b, 32 + 40, 16)
        self.bad(image=b)

    def test_metadata_aliases_and_duplicate_relocation(self):
        for field, value in ((SECTIONS + 80 + 56, RELOCS),
                             (SECTIONS + 160 + 48, SYMS),
                             (SECTIONS + 80 + 48, STRINGS)):
            b = fixture()
            struct.pack_into('<I', b, field, value)
            self.bad(obj=b)
        b = fixture()
        struct.pack_into('<i', b, RELOCS + 8, 0)
        self.bad(obj=b)

    def test_bind_metadata_overlap(self):
        for offset in (40, SYMS, STRINGS):
            b = fixture(True)
            struct.pack_into('<I', b, INFO + 16, offset)
            self.bad(image=b)

    def test_classic_auxiliary_metadata_rejected_not_aliased(self):
        commands = [
            struct.pack('<4I', 0x80000033, 16, 0xfffffff0, 32),
            struct.pack('<4I', 0x80000033, 16, DATA, 4)]
        dynamic = bytearray(80)
        struct.pack_into('<II', dynamic, 0, 0xb, 80)
        struct.pack_into('<II', dynamic, 56, BIND, 1)
        commands.append(dynamic)
        for command in commands:
            with self.subTest(command=bytes(command).hex()):
                image = fixture(True)
                count, size = struct.unpack_from('<II', image, 16)
                image[32 + size:32 + size + len(command)] = command
                struct.pack_into('<II', image, 16, count + 1, size + len(command))
                self.bad(image=image)
        image = fixture(True)
        struct.pack_into('<II', image, INFO + 40, DATA, 4)
        self.bad(image=image)

    def test_unknown_multi_template_and_absolute_offset(self):
        b = fixture(True)
        struct.pack_into('<I', b, SECTIONS + 64, 0x80000011)
        self.bad(image=b)
        b = fixture(True)
        struct.pack_into('<Q', b, DESC + 16, BASE + DATA)
        self.bad(image=b)

    def test_duplicate_info_and_overlapping_segments(self):
        for command in (fixture(True)[INFO:INFO + 48],
                        fixture(True)[32:32 + 72]):
            b = fixture(True)
            command = bytearray(command)
            if len(command) == 72:
                struct.pack_into('<I', command, 4, 72)
                struct.pack_into('<I', command, 64, 0)
            count, size = struct.unpack_from('<II', b, 16)
            b[32 + size:32 + size + len(command)] = command
            struct.pack_into('<II', b, 16, count + 1, size + len(command))
            self.bad(image=b)

    def test_duplicate_bootstrap_or_weak_definition(self):
        for field, fmt, value in ((SYMS + 2 * 16, '<I', 22),  # bootstrap string offset
                                   (SYMS + 16 + 6, '<H', 0x80)):
            b = fixture()
            struct.pack_into(fmt, b, field, value)
            self.bad(obj=b)
        b = fixture(True)
        struct.pack_into('<I', b, 24, 0x180)
        self.bad(image=b)

    def test_truncated_bytes(self):
        for end in (10, 80, DESC + 10, BIND + len(STREAM) - 1):
            self.bad(image=fixture(True)[:end])

    def test_forged_function_or_relocation_record(self):
        obj, image = tls.MachO(bytes(fixture())), tls.MachO(bytes(fixture(True)))
        of, lf = obj.function(b'_entry'), image.function(b'_entry')
        reloc = obj.relocations(of)[0]
        with self.assertRaises(ValueError):
            tls.attest_tlvp(obj, image, dict(of, code=bytes(8)), lf, reloc)
        with self.assertRaises(ValueError):
            tls.attest_tlvp(obj, image, of, lf, dict(reloc, target=2))


if __name__ == '__main__':
    unittest.main()
