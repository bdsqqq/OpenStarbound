"""Current30 admission. Old plans select paths, never source epochs or receipts.

Products and admission evidence belong on P, inside enclosure E; all of G,
including backing E/image.dmg, remains charged. Role product trees are fresh.
"""
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = load('_sv_configuration', Path(__file__).with_name('configuration.py'))
# Only context-independent primitives, never old prepare/validate/origin APIs.
primitives = load('_sv_input_primitives', ROOT / 'source/lab/id-map-production/game_build_admission.py')
allocation = load('_sv_allocation', ROOT / 'source/lab/id-map-production/allocation.py')
need = config.need
profiles = config.profiles
SELECTORS = config.SELECTORS
CAPS = dict(allocation.CAPS)
DEADLINES = dict(primitives.DEADLINES)
CHECKPOINT = '825c30e46055e3c1c486b572dddf173c9017b889'
STAGE = 'STATIC_VECTOR_CURRENT30_SOURCE_ADMISSION_V3'
SCOPE = 'source/tool admission only; NOT game qualification'
HEADER = 'source/lab/behavior/static_vector_scene.hpp'
ARCHIVE = 'rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'
TOOL_PLAN = primitives.TOOL_PLAN
TOOL_PLAN_SHA = primitives.TOOL_PLAN_SHA
PREDECESSORS = {
    'reference': 'dfa33f62d3f5160adc1a82420b2ac12ea015c05cbdd3a5f0ff1e6cf6be969cbe',
    'candidate': 'e5a6fd3aad13c97490eac1022a9590bc8ab1aa513c50f15ec1dc10a487f36025'}
sha = primitives.sha
physical = primitives.physical
no_symlink_parents = primitives.no_symlink_parents
bounded = load('_sv_bounded_outputs', Path(__file__).with_name('bounded_outputs.py'))
er = load('_sv_enclosure_release', Path(__file__).with_name('enclosure_release.py'))
policy = load('_sv_enclosure_policy', Path(__file__).with_name('enclosure_policy.py'))
LIFECYCLE_TOOLS = {'hdiutil': '/usr/bin/hdiutil', 'sandbox-exec': '/usr/bin/sandbox-exec'}
FILESYSTEM_METADATA = frozenset(('.fseventsd', '.Trashes', '.metadata_never_index'))
FILESYSTEM_METADATA_CLASS = 'GENERATED_MUTABLE_FILESYSTEM_NOT_SOURCE'
PHASES = ('provenance-begin', 'configure', 'provenance-configured', 'cargo', 'compile', 'provenance-seal', 'provenance-verify')


def controller_outputs(root=None):
    """Finite logical JSON destinations, NOT native/physical allocation bounds.

    Caps are failure thresholds, not forecasts of future artifact sizes. Common
    provenance subprocess writes, logs, captures and native products are outside
    this contract. A retained partial blocks another attempt at the same path.
    """
    root = root or build_root()
    mib = 1024**2
    result = {root / 'current30-admission/plan.json': 64 * mib,
              root / 'completion.json': 64 * 1024, root / 'failure.json': 64 * 1024}
    for role in profiles():
        side = root / role
        for phase in PHASES:
            if phase == 'cargo' and role == 'reference':
                continue
            for suffix in ('.command.json', '.receipt.json'):
                result[side / (phase + suffix)] = 256 * 1024
        for name in ('build-inputs.json', 'inputs-before.json', 'complete-tool-admission.json',
                     'dependencies.json', 'static-vector-build.json'):
            result[side / name] = 64 * mib
        if role == 'candidate':
            result[side / 'cargo-expanded.json'] = 8 * mib
            result[side / 'prelink-archive.json'] = 8 * mib
        result[side / 'bin/starbound.behavior-build.json'] = 128 * mib
    return result


def controller_limit(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and path in controller_outputs(),
         'undeclared controller output path')
    return controller_outputs()[path]


def controller_output_bound():
    """Published + fixed partial logical bytes only; directory blocks excluded."""
    return 2 * sum(controller_outputs().values())


def dump(path, value):
    return bounded.write_json(path, value, controller_limit(path))


def write_common(path, value, expected=None):
    """Opt-in common-provenance publication at the two known role paths."""
    path = Path(path)
    need(path in {build_root() / role / name for role in profiles()
                  for name in ('build-inputs.json', 'bin/starbound.behavior-build.json')},
         'exact common provenance output required')
    limit = controller_limit(path)
    if expected is not None:
        need(type(expected['size']) is int and 0 <= expected['size'] <= limit,
             'existing common proof exceeds contract')
    return bounded.write_json(path, value, limit, replace_expected=expected)


