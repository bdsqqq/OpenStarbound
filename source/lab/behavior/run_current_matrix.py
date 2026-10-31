#!/usr/bin/env python3
"""Compare existing real-game scenes without inventing a legacy origin certificate.

Supply current native/Rust clients and an owned isolated ship fixture. Reuses the
existing scene decoders, process guardian and fixed storage caps. Successful
scratch worlds are removed; compact receipts and images remain. No builds here.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import static_vector_scenarios as scenes

ROOT = Path(__file__).resolve().parents[3]
lab = scenes.runner
spec = importlib.util.spec_from_file_location('_current_matrix_process', ROOT / 'scripts/build-static-vector-behavior-lab.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(decoded):
    """All bytes, including alpha; no crops, masks, backend-fitted tolerances."""
    reference, repeat, candidate = decoded
    if not reference.keys() == repeat.keys() == candidate.keys():
        raise ValueError('frame names differ')
    rows = []
    for name in reference:
        frames = [source[name] for source in decoded]
        raw = [lab.image(frame['png']).tobytes() for frame in frames]
        if raw[0] != raw[1] or raw[0] != raw[2]:
            raise ValueError('full RGBA differs: ' + name)
        states = [frame['receipt']['worldState'] for frame in frames]
        if not states[0] == states[1] == states[2]:
            raise ValueError('validated world/consumer state differs: ' + name)
        # Consumer proofs can contain multi-megabyte input byte vectors. They
        # were compared above; receipts retain them. Do not duplicate them into
        # every per-scene/aggregate summary.
        state_bytes = json.dumps(states[0], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        rows.append(dict(name=name, rgbaSha256=hashlib.sha256(raw[0]).hexdigest(),
                         stateSha256=hashlib.sha256(state_bytes).hexdigest()))
    return rows


def retire_scratch(cap, write):
    """Retire only a completed, closed, sentinel-owned scene's disposable data."""
    lab.check_owned(cap)
    scratch = [cap / 'frames/storage', cap / 'home', cap / 'tmp']
    files = [p for directory in scratch for p in directory.rglob('*') if p.is_symlink() or p.is_file()]
    inventory = [dict(path=str(p.relative_to(cap)), symlink=os.readlink(p)) if p.is_symlink() else
        dict(path=str(p.relative_to(cap)), bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(files)]
    write(cap / 'scratch-removed.json', dict(files=inventory,
        reason='rebuildable isolated worlds/cache; no archive duplication'))
    for directory in scratch:
        shutil.rmtree(directory)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'assets', 'output', 'ship-context', 'ship-system'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--scene', action='append', choices=scenes.SCENARIOS25)
    ap.add_argument('--budget-seconds', type=int, default=1200)
    args = ap.parse_args()
    if not 1 <= args.budget_seconds <= 1800:
        raise ValueError('bounded matrix clock required')
    selected = args.scene or [s for s in scenes.SCENARIOS25 if s != 'lighting-room']
    if len(set(selected)) != len(selected):
        raise ValueError('duplicate scene')
    inputs = {name: getattr(args, name).resolve(strict=True) for name in
              ('reference', 'candidate', 'assets', 'ship_context', 'ship_system')}
    for name in ('ship_context', 'ship_system'):
        if not inputs[name].is_relative_to(ROOT / 'build'):
            raise ValueError('only owned lab fixture data under build may seed worlds')
    if inputs['ship_context'].name != '00000000000000000000000000000042.clientcontext' or inputs['ship_system'].suffix != '.system':
        raise ValueError('explicit laboratory player/system fixture required')
    if inputs['ship_context'].read_bytes()[:6] != b'SBVJ01':
        raise ValueError('native versioned client-context fixture required')
    root = builder.ad.allocation_root()
    if not args.output.resolve().is_relative_to(root):
        raise ValueError('output must remain inside the existing charged active root')
    names = set(re.findall(r'^option\((STAR_USE_RUST_\w+) ', (ROOT / 'source/CMakeLists.txt').read_text(), re.M))
    caches = {}
    for role in ('reference', 'candidate'):
        path = inputs[role].parent.parent / 'CMakeCache.txt'
        rows = re.findall(r'^(STAR_USE_RUST_\w+):BOOL=(ON|OFF)$', path.read_text(), re.M)
        if len(rows) != len(dict(rows)) or len(rows) != len(names) or set(dict(rows)) != names:
            raise ValueError('all unique current build selectors required')
        values = dict(rows)
        expected = {key: 'ON' if role == 'candidate' and key != 'STAR_USE_RUST_LINE_QUERY' else 'OFF' for key in values}
        if values != expected:
            raise ValueError('native/combined build selector profile differs')
        caches[role] = dict(path=str(path), sha256=sha(path), selectors=values)
    out = lab.create_owned(args.output.resolve())
    deadline = time.monotonic() + args.budget_seconds
    pins = {name: dict(path=str(path), sha256=sha(path)) for name, path in inputs.items()}
    write = lambda p, value: builder.ad.bounded.write_json(p, value, 4 * 1024**2)
    write(out / 'inputs.json', dict(inputs=pins, caches=caches, scenes=selected, toolSha256=sha(Path(__file__)), scope='finite current-client matrix; NOT whole-origin/full-port qualification'))
    literal = str(root).replace('\\', '\\\\').replace('"', '\\"')
    policy = ('(version 1)(allow default)(deny file-mount file-unmount)(deny file-write*)'
              '(allow file-write* (subpath "' + literal + '") '
              '(regex #"^(/private)?/var/tmp/starbound[.]tmpfile[.][A-Za-z0-9]+$"))')
    def validate():
        if time.monotonic() >= deadline:
            raise ValueError('matrix clock expired')
        builder.ad.allocation.enforce_live(ROOT, root)

    results = []
    for scene in selected:
        paths, decoded = [], []
        for role in ('reference', 'repeat', 'candidate'):
            # Do not launch a client that cannot receive its full declared
            # capture timeout. Completed per-scene results remain checkpoints.
            if deadline - time.monotonic() < 180:
                raise ValueError('matrix budget too short to admit another complete capture')
            cap = lab.create_owned(out / (scene + '-' + role))
            frames = lab.create_owned(cap / 'frames')
            storage = lab.create_owned(frames / 'storage')
            home = lab.create_owned(cap / 'home')
            tmp = lab.create_owned(cap / 'tmp')
            (storage / 'universe').mkdir()
            for name in ('ship_context', 'ship_system'):
                source = inputs[name]
                if sha(source) != pins[name]['sha256']:
                    raise ValueError('fixture data changed')
                shutil.copyfile(source, storage / 'universe' / source.name)
            cfg = dict(outputDirectory=str(frames), storageDirectory=str(storage), scenario=scene,
                       maxFrames=1800, platformWrites=False)
            lab.dump(cap / 'scenario.json', cfg)
            defaults = dict(includeUGC=False, vsync=False, windowedResolution=[1000, 600], fullscreen=False,
                maximized=False, borderless=False, sfxVol=0, musicVol=0, instrumentVol=0,
                clearUniverseFiles=False, clientIPJoinable=False, clientP2PJoinable=False,
                serverAdvertise=False, serverIP='127.0.0.1')
            if scene == 'option-parser-room':
                defaults['optionParserProof'] = lab.option_parser_proof.CONFIGURATION
            if scene in ('encoding-room', 'vlq-room', 'bytes-room', 'compression-room', 'zstd-room', 'path-embed-room'):
                defaults['safe'] = dict(allowRemoteAssets=True)
            lab.dump(cap / 'sbinit.config', dict(assetDirectories=[], assetSources=[str(inputs['assets']),
                *(str(p.resolve()) for p in scenes.asset_overlays(scene).values())], storageDirectory=str(storage),
                logDirectory=str(storage), includeUGC=False, defaultConfiguration=defaults))
            exe = inputs['candidate' if role == 'candidate' else 'reference']
            if sha(exe) != pins['candidate' if role == 'candidate' else 'reference']['sha256']:
                raise ValueError('client changed during matrix')
            env = dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=str(home), TMPDIR=str(tmp), LANG='C', LC_ALL='C',
                XDG_DATA_HOME=str(home / 'data'), XDG_CONFIG_HOME=str(home / 'config'), XDG_CACHE_HOME=str(home / 'cache'),
                STAR_BEHAVIOR_LAB=str(cap / 'scenario.json'))
            started = time.monotonic()
            def remaining():
                return max(0, min(deadline - time.monotonic(), 180 - (time.monotonic() - started)))
            def output(path):
                if path.parent != cap or path.exists():
                    raise ValueError('fresh owned process output required')
            builder._supervise_command(['/usr/bin/sandbox-exec', '-p', policy, str(exe), '-bootconfig', str(cap / 'sbinit.config')],
                ROOT, env, cap / 'process', limits=dict(stdoutBytes=4 * 1024**2, stderrBytes=2 * 1024**2,
                readChunkBytes=65536, overflowBytes=65536), validate=validate, remaining_seconds=remaining,
                python=Path(sys.executable).resolve(), witness={}, write_record=write, check_output=output,
                scope='ACTUAL_CURRENT_CLIENT_EXISTING_SCENE_NOT_LEGACY_CERTIFICATE', stdin=subprocess.DEVNULL)
            data = scenes.decode_old(frames, scene)
            if any(frame['receipt']['lightingBackend'] != ('rust' if role == 'candidate' else 'cpp') for frame in data.values()):
                raise ValueError('actual lighting backend differs from declared client role')
            decoded.append(data)
            paths.append(cap)
        result = dict(scene=scene, frames=compare(decoded))
        write(out / (scene + '-result.json'), result)
        # Only successful, closed, newly owned scratch. Keep failed worlds intact.
        for cap in paths:
            retire_scratch(cap, write)
        results.append(result)
        print(scene + ': native/repeat/combined pixels + consumer state PASS', flush=True)
    write(out / 'result.json', dict(status='CURRENT_COMBINED_EXISTING_SCENES_PASS', scenes=len(results),
        newGameRuns=3 * len(results), comparisons=results, inputs=pins, budget=builder.ad.check_budget(),
        limits=['finite seeded-ship scene matrix; native random-start crashes remain unresolved',
                'actual game/decoder observations, not a legacy source-origin certificate or full port']))


if __name__ == '__main__':
    main()
