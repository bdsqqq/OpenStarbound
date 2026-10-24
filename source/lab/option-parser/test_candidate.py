#!/usr/bin/env python3
"""Pure verifier controls: no compile, Cargo, native object, or game writes."""
import unittest
from pathlib import Path
import run as native
from candidate_run import validate_counts


class SourceGate(unittest.TestCase):
    def setUp(self):
        self.raw = (Path(__file__).parent / 'StarOptionParser.original.cpp').read_bytes()
        prefix, body = self.raw.split(b'namespace Star {', 1)
        self.port = (prefix + b'#ifdef STAR_USE_RUST_OPTION_PARSER\n'
                     b'// Selected production body belongs to another gate.\n'
                     b'#else\nnamespace Star {' + body + b'#endif\n')

    def test_unchanged_and_preserved_fallback(self):
        self.assertTrue(native.current_source_matches('cpp', self.raw, self.raw))
        self.assertTrue(native.current_source_matches('cpp', self.raw, self.port))

    def test_body_whitespace_is_not_normalized(self):
        bad = self.port.replace(b'namespace Star {\n\nvoid', b'namespace Star {\n void', 1)
        self.assertNotEqual(bad, self.port)
        self.assertFalse(native.current_source_matches('cpp', self.raw, bad))

    def test_original_includes_required(self):
        self.assertFalse(native.current_source_matches('cpp', self.raw,
                         self.port.replace(b'"StarIterator.hpp"', b'"bad.hpp"', 1)))

    def test_guard_structure_and_trailing_injection(self):
        for bad in (self.port + b'#else\n', self.port + b'void injected();\n',
                    self.port.replace(b'#else\n', b'#else\n#else\n', 1),
                    self.port.replace(b'#endif\n', b'', 1)):
            with self.subTest(bad=bad):
                self.assertFalse(native.current_source_matches('cpp', self.raw, bad))

    def test_public_header_byte_exact(self):
        self.assertTrue(native.current_source_matches('hpp', b'header', b'header'))
        self.assertFalse(native.current_source_matches('hpp', b'header', b'header '))


class CounterGate(unittest.TestCase):
    def setUp(self):
        # Synthetic counts ONLY: these are verifier cases, not execution receipts.
        self.rows = [[i, 3, 2, 1] for i in range(8)]

    def encode(self, rows):
        return ''.join(' '.join(map(str, row)) + '\n' for row in rows).encode()

    def test_positive(self):
        self.assertEqual(validate_counts(self.encode(self.rows)), self.rows)

    def test_native_and_suppression_rejected_as_rust(self):
        zero = self.encode([[i, 0, 0, 0] for i in range(8)])
        validate_counts(zero, 'cpp')
        with self.assertRaises(ValueError):
            validate_counts(zero)

    def test_pending_route(self):
        self.rows[3][3] = 0
        with self.assertRaises(ValueError):
            validate_counts(self.encode(self.rows))

    def test_missing_required_native_exception(self):
        for mode in (3, 4, 7):
            rows = [r[:] for r in self.rows]
            rows[mode] = [mode, 2, 2, 0]
            with self.assertRaises(ValueError):
                validate_counts(self.encode(rows))

    def test_schema_range(self):
        for data in (b'', self.encode(self.rows) + b'8 1 1 0\n',
                     self.encode(self.rows).replace(b'0 3 2 1', b'0 -1 2 1'),
                     self.encode(self.rows).replace(b'0 3 2 1', b'0 18446744073709551616 2 1')):
            with self.assertRaises(ValueError):
                validate_counts(data)


if __name__ == '__main__':
    unittest.main()
