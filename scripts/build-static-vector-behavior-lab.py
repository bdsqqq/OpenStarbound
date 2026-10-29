#!/usr/bin/env python3
"""Fresh current30 pair builder; source API only until parent admits real inputs.

Candidate phases: begin/configure/configured/CARGO+PRELINK-SEAL/compile/seal/verify.
Reference omits Cargo. No combined Cargo/native link phase is permitted. The
archive seal is a synchronous barrier between cargo receipt and native launch.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shlex
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


ad = load('_sv_builder_admission', ROOT / 'source/lab/static-vector-game/game_build_admission.py')
code = load('_sv_builder_code', ROOT / 'source/lab/static-vector-game/game_origin.py')
bp = load('_sv_common_provenance', ROOT / 'source/lab/behavior/build_provenance.py')
# This Make grammar is context-independent; it never invokes old build_pair.
make_rule = load('_sv_dep_grammar', ROOT / 'scripts/build-id-map-behavior-lab.py').make_rule
PHASES = ('provenance-begin', 'configure', 'provenance-configured', 'cargo', 'compile', 'provenance-seal', 'provenance-verify')
SCHEMA = 'static-vector-whole-game-origin-v1'
identity = ad.identity


def phases(role):
    ad.need(role in ad.profiles(), 'exact backend')
    return tuple(p for p in PHASES if p != 'cargo' or role == 'candidate')


def environment(plan, role):
    home = pwd.getpwuid(os.getuid()).pw_dir
    return dict(HOME=home, PATH='/usr/bin:/bin', SDKROOT=plan['sdk'],
        VCPKG_ROOT=home + '/.cache/openstarbound-vcpkg',
        CARGO_HOME=str(Path(plan['buildRoot']) / role / 'cargo-home'),
        TMPDIR=str(Path(plan['buildRoot']) / role / 'tmp'))


def phase_command(plan, role, phase):
    side = Path(plan['buildRoot']) / role
    ad.need(phase in phases(role), 'undeclared phase')
    if phase in ('configure', 'cargo', 'compile'):
        return ad.commands(plan, role)[{'configure': 'configure', 'cargo': 'cargo', 'compile': 'build'}[phase]]
    action = phase.removeprefix('provenance-')
    argv = [plan['python'], str(ROOT / 'source/lab/behavior/build_provenance.py'), action, '--source-root', str(ROOT)]
    if action == 'begin':
        argv += ['--build-dir', str(side / 'cmake')]
    if action != 'verify':
        argv += ['--snapshot', str(side / 'build-inputs.json')]
    if action in ('seal', 'verify'):
        argv += ['--binary', str(side / 'bin/starbound')]
    return argv


def remaining(plan):
    ad.check_deadline(plan)
    return (dt.datetime.fromisoformat(plan['createdUTC']) + dt.timedelta(seconds=ad.DEADLINES['maxAgeSeconds']) - dt.datetime.now(dt.timezone.utc)).total_seconds()


def supervise(argv, cwd, env, output, plan):
    """Owned PGID, original clock, complete reaping, immutable failures."""
    ad.validate(plan)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    ad.dump(output.with_suffix('.command.json'), dict(argv=argv, cwd=str(cwd), environment=env,
            startedUTC=started, inputsSha256=code.sha(json.dumps(plan['witness'], sort_keys=True).encode())))
    start = time.monotonic()
    with output.with_suffix('.stdout').open('xb') as stdout, output.with_suffix('.stderr').open('xb') as stderr:
        remaining(plan)
        ad.validate(plan)
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        failure = None
        try:
            while True:
                try:
                    proc.wait(timeout=min(2, remaining(plan)))
                    break
                except subprocess.TimeoutExpired:
                    ad.validate(plan)
        except BaseException as exc:
            failure = str(exc)
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=min(3, max(0.001, remaining(plan))))
            except (subprocess.TimeoutExpired, ValueError):
                pass
            raise
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            ad.dump(output.with_suffix('.receipt.json'), dict(argv=argv, returncode=proc.returncode,
                elapsedSeconds=time.monotonic() - start, failure=failure, pid=proc.pid, pgid=proc.pid,
                reaped=True, finishedUTC=dt.datetime.now(dt.timezone.utc).isoformat()))
    ad.need(proc.returncode == 0, 'native phase failed; logs retained')
    ad.validate(plan)


def cargo_command(plan, build):
    """Bind the actual evaluated Ninja custom command BEFORE Cargo runs.

    No shell fallback, response file, extra Cargo invocation or seeded target.
    CMake's escaped command is expanded only with shlex, not executed here.
    """
    text = (build / 'build.ninja').read_text().replace('$\n', '')
    lines = [line.partition(' = ')[2] for line in text.splitlines()
             if line.startswith('  COMMAND = ') and '--package star-engine-ffi' in line]
    ad.need(len(lines) == 1, 'unique evaluated aggregate Cargo command')
    words = shlex.split(lines[0])
    ad.need('&&' in words and words[:1] == ['cd'], 'known CMake command working directory')
    split = words.index('&&')
    ad.need(split == 2 and Path(words[1]) == build, 'Cargo working directory')
    argv = words[split + 1:]
    expected = [plan['tools']['CMAKE_EXECUTABLE'], '-E', 'env', 'CARGO_TARGET_DIR=' + str(build / 'rust-engine-ffi'),
        'RUSTC=' + plan['tools']['STAR_RUSTC_EXECUTABLE'], plan['tools']['STAR_CARGO_EXECUTABLE'],
        'build', '--manifest-path', str(ROOT / 'source/rust/Cargo.toml'), '--package', 'star-engine-ffi',
        '--target', 'aarch64-apple-darwin', '--release', '--locked', '--offline']
    ad.need(argv == expected, 'expanded actual Cargo argv mismatch')
    return dict(argv=argv, cwd=str(build), ninja=identity(build / 'build.ninja'),
                rustSources={p: h for p, h in plan['witness']['files'].items() if Path(p).is_relative_to(ROOT / 'source/rust')})


def dependency_witness(plan, configured, snapshot):
    """All compiled TUs, plus required actual WorldClient/client header closure.

    SDK includes must be admitted physical members; neither basename matching nor
    a blanket SDK exemption is allowed. The runtime callsite relation is separate.
    """
    role = configured['role']
    build = Path(plan['buildRoot']) / role / 'cmake'
    expected = dict(plan['witness']['files'])
    expected.update(snapshot['compile_source_files'])
    rows = json.loads((build / 'compile_commands.json').read_text())
    result = {}
    for row in rows:
        argv = row.get('arguments') or shlex.split(row['command'])
        ad.need(argv.count('-o') == 1, 'one compile object')
        directory = Path(row['directory'])
        obj = Path(argv[argv.index('-o') + 1])
        obj = obj if obj.is_absolute() else directory / obj
        ad.no_symlink_parents(obj)
        obj = obj.resolve(strict=False)
        ad.need(obj.is_relative_to(build), 'scoped compile object')
        # The database includes server/CLI targets not requested by starbound.
        # Observe produced objects only; required consumers and every actual
        # link-map object are checked separately, so missing inputs cannot hide.
        if not obj.exists():
            continue
        ad.need(argv.count('-c') == 1 and all(not word.startswith('@') for word in argv), 'one expanded actual compile input')
        ad.need(argv[0] in (plan['tools']['CMAKE_C_COMPILER'], plan['tools']['CMAKE_CXX_COMPILER']), 'admitted actual compile tool')
        source = Path(argv[argv.index('-c') + 1])
        source = (source if source.is_absolute() else directory / source).resolve(strict=True)
        declared = Path(row['file'])
        declared = (declared if declared.is_absolute() else directory / declared).resolve(strict=True)
        ad.need(source == declared and expected.get(str(source)) == ad.sha(source), 'admitted actual compile source')
        dep = Path(str(obj) + '.d')
        target, paths = make_rule(dep.read_text())
        target = Path(target) if Path(target).is_absolute() else directory / target
        ad.need(target.resolve(strict=True) == obj, 'actual depfile object mismatch')
        bindings = {}
        for name in paths:
            path = Path(name) if Path(name).is_absolute() else directory / name
            resolved = path.resolve(strict=True)
            ad.need(expected.get(str(resolved)) == ad.sha(resolved), 'unadmitted dependency: ' + str(path))
            ad.need(obj.stat().st_mtime_ns >= resolved.stat().st_mtime_ns, 'dependency newer than object')
            bindings[str(resolved)] = identity(resolved)
        ad.need(str(obj) not in result, 'duplicate compiled object')
        ad.need(str(source) in bindings, 'actual compile source missing from dependency rule')
        result[str(obj)] = dict(object=identity(obj), depfile=identity(dep), dependencies=bindings,
                               compileArgv=argv, cwd=str(directory), compiler=identity(Path(argv[0]).resolve(strict=True)))
    required = {
        'client': ['source/client/StarClientApplication.cpp', ad.HEADER],
        'world': ['source/game/StarWorldClient.cpp', 'source/game/StarTileSectorArray.hpp',
                  'source/core/StarTileSectorArrayObserver.hpp', 'source/core/StarStaticVector.hpp']}
    for label, headers in required.items():
        obj = configured['objects'][label]['object']
        ad.need(obj in result, 'missing required compiled consumer')
        deps = result[obj]['dependencies']
        for header in headers:
            ad.need(str(ROOT / header) in deps, 'missing actual dependency: ' + header)
        abi = str(ROOT / 'source/core/StarRustStaticVector.h')
        host = str(ROOT / 'source/core/StarStaticVectorHost.hpp')
        if label == 'world':
            ad.need((abi in deps) == (role == 'candidate') and (host in deps) == (role == 'candidate'), 'ON-only StaticVector host/ABI closure')
    ad.need(any(Path(path).is_relative_to(Path(plan['sdk']).resolve()) for row in result.values() for path in row['dependencies']), 'actual consumed SDK includes required')
    return dict(schema='static-vector-compile-dependencies-v1', objects=result)


def compiled_library(path, dependencies):
    """Bind EVERY physical native archive object to an observed compiled TU.

    Symbol tables are archive metadata; no other unrecognized member is waived.
    Duplicate byte-identical native inputs are ambiguous and block this reader.
    """
    objects = {}
    for record in dependencies['objects'].values():
        objects.setdefault(record['object']['sha256'], []).append(record['object'])
    members = code.archive_identity.members(path.read_bytes())
    result = []
    for member in members:
        if member['name'] in (b'__.SYMDEF', b'__.SYMDEF SORTED', b'__.SYMDEF_64', b'__.SYMDEF_64 SORTED'):
            continue
        ad.need(member['body'].startswith(b'\xcf\xfa\xed\xfe'), 'unknown native archive member')
        matches = objects.get(member['sha256'], [])
        ad.need(len(matches) == 1, 'unique compiled TU for every physical native archive member')
        result.append(dict(member_header_offset=member['offset'], member_name_hex=member['name'].hex(),
                           member_sha256=member['sha256'], object=matches[0]))
    ad.need(result, 'nonempty compiled native library')
    return result


def link_map_closure(plan, side, dependencies, seal):
    """Resolve actual linker object origins, including driver-injected archives.

    Map entries bind physical members, not archive basenames. Duplicate named
    members remain ambiguous and block; no member is assigned after the fact.
    """
    helpers = code.base.helper_identities()
    path = side / 'link.map'
    entries = code.archive_identity.link_map_objects(path.read_bytes())
    rows = []
    aggregate = side / 'cmake' / ad.ARCHIVE
    for entry in entries:
        if entry == b'linker synthesized':
            rows.append(dict(kind='LINKER_SYNTHESIZED', origin_hex=entry.hex()))
            continue
        if entry.endswith(b')') and b'(' in entry:
            raw_path, member_name = entry[:-1].rsplit(b'(', 1)
            library = Path(os.fsdecode(raw_path))
            library = library if library.is_absolute() else side / 'cmake' / library
            library = library.resolve(strict=True)
            library_id = identity(library)
            if library == aggregate:
                ad.need(seal is not None and seal['identity'] == library_id and seal['fileState'] == ad.file_state(library), 'map aggregate differs from prelink seal')
            elif library.is_relative_to(side / 'cmake'):
                compiled_library(library, dependencies)
            else:
                ad.need(plan['witness']['files'].get(str(library)) == library_id['sha256'], 'unadmitted driver/native archive')
            members = code.archive_identity.arm64_archive_members(library.read_bytes())
            matches = [m for m in members if m['name'] == member_name]
            ad.need(len(matches) == 1, 'unique actual link-map physical archive member required')
            member = matches[0]
            rows.append(dict(kind='ARCHIVE_MEMBER', archive=library_id, member_header_offset=member['offset'],
                member_name_hex=member_name.hex(), member_sha256=member['sha256']))
        else:
            obj = Path(os.fsdecode(entry))
            obj = obj if obj.is_absolute() else side / 'cmake' / obj
            obj = obj.resolve(strict=True)
            ad.need(str(obj) in dependencies['objects'], 'link-map object without actual compile/SDK closure')
            rows.append(dict(kind='COMPILED_OBJECT', object=identity(obj)))
    return dict(map=identity(path), objects=rows, imported_helper_sha256=helpers)


def link_closure(plan, role, dependencies, seal):
    """Fail closed unless every evaluated native link object has a dep witness."""
    side = Path(plan['buildRoot']) / role
    text = (side / 'cmake/build.ninja').read_text().replace('$\n', '')
    blocks = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('build ') and str(side / 'bin/starbound') in line and 'EXECUTABLE_LINKER' in line:
            body = []
            for following in lines[i + 1:]:
                if not following.startswith('  '):
                    break
                body.append(following)
            blocks.append((line, body))
    ad.need(len(blocks) == 1, 'unique evaluated game link block')
    line, body = blocks[0]
    tokens = shlex.split(line.replace('$ ', '\\ ').split(': ', 1)[1])
    objects = [str((side / 'cmake' / word).resolve(strict=True)) if not Path(word).is_absolute() else word for word in tokens if word.endswith('.o')]
    ad.need(objects and all(obj in dependencies['objects'] for obj in objects), 'complete direct link object/dependency closure required')
    libraries = [v.partition(' = ')[2] for v in body if v.startswith('  LINK_LIBRARIES = ')]
    ad.need(len(libraries) == 1, 'evaluated link libraries')
    archive = side / 'cmake' / ad.ARCHIVE
    aggregate = [word for word in shlex.split(libraries[0]) if 'libstar_engine_ffi' in word]
    if role == 'candidate':
        ad.need(len(aggregate) == 1 and (side / 'cmake' / aggregate[0]).resolve(strict=True) == archive and seal['identity'] == identity(archive), 'exact prelink canonical archive')
    else:
        ad.need(not aggregate and seal is None and not (side / 'cmake/rust-engine-ffi').exists(), 'reference aggregate excluded')
    # Every physical native library must also be bound; object archives are not
    # silently treated as source. Further library closure is a qualification gate.
    libs = {}
    for word in shlex.split(libraries[0]):
        if word.endswith(('.a', '.dylib')):
            path = Path(word) if Path(word).is_absolute() else side / 'cmake' / word
            path = path.resolve(strict=True)
            if path == archive:
                ad.need(seal['identity'] == identity(path) and seal['fileState'] == ad.file_state(path), 'prelink archive was rewritten during native build')
                libs[str(path)] = dict(identity=identity(path), origin='PRELINK_CARGO_SEAL')
            elif path.is_relative_to(side / 'cmake'):
                ad.need(path.suffix == '.a', 'generated dynamic library requires a separate origin contract')
                libs[str(path)] = dict(identity=identity(path), members=compiled_library(path, dependencies))
            else:
                ad.need(plan['witness']['files'].get(str(path)) == ad.sha(path), 'unadmitted native link library')
                libs[str(path)] = dict(identity=identity(path), origin='ADMITTED_CURRENT_NATIVE_INPUT')
    return dict(linkBlockSha256=code.sha((line + '\n' + '\n'.join(body)).encode()), objects=objects, libraries=libs,
                actualOrigins=link_map_closure(plan, side, dependencies, seal))


def build_pair(plan_path, pin, run=supervise):
    plan_path = Path(plan_path).absolute()
    ad.need(ad.sha(plan_path) == pin, 'external admission plan pin')
    plan = json.loads(plan_path.read_text())
    root = ad.validate(plan)
    ad.need(not any(os.path.lexists(root / r) for r in ad.profiles()), 'fresh roles; no resuming failed build')
    try:
        for role in ('reference', 'candidate'):
            side = root / role
            side.mkdir(); (side / 'tmp').mkdir(); (side / 'cargo-home').mkdir()
            env = environment(plan, role)
            configured = None
            seal = None
            for phase in phases(role):
                ad.validate(plan)
                if phase == 'cargo':
                    ad.need(not (side / 'cmake/rust-engine-ffi').exists() and not (side / 'bin/starbound').exists(), 'fresh Cargo production required')
                    cargo = cargo_command(plan, side / 'cmake')
                    ad.need(cargo['rustSources'], 'current Rust source closure')
                    ad.dump(side / 'cargo-expanded.json', cargo)
                if phase == 'compile' and role == 'candidate':
                    ad.need(seal is not None and seal['identity'] == identity(side / 'cmake' / ad.ARCHIVE) and seal['fileState'] == ad.file_state(side / 'cmake' / ad.ARCHIVE), 'prelink physical archive barrier')
                    ad.need(cargo_command(plan, side / 'cmake') == cargo, 'Cargo recipe drift before native link')
                run(phase_command(plan, role, phase), ROOT / 'source', env, side / phase, plan)
                ad.validate(plan)
                if phase == 'provenance-begin':
                    ad.dump(side / 'inputs-before.json', json.loads((side / 'build-inputs.json').read_text()))
                if phase == 'configure':
                    configured = ad.configured(plan, pin, side / 'cmake')
                if phase == 'cargo':
                    archive = side / 'cmake' / ad.ARCHIVE
                    seal = dict(identity=identity(archive), fileState=ad.file_state(archive), physical=code.seal_archive(archive.read_bytes()),
                                cargo=cargo, sealedUTC=dt.datetime.now(dt.timezone.utc).isoformat())
                    ad.dump(side / 'prelink-archive.json', seal)
                if phase == 'compile':
                    ad.need(ad.check_configured(plan, side / 'cmake') == {k: v for k, v in configured.items() if k != 'planSha256'}, 'configured source drift')
                    deps = dependency_witness(plan, configured, json.loads((side / 'build-inputs.json').read_text()))
                    ad.dump(side / 'dependencies.json', deps)
                    link = link_closure(plan, role, deps, seal)
            binary = side / 'bin/starbound'
            proof = json.loads(bp.sidecar(binary).read_text())
            ad.need(proof == json.loads((side / 'provenance-verify.stdout').read_text()), 'common proof mismatch')
            record = dict(schema=SCHEMA, role=role, admission=identity(plan_path), binary=identity(binary),
                configured=identity(side / 'complete-tool-admission.json'), dependencies=identity(side / 'dependencies.json'),
                archive=seal, link=link, environment=env, phases=list(phases(role)),
                builder=identity(Path(__file__).resolve()), limitation='built input binding, NOT runtime qualification')
            ad.dump(side / 'static-vector-build.json', record)
            # Supplement the common proof; do not replace its top-level/cache.
            proof['gameOrigin'] = record
            with bp.sidecar(binary).open('w') as stream:
                json.dump(proof, stream, sort_keys=True)
        ad.validate(plan)
        ad.dump(root / 'completion.json', dict(schema=SCHEMA, status='BUILT_NOT_GAME_QUALIFIED', admissionSha256=pin,
                backends={r: identity(root / r / 'static-vector-build.json') for r in ad.profiles()}))
    except BaseException as error:
        ad.dump(root / 'failure.json', dict(status='FAILED_NOT_RESUMABLE', error=str(error), admissionSha256=pin))
        raise
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    args = parser.parse_args()
    build_pair(args.plan, args.sha)


if __name__ == '__main__':
    main()
