"""Cache-derived PRE-execution admission, not another guessed tool list.

The three earlier canonical stages remain immutable, unqualified evidence.
This stage derives ALL cache FILEPATH executables, fixes their selected paths in
its future argv, checks each pin before launch, then reconciles selection after
configure. Actual retained Core dependencies get an independently qualified
historical source/object witness, not the smaller TTL fixture's input list.
"""
import copy
import re
import shlex
from common import *
import canonical as provisional

CMAKE = provisional.CMAKE
NINJA = provisional.NINJA
SDK = provisional.SDK
TOOLS = provisional.TOOLS
CM = OUT / 'guarded-cmake'
ARCHIVE = CM / 'rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'
RECORD = OUT / 'guarded-canonical.typed'
RUNTIME = ROOT / 'build/lru-production-runtime-r1/acquisition-4/report.typed'
RUNTIME_SHA = 'beec45da25fec2ed9e5e052dd5dfc4b8c498a425debffd2a275afa59899ab41c'
REFERENCE = ROOT / 'build/behavior/lru-cache-combined-r1/reference/cmake'


def selection(cache):
    rows = re.findall(r'^([^/#\n][^:\n]*):([^=\n]*)=(.*)$', Path(cache).read_text(), re.M)
    selected = {}
    for key, kind, value in rows:
        if not value or value.endswith('-NOTFOUND'):
            continue
        if key.endswith('_LAUNCHER'):
            need(';' not in value and Path(value).is_absolute(), 'unresolved selected launcher')
            selected[key] = value
        elif Path(value).is_absolute() and Path(value).is_file() and os.access(value, os.X_OK):
            selected[key] = value
    selected.update(CMAKE_EXECUTABLE=CMAKE, APPLE_TOOLCHAIN_SELECTOR='/usr/bin/xcrun',
                    STAR_CARGO_EXECUTABLE=str(TOOLS / 'cargo'), STAR_RUSTC_EXECUTABLE=str(TOOLS / 'rustc'))
    for name in ('CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_AR', 'CMAKE_RANLIB', 'CMAKE_LINKER', 'CMAKE_MAKE_PROGRAM'):
        need(name in selected, 'missing mandatory selected tool ' + name)
    for key, value in selected.items():
        need(Path(value).is_absolute() and ';' not in value, 'unresolved executable ' + key)
        need(Path(value).is_file() and os.access(value, os.X_OK), 'nonexecutable selected tool ' + key)
        with Path(value).open('rb') as stream:
            prefix = stream.read(256)
        # No implicit interpreter/wrapper resolution is accepted by this mechanism.
        # Current selected tools are native binaries. A script requires a new
        # explicit interpreter/argument contract BEFORE launch, never a waiver.
        need(not prefix.startswith(b'#!'), 'unresolved interpreter wrapper ' + key)
    return dict(sorted(selected.items()))


def check_admission(plan, pins):
    need(plan['stage'] == 'CACHE_DERIVED_PREEXECUTION', 'wrong admission stage')
    need(sha(plan['seedCache']) == plan['seedCacheSha256'], 'seed cache physical pin')
    need(plan['tools'] == selection(plan['seedCache']), 'selected cache changed')
    need(sha(OUT / 'guarded-lineage.typed') == plan['lineageSha256'], 'lineage record pin')
    lineage = load(OUT / 'guarded-lineage.typed')
    for field in ('dependencies', 'metadata'):
        for path, expected in lineage[field].items():
            need(pins.get(path) == expected, 'missing qualified Core dependency before execution ' + path)
    for key, path in plan['tools'].items():
        need(type(pins.get(path)) is str and pins[path] == sha(path), 'missing/changed PREexecution tool ' + key)
    # Every selected cache executable is fixed explicitly, not left to another
    # search during configure. Pseudo selector/compiler process probes are pins,
    # not CMake cache arguments.
    for key, path in plan['tools'].items():
        if key not in ('CMAKE_EXECUTABLE', 'APPLE_TOOLCHAIN_SELECTOR'):
            need('-D' + key + '=' + path in plan['argv'], 'tool not fixed in future argv ' + key)
    for path, expected in pins.items():
        need(type(expected) is str and sha(path) == expected, 'pre-execution input drift ' + path)
    return True


