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
import secrets
import selectors
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
physical = load('_sv_physical_link_map', ROOT / 'source/lab/static-vector-game/physical_link_map.py')
# This Make grammar is context-independent; it never invokes old build_pair.
make_rule = load('_sv_dep_grammar', ROOT / 'scripts/build-id-map-behavior-lab.py').make_rule
PHASES = ad.PHASES
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
    argv = [plan['python'], str(ROOT / 'source/lab/static-vector-game/provenance.py'), action, '--source-root', str(ROOT)]
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


def phase_output_limits(phase):
    ad.need(phase in PHASES, 'undeclared phase')
    return dict(stdoutBytes=(64 if phase in ('provenance-seal', 'provenance-verify') else 8) * 1024**2,
                stderrBytes=2 * 1024**2, readChunkBytes=65536, overflowBytes=65536)


def pair_phase_output_bound():
    """only the 13 known phase logs and their overflow evidence, not other artifacts."""
    return sum(limits['stdoutBytes'] + limits['stderrBytes'] + 2 * limits['overflowBytes']
               for role in ('reference', 'candidate') for phase in phases(role)
               for limits in (phase_output_limits(phase),))


GUARDIAN = ROOT / 'scripts/static-vector-phase-guardian.py'
GUARDIAN_SCHEMA = 'static-vector-phase-guardian-v1'
STATUS_BYTES = 4096


def guardian_status(data, pid, token, source_sha):
    ad.need(0 < len(data) <= STATUS_BYTES, 'guardian status size')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            ad.need(key not in result, 'duplicate guardian status key')
            result[key] = value
        return result

    text = data.decode('utf-8')
    row, end = json.JSONDecoder(object_pairs_hook=unique).raw_decode(text)
    ad.need(end == len(text), 'trailing guardian status bytes')
    keys = {'schema', 'token', 'sourceSha256', 'guardianPID', 'guardianPGID', 'guardianSID',
            'commandPID', 'returncode', 'commandReaped', 'launchError'}
    ad.need(type(row) is dict and set(row) == keys, 'guardian status schema keys')
    ad.need(row['schema'] == GUARDIAN_SCHEMA and row['token'] == token
            and row['sourceSha256'] == source_sha, 'guardian status identity')
    ad.need(all(type(row[key]) is int and row[key] == pid
                for key in ('guardianPID', 'guardianPGID', 'guardianSID')), 'guardian session identity')
    child = row['commandPID']
    ad.need(child is None or (type(child) is int and 0 < child < 2**31 and child != pid), 'guardian command pid')
    ad.need(type(row['commandReaped']) is bool, 'guardian command reaping type')
    error = row['launchError']
    ad.need(error is None or (type(error) is str and 0 < len(error.encode('utf-8')) <= 512), 'guardian error bound')
    if row['commandReaped']:
        ad.need(child is not None and type(row['returncode']) is int and error is None, 'guardian completed command')
    else:
        ad.need(row['returncode'] is None and error is not None, 'guardian failed command')
    return row


def supervise(argv, cwd, env, output, plan):
    """bounded raw-byte capture; overflow is retained evidence, never a qualified pass."""
    phase = output.name
    limits = phase_output_limits(phase)
    # Reject undeclared locations before even creating raw capture files.
    for suffix in ('.command.json', '.receipt.json'):
        ad.controller_limit(output.with_suffix(suffix))
    ad.validate(plan)
    python = Path(sys.executable).resolve(strict=True)
    ad.need(Path(plan.get('python', str(python))).resolve(strict=True) == python, 'guardian trusted Python mismatch')
    _supervise_command(argv, cwd, env, output, limits=limits,
        validate=lambda: ad.validate(plan), remaining_seconds=lambda: remaining(plan),
        python=python, witness=plan['witness'], write_record=ad.dump,
        check_output=lambda path: ad.controller_limit(path)
            if path.name.endswith(('.command.json', '.receipt.json')) else None)


