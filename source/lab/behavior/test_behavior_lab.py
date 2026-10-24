"""Synthetic negative controls only; these do NOT establish real-game parity."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from PIL import Image
import behavior_lab as lab


class BehaviorLabTests(unittest.TestCase):
    def setUp(self):
        lab.BUILD.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="behavior-selftest-", dir=lab.BUILD)
        self.root = Path(self.temp.name)

    def tearDown(self):
        # Only the test-created temporary tree is removed, never run artifacts.
        self.temp.cleanup()

    def fixture(self, label, backend="cpp"):
        directory = lab.create_owned(self.root / label)
        # Synthetic values follow the native schema, not native-game evidence.
        stages = ("lit-room", "occluder-added", "occluder-restored")
        actions = ("room-populated", "foreground-occluder-added", "foreground-occluder-removed")
        for index, color in enumerate(((22, 0, 0), (0, 55, 0), (22, 0, 0))):
            name = stages[index]
            Image.new("RGB", (24, 16), color).save(directory / f"{name}.png")
            lab.dump(directory / f"{name}.json", {"name": name, "file": name + ".png", "width": 24, "height": 16,
                     "capture": {"source": "final-default-framebuffer", "stage": "after-imgui-before-swap"},
                     "metadata": {"scenario": "lighting-room", "inWorld": True, "stage": name,
                     "worldState": {"light": True, "occluder": index == 1, "position": [10, 20]},
                     "worldId": "synthetic-world", "worldSize": [256, 128],
                     "playerPosition": [10, 20], "cameraPosition": [62, 48], "cameraPixelRatio": 3,
                     "playerOutsideView": True, "uiHidden": True,
                     "stabilization": {"sky": "barren-black", "stars": False, "debris": False,
                                       "spawning": False, "lightFlicker": False, "objectAnimation": False},
                     "lightingCompleted": True, "fullbright": False,
                     "material": "smoothmetal", "materialId": 1,
                     "lightObject": "behaviorlabconstantlight", "lightEntityId": 100,
                     "lightPosition": [48, 48], "lightColor": [1.0, 0.82, 0.63],
                     "lightType": "PointAsSpread", "lightEntityReplicated": True,
                     "changedTileMin": [62, 33], "changedTileMax": [62, 59],
                     "occluderPresent": index == 1, "observedOccluderMaterial": 1 if index == 1 else 0,
                     "action": actions[index], "seed": 42, "stageIndex": index,
                     "replicatedSettledUpdates": 90, "updateIndex": 150 + index,
                     "lightingBackend": backend, "rustLightingCalls": 15 if backend == "rust" else 0}})
        self.seal(directory)
        return directory

    def seal(self, directory):
        # Fixtures deliberately use fake identities: never presented as native evidence.
        manifest = directory / "manifest.json"
        if manifest.exists():
            manifest.unlink()
        identity = {"sha256": "0" * 64, "path": "synthetic-negative-control", "size": 0}
        lab.dump(manifest, {"schema": 1, "exitCode": 0, "captureId": str(directory),
                           "buildProvenance": {"schema": 1, "binary": identity["path"],
                               "binary_sha256": identity["sha256"],
                               "source_files": {"synthetic-negative-control.cpp": "0" * 64}},
                           "overlayFiles": {}, "semanticBootconfig": {}, "semanticConfiguration": {},
                           "frames": lab.inventory(lab.captures(directory)),
                           **{key: identity for key in ("binary", "assets", "configuration", "bootconfig")}})

    def compare(self, reference, candidate, label="comparison", same=False):
        return lab.pair_compare(reference, candidate, self.root / label, same_backend=same)

    def snapshot(self, directory):
        return {str(p.relative_to(directory)): lab.sha(p) for p in directory.rglob("*") if p.is_file()}

    def test_native_lighting_requires_restored_pixels_and_state(self):
        stages = ("lit-room", "occluder-added", "occluder-restored")
        actions = ("room-populated", "foreground-occluder-added", "foreground-occluder-removed")
        valid = {name: {"pixelsSha256": "occluded" if index == 1 else "lit",
                       "receipt": {"stage": name, "stageIndex": index, "action": actions[index],
                                   "occluderPresent": index == 1, "materialId": 1,
                                   "observedOccluderMaterial": 1 if index == 1 else 0}}
                 for index, name in enumerate(stages)}
        lab.validate_lighting_sequence(valid)
        for fault in ("restored-pixels", "unchanged", "action", "material", "restored-state",
                      "restored-declared-state", "missing"):
            with self.subTest(fault=fault):
                frames = json.loads(json.dumps(valid))
                if fault == "restored-pixels":
                    frames[stages[2]]["pixelsSha256"] = "different"
                elif fault == "unchanged":
                    frames[stages[1]]["pixelsSha256"] = "lit"
                elif fault == "action":
                    frames[stages[1]]["receipt"]["action"] = "room-populated"
                elif fault == "material":
                    frames[stages[1]]["receipt"]["observedOccluderMaterial"] = 0
                elif fault == "restored-state":
                    frames[stages[2]]["receipt"]["lightColor"] = [0, 0, 0]
                elif fault == "restored-declared-state":
                    frames[stages[0]]["receipt"]["worldState"] = {"declared": {"light": True}}
                    frames[stages[2]]["receipt"]["worldState"] = {"declared": {"light": False}}
                else:
                    del frames[stages[2]]
                with self.assertRaises(lab.LabError):
                    lab.validate_lighting_sequence(frames)

    def test_public_capture_and_compare_reject_contract_downgrades(self):
        reference = self.fixture("ref")
        for fault, reason in (("generic-names", "exactly its three named stages"),
                              ("declared-only", "missing native scene state"),
                              ("missing-field", "missing native scene state: lightColor"),
                              ("fullbright", "bypasses lighting")):
            with self.subTest(fault=fault):
                candidate = self.fixture(fault, "rust")
                stages = ("lit-room", "occluder-added", "occluder-restored")
                for index, name in enumerate(stages):
                    path = candidate / f"{name}.json"
                    envelope = lab.load(path)
                    metadata = envelope["metadata"]
                    if fault == "generic-names":
                        generic = f"stage-{index}"
                        envelope.update(name=generic, file=generic + ".png")
                        metadata["stage"] = generic
                        (candidate / f"{name}.png").rename(candidate / f"{generic}.png")
                        path.rename(candidate / f"{generic}.json")
                        path = candidate / f"{generic}.json"
                    elif fault == "declared-only":
                        for field in lab.SCENE_FIELDS:
                            del metadata[field]
                    elif fault == "missing-field":
                        del metadata["lightColor"]
                    else:
                        metadata["fullbright"] = True
                    path.write_text(json.dumps(envelope))
                # Do not reseal: validation must reject the capture before integrity checking.
                with self.assertRaisesRegex(lab.LabError, reason):
                    lab.captures(candidate)
                report = self.compare(reference, candidate, "compare-" + fault)
                self.assertFalse(report["passed"])
                self.assertIn(reason, report["errors"][0])
                self.assertNotIn("changed since manifest", report["errors"][0])

    def test_exact_pass_nonwriting_verifier(self):
        reference, candidate = self.fixture("ref"), self.fixture("candidate", "rust")
        before = [self.snapshot(p) for p in (reference, candidate)]
        report = self.compare(reference, candidate)
        self.assertTrue(report["passed"], report)
        self.assertEqual(before, [self.snapshot(p) for p in (reference, candidate)])
        self.assertTrue((self.root / "comparison/lit-room-diff.png").is_file())
        self.assertEqual(report["frames"]["lit-room"]["maxError"], 0)

    def test_one_pixel_tile_and_color_corruption_detected(self):
        reference = self.fixture("ref")
        for kind in ("one-pixel", "tile", "color"):
            with self.subTest(kind=kind):
                candidate = self.fixture(kind, "rust")
                path = candidate / "lit-room.png"
                frame = lab.image(path)
                if kind == "one-pixel":
                    frame.putpixel((3, 4), (23, 0, 0, 255))
                elif kind == "tile":
                    frame.paste((255, 255, 0, 255), (0, 0, 8, 8))
                else:
                    frame = Image.new("RGBA", frame.size, (0, 22, 0, 255))
                frame.save(path)
                frame.save(candidate / "occluder-restored.png")
                self.seal(candidate)  # Exercise pixel gate, not only hash-integrity gate.
                before = self.snapshot(candidate)
                report = self.compare(reference, candidate, "diff-" + kind)
                self.assertFalse(report["passed"])
                row = report["frames"]["lit-room"]
                self.assertGreater(row["maxError"], 0)
                self.assertEqual(row["changedPixels"], {"one-pixel": 1, "tile": 64, "color": 384}[kind])
                self.assertEqual(before, self.snapshot(candidate))

    def test_alpha_only_corruption_detected(self):
        reference, candidate = self.fixture("ref"), self.fixture("candidate", "rust")
        path = candidate / "lit-room.png"
        frame = lab.image(path)
        frame.putpixel((0, 0), (22, 0, 0, 254))
        frame.save(path)
        frame.save(candidate / "occluder-restored.png")
        self.seal(candidate)
        report = self.compare(reference, candidate)
        self.assertFalse(report["passed"])
        self.assertEqual(report["frames"]["lit-room"]["changedPixels"], 1)

    def test_reference_nondeterminism_blocks(self):
        reference, repeat = self.fixture("ref"), self.fixture("repeat")
        for name in ("lit-room", "occluder-restored"):
            path = repeat / f"{name}.json"
            receipt = lab.load(path)
            receipt["metadata"]["worldState"]["light"] = 900
            path.write_text(json.dumps(receipt))
        self.seal(repeat)
        report = self.compare(reference, repeat, same=True)
        self.assertFalse(report["passed"])
        self.assertIn("worldState differs", report["frames"]["lit-room"]["errors"])

    def test_changed_since_capture_rejected(self):
        reference, candidate = self.fixture("ref"), self.fixture("candidate", "rust")
        for name in ("lit-room", "occluder-restored"):
            Image.new("RGB", (24, 16), "white").save(candidate / f"{name}.png")
        report = self.compare(reference, candidate)
        self.assertFalse(report["passed"])
        self.assertIn("changed since manifest", report["errors"][0])

    def test_missing_frame_rejected(self):
        reference, candidate = self.fixture("ref"), self.fixture("candidate", "rust")
        (candidate / "occluder-added.png").unlink()
        self.assertFalse(self.compare(reference, candidate)["passed"])

    def test_dimensions_mismatch(self):
        reference, candidate = self.fixture("ref"), self.fixture("candidate", "rust")
        for name in ("lit-room", "occluder-restored"):
            Image.new("RGB", (12, 16), "red").save(candidate / f"{name}.png")
            receipt_path = candidate / f"{name}.json"
            receipt = lab.load(receipt_path)
            receipt["width"] = 12
            receipt_path.write_text(json.dumps(receipt))
        self.seal(candidate)
        report = self.compare(reference, candidate)
        self.assertFalse(report["passed"])
        self.assertIn("dimensions differ", report["frames"]["lit-room"]["errors"])

    def test_wrong_backend_zero_calls_or_nonworld_refused(self):
        for field, value, reason in (("lightingBackend", "cpp", "reference exercised Rust"),
                                     ("rustLightingCalls", 0, "Rust backend never exercised"),
                                     ("inWorld", False, "not in-world")):
            with self.subTest(field=field):
                reference, candidate = self.fixture("ref-" + field), self.fixture("cand-" + field, "rust")
                path = candidate / "lit-room.json"
                receipt = lab.load(path)
                receipt["metadata"][field] = value
                path.write_text(json.dumps(receipt))
                # Invalid receipts must fail even before provenance sealing.
                with self.assertRaisesRegex(lab.LabError, reason):
                    lab.captures(candidate)

    def test_static_scene_refused(self):
        candidate = self.fixture("candidate", "rust")
        for path in candidate.glob("*.png"):
            Image.new("RGB", (24, 16), "black").save(path)
        with self.assertRaisesRegex(lab.LabError, "occluder did not change the pixels"):
            lab.captures(candidate)

    def test_unsafe_storage_and_reuse_refused_without_writes(self):
        storage = lab.ROOT / "storage"
        before = sorted(storage.iterdir()) if storage.exists() else None
        for path in (storage, Path.home(), lab.BUILD, self.root / "../.." / "storage"):
            with self.subTest(path=path), self.assertRaises(lab.LabError):
                lab.create_owned(path)
        self.assertEqual(before, sorted(storage.iterdir()) if storage.exists() else None)
        with self.assertRaises(lab.LabError):
            lab.create_owned(self.root)

    def test_symlink_output_and_input_refused(self):
        (self.root / "escape").symlink_to(lab.ROOT / "storage", target_is_directory=True)
        with self.assertRaises(lab.LabError):
            lab.create_owned(self.root / "escape/new-run")
        candidate = self.fixture("candidate", "rust")
        receipt = candidate / "lit-room.json"
        receipt.unlink()
        receipt.symlink_to(candidate / "occluder-added.json")
        with self.assertRaises(lab.LabError):
            lab.captures(candidate)

    def test_repeat_must_be_independent(self):
        reference = self.fixture("ref")
        self.assertFalse(self.compare(reference, reference, same=True)["passed"])

    def test_overlay_and_semantic_configuration_mismatch_block(self):
        reference = self.fixture("ref")
        for field in ("overlayFiles", "semanticBootconfig", "semanticConfiguration"):
            candidate = self.fixture("candidate-" + field, "rust")
            path = candidate / "manifest.json"
            manifest = lab.load(path)
            manifest[field] = {"changed": True}
            path.write_text(json.dumps(manifest))
            report = self.compare(reference, candidate, "comparison-" + field)
            self.assertFalse(report["passed"])
            self.assertIn(field, report["errors"][0])

    def test_run_blocks_candidate_after_nondeterministic_baseline(self):
        reference, repeat = self.fixture("ref"), self.fixture("repeat")
        path = repeat / "lit-room.png"
        frame = lab.image(path)
        frame.putpixel((0, 0), (23, 0, 0, 255))
        frame.save(path)
        frame.save(repeat / "occluder-restored.png")
        self.seal(repeat)
        with mock.patch.object(lab, "capture", side_effect=[reference, repeat]) as capture:
            result = lab.main(["run", "--reference", "/unused/ref", "--candidate", "/unused/cand",
                               "--assets", "/unused/assets", "--output", str(self.root / "run")])
        self.assertEqual(result, 1)
        self.assertEqual(capture.call_count, 2)
        self.assertIn("blocks candidate", lab.load(self.root / "run/report.json")["reason"])

    def test_native_flat_scene_metadata_projection_and_missing_fields(self):
        native = {field: "stable-test-state" for field in lab.SCENE_FIELDS}
        for field in ("playerOutsideView", "uiHidden", "lightingCompleted", "lightEntityReplicated"):
            native[field] = True
        native.update(fullbright=False, replicatedSettledUpdates=90, updateIndex=150)
        state = lab.semantic_world_state(native)
        self.assertEqual(set(state), set(lab.SCENE_FIELDS))
        self.assertNotIn("updateIndex", state)
        native["updateIndex"] = 500
        native["replicatedSettledUpdates"] = 100
        self.assertEqual(state, lab.semantic_world_state(native))
        native["worldState"] = {"declaredScene": "stable"}
        combined = lab.semantic_world_state(native)
        self.assertEqual(combined["native"], state)
        self.assertEqual(combined["declared"], native["worldState"])
        native["uiHidden"] = False
        with self.assertRaisesRegex(lab.LabError, "uiHidden"):
            lab.semantic_world_state(native)
        native["uiHidden"] = True
        del native["lightColor"]
        with self.assertRaisesRegex(lab.LabError, "lightColor"):
            lab.semantic_world_state(native)

    def test_cli_baseline_diagnostic_never_claims_candidate_parity(self):
        reference, repeat = self.fixture("ref"), self.fixture("repeat")
        output = self.root / "diagnostic"
        code = lab.main(["compare", "--same-backend", "--reference", str(reference),
                         "--candidate", str(repeat), "--output", str(output)])
        self.assertEqual(code, 0)
        report = lab.load(output / "report.json")
        self.assertTrue(report["passed"])
        self.assertFalse(report["parityCertified"])
        self.assertEqual(report["kind"], "reference-repeatability-only")

    def test_constant_light_asset_contract(self):
        base = lab.ASSET_OVERLAYS["behavior-fixture"] / "objects/behaviorlab/constantlight"
        config = lab.load(base / "constantlight.object")
        self.assertEqual(config["objectName"], "behaviorlabconstantlight")
        self.assertEqual(config["lightColor"], [255, 210, 160])
        self.assertFalse(config["pointLight"])
        self.assertEqual(config["lightType"], "PointAsSpread")
        self.assertTrue(config["unbreakable"])
        self.assertFalse(config["hasObjectItem"])
        for key in ("scripts", "animationScripts", "particleEmitters"):
            self.assertFalse(config.get(key))
        for key in ("animation", "flickerPeriod", "soundEffect", "particleEmitter"):
            self.assertNotIn(key, config)
        self.assertEqual(len(config["orientations"]), 1)
        orientation = config["orientations"][0]
        self.assertEqual(orientation["spaces"], [[0, 0]])
        self.assertEqual(orientation["anchors"], ["bottom"])
        self.assertEqual(orientation["anchorMaterial"], "smoothmetal")
        self.assertEqual(orientation["lightPosition"], [0, 0])
        self.assertEqual(orientation["frames"], 1)
        self.assertEqual(orientation["imagePosition"], [0, 0])
        for key in ("particleEmitter", "particleEmitters"):
            self.assertNotIn(key, orientation)
        sprite = lab.image(base / orientation["image"])
        self.assertEqual(sprite.size, (8, 8))
        self.assertEqual(sprite.getchannel("A").getextrema(), (255, 255))

    def test_overlay_hashes_namespaced_and_reject_symlinks(self):
        sources = {}
        for name in ("opensb", "behavior-fixture"):
            source = self.root / name
            source.mkdir()
            (source / "same.object").write_text(name)
            sources[name] = source
        with mock.patch.object(lab, "ASSET_OVERLAYS", sources):
            before = lab.overlay_identity()
            self.assertEqual(set(before), {"opensb/same.object", "behavior-fixture/same.object"})
            self.assertNotEqual(*before.values())
            fixture = sources["behavior-fixture"] / "same.object"
            fixture.write_text("changed constant light")
            self.assertNotEqual(before, lab.overlay_identity())
            (sources["behavior-fixture"] / "linked").symlink_to(sources["opensb"], target_is_directory=True)
            with self.assertRaisesRegex(lab.LabError, "symlink"):
                lab.overlay_identity()
        with mock.patch.object(lab, "ASSET_OVERLAYS", {"behavior-fixture": self.root / "absent"}):
            with self.assertRaisesRegex(lab.LabError, "overlay missing"):
                lab.overlay_identity()

    def test_capture_runner_isolates_bootconfig_and_seals_inputs(self):
        source = self.fixture("source-frames")
        executable = self.root / "fake-client"
        executable.write_text(
            "#!" + os.sys.executable + "\n"
            "import json, os, pathlib, shutil, sys\n"
            "config = json.loads(pathlib.Path(os.environ['STAR_BEHAVIOR_LAB']).read_text())\n"
            "boot = json.loads(pathlib.Path(sys.argv[2]).read_text())\n"
            "out = pathlib.Path(config['outputDirectory'])\n"
            "assert (out / '.star-behavior-lab').is_file()\n"
            "assert boot['includeUGC'] is False and config['platformWrites'] is False\n"
            "assert pathlib.Path(boot['storageDirectory']).parent == out\n"
            "assert config['storageDirectory'] == boot['storageDirectory']\n"
            "assert boot['logDirectory'] == boot['storageDirectory']\n"
            "assert (pathlib.Path(boot['storageDirectory']) / '.star-behavior-lab').is_file()\n"
            "assert pathlib.Path(os.environ['HOME']).parent == pathlib.Path.cwd()\n"
            f"source = pathlib.Path({str(source)!r})\n"
            "for p in source.iterdir():\n"
            "    if p.suffix == '.png' or (p.suffix == '.json' and p.name != 'manifest.json'):\n"
            "        shutil.copyfile(p, out / p.name)\n")
        executable.chmod(0o755)
        assets = self.root / "packed.pak"
        assets.write_bytes(b"synthetic assets only")
        lab.build_provenance.seal(executable, lab.build_provenance.begin())
        captured = lab.capture(executable, assets, self.root / "isolated-run", 10)
        frames, manifest = lab.validated(captured)
        self.assertEqual(len(frames), 3)
        self.assertEqual(manifest["binary"]["sha256"], lab.sha(executable))
        self.assertEqual(manifest["assets"]["sha256"], lab.sha(assets))
        boot = lab.load(captured.parent / "sbinit.config")
        self.assertEqual(boot["assetSources"], [str(assets), *(str(p.resolve()) for p in lab.ASSET_OVERLAYS.values())])
        fixture_prefix = "behavior-fixture/objects/behaviorlab/constantlight/"
        for filename in ("constantlight.object", "constantlight.png"):
            path = lab.ASSET_OVERLAYS["behavior-fixture"] / "objects/behaviorlab/constantlight" / filename
            self.assertEqual(manifest["overlayFiles"][fixture_prefix + filename], lab.sha(path))
        self.assertEqual(lab.load(captured.parent / "launch.json")["overlayFiles"], manifest["overlayFiles"])
        self.assertEqual(manifest["semanticConfiguration"]["outputDirectory"], "<isolated-output>")
        self.assertNotIn(str(lab.ROOT / "storage"), (captured.parent / "sbinit.config").read_text())
        repeated = lab.capture(executable, assets, self.root / "isolated-repeat", 10)
        self.assertTrue(self.compare(captured, repeated, "isolated-repeat-check", same=True)["passed"])

    def test_capture_rejects_stale_build_before_outputs_or_launch(self):
        source_root = self.root / "fake-source"
        (source_root / "source").mkdir(parents=True)
        source = source_root / "source/demo.cpp"
        source.write_text("// first revision")
        executable = self.root / "stale-client"
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        assets = self.root / "assets.pak"
        assets.write_bytes(b"synthetic assets")
        proof = lab.build_provenance.begin(source_root=source_root)
        lab.build_provenance.seal(executable, proof, source_root=source_root)
        source.write_text("// edited without rebuilding")
        output = self.root / "must-not-create"
        with mock.patch.object(lab.build_provenance, "SOURCE_ROOT", source_root), mock.patch.object(lab.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(lab.LabError, "build inputs differ"):
                lab.capture(executable, assets, output, 10)
            launch.assert_not_called()
        self.assertFalse(output.exists())

    def test_compare_rejects_missing_build_source_identity(self):
        reference, candidate = self.fixture("ref"), self.fixture("candidate", "rust")
        path = candidate / "manifest.json"
        manifest = lab.load(path)
        del manifest["buildProvenance"]
        path.write_text(json.dumps(manifest))
        report = self.compare(reference, candidate)
        self.assertFalse(report["passed"])
        self.assertIn("source-bound build identity", report["errors"][0])

    def test_capture_timeout_retains_failure_and_kills_owned_process(self):
        executable = self.root / "sleeper"
        executable.write_text("#!" + os.sys.executable + "\nimport time\ntime.sleep(60)\n")
        executable.chmod(0o755)
        assets = self.root / "packed.pak"
        assets.write_bytes(b"synthetic assets")
        lab.build_provenance.seal(executable, lab.build_provenance.begin())
        run = self.root / "timed-out-run"
        with self.assertRaises(subprocess.TimeoutExpired):
            lab.capture(executable, assets, run, 0.05)
        failure = lab.load(run / "failure.json")
        self.assertIn("timed out", failure["reason"])
        with self.assertRaises(ProcessLookupError):
            os.killpg(failure["pid"], 0)
        self.assertFalse((run / "frames/manifest.json").exists())

    def test_capture_unsafe_storage_never_launches(self):
        assets = self.root / "packed.pak"
        assets.write_bytes(b"synthetic assets")
        with mock.patch.object(lab.subprocess, "Popen") as popen:
            with self.assertRaises(lab.LabError):
                lab.capture(Path(os.sys.executable).resolve(), assets, lab.ROOT / "storage", 10)
        popen.assert_not_called()

    def test_timeout_private_group_cleanup(self):
        # No native game launch: a Python sleeper in a private session only.
        process = subprocess.Popen([os.sys.executable, "-c", "import time; time.sleep(60)"],
                                   cwd=self.root, start_new_session=True)
        lab.stop_process_group(process)
        self.assertIsNotNone(process.poll())
        with self.assertRaises(ProcessLookupError):
            os.killpg(process.pid, 0)


if __name__ == "__main__":
    unittest.main()
