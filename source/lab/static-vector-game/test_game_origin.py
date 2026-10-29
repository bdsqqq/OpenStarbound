"""Synthetic byte/provider guards; NOT emitted-code qualification."""
import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('_sv_code_test', Path(__file__).with_name('game_origin.py'))
code = importlib.util.module_from_spec(spec)
spec.loader.exec_module(code)


class CodeTests(unittest.TestCase):
    def test_unique_all_five_providers_and_duplicate_runtime(self):
        members = [dict(body=b'\xcf\xfa\xed\xfe' + bytes([i]), offset=i, name=b'object', sha256=str(i)) for i in range(5)]
        definitions = {m['body']: {n} for m, n in zip(members, code.NAMES)}
        with patch.object(code.archive_identity, 'members', return_value=members), patch.object(code.archive_identity, 'external_definitions', side_effect=lambda b: definitions[b]):
            self.assertEqual(set(code.providers(b'fixture')), set(code.NAMES))
            members.append(dict(members[-1], offset=99))
            with self.assertRaises(ValueError):
                code.providers(b'fixture')

    def test_missing_provider_and_bad_archive(self):
        with self.assertRaises(ValueError):
            code.providers(b'not an archive')
        with patch.object(code.archive_identity, 'members', return_value=[]):
            with self.assertRaises(ValueError):
                code.providers(b'fixture')

    def test_predeclared_native_owners_not_arbitrary_wrappers(self):
        self.assertTrue(code.allowed_owner(code.WORLD_RENDER + b'ERNS_6RenderE', code.NAMES[0]))
        self.assertTrue(code.allowed_owner(b'__ZN4Star23TileSectorArrayObserver8snapshotEv', code.NAMES[1]))
        self.assertFalse(code.allowed_owner(b'__ZN4Star15UnrelatedHelper3runEv', code.NAMES[0]))
        self.assertFalse(code.allowed_owner(b'__ZN4Star12StaticVector3runEv', code.NAMES[0]))

    def test_missing_native_edge_blocks(self):
        class Image:
            symbols = []
            def function(self, name):
                return dict(start=16, end=20, code=struct.pack('<I', 0xd503201f))
        with self.assertRaisesRegex(ValueError, 'WorldClient'):
            code.native_edges(Image(), Image())

    def test_tlvp_missing_data_origin_blocks_even_if_generic_code_matches(self):
        class Object:
            def function(self, name):
                return dict(start=0, code=struct.pack('<I', 0x90000000))
            def relocations(self, function):
                return [dict(type=8, offset=0)]
        with patch.object(code.base, 'strict_compare', return_value={'normalized': 'matches'}), \
             patch.object(code.tls, 'attest_tlvp', side_effect=ValueError('unsupported physical origin')):
            with self.assertRaisesRegex(ValueError, 'UNAVAILABLE_TLVP_DATA_ORIGIN'):
                code.strict_compare(Object(), Object(), b'_function')

    def test_real_byte_tls_bridge_and_modified_data_rejected(self):
        from test_tls_data_origin import fixture, DATA
        obj = code.MachO(bytes(fixture()))
        image = code.MachO(bytes(fixture(True)))
        result = code.strict_compare(obj, image, b'_entry')
        self.assertEqual(len(result['tls_data_origins']), 2)
        self.assertEqual({p['relocation_type'] for p in result['tls_data_origins']}, {8, 9})
        self.assertEqual(result['tls_data_origins'][0]['proof']['bootstrap_fixup']['ordinal'], 1)
        changed = fixture(True)
        changed[DATA] ^= 1
        with self.assertRaisesRegex(ValueError, 'UNAVAILABLE_TLVP_DATA_ORIGIN.*initial bytes'):
            code.strict_compare(obj, code.MachO(bytes(changed)), b'_entry')

    def test_page_target_origin_not_just_masked_instruction(self):
        class Object:
            symbols = [{'name': b'_data'}]
            def function(self, name):
                return dict(start=0x1000, code=struct.pack('<I', 0x90000000))
            def relocations(self, function):
                return [dict(type=3, external=1, target=0, offset=0)]
            def definitions(self, name):
                return [{'value': 0x3000}]
        with patch.object(code.base, 'strict_compare', return_value={'normalized': 'matches'}):
            with self.assertRaisesRegex(ValueError, 'PAGE21'):
                code.strict_compare(Object(), Object(), b'_function')

    def test_strict_unknown_relocation_is_not_waived(self):
        class Object:
            symbols = []
            def function(self, name):
                return dict(start=0, end=4, code=struct.pack('<I', 0xd503201f))
            def relocations(self, function):
                return [dict(type=7, offset=0, external=False, target=0)]
        with self.assertRaises(ValueError):
            code.strict_compare(Object(), Object(), b'_fn')


if __name__ == '__main__':
    unittest.main()
