import copy
import json
import unittest
from PIL import Image
import json_patch_proof as proof


def fixture(backend="rust"):
    calls = copy.deepcopy(proof.CALLS) if backend == "rust" else {k: [0] * 10 for k in proof.CALLS}
    return {"jsonPatchProof": {"version": 1, "assets": {"backend": backend, "sourceHex": proof.SOURCE.hex(),
        "patchesHex": [p.hex() for p in proof.PATCHES], "value": copy.deepcopy(proof.VALUE), "calls": calls},
        "visual": {"color": proof.COLOR.copy(), "scale": 4, "label": "PATCH", "imagePath": "/behaviorlab/jsonpatch-result.png"}}}


class JsonPatchProofTests(unittest.TestCase):
    def test_backends_normalize_equal(self):
        self.assertEqual(proof.validate(fixture()), proof.validate(fixture("cpp")))

    def test_literal_inputs_cover_handlers_search_and_rollbacks(self):
        source = json.loads(proof.SOURCE); first, second = map(json.loads, proof.PATCHES)
        self.assertEqual(source["a/b"]["~é"], [64, 128])
        self.assertEqual({op["op"] for op in first if isinstance(op, dict)}, {"test", "add", "remove", "replace", "move", "copy", "merge"})
        self.assertTrue(any(isinstance(op, list) for op in first))
        self.assertEqual(second[0]["value"], "BAD")
        self.assertEqual(proof.VALUE["visual"], {"rgb": [64,128,192], "scale": 4, "label": "PATCH"})
        self.assertEqual(sum(proof.CALLS["attempt"]), 47)
        self.assertEqual(sum(proof.CALLS["success"]) + sum(proof.CALLS["exception"]), 47)

    def test_no_false_game_public_patch_attribution(self):
        p = fixture(); p["jsonPatchProof"]["assets"]["calls"]["attempt"][0] = 1
        with self.assertRaisesRegex(ValueError, "semantic receipts"): proof.validate(p)

    def test_failed_tests_need_attempts_and_exception_receipts(self):
        for name, index, value in (("attempt", 3, 3), ("success", 3, 5), ("exception", 3, 0), ("exception", 1, 0)):
            p = fixture(); p["jsonPatchProof"]["assets"]["calls"][name][index] = value
            with self.subTest(name=name, index=index), self.assertRaisesRegex(ValueError, "semantic receipts"): proof.validate(p)

    def test_full_nonvisual_json_and_both_rollback_boundaries(self):
        for mutate in (lambda v: v["items"][0].update(n=9), lambda v: v["visual"].update(scale=99), lambda v: v["visual"].update(label="BAD"), lambda v: v.pop("after")):
            p = fixture(); mutate(p["jsonPatchProof"]["assets"]["value"])
            with self.assertRaisesRegex(ValueError, "typed result/search/rollback"): proof.validate(p)

    def test_inputs_numeric_type_bool_and_schema_drift_fail(self):
        p = fixture(); p["jsonPatchProof"]["assets"]["value"]["items"][0]["n"] = 10.0
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["jsonPatchProof"]["assets"]["calls"]["success"][0] = False
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["jsonPatchProof"]["assets"]["patchesHex"].reverse()
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["jsonPatchProof"]["unobserved"] = True
        with self.assertRaises(ValueError): proof.validate(p)

    def test_both_visible_outputs_required(self):
        frame = Image.new("RGBA", (1000,600), (0,0,0,255)); receipt = {"cameraPosition": [64,48], "cameraPixelRatio": 2}
        with self.assertRaisesRegex(ValueError, "pixel ink"): proof.visible(frame, receipt)
        frame.paste(tuple(proof.COLOR), (468,268,532,332))
        with self.assertRaisesRegex(ValueError, "label"): proof.visible(frame, receipt)
        frame.paste((255,255,255,255), (465,215,530,220)); proof.visible(frame, receipt)


if __name__ == "__main__": unittest.main()
