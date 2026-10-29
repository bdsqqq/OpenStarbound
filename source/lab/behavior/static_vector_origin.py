"""Deterministic, read-only current30 whole-game origin reader.

No subprocess/version probe, archived SDK restoration, old29 attestations, clock
renewal or producer impersonation. Successful local bindings are not runtime
adoption: the frontend must retain this opaque result exactly with its captures.
"""
import datetime as dt
import importlib.util
import json
import math
import re
import signal
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
SCHEMA = 'static-vector-whole-game-origin-v1'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ad = load('_sv_origin_admission', ROOT / 'source/lab/static-vector-game/game_build_admission.py')
builder = load('_sv_origin_builder', ROOT / 'scripts/build-static-vector-behavior-lab.py')
code = load('_sv_origin_emitted', ROOT / 'source/lab/static-vector-game/game_origin.py')
bp = load('_sv_origin_common', ROOT / 'source/lab/behavior/build_provenance.py')
json_contract = load('_sv_origin_json_types', ROOT / 'source/lab/behavior/static_vector_proof.py')
same_json = json_contract.same_json
need = ad.need
identity = ad.identity


def unique_object(pairs):
    """Ambiguous receipts must not hide an incomplete declaration via last-wins."""
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def read(path):
    path = Path(path)
    if path in ad.controller_outputs():
        need(path.stat().st_size <= ad.controller_limit(path), 'controller JSON exceeds byte limit')
    identity(path)
    value = json.loads(Path(path).read_text(), object_pairs_hook=unique_object)
    need(type(value) is dict, 'JSON object required')
    return value


def bound(record, path):
    need(same_json(record, identity(path)), 'changed physical output binding: ' + str(path))
    return record


def utc(value):
    stamp = dt.datetime.fromisoformat(value)
    need(stamp.tzinfo is not None, 'aware timestamp required')
    return stamp


def phase_protocol(plan, phase, command, receipt, side):
    """Bind the live-guardian protocol as DATA; never launch or renew its clock."""
    limits = builder.phase_output_limits(phase)
    for row in (command, receipt):
        need(same_json(row['phase'], phase) and same_json(row['outputLimits'], limits),
             'exact phase/output limits')
    python = Path(sys.executable).resolve(strict=True)
    need(ad.physical(plan['python']) == str(python), 'current admitted Python')
    launcher = dict(python=identity(python), guardian=identity(builder.GUARDIAN))
    for item in launcher.values():
        need(plan['witness']['files'].get(item['path']) == item['sha256'], 'launcher source witness')
    need(same_json(command['launcher'], launcher) and same_json(receipt['launcher'], launcher),
         'current physical guardian/Python launcher')
    need(same_json(command['guardianSchema'], builder.GUARDIAN_SCHEMA) and
         same_json(command['statusBytes'], builder.STATUS_BYTES), 'bounded guardian protocol')
    launch = command['launchArgv']
    need(type(launch) is list and len(launch) >= 12 and all(type(arg) is str for arg in launch),
         'guardian launch argv strings')
    fd, token = launch[4], launch[6]
    need(re.fullmatch(r'[1-9][0-9]*', fd) is not None and int(fd) > 2 and
         re.fullmatch(r'[0-9a-f]{64}', token) is not None, 'private descriptor/token')
    expected = [str(python), '-B', str(builder.GUARDIAN), '--status-fd', fd, '--token', token,
        '--source-sha', launcher['guardian']['sha256'], '--environment-json',
        json.dumps(command['environment'], sort_keys=True), '--'] + command['argv']
    need(same_json(launch, expected) and same_json(receipt['launchArgv'], expected), 'exact guardian launch')
    bound(receipt['command'], side / (phase + '.command.json'))
    pid = receipt['pid']
    need(type(pid) is int and 0 < pid < 2**31 and type(receipt['pgid']) is int and
         receipt['pgid'] == pid, 'owned guardian process group')
    status_data = json.dumps(receipt['guardianStatus'], sort_keys=True, separators=(',', ':')).encode('utf-8')
    status = builder.guardian_status(status_data, pid, token, launcher['guardian']['sha256'])
    need(same_json(status, receipt['guardianStatus']) and receipt['guardianStatusEOF'] is True and
         type(receipt['guardianStatusBytes']) is int and receipt['guardianStatusBytes'] == len(status_data),
         'complete bounded canonical guardian status')
    need(type(receipt['commandPID']) is int and receipt['commandPID'] == status['commandPID'] and
         status['commandReaped'] is True and receipt['commandReaped'] is True and
         type(status['returncode']) is int and status['returncode'] == 0 and
         type(receipt['returncode']) is int and receipt['returncode'] == 0, 'successful reaped actual command')
    need(type(receipt['guardianReturncode']) is int and receipt['guardianReturncode'] == -signal.SIGKILL and
         receipt['reaped'] is True and receipt['guardianReaped'] is True and
         receipt['reapedScope'] == 'DIRECT_GUARDIAN_ONLY', 'live guardian killed and directly reaped')
    need(receipt['outputComplete'] is True and receipt['failure'] is None and receipt['cleanupFailure'] is None,
         'incomplete/failed phase cannot qualify')
    need(type(receipt['streams']) is dict and set(receipt['streams']) == {'stdout', 'stderr'}, 'exact streams')
    outputs = {}
    for name in ('stdout', 'stderr'):
        path = side / (phase + '.' + name)
        # Bound physical size BEFORE identity() hashes bytes or trusting counts.
        ad.no_symlink_parents(path)
        need(path.is_file() and path.resolve(strict=True) == path and
             path.stat().st_size <= limits[name + 'Bytes'], 'bounded physical raw stream')
        row = receipt['streams'][name]
        need(type(row) is dict and set(row) == {'bytesRead', 'bytesWritten', 'eof', 'overflow'}, 'exact stream fields')
        need(all(type(row[key]) is int and row[key] >= 0 for key in ('bytesRead', 'bytesWritten')) and
             row['bytesRead'] == row['bytesWritten'] == path.stat().st_size and
             row['eof'] is True and row['overflow'] is None, 'complete exact raw byte counts')
        outputs[name] = identity(path)
    return outputs


