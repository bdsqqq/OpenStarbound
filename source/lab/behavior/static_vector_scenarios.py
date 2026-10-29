"""Explicit scene26 registry and decode-only access to acquired scene1–25 readers."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
FROZEN = {'behavior_lab.py': 'f59670736610be310b6b591b78cc7e4ade2e3c9bfb20b9ba5b6b53eabc05fe32',
          'test_native_scenario_contract.py': '67c8df97ee69a4d6f79c8b8afa934f83192fb5e25f9b09270447397d40653391'}


def assert_frozen():
    for name, digest in FROZEN.items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != digest:
            raise ValueError('frozen reader identity changed: ' + name)


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


assert_frozen()
runner = load_source('_static_vector_frozen_decoder', HERE / 'behavior_lab.py')
# Existing scene25 frontend hooks its OWN private runner. No new hooks, globals,
# launch, origin, validation or comparator from that frontend are used here.
id_decoder = load_source('_static_vector_scene25_decoder', HERE / 'behavior_lab_id_map.py')
configuration = load_source('_static_vector_profiles', HERE.parent / 'static-vector-game/configuration.py')
SCENARIO = 'static-vector-room'
SCENARIOS25 = (*runner.SCENARIOS, 'id-map-room')
SCENARIOS = (*SCENARIOS25, SCENARIO)


def require(scenario):
    assert_frozen()
    if scenario not in SCENARIOS:
        raise runner.LabError('unknown scenario')
    return scenario


def asset_overlays(scenario):
    require(scenario)
    overlays = runner.asset_overlays(scenario)
    if scenario == 'id-map-room':
        overlays['id-map-fixture'] = HERE / 'id-map-assets'
    return overlays


def overlay_identity(scenario):
    result = {}
    for name, source in asset_overlays(scenario).items():
        source = runner.canonical(source)
        if not source.is_dir():
            raise runner.LabError('missing asset overlay: ' + name)
        for path in sorted(source.rglob('*')):
            runner.canonical(path)
            if path.is_file():
                result[name + '/' + path.relative_to(source).as_posix()] = runner.sha(path)
    return result


def decode_old(directory, scenario):
    require(scenario)
    if scenario == SCENARIO:
        raise runner.LabError('scene26 requires trusted configuration/process decoder')
    frames = id_decoder.captures(directory) if scenario == 'id-map-room' else runner.captures(directory)
    if any(f['receipt']['scenario'] != scenario for f in frames.values()):
        raise runner.LabError('decoded scenario differs from admitted configuration')
    return frames


def backend(proof):
    cache = proof.get('build_identity', {}).get('cache', {})
    selectors = {k: v for k, v in cache.items() if k.startswith('STAR_USE_RUST_')}
    role = 'candidate' if selectors.get(configuration.STATIC_VECTOR) == 'ON' else 'reference'
    configuration.validate_profile(role, selectors)
    return 'rust' if role == 'candidate' else 'native'


def bind_old(frames, scenario, proof, config):
    """Preserve old configuration-bound extras without invoking old origin readers."""
    wanted = backend(proof)
    if scenario == 'weighted-pool-room':
        # This is the source-membership/selector portion of the old admission,
        # not its historical origin reader; current30 origin is checked outside.
        import re
        sources = proof.get('source_files', {})
        if any(not isinstance(sources.get(k), str) or not re.fullmatch('[0-9a-f]{64}', sources[k])
               for k in runner.build_provenance.WEIGHTED_POOL_SOURCES):
            raise runner.LabError('WeightedPool production source origin missing')
    for key in {'weighted-pool-room': ('weightedPoolProof',), 'ttl-room': ('ttlProof',),
                'id-map-room': ('idMapProof',)}.get(scenario, ()):
        for frame in frames.values():
            p = frame['receipt'][key]
            import static_vector_proof
            if p['backend'] != wanted or not static_vector_proof.same_json(p['configuration'], config):
                raise runner.LabError('actual backend/configuration differs: ' + key)
    if scenario == 'lru-room' and any(f['receipt']['lruProof']['backend'] != wanted for f in frames.values()):
        raise runner.LabError('LRU actual backend differs')
