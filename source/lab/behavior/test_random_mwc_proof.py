import copy
import unittest
from PIL import Image
import random_mwc_proof as proof


def fixture(backend="rust"):
    p = {"version": 1, "fixture": "random-mwc-v1", "backend": backend, "complete": True, "sameUserdata": True,
         "events": copy.deepcopy(proof.EVENTS), "resetDraw": copy.deepcopy(proof.RESET),
         "lua": proof.LUA.copy(), "visual": copy.deepcopy(proof.VISUAL)}
    if backend == "cpp":
        for row in p["events"] + [p["resetDraw"]]: row["calls"] = [0, 0, 0]
    return {"randomMwcProof": p}


class RandomMwcProofTests(unittest.TestCase):
    def test_both_backends_normalize_equal(self):
        self.assertEqual(proof.validate(fixture()), proof.validate(fixture("cpp")))

    def test_literal_unsigned_native_signed_lua_and_visual(self):
        unsigned = 15329329036541151364
        self.assertEqual(str(unsigned - (1 << 64)), proof.LUA["e"])
        self.assertEqual([2950892229 >> shift & 255 for shift in (0, 8, 16)], proof.COLOR[:3])
        self.assertEqual(32 + 445970691 % 33, 44)
        p = fixture(); p["randomMwcProof"]["lua"]["e"] = str(unsigned)
        with self.assertRaisesRegex(ValueError, "Lua signed"): proof.validate(p)

    def test_every_native_operation_needs_scoped_receipt(self):
        for i in range(9):
            p = fixture(); p["randomMwcProof"]["events"][i]["calls"] = [0, 0, 0]
            with self.subTest(event=i), self.assertRaisesRegex(ValueError, "receipt"): proof.validate(p)
        p = fixture(); p["randomMwcProof"]["events"][0]["calls"] = [1, 0, 32]
        with self.assertRaisesRegex(ValueError, "receipt"): proof.validate(p)

    def test_owned_identity_complete_reset_and_order_required(self):
        for field in ("complete", "sameUserdata"):
            p = fixture(); p["randomMwcProof"][field] = False
            with self.subTest(field=field), self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["randomMwcProof"]["events"][1], p["randomMwcProof"]["events"][2] = p["randomMwcProof"]["events"][2], p["randomMwcProof"]["events"][1]
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["randomMwcProof"]["resetDraw"]["native"] = "0"
        with self.assertRaises(ValueError): proof.validate(p)

    def test_paired_wrong_output_and_visual_rejected(self):
        p = fixture(); p["randomMwcProof"]["events"][1]["native"] = "123"
        p["randomMwcProof"]["visual"]["rgb"] = [123, 0, 0]
        with self.assertRaisesRegex(ValueError, "native seed/draw"): proof.validate(p)

    def test_no_precision_loss_bool_coercion_or_unadvertised_fields(self):
        p = fixture(); p["randomMwcProof"]["lua"]["b"] = float(proof.LUA["b"])
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["randomMwcProof"]["events"][7]["native"] = 1
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["randomMwcProof"]["totalCalls"] = [2, 1, 9]
        with self.assertRaises(ValueError): proof.validate(p)

    def test_exact_actual_derived_visible_width_and_normal_label(self):
        frame = Image.new("RGBA", (1000, 600), (0, 0, 0, 255)); receipt = {"cameraPosition": [64, 48], "cameraPixelRatio": 2}
        with self.assertRaisesRegex(ValueError, "visible area"): proof.visible(frame, receipt)
        frame.paste(tuple(proof.COLOR), (468, 268, 532, 332))
        with self.assertRaisesRegex(ValueError, "visible area"): proof.visible(frame, receipt)
        frame.paste(tuple(proof.COLOR), (412, 268, 588, 332))
        with self.assertRaisesRegex(ValueError, "label"): proof.visible(frame, receipt)
        frame.paste((255, 255, 255, 255), (465, 215, 530, 220)); proof.visible(frame, receipt)


if __name__ == "__main__": unittest.main()
