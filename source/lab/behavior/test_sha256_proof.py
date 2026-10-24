"""Synthetic verifier sensitivity; never native-game evidence."""
import base64
import hashlib
import json
import unittest
import behavior_lab as lab
import sha256_proof as sha
import test_behavior_lab as fixtures


def proof(backend="cpp", data=b"/fixture.png\x80\x08"):
    chunks = [len(data) - 2, 2]
    return {"version": 1,
            "assets": {"backend": backend, "digestHex": hashlib.sha256(data).hexdigest(),
                       "transcriptBase64": base64.b64encode(data).decode(), "chunkSizes": chunks,
                       "rustCalls": [1, len(chunks), 1, 0] if backend == "rust" else [0] * 4},
            "database": {"backend": backend, "key": sha.KEY,
                         "foundBeforeHex": sha.BEFORE, "foundUpdatedHex": sha.UPDATED,
                         "foundReopenedHex": sha.UPDATED, "removed": True,
                         "containsAfterRemove": False, "recordCountAfterRemove": 0,
                         "rustCalls": [0, 0, 0, 7] if backend == "rust" else [0] * 4}}


class Sha256ProofTests(unittest.TestCase):
    def setUp(self):
        self.factory = fixtures.BehaviorLabTests()
        self.factory.setUp()

    def tearDown(self):
        self.factory.tearDown()

    def capture(self, label, backend="cpp", lighting="cpp", data=b"/fixture.png\x80\x08"):
        directory = self.factory.fixture(label, lighting)
        for name in ("lit-room", "occluder-added", "occluder-restored"):
            path = directory / (name + ".json")
            envelope = lab.load(path)
            envelope["metadata"].update(scenario="sha256-room", sha256Proof=proof(backend, data))
            path.write_text(json.dumps(envelope))
        self.factory.seal(directory)
        return directory

    def test_public_exact_compare_and_backend_selection(self):
        reference = self.capture("reference")
        for lighting in ("cpp", "rust"):
            candidate = self.capture("candidate-" + lighting, "rust", lighting)
            result = self.factory.compare(reference, candidate, "compare-" + lighting)
            self.assertTrue(result["passed"], result)
        repeat = self.capture("repeat")
        self.assertTrue(self.factory.compare(reference, repeat, "repeat-check", same=True)["passed"])
        self.assertFalse(self.factory.compare(reference, repeat, "wrong-backend")["passed"])

    def test_same_input_required_even_if_both_digests_are_correct(self):
        reference = self.capture("reference")
        candidate = self.capture("other-input", "rust", data=b"/different.png\x80\x08")
        result = self.factory.compare(reference, candidate, "different-input")
        self.assertFalse(result["passed"])
        self.assertIn("worldState differs", result["frames"]["lit-room"]["errors"])

    def test_digest_and_chunk_and_canonical_encoding_negatives(self):
        mutations = [lambda p: p["assets"].update(digestHex="0" * 64),
                     lambda p: p["assets"].update(chunkSizes=[1]),
                     lambda p: p["assets"].update(chunkSizes=[True, 2]),
                     lambda p: p["assets"].update(transcriptBase64="%%%"),
                     lambda p: p["assets"].update(transcriptBase64=p["assets"]["transcriptBase64"] + "\n"),
                     lambda p: p.update(version=True)]
        for mutate in mutations:
            p = proof("rust")
            mutate(p)
            with self.assertRaises(ValueError):
                sha.validate({"sha256Proof": p})

    def test_receipts_and_database_observations_are_not_inferred(self):
        for side, op in (("assets", 0), ("assets", 1), ("assets", 2), ("database", 3)):
            p = proof("rust")
            p[side]["rustCalls"][op] = 0
            with self.subTest(side=side, op=op), self.assertRaisesRegex(ValueError, "receipt mismatch"):
                sha.validate({"sha256Proof": p})
        for field, value in (("foundReopenedHex", "00"), ("removed", False),
                             ("containsAfterRemove", True), ("recordCountAfterRemove", False),
                             ("backend", "cpp")):
            p = proof("rust")
            p["database"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                sha.validate({"sha256Proof": p})
        p = proof("rust")
        p["assets"]["rustCalls"][0] = True
        with self.assertRaises(ValueError):
            sha.validate({"sha256Proof": p})

    def test_stage_transcripts_cannot_drift(self):
        candidate = self.capture("stage-drift", "rust")
        path = candidate / "occluder-added.json"
        envelope = lab.load(path)
        envelope["metadata"]["sha256Proof"] = proof("rust", b"different")
        path.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(lab.LabError, "SHA input/database evidence changed"):
            lab.captures(candidate)

    def test_sha_scene_has_no_encoding_overlay(self):
        self.assertNotIn("encoding-fixture", lab.asset_overlays("sha256-room"))


if __name__ == "__main__":
    unittest.main()
