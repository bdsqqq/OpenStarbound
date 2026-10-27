"""Binary-structure fixtures, not executable or native-calibration evidence."""
import struct
import unittest
from archive_identity import arm64_archive_members, duplicate_witnesses, external_definitions, members


def object_file(names):
    strings = b'\0'
    rows = b''
    for name in names:
        rows += struct.pack('<IBBHQ', len(strings), 3, 0, 0, 0)  # external N_ABS
        strings += name + b'\0'
    header = struct.pack('<IiiIIIII', 0xfeedfacf, 0x0100000c, 0, 1, 1, 24, 0, 0)
    return header + struct.pack('<IIIIII', 2, 24, 56, len(names), 56 + len(rows), len(strings)) + rows + strings


def archive(objects, long_name=False):
    data = b'!<arch>\n'
    for body in objects:
        name = b'dup.o/'
        if long_name:
            name = b'#1/16'
            body = b'dup.o' + b'\0' * 11 + body
        header = name.ljust(16) + b'0'.ljust(12) + b'0'.ljust(6) + b'0'.ljust(6) + b'644'.ljust(8) + str(len(body)).encode().ljust(10) + b'`\n'
        data += header + body + (b'\n' if len(body) % 2 else b'')
    return data


def map_file(rows):
    return (b'# Object files:\n[0] linker synthesized\n[1] /owned/lib.a(dup.o)\n[2] /owned/lib.a(dup.o)\n'
            b'# Symbols:\n# Address Size File Name\n'
            + b''.join(b'0x1000 0x8 [%d] %s\n' % row for row in rows)
            + b'# Dead Stripped Symbols:\n<<dead>> 0x8 [1] _not_a_live_witness\n')


class ArchiveIdentityTests(unittest.TestCase):
    def identify(self, blob, rows):
        return duplicate_witnesses(blob, map_file(rows), b'/owned/lib.a', b'dup.o')

    def test_physical_members_have_distinct_live_witnesses(self):
        for long_name in (False, True):
            blob = archive([object_file([b'_left\xff']), object_file([b'_right'])], long_name)
            actual = self.identify(blob, [(1, b'_left\xff'), (2, b'_right')])
            self.assertEqual([x['member_offset'] for x in actual], [x['offset'] for x in members(blob)])
            self.assertEqual([x['symbol'] for x in actual], [b'_left\xff', b'_right'])
            self.assertNotEqual(actual[0]['member_sha256'], actual[1]['member_sha256'])

    def test_shared_symbol_is_not_identity(self):
        blob = archive([object_file([b'_shared']), object_file([b'_shared'])])
        with self.assertRaisesRegex(ValueError, 'unique symbol witness'):
            self.identify(blob, [(1, b'_shared'), (2, b'_shared')])

    def test_contradictory_and_reused_member_witnesses_rejected(self):
        blob = archive([object_file([b'_left']), object_file([b'_right'])])
        for rows in [[(1, b'_left'), (1, b'_right'), (2, b'_right')],
                     [(1, b'_left'), (2, b'_left')], [(1, b'_left')]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.identify(blob, rows)

    def test_coherently_changed_member_cannot_keep_old_witness(self):
        blob = archive([object_file([b'_changed']), object_file([b'_right'])])
        with self.assertRaisesRegex(ValueError, 'unique symbol witness'):
            self.identify(blob, [(1, b'_left'), (2, b'_right')])

    def test_archive_truncation_header_size_and_name_bounds(self):
        valid = archive([object_file([b'_left'])], True)
        bad_header = bytearray(valid); bad_header[8 + 58] = 0
        bad_size = bytearray(valid); bad_size[8 + 48:8 + 58] = b'9999999999'
        bad_name = bytearray(valid); bad_name[8:8 + 16] = b'#1/999999'.ljust(16)
        for bad in [valid[:-1], bytes(bad_header), bytes(bad_size), bytes(bad_name), b'!<thin>\n']:
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                members(bad)

    def test_macho_command_symbol_and_string_bounds(self):
        valid = object_file([b'_left'])
        mutations = []
        for offset, value in [(36, 7), (40, 99999), (48, 99999), (56, 99999), (4, 0)]:
            bad = bytearray(valid);struct.pack_into('<I', bad, offset, value);mutations.append(bytes(bad))
        mutations += [valid[:-1], valid[:-1] + b'x']
        for bad in mutations:
            with self.subTest(data=bad[:16]), self.assertRaises(ValueError):
                external_definitions(bad)

    def test_fat_archive_selects_exact_slice_and_rejects_overlap(self):
        x86 = archive([object_file([b'_wrong'])])
        arm = archive([object_file([b'_right'])])
        first = 48
        second = (first + len(x86) + 7) // 8 * 8
        header = (struct.pack('>II', 0xcafebabe, 2)
                  + struct.pack('>iiIII', 0x01000007, 3, first, len(x86), 3)
                  + struct.pack('>iiIII', 0x0100000c, 0, second, len(arm), 3))
        data = header + x86 + b'\0' * (second - first - len(x86)) + arm
        selected = arm64_archive_members(data)
        self.assertEqual(external_definitions(selected[0]['body']), {b'_right'})
        self.assertEqual(selected[0]['offset'], second + 8)
        for offset, value in [(36, first), (32, 1), (44, 32), (4, 999999)]:
            bad = bytearray(data);struct.pack_into('>I', bad, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                arm64_archive_members(bytes(bad))

    def test_indirect_symbol_and_missing_live_table_rejected(self):
        bad = bytearray(object_file([b'_left']));bad[60] = 0x0b
        with self.assertRaisesRegex(ValueError, 'indirect'):
            external_definitions(bytes(bad))
        blob = archive([object_file([b'_left']), object_file([b'_right'])])
        with self.assertRaisesRegex(ValueError, 'live symbol table'):
            duplicate_witnesses(blob, map_file([]).replace(b'# Symbols:', b'# Other:'), b'/owned/lib.a', b'dup.o')


if __name__ == '__main__':
    unittest.main()
