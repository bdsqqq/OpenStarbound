#!/usr/bin/env python3
"""Isolated real-client capture and an exact, fail-closed framebuffer oracle.

No crops, masks, golden updates, or adjustable tolerances: a dynamic reference
is a blocked experiment, not permission to weaken the candidate gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

from PIL import Image, ImageChops
import build_provenance

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "build"
SENTINEL = ".star-behavior-lab"
ASSET_OVERLAYS = {
    "opensb": ROOT / "assets/opensb",
    "behavior-fixture": ROOT / "source/lab/behavior/assets",
}
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
MAX_PIXELS = 16_777_216
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class LabError(Exception):
    pass


def canonical(path: Path) -> Path:
    """Reject symlink traversal, including existing parent components."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise LabError(f"symlink path refused: {part}")
    return path.resolve()


def owned(path: Path) -> Path:
    path = canonical(path)
    build = canonical(BUILD)
    if path == build or build not in path.parents:
        raise LabError(f"output must be a NEW directory strictly under {build}: {path}")
    return path


def create_owned(path: Path) -> Path:
    path = owned(path)
    if path.exists():
        raise LabError(f"refusing existing output (never reuse storage): {path}")
    path.mkdir(parents=True, exist_ok=False)
    (path / SENTINEL).write_text("behavior-lab-v1\n", encoding="utf-8")
    return path


def check_owned(path: Path) -> Path:
    path = owned(path)
    if not path.is_dir() or not canonical(path / SENTINEL).is_file():
        raise LabError(f"missing lab ownership sentinel: {path}")
    return path


def dump(path: Path, value) -> None:
    # All caller paths are newly-created lab outputs, never arbitrary inputs.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def load(path: Path):
    canonical(path)
    def reject(value):
        raise LabError(f"non-finite JSON constant: {value}")
    with path.open(encoding="utf-8") as stream:
        return json.load(stream, parse_constant=reject)


def sha(path: Path) -> str:
    canonical(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path) -> dict:
    path = canonical(path)
    if not path.is_file():
        raise LabError(f"not a regular file: {path}")
    return {"path": str(path), "sha256": sha(path), "size": path.stat().st_size}


def image(path: Path) -> Image.Image:
    canonical(path)
    with Image.open(path) as source:
        if source.format != "PNG" or source.width * source.height > MAX_PIXELS:
            raise LabError(f"not a bounded PNG: {path}")
        source.load()
        return source.convert("RGBA")


# The native scenario currently emits flat caller metadata. This explicit
# projection is the semantic state boundary, not a mask over visual changes.
# Only scheduling diagnostics (updateIndex/replicatedSettledUpdates) and backend
# call counters are excluded from exact state equality; pixels are never masked.
SCENE_FIELDS = (
    "worldId", "worldSize", "playerPosition", "cameraPosition", "cameraPixelRatio",
    "playerOutsideView", "uiHidden", "stabilization", "lightingCompleted", "fullbright",
    "material", "materialId", "lightObject", "lightEntityId", "lightPosition", "lightColor",
    "lightType", "lightEntityReplicated", "changedTileMin", "changedTileMax",
    "occluderPresent", "observedOccluderMaterial", "action", "seed", "stageIndex",
)


def semantic_world_state(receipt: dict) -> dict:
    state = receipt.get("worldState")
    if "worldState" in receipt and (not isinstance(state, dict) or not state):
        raise LabError("worldState must be a nonempty object")
    missing = [field for field in SCENE_FIELDS if field not in receipt]
    if missing:
        raise LabError("missing native scene state: " + ", ".join(missing))
    for field in ("playerOutsideView", "uiHidden", "lightingCompleted", "lightEntityReplicated"):
        if receipt[field] is not True:
            raise LabError(f"native scene assertion failed: {field}")
    if receipt["fullbright"] is not False:
        raise LabError("native scene bypasses lighting")
    settled = receipt.get("replicatedSettledUpdates")
    if type(settled) is not int or settled < 90:
        raise LabError("native scene has not settled for 90 updates")
    native = {field: receipt[field] for field in SCENE_FIELDS}
    # A native declared object supplements, rather than weakens, the frozen
    # flat schema: retain both when the driver supplies both representations.
    return native if state is None else {"declared": state, "native": native}