def dependency_witness():
    """Metadata-only Ninja query. No compiler/build action is launched."""
    need(sha(RUNTIME) == RUNTIME_SHA, 'qualified historical Core witness pin')
    historical = load(RUNTIME)['inputs']
    reference = json.loads((REFERENCE / 'compile_commands.json').read_bytes())
    ninja = (REFERENCE / 'build.ninja').read_text().splitlines()
    i = next(i for i, line in enumerate(ninja) if line.startswith('build ') and '/bin/starbound:' in line)
    objects = [str(REFERENCE / p) for p in shlex.split(ninja[i].split(': ', 1)[1])[1:]
               if p.endswith('.o') and p.startswith(('core/', 'extern/'))]
    need(len(objects) == len(set(objects)) == 113, '113 retained object membership')
    metadata = hashes([REFERENCE / '.ninja_deps', REFERENCE / 'build.ninja', REFERENCE / 'compile_commands.json', RUNTIME])
    if not (OUT / 'guarded-lineage.typed').exists():
        command('guarded-object-deps', [NINJA, '-t', 'deps', *[str(Path(p).relative_to(REFERENCE)) for p in objects]], cwd=REFERENCE)
    else:
        # Reuse the explicitly historical metadata-only query from the first
        # preflight, not a fresh compiler witness. Verify its exact plan/receipt
        # and reconstruct the SAME dependency set below before any new launch.
        verify_commands({}, lambda p: Path(p).read_bytes())
        plan = load(OUT / 'guarded-object-deps.plan')
        need(plan['argv'] == [NINJA, '-t', 'deps', *[str(Path(p).relative_to(REFERENCE)) for p in objects]], 'retained query argv')
    need(metadata == hashes(map(Path, metadata)), 'retained metadata changed')
    deps = set(); observed = []
    for block in (OUT / 'guarded-object-deps.stdout').read_text().strip().split('\n\n'):
        lines = block.splitlines()
        m = re.fullmatch(r'(.+): #deps ([0-9]+), deps mtime ([0-9]+) \(VALID\)', lines[0])
        need(m is not None and len(lines) - 1 == int(m[2]), 'valid retained dependency records')
        observed.append(str(REFERENCE / m[1]))
        deps.update(str(Path(p.strip()) if Path(p.strip()).is_absolute() else REFERENCE / p.strip()) for p in lines[1:])
    need(observed == objects, 'exact retained dependency object membership')
    checked = {}
    for path in sorted(deps | set(objects)):
        need(path in historical, 'dependency absent from qualified historical input map ' + path)
        need(sha(path) == historical[path], 'qualified Core dependency changed ' + path)
        checked[path] = historical[path]
    # The source selected for each object is also explicit in compile_commands.
    for row in reference:
        if row['output'] in objects:
            need(row['file'] in deps, 'object source missing from Ninja dependencies')
            need('-DSTAR_USE_RUST' not in row['command'], 'retained Core selector drift')
    result = dict(status='EXACT_QUALIFIED_CORE_DEPENDENCIES', historicalReport=str(RUNTIME),
                  historicalReportSha256=RUNTIME_SHA, dependencies=checked, metadata=metadata, objects=objects)
    if (OUT / 'guarded-lineage.typed').exists():
        need(load(OUT / 'guarded-lineage.typed') == result, 'retained query exact reconstruction')
    else:
        dump(OUT / 'guarded-lineage.typed', result)
    return result


