import base64
import copy
import struct
import unittest
from PIL import Image
import bytes_proof as proof


def fixture(backend="rust"):
    pages = bytearray(1024)
    pages[:8] = b"BTreeDB5"
    pages[8:12] = struct.pack(">I", 512)
    pages[28:32] = struct.pack(">I", 32)
    lengths = [127, 128, 700]
    calls = lambda values: values if backend == "rust" else [0] * 6
    return {"bytesProof": {"version": 1,
        "assets": {"backend": backend, "inputHex": proof.INPUT_HEX, "values": copy.deepcopy(proof.VALUES),
                   "rustCalls": calls([0, 0, 0, 0, 0, 3]), "visualColor": proof.COLOR.copy()},
        "save": {"wireHex": proof.SAVE_HEX, "value": copy.deepcopy(proof.VALUE),
                 "consumed": len(bytes.fromhex(proof.SAVE_HEX)),
                 "writeCalls": calls([0, 0, 0, 5, 0, 0]), "readCalls": calls([0, 0, 0, 0, 0, 5])},
        "packets": {"currentInputHex": "013f000000", "legacyInputHex": "01", "currentWireHex": "013f000000", "legacyWireHex": "01",
                    "currentConsumed": 5, "legacyConsumed": 1, "paused": [True, True], "timescales": [0.5, 1.0],
                    "writeCalls": calls([0, 0, 0, 1, 0, 0]), "readCalls": calls([0, 0, 0, 0, 0, 1])},
        "database": {"valueLengths": lengths,
                     "foundHex": [bytes((i + seed) & 255 for i in range(n)).hex() for seed, n in enumerate(lengths)],
                     "pagesBase64": base64.b64encode(pages).decode(), "rustCalls": calls([0, 0, 0, 4, 0, 3])}}}


class BytesProofTests(unittest.TestCase):
    def test_backends_normalize_same_observation(self):
        self.assertEqual(proof.validate(fixture("cpp")), proof.validate(fixture()))

    def test_independent_ieee_anchors(self):
        data = bytes.fromhex(proof.INPUT_HEX)
        self.assertEqual(data[:2], b"\x06\x03")
        self.assertEqual([struct.unpack(">d", data[i + 1:i + 9])[0] for i in (2, 11, 20)], [0.25, 0.5, 0.75])
        self.assertEqual(len(bytes.fromhex(proof.SAVE_HEX)), 68)
        self.assertEqual(bytes.fromhex(proof.SAVE_HEX)[16:20], b"\x01\x02\x03\x04")
        self.assertEqual(struct.unpack(">f", bytes.fromhex("3f000000"))[0], 0.5)

    def test_paired_wrong_save_rejected(self):
        p = fixture(); p["bytesProof"]["save"]["wireHex"] = proof.SAVE_HEX.replace("01020304", "04030201")
        p["bytesProof"]["save"]["value"]["version"] = 0x04030201
        with self.assertRaisesRegex(ValueError, "independent wire"):
            proof.validate(p)

    def test_paired_wrong_packet_rejected(self):
        p = fixture()["bytesProof"]
        p["packets"]["currentInputHex"] = p["packets"]["currentWireHex"] = "010000003f"
        with self.assertRaisesRegex(ValueError, "binary32"):
            proof.validate({"bytesProof": p})

    def test_missing_receipt_rejected(self):
        for scope, key in (("assets", "rustCalls"), ("save", "writeCalls"), ("packets", "readCalls"), ("database", "rustCalls")):
            p = fixture(); p["bytesProof"][scope][key] = [0] * 6
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, "receipt"):
                proof.validate(p)

    def test_boolean_number_rejected(self):
        for scope, key in (("save", "consumed"), ("packets", "legacyConsumed")):
            p = fixture(); p["bytesProof"][scope][key] = True
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                proof.validate(p)
        p = fixture(); p["bytesProof"]["packets"]["timescales"][1] = True
        with self.assertRaises(ValueError): proof.validate(p)

    def test_integral_float_json_spelling(self):
        p = fixture(); p["bytesProof"]["packets"]["timescales"][1] = 1
        proof.validate(p)

    def test_header_endianness_corruption_rejected(self):
        p = fixture(); d = p["bytesProof"]["database"]
        pages = bytearray(base64.b64decode(d["pagesBase64"])); pages[8:12] = struct.pack("<I", 512)
        d["pagesBase64"] = base64.b64encode(pages).decode()
        with self.assertRaisesRegex(ValueError, "fixed-width header"): proof.validate(p)

    def test_unknown_field_rejected(self):
        p = fixture(); p["bytesProof"]["assets"]["unmeasured"] = True
        with self.assertRaisesRegex(ValueError, "schema"): proof.validate(p)

    def test_visible_native_result_required(self):
        frame = Image.new("RGBA", (1000, 600), (0, 0, 0, 255))
        receipt = {"cameraPosition": [64, 48], "cameraPixelRatio": 2}
        with self.assertRaisesRegex(ValueError, "visible"): proof.visible(frame, receipt)
        frame.paste(tuple(proof.COLOR), (468, 268, 532, 332))
        proof.visible(frame, receipt)


if __name__ == "__main__": unittest.main()
