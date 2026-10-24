import unittest
from PIL import Image
import shell_proof as proof


def fixture(backend="rust"):
    count = int(backend == "rust")
    return {"shellProof": {"version": 1, "backend": backend, "admin": True,
        "queryPosition": [64, 48], "originalGravity": 80,
        "commands": [{"commandHex": command, "tokenHex": ["302e3235"], "tokenCalls": count,
                      "responses": proof.RESPONSE.copy(), "gravity": 0.25, "gravityBits": "3e800000", "rustCalls": count}
                     for command in proof.COMMANDS],
        "query": {"responses": ["0.25"], "gravity": 0.25, "rustCalls": 0},
        "restore": {"responses": ["Gravity reset"], "gravity": 80, "rustCalls": 0},
        "visual": {"gravity": 0.25, "imagePath": "/behaviorlab/shell-result.png", "label": "SHELL", "color": proof.COLOR.copy()}}}


class ShellProofTests(unittest.TestCase):
    def test_backends_normalize_equal(self):
        self.assertEqual(proof.validate(fixture()), proof.validate(fixture("cpp")))

    def test_literals_are_not_candidate_generated(self):
        self.assertEqual(bytes.fromhex(proof.COMMANDS[0]), b'/setgravity "\\u0030.25"')
        self.assertEqual(bytes.fromhex(proof.COMMANDS[1]), b'/setgravity "0.25"')
        self.assertEqual(bytes.fromhex("302e3235"), b"0.25")

    def test_paired_wrong_response_and_state_rejected(self):
        p = fixture(); p["shellProof"]["commands"][0].update(responses=["Gravity set to 1"], gravity=1, gravityBits="3f800000")
        with self.assertRaisesRegex(ValueError, "observed gravity"): proof.validate(p)

    def test_receipts_need_both_direct_and_actual_consumers(self):
        for key in ("tokenCalls", "rustCalls"):
            p = fixture(); p["shellProof"]["commands"][0][key] = 0
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "receipt"): proof.validate(p)

    def test_restore_and_type_failures(self):
        for value in (0.25, True, float("nan")):
            p = fixture(); p["shellProof"]["restore"]["gravity"] = value
            with self.subTest(value=value), self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["shellProof"]["commands"][0]["rustCalls"] = True
        with self.assertRaises(ValueError): proof.validate(p)

    def test_admin_and_unknown_schema_rejected(self):
        p = fixture(); p["shellProof"]["admin"] = False
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["shellProof"]["query"]["unobserved"] = 1
        with self.assertRaises(ValueError): proof.validate(p)

    def test_both_visible_outputs_required(self):
        frame = Image.new("RGBA", (1000, 600), (0, 0, 0, 255))
        receipt = {"cameraPosition": [64, 48], "cameraPixelRatio": 2}
        with self.assertRaisesRegex(ValueError, "image result"): proof.visible(frame, receipt)
        frame.paste(tuple(proof.COLOR), (468, 268, 532, 332))
        with self.assertRaisesRegex(ValueError, "label"): proof.visible(frame, receipt)
        frame.paste((255, 255, 255, 255), (475, 220, 490, 225))
        proof.visible(frame, receipt)


if __name__ == "__main__": unittest.main()
