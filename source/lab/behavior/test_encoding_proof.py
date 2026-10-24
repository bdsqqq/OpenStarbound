"""Synthetic sensitivity fixtures, never evidence of a running game."""
import base64
import copy
import io
import json
import unittest
from PIL import Image
import behavior_lab as lab
import encoding_proof as encoding
import test_behavior_lab as fixtures


def pattern():
    image = Image.new("RGBA", (16, 16))
    image.putdata([encoding.PALETTE[(x // 4 + y // 4 + 1) % 4] for y in range(16) for x in range(16)])
    return image


def proof(backend="cpp"):
    stream = io.BytesIO()
    pattern().save(stream, format="PNG")
    png = stream.getvalue()
    return dict(version=1, patternSize=[16, 16], backend=backend, drawDirective="multiply=ffffff",
                embeddedPath="/opensb_data;bin;" + base64.urlsafe_b64encode(png).decode().rstrip("="),
                dataUri="data:image/png;base64," + base64.b64encode(png).decode(),
                receipts={scope: [int(backend == "rust" and op in active) for op in range(5)]
                          for scope, active in encoding.SCOPES.items()},
                drawReceipts=[int(backend == "rust"), 0, 0, 0, 0])


class EncodingProofTests(unittest.TestCase):
    def setUp(self):
        self.factory = fixtures.BehaviorLabTests()
        self.factory.setUp()

    def tearDown(self):
        self.factory.tearDown()

    def capture(self, label, backend="cpp", lighting="cpp", visible=True):
        directory = self.factory.fixture(label, lighting)
        for index, name in enumerate(("lit-room", "occluder-added", "occluder-restored")):
            path = directory / (name + ".json")
            envelope = lab.load(path)
            envelope.update(width=160, height=128)
            envelope["metadata"].update(scenario="encoding-room", cameraPosition=[64, 48], cameraPixelRatio=2,
                                          encodingProof=proof(backend))
            path.write_text(json.dumps(envelope))
            frame = Image.new("RGBA", (160, 128), (22, 0, 0, 255) if index != 1 else (0, 55, 0, 255))
            if visible:
                frame.paste(pattern().resize((64, 64), Image.Resampling.NEAREST), (48, 32))
            frame.save(directory / (name + ".png"))
        self.factory.seal(directory)
        return directory

    def test_exact_public_compare_and_backend_attribution(self):
        reference = self.capture("reference")
        for lighting in ("cpp", "rust"):
            candidate = self.capture("candidate-" + lighting, "rust", lighting)
            result = self.factory.compare(reference, candidate, "compare-" + lighting)
            self.assertTrue(result["passed"], result)
        repeat = self.capture("repeat")
        self.assertTrue(self.factory.compare(reference, repeat, "repeat-check", same=True)["passed"])
        self.assertFalse(self.factory.compare(reference, repeat, "wrong-backend")["passed"])

    def test_each_required_operation_receipt_is_observable(self):
        valid = proof("rust")
        for scope, active in {**encoding.SCOPES, "draw": {0}}.items():
            for op in active:
                bad = copy.deepcopy(valid)
                calls = bad["drawReceipts"] if scope == "draw" else bad["receipts"][scope]
                calls[op] = 0
                with self.subTest(scope=scope, op=op), self.assertRaisesRegex(ValueError, "receipt mismatch"):
                    encoding.validate({"encodingProof": bad})
        for value in (True, -1, 1.5, float("nan"), 10**100):
            bad = copy.deepcopy(valid)
            bad["drawReceipts"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                encoding.validate({"encodingProof": bad})

    def test_schema_byte_and_pattern_failures(self):
        valid = proof()
        mutations = [lambda p: p.pop("receipts"), lambda p: p.update(version=True),
                     lambda p: p.update(embeddedPath=p["embeddedPath"] + "="),
                     lambda p: p.update(dataUri=p["dataUri"][:-1] + "A"),
                     lambda p: p.update(drawDirective="multiply=000000")]
        for mutate in mutations:
            bad = copy.deepcopy(valid)
            mutate(bad)
            with self.assertRaises(ValueError):
                encoding.validate({"encodingProof": bad})
        # A mutually consistent wrong round-trip still must fail the independent pattern.
        stream = io.BytesIO()
        Image.new("RGBA", (16, 16), "red").save(stream, format="PNG")
        png = stream.getvalue()
        bad = dict(valid, embeddedPath="/opensb_data;bin;" + base64.urlsafe_b64encode(png).decode().rstrip("="),
                   dataUri="data:image/png;base64," + base64.b64encode(png).decode())
        with self.assertRaisesRegex(ValueError, "independent rotated pattern"):
            encoding.validate({"encodingProof": bad})

    def test_invisible_pattern_rejected_before_manifest_hash(self):
        candidate = self.capture("invisible", "rust")
        for name in ("lit-room", "occluder-added", "occluder-restored"):
            Image.new("RGBA", (160, 128), (22, 0, 0, 255)).save(candidate / (name + ".png"))
        with self.assertRaisesRegex(lab.LabError, "missing visible palette ink"):
            lab.captures(candidate)

    def test_stage_bytes_cannot_drift_even_when_decoded_pixels_match(self):
        candidate = self.capture("stage-drift", "rust")
        stream = io.BytesIO()
        pattern().save(stream, format="PNG", compress_level=0)
        png = stream.getvalue()
        path = candidate / "occluder-added.json"
        envelope = lab.load(path)
        p = envelope["metadata"]["encodingProof"]
        p["embeddedPath"] = "/opensb_data;bin;" + base64.urlsafe_b64encode(png).decode().rstrip("=")
        p["dataUri"] = "data:image/png;base64," + base64.b64encode(png).decode()
        encoding.validate({"encodingProof": p})
        path.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(lab.LabError, "encoding bytes changed across scene stages"):
            lab.captures(candidate)

    def test_existing_scenes_do_not_load_encoding_overlay(self):
        self.assertNotIn("encoding-fixture", lab.asset_overlays("lighting-room"))
        self.assertNotIn("encoding-fixture", lab.asset_overlays("raycast-room"))
        self.assertIn("encoding-fixture", lab.asset_overlays("encoding-room"))


if __name__ == "__main__":
    unittest.main()
