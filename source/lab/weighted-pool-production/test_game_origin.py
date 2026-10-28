"""Hermetic synthetic Mach-O/ar controls; no compiler, linker or native execution."""
import ast
from pathlib import Path
import struct
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import game_origin as g

RUN = b'_sb_wp_run'
COUNT = b'_sb_wp_count'
EH = b'_rust_eh_personality'
HELPER = b'_helper'
OWNER = b'__ZN4Star22RustWeightedPoolDetail5Frame3runEjj'
BASE = 0x100000000
RET = 0xd65f03c0


def branch(start, target, link=True):
    assert (target - start) % 4 == 0
    return (0x94000000 if link else 0x14000000) | (((target - start) // 4) & 0x3ffffff)


def macho(kind, words, symbols, relocations=()):
    """One __text section with externally defined, individually bounded symbols."""
    text = struct.pack('<' + 'I' * len(words), *words)
    addr = BASE if kind == 2 else 0
    command_size = 152 + 24
    textoff = 32 + command_size
    reloff = textoff + len(text)
    reloc = b''.join(struct.pack('<iI', offset, target | (pc << 24) | (2 << 25) | (1 << 27) | (typ << 28))
                     for offset, typ, target, pc in relocations)
    symoff = reloff + len(reloc)
    strings = b'\0'
    table = b''
    for name, offset in symbols:
        table += struct.pack('<IBBHQ', len(strings), 0xf, 1, 0, addr + offset)
        strings += name + b'\0'
    stroff = symoff + len(table)
    header = struct.pack('<IiiIIIII', 0xfeedfacf, 0x100000c, 0, kind, 2, command_size, 0, 0)
    segment = struct.pack('<II16sQQQQiiII', 0x19, 152, b'__TEXT', addr, len(text), textoff, len(text), 7, 5, 1, 0)
    section = struct.pack('<16s16sQQIIIIIIII', b'__text', b'__TEXT', addr, len(text), textoff, 2,
                          reloff, len(relocations), 0x80000400, 0, 0, 0)
    symtab = struct.pack('<IIIIII', 2, 24, symoff, len(symbols), stroff, len(strings))
    return header + segment + section + symtab + text + reloc + table + strings


def archive(*objects):
    data = b'!<arch>\n'
    for obj in objects:
        header = b'fixture.o/      ' + b'0           ' + b'0     ' + b'0     ' + b'100644  ' + str(len(obj)).encode().ljust(10) + b'`\n'
        assert len(header) == 60
        data += header + obj + (b'\n' if len(obj) % 2 else b'')
    return data


def fixtures():
    obj = macho(1, [0x94000000, RET, RET, RET, RET],
                [(RUN, 0), (COUNT, 8), (EH, 12), (HELPER, 16)], [(0, 2, 3, 1)])
    image = macho(2, [branch(0, 8), RET, branch(8, 24), RET, RET, RET, RET],
                  [(OWNER, 0), (RUN, 8), (COUNT, 16), (EH, 20), (HELPER, 24)])
    return obj, image


class GameOriginTests(unittest.TestCase):
    def test_positive_archive_code_and_native_call(self):
        obj, image = fixtures()
        report = g.attest(image, archive(obj))
        self.assertTrue(report['complete'], report)
        self.assertEqual(len(report['functions']), 3)
        self.assertEqual(report['game_sha256'], g.sha(image))
        edge = report['native_call_edges'][0]
        self.assertEqual(edge['instruction_address'], BASE)
        self.assertEqual(edge['target_address'], BASE + 8)
        self.assertEqual(edge['kind'], 'BL')
        run = report['functions'][0]
        self.assertEqual(run['relocations'][0]['mask'], '0x3ffffff')
        self.assertEqual(run['member_header_offset'], 8)

    def test_modified_nonrelocated_instruction_rejected(self):
        obj, image = fixtures()
        bad = bytearray(image)
        bad[32 + 176 + 12:32 + 176 + 16] = struct.pack('<I', 0xd503201f)  # NOP replacing RET
        with self.assertRaisesRegex(ValueError, 'nonrelocated'):
            g.compare_function(g.MachO(obj), g.MachO(bytes(bad)), RUN)

    def test_relocated_call_to_wrong_target_rejected(self):
        obj, image = fixtures()
        bad = bytearray(image)
        struct.pack_into('<I', bad, 32 + 176 + 8, branch(8, 20))
        with self.assertRaisesRegex(ValueError, 'branch target differs'):
            g.compare_function(g.MachO(obj), g.MachO(bytes(bad)), RUN)

    def test_native_call_to_wrong_target_rejected(self):
        _, image = fixtures()
        bad = bytearray(image)
        struct.pack_into('<I', bad, 32 + 176, branch(0, 16))
        with self.assertRaisesRegex(ValueError, 'no direct native'):
            g.call_edges(g.MachO(bytes(bad)), RUN)

    def test_rust_self_call_is_not_native_edge(self):
        _, image = fixtures()
        image = image.replace(OWNER, b'R' * len(OWNER))
        with self.assertRaisesRegex(ValueError, 'no direct native'):
            g.call_edges(g.MachO(image), RUN)

    def test_wrong_symbol_rejected(self):
        obj, image = fixtures()
        with self.assertRaisesRegex(ValueError, 'exact function definition'):
            g.compare_function(g.MachO(obj), g.MachO(image), b'_sb_wp_run_typo')

    def test_duplicate_physical_provider_rejected(self):
        obj, image = fixtures()
        report = g.attest(image, archive(obj, obj))
        self.assertFalse(report['complete'])
        self.assertEqual(len(report['blockers']), 3)
        self.assertTrue(all('unique physical' in b['reason'] for b in report['blockers']))

    def test_unsupported_relocation_rejected(self):
        _, image = fixtures()
        obj = macho(1, [0x94000000, RET, RET, RET, RET],
                    [(RUN, 0), (COUNT, 8), (EH, 12), (HELPER, 16)], [(0, 9, 3, 0)])
        with self.assertRaisesRegex(ValueError, 'TLVP zero-addend LDR required'):
            g.compare_function(g.MachO(obj), g.MachO(image), RUN)

    def test_wrong_physical_provider_body_rejected(self):
        obj, image = fixtures()
        bad = bytearray(obj)
        struct.pack_into('<I', bad, 32 + 176 + 4, 0xd503201f)
        report = g.attest(image, archive(bytes(bad)))
        self.assertFalse(report['complete'])
        self.assertIn('nonrelocated', report['blockers'][0]['reason'])

    def test_tlvp_without_local_descriptor_stays_partial(self):
        _, image = fixtures()
        obj = macho(1, [0x94000000, RET, 0xf9400000, RET, RET],
                    [(RUN, 0), (COUNT, 8), (EH, 12), (HELPER, 16)],
                    [(0, 2, 3, 1), (8, 9, 3, 0)])
        bad = bytearray(image)
        struct.pack_into('<I', bad, 32 + 176 + 16, 0x913f8000)
        report = g.attest(bytes(bad), archive(obj))
        self.assertFalse(report['complete'])
        self.assertEqual(len(report['functions']), 2)
        self.assertTrue(report['native_call_edges'])
        self.assertIn('local object TLV descriptor required', report['blockers'][0]['reason'])

    def test_encoded_addend_is_not_arbitrarily_masked(self):
        obj, image = fixtures()
        bad = bytearray(obj)
        struct.pack_into('<I', bad, 32 + 176, 0x94000001)
        with self.assertRaisesRegex(ValueError, 'addend unsupported'):
            g.compare_function(g.MachO(bytes(bad)), g.MachO(image), RUN)

    def test_addend_relocation_rejected_without_target_indexing(self):
        obj, image = fixtures()
        bad = bytearray(obj)
        # ADDEND uses symbolnum as a signed addend, NOT as a symbol index.
        struct.pack_into('<I', bad, 32 + 176 + 20 + 4, (10 << 28) | (2 << 25) | 0xffffff)
        with self.assertRaisesRegex(g.UnsupportedRelocation, 'unsupported relocation type 10'):
            g.compare_function(g.MachO(bytes(bad)), g.MachO(image), RUN)

    def test_got_relaxation_is_not_supported_by_page_masks(self):
        for typ in (5, 6, 9, 10, 11):
            with self.subTest(typ=typ), self.assertRaisesRegex(ValueError, 'unsupported relocation type'):
                g.relocation_mask(0x90000000, dict(type=typ, length=2, external=1, pcrel=1))

    def test_apple_local_tlvp_rule_and_exact_target(self):
        obj = SimpleNamespace(symbols=[dict(type=0xf, section=1, name=b'_local_tlv',value=0)],
                              sections=[dict(flags=0x13,address=0,size=24)])
        image = SimpleNamespace(sections=[dict(flags=0x13,address=BASE+0xfe0,size=24)],
                                definitions=lambda name: [dict(section=1, value=BASE+0xfe0)] if name==b'_local_tlv' else [])
        reloc = dict(type=9, length=2, external=1, pcrel=0, target=0)
        self.assertEqual(g.local_tlvp_lea(obj, image, 0xf9400000, 0x913f8000, reloc), 0x91000000)
        for original, linked in [(RET,0x913f8000), (0xf9400400,0x913f8000),
                                 (0xf9400000,0x913f8001), (0xf9400000,0x913f7c00),
                                 (0xf9400000,0xf947f000)]:
            with self.subTest(original=original,linked=linked), self.assertRaises(ValueError):
                g.local_tlvp_lea(obj,image,original,linked,reloc)
        for field,value in [('external',0),('length',3),('pcrel',1)]:
            bad=dict(reloc);bad[field]=value
            with self.assertRaises(ValueError):g.local_tlvp_lea(obj,image,0xf9400000,0x913f8000,bad)
        for flags in [0,0x12]:
            obj.sections[0]['flags']=flags
            with self.assertRaisesRegex(ValueError,'object TLV'):g.local_tlvp_lea(obj,image,0xf9400000,0x913f8000,reloc)
        obj.sections[0]['flags']=0x13
        image.sections[0]['size']=23
        with self.assertRaisesRegex(ValueError,'descriptor address bounds'):g.local_tlvp_lea(obj,image,0xf9400000,0x913f8000,reloc)
        image.sections[0]['size']=24
        image.definitions=lambda name: []
        with self.assertRaisesRegex(ValueError,'linked TLV'):g.local_tlvp_lea(obj,image,0xf9400000,0x913f8000,reloc)

    def test_changed_opcode_not_masked(self):
        obj, image = fixtures()
        bad = bytearray(image)
        struct.pack_into('<I', bad, 32 + 176 + 8, branch(8, 24, link=False))
        with self.assertRaisesRegex(ValueError, 'nonrelocated'):
            g.compare_function(g.MachO(obj), g.MachO(bytes(bad)), RUN)

    def test_malformed_bounds_rejected(self):
        obj, _ = fixtures()
        for length in (0, 31, 100, len(obj) - 1):
            with self.subTest(length=length), self.assertRaises(ValueError):
                g.MachO(obj[:length])
        bad = bytearray(obj)
        struct.pack_into('<I', bad, 32 + 72 + 48, 0xffffffff)  # section file offset
        with self.assertRaisesRegex(ValueError, 'section data bounds'):
            g.MachO(bytes(bad))

    def test_external_pins_required(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'image'
            path.write_bytes(b'not executable')
            self.assertEqual(g.pinned(path, g.sha(b'not executable')), b'not executable')
            with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
                g.pinned(path, '0' * 64)
            with self.assertRaisesRegex(ValueError, 'external lowercase'):
                g.pinned(path, '')

    def test_no_execution_imports_or_shell_calls(self):
        # Structural guard complements the runtime tripwire; artifact bytes must
        # never become an argv or be handed to any native parser/tool.
        source = Path(g.__file__).read_text()
        tree = ast.parse(source)
        blocked_modules = {'subprocess', 'ctypes', 'os', 'pty', 'multiprocessing'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse({a.name.split('.')[0] for a in node.names} & blocked_modules)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], blocked_modules)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'eval', 'exec', 'compile', '__import__'})
        import subprocess
        obj, image = fixtures()
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('native execution forbidden')):
            self.assertTrue(g.attest(image, archive(obj))['complete'])

    def test_abi_masks_preserve_all_other_fields(self):
        for typ, word, pc, mask in ((2, 0x94000000, 1, 0x03ffffff),
                                    (3, 0x90000008, 1, 0x60ffffe0),
                                    (8, 0x90000008, 1, 0x60ffffe0),
                                    (4, 0x91000108, 0, 0x003ffc00),
                                    (4, 0xf9400108, 0, 0x003ffc00)):
            reloc = dict(type=typ, length=2, external=1, pcrel=pc)
            self.assertEqual(g.relocation_mask(word, reloc), mask)
        with self.assertRaisesRegex(ValueError, 'PAGEOFF12 encoding'):
            g.relocation_mask(RET, dict(type=4, length=2, external=1, pcrel=0))


if __name__ == '__main__':
    unittest.main()