def preflight():
    need(not CM.exists() and not RECORD.exists(), 'fresh guarded stage required')
    lineage = dependency_witness()
    tools = selection(provisional.CM / 'CMakeCache.txt')
    argv = [CMAKE, '--preset', 'macos-arm-release', '-B', str(CM),
            '-DCMAKE_OSX_SYSROOT=' + SDK, '-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON',
            '-DCMAKE_VERBOSE_MAKEFILE=OFF', '-DBUILD_TESTING=OFF',
            '-DSTAR_ENABLE_STEAM_INTEGRATION=OFF', '-DSTAR_ENABLE_DISCORD_INTEGRATION=OFF',
            '-DSTAR_BUILD_LIGHTING_LAB=OFF', '-DSTAR_USE_RUST_LIGHTING=ON',
            '-DVCPKG_MANIFEST_INSTALL=OFF', '-DVCPKG_INSTALLED_DIR=' + str(ROOT / 'build/macos-arm-release/vcpkg_installed'),
            '-DSTAR_RUNTIME_OUTPUT_DIRECTORY=' + str(OUT / 'unused-bin')]
    argv += ['-D' + key + '=' + value for key, value in tools.items()
             if key not in ('CMAKE_EXECUTABLE', 'APPLE_TOOLCHAIN_SELECTOR')]
    pins = provisional.stable_sources()
    pins.update(lineage['dependencies']); pins.update(lineage['metadata'])
    pins.update(hashes(map(Path, tools.values())))
    pins.update(hashes(p for p in HERE.glob('*') if p.is_file()))
    pins.update(hashes([provisional.CM / 'CMakeCache.txt', OUT / 'guarded-lineage.typed']))
    plan = dict(stage='CACHE_DERIVED_PREEXECUTION', tools=tools, argv=argv,
                seedCache=str(provisional.CM / 'CMakeCache.txt'), seedCacheSha256=sha(provisional.CM / 'CMakeCache.txt'),
                lineageSha256=sha(OUT / 'guarded-lineage.typed'))
    check_admission(plan, pins)
    controls = []
    for key, path in tools.items():
        bad = dict(pins); del bad[path]
        try:
            check_admission(plan, bad)
        except ValueError as error:
            need('PREexecution tool' in str(error), 'wrong missing-tool barrier')
            controls.append(dict(missing=key, rejected=str(error)))
        else:
            raise ValueError('missing selected tool admitted ' + key)
    bad = dict(pins); bad[tools['CMAKE_C_COMPILER']] = '0' * 64
    try:
        check_admission(plan, bad)
    except ValueError as error:
        need('PREexecution tool' in str(error), 'wrong changed-compiler barrier')
        controls.append(dict(changed='compiler', rejected=str(error)))
    else:
        raise ValueError('changed compiler admitted')
    bad = dict(pins)
    cpp = next(p for p in lineage['dependencies'] if p.endswith('.cpp'))
    del bad[cpp]
    try:
        check_admission(plan, bad)
    except ValueError as error:
        need('qualified Core dependency' in str(error), 'wrong missing Core source barrier')
        controls.append(dict(missing='qualified-Core-source', rejected=str(error)))
    else:
        raise ValueError('missing Core source admitted')
    launcher = OUT / 'guarded-launcher-control.cache'
    write(launcher, (Path(plan['seedCache']).read_text() + '\nCMAKE_CXX_COMPILER_LAUNCHER:STRING=/bin/sh;--foreign-wrapper\n').encode())
    try:
        selection(launcher)
    except ValueError as error:
        need('unresolved selected launcher' in str(error), 'wrong launcher barrier')
        controls.append(dict(unresolved='launcher', rejected=str(error)))
    else:
        raise ValueError('unresolved launcher admitted')
    need(not CM.exists(), 'preflight controls launched configure')
    dump(OUT / 'guarded-plan.typed', plan)
    dump(OUT / 'guarded-configure-source-before.typed', pins)
    dump(OUT / 'guarded-admission-controls.typed', dict(positive=True, negatives=controls, noConfigureLaunched=True))
    print('REAL_CACHE_DERIVED_ADMISSION_AND_CONTROLS_PASS', len(tools), len(pins), flush=True)