def phase_bindings(plan, role, record):
    """Validate recorded original-window execution, not reader wall clock."""
    side = Path(plan['buildRoot']) / role
    phases = builder.phases(role)
    need(same_json(record['phases'], list(phases)), 'exact six/reference seven/candidate phases')
    need(not any(side.glob('*-overflow.bin')), 'successful role has overflow artifacts')
    for suffix in ('.command.json', '.receipt.json'):
        need({p.name for p in side.glob('*' + suffix)} == {p + suffix for p in phases}, 'missing/extra supervised phase')
    previous = utc(plan['createdUTC'])
    end = previous + dt.timedelta(seconds=ad.DEADLINES['maxAgeSeconds'])
    inputs = code.sha(json.dumps(plan['witness'], sort_keys=True).encode())
    result = {}
    for phase in phases:
        command = read(side / (phase + '.command.json'))
        receipt = read(side / (phase + '.receipt.json'))
        start, finish = utc(command['startedUTC']), utc(receipt['finishedUTC'])
        need(previous <= start <= finish <= end, 'phase outside original clock/order: ' + phase)
        previous = finish
        need(same_json(command['argv'], builder.phase_command(plan, role, phase)) and
             same_json(receipt['argv'], command['argv']), 'exact expanded phase command')
        need(command['cwd'] == str(ROOT / 'source') and
             same_json(command['environment'], builder.environment(plan, role)) and
             same_json(record['environment'], command['environment']), 'phase environment/cwd')
        need(command['inputsSha256'] == inputs, 'before-phase admitted input witness')
        outputs = phase_protocol(plan, phase, command, receipt, side)
        elapsed = receipt['elapsedSeconds']
        need(type(elapsed) in (float, int) and math.isfinite(elapsed) and 0 <= elapsed <= ad.DEADLINES['maxAgeSeconds'], 'invalid elapsed time')
        result[phase] = dict(command=identity(side / (phase + '.command.json')),
            receipt=identity(side / (phase + '.receipt.json')), **outputs)
    if role == 'candidate':
        seal = record['archive']
        cargo_end = utc(read(side / 'cargo.receipt.json')['finishedUTC'])
        compile_start = utc(read(side / 'compile.command.json')['startedUTC'])
        need(cargo_end <= utc(seal['sealedUTC']) <= compile_start, 'archive MUST be physically sealed before native link phase')
    return result


