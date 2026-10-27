"""A Python-advertised scene must survive the native startup safety gate."""
from pathlib import Path
import re
import unittest
from unittest import mock
from PIL import Image
import test_string_view_proof as string_view_fixtures
import test_path_embed_proof as path_embed_fixtures
import behavior_lab as lab


def check_native_scenarios(source, scenarios):
    function = source.split("void ClientApplication::validateBehaviorStorage()", 1)[1]
    gate = function.split('throw StarException("BehaviorLab: unsupported scenario")', 1)[0]
    allowed = re.findall(r'scenario != "([a-z0-9-]+)"', gate)
    if not allowed or set(allowed) != set(scenarios):
        raise ValueError("native startup scenario allowlist differs from advertised scenes")


def ttl_capture_gate(source, prepared, stage, clock, deadline):
    """Model ONLY the exact native capture precondition, not cache semantics."""
    prefix = source.split('void ClientApplication::renderBehaviorScenario()', 1)[1].split('  auto world =', 1)[0]
    if '!BehaviorLab::ttlFramePrepared(m_behaviorStage)' in prefix:
        return prepared == stage
    if '!BehaviorLab::ttlReady(m_behaviorStage)' in prefix:
        return stage != 1 or clock >= deadline
    raise ValueError('missing native TTL capture barrier')


class TtlPreparedFrameContractTests(unittest.TestCase):
    def test_deadline_crossing_cannot_capture_previous_phase(self):
        source = (lab.ROOT / 'source/client/StarClientApplication.cpp').read_text()
        self.assertIn('return ttlConsumer().stage == int(stage);', source)
        # Preparation saw deadline-1 and did nothing. Time crosses later in the
        # SAME render: readiness alone would queue phase1 with phase0 metadata.
        self.assertFalse(ttl_capture_gate(source, 0, 1, 99, 100))
        self.assertFalse(ttl_capture_gate(source, 0, 1, 100, 100))
        self.assertTrue(ttl_capture_gate(source, 1, 1, 100, 100))

    def test_old_native_clock_gate_reproduces_stale_phase_in_isolation(self):
        source = (lab.ROOT / 'source/client/StarClientApplication.cpp').read_text()
        old = source.replace('!BehaviorLab::ttlFramePrepared(m_behaviorStage)', '!BehaviorLab::ttlReady(m_behaviorStage)')
        self.assertFalse(ttl_capture_gate(old, 0, 1, 99, 100))
        self.assertTrue(ttl_capture_gate(old, 0, 1, 100, 100))
        with self.assertRaises(AssertionError):
            self.assertFalse(ttl_capture_gate(old, 0, 1, 100, 100))

    def test_label_uses_prepared_phase_not_another_deadline_read(self):
        source = (lab.ROOT / 'source/client/StarClientApplication.cpp').read_text()
        self.assertIn('&& BehaviorLab::ttlFramePrepared(m_behaviorStage))\n        BehaviorLab::renderTtlLabel', source)