def captures(directory: Path) -> dict:
    directory = check_owned(directory)
    pngs = {p.stem: p for p in directory.glob("*.png")}
    receipts = {p.stem: p for p in directory.glob("*.json") if p.name != "manifest.json"}
    if pngs.keys() != receipts.keys() or len(pngs) < 3:
        raise LabError(f"need >=3 paired named PNG/JSON frames: {directory}")
    result = {}
    for name in sorted(pngs):
        if not NAME.fullmatch(name):
            raise LabError(f"unsafe capture name: {name}")
        envelope = load(receipts[name])
        if not isinstance(envelope, dict) or envelope.get("name") != name or envelope.get("file") != name + ".png":
            raise LabError(f"invalid capture envelope: {name}")
        capture_info = envelope.get("capture")
        if not isinstance(capture_info, dict) or capture_info.get("source") != "final-default-framebuffer" or capture_info.get("stage") != "after-imgui-before-swap":
            raise LabError(f"capture is not final framebuffer/pre-swap: {name}")
        receipt = envelope.get("metadata")
        if not isinstance(receipt, dict):
            raise LabError(f"receipt metadata must be object: {name}")
        if receipt.get("scenario") != "lighting-room":
            raise LabError(f"wrong scenario: {name}")
        if receipt.get("inWorld") is not True:
            raise LabError(f"capture is not in-world: {name}")
        if not isinstance(receipt.get("stage"), str) or not receipt["stage"]:
            raise LabError(f"missing stage: {name}")
        receipt = dict(receipt)
        receipt["worldState"] = semantic_world_state(receipt)
        if receipt.get("lightingBackend") not in ("cpp", "rust"):
            raise LabError(f"missing lightingBackend receipt: {name}")
        calls = receipt.get("rustLightingCalls")
        if type(calls) is not int or calls < 0:
            raise LabError(f"invalid Rust call receipt: {name}")
        if receipt["lightingBackend"] == "rust" and calls == 0:
            raise LabError(f"Rust backend never exercised: {name}")
        if receipt["lightingBackend"] == "cpp" and calls != 0:
            raise LabError(f"reference exercised Rust: {name}")
        frame = image(pngs[name])
        if [envelope.get("width"), envelope.get("height")] != list(frame.size):
            raise LabError(f"receipt/PNG dimensions disagree: {name}")
        result[name] = {"receipt": receipt, "png": pngs[name], "dimensions": list(frame.size),
                        "pngSha256": sha(pngs[name]), "receiptSha256": sha(receipts[name]),
                        "pixelsSha256": hashlib.sha256(frame.tobytes()).hexdigest()}
    validate_lighting_sequence(result)
    return result


def validate_lighting_sequence(frames: dict) -> None:
    """Restoration must undo the action, not merely produce a third picture."""
    stages = ("lit-room", "occluder-added", "occluder-restored")
    actions = ("room-populated", "foreground-occluder-added", "foreground-occluder-removed")
    if set(frames) != set(stages):
        raise LabError("native lighting scenario requires exactly its three named stages")
    for index, (name, action) in enumerate(zip(stages, actions)):
        receipt = frames[name]["receipt"]
        if (receipt.get("stage") != name or receipt.get("stageIndex") != index
                or receipt.get("action") != action or receipt.get("occluderPresent") is not (index == 1)):
            raise LabError(f"native lighting action/state mismatch: {name}")
        occupied = receipt.get("observedOccluderMaterial") == receipt.get("materialId")
        if occupied != (index == 1):
            raise LabError(f"native lighting observed material mismatch: {name}")
    initial, occluded, restored = (frames[name] for name in stages)
    if initial["pixelsSha256"] != restored["pixelsSha256"]:
        raise LabError("native lighting restoration did not restore the initial pixels")
    if initial["pixelsSha256"] == occluded["pixelsSha256"]:
        raise LabError("native lighting occluder did not change the pixels")
    before, after = initial["receipt"], restored["receipt"]
    stable = set(SCENE_FIELDS) - {"stageIndex", "action", "occluderPresent"}
    if any(before.get(field) != after.get(field) for field in stable):
        raise LabError("native lighting restoration did not restore scene state")
    if before.get("worldState", {}).get("declared") != after.get("worldState", {}).get("declared"):
        raise LabError("native lighting restoration did not restore declared scene state")


def inventory(frames: dict) -> dict:
    return {name: {k: value[k] for k in ("dimensions", "pngSha256", "receiptSha256", "pixelsSha256")}
            for name, value in frames.items()}