def _supervise_command(argv, cwd, env, output, *, limits, validate,
                       remaining_seconds, python, witness, write_record,
                       check_output, scope=None):
    """Owned guardian/capture mechanism; callers supply their own admission clock.

    A successful return follows cleanup and durable receipt publication. Failure
    reaps the direct guardian but never invents missing command-reaping evidence.
    """
    phase = output.name
    for suffix in ('.command.json', '.receipt.json'):
        check_output(output.with_suffix(suffix))
    extra = {} if scope is None else {'scope': scope}
    launcher = dict(python=identity(python), guardian=identity(GUARDIAN))
    token = secrets.token_hex(32)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    start = time.monotonic()
    proc, selector, status_pipe, status_write = None, None, None, None
    status_data, status, status_eof, status_bytes_read = bytearray(), None, False, 0
    launch_argv, command_record = None, None
    streams, files = {}, {}
    failure, complete, reaped, group_stopped = None, False, False, False
    counts = {name: dict(bytesRead=0, bytesWritten=0, eof=False, overflow=None)
              for name in ('stdout', 'stderr')}

    def stop_group(sig):
        # the guardian stays live after its report; never poll/reap it before
        # the final group signal, and never reinterpret EPERM as success.
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass

    try:
        for name in counts:
            path = output.with_suffix('.' + name)
            check_output(path)
            files[name] = path.open('xb')
        remaining_seconds()
        validate()
        status_read, status_write = os.pipe()
        try:
            status_pipe = os.fdopen(status_read, 'rb', buffering=0)
        except BaseException:
            os.close(status_read)
            raise
        launch_argv = [str(python), '-B', str(GUARDIAN), '--status-fd', str(status_write),
                       '--token', token, '--source-sha', launcher['guardian']['sha256'],
                       '--environment-json', json.dumps(env, sort_keys=True), '--'] + list(argv)
        write_record(output.with_suffix('.command.json'), dict(argv=argv, launchArgv=launch_argv,
            launcher=launcher, guardianSchema=GUARDIAN_SCHEMA, statusBytes=STATUS_BYTES,
            cwd=str(cwd), environment=env, phase=phase, outputLimits=limits, startedUTC=started,
            inputsSha256=code.sha(json.dumps(witness, sort_keys=True).encode()), **extra))
        command_record = identity(output.with_suffix('.command.json'))
        ad.need(launcher == dict(python=identity(python), guardian=identity(GUARDIAN)), 'guardian launcher drift')
        proc = subprocess.Popen(launch_argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True, pass_fds=(status_write,))
        streams = dict(stdout=proc.stdout, stderr=proc.stderr)
        os.close(status_write)
        status_write = None
        selector = selectors.DefaultSelector()
        for name, stream in dict(streams, status=status_pipe).items():
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        next_validation = time.monotonic() + 2
        while True:
            left = remaining_seconds()
            ad.need(left > 0, 'original phase deadline expired')
            now = time.monotonic()
            if now >= next_validation:
                validate()
                next_validation = time.monotonic() + 2
            if not group_stopped and status is not None:
                stop_group(signal.SIGKILL)
                group_stopped = True
            if group_stopped and all(row['eof'] for row in counts.values()):
                break
            # pipe EOF alone does not mean command exit; the guardian's private
            # one-shot report is the only command completion barrier.
            delay = min(0.1, left, max(0, next_validation - time.monotonic()))
            for key, _ in selector.select(delay):
                name, stream = key.data, key.fileobj
                try:
                    size = STATUS_BYTES + 1 - len(status_data) if name == 'status' else limits['readChunkBytes']
                    data = os.read(stream.fileno(), size)
                except BlockingIOError:
                    continue
                if name == 'status':
                    if data:
                        status_bytes_read += len(data)
                        ad.need(status_bytes_read <= STATUS_BYTES, 'guardian status size')
                        status_data.extend(data)
                    else:
                        status_eof = True
                        selector.unregister(stream)
                        status = guardian_status(bytes(status_data), proc.pid, token, launcher['guardian']['sha256'])
                    continue
                row = counts[name]
                if not data:
                    row['eof'] = True
                    selector.unregister(stream)
                    continue
                row['bytesRead'] += len(data)
                allowed = max(0, limits[name + 'Bytes'] - row['bytesWritten'])
                prefix = data[:allowed]
                files[name].write(prefix)
                row['bytesWritten'] += len(prefix)
                overflow = data[len(prefix):]
                if overflow:
                    path = output.with_suffix('.' + name + '-overflow.bin')
                    check_output(path)
                    ad.need(len(overflow) <= limits['overflowBytes'], 'overflow evidence bound')
                    with path.open('xb') as evidence:
                        evidence.write(overflow)
                    row['overflow'] = dict(path=str(path), sizeBytes=len(overflow), sha256=code.sha(overflow))
                    raise ValueError('OUTPUT_LIMIT_EXCEEDED')
        for file in files.values():
            file.flush()
        proc.wait()
        reaped = True
        ad.need(status['commandReaped'], 'guardian command launch or wait failed; logs retained')
        ad.need(status['returncode'] == 0, 'native phase failed; logs retained')
        ad.need(proc.returncode == -signal.SIGKILL, 'guardian did not remain live until group cleanup')
        ad.need(launcher == dict(python=identity(python), guardian=identity(GUARDIAN)), 'guardian launcher drift')
        validate()
        complete = True
    except BaseException as exc:
        failure = str(exc) or type(exc).__name__
        raise
    finally:
        try:
            if proc is not None and not reaped:
                # no intermediate TERM: it could retire the live guardian
                # before final cleanup and recreate zombie-only Darwin EPERM.
                # no poll/wait before this last group signal either.
                try:
                    if not group_stopped:
                        stop_group(signal.SIGKILL)
                finally:
                    proc.wait()
                    reaped = True
        finally:
            cleanup_error = None
            if status_write is not None:
                try:
                    os.close(status_write)
                except BaseException as exc:
                    cleanup_error = exc
            for resource in [selector, status_pipe] + list(streams.values()) + list(files.values()):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as exc:
                        if cleanup_error is None:
                            cleanup_error = exc
            raise_cleanup = cleanup_error is not None and failure is None
            if cleanup_error is not None:
                complete = False
                failure = failure or str(cleanup_error) or type(cleanup_error).__name__
            receipt = dict(argv=argv, launchArgv=launch_argv,
                launcher=launcher, command=command_record, phase=phase, guardianStatus=status,
                guardianStatusBytes=status_bytes_read, guardianStatusEOF=status_eof,
                commandPID=status['commandPID'] if status is not None else None,
                commandReaped=status['commandReaped'] if status is not None else False,
                guardianReturncode=proc.returncode if proc is not None else None,
                outputLimits=limits, streams=counts, outputComplete=complete,
                returncode=status['returncode'] if status is not None else None,
                elapsedSeconds=time.monotonic() - start, failure=failure,
                cleanupFailure=str(cleanup_error) if cleanup_error is not None else None,
                pid=proc.pid if proc is not None else None,
                pgid=proc.pid if proc is not None else None, reaped=reaped,
                guardianReaped=reaped, reapedScope='DIRECT_GUARDIAN_ONLY',
                finishedUTC=dt.datetime.now(dt.timezone.utc).isoformat(), **extra)
            write_record(output.with_suffix('.receipt.json'), receipt)
            if raise_cleanup:
                raise cleanup_error
    return receipt


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
    Content is captured once per physical path in THIS invocation, with physical
    fingerprints bracketing the hash and checked again at the return barrier.
    Like any before/after witness, this cannot detect restored intervening edits.
    """
    captured = {}

    def fingerprint(path):
        ad.no_symlink_parents(path)
        info = path.stat()
        return tuple(getattr(info, key) for key in
                     ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink'))

    def capture(path):
        if path not in captured:
            before = fingerprint(path)
            record = identity(path)
            ad.need(before == fingerprint(path), 'compile input changed during capture: ' + str(path))
            captured[path] = (record, before)
        return captured[path][0]

    role = configured['role']
    build = Path(plan['buildRoot']) / role / 'cmake'
    expected = dict(plan['witness']['files'])
    expected.update(snapshot['compile_source_files'])
    database = build / 'compile_commands.json'
    capture(database)
    rows = json.loads(database.read_text())
    result, closures, dependencies = {}, {}, set()
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
        ad.need(source == declared and expected.get(str(source)) == capture(source)['sha256'], 'admitted actual compile source')
        dep = Path(str(obj) + '.d')
        dep_identity = capture(dep)
        target, paths = make_rule(dep.read_text())
        target = Path(target) if Path(target).is_absolute() else directory / target
        ad.need(target.resolve(strict=True) == obj, 'actual depfile object mismatch')
        object_identity = capture(obj)
        bindings = set()
        for name in paths:
            path = Path(name) if Path(name).is_absolute() else directory / name
            resolved = path.resolve(strict=True)
            record = capture(resolved)
            ad.need(expected.get(str(resolved)) == record['sha256'], 'unadmitted dependency: ' + str(path))
            ad.need(captured[obj][1][4] >= captured[resolved][1][4], 'dependency newer than object')
            bindings.add(record['path'])  # Share the cached canonical spelling across TU closures.
        ad.need(str(obj) not in result, 'duplicate compiled object')
        ad.need(str(source) in bindings, 'actual compile source missing from dependency rule')
        closures[str(obj)] = bindings
        dependencies.update(bindings)
        result[str(obj)] = dict(object=object_identity, depfile=dep_identity,
                               compileArgv=argv, cwd=str(directory), compiler=capture(Path(argv[0]).resolve(strict=True)))
    required = {
        'client': ['source/client/StarClientApplication.cpp', ad.HEADER],
        'world': ['source/game/StarWorldClient.cpp', 'source/game/StarTileSectorArray.hpp',
                  'source/core/StarTileSectorArrayObserver.hpp', 'source/core/StarStaticVector.hpp']}
    for label, headers in required.items():
        obj = configured['objects'][label]['object']
        ad.need(obj in result, 'missing required compiled consumer')
        deps = closures[obj]
        for header in headers:
            ad.need(str(ROOT / header) in deps, 'missing actual dependency: ' + header)
        abi = str(ROOT / 'source/core/StarRustStaticVector.h')
        host = str(ROOT / 'source/core/StarStaticVectorHost.hpp')
        if label == 'world':
            ad.need((abi in deps) == (role == 'candidate') and (host in deps) == (role == 'candidate'), 'ON-only StaticVector host/ABI closure')
    ad.need(any(Path(path).is_relative_to(Path(plan['sdk']).resolve()) for path in dependencies), 'actual consumed SDK includes required')
    paths = sorted(dependencies)
    indices = {path: index for index, path in enumerate(paths)}
    for obj, bindings in closures.items():
        result[obj]['dependency_ids'] = sorted(indices[path] for path in bindings)
    files = [captured[Path(path)][0] for path in paths]
    # Revisit even inputs last seen in an early TU: cache hits alone are not a
    # stability witness for edits made while later objects are being processed.
    for path, (_, before) in captured.items():
        ad.need(before == fingerprint(path), 'compile input changed before return: ' + str(path))
    return dict(schema='static-vector-compile-dependencies-v2', files=files, objects=result)


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

    Map entries bind physical members, not archive basenames. Duplicate names
    require unique live external-definition witnesses, never first-member order.
    """
    helpers = code.base.helper_identities()
    path = side / 'link.map'
    map_data = path.read_bytes()
    entries = physical.indexed_objects(map_data)
    rows, archives, groups, used_inputs = [], {}, {}, set()
    aggregate = side / 'cmake' / ad.ARCHIVE
    for index, entry in entries.items():
        if entry == b'linker synthesized':
            rows.append(dict(kind='LINKER_SYNTHESIZED', object_index=index, origin_hex=entry.hex()))
            continue
        if entry.endswith(b')') and b'(' in entry:
            raw_path, member_name = entry[:-1].rsplit(b'(', 1)
            library = Path(os.fsdecode(raw_path))
            library = library if library.is_absolute() else side / 'cmake' / library
            library = library.resolve(strict=True)
            if library not in archives:
                library_id = identity(library)
                if library == aggregate:
                    ad.need(seal is not None and seal['identity'] == library_id and seal['fileState'] == ad.file_state(library), 'map aggregate differs from prelink seal')
                elif library.is_relative_to(side / 'cmake'):
                    compiled_library(library, dependencies)
                else:
                    ad.need(plan['witness']['files'].get(str(library)) == library_id['sha256'], 'unadmitted driver/native archive')
                data = library.read_bytes()
                ad.need(code.sha(data) == library_id['sha256'], 'archive changed during map resolution')
                archives[library] = (library_id, data)
            library_id, data = archives[library]
            key = (raw_path, member_name)
            if key not in groups:
                groups[key] = physical.resolve_archive_group(data, map_data, raw_path, member_name)
            member = groups[key][index]
            physical_key = (str(library), member['member_header_offset'])
            ad.need(physical_key not in used_inputs, 'physical archive member repeated through map aliases')
            used_inputs.add(physical_key)
            rows.append(dict(kind='ARCHIVE_MEMBER', object_index=index, archive=library_id, **member))
        else:
            obj = Path(os.fsdecode(entry))
            obj = obj if obj.is_absolute() else side / 'cmake' / obj
            obj = obj.resolve(strict=True)
            ad.need(str(obj) in dependencies['objects'], 'link-map object without actual compile/SDK closure')
            ad.need(str(obj) not in used_inputs, 'physical compiled object repeated through map aliases')
            used_inputs.add(str(obj))
            rows.append(dict(kind='COMPILED_OBJECT', object_index=index, object=identity(obj)))
    return dict(map=identity(path), objects=rows, imported_helper_sha256=helpers)


