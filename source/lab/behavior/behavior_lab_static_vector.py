#!/usr/bin/env python3
"""Current30 scene26 frontend. Pure fixtures do not qualify a running game."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

import static_vector_scenarios as scenarios
import static_vector_proof as proof_reader

r = scenarios.runner
HERE = Path(__file__).resolve().parent
SCENARIO = scenarios.SCENARIO
SCENARIOS = scenarios.SCENARIOS
RESTORATION = 'static-vector-restoration.json'
BINDING = 'static-vector-binding.json'
LabError = r.LabError
# Context-independent primitives only; never old launch/validated/comparator.
create_owned, canonical, check_owned = r.create_owned, r.canonical, r.check_owned
image, dump, load, identity = r.image, r.dump, r.load, r.identity
Image, ImageChops = r.Image, r.ImageChops


def _frontend_identity():
    scenarios.assert_frozen()
    return {name: identity(path) for name, path in {
        'tool': Path(__file__), 'producer': HERE / 'static_vector_capture.py',
        'registry': HERE / 'static_vector_scenarios.py', 'proofReader': HERE / 'static_vector_proof.py',
        'originValidator': HERE / 'static_vector_origin.py',
        'configurationReader': HERE.parent / 'static-vector-game/configuration.py',
        'legacy': HERE / 'behavior_lab.py', 'legacyContract': HERE / 'test_native_scenario_contract.py',
        'scene25Decoder': HERE / 'behavior_lab_id_map.py', 'scene25Proof': HERE / 'id_map_proof.py',
    }.items()}


def _check_game_origin(executable, proof):
    path = HERE / 'static_vector_origin.py'
    try:
        reader = scenarios.load_source('_static_vector_current_origin', path)
        result = reader.validate_game_origin(Path(executable), proof)
    except Exception as error:
        raise LabError('current30 game origin rejected/unavailable: ' + str(error)) from error
    if type(result) is not dict or not result or result.get('schema') != 'static-vector-whole-game-origin-v1':
        raise LabError('current30 game origin returned no valid opaque binding')
    return result


def verified_build(executable):
    scenarios.assert_frozen()
    proof = load(r.build_provenance.sidecar(Path(executable)))
    scenarios.backend(proof)
    _check_game_origin(executable, proof)
    return proof


def _capture_arguments(argv, executable, assets, directory, timeout, scenario):
    if (type(argv) is not list or len(argv) < 2 or argv[1] != 'capture'
            or not all(type(a) is str and '\0' not in a for a in argv)
            or canonical(Path(argv[0])) != Path(__file__).resolve()):
        raise LabError('actual current30 frontend capture argv required')
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    for flag in ('capture', 'assets', 'output'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--scenario', choices=SCENARIOS, default=SCENARIO)
    try:
        args = parser.parse_args(argv[2:])
    except (argparse.ArgumentError, SystemExit) as error:
        raise LabError('frontend argv malformed') from error
    if (any(canonical(a) != canonical(b) for a, b in
            ((args.capture, executable), (args.assets, assets), (args.output, directory)))
            or args.timeout != timeout or args.scenario != scenario):
        raise LabError('frontend argv differs from actual capture request')


def captures(directory, configuration, backend, process_exit_code):
    directory = check_owned(directory)
    scenario = scenarios.require(configuration['scenario'])
    if scenario != SCENARIO:
        return scenarios.decode_old(directory, scenario)
    allowed = {'manifest.json', RESTORATION, *(s + ext for s in proof_reader.STAGES for ext in ('.png', '.json'))}
    if any(p.suffix.lower() in ('.png', '.json') and p.name not in allowed for p in directory.iterdir()):
        raise LabError('unknown scene26 JSON/PNG refused')
    if ({p.stem for p in directory.glob('*.png')} != set(proof_reader.STAGES)
            or {p.name for p in directory.glob('*.json')} - {'manifest.json', RESTORATION}
            != {s + '.json' for s in proof_reader.STAGES}):
        raise LabError('scene26 requires exactly three paired frames')
    result, raw = {}, []
    for stage in proof_reader.STAGES:
        envelope = load(directory / (stage + '.json'))
        if (type(envelope) is not dict or envelope.get('name') != stage or envelope.get('file') != stage + '.png'
                or envelope.get('capture', {}).get('source') != 'final-default-framebuffer'
                or envelope.get('capture', {}).get('stage') != 'after-imgui-before-swap'):
            raise LabError('scene26 requires actual final framebuffer envelope')
        receipt = envelope.get('metadata')
        if type(receipt) is not dict:
            raise LabError('scene26 metadata object required')
        raw.append(receipt)
        frame = image(directory / (stage + '.png'))
        if (type(envelope.get('width')) is not int or type(envelope.get('height')) is not int
                or [envelope['width'], envelope['height']] != list(frame.size)):
            raise LabError('scene26 PNG dimensions differ')
        lighting, calls = receipt.get('lightingBackend'), receipt.get('rustLightingCalls')
        if (lighting not in ('cpp', 'rust') or type(calls) is not int
                or (calls != 0 if lighting == 'cpp' else calls <= 0)):
            raise LabError('scene26 lighting backend/count invalid')
        result[stage] = dict(receipt=dict(receipt), png=directory / (stage + '.png'), dimensions=list(frame.size),
                             pngSha256=r.sha(directory / (stage + '.png')),
                             receiptSha256=r.sha(directory / (stage + '.json')),
                             pixelsSha256=hashlib.sha256(frame.tobytes()).hexdigest())
    observations = proof_reader.validate_sequence(raw, load(directory / RESTORATION), backend=backend,
                            configuration=configuration, process_exit_code=process_exit_code)
    for stage, receipt, observation in zip(proof_reader.STAGES, raw, observations):
        state = r.semantic_world_state(receipt)
        state['staticVectorProof'] = observation
        result[stage]['receipt']['worldState'] = state
    if result[proof_reader.STAGES[0]]['pixelsSha256'] == result[proof_reader.STAGES[1]]['pixelsSha256']:
        raise LabError('scene26 occluder did not visibly change pixels')
    return result


def _binding(directory, manifest, origin, launch):
    scenario = manifest['semanticConfiguration']['scenario']
    restoration = (identity(directory / RESTORATION) if scenario == SCENARIO else
                   identity(directory / 'idmap-restoration.json') if scenario == 'id-map-room' else None)
    return dict(schema=1, scenario=scenario, captureManifest=identity(directory / 'manifest.json'),
        restoration=restoration, launch=identity(directory.parent / 'launch.json'),
        processStart=manifest['processStart'], processExit=manifest['processExit'], configuration=manifest['configuration'],
        bootconfig=manifest['bootconfig'], binary=manifest['binary'], assets=manifest['assets'],
        compiledHeader=identity(HERE / 'static_vector_scene.hpp'), frontend=launch['frontend'], gameOrigin=origin)


def validated(directory):
    directory = check_owned(directory)
    if any((p / name).exists() for p in (directory, directory.parent) for name in ('failure.json', 'rejected-manifest.json')):
        raise LabError('aborted capture cannot qualify')
    manifest = load(directory / 'manifest.json')
    if (type(manifest) is not dict or type(manifest.get('schema')) is not int or manifest['schema'] != 1
            or type(manifest.get('exitCode')) is not int or manifest['exitCode'] != 0
            or type(manifest.get('captureId')) is not str or not manifest['captureId']):
        raise LabError('successful typed manifest required')
    r.validate_process_binding(directory, manifest)
    for field, path in (('configuration', directory.parent / 'scenario.json'), ('bootconfig', directory.parent / 'sbinit.config'),
                        ('binary', Path(manifest['binary']['path'])), ('assets', Path(manifest['assets']['path']))):
        if identity(path) != manifest[field]:
            raise LabError('actual identity changed: ' + field)
    config = load(directory.parent / 'scenario.json')
    scenario = scenarios.require(config['scenario'])
    expected = dict(scenario=scenario, outputDirectory=str(directory), storageDirectory=str(directory / 'storage'),
                    maxFrames=1800, platformWrites=False)
    if not proof_reader.same_json(config, expected):
        raise LabError('actual isolated scenario configuration mismatch')
    check_owned(directory / 'storage')
    from static_vector_capture import boot_configuration, semantic_configuration, semantic_boot
    boot = load(directory.parent / 'sbinit.config')
    if not proof_reader.same_json(boot, boot_configuration(scenario, manifest['assets']['path'], directory / 'storage')):
        raise LabError('actual isolated boot configuration mismatch')
    for field, expected in (('semanticConfiguration', semantic_configuration(config)),
                            ('semanticBootconfig', semantic_boot(boot)), ('overlayFiles', scenarios.overlay_identity(scenario))):
        if not proof_reader.same_json(manifest.get(field), expected):
            raise LabError('semantic configuration/overlay changed: ' + field)
    binary = Path(manifest['binary']['path'])
    proof = verified_build(binary)
    if not proof_reader.same_json(proof, manifest['buildProvenance']):
        raise LabError('current build proof changed')
    backend = scenarios.backend(proof)
    origin = _check_game_origin(binary, proof)
    launch = load(directory.parent / 'launch.json')
    frontend = launch.get('frontend')
    if (type(frontend) is not dict or set(frontend) != {'identities', 'argv'}
            or frontend['identities'] != _frontend_identity()):
        raise LabError('actual new frontend/producer identity differs')
    _capture_arguments(frontend['argv'], binary, Path(manifest['assets']['path']), directory.parent,
                       launch['timeoutSeconds'], scenario)
    command = [str(binary), '-bootconfig', str(directory.parent / 'sbinit.config')]
    for field in ('binary', 'assets', 'buildProvenance', 'overlayFiles', 'configuration', 'bootconfig', 'command'):
        if not proof_reader.same_json(launch.get(field), manifest[field]):
            raise LabError('launch/manifest mismatch: ' + field)
    if launch['command'] != command or not proof_reader.same_json(launch.get('gameOrigin'), origin):
        raise LabError('native argv/current origin mismatch')
    from static_vector_capture import validate_launch_protocol
    validate_launch_protocol(directory.parent, launch, manifest)
    frames = captures(directory, config, backend, manifest['exitCode'])
    if r.inventory(frames) != manifest['frames']:
        raise LabError('capture inventory changed')
    scenarios.bind_old(frames, scenario, proof, config)
    if not proof_reader.same_json(load(directory.parent / BINDING), _binding(directory, manifest, origin, launch)):
        raise LabError('external restoration/process/origin binding differs')
    return frames, manifest


def capture(executable, assets, directory, timeout=180, scenario=SCENARIO, *, frontend_argv=None):
    from static_vector_capture import CaptureRequest, ProducerIdentity, capture as produce
    _capture_arguments(frontend_argv, executable, assets, directory, timeout, scenario)
    return produce(CaptureRequest(Path(executable), Path(assets), Path(directory), timeout, scenario,
                                 tuple(frontend_argv)), ProducerIdentity(_frontend_identity()))


# Acquired per-scenario comparator projection; regression tests pin every old branch.
def pair_compare(reference: Path, candidate: Path, output: Path, same_backend=False) -> dict:
    """Read-only with respect to inputs; output must be a fresh lab directory."""
    output = create_owned(output)
    report = {"schema": 1, "passed": False, "parityCertified": False, "inspectionRequired": True, "gate": {"maxError": 0, "changedPixels": 0},
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
            if ref_meta["scenario"] in ("static-vector-room", "id-map-room"):
                key = "staticVectorProof" if ref_meta["scenario"] == "static-vector-room" else "idMapProof"
                wanted = "native" if same_backend else "rust"
                if ref_meta[key]["backend"] != "native" or cand_meta[key]["backend"] != wanted:
                    row["errors"].append("expected native reference and correct typed scene backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "buffer-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["bufferProof"]["backend"] != "cpp" or cand_meta["bufferProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct Buffer backend")
                ref_io = ref_meta["bufferProof"].get("ioDevice")
                cand_io = cand_meta["bufferProof"].get("ioDevice")
                if ref_io is not None or cand_io is not None:
                    if ref_io is None or cand_io is None or ref_io["backend"] != "cpp" or cand_io["backend"] != wanted:
                        row["errors"].append("expected C++ reference and correct IODevice backend")
                ref_file, cand_file = ref_meta.get("fileProof"), cand_meta.get("fileProof")
                if ref_file is not None or cand_file is not None:
                    if (ref_file is None or cand_file is None or ref_file["backend"] != "cpp"
                            or (same_backend and cand_file["backend"] != "cpp")):
                        row["errors"].append("expected C++ reference and consistent File repeat backend")
                    # Earlier combined profiles leave File OFF. The File-specific
                    # qualifier separately requires its ON selector and Rust scopes.
                ref_ba = ref_meta["bufferProof"].get("byteArray")
                cand_ba = cand_meta["bufferProof"].get("byteArray")
                if ref_ba is not None or cand_ba is not None:
                    if ref_ba is None or cand_ba is None or ref_ba["backend"] != "cpp" or (same_backend and cand_ba["backend"] != "cpp"):
                        row["errors"].append("expected C++ reference and consistent ByteArray repeat backend")
                    # Older combined profiles intentionally leave ByteArray OFF.
                    # ByteArray qualification separately requires its ON build
                    # selector and Rust receipt; either valid candidate backend
                    # is compatible with this generic historical comparator.
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "datastream-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["dataStreamProof"]["backend"] != "cpp" or cand_meta["dataStreamProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct DataStream backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "host-address-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["hostAddressProof"]["backend"] != "cpp" or cand_meta["hostAddressProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct HostAddress backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "option-parser-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["optionParserProof"]["backend"] != "cpp" or cand_meta["optionParserProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct OptionParser backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "weighted-pool-room":
                wanted = "native" if same_backend else "rust"
                if ref_meta["weightedPoolProof"]["backend"] != "native" or cand_meta["weightedPoolProof"]["backend"] != wanted:
                    row["errors"].append("expected native reference and correct WeightedPool backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "ttl-room":
                wanted = "native" if same_backend else "rust"
                if ref_meta["ttlProof"]["backend"] != "native" or cand_meta["ttlProof"]["backend"] != wanted:
                    row["errors"].append("expected native reference and correct TTL backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "lru-room":
                wanted = "native" if same_backend else "rust"
                if ref_meta["lruProof"]["backend"] != "native" or cand_meta["lruProof"]["backend"] != wanted:
                    row["errors"].append("expected native reference and correct LRU backend")
                if ref_meta["lightingBackend"] != "cpp" or (same_backend and cand_meta["lightingBackend"] != "cpp"):
                    row["errors"].append("expected C++ reference lighting")
            elif ref_meta["scenario"] == "path-embed-room":
                wanted = "native" if same_backend else "rust"
                if ref_meta["pathEmbedProof"]["backend"] != "native" or cand_meta["pathEmbedProof"]["backend"] != wanted:
                    row["errors"].append("expected native reference and correct PathEmbed backend")
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
            elif ref_meta["scenario"] == "stringview-room":
                wanted = "cpp" if same_backend else "rust"
                if ref_meta["stringViewProof"]["backend"] != "cpp" or cand_meta["stringViewProof"]["backend"] != wanted:
                    row["errors"].append("expected C++ reference and correct StringView backend")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    take = commands.add_parser('capture')
    for flag in ('capture', 'assets', 'output'):
        take.add_argument('--' + flag, type=Path, required=True)
    take.add_argument('--timeout', type=float, default=180)
    take.add_argument('--scenario', choices=SCENARIOS, default=SCENARIO)
    verify = commands.add_parser('verify')
    verify.add_argument('frames', type=Path)
    compare = commands.add_parser('compare')
    for flag in ('reference', 'candidate', 'output'):
        compare.add_argument('--' + flag, type=Path, required=True)
    compare.add_argument('--repeat', type=Path)
    compare.add_argument('--same-backend', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            validated(args.frames)
            return 0
        if args.command == 'capture':
            actual = [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)]
            capture(args.capture, args.assets, args.output, args.timeout, args.scenario, frontend_argv=actual)
            return 0
        if not args.same_backend and args.repeat is None:
            raise LabError('independent native --repeat required BEFORE candidate comparison')
        output = create_owned(args.output)
        baseline = pair_compare(args.reference, args.candidate if args.same_backend else args.repeat,
                                output / 'repeatability', same_backend=True)
        comparison = None
        if not args.same_backend and baseline['passed']:
            comparison = pair_compare(args.reference, args.candidate, output / 'comparison')
        passed = baseline['passed'] and (args.same_backend or bool(comparison and comparison['passed']))
        dump(output / 'report.json', dict(passed=passed, parityCertified=False, inspectionRequired=True,
            repeatability=baseline, comparison=comparison,
            kind='reference-repeatability-only' if args.same_backend else 'exact-pixels-and-state'))
        return 0 if passed else 1
    except (LabError, OSError, ValueError, KeyError, TypeError, Image.DecompressionBombError) as error:
        print('behavior-lab-static-vector: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
