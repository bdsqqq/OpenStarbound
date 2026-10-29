"""Deterministic, read-only current30 whole-game origin reader.

No subprocess/version probe, archived SDK restoration, old29 attestations, clock
renewal or producer impersonation. Successful local bindings are not runtime
adoption: the frontend must retain this opaque result exactly with its captures.
"""
import datetime as dt
import importlib.util
import json
import math
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
need = ad.need
identity = ad.identity


def read(path):
    identity(path)
    value = json.loads(Path(path).read_text())
    need(type(value) is dict, 'JSON object required')
    return value


def bound(record, path):
    need(record == identity(path), 'changed physical output binding: ' + str(path))
    return record


def utc(value):
    stamp = dt.datetime.fromisoformat(value)
    need(stamp.tzinfo is not None, 'aware timestamp required')
    return stamp


def phase_bindings(plan, role, record):
    """Validate recorded original-window execution, not reader wall clock."""
    side = Path(plan['buildRoot']) / role
    phases = builder.phases(role)
    need(record['phases'] == list(phases), 'exact six/reference seven/candidate phases')
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
        need(command['argv'] == receipt['argv'] == builder.phase_command(plan, role, phase), 'exact expanded phase command')
        need(command['cwd'] == str(ROOT / 'source') and command['environment'] == record['environment'] == builder.environment(plan, role), 'phase environment/cwd')
        need(command['inputsSha256'] == inputs, 'before-phase admitted input witness')
        need(type(receipt['returncode']) is int and receipt['returncode'] == 0 and receipt['failure'] is None,
             'failed phase cannot qualify')
        need(type(receipt['pid']) is int and receipt['pid'] > 0 and receipt['pgid'] == receipt['pid'] and receipt['reaped'] is True, 'owned reaped process group required')
        elapsed = receipt['elapsedSeconds']
        need(type(elapsed) in (float, int) and math.isfinite(elapsed) and 0 <= elapsed <= ad.DEADLINES['maxAgeSeconds'], 'invalid elapsed time')
        result[phase] = {kind: identity(side / (phase + suffix)) for kind, suffix in
            [('command', '.command.json'), ('receipt', '.receipt.json'), ('stdout', '.stdout'), ('stderr', '.stderr')]}
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
    need(record['schema'] == SCHEMA and record['role'] == role and proof['gameOrigin'] == record, 'opaque record/role/schema mismatch')
    bound(record['binary'], side / 'bin/starbound')
    bound(record['builder'], ROOT / 'scripts/build-static-vector-behavior-lab.py')
    bound(record['configured'], side / 'complete-tool-admission.json')
    bound(record['dependencies'], side / 'dependencies.json')
    configured = read(side / 'complete-tool-admission.json')
    need(configured.pop('planSha256') == record['admission']['sha256'], 'configured admission digest')
    need(configured == ad.check_configured(plan, side / 'cmake'), 'current configured consumer inputs')
    common = common_proof(plan, role, proof)
    deps = builder.dependency_witness(plan, configured, proof)
    need(deps == read(side / 'dependencies.json'), 'actual compiler/SDK dependencies drift')
    commands = phase_bindings(plan, role, record)
    seal = record['archive']
    link = builder.link_closure(plan, role, deps, seal)
    need(record['link'] == link, 'actual complete link closure drift')
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
    need(Path(admission['path']).is_relative_to(root) and admission['sha256'] == completion['admissionSha256'] and
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
