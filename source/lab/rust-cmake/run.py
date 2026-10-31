#!/usr/bin/env python3
"""Actual CMake graph, diagnostic Cargo observer only: never builds a Rust archive.

A poisoned or absent ambient RUSTC must not override CMake's selected compiler.
The frozen original recipe is the isolated known-failure control.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')


def command(prefix, argv, env, expected):
    dump(str(prefix)+'.plan.json', dict(argv=argv, env=env, expected=expected))
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    with Path(str(prefix)+'.stdout').open('xb') as out, Path(str(prefix)+'.stderr').open('xb') as err:
        p = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                             stdout=out, stderr=err, start_new_session=True)
        dump(str(prefix)+'.started.json', dict(pid=p.pid, pgid=os.getpgid(p.pid), started=started))
        timed = False
        try:
            code = p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            timed = True
            os.killpg(p.pid, signal.SIGKILL)
            code = p.wait()
        try:
            os.killpg(p.pid, 0)
            gone = False
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            gone = True
    dump(str(prefix)+'.receipt.json', dict(pid=p.pid, returncode=code, groupGone=gone,
         reaped=True, timedOut=timed, started=started,
         ended=dt.datetime.now(dt.timezone.utc).isoformat(),
         stdoutSha256=sha(str(prefix)+'.stdout'), stderrSha256=sha(str(prefix)+'.stderr')))
    if timed or not gone or (code == 0) != expected:
        raise ValueError('actual CMake observer status '+str(prefix))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['output', 'cmake', 'ninja', 'rustc']:
        ap.add_argument('--'+name, required=True)
    ap.add_argument('--historical-source', default=str(Path(__file__).with_name('Rust.original.cmake')))
    ap.add_argument('--historical-sha', default='d2a07074c05620f0ca296305c63f131ddcb0c56e884cb978780fdd5ad5266747')
    a = ap.parse_args()
    out = Path(a.output).resolve()
    out.mkdir(exist_ok=False)
    current = ROOT/'cmake/Rust.cmake'
    historical = Path(a.historical_source).resolve()
    if sha(historical) != a.historical_sha:
        raise ValueError('frozen known-failure source pin')
    old = historical.read_text()
    insertion = '"CARGO_TARGET_DIR=${STAR_RUST_TARGET_DIR}"'
    expected = old.replace(insertion, insertion+'\n    "RUSTC=${STAR_RUSTC_EXECUTABLE}"')
    expected = expected.replace('# Keep Cargo output isolated per CMake build, with an explicit native target.',
        '# Isolate by default; callers may share a Cargo cache across compatible native builds.')
    expected = expected.replace('set(STAR_RUST_TARGET_DIR "${CMAKE_BINARY_DIR}/rust-engine-ffi")',
        'set(STAR_RUST_TARGET_DIR "${CMAKE_BINARY_DIR}/rust-engine-ffi" CACHE PATH\n  "Cargo target directory for the single Rust engine archive")')
    if old.count(insertion) != 1 or expected != current.read_text():
        raise ValueError('compiler-environment and optional target-cache recipe delta')
    tools = {name: str(Path(getattr(a, name)).resolve(strict=True)) for name in ['cmake', 'ninja', 'rustc']}
    pins = {p: sha(p) for p in [*tools.values(), str(current), str(historical), str(Path(__file__).resolve())]}
    dump(out/'admission.json', dict(tools=tools, pins=pins, scope='actual CMake; diagnostic Cargo observer, NO Rust compilation/archive/game'))
    rows = []
    for old_recipe in [True, False]:
        for poisoned in [False, True]:
            case = out/(('original' if old_recipe else 'selected')+('-poisoned' if poisoned else '-absent'))
            case.mkdir()
            fixture = case/'workspace with spaces'
            (fixture/'rust').mkdir(parents=True)
            (fixture/'rust/Cargo.toml').write_text('[workspace]\nmembers=[]\n')
            (fixture/'rust/Cargo.lock').write_text('version = 3\n')
            probe = fixture/'diagnostic cargo'
            expected_args = ['build', '--manifest-path', str(fixture/'rust/Cargo.toml'), '--package', 'star-engine-ffi']
            probe.write_text('#!'+sys.executable+'\nimport json,os,pathlib,sys\n'+
                'wanted='+repr(tools['rustc'])+'\n'+
                'record=dict(rustc=os.environ.get("RUSTC"),argv=sys.argv[1:],target=os.environ.get("CARGO_TARGET_DIR"))\n'+
                'pathlib.Path('+repr(str(case/'observer.json'))+').write_text(json.dumps(record,sort_keys=True))\n'+
                'sys.exit(0 if record["rustc"]==wanted else 73)\n')
            probe.chmod(0o755)
            recipe = historical if old_recipe else current
            (fixture/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(compiler_env_probe LANGUAGES NONE)\nset(STAR_ARCHITECTURE '+('arm64' if platform.machine() in ('arm64','aarch64') else 'x86_64')+')\ninclude('+json.dumps(str(recipe))+')\n')
            env = dict(PATH='/usr/bin:/bin', LANG='C', LC_ALL='C', PYTHONDONTWRITEBYTECODE='1')
            if poisoned:
                env['RUSTC'] = str(case/'NOT-SELECTED-RUSTC')
            binary = case/'cmake'
            configure = [tools['cmake'], '-G', 'Ninja', '-S', str(fixture), '-B', str(binary),
                         '-DCMAKE_MAKE_PROGRAM='+tools['ninja'], '-DSTAR_CARGO_EXECUTABLE='+str(probe),
                         '-DSTAR_RUSTC_EXECUTABLE='+tools['rustc']]
            # Default stays per-build. Also exercise an explicit path containing
            # spaces while the ambient compiler is poisoned.
            target = case/'shared target' if not old_recipe and poisoned else binary/'rust-engine-ffi'
            if not old_recipe and poisoned:
                configure.append('-DSTAR_RUST_TARGET_DIR='+str(target))
            command(case/'configure', configure, env, True)
            command(case/'build', [tools['cmake'], '--build', str(binary), '--target', 'star_rust_engine_ffi_build'], env, not old_recipe)
            observed = json.loads((case/'observer.json').read_bytes())
            if observed['argv'][:len(expected_args)] != expected_args or observed['argv'][-3:] != ['--release', '--locked', '--offline']:
                raise ValueError('unchanged Cargo graph arguments')
            if observed['target'] != str(target):
                raise ValueError('default or explicit Cargo target directory not respected')
            if (observed['rustc'] == tools['rustc']) != (not old_recipe):
                raise ValueError('compiler observer contract')
            if list(binary.rglob('*.a')) or list(binary.rglob('*.lib')):
                raise ValueError('diagnostic observer must never produce an archive')
            rows.append(dict(case=case.name, selectedCompiler=not old_recipe, ambientPoisoned=poisoned,
                             observerSha256=sha(case/'observer.json')))
    if any(sha(p) != h for p, h in pins.items()):
        raise ValueError('admitted input drift')
    dump(out/'report.json', dict(status='ACTUAL_CMAKE_COMPILER_ENV_DIAGNOSTIC_PASS', cases=rows,
         actualCommands=8, admissionSha256=sha(out/'admission.json'),
         limits=['diagnostic Cargo observer, not real Cargo/Rust archive/game qualification',
                 'current native platform only; not full project or Windows runtime qualification']))
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
