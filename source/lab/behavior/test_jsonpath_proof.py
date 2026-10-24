import json
import unittest
from PIL import Image
import jsonpath_proof as proof


def fixture(backend="rust"):
    def row(path, value, calls):
        return {"path": path, "value": value, "rustCalls": calls if backend == "rust" else [0, 0]}
    return {"jsonPathProof": {"version": 1, "assets": {"backend": backend,
        "sourceHex": proof.SOURCE.hex(), "patchHex": proof.PATCH.hex(),
        "rgb": row(proof.BASE + ":visual.rgb", [64, 128, 192], [21, 2]),
        "scale": row(proof.BASE + ":visual.scale", 4, [0, 2]),
        "label": row(proof.BASE + ":visual.label", "JSONPATH", [0, 2])},
        "script": {"query": row("é[0].雪", 9, [0, 3]), "missing": row("missing", 77, [0, 1]),
                   "malformed": {"path": "é[0x].雪", "accepted": False, "nativeErrorMatched": True,
                                 "rustCalls": [0, 2] if backend == "rust" else [0, 0]}},
        "visual": {"imagePath": "/behaviorlab/jsonpath-result.png", "color": proof.COLOR.copy(), "scale": 4, "label": "JSONPATH"}}}


class JsonPathProofTests(unittest.TestCase):
    def test_both_backends_have_equal_semantics(self):
        self.assertEqual(proof.validate(fixture()), proof.validate(fixture("cpp")))

    def test_independent_source_literals(self):
        source = json.loads(proof.SOURCE)
        self.assertEqual(source["a/b"]["~é"], [64, 128])
        patch = json.loads(proof.PATCH)
        self.assertEqual([p["path"] for p in patch], ["/visual/rgb/-"] * 3)
        self.assertEqual(patch[0]["from"], "/a~1b/~0é/0")
        self.assertEqual(patch[2]["value"], 192)

    def test_paired_wrong_rgb_rejected(self):
        p = fixture(); p["jsonPathProof"]["assets"]["rgb"]["value"] = [1, 2, 3]
        p["jsonPathProof"]["visual"]["color"] = [1, 2, 3, 255]
        with self.assertRaisesRegex(ValueError, "actual Assets"): proof.validate(p)

    def test_each_consumer_needs_its_own_receipts(self):
        for group, name in (("assets", "rgb"), ("assets", "scale"), ("assets", "label"),
                            ("script", "query"), ("script", "missing"), ("script", "malformed")):
            p = fixture(); p["jsonPathProof"][group][name]["rustCalls"] = [0, 0]
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "receipt"): proof.validate(p)

    def test_malformed_error_must_not_be_traversal_default(self):
        for key, value in (("accepted", True), ("nativeErrorMatched", False)):
            p = fixture(); p["jsonPathProof"]["script"]["malformed"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "native syntax"): proof.validate(p)

    def test_bool_and_schema_drift_rejected(self):
        p = fixture(); p["jsonPathProof"]["script"]["missing"]["value"] = True
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["jsonPathProof"]["assets"]["scale"]["rustCalls"] = [False, 2]
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["jsonPathProof"]["assets"]["hidden"] = 1
        with self.assertRaises(ValueError): proof.validate(p)

    def test_visible_result_and_caption_required(self):
        frame = Image.new("RGBA", (1000, 600), (0, 0, 0, 255))
        receipt = {"cameraPosition": [64, 48], "cameraPixelRatio": 2}
        with self.assertRaisesRegex(ValueError, "result ink"): proof.visible(frame, receipt)
        frame.paste(tuple(proof.COLOR), (468, 268, 532, 332))
        with self.assertRaisesRegex(ValueError, "label"): proof.visible(frame, receipt)
        frame.paste((255, 255, 255, 255), (465, 215, 530, 220))
        proof.visible(frame, receipt)


if __name__ == "__main__": unittest.main()
