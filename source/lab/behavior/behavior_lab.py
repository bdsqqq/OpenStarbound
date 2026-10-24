#!/usr/bin/env python3
"""Isolated real-client capture and an exact, fail-closed framebuffer oracle.

No comparison crops, masks, golden updates, or adjustable tolerances: a dynamic reference
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
import struct
import subprocess
import sys
import time
import uuid

from PIL import Image, ImageChops
import build_provenance
import encoding_proof
import sha256_proof
import vlq_proof
import bytes_proof
import unicode_proof
import shell_proof
import jsonpath_proof
import assetpath_proof
import random_mwc_proof
import json_patch_proof
import text_scan_proof
import compression_proof
import zstd_proof
import option_parser_proof

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "build"
SENTINEL = ".star-behavior-lab"
ASSET_OVERLAYS = {
    "opensb": ROOT / "assets/opensb",
    "behavior-fixture": ROOT / "source/lab/behavior/assets",
}
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
SCENARIOS = ("lighting-room", "raycast-room", "encoding-room", "sha256-room", "vlq-room", "bytes-room", "unicode-room", "shell-room", "jsonpath-room", "assetpath-room", "random-room", "jsonpatch-room", "text-room", "compression-room", "zstd-room", "option-parser-room")
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
    if receipt.get("scenario") == "raycast-room":
        ray = validate_raycast_state(receipt)
        native["raycastState"] = {key: value for key, value in ray.items() if key not in ("client", "server")}
        for side in ("client", "server"):
            native["raycastState"][side] = ray_observation(ray[side])
    if receipt.get("scenario") == "encoding-room":
        try:
            native["encodingProof"] = encoding_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "sha256-room":
        try:
            native["sha256Proof"] = sha256_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "vlq-room":
        try:
            native["vlqProof"] = vlq_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "bytes-room":
        try:
            native["bytesProof"] = bytes_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "unicode-room":
        try:
            native["unicodeProof"] = unicode_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "shell-room":
        try:
            native["shellProof"] = shell_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "jsonpath-room":
        try:
            native["jsonPathProof"] = jsonpath_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "assetpath-room":
        try:
            native["assetPathProof"] = assetpath_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "random-room":
        try:
            native["randomMwcProof"] = random_mwc_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "jsonpatch-room":
        try:
            native["jsonPatchProof"] = json_patch_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "text-room":
        try:
            native["textScanProof"] = text_scan_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "compression-room":
        try:
            native["compressionProof"] = compression_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "zstd-room":
        try:
            native["zstdProof"] = zstd_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
    if receipt.get("scenario") == "option-parser-room":
        try:
            native["optionParserProof"] = option_parser_proof.validate(receipt)
        except ValueError as error:
            raise LabError(str(error)) from error
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
    scenarios = set()
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
        if receipt.get("scenario") not in SCENARIOS:
            raise LabError(f"wrong scenario: {name}")
        scenarios.add(receipt["scenario"])
        if len(scenarios) != 1:
            raise LabError("mixed capture scenarios")
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
        if receipt["scenario"] == "raycast-room":
            validate_raycast_ink(frame, receipt)
        if receipt["scenario"] == "encoding-room":
            try:
                encoding_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "vlq-room":
            try:
                vlq_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "bytes-room":
            try:
                bytes_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "unicode-room":
            try:
                unicode_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "shell-room":
            try:
                shell_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "jsonpath-room":
            try:
                jsonpath_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "assetpath-room":
            try:
                assetpath_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "random-room":
            try:
                random_mwc_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "jsonpatch-room":
            try:
                json_patch_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "text-room":
            try:
                text_scan_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "compression-room":
            try:
                compression_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "zstd-room":
            try:
                zstd_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        if receipt["scenario"] == "option-parser-room":
            try:
                option_parser_proof.bind(receipt, directory.parent / "sbinit.config", load(directory.parent / "sbinit.config"))
                option_parser_proof.visible(frame, receipt)
            except ValueError as error:
                raise LabError(str(error)) from error
        result[name] = {"receipt": receipt, "png": pngs[name], "dimensions": list(frame.size),
                        "pngSha256": sha(pngs[name]), "receiptSha256": sha(receipts[name]),
                        "pixelsSha256": hashlib.sha256(frame.tobytes()).hexdigest()}
    if scenarios in ({"lighting-room"}, {"encoding-room"}, {"sha256-room"}, {"vlq-room"}, {"bytes-room"}, {"unicode-room"}, {"shell-room"}, {"jsonpath-room"}, {"assetpath-room"}, {"random-room"}, {"jsonpatch-room"}, {"text-room"}, {"compression-room"}, {"zstd-room"}, {"option-parser-room"}):
        validate_lighting_sequence(result)
        if scenarios == {"encoding-room"}:
            proofs = [encoding_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("encoding bytes changed across scene stages")
        if scenarios == {"sha256-room"}:
            proofs = [sha256_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("SHA input/database evidence changed across scene stages")
        if scenarios == {"vlq-room"}:
            proofs = [vlq_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("VLQ wire/database evidence changed across scene stages")
        if scenarios == {"bytes-room"}:
            proofs = [bytes_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("byte-order wire/database evidence changed across scene stages")
        if scenarios == {"unicode-room"}:
            proofs = [unicode_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("Unicode bytes changed across scene stages")
        if scenarios == {"shell-room"}:
            proofs = [shell_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("shell commands/world observations changed across stages")
        if scenarios == {"jsonpath-room"}:
            proofs = [jsonpath_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("JSON-path actual observations changed across stages")
        if scenarios == {"assetpath-room"}:
            proofs = [assetpath_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("asset-path actual crop/alias observations changed across stages")
        if scenarios == {"random-room"}:
            proofs = [random_mwc_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("random MWC owned userdata observations changed across stages")
        if scenarios == {"jsonpatch-room"}:
            proofs = [json_patch_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("JSON patch actual handler/rollback observations changed across stages")
        if scenarios == {"text-room"}:
            proofs = [text_scan_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("actual text scanner events/glyphs changed across stages")
        if scenarios == {"compression-room"}:
            proofs = [compression_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("actual compression producer/consumer observations changed across stages")
        if scenarios == {"zstd-room"}:
            proofs = [zstd_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("actual Zstd image/TCP observations changed across stages")
        if scenarios == {"option-parser-room"}:
            proofs = [option_parser_proof.validate(frame["receipt"]) for frame in result.values()]
            if any(proof != proofs[0] for proof in proofs[1:]):
                raise LabError("actual startup/Root configuration changed across scene stages")
    else:
        validate_raycast_sequence(result)
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


RAY_QUERIES = ("collision", "point", "tiles", "limitedTiles", "zeroLimitTiles")
RAY_STAGES = ("ray-clear", "ray-blocked", "ray-restored")


def numeric_vector(value, length, integer=False) -> bool:
    return (isinstance(value, list) and len(value) == length
            and all(type(item) is int if integer else
                    type(item) in (int, float) and abs(item) <= 1e308 and math.isfinite(item)
                    for item in value))


def ray_observation(side: dict) -> dict:
    return {key: value for key, value in side.items() if key not in ("backend", "rustCalls")}


def validate_raycast_state(receipt: dict) -> dict:
    """Validate expectations without normalizing raw cross-backend observations."""
    ray = receipt.get("raycastState")
    if not isinstance(ray, dict) or set(ray) != {"start", "end", "occluderColumns", "markerEnd", "client", "server"}:
        raise LabError("invalid raycastState schema")
    if (not numeric_vector(ray["start"], 2) or not numeric_vector(ray["end"], 2)
            or not numeric_vector(ray["occluderColumns"], 2, integer=True)
            or ray["start"] != [54.5, 48.5] or ray["end"] != [74.5, 48.5] or ray["occluderColumns"] != [62, 70]):
        raise LabError("invalid raycast geometry")
    blocked = receipt.get("stageIndex") == 1
    for side in ("client", "server"):
        result = ray[side]
        if not isinstance(result, dict) or set(result) != {*RAY_QUERIES, "normal", "backend", "rustCalls"}:
            raise LabError(f"invalid raycast {side} schema")
        calls = result["rustCalls"]
        backend = result["backend"]
        if backend not in ("cpp", "rust") or not isinstance(calls, dict) or set(calls) != set(RAY_QUERIES):
            raise LabError(f"invalid raycast {side} backend receipt")
        for query in RAY_QUERIES:
            count = calls[query]
            if type(count) is not int or (count <= 0 if backend == "rust" else count != 0):
                raise LabError(f"invalid raycast {side} {query} call receipt")
        if result["collision"] is not blocked:
            raise LabError(f"wrong raycast {side} collision")
        for field, expected in (("tiles", [[62, 48], [70, 48]] if blocked else []),
                                ("limitedTiles", [[62, 48]] if blocked else []), ("zeroLimitTiles", []),
                                ("normal", [1, 0] if blocked else None)):
            value = result[field]
            if field == "normal":
                typed = value is None if not blocked else numeric_vector(value, 2, integer=True)
            else:
                typed = isinstance(value, list) and all(numeric_vector(tile, 2, integer=True) for tile in value)
            if not typed or value != expected:
                raise LabError(f"wrong raycast {side} {field}")
        point = result["point"]
        if blocked:
            # C++ JSON printers may shorten a float's decimal spelling. Only
            # the fixed expectation rounds to f32; semantic equality stays raw.
            expected_x = struct.unpack("f", struct.pack("f", 62 - 0.0001))[0]
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                    or abs(point[0]) > 1e6
                    or struct.unpack("f", struct.pack("f", point[0]))[0] != expected_x or point[1] != 48.5):
                raise LabError(f"wrong raycast {side} point")
        elif point is not None:
            raise LabError(f"wrong raycast {side} clear point")
    if ray_observation(ray["client"]) != ray_observation(ray["server"]):
        raise LabError("raycast client/server observations disagree")
    if not numeric_vector(ray["markerEnd"], 2) or ray["markerEnd"] != (ray["client"]["point"] if blocked else ray["end"]):
        raise LabError("raycast markerEnd does not follow actual client result")
    return ray


def validate_raycast_ink(frame: Image.Image, receipt: dict) -> None:
    """Require result-local ink, independently of exact full-frame equality.

    Equal images can both omit the overlay. These bounded assertion ROIs are
    never used to crop/mask the framebuffer comparison or its pixel hashes.
    """
    ray = validate_raycast_state(receipt)
    camera, ratio = receipt["cameraPosition"], receipt["cameraPixelRatio"]
    if (not numeric_vector(camera, 2) or camera != [64, 48]
            or type(ratio) not in (int, float) or ratio != 2):
        raise LabError("invalid raycast marker camera geometry")
    # Native TilePixels=8; camera ratio maps logical pixels to framebuffer pixels.
    scale = 8 * ratio
    def project(point):
        return (frame.width / 2 + (point[0] - camera[0]) * scale,
                frame.height / 2 - (point[1] - camera[1]) * scale)
    start, end = project(ray["start"]), project(ray["markerEnd"])
    if any(not (0 <= x < frame.width and 0 <= y < frame.height) for x, y in (start, end)):
        raise LabError("raycast marker segment outside viewport")
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 0:
        raise LabError("zero-length raycast marker segment")

    def pixels_around(a, b, radius):
        left = max(0, math.floor(min(a[0], b[0]) - radius))
        top = max(0, math.floor(min(a[1], b[1]) - radius))
        right = min(frame.width, math.ceil(max(a[0], b[0]) + radius) + 1)
        bottom = min(frame.height, math.ceil(max(a[1], b[1]) + radius) + 1)
        roi = frame.crop((left, top, right, bottom))
        for y in range(roi.height):
            for x in range(roi.width):
                yield left + x + 0.5, top + y + 0.5, roi.getpixel((x, y))

    cyan = False
    for x, y, (r, g, b, a) in pixels_around(start, end, 3):
        t = ((x - start[0]) * dx + (y - start[1]) * dy) / length_squared
        if (0 <= t <= 1 and (x - start[0] - t * dx) ** 2 + (y - start[1] - t * dy) ** 2 <= 9
                and a > 0 and r <= 64 and g >= 128 and b >= 128):
            cyan = True
            break
    if not cyan:
        raise LabError("raycast marker missing cyan ink on result segment")
    if not any(abs(x - end[0]) <= 8 and abs(y - end[1]) <= 8
               and a > 0 and r >= 128 and g >= 128 and b <= 128
               for x, y, (r, g, b, a) in pixels_around(end, end, 8)):
        raise LabError("raycast marker missing yellow ink around actual markerEnd")


def validate_raycast_sequence(frames: dict) -> None:
    if set(frames) != set(RAY_STAGES):
        raise LabError("native raycast scenario requires exactly its three named stages")
    actions = ("room-populated", "foreground-occluder-added", "foreground-occluder-removed")
    for index, (name, action) in enumerate(zip(RAY_STAGES, actions)):
        receipt = frames[name]["receipt"]
        if (receipt["stage"] != name or type(receipt["stageIndex"]) is not int
                or receipt["stageIndex"] != index or receipt["action"] != action
                or receipt["occluderPresent"] is not (index == 1)):
            raise LabError(f"native raycast action/state mismatch: {name}")
        if (receipt["changedTileMin"] != [62, 33] or receipt["changedTileMax"] != [70, 59]
                or receipt["worldSize"] != [128, 96]
                or receipt["playerPosition"] != [12, 4]
                or receipt["cameraPosition"] != [64, 48]
                or receipt["cameraPixelRatio"] != 2
                or receipt["lightPosition"] != [52.5, 33.5]
                or receipt["stabilization"] != {"sky": "barren-black", "stars": False, "debris": False,
                    "spawning": False, "lightFlicker": False, "objectAnimation": False}
                or receipt["material"] != "smoothmetal"
                or receipt["lightObject"] != "behaviorlabconstantlight"
                or receipt["lightType"] != "PointAsSpread"):
            raise LabError(f"native raycast room geometry mismatch: {name}")
        if ((receipt["observedOccluderMaterial"] == receipt["materialId"]) != (index == 1)):
            raise LabError(f"native raycast observed material mismatch: {name}")
    initial, blocked, restored = (frames[name] for name in RAY_STAGES)
    if initial["pixelsSha256"] != restored["pixelsSha256"]:
        raise LabError("native raycast restoration did not restore initial pixels")
    if initial["pixelsSha256"] == blocked["pixelsSha256"]:
        raise LabError("native raycast occluder did not change pixels")
    stable = set(SCENE_FIELDS) - {"stageIndex", "action", "occluderPresent"}
    before, after = initial["receipt"], restored["receipt"]
    if (any(before[field] != after[field] for field in stable)
            or before["worldState"].get("declared") != after["worldState"].get("declared")
            or before["worldState"].get("raycastState") != after["worldState"].get("raycastState")
            or before["worldState"].get("native", {}).get("raycastState") != after["worldState"].get("native", {}).get("raycastState")):
        raise LabError("native raycast restoration did not restore scene state")


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
            if ref_meta["scenario"] != cand_meta["scenario"]:
                row["errors"].append("scenario differs")
            if ref_meta["scenario"] == "option-parser-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["optionParserProof"]["backend"] != "cpp" or cand_meta["optionParserProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct OptionParser backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "zstd-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["zstdProof"]["backend"] != "cpp" or cand_meta["zstdProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct Zstd backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "compression-room":
                wanted = "cpp" if same_backend else "rust"
                if any(ref_meta["compressionProof"]["operations"][name]["backend"] != "cpp" or cand_meta["compressionProof"]["operations"][name]["backend"] != wanted for name in ("embed", "zlib", "gzip")):
                    row["errors"].append("expected C++ reference and correct compression backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "text-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["textScanProof"]["backend"] != "cpp" or cand_meta["textScanProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct text scanner backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "jsonpatch-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["jsonPatchProof"]["assets"]["backend"] != "cpp" or cand_meta["jsonPatchProof"]["assets"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct JSON patch backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "random-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["randomMwcProof"]["backend"] != "cpp" or cand_meta["randomMwcProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct random MWC backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "assetpath-room":
                wanted = "cpp" if same_backend else "rust"
                if (ref_meta["assetPathProof"]["assets"]["backend"] != "cpp" or cand_meta["assetPathProof"]["assets"]["backend"] != wanted):
                    row["errors"].append("expected C++ reference and correct asset-path backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "jsonpath-room":
                wanted = "cpp" if same_backend else "rust"
                if (ref_meta["jsonPathProof"]["assets"]["backend"] != "cpp" or cand_meta["jsonPathProof"]["assets"]["backend"] != wanted):
                    row["errors"].append("expected C++ reference and correct JSON-path backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "shell-room":
                wanted = "cpp" if same_backend else "rust"
                if (ref_meta["shellProof"]["backend"] != "cpp" or cand_meta["shellProof"]["backend"] != wanted):
                    row["errors"].append("expected C++ reference and correct shell backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "unicode-room":
                wanted = "cpp" if same_backend else "rust"
                if (ref_meta["unicodeProof"]["assets"]["backend"] != "cpp"
                        or cand_meta["unicodeProof"]["assets"]["backend"] != wanted):
                    row["errors"].append("expected C++ reference and correct Unicode backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "bytes-room":
                wanted = "cpp" if same_backend else "rust"
                if (ref_meta["bytesProof"]["assets"]["backend"] != "cpp"
                        or cand_meta["bytesProof"]["assets"]["backend"] != wanted):
                    row["errors"].append("expected C++ reference and correct byte-order backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "vlq-room":
                wanted = "cpp" if same_backend else "rust"
                if (ref_meta["vlqProof"]["assets"]["backend"] != "cpp"
                        or cand_meta["vlqProof"]["assets"]["backend"] != wanted):
                    row["errors"].append("expected C++ reference and correct VLQ backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "sha256-room":
                wanted = "cpp" if same_backend else "rust"
                if (ref_meta["sha256Proof"]["assets"]["backend"] != "cpp"
                        or cand_meta["sha256Proof"]["assets"]["backend"] != wanted):
                    row["errors"].append("expected C++ reference and correct SHA backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "encoding-room":
                wanted = "cpp" if same_backend else "rust"
                if (ref_meta["encodingProof"]["backend"] != "cpp"
                        or cand_meta["encodingProof"]["backend"] != wanted):
                    row["errors"].append("expected C++ reference and correct encoding backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "raycast-room":
                wanted = "cpp" if same_backend else "rust"
                for side in ("client", "server"):
                    if (ref_meta["raycastState"][side]["backend"] != "cpp"
                            or cand_meta["raycastState"][side]["backend"] != wanted):
                        row["errors"].append("expected C++ reference and correct raycast comparison backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            else:
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


def asset_overlays(scenario="lighting-room") -> dict:
    overlays = dict(ASSET_OVERLAYS)
    if scenario == "encoding-room":
        overlays["encoding-fixture"] = ROOT / "source/lab/behavior/encoding-assets"
    if scenario == "vlq-room":
        overlays["vlq-fixture"] = ROOT / "source/lab/behavior/vlq-assets"
    if scenario == "bytes-room":
        overlays["bytes-fixture"] = ROOT / "source/lab/behavior/bytes-assets"
    if scenario == "unicode-room":
        overlays["unicode-fixture"] = ROOT / "source/lab/behavior/unicode-assets"
    if scenario == "shell-room":
        overlays["shell-fixture"] = ROOT / "source/lab/behavior/shell-assets"
    if scenario == "jsonpath-room":
        overlays["jsonpath-fixture"] = ROOT / "source/lab/behavior/jsonpath-assets"
    if scenario == "assetpath-room":
        overlays["assetpath-fixture"] = ROOT / "source/lab/behavior/assetpath-assets"
    if scenario == "random-room":
        overlays["random-mwc-fixture"] = ROOT / "source/lab/behavior/random-mwc-assets"
    if scenario == "jsonpatch-room":
        overlays["jsonpatch-fixture"] = ROOT / "source/lab/behavior/jsonpatch-assets"
    if scenario == "compression-room":
        overlays["compression-fixture"] = ROOT / "source/lab/behavior/compression-assets"
    if scenario == "zstd-room":
        overlays["zstd-fixture"] = ROOT / "source/lab/behavior/zstd-assets"
    if scenario == "option-parser-room":
        overlays["option-parser-fixture"] = ROOT / "source/lab/behavior/option-parser-assets"
    return overlays


def overlay_identity(scenario="lighting-room") -> dict:
    files = {}
    for name, source in asset_overlays(scenario).items():
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


def capture(executable: Path, assets: Path, directory: Path, timeout: float, scenario="lighting-room") -> Path:
    if scenario not in SCENARIOS:
        raise LabError("unknown scenario")
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
                         "scenario": scenario, "maxFrames": 1800, "platformWrites": False})
    dump(bootconfig, {"assetDirectories": [], "assetSources": [asset_id["path"],
                          *(str(canonical(path)) for path in asset_overlays(scenario).values())],
                      "storageDirectory": str(storage), "logDirectory": str(storage), "includeUGC": False,
                      "defaultConfiguration": {"includeUGC": False, "vsync": False,
                        "windowedResolution": [960, 540], "fullscreen": False,
                        "maximized": False, "borderless": False, "sfxVol": 0, "musicVol": 0,
                        "instrumentVol": 0, "clearUniverseFiles": False,
                        "clientIPJoinable": False, "clientP2PJoinable": False,
                        "serverAdvertise": False, "serverIP": "127.0.0.1",
                        **({"optionParserProof": option_parser_proof.CONFIGURATION} if scenario == "option-parser-room" else {}),
                        **({"safe": {"allowRemoteAssets": True}} if scenario in ("encoding-room", "vlq-room", "bytes-room", "compression-room", "zstd-room") else {})}})
    # Both overlays are required inputs; namespace their hashes to avoid collisions.
    overlay = overlay_identity(scenario)
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
    overlay_after = overlay_identity(scenario)
    if overlay != overlay_after:
        raise LabError("asset overlay changed while client ran")
    captured = captures(frames)
    if any(frame["receipt"]["scenario"] != scenario for frame in captured.values()):
        raise LabError("captured scenario differs from requested scenario")
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
        cmd.add_argument("--scenario", choices=SCENARIOS, default="lighting-room")
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
            print(capture(args.capture, args.assets, output, args.timeout, scenario=args.scenario))
            return 0
        output = create_owned(output)
        if args.command == "run":
            reference = capture(args.reference, args.assets, output / "reference", args.timeout, scenario=args.scenario)
            repeat = capture(args.reference, args.assets, output / "reference-repeat", args.timeout, scenario=args.scenario)
            baseline = pair_compare(reference, repeat, output / "repeatability", same_backend=True)
            if not baseline["passed"]:
                dump(output / "report.json", {"passed": False, "parityCertified": False,
                                             "reason": "reference nondeterminism blocks candidate launch",
                                             "repeatability": baseline})
                return 1
            candidate = capture(args.candidate, args.assets, output / "candidate", args.timeout, scenario=args.scenario)
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
