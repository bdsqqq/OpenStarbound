#!/usr/bin/env python3
"""Build one freshly admitted IdMap pair; never launch it or retire predecessors.

The immutable legacy recipe is not invoked. A successful build is NOT origin,
gameplay or module qualification. Every native command remains deadline/budget
supervised, with its actual argv and sanitized environment recorded beforehand.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ad = load('_idmap_builder_admission', ROOT / 'source/lab/id-map-production/game_build_admission.py')
bp = load('_idmap_builder_provenance', ROOT / 'source/lab/behavior/build_provenance.py')


def identity(path):
    path = Path(path)
    ad.no_symlink_parents(path)
    ad.need(path.is_file(), 'physical build product required: ' + str(path))
    return dict(path=str(path), sha256=ad.sha(path), size=path.stat().st_size)


def read_plan(path, pin):
    path = Path(path).absolute()
    ad.no_symlink_parents(path)
    ad.need(ad.sha(path) == pin, 'external admission SHA256 mismatch')
    plan = json.loads(path.read_text())
    ad.validate(plan)
    return plan


def environment(plan, role):
    # Do not inherit RUSTFLAGS/CFLAGS/SDKROOT/tool-search overrides from a shell.
    home = pwd.getpwuid(os.getuid()).pw_dir
    return dict(HOME=home, PATH='/usr/bin:/bin', SDKROOT=plan['sdk'],
                VCPKG_ROOT=home + '/.cache/openstarbound-vcpkg',
                CARGO_HOME=str(Path(plan['buildRoot']) / role / 'cargo-home'),
                TMPDIR=str(Path(plan['buildRoot']) / role / 'tmp'))


def remaining(plan):
    end = dt.datetime.fromisoformat(plan['createdUTC']) + dt.timedelta(seconds=ad.DEADLINES['maxAgeSeconds'])
    value = (end - dt.datetime.now(dt.timezone.utc)).total_seconds()
    ad.need(value > 0, 'original admission deadline reached')
    return value


def supervise(argv, cwd, env, output, plan):
    """Preserve failed commands; terminate only this owned process group."""
    started_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    ad.dump(output.with_suffix('.command.json'), dict(argv=argv, cwd=str(cwd), environment=env, startedUTC=started_utc))
    remaining(plan)
    ad.check_budget(Path(plan['buildRoot']))
    ad.need(not os.path.lexists(ROOT / 'build/.migration-cleanup.lock'), 'cleanup active before owned command')
    start = time.monotonic()
    with output.with_suffix('.stdout').open('xb') as stdout, output.with_suffix('.stderr').open('xb') as stderr:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        failure = None
        try:
            while True:
                try:
                    code = proc.wait(timeout=min(2, remaining(plan)))
                    break
                except subprocess.TimeoutExpired:
                    ad.need(not os.path.lexists(ROOT / 'build/.migration-cleanup.lock'), 'cleanup started during owned build')
                    ad.check_budget(Path(plan['buildRoot']))
        except BaseException as error:
            failure = str(error)
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            raise
        finally:
            # Even a successful leader may leave a descendant behind. No
            # command in this recipe is allowed to create a background service.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            ad.dump(output.with_suffix('.receipt.json'), dict(argv=argv, returncode=proc.returncode,
                    elapsedSeconds=time.monotonic() - start, failure=failure, pid=proc.pid,
                    finishedUTC=dt.datetime.now(dt.timezone.utc).isoformat()))
    ad.need(code == 0, 'native command failed; immutable logs retained: ' + str(output))
    ad.check_deadline(plan)
    ad.check_budget(Path(plan['buildRoot']))


def make_rule(raw):
    """Decode clang's single Make dependency rule, not shell quoting.

    Quotes are ordinary filename characters. Reject additional rules instead of
    treating a phony target as another dependency; escaped spaces/#/$ survive.
    """
    tokens, current, left = [], [], None
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == '\\':
            ad.need(i + 1 < len(raw), 'trailing dependency escape')
            i += 1
            if raw[i] != '\n':
                current.append(raw[i])
        elif c == '$':
            ad.need(i + 1 < len(raw) and raw[i + 1] == '$', 'unsupported Make expansion')
            current.append('$')
            i += 1
        elif c == ':':
            ad.need(left is None, 'multiple dependency rules/targets')
            if current:
                tokens.append(''.join(current)); current = []
            left, tokens = tokens, []
        elif c.isspace():
            if current:
                tokens.append(''.join(current)); current = []
        else:
            ad.need(c != '#', 'unescaped dependency comment')
            current.append(c)
        i += 1
    if current:
        tokens.append(''.join(current))
    ad.need(left is not None and len(left) == 1 and tokens, 'one nonempty dependency rule required')
    return left[0], tokens


def dependency_witness(plan, receipt, snapshot):
    obj, dep = Path(receipt['clientObject']), Path(receipt['clientDepfile'])
    identity(obj); dep_id = identity(dep)
    # Compile commands are relative to the admitted CMake working directory.
    role_build = Path(plan['buildRoot']) / receipt['backend'] / 'cmake'
    target, paths = make_rule(dep.read_text())
    target = Path(target) if Path(target).is_absolute() else role_build / target
    ad.need(target == obj, 'dependency target differs from actual configured client object')
    expected = dict(plan['witness']['files'])
    expected.update(snapshot['compile_source_files'])
    bindings = {}
    for name in paths:
        path = Path(name) if Path(name).is_absolute() else role_build / name
        resolved = path.resolve(strict=True)
        ad.need(str(resolved) in expected and ad.sha(resolved) == expected[str(resolved)],
                'unadmitted/changed compiler dependency: ' + str(path))
        ad.need(obj.stat().st_mtime_ns >= resolved.stat().st_mtime_ns, 'dependency newer than client object')
        bindings[str(resolved)] = dict(physical=str(resolved), sha256=expected[str(resolved)])
    header = plan['compiledHeader']
    ad.need(header['path'] in bindings and bindings[header['path']]['sha256'] == header['sha256'],
            'actual compile did not consume admitted id_map_scene.hpp')
    client = str(ROOT / 'source/client/StarClientApplication.cpp')
    ad.need(client in bindings, 'actual client source missing from dependency rule')
    return dict(schema=1, clientObject=identity(obj), depfile=dep_id, dependencies=bindings,
                headerRole='OBSERVED_COMPILER_DEPENDENCY; not emitted-code or dynamic proof')


def build_pair(plan_path, pin, run=supervise):
    plan = read_plan(plan_path, pin)
    root = Path(plan['buildRoot'])
    ad.need(not os.path.lexists(root), 'fresh generation required; never resume/relabel a failed pair')
    root.mkdir()
    try:
        for role in ('reference', 'candidate'):
            ad.validate(plan)
            side = root / role
            side.mkdir(); (side / 'tmp').mkdir(); (side / 'cargo-home').mkdir()
            build = side / 'cmake'
            env = environment(plan, role)
            snapshot_path = side / 'build-inputs.json'
            provenance = [sys.executable, str(Path(bp.__file__).resolve())]
            def probe(phase):
                args = provenance + [phase, '--source-root', str(ROOT)]
                if phase == 'begin':
                    args += ['--build-dir', str(build)]
                if phase != 'verify':
                    args += ['--snapshot', str(snapshot_path)]
                if phase in ('seal', 'verify'):
                    args += ['--binary', str(side / 'bin/starbound')]
                # Generic provenance invokes native --version probes. Keep
                # those descendants inside the same supervised owned group.
                run(args, ROOT / 'source', env, side / ('provenance-' + phase), plan)
            probe('begin')
            ad.dump(side / 'inputs-before.json', json.loads(snapshot_path.read_text()))
            argv = ad.commands(plan, role)
            run(argv['configure'], ROOT / 'source', env, side / 'configure', plan)
            receipt = ad.configured(plan, pin, build)
            probe('configured')
            snapshot = json.loads(snapshot_path.read_text())
            ad.validate(plan)
            run(argv['build'], ROOT / 'source', env, side / 'compile', plan)
            ad.validate(plan)
            ad.need(ad.check_configured(plan, build) == {k: v for k, v in receipt.items() if k != 'planSha256'},
                    'configuration changed during compilation')
            dependencies = dependency_witness(plan, receipt, snapshot)
            ad.dump(side / 'client-dependencies.json', dependencies)
            binary = side / 'bin/starbound'
            probe('seal')
            proof = json.loads(bp.sidecar(binary).read_text())
            # This separate record supplements, never edits/relabels, generic provenance.
            result = dict(schema=1, backend=role, admission=identity(Path(plan_path).absolute()),
                          admissionSha256=pin, binary=identity(binary), genericProof=identity(bp.sidecar(binary)),
                          configured=identity(side / 'complete-tool-admission.json'),
                          dependencies=identity(side / 'client-dependencies.json'),
                          builder=identity(Path(__file__).resolve()), environment=env,
                          limitations=['compiled input/build binding only; NOT game/emitted-code/runtime qualification'])
            if role == 'candidate':
                result['archive'] = identity(build / 'rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a')
            else:
                ad.need(not (build / 'rust-engine-ffi').exists(), 'reference must not build a Rust aggregate')
                result['archive'] = None
            probe('verify')
            ad.need(proof == json.loads((side / 'provenance-verify.stdout').read_text()),
                    'generic proof changed after build')
            ad.dump(side / 'id-map-build.json', result)
        ad.validate(plan)
        ad.dump(root / 'completion.json', dict(status='ADMITTED_PAIR_BUILT_NOT_GAME_QUALIFIED',
                admissionSha256=pin, backends={r: identity(root / r / 'id-map-build.json') for r in ('reference', 'candidate')}))
    except BaseException as error:
        ad.dump(root / 'failure.json', dict(status='FAILED_NOT_RESUMABLE', error=str(error),
                allocationObservation=getattr(error, 'observation', None), admissionSha256=pin))
        raise
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args(argv)
    if args.check_only:
        read_plan(args.plan, args.sha)
    else:
        build_pair(args.plan, args.sha)


if __name__ == '__main__':
    main()