def common_proof(plan, role, proof):
    side = Path(plan['buildRoot']) / role
    binary, build = side / 'bin/starbound', side / 'cmake'
    need(proof['schema'] == bp.SCHEMA and proof['source_root'] == str(ROOT) and
         proof['build_dir'] == str(build) and proof['binary'] == str(binary) and
         proof['binary_sha256'] == ad.sha(binary), 'common provenance schema/path/binary')
    # These functions read current sources/configuration only, not --version.
    bp._check_sources(proof['source_files'], ROOT)
    need(proof['compile_source_files'] == bp._compile_source_inputs(build), 'current complete compiled source inputs')
    cache_text = (build / 'CMakeCache.txt').read_text()
    ad.config.validate_cache(role, cache_text)
    cache = {}
    for line in cache_text.splitlines():
        if not line or line.startswith(('#', '//')) or '=' not in line or ':' not in line.partition('=')[0]:
            continue
        key_type, value = line.split('=', 1)
        key = key_type.split(':', 1)[0]
        if key.startswith(('CMAKE_', 'VCPKG_', 'STAR_')):
            cache[key] = value
    build_identity = proof['build_identity']
    need(build_identity['kind'] == 'cmake' and build_identity['cache'] == cache and
         {k: v for k, v in cache.items() if k.startswith('STAR_USE_RUST_')} == ad.profiles()[role], 'common all30 exact cache binding')
    need(build_identity['files'] == {str(build / name): ad.sha(build / name) for name in
             ('CMakeCache.txt', 'build.ninja', 'compile_commands.json')}, 'common configured files')
    tool_keys = ('CMAKE_COMMAND', 'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_MAKE_PROGRAM',
                 'CMAKE_AR', 'CMAKE_RANLIB', 'CMAKE_TOOLCHAIN_FILE', 'STAR_CARGO_EXECUTABLE', 'STAR_RUSTC_EXECUTABLE')
    need(set(build_identity['tools']) == {k for k in tool_keys if cache.get(k)}, 'complete generic tool membership')
    for key, tool in build_identity['tools'].items():
        path = cache[key]
        need(tool['path'] == path and tool['sha256'] == ad.sha(path) and
             plan['witness']['files'].get(ad.physical(path)) == ad.sha(path), 'current tool bytes and admitted identity')
    snapshot = read(side / 'build-inputs.json')
    for key in ('schema', 'source_root', 'source_files', 'build_dir', 'compile_source_files', 'build_identity'):
        need(proof[key] == snapshot[key], 'snapshot/common proof mismatch: ' + key)
    before = read(side / 'inputs-before.json')
    need(before == {key: snapshot[key] for key in ('schema', 'source_root', 'source_files', 'build_dir')}, 'before configure source binding')
    recorded = dict(proof)
    recorded.pop('gameOrigin')
    need(recorded == read(side / 'provenance-verify.stdout'), 'common verified proof changed')
    return dict(before=identity(side / 'inputs-before.json'), snapshot=identity(side / 'build-inputs.json'))


