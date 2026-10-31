"""Guarded production projection: preserve native OFF, share one typed host."""
import importlib.util
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('_bimap_production_generator', HERE / 'generate_core.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def restore_native(header):
    for signature, old, new in g.bodies():
        prefix = signature + ' {\n'
        guarded = (prefix + '#ifdef STAR_USE_RUST_BIMAP\n' + new[len(prefix):-2]
                   + '\n#else\n' + old[len(prefix):-2] + '\n#endif\n}')
        header = g.unique_replace(header, guarded, old)
    return g.unique_replace(header, '#include "StarString.hpp"\n#ifdef STAR_USE_RUST_BIMAP\n#include "StarBiMapHost.hpp"\n#endif', '#include "StarString.hpp"')


class ProductionTests(unittest.TestCase):
    def test_all_twenty_one_native_bodies_and_fields_restored_exactly(self):
        self.assertEqual(len(g.bodies()), 21)
        header = (ROOT / 'source/core/StarBiMap.hpp').read_text()
        self.assertEqual(restore_native(header), (HERE / 'StarBiMap.original.hpp').read_text())

    def test_known_field_and_native_branch_drift_detected(self):
        header = (ROOT / 'source/core/StarBiMap.hpp').read_text()
        original = (HERE / 'StarBiMap.original.hpp').read_text()
        field = header.replace('  LeftMap m_leftMap;', '  LeftMap m_leftMap;\n  unsigned unexpected;')
        self.assertNotEqual(restore_native(field), original)
        wrong = header.replace('  return m_leftMap.empty();\n#endif', '  return false;\n#endif')
        with self.assertRaises(ValueError):
            restore_native(wrong)

    def test_single_host_implementation(self):
        shim = (HERE / 'frame.hpp').read_text()
        self.assertIn('#include "../../core/StarBiMapHost.hpp"', shim)
        self.assertNotIn('struct Frame', shim)
        host = (ROOT / 'source/core/StarBiMapHost.hpp').read_text()
        self.assertEqual(host.count('struct Frame {'), 1)
        self.assertIn('exception = std::current_exception();', host)
        self.assertIn('if (exception) std::rethrow_exception(exception);', host)

    def test_default_off_and_existing_aggregate(self):
        cmake = (ROOT / 'source/CMakeLists.txt').read_text()
        options = re.findall(r'option\(STAR_USE_RUST_BIMAP "[^"\n]+" (ON|OFF)\)', cmake)
        self.assertEqual(options, ['OFF'])
        gates = re.findall(r'^if\(([^\n]+)\)\n  include\(Rust\)\nendif\(\)', cmake, re.M)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].split(' OR ').count('STAR_USE_RUST_BIMAP'), 1)
        self.assertEqual(cmake.count('if(STAR_USE_RUST_BIMAP)\n  add_compile_definitions(STAR_USE_RUST_BIMAP)\nendif()'), 1)


if __name__ == '__main__':
    unittest.main()
