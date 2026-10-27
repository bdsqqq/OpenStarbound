"""Evidence codec fixtures, including the nested byte paths that stopped acquisition."""
import json
from pathlib import Path
import struct
import unittest

from native_evidence_json import FORMAT, dumps, loads


def wrapped(node):
    return json.dumps({"format": FORMAT, "root": node})


class EvidenceJsonTests(unittest.TestCase):
    def test_nested_native_paths_round_trip(self):
        value = {"objects": [b"/core/a.o", b"/opaque/\x93.o"],
                 "archive_members": [(b"/lib.a", b"member\xff.o")],
                 b"byte-key": {("tuple", 3): b"\x00\xff"}}
        self.assertEqual(loads(dumps(value)), value)

    def test_every_byte_and_unicode(self):
        value = [bytes(range(256)), "", "\u2603", "\ud800", None, [], (), {}]
        self.assertEqual(loads(dumps(value)), value)
        self.assertTrue(dumps(value).isascii())

    def test_types_do_not_alias(self):
        values = [None, False, 0, 0.0, "", b"", [], (), {}]
        self.assertEqual(len(set(map(dumps, values))), len(values))
        for value in values:
            self.assertIs(type(loads(dumps(value))), type(value))

    def test_marker_shaped_dictionary_is_not_bytes(self):
        value = {"bytes": "ff", "root": ["bytes", "ff"]}
        self.assertEqual(loads(dumps(value)), value)
        self.assertNotEqual(dumps(value), dumps(b"\xff"))

    def test_float_bits_not_numeric_normalization(self):
        for bits in ["0000000000000000", "8000000000000000", "7ff0000000000000",
                     "fff0000000000000", "7ff8000000000042"]:
            value = struct.unpack(">d", bytes.fromhex(bits))[0]
            self.assertEqual(struct.pack(">d", loads(dumps(value))).hex(), bits)

    def test_large_integers(self):
        for value in [-(1 << 127), (1 << 128) - 1]:
            self.assertEqual(loads(dumps(value)), value)

    def test_unsupported_objects_and_cycles_rejected(self):
        for value in [Path("/not-implicitly-stringified"), {1, 2}, object()]:
            with self.assertRaises(TypeError):
                dumps(value)
        cycle = []; cycle.append(cycle)
        with self.assertRaises(ValueError):
            dumps(cycle)

    def test_bad_tags_and_payloads_rejected(self):
        for node in [["bytes", "f"], ["bytes", "FF"], ["bool", 1], ["int", True],
                     ["int", "-0"], ["int", "01"], ["float64", "00"],
                     ["none", False], ["unknown", 1], ["str", 3], ["tuple", {}]]:
            with self.subTest(node=node), self.assertRaises(ValueError):
                loads(wrapped(node))

    def test_mapping_collisions_and_unhashable_keys_rejected(self):
        for entries in [
            [[["str", "a"], ["none", None]], [["str", "a"], ["bool", True]]],
            [[["bool", True], ["none", None]], [["int", "1"], ["none", None]]],
            [[["list", []], ["none", None]]],
        ]:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                loads(wrapped(["dict", entries]))

    def test_envelope_and_duplicate_fields_rejected(self):
        for text in ['{}', '[]', '{"format":"wrong","root":["none",null]}',
                     '{"format":"star-native-evidence-v1","format":"star-native-evidence-v1","root":["none",null]}']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                loads(text)
        with self.assertRaises(TypeError):
            loads(b"raw map bytes")


if __name__ == "__main__":
    unittest.main()