def role_binding(plan, role, record, proof):
    side = Path(plan['buildRoot']) / role
    need(record['schema'] == SCHEMA and record['role'] == role and same_json(proof['gameOrigin'], record), 'opaque record/role/schema mismatch')
    bound(record['binary'], side / 'bin/starbound')
    bound(record['builder'], ROOT / 'scripts/build-static-vector-behavior-lab.py')
    bound(record['configured'], side / 'complete-tool-admission.json')
    bound(record['dependencies'], side / 'dependencies.json')
    configured = read(side / 'complete-tool-admission.json')
    need(configured.pop('planSha256') == record['admission']['sha256'], 'configured admission digest')
    need(configured == ad.check_configured(plan, side / 'cmake'), 'current configured consumer inputs')
    common = common_proof(plan, role, proof)
    deps = builder.dependency_witness(plan, configured, proof)
    # Numeric dependency IDs must not accept JSON booleans/floats via Python ==.
    need(same_json(deps, read(side / 'dependencies.json')), 'actual compiler/SDK dependencies drift')
    commands = phase_bindings(plan, role, record)
    seal = record['archive']
    link = builder.link_closure(plan, role, deps, seal)
    need(same_json(record['link'], link), 'actual complete link closure drift')
    binary = side / 'bin/starbound'
    need(binary.stat().st_size <= code.MAX_INPUT_BYTES, 'bounded native game')
    if role == 'candidate':
        archive = side / 'cmake' / ad.ARCHIVE
        bound(seal['identity'], archive)
        need(seal['fileState'] == ad.file_state(archive), 'prelink archive physical identity changed')
        need(seal == read(side / 'prelink-archive.json') and seal['physical'] == code.seal_archive(archive.read_bytes()), 'actual canonical prelink archive drift')
        need(seal['cargo'] == read(side / 'cargo-expanded.json') == builder.cargo_command(plan, side / 'cmake'), 'fresh actual Cargo source/tool/argv proof')
        world = Path(configured['objects']['world']['object'])
        emitted = code.attest(binary.read_bytes(), archive.read_bytes(), world.read_bytes(),
            map_data=(side / 'link.map').read_bytes(), physical_objects=builder.link_object_bytes(link))
    else:
        need(seal is None, 'reference aggregate excluded')
        image = code.MachO(binary.read_bytes())
        need(image.kind == 2 and not any(s['name'] in code.NAMES[:4] for s in image.symbols), 'reference native-only exports')
        emitted = dict(status='NO_RUST', game_sha256=ad.sha(binary))
    return dict(record=identity(side / 'static-vector-build.json'), binary=record['binary'],
                compiledSources=proof['compile_source_files'], dependencies=record['dependencies'],
                common=common, commands=commands, link=link, emittedCode=emitted)


def validate_game_origin(executable: Path, proof: dict) -> dict:
    """Return nonempty deterministic opaque bindings, or raise; NEVER launch."""
    executable = Path(executable)
    identity(executable)
    side, root = executable.parent.parent, executable.parent.parent.parent
    need(root == ad.build_root() and side.name in ad.profiles() and executable == root / side.name / 'bin/starbound', 'exact current owned role binary')
    need(not any((p / 'failure.json').exists() for p in (root, root / 'reference', root / 'candidate')), 'failed generation cannot qualify')
    need(proof == read(bp.sidecar(executable)), 'supplied proof must equal physical sidecar')
    completion = read(root / 'completion.json')
    need(completion['schema'] == SCHEMA and completion['status'] == 'BUILT_NOT_GAME_QUALIFIED' and set(completion['backends']) == set(ad.profiles()), 'exact successful pair completion')
    records, proofs = {}, {}
    for role in ad.profiles():
        path = root / role / 'static-vector-build.json'
        bound(completion['backends'][role], path)
        records[role] = read(path)
        proofs[role] = read(bp.sidecar(root / role / 'bin/starbound'))
    admission = records[side.name]['admission']
    bound(admission, Path(admission['path']))
    need(Path(admission['path']) == root / 'current30-admission/plan.json' and
         admission['sha256'] == completion['admissionSha256'] and
         all(record['admission'] == admission for record in records.values()), 'common admission pin inside G')
    plan = read(admission['path'])
    ad.static_plan(plan)  # No current-age gate: only original receipt clock matters.
    need(plan['retention'] == identity(plan['retention']['path']) and read(plan['retention']['path']) == plan['retentionForecast'], 'parent product conservation cost proof changed')
    backends = {role: role_binding(plan, role, records[role], proofs[role]) for role in ad.profiles()}
    reference_end = utc(read(root / 'reference/provenance-verify.receipt.json')['finishedUTC'])
    candidate_start = utc(read(root / 'candidate/provenance-begin.command.json')['startedUTC'])
    need(reference_end <= candidate_start, 'pair original execution order')
    ad.unchanged(plan['witness'])
    return dict(schema=SCHEMA, role=side.name, admission=admission, completion=identity(root / 'completion.json'),
        backends=backends, currentInputs=code.sha(json.dumps(plan['witness'], sort_keys=True).encode()),
        validator=identity(Path(__file__).resolve()), limitations=[
            'local current-byte/recorded-command binding; not signed historical attestation',
            'before/after witnesses cannot detect intervening reverted edits',
            'encoded native edges are NOT runtime TLS/callsite adoption or game qualification',
            'unavailable/archived source/tool/SDK/member origins fail closed'])
