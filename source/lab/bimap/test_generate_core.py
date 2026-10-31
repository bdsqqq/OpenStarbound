"""Source-generator controls only; no native compiler, process or adoption."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
G = ROOT / 'build/behavior/static-vector-combined-r1'
spec = importlib.util.spec_from_file_location('_bimap_core_generator_test', HERE / 'generate_core.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=G)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_exact_source_and_fixture_projections(self):
        out = self.root / 'generated'
        g.generate(out)
        m = json.loads((out / 'manifest.json').read_text())
        self.assertEqual(set(p.name for p in out.iterdir()),
                         {'manifest.json', 'candidate.cpp', 'StarBiMap.generated.hpp'})
        self.assertEqual(len(m['body_replacements']), 21)
        self.assertTrue(m['body_projection']['equal'])
        self.assertEqual(m['body_projection']['fixture_reverse_projection_sha256'], g.NATIVE_SHA)
        header = (out / 'StarBiMap.generated.hpp').read_text()
        self.assertIn('LeftMap m_leftMap;\n  RightMap m_rightMap;', header)
        self.assertIn('auto const& pair = *cursor;', header)
        self.assertIn('SB_BIMAP_MODE_EQUAL_PAIR', header)
        self.assertIn('SB_BIMAP_MODE_EQUAL_SCOPED_ENTRIES', header)
        self.assertNotIn('std::optional', header)
        self.assertEqual(m['support']['kind'], 'shim')
        self.assertEqual(m['support']['sha256'], g.SHIM_SHA)
        self.assertIn('#include "' + str(HERE / 'StarString.hpp') + '"', header)
        candidate = (out / 'candidate.cpp').read_text()
        self.assertIn('mode < SB_BIMAP_MODE_COUNT', candidate)

    def test_real_support_uses_pinned_absolute_production_include(self):
        out = self.root / 'real-support'
        g.generate(out, real_support=True)
        m = json.loads((out / 'manifest.json').read_text())
        production = ROOT / 'source/core/StarString.hpp'
        header = (out / 'StarBiMap.generated.hpp').read_text()
        self.assertIn('#include "' + str(production) + '"', header)
        self.assertNotIn('#include "' + str(HERE / 'StarString.hpp') + '"', header)
        digest = hashlib.sha256(production.read_bytes()).hexdigest()
        self.assertEqual(m['support'], {'kind': 'real', 'path': str(production), 'sha256': digest})
        self.assertIn({'path': str(production), 'sha256': digest}, m['inputs'])
        self.assertEqual(m['body_projection']['fixture_reverse_projection_sha256'], g.NATIVE_SHA)
        default = self.root / 'default-support'
        g.generate(default)
        self.assertEqual((out / 'candidate.cpp').read_bytes(), (default / 'candidate.cpp').read_bytes())

    def test_new_adapters_preserve_native_locals_and_return_expressions(self):
        replacements = {signature: (old, new) for signature, old, new in g.bodies()}
        base = 'BiMap<LeftT, RightT, LeftMapT, RightMapT>::'
        for side, key_type, key, native_map in [
            ('Right', 'Left', 'left', 'm_leftMap'),
            ('Left', 'Right', 'right', 'm_rightMap'),
        ]:
            value = side.lower()
            pointer = value + 'Ptr'
            with self.subTest(side=side):
                _, maybe = replacements[f'Maybe<{side}T> ' + base + f'maybe{side}({key_type} const& {key}) const']
                self.assertIn(f'  auto i = {native_map}.find({key});', maybe)
                self.assertIn(f'(bool)(i != {native_map}.end())', maybe)
                self.assertIn('if (frame.run(SB_BIMAP_MODE_PRESENT).value)\n    return *i->second;\n  return {};', maybe)
                _, take_maybe = replacements[f'Maybe<{side}T> ' + base + f'maybeTake{side}({key_type} const& {key})']
                self.assertIn(f'  auto {pointer} = {native_map}.maybeTake({key}).value();\n', take_maybe)
                self.assertIn(f'    {side} {value} = *{pointer};', take_maybe)
                self.assertIn(f'm_{value}Map.remove(*{pointer});', take_maybe)
                self.assertIn(f'remove.run(SB_BIMAP_MODE_REMOVE_TAKEN);\n    return {value};', take_maybe)
                _, take = replacements[f'{side}T ' + base + f'take{side}({key_type} const& {key})']
                self.assertIn(f'    auto {value} = maybeTake{side}({key});', take)
                self.assertIn(f'      return {value}.take();\n  }}\n  auto missing =', take)
                self.assertIn(f'throw MapException::format("No such key in BiMap::take{side}", outputAny({key}));', take)
                self.assertIn('missing.run(SB_BIMAP_MODE_THROW_TAKE);', take)
        _, pairs = replacements['auto ' + base + 'pairs() const -> List<value_type>']
        self.assertIn('auto const& p = *cursor;\n          values.append(p);', pairs)
        self.assertIn('frame.run(SB_BIMAP_MODE_PAIRS);\n  }\n  return values;', pairs)

    def test_stale_pin_rejected_before_output_creation(self):
        out = self.root / 'bad'
        with patch.object(g, 'FROZEN_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'byte pin mismatch'):
                g.generate(out)
        self.assertFalse(out.exists())

    def test_missing_or_ambiguous_source_replacement_rejected(self):
        for text, old in [('abc', 'missing'), ('aa', 'a')]:
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, 'match exactly once'):
                    g.unique_replace(text, old, 'replacement')

    def test_known_out_of_scope_fixture_mutation_detected_before_writes(self):
        original = g.unique_replace
        def mutate(text, old, new):
            result = original(text, old, new)
            if old == '  try { Fixture::cases(); return 0; }':
                result += '\n// isolated unauthorized fixture mutation\n'
            return result
        out = self.root / 'bad-projection'
        with patch.object(g, 'unique_replace', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'fixture projection drift'):
                g.generate(out)
        self.assertFalse(out.exists())

    def test_existing_output_is_not_rewritten(self):
        out = self.root / 'generated'
        g.generate(out)
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
        with self.assertRaisesRegex(ValueError, 'must be new'):
            g.generate(out)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()})

    def test_aliased_output_parent_is_rejected(self):
        (self.root / 'real').mkdir()
        (self.root / 'alias').symlink_to(self.root / 'real', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'canonical'):
            g.generate(self.root / 'alias/generated')
        self.assertEqual(list((self.root / 'real').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