class NativeScenarioContractTests(unittest.TestCase):
    def test_every_advertised_scenario_is_accepted(self):
        source = (lab.ROOT / "source/client/StarClientApplication.cpp").read_text()
        check_native_scenarios(source, lab.SCENARIOS)

    def test_known_missing_scene_is_detected_without_mutating_native_source(self):
        source = (lab.ROOT / "source/client/StarClientApplication.cpp").read_text()
        # Exactly the omitted-clause failure observed in assetpath-actual-r1.
        clause = ' && scenario != "assetpath-room"'
        self.assertEqual(source.count(clause), 1)
        with self.assertRaisesRegex(ValueError, "startup scenario allowlist"):
            check_native_scenarios(source.replace(clause, "", 1), lab.SCENARIOS)

    def test_stringview_is_twentieth_and_overlay_is_isolated(self):
        self.assertEqual(len(lab.SCENARIOS), 23)
        self.assertEqual(lab.SCENARIOS[19], "stringview-room")
        overlay = lab.ROOT / "source/lab/behavior/string-view-assets"
        self.assertEqual(lab.asset_overlays("stringview-room")["string-view-fixture"], overlay)
        for scenario in lab.SCENARIOS:
            if scenario != "stringview-room":
                self.assertNotIn("string-view-fixture", lab.asset_overlays(scenario))

    def test_path_embed_is_twenty_first_and_overlay_is_isolated(self):
        self.assertEqual(len(lab.SCENARIOS), 23)
        self.assertEqual(lab.SCENARIOS[20], "path-embed-room")
        overlay = lab.ROOT / "source/lab/behavior/path-embed-assets"
        self.assertEqual(lab.asset_overlays("path-embed-room")["path-embed-fixture"], overlay)
        for scenario in lab.SCENARIOS:
            if scenario != "path-embed-room":
                self.assertNotIn("path-embed-fixture", lab.asset_overlays(scenario))
        source = (lab.ROOT / "source/client/StarClientApplication.cpp").read_text()
        clause = ' && scenario != "path-embed-room"'
        self.assertEqual(source.count(clause), 1)
        with self.assertRaisesRegex(ValueError, "startup scenario allowlist"):
            check_native_scenarios(source.replace(clause, "", 1), lab.SCENARIOS)

    def test_lru_is_twenty_second_and_overlay_is_isolated(self):
        self.assertEqual(lab.SCENARIOS[21], "lru-room")
        overlays = lab.asset_overlays("lru-room")
        self.assertIn(lab.ROOT / "source/lab/behavior/lru-assets", overlays.values())
        for scenario in lab.SCENARIOS[:21]:
            self.assertNotIn(lab.ROOT / "source/lab/behavior/lru-assets", lab.asset_overlays(scenario).values())
        source = (lab.ROOT / "source/client/StarClientApplication.cpp").read_text()
        clause = ' && scenario != "lru-room"'
        self.assertEqual(source.count(clause), 1)
        with self.assertRaisesRegex(ValueError, "startup scenario allowlist"):
            check_native_scenarios(source.replace(clause, "", 1), lab.SCENARIOS)

    def test_missing_stringview_native_gate_is_detected(self):
        source = (lab.ROOT / "source/client/StarClientApplication.cpp").read_text()
        clause = ' && scenario != "stringview-room"'
        self.assertEqual(source.count(clause), 1)
        with self.assertRaisesRegex(ValueError, "startup scenario allowlist"):
            check_native_scenarios(source.replace(clause, "", 1), lab.SCENARIOS)


class StringViewScenarioIntegrationTests(unittest.TestCase):
    """In-memory synthetic frames only; no game, captures, files, or deletion."""

    def frames(self, backend, mutate=None, scenario="stringview-room", fixture=string_view_fixtures.fixture, image_fixture=None):
        stages = ("lit-room", "occluder-added", "occluder-restored")
        actions = ("room-populated", "foreground-occluder-added", "foreground-occluder-removed")
        directory = mock.Mock()
        pngs = [Path("/synthetic") / (name + ".png") for name in stages]
        receipts = [path.with_suffix(".json") for path in pngs]
        directory.glob.side_effect = lambda pattern: pngs if pattern == "*.png" else receipts
        envelopes = {}
        for index, path in enumerate(receipts):
            r = {field: "synthetic-stable-state" for field in lab.SCENE_FIELDS}
            r.update(scenario=scenario, inWorld=True, stage=stages[index],
                worldId="synthetic-world", worldSize=[256, 128], playerPosition=[10, 20], materialId=1,
                cameraPosition=[64, 48], cameraPixelRatio=2, playerOutsideView=True,
                uiHidden=True, lightingCompleted=True, lightEntityReplicated=True,
                fullbright=False, replicatedSettledUpdates=90, stageIndex=index,
                occluderPresent=index == 1, observedOccluderMaterial=1 if index == 1 else 0,
                action=actions[index], lightingBackend="cpp", rustLightingCalls=0)
            r.update(fixture(backend))
            if mutate:
                mutate(r, index)
            envelopes[path] = {"name": stages[index], "file": pngs[index].name,
                "width": 400 if image_fixture else 24, "height": 240 if image_fixture else 16, "metadata": r,
                "capture": {"source": "final-default-framebuffer", "stage": "after-imgui-before-swap"}}
        def image(path):
            color = (0, 55, 0, 255) if path.stem == stages[1] else (22, 0, 0, 255)
            if image_fixture:
                result = image_fixture()
                result.putpixel((0, 0), color)
                return result
            return Image.new("RGBA", (24, 16), color)
        with mock.patch.object(lab, "check_owned", side_effect=lambda p: p), \
             mock.patch.object(lab, "load", side_effect=envelopes.__getitem__), \
             mock.patch.object(lab, "image", side_effect=image), \
             mock.patch.object(lab, "sha", return_value="0" * 64):
            return lab.captures(directory)

    def compare(self, reference, candidate, same=False):
        def manifest(identity):
            return {"captureId": identity, "assets": {"sha256": "0" * 64},
                "binary": {"sha256": "0" * 64}, "overlayFiles": {},
                "semanticBootconfig": {}, "semanticConfiguration": {}}
        with mock.patch.object(lab, "create_owned", side_effect=lambda p: p), \
             mock.patch.object(lab, "check_owned", side_effect=lambda p: p), \
             mock.patch.object(lab, "validated", side_effect=[(reference, manifest("reference")), (candidate, manifest("candidate"))]), \
             mock.patch.object(lab, "dump"), \
             mock.patch.object(lab, "image", return_value=Image.new("RGBA", (24, 16))), \
             mock.patch.object(Image.Image, "save"):
            return lab.pair_compare(Path("/synthetic/reference"), Path("/synthetic/candidate"),
                Path("/synthetic/report"), same_backend=same)

    def test_synthetic_cpp_repeat_and_rust_pair_pass(self):
        cpp, rust = self.frames("cpp"), self.frames("rust")
        self.assertTrue(self.compare(cpp, cpp, same=True)["passed"])
        self.assertTrue(self.compare(cpp, rust)["passed"])

    def test_pair_rejects_wrong_backend(self):
        cpp, rust = self.frames("cpp"), self.frames("rust")
        for ref, cand, same in ((cpp, cpp, False), (rust, rust, False), (cpp, rust, True)):
            result = self.compare(ref, cand, same)
            self.assertFalse(result["passed"])
            self.assertIn("StringView backend", str(result))

    def test_captures_reject_missing_proof(self):
        with self.assertRaisesRegex(lab.LabError, "missing consumer proof"):
            self.frames("rust", lambda r, i: r.pop("stringViewProof"))

    def test_captures_reject_each_missing_required_mode(self):
        for index, modes in enumerate(string_view_fixtures.p.REQUIRED):
            for mode in modes:
                def mutate(r, stage):
                    q = r["stringViewProof"]
                    for event in string_view_fixtures.p.EVENTS:
                        q["scopes"][index]["calls"][event][mode] = 0
                    string_view_fixtures.aggregate(q)
                with self.subTest(scope=index, mode=mode), self.assertRaisesRegex(lab.LabError, "missing consumer mode"):
                    self.frames("rust", mutate)

    def test_pair_revalidates_normalized_observations_via_captures(self):
        def mutate(r, stage):
            if stage == 1:
                r["stringViewProof"]["font"]["glyphs"][0]["rgba"] = [18, 52, 86, 255]
        with self.assertRaisesRegex(lab.LabError, "foreground font"):
            self.frames("rust", mutate)