def supplement_sidecar(path, value, expected):
    path = Path(path)
    need(path in {build_root() / role / 'bin/starbound.behavior-build.json' for role in profiles()},
         'exact generated sidecar required')
    limit = controller_limit(path)
    need(type(expected['size']) is int and 0 <= expected['size'] <= limit,
         'existing common proof exceeds sidecar contract')
    # Match the former compact sidecar serialization byte-for-byte below cap.
    return bounded.write_json(path, value, limit, indent=None, newline=False, replace_expected=expected)

unchanged = primitives.unchanged
tree_members = primitives.tree_members


def allocation_root():
    return ROOT / 'build/behavior/static-vector-combined-r1'


def enclosure_root():
    return allocation_root() / 'current30-enclosure'


def build_root():
    return enclosure_root() / 'products'


def _bounded_owner_file(path):
    """Check physical type/link/size BEFORE any hash or read; pin both identities."""
    path = er.physical(str(path))
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
         0 < before.st_size <= 1024**2, 'bounded regular single-link ownership file')
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
    state = {key: getattr(before, key) for key in fields}
    with path.open('rb') as stream:
        raw = stream.read(1024**2 + 1)
    after = path.lstat()
    need(len(raw) == before.st_size and
         {key: getattr(after, key) for key in fields} == state,
         'ownership file changed during read')
    record = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    return raw, dict(identity=record, physical=state)


def _owner_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate owner JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite owner JSON')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def _require_single_device(root, device):
    """Reject unsupported descendant mounts; this is NOT allocation accounting.

    The whole-G observer still charges every device. This quiescent topology
    check neither replaces it nor proves that a later mount cannot be created.
    """
    need(type(device) is int and device > 0, 'exact guest device required')
    root = er.physical(str(root))
    before = root.stat()
    need(stat.S_ISDIR(before.st_mode) and before.st_dev == device, 'owned guest root device')
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                state = entry.stat(follow_symlinks=False)
                need(state.st_dev == device, 'unsupported descendant device')
                if stat.S_ISDIR(state.st_mode):
                    pending.append(Path(entry.path))
    after = root.stat()
    need((after.st_dev, after.st_ino) == (before.st_dev, before.st_ino), 'guest root changed')