def configured_inputs():
    pins = load(OUT / 'guarded-configure-source-before.typed')
    paths = set(map(Path, pins))
    paths.update(p for p in CM.rglob('*') if p.is_file() and
                 (p.suffix in ('.cmake', '.ninja', '.h', '.hpp', '.c', '.cpp') or p.name in ('CMakeCache.txt', 'compile_commands.json'))
                 and 'rust-engine-ffi' not in p.parts)
    return hashes(paths)


def acquire():
    plan = load(OUT / 'guarded-plan.typed'); pins = load(OUT / 'guarded-configure-source-before.typed')
    need(not CM.exists() and not RECORD.exists(), 'fresh pre-admitted execution only')
    check_admission(plan, pins)  # BEFORE the first configure/compiler action.
    command('guarded-canonical-configure', plan['argv'], timeout=180, cwd=ROOT / 'source')
    need(pins == hashes(map(Path, pins)), 'guarded configure input drift')
    need(selection(CM / 'CMakeCache.txt') == plan['tools'], 'actual configure selected an unadmitted executable')
    inputs = configured_inputs(); dump(OUT / 'guarded-canonical-inputs-before.typed', inputs)
    ninja = (CM / 'build.ninja').read_text()
    need('--package star-engine-ffi --target aarch64-apple-darwin --release --locked --offline' in ninja
         and 'ffi/src/ttl_cache.rs' in ninja, 'single canonical generated Cargo recipe')
    command('guarded-canonical-build', [CMAKE, '--build', CM, '--target', 'star_rust_engine_ffi_build', '--parallel', '2'], timeout=300, cwd=ROOT / 'source')
    need(inputs == configured_inputs(), 'guarded target inputs changed')
    dump(RECORD, dict(status='CACHE_DERIVED_PREADMITTED_CANONICAL_BUILT', inputs=inputs,
                     archive=str(ARCHIVE), archive_sha256=sha(ARCHIVE),
                     planSha256=sha(OUT / 'guarded-plan.typed'), beforeSha256=sha(OUT / 'guarded-configure-source-before.typed'),
                     controlsSha256=sha(OUT / 'guarded-admission-controls.typed'),
                     limits='finite selected-tool/recipe/source admission; not universal transitive execution/runtime attestation or bridge qualification'))
    verify()
    print('CACHE_DERIVED_PREADMITTED_CANONICAL_BUILT', sha(ARCHIVE), flush=True)


def verify():
    plan = load(OUT / 'guarded-plan.typed'); pins = load(OUT / 'guarded-configure-source-before.typed')
    check_admission(plan, pins)
    record = load(RECORD)
    need(record['status'] == 'CACHE_DERIVED_PREADMITTED_CANONICAL_BUILT', 'guarded canonical status')
    need(record['inputs'] == configured_inputs(), 'guarded canonical input membership/bytes')
    need(record['archive'] == str(ARCHIVE) and record['archive_sha256'] == sha(ARCHIVE), 'guarded canonical artifact bytes')
    need(selection(CM / 'CMakeCache.txt') == plan['tools'], 'guarded selected tools')
    for key, name in [('planSha256', 'guarded-plan.typed'), ('beforeSha256', 'guarded-configure-source-before.typed'), ('controlsSha256', 'guarded-admission-controls.typed')]:
        need(record[key] == sha(OUT / name), 'guarded admission record binding')
    return record


def require_complete():
    return verify()


if __name__ == '__main__':
    if sys.argv[1:] == ['--preflight']:
        preflight()
    elif sys.argv[1:] == ['--acquire']:
        acquire()
    elif sys.argv[1:] == ['--verify']:
        verify(); print('GUARDED_CANONICAL_READONLY_PASS')
    else:
        raise SystemExit('use --preflight, --acquire or --verify')
