"""Synthetic physical-byte controls; no compiler, game or provenance admission."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('_test_physical', Path(__file__).with_name('physical_link_map.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def macho(names=(b'_left',), kind=1, address=0, section=b'__data', flags=0, size=32):
    strings, rows = b'\0', b''
    for i, name in enumerate(names):
        rows += struct.pack('<IBBHQ', len(strings), 0xf, 1, 0, address + i * 8)
        strings += name + b'\0'
    end = 32 + 152 + 24
    header = struct.pack('<IiiIIIII', 0xfeedfacf, 0x100000c, 0, kind, 2, 176, 0, 0)
    segment = struct.pack('<II16sQQQQiiII', 0x19, 152, b'__DATA', address, size, end, size, 3, 3, 1, 0)
    sec = struct.pack('<16s16sQQIIIIIIII', section, b'__DATA', address, size, end, 3, 0, 0, flags, 0, 0, 0)
    syms = struct.pack('<IIIIII', 2, 24, end + size, len(names), end + size + len(rows), len(strings))
    return header + segment + sec + syms + bytes(size) + rows + strings


def ar(bodies, name=b'dup\xff.o'):
    data = b'!<arch>\n'
    for body in bodies:
        header = (name + b'/').ljust(16) + b'0'.ljust(12) + b'0'.ljust(6) + b'0'.ljust(6) + b'644'.ljust(8) + str(len(body)).encode().ljust(10) + b'`\n'
        data += header + body + (b'\n' if len(body) % 2 else b'')
    return data


def linkmap(rows=(), indices=(7, 91), path=b'/owned/lib\xff.a', member=b'dup\xff.o'):
    return (b'# Object files:\n[0] linker synthesized\n'
            + b''.join(b'[%d] ' % i + path + b'(' + member + b')\n' for i in indices)
            + b'# Symbols:\n# Address Size File Name\n'
            + b''.join(b'0x%x 0x%x [%d] %s\n' % r for r in rows)
            + b'# Dead Stripped Symbols:\n<<dead>> 0x8 [7] _left\n')


class PhysicalTests(unittest.TestCase):
    def resolve(self, blob, data):
        return p.resolve_archive_group(blob, data, b'/owned/lib\xff.a', b'dup\xff.o')

    def test_sparse_non_utf8_and_reversed_physical_selection(self):
        blob = ar([macho((b'_left\xff',)), macho((b'_right',))])
        result = self.resolve(blob, linkmap([(4096, 8, 7, b'_right'), (4104, 8, 91, b'_left\xff')]))
        members = p.archive.arm64_archive_members(blob)
        self.assertEqual(result[7]['member_header_offset'], members[1]['offset'])
        self.assertEqual(result[91]['member_header_offset'], members[0]['offset'])
        self.assertEqual(result[91]['witnesses'], [b'_left\xff'.hex()])
        self.assertEqual(list(p.indexed_objects(linkmap())), [0, 7, 91])

    def test_invalid_object_ids(self):
        data = linkmap()
        for bad in (data.replace(b'[91]', b'[7]'), data.replace(b'[91]', b'[-1]'), data.replace(b'[91]', b'[x]')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.indexed_objects(bad)

    def test_fat32_absolute_member_offsets(self):
        blob = ar([macho(), macho((b'_right',))])
        fat = struct.pack('>IIiiIII', 0xcafebabe, 1, 0x100000c, 0, 32, len(blob), 3) + bytes(4) + blob
        result = self.resolve(fat, linkmap([(4096, 8, 7, b'_left'), (4104, 8, 91, b'_right')]))
        self.assertEqual(result[7]['member_header_offset'], 40)

    def test_absent_dead_only_contradictory_reused_and_first_member_shortcut_reject(self):
        blob = ar([macho(), macho((b'_right',))])
        for rows in ([], [(4096, 8, 7, b'_unknown')],
                     [(4096, 8, 7, b'_left'), (4104, 8, 7, b'_right')],
                     [(4096, 8, 7, b'_left'), (4104, 8, 91, b'_left')],
                     [(4096, 8, 7, b'_left')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.resolve(blob, linkmap(rows))
        with self.assertRaises(ValueError):
            self.resolve(blob, linkmap(indices=(7,), path=b'/wrong/lib.a'))

    def test_shared_external_constraint_and_unknown_local_names(self):
        blob = ar([macho((b'_left', b'_shared')), macho((b'_right', b'_shared')),
                   macho((b'_third', b'_other'))])
        good = [(4096, 8, 7, b'_left'), (4104, 8, 7, b'_shared'), (4112, 8, 7, b'local-only')]
        self.assertIn(7, self.resolve(blob, linkmap(good, indices=(7,))))
        with self.assertRaises(ValueError):
            self.resolve(blob, linkmap(good + [(4120, 8, 7, b'_other')], indices=(7,)))
        # A nonunique external name still constrains selection even without a witness.
        blob = ar([macho((b'_left',)), macho((b'_right', b'_shared')), macho((b'_third', b'_shared'))])
        with self.assertRaises(ValueError):
            self.resolve(blob, linkmap(good[:2], indices=(7,)))

    def test_all_unique_witnesses_agree(self):
        blob = ar([macho((b'_left', b'_second')), macho((b'_right',))])
        result = self.resolve(blob, linkmap([(4096, 8, 7, b'_left'), (4104, 8, 7, b'_second')], indices=(7,)))
        self.assertEqual(result[7]['witnesses'], [b'_left'.hex(), b'_second'.hex()])

    def test_single_member_requires_exactly_one_index(self):
        blob = ar([macho()])
        self.assertIn(7, self.resolve(blob, linkmap(indices=(7,))))
        with self.assertRaises(ValueError):
            self.resolve(blob, linkmap())

    def test_selected_definition_positive_and_fail_closed(self):
        obj, image = macho(), p.generic.MachO(macho(kind=2, address=4096))
        data = linkmap([(4096, 8, 7, b'_left')], indices=(7,))
        result = p.selected_definition(data, image, {7: obj}, b'_left')
        self.assertEqual(result['binding']['object_index'], 7)
        self.assertEqual(result['object'].data, obj)
        cases = [(data, image, {91: obj}),
                 (data.replace(b'0x1000', b'0x1001'), image, {7: obj}),
                 (linkmap(indices=(7,)), image, {7: obj}),
                 (data, image, {7: macho((b'_wrong',))}),
                 (data, p.generic.MachO(macho((b'_wrong',), kind=2, address=4096)), {7: obj}),
                 (data, image, {7: macho(section=b'__other')}),
                 (data.replace(b'0x8', b'0x40'), image, {7: obj}),
                 (data, object(), {7: obj}),
                 (data, image, {7: macho((b'_left', b'_left'))}),
                 (data, p.generic.MachO(macho((b'_left', b'_left'), kind=2, address=4096)), {7: obj}),
                 (data, image, {7: macho((), size=32)}),
                 (data, image, {7: macho(flags=0x13)}),
                 (data.replace(b'0x8', b'0x0'), image, {7: obj})]
        for m, im, objects in cases:
            with self.subTest(objects=objects.keys()), self.assertRaises(ValueError):
                p.selected_definition(m, im, objects, b'_left')

    def test_span_cannot_cross_next_symbol(self):
        data = linkmap([(4096, 16, 7, b'_left')], indices=(7,))
        with self.assertRaises(ValueError):
            p.selected_definition(data, p.generic.MachO(macho((b'_left', b'_next'), kind=2, address=4096)), {7: macho()}, b'_left')


if __name__ == '__main__':
    unittest.main()
