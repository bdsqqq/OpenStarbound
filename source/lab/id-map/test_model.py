"""Hermetic tests: model contracts and intentional transcript corruptions only."""

import unittest

import model


class FiniteModelTests(unittest.TestCase):
    def test_default_unsigned(self):
        m = model.ReferenceMap()
        self.assertEqual([m.next_id(), m.next_id()], [0, 1])

    def test_inclusive_unreserved_cycle(self):
        m = model.ReferenceMap(10, 12)
        self.assertEqual([m.next_id() for _ in range(5)], [10, 11, 12, 10, 11])
        self.assertEqual(m.contents, {})

    def test_high_unsigned_wrap(self):
        m = model.ReferenceMap(0xFFFFFFFD, 0xFFFFFFFF)
        self.assertEqual([m.next_id() for _ in range(4)],
                         [4294967293, 4294967294, 4294967295, 4294967293])

    def test_explicit_does_not_advance_or_validate_range(self):
        m = model.ReferenceMap(10, 12)
        m.explicit_add(11, 77)
        m.explicit_add(99, 5)
        self.assertEqual(m.cursor, 10)
        self.assertEqual(m.next_id(), 10)
        self.assertEqual(m.next_id(), 12)

    def test_fill_last_slot_then_exact_exhaustion(self):
        m = model.ReferenceMap(10, 12)
        self.assertEqual([m.auto_add(v) for v in [100, 200, 300]], [10, 11, 12])
        with self.assertRaises(model.IdFailure) as caught:
            m.next_id()
        self.assertEqual(str(caught.exception), "No id space left in IdMapWrapper")

    def test_duplicate_exception_and_no_replacement(self):
        m = model.ReferenceMap(10, 12)
        m.explicit_add(11, 200)
        with self.assertRaises(model.IdFailure) as caught:
            m.explicit_add(11, 999)
        self.assertEqual(str(caught.exception),
                         "IdMapWrapper::add(id, value) called with pre-existing id '11'")
        self.assertEqual(m.contents[11], 200)
        self.assertEqual(m.cursor, 10)

    def test_hole_after_wrap(self):
        m = model.ReferenceMap(10, 12)
        for v in [100, 200, 300]:
            m.auto_add(v)
        del m.contents[11]
        self.assertEqual(m.auto_add(201), 11)

    def test_clear_resets_cursor(self):
        m = model.ReferenceMap(10, 12)
        m.auto_add(7)
        m.next_id()
        m.clear()
        self.assertEqual(m.cursor, 10)
        self.assertEqual(m.contents, {})

    def test_equality_ignores_cursor(self):
        a, b = model.ReferenceMap(10, 12), model.ReferenceMap(10, 12)
        a.auto_add(7)
        b.explicit_add(10, 7)
        b.next_id()
        b.next_id()
        self.assertNotEqual(a.cursor, b.cursor)
        self.assertEqual(a, b)

    def test_equality_checks_range_and_contents(self):
        a, b = model.ReferenceMap(10, 12), model.ReferenceMap(10, 13)
        a.explicit_add(10, 7)
        b.explicit_add(10, 7)
        self.assertNotEqual(a, b)
        c = model.ReferenceMap(10, 12)
        c.explicit_add(10, 8)
        self.assertNotEqual(a, c)

    def test_literal_stream_bytes_independent_encoding(self):
        # A standard-library encoding cross-check, not native output acquisition.
        literal = bytes.fromhex(model.ONE_ENTRY_HEX)
        expected = b"\x01" + b"".join(n.to_bytes(4, "big") for n in (11, 77, 10, 12, 10))
        self.assertEqual(literal, expected)
        self.assertEqual(len(literal), 21)

    def test_literal_partial_boundaries(self):
        rows = dict(model.CASE_ROWS)
        expected_fields = {
            "partial-count": (0, (40, 44, 41)),
            "partial-entry": (0, (40, 44, 41)),
            "partial-min": (1, (11, 77, 40, 44, 41)),
            "partial-max": (1, (11, 77, 10, 44, 41)),
        }
        for name, (count, fields) in expected_fields.items():
            encoded = bytes([count]) + b"".join(n.to_bytes(4, "big") for n in fields)
            self.assertEqual(rows[name], encoded.hex())

    def test_reject_unsupported_model_ranges(self):
        for bounds in [(-1, 2), (2, 2), (3, 2), (0, 0x100000000)]:
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                model.ReferenceMap(*bounds)


class TranscriptTests(unittest.TestCase):
    def test_ascii_exact_counts_and_unique_names(self):
        text = model.expected()
        text.encode("ascii")
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(len(model.case_names), 44)
        self.assertEqual(len(model.property_names), 12)
        self.assertEqual(len(text.splitlines()), 56)
        self.assertEqual(len(set(model.case_names)), 44)
        self.assertEqual(len(set(model.property_names)), 12)
        model.verify(text)

    def test_reject_early_fullness_semantic_corruption(self):
        # Known falsifier: the >= mutant rejects an available final slot.
        corrupt = model.expected().replace("CASE\tordered/fill-last-slot\t12\n",
                                           "CASE\tordered/fill-last-slot\tEXHAUSTED\n")
        self.assertNotEqual(corrupt, model.expected())
        with self.assertRaises(ValueError):
            model.verify(corrupt)

    def test_reject_rollback_claim(self):
        corrupt = model.expected().replace(
            "CASE\thash/partial-max\t010000000b0000004d0000000a0000002c00000029\n",
            "CASE\thash/partial-max\t010000002a00000009000000280000002c00000029\n")
        self.assertNotEqual(corrupt, model.expected())
        with self.assertRaises(ValueError):
            model.verify(corrupt)

    def test_reject_missing_property(self):
        lines = model.expected().splitlines(keepends=True)
        with self.assertRaises(ValueError):
            model.verify("".join(lines[:-1]))

    def test_reject_duplicate_reorder_extra_and_newline(self):
        text = model.expected()
        lines = text.splitlines(keepends=True)
        corruptions = [text + lines[0], "".join([lines[1], lines[0], *lines[2:]]),
                       text + "PASS\tinvented\n", text.rstrip("\n"), text.replace("\n", "\r\n")]
        for corrupt in corruptions:
            with self.subTest(corrupt=corrupt[:80]), self.assertRaises(ValueError):
                model.verify(corrupt)


if __name__ == "__main__":
    unittest.main()
