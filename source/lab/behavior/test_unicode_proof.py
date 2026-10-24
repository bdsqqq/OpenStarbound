import copy
import json
import unittest
from PIL import Image
import unicode_proof as proof


def fixture(backend="rust"):
    def calls(required=(), exact=None):
        if backend == "cpp": return [0] * 10
        return exact or [int(i in required) for i in range(10)]
    return {"unicodeProof": {"version": 1,
        "assets": {"backend": backend, "sourceHex": proof.SOURCE.hex(), "textHex": proof.TEXT_BYTES.hex(),
                   "parseCalls": calls((1, 3, 4, 6)), "visualColor": proof.COLOR.copy(), "label": "UNICODE"},
        "string": {"boundedLength": 5, "sentinelLength": 3, "validUtf8": True,
                   "rustCalls": calls(exact=[1, 2, 0, 0, 0, 0, 0, 0, 0, 0])},
        "json": {"wireHex": proof.JSON_BYTES.hex(), "textHex": proof.TEXT_BYTES.hex(),
                 "writeCalls": calls((5,)), "readCalls": calls((3, 4, 6))},
        "save": {"wireHex": proof.SAVE_BYTES.hex(), "value": copy.deepcopy(proof.VALUE),
                 "consumed": len(proof.SAVE_BYTES), "writeCalls": calls(), "readCalls": calls()}}}


class UnicodeProofTests(unittest.TestCase):
    def test_observations_equal_across_backends(self):
        self.assertEqual(proof.validate(fixture("cpp")), proof.validate(fixture()))

    def test_independent_text_and_format_anchors(self):
        self.assertEqual(json.loads(proof.SOURCE)["text"].encode(), bytes.fromhex("41c3a9f09f9880005a"))
        self.assertEqual(json.loads(proof.JSON_BYTES), proof.TEXT)
        self.assertEqual(len(proof.TEXT_BYTES), 9)
        self.assertEqual(len(proof.TEXT), 5)
        self.assertEqual(len(proof.SAVE_BYTES), 59)
        self.assertIn(b"\x07\x01\x04text\x05\x09" + proof.TEXT_BYTES, proof.SAVE_BYTES)

    def test_paired_wrong_json_rejected(self):
        p = fixture(); p["unicodeProof"]["json"].update(wireHex="224122", textHex="41")
        with self.assertRaisesRegex(ValueError, "independent literal"): proof.validate(p)

    def test_missing_receipt_rejected(self):
        for scope, field in (("assets", "parseCalls"), ("string", "rustCalls"), ("json", "writeCalls")):
            p = fixture(); p["unicodeProof"][scope][field] = [0] * 10
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, "receipt"):
                proof.validate(p)

    def test_nul_truncation_and_type_confusion_rejected(self):
        for key, value in (("boundedLength", 3), ("boundedLength", True), ("sentinelLength", 5), ("validUtf8", 1)):
            p = fixture(); p["unicodeProof"]["string"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): proof.validate(p)

    def test_wrong_save_payload_and_schema_rejected(self):
        p = fixture(); p["unicodeProof"]["save"]["wireHex"] = proof.SAVE_BYTES.hex()[:-2]
        with self.assertRaisesRegex(ValueError, "independent literal format"): proof.validate(p)
        p = fixture(); p["unicodeProof"]["assets"]["glyphCertified"] = True
        with self.assertRaisesRegex(ValueError, "schema"): proof.validate(p)

    def test_actual_result_and_font_ink_both_required(self):
        frame = Image.new("RGBA", (1000, 600), (0, 0, 0, 255))
        receipt = {"cameraPosition": [64, 48], "cameraPixelRatio": 2}
        with self.assertRaisesRegex(ValueError, "result ink"): proof.visible(frame, receipt)
        frame.paste(tuple(proof.COLOR), (468, 268, 532, 332))
        with self.assertRaisesRegex(ValueError, "normal-font"): proof.visible(frame, receipt)
        frame.paste((255, 255, 255, 255), (465, 220, 475, 225))
        proof.visible(frame, receipt)


if __name__ == "__main__": unittest.main()
