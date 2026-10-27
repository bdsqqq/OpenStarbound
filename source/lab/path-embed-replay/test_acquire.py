"""Pre-acquisition contract checks; real replay controls live in acquire.controls."""
import unittest
import acquire


class AcquisitionContract(unittest.TestCase):
    def test_recursive_numeric_types(self):
        for bad in (True, 1.0):
            with self.assertRaises(ValueError):
                acquire.equal({'nested': [bad]}, {'nested': [1]}, 'type mismatch')

    def test_reconstructed_membership(self):
        out = acquire.BASE / 'uncreated-test-fixture'
        rs, libs, jobs, sdk, plan, links = acquire.recipe(out)
        self.assertEqual(len(rs), 113)
        self.assertEqual(len(jobs), 121)
        self.assertEqual(len(links), 8)
        self.assertEqual(len({n for n, _ in plan}), len(plan))
        for variant, argv in links.items():
            self.assertEqual(argv[-1], '-Wl,-t,-trace_implicit_libraries')
            self.assertIn(str(out / 'links' / variant / 'native'), argv)
        self.assertEqual(len(acquire.contract.expected(
            b''.join((n + '\tleaf\t00\n').encode() for n, o, m, b in acquire.contract.cases()
                     if o == 'C' and m in (2, 3))).splitlines()), 357)
        required = acquire.artifact_paths(out, jobs, plan, links)
        self.assertIn(out / 'links/original/expanded-before.json', required)
        self.assertEqual(len([p for p in required if p.suffix == '.o']), 121)

    def test_owned_output(self):
        with self.assertRaises(ValueError):
            acquire.safe_root(acquire.ROOT / 'storage' / 'fixture', fresh=True)
        with self.assertRaises(ValueError):
            acquire.safe_root(acquire.BASE, fresh=True)


if __name__ == '__main__':
    unittest.main()