def enclosure_state():
    """Recorded setup association plus CURRENT physical pins, not live attestation.

    No mutable backing bytes are hashed. Recorded device info cannot detect a
    reverted intervening mount; future native checks still recheck all pins.
    """
    def committed():
        need(not any(os.path.lexists(enclosure_root() / name) for name in
                     ('.setup-in-progress', 'setup-failure.json', 'release-evidence')),
             'setup must be committed and nonterminal')
    committed()
    raw, owner_file = _bounded_owner_file(enclosure_root() / 'owner.json')
    info, info_file = _bounded_owner_file(enclosure_root() / 'ownership-info.plist')
    owner = _owner_json(raw)
    er.validate_owner(owner)
    need(owner['root'] == str(enclosure_root()) and
         owner['image']['path'] == str(enclosure_root() / 'image.dmg') and
         owner['mount']['path'] == str(build_root()), 'exact current enclosure namespace')
    # A sanity cap only, not a future physical allocation/conservation bound.
    need(owner['image']['maxBytes'] <= CAPS['newRootBytes'] // 2, 'image sanity cap')
    er.image_state(owner)
    er.tool_state(owner)
    er.mounted_state(owner)
    _require_single_device(build_root(), owner['mount']['st_dev'])
    er.association(info, owner)
    need(_bounded_owner_file(enclosure_root() / 'owner.json')[1] == owner_file and
         _bounded_owner_file(enclosure_root() / 'ownership-info.plist')[1] == info_file,
         'ownership files changed')
    committed()
    return dict(owner=owner, ownerFile=owner_file, infoFile=info_file)


def source_roots(tools, sdk):
    # Lifecycle tools are individual system files, never CMake -D selections.
    return primitives.source_roots(tools, sdk) + list(LIFECYCLE_TOOLS.values())


def identity(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute canonical path required')
    no_symlink_parents(path)
    need(path.resolve(strict=True) == path and path.is_file(), 'physical regular file required: ' + str(path))
    return dict(path=str(path), sha256=sha(path), size=path.stat().st_size)


def file_state(path):
    identity(path)
    info = Path(path).stat()
    need(info.st_nlink == 1, 'unique physical output file required')
    return {key: getattr(info, key) for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')}


def check_budget(root=None):
    need(allocation.CAPS == CAPS, 'fixed allocation caps')
    need(root is None or Path(root) == allocation_root(), 'whole allocation root required')
    return allocation.enforce(ROOT, allocation_root())


def check_binaries():
    """The needed IdMap pair stays LIVE; no retirement assertion is inherited."""
    need(not os.path.lexists(ROOT / 'build/.migration-cleanup.lock'), 'cleanup active')
    expected = {ROOT / 'build/behavior/id-map-combined-r2' / role / 'bin/starbound': pin
                for role, pin in PREDECESSORS.items()}
    for path, pin in expected.items():
        need(identity(path)['sha256'] == pin, 'protected predecessor changed')
    behavior = ROOT / 'build/behavior'
    # Include legacy unqualified roots, dangling aliases and arbitrary nesting.
    for base, dirs, files in os.walk(behavior, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            if path.is_symlink():
                need(name != 'starbound' and name not in ('bin', 'reference', 'candidate') and
                     Path(base) != behavior and Path(base).name != 'bin', 'binary path alias')
            if path.is_file() and Path(base).name == 'bin':
                with path.open('rb') as stream:
                    magic = stream.read(4)
                if magic in (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\x7fELF'):
                    need(path in expected or path in {build_root() / r / 'bin/starbound' for r in profiles()}, 'unexpected native binary in role bin')
            if name == 'starbound':
                allowed = {build_root() / r / 'bin/starbound' for r in profiles()}
                need(path in expected or path in allowed, 'unexpected native game binary: ' + str(path))
                identity(path)
    return {str(p): identity(p) for p in expected}


def _metadata_tree(path, mutable=False):
    """Even generated OS state is readable, physical, and never native input."""
    no_symlink_parents(path)
    info = path.lstat()
    need(not stat.S_ISLNK(info.st_mode), 'metadata alias forbidden')
    if stat.S_ISDIR(info.st_mode):
        result = {}
        # scandir propagates unreadable-tree errors, unlike default os.walk.
        with os.scandir(path) as entries:
            for entry in entries:
                result.update(_metadata_tree(Path(entry.path), mutable))
        return result
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'metadata regular single-link file')
    need(path.suffix not in ('.o', '.a', '.dylib') and path.name != 'starbound',
         'product in initial metadata root')
    with path.open('rb') as stream:
        need(stream.read(4) not in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe',
             b'\xfe\xed\xfa\xcf', b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe',
             b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca',
             b'\x7fELF', b'!<ar', b'!<th'), 'native input in metadata root')
    return {} if mutable else {str(path): identity(path)}


def metadata_inventory(root):
    """Only named root OS metadata is mutable; it is NOT source or budget-exempt."""
    no_symlink_parents(root)
    need(root.is_dir(), 'existing metadata root required')
    need(not any(os.path.lexists(root / r) for r in profiles()), 'fresh role product directories required')
    result = {}
    with os.scandir(root) as entries:
        for entry in entries:
            result.update(_metadata_tree(Path(entry.path), entry.name in FILESYSTEM_METADATA))
    return result


def check_deadline(plan, now=None):
    need(plan['deadlines'] == DEADLINES, 'immutable 35 minute clock')
    created = dt.datetime.fromisoformat(plan['createdUTC'])
    need(created.tzinfo is not None, 'aware creation timestamp')
    age = ((now or dt.datetime.now(dt.timezone.utc)) - created).total_seconds()
    need(0 <= age < DEADLINES['maxAgeSeconds'], 'original admission deadline reached')


def native_sandbox(plan, enclosure=None):
    state = enclosure if enclosure is not None else enclosure_state()
    need(policy.same(plan['enclosure'], state), 'mounted enclosure ownership drift')
    primitives._require_pin(plan['witness'], policy.TOOL, 'Native sandbox tool')
    return policy.binding(state['owner'], identity(policy.TOOL))


def sandbox_command(plan, argv):
    # Default Native admission cannot borrow a host-control owner's wider root.
    need(plan['buildRoot'] == str(build_root()) and
         plan['enclosure']['owner']['root'] == str(enclosure_root()) and
         plan['enclosure']['owner']['mount']['path'] == str(build_root()),
         'exact Native enclosure products required')
    expected = policy.binding(plan['enclosure']['owner'], plan['nativeSandbox']['tool'])
    need(policy.same(plan['nativeSandbox'], expected), 'Native sandbox binding drift')
    return policy.wrap(plan['buildRoot'], argv)


def commands(plan, role):
    """Settled phase argv: candidate cargo target MUST finish/seal before build.

    Cargo's expanded evaluated command is separately checked before execution;
    the cmake target is the existing single aggregate, not a prebuilt API.
    """
    need(role in profiles(), 'exact role')
    side = Path(plan['buildRoot']) / role
    tools = plan['tools']
    configure = [tools['CMAKE_EXECUTABLE'], '--preset', 'macos-arm-release', '-B', str(side / 'cmake')]
    configure += ['-D' + k + '=' + v for k, v in sorted(tools.items()) if k not in primitives.EXCLUDED]
    configure += config.configure_options(role)
    configure += ['-DCMAKE_OSX_SYSROOT=' + plan['sdk'],
        '-DCMAKE_EXE_LINKER_FLAGS=-Wl,-map,' + str(side / 'link.map'), '-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON',
        '-DCMAKE_VERBOSE_MAKEFILE=OFF', '-DBUILD_TESTING=OFF', '-DSTAR_ENABLE_STEAM_INTEGRATION=OFF',
        '-DSTAR_ENABLE_DISCORD_INTEGRATION=OFF', '-DSTAR_BUILD_LIGHTING_LAB=OFF',
        '-DSTAR_RUNTIME_OUTPUT_DIRECTORY=' + str(side / 'bin'), '-DVCPKG_MANIFEST_INSTALL=OFF',
        '-DVCPKG_INSTALLED_DIR=' + str(ROOT / 'build/macos-arm-release/vcpkg_installed')]
    keys = [a[2:].partition('=')[0] for a in configure if a.startswith('-D')]
    need(len(keys) == len(set(keys)), 'duplicate configure arguments')
    base = [tools['CMAKE_EXECUTABLE'], '--build', str(side / 'cmake'), '--target']
    return dict(configure=sandbox_command(plan, configure),
                cargo=sandbox_command(plan, base + ['star_rust_engine_ffi_build', '--parallel', '6', '--', '-d', 'keepdepfile']) if role == 'candidate' else None,
                build=sandbox_command(plan, base + ['starbound', '--parallel', '6', '--', '-d', 'keepdepfile']))


def current_inputs(plan):
    need(policy.same(plan['nativeSandbox'], native_sandbox(plan)), 'Native sandbox current binding drift')
    config.validate_source()
    tools, sdk = primitives.selected_paths(plan['toolPlan'], plan['toolPlanSha256'])
    need(plan['tools'] == tools and plan['sdk'] == sdk and plan['sdkPhysical'] == physical(sdk), 'current tool/SDK drift')
    roots = source_roots(tools, sdk)
    need(plan['sourceRoots'] == roots, 'source/tool scope drift')
    members = tree_members(roots)
    need(members == plan['treeMembers'], 'current source/tool/SDK membership drift')
    primitives.check_member_scope(members)
    need(all(resolved in plan['witness']['files'] for name, resolved in members.items() if Path(name).is_file()), 'unhashed member')
    for path in LIFECYCLE_TOOLS.values():
        primitives._require_pin(plan['witness'], path, 'lifecycle tool')
    unchanged(plan['witness'])
    need(plan['retention'] == identity(plan['retention']['path']) and
         json.loads(Path(plan['retention']['path']).read_text()) == plan['retentionForecast'], 'parent retention proof drift')
    need(plan['python'] in plan['witness']['aliases'] and
         plan['witness']['files'].get(physical(plan['python'])) == sha(plan['python']), 'actual admitted Python')
    need(plan['lifecycleTools'] == LIFECYCLE_TOOLS and
         plan['filesystemMetadataClassification'] ==
         {name: FILESYSTEM_METADATA_CLASS for name in sorted(FILESYSTEM_METADATA)},
         'lifecycle tools/filesystem metadata contract')
    for name in FILESYSTEM_METADATA:
        path = build_root() / name
        if os.path.lexists(path):
            _metadata_tree(path, mutable=True)
    for path, record in plan['initialMetadata'].items():
        need(Path(path).is_relative_to(build_root()) and
             Path(path).relative_to(build_root()).parts[0] not in FILESYSTEM_METADATA,
             'generated filesystem metadata is not immutable source')
        need(identity(path) == record, 'initial metadata changed')
    need(plan['predecessors'] == check_binaries(), 'needed live predecessors changed')


def static_plan(plan):
    need(plan['stage'] == STAGE and plan['scope'] == SCOPE and plan['caps'] == CAPS, 'exact admission contract')
    need(plan['sourceCheckpoint'] == CHECKPOINT and plan['checkpointRole'] == 'BASE_ONLY; current working-tree bytes authoritative', 'current source base required')
    need(plan['buildRoot'] == str(build_root()) and plan['profiles'] == profiles(), 'current30 root/profiles')
    need(plan['deadlines'] == DEADLINES, 'fixed clock')
    need(plan['toolPlan'] == str(ROOT / TOOL_PLAN) and plan['toolPlanSha256'] == TOOL_PLAN_SHA and
         plan['toolPlanRole'] == 'PATH_SELECTION_ONLY; historical admission NOT reused', 'path-selector plan pin')
    # Python equality conflates bool/int/float; physical owner pins do not.
    state = enclosure_state()
    need(policy.same(plan['enclosure'], state), 'mounted enclosure ownership drift')
    need(policy.same(plan['nativeSandbox'], native_sandbox(plan, state)), 'Native sandbox binding drift')
    need(plan['commands'] == {r: commands(plan, r) for r in profiles()}, 'actual future argv drift')
    current_inputs(plan)


def validate(plan):
    static_plan(plan)
    check_deadline(plan)
    budget = check_budget()
    check_retention(plan['retentionForecast'], plan['sourceCheckpoint'], budget)
    return build_root()


RETENTION_PRODUCTS = frozenset({
    'predecessor-reference', 'predecessor-candidate', 'new-reference', 'new-candidate',
    'native-objects-and-libraries', 'cargo-products', 'admission-and-capture-evidence'})


def check_retention(forecast, checkpoint, budget):
    """Binary-only costs cannot reserve conservation of an entire generation.

    Values are conservative ADDITIONAL allocated archive bytes, including CAS
    encoding/manifests/directory overhead, not raw sizes or expected compression.
    The parent must establish the estimates; this guard only checks coverage and
    capacity. It does not turn an asserted forecast into measured artifact costs.
    """
    need(type(forecast) is dict and
         forecast.get('schema') == 'static-vector-product-retention-forecast-v1' and
         forecast.get('sourceCheckpoint') == checkpoint and forecast.get('complete') is True and
         type(forecast.get('products')) is dict and set(forecast['products']) == RETENTION_PRODUCTS,
         'complete generation conservation forecast required; binaries alone are insufficient')
    costs = forecast['products']
    need(all(type(v) is int and v > 0 for v in costs.values()) and
         sum(costs.values()) <= CAPS['archiveBytes'] - budget['archiveBytes'],
         'generation retention costs exceed fixed archive headroom')
    return sum(costs.values())


def prepare(output, checkpoint, initial_metadata, retention, retention_sha, *, created_utc):
    """Parent supplies inventoried metadata and a fresh product-retention forecast.

    No existing capacity-target or archived-plan receipt implies this forecast.
    Its conservative additional allocated archive reservation is checked against
    the ACTUAL disjoint allocation observation before creating any file.
    """
    check_deadline(dict(createdUTC=created_utc, deadlines=DEADLINES))
    output = Path(output).absolute()
    need('..' not in output.parts, 'no admission output traversal')
    no_symlink_parents(output)
    root = build_root()
    need(output == root / 'current30-admission' and not os.path.lexists(output),
         'one canonical fresh current30 admission required')
    need(checkpoint == CHECKPOINT, 'current base checkpoint required')
    enclosure = enclosure_state()
    config.validate_source()
    need(metadata_inventory(root) == initial_metadata, 'explicit exact metadata-only initial inventory')
    budget = check_budget()
    retention = Path(retention).absolute()
    need(retention.is_relative_to(root) and sha(retention) == retention_sha, 'parent retention forecast pin inside products')
    forecast = json.loads(retention.read_text())
    check_retention(forecast, checkpoint, budget)
    tools, sdk = primitives.selected_paths(ROOT / TOOL_PLAN, TOOL_PLAN_SHA)
    roots = source_roots(tools, sdk)
    members = tree_members(roots)
    primitives.check_member_scope(members)
    witness = primitives.closure([Path(r) for r in roots if Path(r).is_dir()])
    paths = list(tools.values()) + list(LIFECYCLE_TOOLS.values()) + list(map(str, primitives.auxiliary_tools())) + [str(ROOT / TOOL_PLAN), sys.executable]
    paths += [r for r in roots if Path(r).is_file()]
    primitives._pin(witness, paths)
    plan = dict(stage=STAGE, scope=SCOPE, caps=CAPS, deadlines=DEADLINES,
        createdUTC=created_utc, sourceCheckpoint=checkpoint,
        checkpointRole='BASE_ONLY; current working-tree bytes authoritative', buildRoot=str(root),
        profiles=profiles(), tools=tools, sdk=sdk, sdkPhysical=physical(sdk), toolPlan=str(ROOT / TOOL_PLAN),
        toolPlanSha256=TOOL_PLAN_SHA, toolPlanRole='PATH_SELECTION_ONLY; historical admission NOT reused',
        sourceRoots=roots, treeMembers=members, witness=witness,
        enclosure=enclosure, lifecycleTools=dict(LIFECYCLE_TOOLS),
        filesystemMetadataClassification={name: FILESYSTEM_METADATA_CLASS for name in sorted(FILESYSTEM_METADATA)},
        initialMetadata=initial_metadata, predecessors=check_binaries(), budgetBefore=budget,
        retention=identity(retention), retentionForecast=forecast, python=str(Path(sys.executable).absolute()))
    plan['nativeSandbox'] = native_sandbox(plan, enclosure)
    plan['commands'] = {r: commands(plan, r) for r in profiles()}
    validate(plan)
    output.mkdir()
    bounded.write_json(output / 'plan.json', plan, controller_limit(output / 'plan.json'),
                       indent=None, separators=(',', ':'), newline=False)
    validate(plan)
    return plan


def check_configured(plan, build):
    build = Path(build).absolute()
    role = build.parent.name
    need(role in profiles() and build == build_root() / role / 'cmake', 'exact configured role path')
    no_symlink_parents(build)
    cache = build / 'CMakeCache.txt'
    cache_text = cache.read_text()
    for line in cache_text.splitlines():
        key, _, value = line.partition('=')
        need(not (key.split(':')[0].endswith('_COMPILER_LAUNCHER') and value), 'unadmitted compiler launcher')
    need('CMAKE_EXE_LINKER_FLAGS:STRING=-Wl,-map,' + str(build.parent / 'link.map') in cache_text.splitlines(), 'actual linker map output flag')
    config.validate_cache(role, cache.read_text())
    need(primitives.selection(cache) == plan['tools'], 'configured tool selection drift')
    need(primitives.sdk_from_ninja(build / 'build.ninja') == plan['sdk'], 'configured SDK drift')
    rows = json.loads((build / 'compile_commands.json').read_text())
    objects = {}
    for filename, source in [('client', 'client/StarClientApplication.cpp'), ('world', 'game/StarWorldClient.cpp')]:
        selected = [row for row in rows if Path(row['file']).resolve() == ROOT / 'source' / source]
        need(len(selected) == 1, 'unique actual compile command: ' + source)
        row = selected[0]
        argv = row.get('arguments') or shlex.split(row['command'])
        config.validate_flags(role, argv)
        need(argv[0] == plan['tools']['CMAKE_CXX_COMPILER'] and argv.count('-c') == argv.count('-o') == 1, 'actual compiler/input/output')
        directory = Path(row['directory'])
        need(directory.is_absolute(), 'absolute compilation directory')
        def resolve(value):
            p = Path(value)
            return (p if p.is_absolute() else directory / p).resolve(strict=False)
        need(resolve(argv[argv.index('-c') + 1]) == ROOT / 'source' / source, 'actual source mismatch')
        sdks = [argv[i + 1] for i, word in enumerate(argv[:-1]) if word == '-isysroot']
        need(sdks == [plan['sdk']], 'actual compiler SDK')
        obj = resolve(argv[argv.index('-o') + 1])
        need(obj.is_relative_to(build) and obj.suffix == '.o', 'scoped actual object')
        no_symlink_parents(obj)
        objects[filename] = dict(object=str(obj), depfile=str(obj) + '.d', directory=str(directory), argv=argv)
    return dict(role=role, objects=objects, files={name: identity(build / name) for name in
                ('CMakeCache.txt', 'build.ninja', 'compile_commands.json')}, selectors=profiles()[role])


def configured(plan, plan_sha, build):
    validate(plan)
    receipt = dict(check_configured(plan, build), planSha256=plan_sha)
    dump(Path(build).parent / 'complete-tool-admission.json', receipt)
    return receipt
