"""Synthetic emitted-code controls only; no native build, game or archive proof."""
import ast
import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import game_origin as g

# Reuse unchanged literal Mach-O/ar generators, not old WeightedPool attest().
_spec = importlib.util.spec_from_file_location(
    'id_map_synthetic_generators', g.LAB / 'weighted-pool-production/test_game_origin.py')
f = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(f)
RUN, COUNT, EH = g.NAMES
OWNER = g.OWNER
HELPER = b'_helper'
RET = f.RET
NOP = 0xd503201f


def fixtures(owner=OWNER, owner_word=None, image_names=None, object_names=None, reloc_type=2):
    obj = f.macho(1, [0x94000000, RET, RET, RET, RET],
                  object_names or [(RUN, 0), (COUNT, 8), (EH, 12), (HELPER, 16)],
                  [(0, reloc_type, 3, 1)])
    image = f.macho(2, [f.branch(0, 8) if owner_word is None else owner_word,
                        RET, f.branch(8, 24), RET, RET, RET, RET],
                    image_names or [(owner, 0), (RUN, 8), (COUNT, 16), (EH, 20), (HELPER, 24)])
    return obj, image


class IdMapOriginTests(unittest.TestCase):
    def blocked(self, report, reason):
        self.assertFalse(report['complete'], report)
        self.assertTrue(any(reason in b['reason'] for b in report['blockers']), report)

    def test_positive_SYNTHETIC_emitted_code_only(self):
        obj, image = fixtures()
        report = g.attest(image, f.archive(obj))
        self.assertTrue(report['complete'], report)
        self.assertEqual(report['game_sha256'], g.sha(image))
        self.assertEqual(report['archive_sha256'], g.sha(f.archive(obj)))
        self.assertEqual(len(report['functions']), 3)
        self.assertEqual(len(report['providers']), 3)
        self.assertEqual(len(report['imported_helper_sha256']), 3)
        self.assertIn(str(g.GENERIC_PATH), report['imported_helper_sha256'])
        self.assertEqual(report['verifier_sha256'], g.sha(Path(g.__file__).read_bytes()))
        edge = report['native_call_edges'][0]
        self.assertEqual((edge['owner_hex'], edge['instruction_address'], edge['target_address']),
                         (OWNER.hex(), f.BASE, f.BASE + 8))
        self.assertEqual(edge['kind'], 'BL')
        for identity in report['functions']:
            self.assertEqual(identity['member_header_offset'], 8)
            self.assertEqual(identity['member_sha256'], g.sha(obj))
            self.assertEqual(identity['size'], identity['linked_end'] - identity['address'])
        self.assertEqual(report['functions'][0]['relocations'][0]['mask'], '0x3ffffff')

    def test_no_root_definition(self):
        obj, image = fixtures(image_names=[(OWNER, 0), (b'_other_run', 8),
                                          (COUNT, 16), (EH, 20), (HELPER, 24)])
        self.blocked(g.attest(image, f.archive(obj)), 'exact function definition')

    def test_not_MH_EXECUTE(self):
        obj, _ = fixtures()
        self.blocked(g.attest(obj, f.archive(obj)), 'MH_EXECUTE')

    def test_missing_archive_provider(self):
        obj, image = fixtures(object_names=[(RUN, 0), (b'_other_count', 8), (EH, 12), (HELPER, 16)])
        self.blocked(g.attest(image, f.archive(obj)), 'unique physical')

    def test_duplicate_EH_even_identical_bytes_and_duplicate_member_names(self):
        obj, image = fixtures()
        extra = f.macho(1, [RET], [(EH, 0)])
        report = g.attest(image, f.archive(obj, extra, extra))
        self.blocked(report, 'unique physical')
        provider = next(p for p in report['providers'] if p['name_hex'] == EH.hex())
        self.assertEqual(len(provider['members']), 3)
        self.assertEqual(len({m['member_header_offset'] for m in provider['members']}), 3)

    def test_spoof_count_cpp_symbol_same_bytes_is_not_provider(self):
        obj, image = fixtures(object_names=[(RUN, 0), (b'__Z14sb_idmap_countjj', 8),
                                           (EH, 12), (HELPER, 16)])
        self.blocked(g.attest(image, f.archive(obj)), 'unique physical')

    def test_no_exact_owner_substring_or_lambda(self):
        for name in (OWNER + b'.cold', b'__ZZN4Star15RustIdMapDetail5Frame3runEvENK3$_0clEv',
                     b'__ZN4Star22RustWeightedPoolDetail5Frame3runEjj'):
            with self.subTest(name=name):
                obj, image = fixtures(owner=name)
                self.blocked(g.attest(image, f.archive(obj)), 'exact function definition')

    def test_rust_self_call_does_not_replace_native_edge(self):
        obj = f.macho(1, [0x94000000, RET, RET, RET, RET],
                      [(RUN, 0), (COUNT, 8), (EH, 12), (HELPER, 16)], [(0, 2, 0, 1)])
        image = f.macho(2, [RET, RET, f.branch(8, 8), RET, RET, RET, RET],
                        [(OWNER, 0), (RUN, 8), (COUNT, 16), (EH, 20), (HELPER, 24)])
        report = g.attest(image, f.archive(obj))
        self.assertEqual(len(report['functions']), 3, report)
        self.blocked(report, 'no direct native')

    def test_unknown_relocations_including_TLVP_fail_original_exception(self):
        for typ in (0, 5, 6, 7, 9, 10, 11, 15):
            with self.subTest(typ=typ):
                obj, image = fixtures(reloc_type=typ)
                with self.assertRaises(g._generic.UnsupportedRelocation):
                    g.strict_compare(g._generic.MachO(obj), g._generic.MachO(image), RUN)
                report = g.attest(image, f.archive(obj))
                self.blocked(report, 'unsupported relocation type')
                blocker = next(b for b in report['blockers'] if 'unsupported_relocation' in b)
                self.assertEqual(blocker['unsupported_relocation']['type'], typ)

    def test_duplicate_image_definitions_all_three(self):
        for name, offset in ((RUN, 8), (COUNT, 16), (EH, 20)):
            with self.subTest(name=name):
                obj, image = fixtures(image_names=[(OWNER, 0), (RUN, 8), (COUNT, 16),
                                                  (EH, 20), (HELPER, 24), (name, offset)])
                self.blocked(g.attest(image, f.archive(obj)), 'exact function definition')

    def test_duplicate_archive_providers_all_three(self):
        obj, image = fixtures()
        report = g.attest(image, f.archive(obj, obj))
        self.blocked(report, 'unique physical')
        self.assertEqual(len(report['blockers']), 3)

    def test_reused_bytes_wrong_symbol_not_code_credit(self):
        obj, image = fixtures(object_names=[(b'_reused_run', 0), (COUNT, 8), (EH, 12), (HELPER, 16)])
        self.blocked(g.attest(image, f.archive(obj)), 'unique physical')

    def test_wrong_native_destination(self):
        obj, image = fixtures(owner_word=f.branch(0, 16))
        self.blocked(g.attest(image, f.archive(obj)), 'no direct native')

    def test_unrelated_function_branch_outside_owner_extent(self):
        obj, image = fixtures(owner_word=RET,
                              image_names=[(OWNER, 0), (b'_unrelated', 4), (RUN, 8),
                                           (COUNT, 16), (EH, 20), (HELPER, 24)])
        bad = bytearray(image)
        struct.pack_into('<I', bad, 32 + 176 + 4, f.branch(4, 8))
        self.blocked(g.attest(bytes(bad), f.archive(obj)), 'no direct native')

    def test_B_tail_edge_and_backward_branch_decode(self):
        obj, image = fixtures(owner_word=f.branch(0, 8, link=False))
        report = g.attest(image, f.archive(obj))
        self.assertTrue(report['complete'], report)
        self.assertEqual(report['native_call_edges'][0]['kind'], 'B')
        self.assertEqual(g._generic.branch_destination(f.branch(24, 8), f.BASE + 24), f.BASE + 8)

    def test_nonrelocated_bytes_and_relocated_target_remain_checked(self):
        obj, image = fixtures()
        for offset, word, reason in ((12, NOP, 'nonrelocated'),
                                     (8, f.branch(8, 20), 'branch target differs')):
            with self.subTest(offset=offset):
                bad = bytearray(image)
                struct.pack_into('<I', bad, 32 + 176 + offset, word)
                self.blocked(g.attest(bytes(bad), f.archive(obj)), reason)

    def test_count_and_personality_are_compared_not_just_membership(self):
        obj, image = fixtures()
        for name, offset in ((COUNT, 16), (EH, 20)):
            with self.subTest(name=name):
                bad = bytearray(image)
                struct.pack_into('<I', bad, 32 + 176 + offset, NOP)
                report = g.attest(bytes(bad), f.archive(obj))
                self.blocked(report, 'nonrelocated')
                self.assertTrue(any(b.get('name_hex') == name.hex() for b in report['blockers']))

    def test_duplicate_owner_and_folded_alias_fail_closed(self):
        for extra in ((OWNER, 0), (b'_folded_owner', 0), (b'_folded_run', 8)):
            with self.subTest(extra=extra):
                obj, image = fixtures(image_names=[(OWNER, 0), (RUN, 8), (COUNT, 16),
                                                  (EH, 20), (HELPER, 24), extra])
                self.assertFalse(g.attest(image, f.archive(obj))['complete'])

    def test_malformed_inputs_and_fixed_size_bound(self):
        obj, image = fixtures()
        for game, archive in ((b'', f.archive(obj)), (image, b'!<arch>\ntruncated'),
                              (bytearray(image), f.archive(obj))):
            with self.subTest(game_type=type(game), archive_size=len(archive)):
                self.assertFalse(g.attest(game, archive)['complete'])
        # A small patched limit exercises the same pre-parser bound without
        # allocating a resource-bomb fixture; production constant is fixed.
        self.assertEqual(g.MAX_INPUT_BYTES, 128 * 1024 * 1024)
        with patch.object(g, 'MAX_INPUT_BYTES', 32):
            self.blocked(g.attest(image, f.archive(obj)), '128 MiB')

    def test_no_old_attestation_or_execution_capability(self):
        tree = ast.parse(Path(g.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse({a.name for a in node.names} & {'subprocess', 'ctypes', 'os', 'pty'})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, ('attest', 'call_edges', 'local_tlvp_lea'))
        obj, image = fixtures()
        old_attest, old_edges = g._generic.attest, g._generic.call_edges
        self.assertTrue(g.attest(image, f.archive(obj))['complete'])
        self.assertIs(g._generic.attest, old_attest)
        self.assertIs(g._generic.call_edges, old_edges)


if __name__ == '__main__':
    unittest.main()