def validated(directory: Path) -> tuple[dict, dict]:
    frames = captures(directory)
    manifest = load(directory / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("schema") != 1 or manifest.get("exitCode") != 0:
        raise LabError(f"missing successful capture manifest: {directory}")
    if manifest.get("frames") != inventory(frames):
        raise LabError(f"capture changed since manifest was sealed: {directory}")
    for key in ("binary", "assets", "bootconfig", "configuration"):
        item = manifest.get(key, {})
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise LabError(f"missing {key} identity: {directory}")
    proof = manifest.get("buildProvenance")
    if (not isinstance(proof, dict) or proof.get("schema") != 1
            or proof.get("binary_sha256") != manifest["binary"]["sha256"]
            or proof.get("binary") != manifest["binary"]["path"]
            or not isinstance(proof.get("source_files"), dict) or not proof["source_files"]):
        raise LabError(f"missing source-bound build identity: {directory}")
    return frames, manifest


def pair_compare(reference: Path, candidate: Path, output: Path, same_backend=False) -> dict:
    """Read-only with respect to inputs; output must be a fresh lab directory."""
    output = create_owned(output)
    report = {"schema": 1, "passed": False, "gate": {"maxError": 0, "changedPixels": 0},
              "reference": str(reference), "candidate": str(candidate), "frames": {}, "errors": []}
    try:
        if canonical(reference) == canonical(candidate):
            raise LabError("independent runs required; cannot compare a capture to itself")
        expected, ref_manifest = validated(check_owned(reference))
        actual, cand_manifest = validated(check_owned(candidate))
        if ref_manifest.get("captureId") == cand_manifest.get("captureId"):
            raise LabError("independent capture identities required")
        report["identities"] = {"reference": ref_manifest, "candidate": cand_manifest}
        if expected.keys() != actual.keys():
            raise LabError("captured frame-name sets differ (extra/missing frames are failures)")
        if ref_manifest["assets"]["sha256"] != cand_manifest["assets"]["sha256"]:
            raise LabError("reference/candidate asset hashes differ")
        for field in ("overlayFiles", "semanticBootconfig", "semanticConfiguration"):
            if field not in ref_manifest or ref_manifest[field] != cand_manifest.get(field):
                raise LabError(f"reference/candidate {field} differs or is missing")
        if same_backend and ref_manifest["binary"]["sha256"] != cand_manifest["binary"]["sha256"]:
            raise LabError("repeatability runs used different binaries")
        for name, ref in expected.items():
            cand = actual[name]
            row = {"passed": True, "errors": [], "dimensions": ref["dimensions"]}
            ref_meta, cand_meta = ref["receipt"], cand["receipt"]
            for field in ("inWorld", "stage", "worldState"):
                if ref_meta[field] != cand_meta[field]:
                    row["errors"].append(f"{field} differs")
            wanted = ref_meta["lightingBackend"] if same_backend else "rust"
            if ref_meta["lightingBackend"] != "cpp" or cand_meta["lightingBackend"] != wanted:
                row["errors"].append("expected C++ reference and correct comparison backend")
            a, b = image(ref["png"]), image(cand["png"])
            a.save(output / f"{name}-expected.png")
            b.save(output / f"{name}-candidate.png")
            if a.size != b.size:
                row["errors"].append("dimensions differ")
                row.update(maxError=None, changedPixels=None)
            else:
                delta = ImageChops.difference(a, b)
                extrema = delta.getextrema()
                row["maxError"] = max(hi for lo, hi in extrema)
                row["changedPixels"] = sum(any(pixel) for pixel in delta.getdata())
                # Opaque visualization preserves RGB differences even when alpha
                # deltas are zero; alpha differences are also shown in grayscale.
                channels = delta.split()
                visual = ImageChops.lighter(delta.convert("RGB"), Image.merge("RGB", [channels[3]] * 3))
                visual.save(output / f"{name}-diff.png")
                if row["changedPixels"]:
                    row["errors"].append("exact framebuffer gate failed")
            row["passed"] = not row["errors"]
            report["frames"][name] = row
        report["passed"] = all(row["passed"] for row in report["frames"].values())
    except (LabError, OSError, ValueError, KeyError, TypeError, Image.DecompressionBombError) as error:
        report["errors"].append(str(error))
    dump(output / "report.json", report)
    return report


def stop_process_group(process: subprocess.Popen) -> None:
    """Only signal the private session created by this runner, never by name."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # The leader can exit before children; signal the same private group again.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def overlay_identity() -> dict:
    files = {}
    for name, source in ASSET_OVERLAYS.items():
        base = canonical(source)
        if not base.is_dir():
            raise LabError(f"required {name} overlay missing")
        for path in sorted(base.rglob("*")):
            canonical(path)  # Also reject directory symlinks omitted by rglob traversal.
            if path.is_file():
                files[f"{name}/{path.relative_to(base).as_posix()}"] = sha(path)
    return files


def verified_build(executable: Path) -> dict:
    try:
        return build_provenance.verify(executable)
    except build_provenance.ProvenanceError as error:
        raise LabError(f"capture requires a current source-bound build: {error}") from error


def capture(executable: Path, assets: Path, directory: Path, timeout: float) -> Path:
    binary_id, asset_id = identity(executable), identity(assets)
    if not os.access(binary_id["path"], os.X_OK):
        raise LabError("capture executable is not executable")
    if not math.isfinite(timeout) or timeout <= 0:
        raise LabError("timeout must be finite and positive")
    proof = verified_build(Path(binary_id["path"]))
    directory = create_owned(directory)
    home = create_owned(directory / "home")
    frames = create_owned(directory / "frames")
    # The native client refuses storage outside its sentinel-marked capture root.
    storage = create_owned(frames / "storage")
    configuration = directory / "scenario.json"
    bootconfig = directory / "sbinit.config"
    dump(configuration, {"outputDirectory": str(frames), "storageDirectory": str(storage),
                         "scenario": "lighting-room", "maxFrames": 1800, "platformWrites": False})
    dump(bootconfig, {"assetDirectories": [], "assetSources": [asset_id["path"],
                          *(str(canonical(path)) for path in ASSET_OVERLAYS.values())],
                      "storageDirectory": str(storage), "logDirectory": str(storage), "includeUGC": False,
                      "defaultConfiguration": {"includeUGC": False, "vsync": False,
                        "windowedResolution": [960, 540], "fullscreen": False,
                        "maximized": False, "borderless": False, "sfxVol": 0, "musicVol": 0,
                        "instrumentVol": 0, "clearUniverseFiles": False,
                        "clientIPJoinable": False, "clientP2PJoinable": False,
                        "serverAdvertise": False, "serverIP": "127.0.0.1"}})
    # Both overlays are required inputs; namespace their hashes to avoid collisions.
    overlay = overlay_identity()
    environment = dict(os.environ)
    for key in ("SteamAppId", "SteamGameId", "STAR_BEHAVIOR_LAB"):
        environment.pop(key, None)
    environment.update(STAR_BEHAVIOR_LAB=str(configuration), HOME=str(home),
                       XDG_DATA_HOME=str(home / "data"), XDG_CONFIG_HOME=str(home / "config"),
                       XDG_CACHE_HOME=str(home / "cache"))
    command = [binary_id["path"], "-bootconfig", str(bootconfig)]
    boot_id, configuration_id = identity(bootconfig), identity(configuration)
    dump(directory / "launch.json", {"binary": binary_id, "assets": asset_id,
         "buildProvenance": proof,
         "overlayFiles": overlay, "bootconfig": boot_id, "configuration": configuration_id,
         "command": command, "timeoutSeconds": timeout})
    started = time.monotonic()
    with (directory / "process.log").open("xb") as log:
        process = subprocess.Popen(command, cwd=directory, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            stop_process_group(process)
            dump(directory / "failure.json", {"reason": "capture interrupted or timed out",
                                              "timeoutSeconds": timeout, "pid": process.pid})
            raise
        finally:
            if process.poll() is not None:
                stop_process_group(process)
    if code:
        dump(directory / "failure.json", {"exitCode": code, "log": str(directory / "process.log")})
        raise LabError(f"client exited {code}; inspect {directory / 'process.log'}")
    # Catch artifact mutation during the run before sealing evidence.
    if (identity(executable) != binary_id or identity(assets) != asset_id
            or identity(bootconfig) != boot_id or identity(configuration) != configuration_id):
        raise LabError("binary/assets/config changed while client ran")
    if verified_build(Path(binary_id["path"])) != proof:
        raise LabError("build provenance changed while client ran")
    overlay_after = overlay_identity()
    if overlay != overlay_after:
        raise LabError("asset overlay changed while client ran")
    captured = captures(frames)
    semantic_bootconfig = load(bootconfig)
    for field in ("storageDirectory", "logDirectory"):
        semantic_bootconfig[field] = "<isolated-storage>"
    semantic_configuration = load(configuration)
    semantic_configuration["outputDirectory"] = "<isolated-output>"
    semantic_configuration["storageDirectory"] = "<isolated-storage>"
    dump(frames / "manifest.json", {"schema": 1, "captureId": uuid.uuid4().hex,
         "binary": binary_id, "assets": asset_id, "buildProvenance": proof,
         "overlayFiles": overlay, "semanticBootconfig": semantic_bootconfig,
         "semanticConfiguration": semantic_configuration, "bootconfig": boot_id,
         "configuration": configuration_id, "command": command, "exitCode": code,
         "elapsedSeconds": time.monotonic() - started, "frames": inventory(captured)})
    return frames


def default_output() -> Path:
    return BUILD / ("behavior-lab-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "capture"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--assets", type=Path, required=True, help="explicit packed.pak file")
        cmd.add_argument("--output", type=Path, default=None, help="NEW directory strictly under repository build/")
        cmd.add_argument("--timeout", type=float, default=180)
        if name == "run":
            cmd.add_argument("--reference", type=Path, required=True)
            cmd.add_argument("--candidate", type=Path, required=True)
            cmd.add_argument("--reference-repeat", action="store_true", default=True,
                             help="always enforced: baseline twice BEFORE candidate; exact gate")
        else:
            cmd.add_argument("--capture", type=Path, required=True, metavar="EXECUTABLE")
    compare = commands.add_parser("compare")
    compare.add_argument("--reference", type=Path, required=True, help="sealed frames directory")
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--repeat", type=Path, help="second C++ baseline frames directory")
    compare.add_argument("--same-backend", action="store_true",
                         help="diagnostic C++ baseline-vs-baseline only; never certifies candidate parity")
    compare.add_argument("--output", type=Path, default=None)
    commands.add_parser("self-test")
    args = parser.parse_args(argv)
    try:
        if args.command == "self-test":
            import unittest
            suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_*.py")
            return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
        output = args.output or default_output()
        if args.command == "capture":
            print(capture(args.capture, args.assets, output, args.timeout))
            return 0
        output = create_owned(output)
        if args.command == "run":
            reference = capture(args.reference, args.assets, output / "reference", args.timeout)
            repeat = capture(args.reference, args.assets, output / "reference-repeat", args.timeout)
            baseline = pair_compare(reference, repeat, output / "repeatability", same_backend=True)
            if not baseline["passed"]:
                dump(output / "report.json", {"passed": False, "parityCertified": False,
                                             "reason": "reference nondeterminism blocks candidate launch",
                                             "repeatability": baseline})
                return 1
            candidate = capture(args.candidate, args.assets, output / "candidate", args.timeout)
        else:
            reference, candidate, repeat = args.reference, args.candidate, args.repeat
            if args.same_backend:
                baseline = pair_compare(reference, candidate, output / "repeatability", same_backend=True)
                dump(output / "report.json", {"passed": baseline["passed"], "parityCertified": False,
                     "kind": "reference-repeatability-only", "inspectionRequired": True,
                     "repeatability": baseline})
                print(output / "report.json")
                return 0 if baseline["passed"] else 1
            baseline = pair_compare(reference, repeat, output / "repeatability", same_backend=True) if repeat else None
        comparison = pair_compare(reference, candidate, output / "comparison")
        certified = bool(comparison["passed"] and baseline and baseline["passed"])
        dump(output / "report.json", {"passed": certified, "parityCertified": False,
             "inspectionRequired": True, "repeatability": baseline, "comparison": comparison,
             "reason": "exact pixels/state only; human artifact inspection still required" if certified
                       else "reference repeatability and candidate comparison must both pass"})
        print(output / "report.json")
        return 0 if certified else 1
    except (LabError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"behavior-lab: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    # Accept the convenient requested --capture / --reference entry points too.
    arguments = sys.argv[1:]
    if arguments and arguments[0].startswith("--"):
        arguments.insert(0, "capture" if "--capture" in arguments else "run")
    raise SystemExit(main(arguments))