class PathEmbedScenarioIntegrationTests(unittest.TestCase):
    """Exercise common scene plumbing with synthetic states, not game captures."""

    def frames(self, backend, mutate=None):
        return StringViewScenarioIntegrationTests().frames(backend, mutate,
            scenario="path-embed-room", fixture=path_embed_fixtures.fixture,
            image_fixture=path_embed_fixtures.frame)

    def compare(self, reference, candidate, same=False):
        return StringViewScenarioIntegrationTests().compare(reference, candidate, same)

    def test_synthetic_native_repeat_and_rust_pair_pass(self):
        native, rust = self.frames("native"), self.frames("rust")
        self.assertTrue(self.compare(native, native, same=True)["passed"])
        self.assertTrue(self.compare(native, rust)["passed"])

    def test_pair_rejects_wrong_backend(self):
        native, rust = self.frames("native"), self.frames("rust")
        for ref, cand, repeat in ((native, native, False), (rust, rust, False), (native, rust, True)):
            result = self.compare(ref, cand, repeat)
            self.assertFalse(result["passed"])
            self.assertIn("PathEmbed backend", str(result))

    def test_captures_reject_missing_or_bypassed_measurement(self):
        with self.assertRaises(lab.LabError):
            self.frames("rust", lambda r, i: r.pop("pathEmbedProof"))
        for operation in ("selector", "escape"):
            def mutate(r, index):
                m = r["pathEmbedProof"]["source"]["measurement"]
                m["delta"][operation] = m["after"][operation] = 0
            with self.subTest(operation=operation), self.assertRaises(lab.LabError):
                self.frames("rust", mutate)

    def test_capture_sequence_rejects_stale_valid_measurement(self):
        def mutate(r, index):
            if index == 1:
                m = r["pathEmbedProof"]["source"]["measurement"]
                m["before"] = {"selector": 1, "escape": 1}
                m["after"] = {"selector": 2, "escape": 2}
        with self.assertRaisesRegex(lab.LabError, "changed across stages"):
            self.frames("rust", mutate)

    def test_common_occluder_contract_still_required(self):
        with self.assertRaises(lab.LabError):
            self.frames("rust", lambda r, i: r.update(occluderPresent=False))


if __name__ == "__main__": unittest.main()
