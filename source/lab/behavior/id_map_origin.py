"""Post-build reader for the NEW IdMap pair, never an admission/launch producer.

Only completion commands that actually ran inside the ORIGINAL admission window
are accepted. Reading a completed build later does not renew that window. No
native subprocess (including generic provenance's --version probes) runs here.
Local receipts cannot prove an unreverted historical edit or unique linker choice.
"""
import datetime as dt
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ad = _load('_idmap_origin_admission', ROOT / 'source/lab/id-map-production/game_build_admission.py')
bp = _load('_idmap_origin_provenance', ROOT / 'source/lab/behavior/build_provenance.py')
builder = _load('_idmap_origin_builder', ROOT / 'scripts/build-id-map-behavior-lab.py')
code = _load('_idmap_origin_code', ROOT / 'source/lab/id-map-production/game_origin.py')
need = ad.need
ROLES = ('reference', 'candidate')
PHASES = ('provenance-begin', 'configure', 'provenance-configured', 'compile',
          'provenance-seal', 'provenance-verify')
ARCHIVE = 'rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'
LIMITS = [
    'local current-byte and recorded-command bindings, not signed or reproducible-build attestation',
    'before/after witnesses cannot detect intervening edits reverted before observation',
    'finite emitted-code/static native edge only; not dynamic behavior or whole-machine provenance',
    'normalized page relocation data addresses are NOT full data-object provenance',
    'original admission window is checked on recorded execution, never renewed by this reader',
]


