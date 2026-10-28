"""Hermetic edge-oracle tests; no native, baseline imports or output files."""

import unittest

import edge_model


class EdgeModelTests(unittest.TestCase):
    def test_exact_ascii_inventory(self):
        text = edge_model.expected()
        text.encode("ascii")
        self.assertEqual(len(edge_model.case_names), 12)
        self.assertEqual(len(edge_model.property_names), 6)
        self.assertEqual(len(set(edge_model.case_names)), 12)
        self.assertEqual(len(set(edge_model.property_names)), 6)
        self.assertEqual(len(text.splitlines()), 18)
        self.assertTrue(text.endswith("\n"))
        edge_model.verify(text)

    def test_row_schema(self):
        for line in edge_model.expected().splitlines():
            fields = line.split("\t")
            self.assertIn(fields[0], ("CASE", "PASS"))
            self.assertEqual(len(fields), 3 if fields[0] == "CASE" else 2)
            self.assertIn(fields[1].split("/")[0], edge_model.BACKENDS)

    def test_outer_copy_literal(self):
        values = {name: value for kind, name, value in edge_model.RECORDS if kind == "CASE"}
        self.assertEqual(values["outer-argument-copy"], "identity-preserved,cursor=10,size=1")

    def test_partial_scalar_from_little_endian_object_bytes(self):
        # uint32 read targets existing storage before endian conversion. EOF skips
        # conversion, so only the available two bytes replace the old object bytes.
        native_min = bytearray((0x11223344).to_bytes(4, "little"))
        self.assertEqual(native_min, b"\x44\x33\x22\x11")
        native_min[:2] = b"\x01\x02"
        mutated_min = int.from_bytes(native_min, "little")
        self.assertEqual(mutated_min, 0x11220201)
        encoded = b"\x00" + b"".join(
            value.to_bytes(4, "big") for value in (mutated_min, 0x55667788, 0x11223345)
        )
        self.assertEqual(encoded.hex(), "00112202015566778811223345")
        values = {name: value for kind, name, value in edge_model.RECORDS if kind == "CASE"}
        self.assertEqual(values["partial-metadata-little-endian"], encoded.hex() + ",pos=3")

    def test_duplicate_packet_literal_shape(self):
        # Independent byte decoding verifies the specified raw packet, not a
        # native serializer or native output. Count=2, then two key/value pairs.
        packet = bytes.fromhex("020000000b0000004d0000000b000000630000000a0000000c0000000a")
        self.assertEqual(len(packet), 29)
        self.assertEqual(packet[0], 2)
        words = [int.from_bytes(packet[i:i + 4], "big") for i in range(1, 29, 4)]
        self.assertEqual(words, [11, 77, 11, 99, 10, 12, 10])
        contents = {}
        for key, value in [(words[0], words[1]), (words[2], words[3])]:
            contents.setdefault(key, value)  # Map insert does not overwrite.
        self.assertEqual(contents, {11: 77})

    def test_outside_cursor_is_returned_before_increment_normalizes(self):
        minimum, maximum, cursor = 10, 12, 99
        first = cursor
        cursor = minimum if cursor < minimum or cursor >= maximum else cursor + 1
        self.assertEqual((first, cursor), (99, 10))

    def test_outside_keys_count_in_fullness(self):
        contents = {99: 1, 100: 2, 101: 3}
        self.assertTrue(len(contents) > 12 - 10)
        self.assertTrue(all(key not in contents for key in (10, 11, 12)))

    def test_printable_uint8_literal(self):
        values = {name: value for kind, name, value in edge_model.RECORDS if kind == "CASE"}
        self.assertEqual(chr(65), "A")
        self.assertEqual(values["printable-uint8-duplicate"],
                         "(IdMapException) IdMapWrapper::add(id, value) called with pre-existing id 'A'")

    def assert_rejected_change(self, old, new):
        original = edge_model.expected()
        changed = original.replace(old, new)
        self.assertNotEqual(changed, original, "control must actually corrupt the transcript")
        with self.assertRaises(ValueError):
            edge_model.verify(changed)

    def test_reject_invented_outer_cursor_advance(self):
        self.assert_rejected_change("cursor=10,size=1", "cursor=11,size=1")

    def test_reject_duplicate_last_wins(self):
        self.assert_rejected_change("size=1,value=77,next=10", "size=1,value=99,next=10")

    def test_reject_eager_cursor_validation(self):
        self.assert_rejected_change("loaded-outside-cursor\t99,10", "loaded-outside-cursor\t10,11")

    def test_reject_invented_partial_rollback(self):
        self.assert_rejected_change("00112202015566778811223345,pos=3",
                                   "00112233445566778811223345,pos=3")

    def test_reject_invented_endian_conversion_after_failure(self):
        self.assert_rejected_change("00112202015566778811223345,pos=3",
                                   "00010222115566778811223345,pos=3")

    def test_reject_decimal_uint8_message(self):
        self.assert_rejected_change("pre-existing id 'A'", "pre-existing id '65'")

    def test_reject_claim_that_outside_keys_do_not_exhaust(self):
        self.assert_rejected_change("outside-keys-exhaustion\t(IdMapException) No id space left in IdMapWrapper",
                                   "outside-keys-exhaustion\t10")

    def test_reject_framing_missing_duplicate_reorder_and_extra(self):
        text = edge_model.expected()
        rows = text.splitlines(keepends=True)
        changed = [text[:-1], text.replace("\n", "\r\n"), "".join(rows[:-1]),
                   text + rows[0], "".join([rows[1], rows[0], *rows[2:]]),
                   text + "PASS\tinvented\n"]
        for value in changed:
            with self.subTest(value=value[:60]), self.assertRaises(ValueError):
                edge_model.verify(value)


if __name__ == "__main__":
    unittest.main()
