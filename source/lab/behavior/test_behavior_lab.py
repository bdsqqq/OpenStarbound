"""Synthetic negative controls only; these do NOT establish real-game parity."""
import json
import os
from pathlib import Path
import subprocess
import signal
import time
import tempfile
import unittest
from unittest import mock

from PIL import Image, ImageDraw
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

    def ray_fixture(self, label, backend="cpp", lighting="cpp"):
        directory = self.fixture(label, lighting)
        for index, old in enumerate(("lit-room", "occluder-added", "occluder-restored")):
            name = lab.RAY_STAGES[index]
            path = directory / f"{old}.json"
            envelope = lab.load(path)
            path.unlink()
            (directory / f"{old}.png").rename(directory / f"{name}.png")
            envelope.update(name=name, file=name + ".png", width=400, height=200)
            metadata = envelope["metadata"]
            metadata.pop("worldState")
            metadata.update(scenario="raycast-room", stage=name, worldSize=[128, 96],
                            playerPosition=[12, 4], cameraPosition=[64, 48], cameraPixelRatio=2,
                            lightPosition=[52.5, 33.5], changedTileMax=[70, 59])
            point = [61.999900817871094, 48.5] if index == 1 else None
            side = dict(collision=index == 1, point=point, normal=[1, 0] if index == 1 else None,
                        tiles=[[62, 48], [70, 48]] if index == 1 else [],
                        limitedTiles=[[62, 48]] if index == 1 else [], zeroLimitTiles=[],
                        backend=backend, rustCalls={key: 1 if backend == "rust" else 0 for key in lab.RAY_QUERIES})
            metadata["raycastState"] = dict(start=[54.5, 48.5], end=[74.5, 48.5], occluderColumns=[62, 70],
                                            markerEnd=point or [74.5, 48.5], client=side,
                                            server=json.loads(json.dumps(side)))
            # Synthetic verifier-sensitivity ink, NOT native rendering evidence.
            frame = Image.new("RGBA", (400, 200), (22, 0, 0, 255))
            draw = ImageDraw.Draw(frame)
            marker_x = 200 + ((point or [74.5, 48.5])[0] - 64) * 16
            draw.line((48, 92, marker_x, 92), fill=(0, 255, 255, 255), width=4)
            draw.line((marker_x, 86, marker_x, 98), fill=(255, 255, 0, 255), width=4)
            frame.save(directory / f"{name}.png")
            lab.dump(directory / f"{name}.json", envelope)
        self.seal(directory)
        return directory

    def mutate_ray(self, directory, change, stages=("ray-blocked",)):
        for name in stages:
            path = directory / f"{name}.json"
            envelope = lab.load(path)
            change(envelope["metadata"])
            path.write_text(json.dumps(envelope))

    def test_ray_public_exact_compare_and_both_lighting_backends(self):
        reference = self.ray_fixture("ref")
        for lighting in ("cpp", "rust"):
            candidate = self.ray_fixture("candidate-" + lighting, "rust", lighting)
            report = self.compare(reference, candidate, "compare-" + lighting)
            self.assertTrue(report["passed"], report)
        repeat = self.ray_fixture("repeat")
        self.assertTrue(self.compare(reference, repeat, "repeat-check", same=True)["passed"])
        wrong = self.ray_fixture("wrong")
        self.assertFalse(self.compare(reference, wrong, "wrong-check")["passed"])

    def test_ray_public_marker_ink_negatives(self):
        reference = self.ray_fixture("ref")
        for fault in ("missing-yellow", "misplaced-yellow", "wrong-yellow", "transparent-yellow",
                      "missing-cyan", "misplaced-cyan", "wrong-cyan", "clear-end-on-blocked"):
            with self.subTest(fault=fault):
                candidate = self.ray_fixture(fault, "rust")
                # Leave the old manifest: public comparison must reject the ink
                # contract BEFORE merely reporting a stale inventory hash.
                for index, stage in enumerate(lab.RAY_STAGES):
                    frame = Image.new("RGBA", (400, 200), (22, 0, 0, 255))
                    draw = ImageDraw.Draw(frame)
                    endpoint = 200 + ((61.999900817871094 if index == 1 else 74.5) - 64) * 16
                    if fault != "missing-cyan":
                        y = 30 if fault == "misplaced-cyan" else 92
                        color = (255, 0, 255, 255) if fault == "wrong-cyan" else (0, 255, 255, 255)
                        draw.line((48, y, endpoint, y), fill=color, width=4)
                    if fault != "missing-yellow":
                        x, y = (30, 30) if fault == "misplaced-yellow" else (endpoint, 92)
                        if fault == "clear-end-on-blocked" and index == 1:
                            x = 368
                        color = ((255, 0, 255, 255) if fault == "wrong-yellow" else
                                 (255, 255, 0, 0) if fault == "transparent-yellow" else (255, 255, 0, 255))
                        draw.line((x, y - 6, x, y + 6), fill=color, width=4)
                    frame.save(candidate / f"{stage}.png")
                with self.assertRaisesRegex(lab.LabError, "raycast marker missing"):
                    lab.captures(candidate)
                report = self.compare(reference, candidate, "compare-" + fault)
                self.assertFalse(report["passed"])
                self.assertIn("raycast marker missing", report["errors"][0])
                self.assertNotIn("changed since manifest", report["errors"][0])

    def test_ray_marker_projection_rejects_invalid_camera_and_small_viewport(self):
        for label, camera, ratio in (("string", ["64", 48], 2), ("bool", [64, 48], True),
                                     ("huge", [10**1000, 48], 2), ("nan", [64, 48], float("nan"))):
            candidate = self.ray_fixture(label, "rust")
            self.mutate_ray(candidate, lambda m: m.update(cameraPosition=camera, cameraPixelRatio=ratio))
            with self.subTest(label=label), self.assertRaises(lab.LabError):
                lab.captures(candidate)
        candidate = self.ray_fixture("small", "rust")
        for stage in lab.RAY_STAGES:
            Image.new("RGBA", (24, 16)).save(candidate / f"{stage}.png")
            path = candidate / f"{stage}.json"
            envelope = lab.load(path)
            envelope.update(width=24, height=16)
            path.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(lab.LabError, "outside viewport"):
            lab.captures(candidate)

    def test_ray_public_adversarial_query_schema(self):
        reference = self.ray_fixture("ref")
        faults = {
            "missing-state": lambda m: m.pop("raycastState"),
            "missing-native": lambda m: m.pop("lightColor"),
            "declared-only": lambda m: (m.update(worldState={"declared": True}), [m.pop(field) for field in lab.SCENE_FIELDS]),
            "unknown-scenario": lambda m: m.update(scenario="generic-room"),
            "fullbright": lambda m: m.update(fullbright=True),
            "unsettled": lambda m: m.update(replicatedSettledUpdates=89),
            "mixed-scenario": lambda m: m.update(scenario="lighting-room"),
            "wrong-collision": lambda m: m["raycastState"]["client"].update(collision=False),
            "wrong-point": lambda m: m["raycastState"]["client"].update(point=[62, 48.5]),
            "wrong-normal": lambda m: m["raycastState"]["client"].update(normal=[-1, 0]),
            "wrong-tile": lambda m: m["raycastState"]["client"].update(tiles=[[63, 48], [70, 48]]),
            "wrong-order": lambda m: m["raycastState"]["client"]["tiles"].reverse(),
            "wrong-cap": lambda m: m["raycastState"]["client"].update(limitedTiles=[[62, 48], [70, 48]]),
            "zero-cap": lambda m: m["raycastState"]["client"].update(zeroLimitTiles=[[62, 48]]),
            "server-result": lambda m: m["raycastState"]["server"].update(point=[62, 48.5]),
            "server-raw-disagreement": lambda m: m["raycastState"]["server"].update(point=[61.9999, 48.5]),
            "missing-counter": lambda m: m["raycastState"]["client"]["rustCalls"].pop("point"),
            "extra-counter": lambda m: m["raycastState"]["client"]["rustCalls"].update(extra=5),
            "marker": lambda m: m["raycastState"].update(markerEnd=[74.5, 48.5]),
            "unknown-backend": lambda m: m["raycastState"]["client"].update(backend="fake"),
            "forged-cpp": lambda m: m["raycastState"]["client"].update(backend="cpp"),
            "extra-field": lambda m: m["raycastState"]["client"].update(extra=True),
            "missing-query": lambda m: m["raycastState"]["client"].pop("limitedTiles"),
            "geometry": lambda m: m.update(changedTileMax=[62, 59]),
            "material": lambda m: m.update(observedOccluderMaterial=0),
            "action": lambda m: m.update(action="room-populated"),
        }
        for label, change in faults.items():
            with self.subTest(fault=label):
                candidate = self.ray_fixture(label, "rust")
                self.mutate_ray(candidate, change)
                with self.assertRaises(lab.LabError):
                    lab.captures(candidate)
                self.assertFalse(self.compare(reference, candidate, "compare-" + label)["passed"])

    def test_ray_each_query_receipt_is_independently_required(self):
        for side in ("client", "server"):
            for query in lab.RAY_QUERIES:
                for count in (0, -1, True, 1.0, None):
                    label = f"{side}-{query}-{count}"
                    candidate = self.ray_fixture(label, "rust")
                    self.mutate_ray(candidate, lambda m: m["raycastState"][side]["rustCalls"].update({query: count}))
                    with self.subTest(side=side, query=query, count=count), self.assertRaises(lab.LabError):
                        lab.captures(candidate)

    def test_ray_raw_cross_backend_points_are_not_tolerance_masked(self):
        reference, candidate = self.ray_fixture("ref"), self.ray_fixture("cand", "rust")
        def shorten(m):
            for side in ("client", "server"):
                m["raycastState"][side]["point"][0] = 61.9999
            m["raycastState"]["markerEnd"][0] = 61.9999
        self.mutate_ray(candidate, shorten)
        self.seal(candidate)  # Fixed f32 assertion passes; raw semantic comparison MUST fail.
        report = self.compare(reference, candidate)
        self.assertFalse(report["passed"])
        self.assertIn("worldState differs", report["frames"]["ray-blocked"]["errors"])

    def test_ray_missing_generic_stages_and_nonrestoration_rejected(self):
        for fault in ("missing", "generic", "state", "pixels", "static"):
            candidate = self.ray_fixture(fault, "rust")
            if fault == "missing":
                (candidate / "ray-blocked.png").unlink()
            elif fault == "generic":
                for index, name in enumerate(lab.RAY_STAGES):
                    path = candidate / f"{name}.json"
                    envelope = lab.load(path)
                    generic = f"frame-{index}"
                    envelope.update(name=generic, file=generic + ".png")
                    envelope["metadata"]["stage"] = generic
                    path.rename(candidate / f"{generic}.json")
                    (candidate / f"{generic}.json").write_text(json.dumps(envelope))
                    (candidate / f"{name}.png").rename(candidate / f"{generic}.png")
            elif fault == "state":
                self.mutate_ray(candidate, lambda m: m.update(lightColor=[0, 0, 0]), ("ray-restored",))
            else:
                lab.image(candidate / "ray-blocked.png").save(candidate / "ray-restored.png" if fault == "pixels" else candidate / "ray-clear.png")
                if fault == "static":
                    lab.image(candidate / "ray-blocked.png").save(candidate / "ray-restored.png")
            with self.subTest(fault=fault), self.assertRaises(lab.LabError):
                lab.captures(candidate)

    def test_ray_tiny_pixel_corruption_reaches_pixel_gate(self):
        reference, candidate = self.ray_fixture("ref"), self.ray_fixture("cand", "rust")
        frame = lab.image(candidate / "ray-clear.png")
        frame.putpixel((0, 0), (23, 0, 0, 255))
        for stage in ("ray-clear", "ray-restored"):
            frame.save(candidate / f"{stage}.png")
        self.seal(candidate)  # Valid restoration, so exercise the actual pixel gate.
        report = self.compare(reference, candidate)
        self.assertFalse(report["passed"])
        self.assertEqual(report["frames"]["ray-clear"]["changedPixels"], 1)

    def test_ray_capture_runner_seals_requested_scenario(self):
        source = self.ray_fixture("source")
        executable = self.root / "fake-client"
        executable.write_text(
            "#!" + os.sys.executable + "\n"
            "import json, os, pathlib, shutil\n"
            "config = json.loads(pathlib.Path(os.environ['STAR_BEHAVIOR_LAB']).read_text())\n"
            "assert config['scenario'] in ('raycast-room', 'lighting-room')\n"
            "out = pathlib.Path(config['outputDirectory'])\n"
            f"source = pathlib.Path({str(source)!r})\n"
            "for p in source.iterdir():\n"
            "    if p.suffix == '.png' or (p.suffix == '.json' and p.name != 'manifest.json'):\n"
            "        shutil.copyfile(p, out / p.name)\n")
        executable.chmod(0o755)
        assets = self.root / "packed.pak"
        assets.write_bytes(b"synthetic assets only")
        lab.build_provenance.seal(executable, lab.build_provenance.begin())
        frames = lab.capture(executable, assets, self.root / "capture", 10, scenario="raycast-room")
        captured, manifest = lab.validated(frames)
        self.assertEqual(set(captured), set(lab.RAY_STAGES))
        self.assertEqual(manifest["semanticConfiguration"]["scenario"], "raycast-room")
        self.assertEqual(manifest["semanticConfiguration"]["storageDirectory"], "<isolated-storage>")
        with self.assertRaisesRegex(lab.LabError, "captured scenario differs"):
            lab.capture(executable, assets, self.root / "mismatch", 10)  # Ray receipts cannot seal as a lighting run.

    def test_ray_run_success_requires_three_independent_captures(self):
        reference, repeat, candidate = (self.ray_fixture("ref"), self.ray_fixture("repeat"),
                                        self.ray_fixture("cand", "rust"))
        with mock.patch.object(lab, "capture", side_effect=[reference, repeat, candidate]) as capture:
            code = lab.main(["run", "--scenario", "raycast-room", "--reference", "/unused/ref",
                             "--candidate", "/unused/cand", "--assets", "/unused/pak", "--output", str(self.root / "run")])
        self.assertEqual(code, 0)
        self.assertEqual(capture.call_count, 3)
        self.assertTrue(lab.load(self.root / "run/report.json")["passed"])
        self.assertTrue(all(call.kwargs == {"scenario": "raycast-room"} for call in capture.call_args_list))

    def test_ray_run_propagates_scenario_and_blocks_unstable_baseline(self):
        reference, repeat = self.ray_fixture("ref"), self.ray_fixture("repeat")
        frame = lab.image(repeat / "ray-clear.png")
        frame.putpixel((0, 0), (23, 0, 0, 255))
        for stage in ("ray-clear", "ray-restored"):
            frame.save(repeat / f"{stage}.png")
        self.seal(repeat)
        with mock.patch.object(lab, "capture", side_effect=[reference, repeat]) as capture:
            code = lab.main(["run", "--scenario", "raycast-room", "--reference", "/unused/ref",
                             "--candidate", "/unused/cand", "--assets", "/unused/pak", "--output", str(self.root / "run")])
        self.assertEqual(code, 1)
        self.assertEqual(capture.call_count, 2)
        self.assertTrue(all(call.kwargs == {"scenario": "raycast-room"} for call in capture.call_args_list))

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
        previous_term = signal.getsignal(signal.SIGTERM)
        previous_int = signal.getsignal(signal.SIGINT)
        captured = lab.capture(executable, assets, self.root / "isolated-run", 10)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous_term)
        self.assertIs(signal.getsignal(signal.SIGINT), previous_int)
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

    def test_capture_clock_invalidates_suspend_and_wall_clock_jumps(self):
        lab.validate_capture_clock(2.0, 2.1)
        for active, wall in ((2, 62), (62, 2), (2, -1), (float('nan'), 2), (2, float('inf'))):
            with self.subTest(active=active, wall=wall), self.assertRaisesRegex(lab.LabError, 'clock'):
                lab.validate_capture_clock(active, wall)

    def test_capture_clock_failure_is_unsealed_and_retained(self):
        executable = Path(os.sys.executable).resolve()
        assets = self.root / 'clock-assets.pak'
        assets.write_bytes(b'synthetic assets')
        output = self.root / 'clock-jump-run'
        process = mock.Mock(pid=123)
        process.wait.return_value = 0
        with mock.patch.object(lab, 'verified_build', return_value={}), \
                mock.patch.object(lab, 'overlay_identity', return_value={}), \
                mock.patch.object(lab.subprocess, 'Popen', return_value=process), \
                mock.patch.object(lab, 'stop_process_group'), \
                mock.patch.object(lab.time, 'monotonic', side_effect=[10, 12]), \
                mock.patch.object(lab.time, 'time', side_effect=[100, 162]):
            with self.assertRaisesRegex(lab.LabError, 'clock'):
                lab.capture(executable, assets, output, 10)
        failure = lab.load(output / 'failure.json')
        self.assertEqual(failure['activeElapsedSeconds'], 2)
        self.assertEqual(failure['wallElapsedSeconds'], 62)
        self.assertFalse((output / 'frames/manifest.json').exists())

    def test_capture_timeout_retains_failure_and_kills_owned_process(self):
        executable = self.root / "sleeper"
        executable.write_text("#!" + os.sys.executable + "\nimport time\ntime.sleep(60)\n")
        executable.chmod(0o755)
        assets = self.root / "packed.pak"
        assets.write_bytes(b"synthetic assets")
        lab.build_provenance.seal(executable, lab.build_provenance.begin())
        run = self.root / "timed-out-run"
        previous_term = signal.getsignal(signal.SIGTERM)
        with self.assertRaises(subprocess.TimeoutExpired):
            lab.capture(executable, assets, run, 0.05)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous_term)
        failure = lab.load(run / "failure.json")
        self.assertIn("timed out", failure["reason"])
        with self.assertRaises(ProcessLookupError):
            os.killpg(failure["pid"], 0)
        self.assertFalse((run / "frames/manifest.json").exists())

    def test_capture_restores_custom_handlers_on_spawn_failure_and_interrupt(self):
        executable = Path(os.sys.executable).resolve()
        assets = self.root / "handler-assets.pak"
        assets.write_bytes(b"synthetic assets")
        previous_term = signal.getsignal(signal.SIGTERM)
        previous_int = signal.getsignal(signal.SIGINT)
        custom = lambda *_: None
        signal.signal(signal.SIGTERM, custom)
        try:
            for label, error in (("spawn", OSError("fixture spawn failure")),
                                 ("interrupt", KeyboardInterrupt())):
                with self.subTest(label=label):
                    process = mock.Mock(pid=123)
                    process.wait.side_effect = error
                    with mock.patch.object(lab, "verified_build", return_value={}), \
                            mock.patch.object(lab, "overlay_identity", return_value={}), \
                            mock.patch.object(lab.subprocess, "Popen", side_effect=error if label == "spawn" else None,
                                              return_value=process), \
                            mock.patch.object(lab, "stop_process_group") as cleanup:
                        with self.assertRaises(type(error)):
                            lab.capture(executable, assets, self.root / label, 1)
                        if label == "spawn":
                            cleanup.assert_not_called()
                        else:
                            cleanup.assert_called_with(process)
                    self.assertIs(signal.getsignal(signal.SIGTERM), custom)
                    self.assertIs(signal.getsignal(signal.SIGINT), previous_int)
        finally:
            signal.signal(signal.SIGTERM, previous_term)

    def test_capture_defers_sigterm_until_spawned_group_is_owned(self):
        executable = Path(os.sys.executable).resolve()
        assets = self.root / "deferred-assets.pak"
        assets.write_bytes(b"synthetic assets")
        previous_term = signal.getsignal(signal.SIGTERM)
        process = mock.Mock(pid=123)

        def spawn(*args, **kwargs):
            self.assertTrue(kwargs["start_new_session"])
            os.kill(os.getpid(), signal.SIGTERM)
            return process

        with mock.patch.object(lab, "verified_build", return_value={}), \
                mock.patch.object(lab, "overlay_identity", return_value={}), \
                mock.patch.object(lab.subprocess, "Popen", side_effect=spawn), \
                mock.patch.object(lab, "stop_process_group") as cleanup:
            with self.assertRaisesRegex(lab.LabError, "SIGTERM"):
                lab.capture(executable, assets, self.root / "deferred-run", 1)
            cleanup.assert_called_with(process)
            process.wait.assert_not_called()
        self.assertIs(signal.getsignal(signal.SIGTERM), previous_term)

    def test_capture_sigterm_cleans_detached_child(self):
        # Signal only this fixture's supervisor, after the detached child is ready.
        executable = self.root / "sigterm-sleeper"
        marker = self.root / "child.pid"
        executable.write_text(
            "#!" + os.sys.executable + "\nimport os, pathlib, time\n"
            f"marker = pathlib.Path({str(marker)!r})\n"
            "ready = marker.with_suffix('.ready')\n"
            "ready.write_text(str(os.getpid()))\nready.rename(marker)\n"
            "time.sleep(5)\n")
        executable.chmod(0o755)
        assets = self.root / "sigterm-assets.pak"
        assets.write_bytes(b"synthetic assets")
        run = self.root / "sigterm-run"
        script = (
            "import pathlib, signal, sys; import behavior_lab as lab; "
            "lab.verified_build = lambda _: {}; lab.overlay_identity = lambda *_: {}; "
            "lab.asset_overlays = lambda *_: {}; "
            "previous_int = signal.getsignal(signal.SIGINT); "
            "previous_term = signal.getsignal(signal.SIGTERM)\n"
            "try:\n"
            f"    lab.capture(pathlib.Path({str(executable)!r}), pathlib.Path({str(assets)!r}), "
            f"pathlib.Path({str(run)!r}), 5)\n"
            "except lab.LabError as error:\n"
            "    assert str(error) == 'capture interrupted by SIGTERM'\n"
            "    assert signal.getsignal(signal.SIGTERM) is previous_term\n"
            "    assert signal.getsignal(signal.SIGINT) is previous_int\n"
            "    sys.exit(42)\n")
        child_pid = None
        with (self.root / "supervisor.log").open("wb") as log:
            supervisor = subprocess.Popen([os.sys.executable, "-c", script],
                cwd=Path(lab.__file__).parent, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 5
                while not marker.exists() and supervisor.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(marker.exists(), "child never became ready")
                child_pid = int(marker.read_text())
                self.assertEqual(os.getpgid(child_pid), child_pid)
                os.kill(supervisor.pid, signal.SIGTERM)
                supervisor.wait(timeout=5)
                status = subprocess.run(["ps", "-o", "stat=", "-p", str(child_pid)],
                                        capture_output=True, text=True, timeout=5).stdout.strip()
                # A zombie is dead but not reaped: require the group to be gone too.
                observation = {"supervisorPid": supervisor.pid, "childPid": child_pid,
                               "supervisorExit": supervisor.returncode, "childStatus": status}
                lab.dump(self.root / "sigterm-observation.json", observation)
                self.assertEqual(status, "", observation)
                self.assertEqual(supervisor.returncode, 42, observation)
                with self.assertRaises(ProcessLookupError):
                    os.killpg(child_pid, 0)
                failure = lab.load(run / "failure.json")
                self.assertEqual(failure["pid"], child_pid)
                self.assertFalse((run / "frames/manifest.json").exists())
            finally:
                if supervisor.poll() is None:
                    supervisor.kill()
                supervisor.wait(timeout=5)
                if child_pid is None and marker.exists():
                    child_pid = int(marker.read_text())
                if child_pid is not None:
                    try:
                        os.killpg(child_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

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
