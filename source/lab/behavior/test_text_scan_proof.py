import copy
import unittest
from PIL import Image
import text_scan_proof as proof


def fixture(backend="rust"):
    return {"textScanProof": {"version": 1, "backend": backend, "inputHex": proof.INPUT.hex(),
        "calls": [1,1,2] if backend == "rust" else [0,0,0], "events": copy.deepcopy(proof.EVENTS),
        "glyphs": copy.deepcopy(proof.GLYPHS), "completed": True}}


class TextScanProofTests(unittest.TestCase):
    def test_native_backends_normalize_equal(self):
        self.assertEqual(proof.validate(fixture()), proof.validate(fixture("cpp")))

    def test_event_input_payload_and_order_are_fixed(self):
        for mutation in (lambda p: p.update(inputHex=b"TEXT".hex()), lambda p: p["events"].reverse(), lambda p: p["events"][0].update(hex=b"blue".hex())):
            p = fixture(); mutation(p["textScanProof"])
            with self.assertRaisesRegex(ValueError, "spans"): proof.validate(p)

    def test_measurement_without_actual_rendered_glyphs_fails(self):
        p = fixture(); p["textScanProof"]["glyphs"] = []
        with self.assertRaisesRegex(ValueError, "foreground glyph"): proof.validate(p)

    def test_red_is_actual_named_color_not_generic_red(self):
        p = fixture(); p["textScanProof"]["glyphs"][0]["rgba"] = [255,0,0,255]
        with self.assertRaisesRegex(ValueError, "foreground glyph"): proof.validate(p)

    def test_rust_execution_event_receipts_are_not_optional(self):
        for calls in ([0,0,0], [1,0,2], [1,1,1], [True,1,2]):
            p = fixture(); p["textScanProof"]["calls"] = calls
            with self.assertRaisesRegex(ValueError, "receipts"): proof.validate(p)

    def test_incomplete_and_schema_drift_fail(self):
        p = fixture(); p["textScanProof"]["completed"] = False
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["textScanProof"]["version"] = True
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["textScanProof"]["widthOnly"] = 32
        with self.assertRaises(ValueError): proof.validate(p)

    def test_visible_red_ink_required_but_antialias_blending_allowed(self):
        frame = Image.new("RGBA", (1000,600), (0,0,0,255)); r = {"cameraPosition": [64,48], "cameraPixelRatio": 2}
        with self.assertRaisesRegex(ValueError, "red glyph ink"): proof.visible(frame, r)
        frame.paste((220,63,57,255), (465,221,480,225)); proof.visible(frame, r)
        frame.paste((0,0,0,255), (465,221,480,225)); frame.paste((255,255,255,255), (465,221,480,225))
        with self.assertRaises(ValueError): proof.visible(frame, r)


if __name__ == "__main__": unittest.main()
