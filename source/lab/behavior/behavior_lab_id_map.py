#!/usr/bin/env python3
"""Explicit scene-25 frontend; synthetic tests are NOT real-game evidence.

The acquired runner stays byte-exact. Capture admission for scene25 is deliberately
unavailable until a new producer binds this tool's actual argv and game origins.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
LEGACY_SHA256 = 'f59670736610be310b6b591b78cc7e4ade2e3c9bfb20b9ba5b6b53eabc05fe32'
SCENARIO = 'id-map-room'
RESTORATION = 'idmap-restoration.json'
BINDING = 'id-map-binding.json'  # Deliberately OUTSIDE frames/.


def _load_legacy(path=HERE / 'behavior_lab.py'):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != LEGACY_SHA256:
        raise RuntimeError('frozen behavior_lab.py hash mismatch')
    spec = importlib.util.spec_from_file_location('_id_map_frozen_behavior_lab', path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


_legacy = _load_legacy()
LabError = _legacy.LabError
import id_map_proof as _proof

_original = {name: getattr(_legacy, name) for name in
             ('captures', 'validated', 'asset_overlays', 'verified_build', 'capture', 'pair_compare')}
SCENARIOS = (*_legacy.SCENARIOS, SCENARIO)
SELECTORS = (*_legacy.build_provenance.WEIGHTED_POOL_SELECTORS, _proof.SELECTOR)


def _assert_frozen():
    if _legacy.sha(HERE / 'behavior_lab.py') != LEGACY_SHA256:
        raise LabError('frozen behavior_lab.py hash mismatch')


def asset_overlays(scenario='lighting-room'):
    _assert_frozen()
    overlays = _original['asset_overlays'](scenario)
    if scenario == SCENARIO:
        overlays['id-map-fixture'] = HERE / 'id-map-assets'
    return overlays


def _is_id_map(directory):
    if (directory / RESTORATION).exists():
        return True
    for path in directory.glob('*.json'):
        if path.name == 'manifest.json':
            continue
        envelope = _legacy.load(path)
        if isinstance(envelope, dict) and isinstance(envelope.get('metadata'), dict):
            if envelope['metadata'].get('scenario') == SCENARIO:
                return True
    return False


def _restoration(directory):
    value = _legacy.load(directory / RESTORATION)
    expected = dict(version=1, scenario=SCENARIO, stat='behaviorLabIdMap', value=0,
                    ownedCategoriesAbsent=True, lastPreparedStage=2)
    if not _proof.same(value, expected):
        raise LabError('IdMap restoration exact schema/type/value mismatch')
    return _legacy.identity(directory / RESTORATION)


def captures(directory):
    _assert_frozen()
    directory = _legacy.check_owned(directory)
    if not _is_id_map(directory):
        return _original['captures'](directory)
    _restoration(directory)
    allowed = {'manifest.json', RESTORATION, *(name + suffix for name in _proof.STAGES
                                               for suffix in ('.png', '.json'))}
    if any(path.suffix.lower() in ('.png', '.json') and path.name not in allowed
           for path in directory.iterdir()):
        raise LabError('IdMap unknown JSON/frame file refused')
    pngs = {p.stem: p for p in directory.glob('*.png')}
    receipts = {p.stem: p for p in directory.glob('*.json')
                if p.name not in ('manifest.json', RESTORATION)}
    if set(pngs) != set(_proof.STAGES) or set(receipts) != set(pngs):
        raise LabError('IdMap requires exactly three paired PNG/JSON frames; unknown JSON refused')
    result = {}
    try:
        for name in _proof.STAGES:
            envelope = _legacy.load(receipts[name])
            if (type(envelope) is not dict or envelope.get('name') != name
                    or envelope.get('file') != name + '.png'):
                raise LabError('IdMap invalid frame envelope')
            info = envelope.get('capture')
            if (type(info) is not dict or info.get('source') != 'final-default-framebuffer'
                    or info.get('stage') != 'after-imgui-before-swap'):
                raise LabError('IdMap requires final framebuffer/pre-swap')
            raw = envelope.get('metadata')
            if (type(raw) is not dict or raw.get('scenario') != SCENARIO
                    or raw.get('inWorld') is not True or raw.get('stage') != name):
                raise LabError('IdMap invalid frame metadata')
            receipt = dict(raw)
            # Preserve BOTH declared invisible state and the frozen native projection.
            receipt['worldState'] = _legacy.semantic_world_state(raw)
            receipt['worldState']['idMapProof'] = _proof.observation(raw)
            lighting, calls = raw.get('lightingBackend'), raw.get('rustLightingCalls')
            if (lighting not in ('cpp', 'rust') or type(calls) is not int
                    or (calls != 0 if lighting == 'cpp' else calls <= 0)):
                raise LabError('IdMap invalid lighting backend/calls')
            frame = _legacy.image(pngs[name])
            if (type(envelope.get('width')) is not int or type(envelope.get('height')) is not int
                    or [envelope['width'], envelope['height']] != list(frame.size)):
                raise LabError('IdMap receipt/PNG dimensions disagree')
            _proof.visible(frame, receipt)
            result[name] = dict(receipt=receipt, png=pngs[name], dimensions=list(frame.size),
                                pngSha256=_legacy.sha(pngs[name]),
                                receiptSha256=_legacy.sha(receipts[name]),
                                pixelsSha256=hashlib.sha256(frame.tobytes()).hexdigest())
        _proof.validate_sequence(result, _legacy.SCENE_FIELDS)
    except ValueError as error:
        raise LabError(str(error)) from error
    return result


def _check_selectors(proof, backend=None):
    build = proof.get('build_identity') if isinstance(proof, dict) else None
    cache = build.get('cache') if isinstance(build, dict) else None
    if not isinstance(cache, dict) or {k for k in cache if k.startswith('STAR_USE_RUST_')} != set(SELECTORS):
        raise LabError('IdMap requires actual complete 29-selector build proof')
    inferred = 'rust' if cache.get(_proof.SELECTOR) == 'ON' else 'native'
    backend = backend or inferred
    for key in SELECTORS:
        expected = 'ON' if backend == 'rust' and key != 'STAR_USE_RUST_LINE_QUERY' else 'OFF'
        if cache.get(key) != expected:
            raise LabError('IdMap backend/config selector mismatch: ' + key)
    return backend


def _check_game_origin(executable, proof):
    """No old WeightedPool attestation or unrelated archive can substitute here."""
    path = _legacy.canonical(HERE / 'id_map_origin.py')
    if not path.is_file():
        raise LabError('IdMap OriginNotReady: new game-origin validator unavailable')
    try:
        spec = importlib.util.spec_from_file_location('_id_map_game_origin', path)
        module = importlib.util.module_from_spec(spec)
        # Register only during execution: dataclass-based validators need this entry.
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
            result = module.validate_game_origin(Path(executable), proof)
        finally:
            sys.modules.pop(spec.name, None)
    except Exception as error:
        raise LabError('IdMap game origin rejected/unavailable: ' + str(error)) from error
    if type(result) is not dict or not result:
        raise LabError('IdMap game origin returned no binding')
    return result


def verified_build(executable):
    _assert_frozen()
    # Generic verify preserves all fields, including actual29. It has no fixed
    # selector extent; the historical WeightedPool-specific verifier is NOT used.
    proof = _original['verified_build'](executable)
    _check_selectors(proof)
    _check_game_origin(executable, proof)
    return proof


def _frontend_identity():
    return dict(tool=_legacy.identity(Path(__file__)),
                proofReader=_legacy.identity(HERE / 'id_map_proof.py'),
                legacy=_legacy.identity(HERE / 'behavior_lab.py'),
                originValidator=(_legacy.identity(HERE / 'id_map_origin.py')
                                 if (HERE / 'id_map_origin.py').is_file() else None))


def _binding(directory, manifest, origin, launch):
    return dict(schema=1, scenario=SCENARIO,
                captureManifest=_legacy.identity(directory / 'manifest.json'),
                restoration=_restoration(directory), launch=_legacy.identity(directory.parent / 'launch.json'),
                processStart=manifest['processStart'], processExit=manifest['processExit'],
                configuration=manifest['configuration'], bootconfig=manifest['bootconfig'],
                binary=manifest['binary'], assets=manifest['assets'],
                compiledHeader=_legacy.identity(HERE / 'id_map_scene.hpp'),
                frontend=launch['frontend'], gameOrigin=origin)


def validated(directory):
    directory = _legacy.check_owned(directory)
    # Original manifest checks run unconditionally, using the new decoder only
    # for scene25. No caught/ignored legacy validation failures.
    frames, manifest = _original['validated'](directory)
    if next(iter(frames.values()))['receipt']['scenario'] != SCENARIO:
        return frames, manifest
    if any((p / 'failure.json').exists() for p in (directory, directory.parent)):
        raise LabError('IdMap aborted capture cannot pass')
    if (type(manifest.get('schema')) is not int or type(manifest.get('exitCode')) is not int
            or not isinstance(manifest.get('captureId'), str) or not manifest['captureId']):
        raise LabError('IdMap invalid successful manifest metadata')
    _legacy.validate_process_binding(directory, manifest)
    for field, path in (('configuration', directory.parent / 'scenario.json'),
                        ('bootconfig', directory.parent / 'sbinit.config')):
        if _legacy.identity(path) != manifest[field]:
            raise LabError('IdMap actual ' + field + ' identity changed')
    for field in ('binary', 'assets'):
        if _legacy.identity(Path(manifest[field]['path'])) != manifest[field]:
            raise LabError('IdMap actual ' + field + ' identity changed')
    config = _legacy.load(Path(manifest['configuration']['path']))
    expected_config = dict(scenario=SCENARIO, outputDirectory=str(directory),
                           storageDirectory=str(directory / 'storage'),
                           maxFrames=1800, platformWrites=False)
    if not _proof.same(config, expected_config):
        raise LabError('IdMap actual isolated configuration mismatch')
    semantic_config = dict(config, outputDirectory='<isolated-output>', storageDirectory='<isolated-storage>')
    semantic_boot = _legacy.load(directory.parent / 'sbinit.config')
    if not isinstance(semantic_boot, dict):
        raise LabError('IdMap boot configuration must be an object')
    for field in ('storageDirectory', 'logDirectory'):
        if field in semantic_boot:
            semantic_boot[field] = '<isolated-storage>'
    if (not _proof.same(manifest.get('semanticConfiguration'), semantic_config)
            or not _proof.same(manifest.get('semanticBootconfig'), semantic_boot)
            or manifest.get('overlayFiles') != _legacy.overlay_identity(SCENARIO)):
        raise LabError('IdMap semantic configuration/asset overlay binding differs')
    backend = next(iter(frames.values()))['receipt']['idMapProof']['backend']
    _check_selectors(manifest['buildProvenance'], backend)
    for frame in frames.values():
        if not _proof.same(frame['receipt']['idMapProof']['configuration'], config):
            raise LabError('IdMap source/capture configuration differs')
    if verified_build(Path(manifest['binary']['path'])) != manifest['buildProvenance']:
        raise LabError('IdMap current game proof differs from capture manifest')
    origin = _check_game_origin(Path(manifest['binary']['path']), manifest['buildProvenance'])
    launch = _legacy.load(directory.parent / 'launch.json')
    frontend = launch.get('frontend')
    if type(frontend) is not dict or set(frontend) != {'identities', 'argv'}:
        raise LabError('IdMap new frontend launch admission missing')
    argv = frontend['argv']
    if (not isinstance(argv, list) or not argv or not all(type(a) is str for a in argv)
            or _legacy.canonical(Path(argv[0])) != Path(__file__).resolve()
            or frontend['identities'] != _frontend_identity()):
        raise LabError('IdMap actual frontend tool identity/argv mismatch')
    if not _proof.same(_legacy.load(directory.parent / BINDING), _binding(directory, manifest, origin, launch)):
        raise LabError('IdMap restoration/process/config/tool/game binding changed')
    return frames, manifest


def pair_compare(reference, candidate, output, same_backend=False):
    """Check IdMap dispatch explicitly BEFORE the frozen full-frame comparator."""
    try:
        expected, _ = validated(reference)
        actual, _ = validated(candidate)
        scenarios = {f['receipt']['scenario'] for f in (*expected.values(), *actual.values())}
        if SCENARIO in scenarios:
            if scenarios != {SCENARIO}:
                raise LabError('IdMap comparison scenario mismatch')
            for frames, wanted in ((expected, 'native'), (actual, 'native' if same_backend else 'rust')):
                if any(f['receipt']['idMapProof']['backend'] != wanted for f in frames.values()):
                    raise LabError('IdMap expected native reference and correct comparison backend')
        return _original['pair_compare'](reference, candidate, output, same_backend)
    except (LabError, OSError, ValueError, KeyError, TypeError, _legacy.Image.DecompressionBombError) as error:
        output = _legacy.create_owned(output)
        report = dict(schema=1, passed=False, frames={}, errors=[str(error)])
        _legacy.dump(output / 'report.json', report)
        return report


def capture(executable, assets, directory, timeout, scenario=SCENARIO):
    if scenario != SCENARIO:
        return _original['capture'](executable, assets, directory, timeout, scenario)
    verified_build(executable)
    # Even a valid new game origin does not admit an old tool's argv. No launch
    # until an actual new-tool producer seals frontend/process/restoration bindings.
    raise LabError('IdMap OriginNotReady: scene25 launch-admission producer not implemented; no game launched')


# Four additive hooks only. verified_build remains original inside the private
# runner so old24 capture behavior is unchanged; scene25 calls ours explicitly.
_legacy.SCENARIOS = SCENARIOS
_legacy.asset_overlays = asset_overlays
_legacy.captures = captures
_legacy.validated = validated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('frames', type=Path)
    compare = commands.add_parser('compare')
    compare.add_argument('--reference', type=Path, required=True)
    compare.add_argument('--candidate', type=Path, required=True)
    compare.add_argument('--output', type=Path, required=True)
    compare.add_argument('--same-backend', action='store_true')
    compare.add_argument('--repeat', type=Path, help='required second native baseline unless --same-backend')
    take = commands.add_parser('capture')
    take.add_argument('--capture', type=Path, required=True)
    take.add_argument('--assets', type=Path, required=True)
    take.add_argument('--output', type=Path, required=True)
    take.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            validated(args.frames)
            return 0
        if args.command == 'compare':
            if not args.same_backend and args.repeat is None:
                raise LabError('IdMap comparison requires an independent native --repeat first')
            output = _legacy.create_owned(args.output)
            baseline = pair_compare(args.reference, args.candidate if args.same_backend else args.repeat,
                                    output / 'repeatability', same_backend=True)
            comparison = None
            if not args.same_backend and baseline['passed']:
                comparison = pair_compare(args.reference, args.candidate, output / 'comparison')
            passed = baseline['passed'] and (args.same_backend or bool(comparison and comparison['passed']))
            _legacy.dump(output / 'report.json', dict(passed=passed, parityCertified=False,
                         inspectionRequired=True, repeatability=baseline, comparison=comparison,
                         kind='reference-repeatability-only' if args.same_backend else 'exact-pixels-and-state'))
            return 0 if passed else 1
        capture(args.capture, args.assets, args.output, args.timeout)
        return 0
    except (LabError, OSError, ValueError, KeyError, TypeError, _legacy.Image.DecompressionBombError) as error:
        print('behavior-lab-id-map: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