def link_object_bytes(link):
    """Re-read a rederived link closure; NOT an independent admission API.

    Physical archive identity and header offset are both mandatory: a matching
    member name or body hash alone cannot select a duplicate-name provider.
    """
    result, archives, seen = {}, {}, set()
    for row in link['actualOrigins']['objects']:
        index = row['object_index']
        ad.need(type(index) is int and index >= 0 and index not in seen, 'unique physical map index')
        seen.add(index)
        if row['kind'] == 'LINKER_SYNTHESIZED':
            continue
        if row['kind'] == 'COMPILED_OBJECT':
            record = row['object']
            path = Path(record['path'])
            ad.need(identity(path) == record, 'direct link object identity changed')
            data = path.read_bytes()
            ad.need(code.sha(data) == record['sha256'], 'direct link object bytes changed')
        else:
            ad.need(row['kind'] == 'ARCHIVE_MEMBER', 'unknown physical origin kind')
            record = row['archive']
            path = Path(record['path'])
            if path not in archives:
                ad.need(identity(path) == record, 'physical archive identity changed')
                data = path.read_bytes()
                ad.need(code.sha(data) == record['sha256'], 'physical archive bytes changed')
                archives[path] = (record, {m['offset']: m for m in physical.archive.arm64_archive_members(data)})
            cached, members = archives[path]
            ad.need(cached == record, 'inconsistent archive identity')
            member = members.get(row['member_header_offset'])
            ad.need(member is not None and member['name'].hex() == row['member_name_hex']
                    and member['sha256'] == row['member_sha256'], 'recorded physical archive member changed')
            data = member['body']
        ad.need(physical.generic.MachO(data).kind == 1, 'physical link input must be MH_OBJECT')
        result[index] = data
    return result


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
            original_sidecar = identity(bp.sidecar(binary))
            proof['gameOrigin'] = record
            ad.supplement_sidecar(bp.sidecar(binary), proof, original_sidecar)
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