def _path(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute path without traversal required')
    ad.no_symlink_parents(path)
    need(path.resolve(strict=True) == path, 'exact physical path required: ' + str(path))
    return path


def _identity(path):
    path = _path(path)
    need(path.is_file(), 'regular physical file required: ' + str(path))
    return dict(path=str(path), sha256=ad.sha(path), size=path.stat().st_size)


def _read(path):
    _identity(path)
    value = json.loads(Path(path).read_text())
    need(type(value) is dict, 'JSON object required: ' + str(path))
    return value


def _bound(record, path):
    need(record == _identity(path), 'recorded output identity changed: ' + str(path))
    return record


def _utc(value):
    need(isinstance(value, str), 'UTC timestamp string required')
    stamp = dt.datetime.fromisoformat(value)
    need(stamp.tzinfo is not None and stamp.utcoffset() is not None, 'timezone-aware timestamp required')
    return stamp


def _pin(plan, path):
    ad._require_pin(plan['witness'], path, 'post-build current input')


def _static_plan(plan, root):
    # Deliberately do NOT call ad.validate/check_deadline/configured: those
    # pre-execution APIs consult current age and cannot validate completed work.
    need(plan['stage'] == ad.STAGE and plan['scope'] == ad.SCOPE, 'exact new admission stage/scope')
    need(plan['caps'] == ad.CAPS and plan['deadlines'] == ad.DEADLINES, 'fixed caps/deadlines')
    _utc(plan['createdUTC'])
    need(re.fullmatch('[0-9a-f]{40}', plan['sourceCheckpoint']) is not None and
         plan['checkpointRole'] == ad.CHECKPOINT_ROLE, 'BASE_ONLY checkpoint required')
    need(plan['buildRoot'] == str(root) and ad.build_root(plan['generation']) == root,
         'admission generation/path mismatch')
    need(plan['profiles'] == ad.profiles(), 'exact 29-selector profiles')
    ad.check_source_selectors()
    need(plan['toolPlan'] == str(ROOT / ad.TOOL_PLAN) and plan['toolPlanSha256'] == ad.TOOL_PLAN_SHA,
         'original external e890 tool-selection path/pin required')
    tools, sdk = ad.selected_paths(plan['toolPlan'], plan['toolPlanSha256'])
    need(plan['toolPlanRole'] == 'PATH_SELECTION_ONLY; historical admission NOT reused', 'tool-plan role')
    need(plan['tools'] == tools and plan['sdk'] == sdk and plan['sdkPhysical'] == ad.physical(sdk),
         'current tool/SDK selection changed')
    need(plan['commands'] == {r: ad.commands(plan, r) for r in ROLES} and
         plan['configureCwd'] == str(ROOT / 'source'), 'actual new command selection changed')
    need(plan['retirement'] == ad.check_retirement(plan['retirement']['manifest'], plan['retirement']['sha256']),
         'two original products retirement changed')
    roots = ad.source_roots(tools, sdk)
    need(plan['sourceRoots'] == roots, 'complete source/tool/SDK root selection changed')
    members = ad.tree_members(roots)
    need(plan['treeMembers'] == members, 'current source/tool/SDK membership changed')
    ad.check_member_scope(members)
    witness = plan['witness']
    need(type(witness['files']) is dict and bool(witness['files']), 'complete nonempty byte witness required')
    for name, physical in members.items():
        if Path(name).is_file():
            need(physical in witness['files'], 'unhashed source/tool/SDK member: ' + name)
    objects = ad.retained_objects()
    need(len(objects) == 113 and plan['retainedReferenceObjects'] == objects, 'original 113 reference objects required')
    for path in list(tools.values()) + list(map(str, ad.auxiliary_tools())):
        ad.native(path)
        need(witness['aliases'].get(str(path)) == ad.physical(path), 'native tool alias missing')
        _pin(plan, path)
    for path in objects + [plan['toolPlan']] + [r for r in roots if Path(r).is_file()]:
        _pin(plan, path)
    header = ROOT / ad.HEADER
    need(plan['compiledHeader'] == dict(path=str(header), physical=ad.physical(header), sha256=ad.sha(header),
         role='DECLARED_FUTURE_COMPILE_DEPENDENCY; not yet compiled'), 'declared actual scene header changed')
    for path in (header, ROOT / 'scripts/build-id-map-behavior-lab.py',
                 ROOT / 'source/lab/behavior/build_provenance.py',
                 ROOT / 'source/lab/id-map-production/game_build_admission.py',
                 ROOT / 'source/lab/id-map-production/game_origin.py', Path(__file__)):
        _pin(plan, path)
    ad.unchanged(witness)


def _commands(plan, role, record):
    side = Path(plan['buildRoot']) / role
    created = _utc(plan['createdUTC'])
    end = created + dt.timedelta(seconds=ad.DEADLINES['maxAgeSeconds'])
    previous = created
    for suffix in ('.command.json', '.receipt.json'):
        need({p.name for p in side.glob('*' + suffix)} == {phase + suffix for phase in PHASES},
             'exact six supervised phases required')
    python = None
    bindings = {}
    for phase in PHASES:
        command_path = side / (phase + '.command.json')
        receipt_path = side / (phase + '.receipt.json')
        command, receipt = _read(command_path), _read(receipt_path)
        started, finished = _utc(command['startedUTC']), _utc(receipt['finishedUTC'])
        need(previous <= started <= finished <= end, 'command outside original admission window/order: ' + phase)
        previous = finished
        need(type(receipt['returncode']) is int and receipt['returncode'] == 0 and receipt['failure'] is None,
             'unsuccessful supervised phase: ' + phase)
        need(type(receipt['pid']) is int and receipt['pid'] > 0 and
             type(receipt['elapsedSeconds']) in (int, float) and math.isfinite(receipt['elapsedSeconds']) and
             receipt['elapsedSeconds'] >= 0,
             'invalid supervised receipt')
        argv = command['argv']
        need(type(argv) is list and argv and all(isinstance(x, str) for x in argv), 'actual argv required')
        if phase in ('configure', 'compile'):
            expected = ad.commands(plan, role)['configure' if phase == 'configure' else 'build']
        else:
            if python is None:
                python = argv[0]
                ad.native(python)
                need(plan['witness']['aliases'].get(python) == ad.physical(python), 'unadmitted Python alias')
                _pin(plan, python)
            need(argv[0] == python, 'unadmitted Python interpreter switch')
            action = phase.removeprefix('provenance-')
            expected = [python, str(ROOT / 'source/lab/behavior/build_provenance.py'), action,
                        '--source-root', str(ROOT)]
            if action == 'begin':
                expected += ['--build-dir', str(side / 'cmake')]
            if action != 'verify':
                expected += ['--snapshot', str(side / 'build-inputs.json')]
            if action in ('seal', 'verify'):
                expected += ['--binary', str(side / 'bin/starbound')]
        need(argv == expected and receipt['argv'] == argv, 'exact actual phase argv mismatch: ' + phase)
        need(command['cwd'] == str(ROOT / 'source') and
             command['environment'] == builder.environment(plan, role) == record['environment'],
             'sanitized actual environment/cwd mismatch')
        bindings[phase] = dict(command=_identity(command_path), receipt=_identity(receipt_path),
                               stdout=_identity(side / (phase + '.stdout')),
                               stderr=_identity(side / (phase + '.stderr')))
    return bindings


def _generic(plan, side, proof, configured):
    binary, build = side / 'bin/starbound', side / 'cmake'
    need(proof == _read(bp.sidecar(binary)), 'generic binary sidecar differs from supplied proof')
    need(proof['schema'] == bp.SCHEMA and proof['source_root'] == str(ROOT) and
         proof['build_dir'] == str(build) and proof['binary'] == str(binary) and
         proof['binary_sha256'] == ad.sha(binary), 'generic proof path/binary/schema mismatch')
    bp._check_sources(proof['source_files'], ROOT)
    snapshot = _read(side / 'build-inputs.json')
    before = _read(side / 'inputs-before.json')
    need(before == {k: snapshot[k] for k in ('schema', 'source_root', 'source_files', 'build_dir')},
         'before-configure snapshot mismatch')
    for key in ('schema', 'source_root', 'source_files', 'build_dir', 'compile_source_files', 'build_identity'):
        need(snapshot[key] == proof[key], 'configured snapshot/proof mismatch: ' + key)
    need(bp._compile_source_inputs(build) == proof['compile_source_files'], 'current compiled source inputs changed')
    identity = proof['build_identity']
    need(identity['kind'] == 'cmake', 'actual CMake build required')
    files = {str(build / name): ad.sha(build / name) for name in
             ('CMakeCache.txt', 'build.ninja', 'compile_commands.json')}
    need(identity['files'] == files, 'generic configured file identities changed')
    cache = {}
    for line in (build / 'CMakeCache.txt').read_text().splitlines():
        if not line or line.startswith(('#', '//')) or '=' not in line or ':' not in line.split('=', 1)[0]:
            continue
        key_type, value = line.split('=', 1)
        key = key_type.split(':', 1)[0]
        if key.startswith(('CMAKE_', 'VCPKG_', 'STAR_')):
            cache[key] = value
    need(identity['cache'] == cache, 'generic current cache mismatch')
    need({k: v for k, v in cache.items() if k.startswith('STAR_USE_RUST_')} == ad.profiles()[side.name],
         'generic exact 29-selector role mismatch')
    tool_keys = ('CMAKE_COMMAND', 'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_MAKE_PROGRAM',
                 'CMAKE_AR', 'CMAKE_RANLIB', 'CMAKE_TOOLCHAIN_FILE', 'STAR_CARGO_EXECUTABLE', 'STAR_RUSTC_EXECUTABLE')
    need(set(identity['tools']) == {k for k in tool_keys if cache.get(k)}, 'generic tool membership mismatch')
    for key, tool in identity['tools'].items():
        need(tool['path'] == cache[key] and tool['sha256'] == ad.sha(cache[key]), 'generic current tool bytes/path changed')
        _pin(plan, cache[key])
    need(configured == ad.check_configured(plan, build), 'actual configuration receipt differs')
    need(proof == _read(side / 'provenance-verify.stdout'), 'recorded generic verify output differs')
    return dict(snapshot=_identity(side / 'build-inputs.json'), before=_identity(side / 'inputs-before.json'))


def _link_archive(side, archive):
    """Read evaluated Ninja's actual starbound link block, not archive metadata."""
    text = (side / 'cmake/build.ninja').read_text().replace('$\n', '')
    blocks = re.findall(r'^build ([^\n]+): ([^\n]+)\n((?:  [^\n]*\n)*)', text, re.M)
    matches = [(outputs, rule, body) for outputs, rule, body in blocks
               if str(side / 'bin/starbound') in outputs.split()]
    need(len(matches) == 1 and 'EXECUTABLE_LINKER' in matches[0][1], 'unique actual starbound link block required')
    body = matches[0][2]
    rows = re.findall(r'^  LINK_LIBRARIES = (.*)$', body, re.M)
    need(len(rows) == 1, 'one actual LINK_LIBRARIES required')
    # Ninja escapes spaces, colons and dollars; no shell/path resolver fallback.
    tokens = re.findall(r'(?:\$[ $:]|[^ ])+', rows[0])
    tokens = [re.sub(r'\$([ $:])', r'\1', token) for token in tokens]
    aggregates = [token for token in tokens if 'libstar_engine_ffi' in token or 'rust-engine-ffi' in token]
    if archive is None:
        need(not aggregates and 'rust-engine-ffi' not in text and not os.path.lexists(side / 'cmake/rust-engine-ffi'),
             'reference must have no Rust aggregate/target')
    else:
        need(len(aggregates) == 1, 'exactly ONE linked canonical aggregate required')
        linked = Path(aggregates[0])
        linked = linked if linked.is_absolute() else side / 'cmake' / linked
        need('..' not in linked.parts and _path(linked) == archive, 'linked aggregate is not physical canonical archive')
    return dict(linkBlockSha256=code.sha((matches[0][0] + ': ' + matches[0][1] + '\n' + body).encode()),
                linkedArchive=None if archive is None else _identity(archive))


def _role(plan, pin, side, record):
    role = side.name
    need(record['schema'] == 1 and record['backend'] == role and record['admissionSha256'] == pin,
         'backend record role/admission mismatch')
    _bound(record['binary'], side / 'bin/starbound')
    _bound(record['genericProof'], bp.sidecar(side / 'bin/starbound'))
    _bound(record['configured'], side / 'complete-tool-admission.json')
    _bound(record['dependencies'], side / 'client-dependencies.json')
    _bound(record['builder'], ROOT / 'scripts/build-id-map-behavior-lab.py')
    commands = _commands(plan, role, record)
    configured = _read(side / 'complete-tool-admission.json')
    need(configured.pop('planSha256') == pin, 'configured admission external pin mismatch')
    proof = _read(bp.sidecar(side / 'bin/starbound'))
    snapshots = _generic(plan, side, proof, configured)
    dependencies = _read(side / 'client-dependencies.json')
    replayed = builder.dependency_witness(plan, configured, proof)
    need(dependencies == replayed, 'observed compiler dependency/header/object witness changed')
    for name, entry in dependencies['dependencies'].items():
        need(_path(name) == Path(entry['physical']) and ad.sha(name) == entry['sha256'],
             'dependency must be current physical canonical input')
    archive = side / 'cmake' / ARCHIVE if role == 'candidate' else None
    if archive is None:
        need(record['archive'] is None, 'reference archive forbidden')
    else:
        _bound(record['archive'], archive)
        need(archive.stat().st_size <= code.MAX_INPUT_BYTES, 'bounded canonical archive required')
    link = _link_archive(side, archive)
    return dict(record=_identity(side / 'id-map-build.json'), binary=record['binary'],
                genericProof=record['genericProof'], configured=record['configured'],
                dependencies=record['dependencies'], commands=commands, snapshots=snapshots, link=link)


def validate_game_origin(executable: Path, proof: dict) -> dict:
    """Return deterministic current bindings or fail closed; never execute a tool."""
    executable = _path(executable)
    relative = executable.relative_to(ROOT)
    need(re.fullmatch(r'build/behavior/id-map-combined-r[1-9][0-9]*/(reference|candidate)/bin/starbound',
                      relative.as_posix()) is not None, 'only exact new physical IdMap game path accepted')
    side, root = executable.parent.parent, executable.parent.parent.parent
    need(not any(os.path.lexists(p / 'failure.json') for p in (root, root / 'reference', root / 'candidate')),
         'failed pair cannot qualify')
    completion = _read(root / 'completion.json')
    need(completion['status'] == 'ADMITTED_PAIR_BUILT_NOT_GAME_QUALIFIED' and
         set(completion['backends']) == set(ROLES), 'successful exact pair completion required')
    records = {}
    for role in ROLES:
        path = root / role / 'id-map-build.json'
        _bound(completion['backends'][role], path)
        records[role] = _read(path)
    own = records[side.name]
    admission = Path(own['admission']['path'])
    _bound(own['admission'], admission)
    pin = own['admissionSha256']
    need(pin == own['admission']['sha256'] == completion['admissionSha256'], 'external admission digest mismatch')
    for record in records.values():
        need(record['admission'] == own['admission'] and record['admissionSha256'] == pin, 'pair admission mismatch')
    plan = _read(admission)
    _static_plan(plan, root)
    need(proof == _read(bp.sidecar(executable)), 'supplied generic proof differs from binary sidecar')
    backends = {role: _role(plan, pin, root / role, records[role]) for role in ROLES}
    reference_end = _utc(_read(root / 'reference/provenance-verify.receipt.json')['finishedUTC'])
    candidate_start = _utc(_read(root / 'candidate/provenance-begin.command.json')['startedUTC'])
    need(reference_end <= candidate_start, 'candidate commands preceded reference completion')
    need(executable.stat().st_size <= code.MAX_INPUT_BYTES, 'bounded game required')
    game = executable.read_bytes()
    image = code._generic.MachO(game)
    need(image.kind == 2, 'native Mach-O MH_EXECUTE required')
    if side.name == 'reference':
        need(not any(symbol['name'] in code.NAMES[:2] for symbol in image.symbols),
             'reference must not contain IdMap run/count symbols')
        emitted = dict(status='NO_RUST', game_sha256=code.sha(game), selectors=ad.profiles()['reference'])
    else:
        archive_bytes = (side / 'cmake' / ARCHIVE).read_bytes()
        emitted = code.attest(game, archive_bytes)
        names = {n.hex() for n in code.NAMES}
        need(emitted['complete'] is True and not emitted['blockers'] and
             emitted['game_sha256'] == code.sha(game) and emitted['archive_sha256'] == code.sha(archive_bytes) and
             len(emitted['functions']) == 3 and {f['name_hex'] for f in emitted['functions']} == names and
             len(emitted['providers']) == 3 and {p['name_hex'] for p in emitted['providers']} == names and
             all(len(p['members']) == 1 for p in emitted['providers']) and emitted['native_call_edges'] and
             all(e['owner_hex'] == code.OWNER.hex() and e['target_name_hex'] == code.NAMES[0].hex()
                 for e in emitted['native_call_edges']),
             'current candidate emitted-code/provider/native-edge witness incomplete')
    ad.unchanged(plan['witness'])
    return dict(schema='id-map-whole-game-origin-v1', backend=side.name,
                admission=own['admission'], completion=_identity(root / 'completion.json'),
                backends=backends, compiledHeader=plan['compiledHeader'], emittedCode=emitted,
                validator=_identity(Path(__file__)), limitations=list(LIMITS))
