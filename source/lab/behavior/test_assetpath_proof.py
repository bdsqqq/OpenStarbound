from io import BytesIO
import unittest
from PIL import Image
import assetpath_proof as proof


def png(wrong=False):
    image = Image.new("RGBA", (32, 16), (255, 0, 0, 255))
    image.paste((0, 0, 0, 255) if wrong else (64, 128, 192, 255), (16, 0, 32, 16))
    out = BytesIO(); image.save(out, format="PNG"); return out.getvalue().hex()


def fixture(backend="rust"):
    def row(frame, counts):
        return {"path": proof.ATLAS + ":" + frame + "?multiply=80ff80", "size": [16, 16],
                "rgbaHex": proof.RGBA.hex(), "rustCalls": counts if backend == "rust" else [0, 0]}
    return {"assetPathProof": {"version": 1, "assets": {"backend": backend, "atlasHex": png(),
        "framesHex": proof.FRAMES.hex(), "named": row("right", [1, 2]), "alias": row("alias", [1, 0])},
        "visual": {"imagePath": "/behaviorlab/assetpath-result.png", "color": proof.COLOR.copy(), "size": [16, 16], "label": "ASSETPATH"}}}


class AssetPathProofTests(unittest.TestCase):
    def test_backends_normalize_equal(self):
        self.assertEqual(proof.validate(fixture()), proof.validate(fixture("cpp")))

    def test_literal_integer_multiply_is_not_identity(self):
        self.assertEqual([a * b // 255 for a, b in zip([64, 128, 192, 255], [128, 255, 128, 255])], proof.COLOR)
        p = fixture(); p["assetPathProof"]["assets"]["named"]["rgbaHex"] = (bytes([64, 128, 192, 255]) * 256).hex()
        with self.assertRaisesRegex(ValueError, "crop/directive"): proof.validate(p)

    def test_independent_atlas_pixels_not_paired_outputs(self):
        p = fixture(); p["assetPathProof"]["assets"]["atlasHex"] = png(wrong=True)
        for name in ("named", "alias"): p["assetPathProof"]["assets"][name]["rgbaHex"] = (bytes([0, 0, 0, 255]) * 256).hex()
        with self.assertRaisesRegex(ValueError, "independent pixels"): proof.validate(p)

    def test_both_named_and_cached_alias_calls(self):
        for name, counts in (("named", [1, 0]), ("named", [0, 2]), ("alias", [0, 0]), ("alias", [1, 2])):
            p = fixture(); p["assetPathProof"]["assets"][name]["rustCalls"] = counts
            with self.subTest(name=name, counts=counts), self.assertRaisesRegex(ValueError, "receipt"): proof.validate(p)

    def test_bad_atlas_and_frame_table_rejected(self):
        for value in ("not hex", "0" * 100, "00" * 9000):
            p = fixture(); p["assetPathProof"]["assets"]["atlasHex"] = value
            with self.subTest(value=value[:10]), self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["assetPathProof"]["assets"]["framesHex"] = proof.FRAMES.replace(b"right", b"left").hex()
        with self.assertRaisesRegex(ValueError, "frame table"): proof.validate(p)

    def test_schema_bool_and_geometry_drift_rejected(self):
        p = fixture(); p["assetPathProof"]["assets"]["alias"]["rustCalls"] = [True, 0]
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["assetPathProof"]["assets"]["named"]["size"] = [32, 16]
        with self.assertRaises(ValueError): proof.validate(p)
        p = fixture(); p["assetPathProof"]["visual"]["paintedFallback"] = True
        with self.assertRaises(ValueError): proof.validate(p)

    def test_both_visible_outputs_required(self):
        frame = Image.new("RGBA", (1000, 600), (0, 0, 0, 255)); receipt = {"cameraPosition": [64, 48], "cameraPixelRatio": 2}
        with self.assertRaisesRegex(ValueError, "crop"): proof.visible(frame, receipt)
        frame.paste(tuple(proof.COLOR), (468, 268, 532, 332))
        with self.assertRaisesRegex(ValueError, "label"): proof.visible(frame, receipt)
        frame.paste((255, 255, 255, 255), (465, 215, 540, 220)); proof.visible(frame, receipt)


if __name__ == "__main__": unittest.main()
