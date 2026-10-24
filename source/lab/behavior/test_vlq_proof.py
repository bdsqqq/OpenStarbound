"""Synthetic public-verifier controls; no native-game evidence."""
import base64
import copy
import json
import unittest
from PIL import Image, ImageDraw
import behavior_lab as lab
import vlq_proof as vlq
import test_behavior_lab as fixtures


def proof(backend="cpp"):
    def calls(values):
        return values if backend == "rust" else [0] * 6
    return {"version": 1,
            "assets": {"backend": backend, "pairInputHex": vlq.PAIR_HEX, "pairValue": [-65, 128],
                       "stringInputHex": vlq.STRING_HEX, "stringValue": "x" * 128,
                       "readCalls": {"pair": calls([0, 0, 1, 0, 0, 2]), "string": calls([0, 0, 1, 0, 0, 0])},
                       "visualColor": [255, 0, 0, 255]},
            "save": {"wireHex": vlq.SAVE_BYTES.hex(), "value": copy.deepcopy(vlq.VALUE),
                     "consumed": len(vlq.SAVE_BYTES), "writeCalls": calls([8, 0, 0, 3, 0, 0]),
                     "readCalls": calls([0, 0, 8, 0, 0, 3])},
            "packets": {"currentPingHex": "8101", "currentPongHex": "8200", "legacyPingHex": "00", "legacyPongHex": "00",
                        "decodedTimes": [-65, 128, 0, 0], "signedSize": 2,
                        "sizeCalls": calls([0, 0, 0, 0, 1, 0]), "writeCalls": calls([0, 0, 0, 2, 0, 0]),
                        "readCalls": calls([0, 0, 0, 0, 0, 2])},
            "database": {"valueLengths": [127, 128, 700],
                         "foundHex": [bytes((i + seed) & 255 for i in range(n)).hex() for seed, n in enumerate((127, 128, 700))],
                         "pagesBase64": base64.b64encode(bytes(1024)).decode(), "rustCalls": calls([3, 3, 3, 0, 0, 0])},
            "eof": {"kind": "EofException", "unsignedValue": 1, "consumed": 1, "readCalls": calls([0, 0, 1, 0, 0, 0])}}


class VlqProofTests(unittest.TestCase):
    def setUp(self):
        self.factory = fixtures.BehaviorLabTests()
        self.factory.setUp()

    def tearDown(self):
        self.factory.tearDown()

    def capture(self, label, backend="cpp", lighting="cpp"):
        directory = self.factory.fixture(label, lighting)
        for index, name in enumerate(("lit-room", "occluder-added", "occluder-restored")):
            path = directory / (name + ".json")
            e = lab.load(path)
            e.update(width=160, height=128)
            e["metadata"].update(scenario="vlq-room", cameraPosition=[64, 48], cameraPixelRatio=2, vlqProof=proof(backend))
            path.write_text(json.dumps(e))
            frame = Image.new("RGBA", (160, 128), (22, 0, 0, 255) if index != 1 else (0, 55, 0, 255))
            ImageDraw.Draw(frame).rectangle((48, 32, 111, 95), fill=(255, 0, 0, 255))
            frame.save(directory / (name + ".png"))
        self.factory.seal(directory)
        return directory

    def test_public_compare_and_backend_selection(self):
        reference = self.capture("ref")
        for lighting in ("cpp", "rust"):
            candidate = self.capture("candidate-" + lighting, "rust", lighting)
            result = self.factory.compare(reference, candidate, "compare-" + lighting)
            self.assertTrue(result["passed"], result)
        repeat = self.capture("repeat")
        self.assertTrue(self.factory.compare(reference, repeat, "repeat-check", same=True)["passed"])
        self.assertFalse(self.factory.compare(reference, repeat, "wrong-backend")["passed"])

    def test_independent_wire_values_and_receipts_reject(self):
        mutations = [lambda p: p["save"].update(wireHex=p["save"]["wireHex"] + "00"),
                     lambda p: p["packets"].update(currentPingHex="0181"),
                     lambda p: p["packets"].update(signedSize=True),
                     lambda p: p["assets"].update(pairValue=[65, 128]),
                     lambda p: p["assets"]["readCalls"].update(pair=[0] * 6),
                     lambda p: p["eof"].update(kind="DataStreamException"),
                     lambda p: p["eof"].update(unsignedValue=0),
                     lambda p: p["eof"].update(readCalls=[0] * 6),
                     lambda p: p["database"]["foundHex"].__setitem__(1, "00")]
        for mutate in mutations:
            p = proof("rust")
            mutate(p)
            with self.assertRaises(ValueError):
                vlq.validate({"vlqProof": p})
        p = proof("rust")
        p["packets"]["readCalls"][5] = True
        with self.assertRaises(ValueError):
            vlq.validate({"vlqProof": p})

    def test_database_bytes_not_only_paired_values(self):
        reference = self.capture("ref")
        candidate = self.capture("changed-pages", "rust")
        for name in ("lit-room", "occluder-added", "occluder-restored"):
            path = candidate / (name + ".json")
            e = lab.load(path)
            e["metadata"]["vlqProof"]["database"]["pagesBase64"] = base64.b64encode(bytes([1]) + bytes(1023)).decode()
            path.write_text(json.dumps(e))
        self.factory.seal(candidate)
        result = self.factory.compare(reference, candidate, "pages-differ")
        self.assertFalse(result["passed"])
        self.assertIn("worldState differs", result["frames"]["lit-room"]["errors"])

    def test_invisible_decoded_fixture_rejected_before_manifest(self):
        candidate = self.capture("invisible", "rust")
        for name in ("lit-room", "occluder-added", "occluder-restored"):
            Image.new("RGBA", (160, 128), (22, 0, 0, 255)).save(candidate / (name + ".png"))
        with self.assertRaisesRegex(lab.LabError, "no visible red fixture ink"):
            lab.captures(candidate)

    def test_only_vlq_scene_loads_overlay(self):
        for scene in ("lighting-room", "raycast-room", "encoding-room", "sha256-room"):
            self.assertNotIn("vlq-fixture", lab.asset_overlays(scene))
        self.assertIn("vlq-fixture", lab.asset_overlays("vlq-room"))


if __name__ == "__main__":
    unittest.main()
