#!/usr/bin/env python3
"""Fresh IdMap source/tool admission, not compilation or game qualification.

The old plan selects tool and SDK PATHS only. Its historical source witnesses,
profiles, receipts and live-inode claims are never imported into this admission.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_generic = _load('_id_map_generic_game_admission',
                 ROOT / 'source/lab/weighted-pool-production/game_build_admission.py')
# These generic primitives are unchanged. In particular, never call the old
# validate/prepare/check_retirement or mutate that module's globals.
selection = _generic.selection
closure = _generic.closure
unchanged = _generic.unchanged
tree_members = _generic.tree_members
native = _generic.native
allocated = _generic.allocated
physical = _generic.physical
no_symlink_parents = _generic.no_symlink_parents
auxiliary_tools = _generic.auxiliary_tools
admission_roots = _generic.admission_roots
sdk_from_ninja = _generic.sdk_from_ninja
dump = _generic.dump
sha = _generic.sha
check_no_old_bins = _generic.check_no_old_bins
_retention = _load('_id_map_product_retention', ROOT / 'scripts/verify-weighted-pool-retention.py')
retired_product_bindings = _retention.retired_product_bindings

SELECTORS = tuple('STAR_USE_RUST_' + name for name in (
    'LIGHTING BLOCKS_ALONG_LINE LINE_QUERY ENCODE SHA256 VLQ BYTES UNICODE SHELL '
    'JSON_PATH TEXT_SCAN COMPRESSION ZSTD DATA_STREAM BUFFER IO_DEVICE BYTE_ARRAY '
    'STRING_VIEW FILE PATH_EMBED LRU_CACHE TTL_CACHE WEIGHTED_POOL HOST_ADDRESS '
    'OPTION_PARSER JSON_PATCH ASSET_PATH RANDOM_MWC ID_MAP').split())
CAPS = dict(liveBytes=4 * 1024 ** 3, archiveBytes=16 * 1024 ** 3,
            newRootBytes=1536 * 1024 ** 2)
SCOPE = 'byte/source/tool admission only; no configure, compilation, runtime or game qualification'
DEADLINES = dict(maxAgeSeconds=35 * 60,
                 execution='parent owns bounded process supervision; no timeout waiver')
STAGE = 'ID_MAP_PREEXECUTION_COMPLETE_CACHE_TOOLS'
CHECKPOINT_ROLE = 'BASE_ONLY; current working-tree bytes authoritative'
TOOL_PLAN = 'build/weighted-pool-game-admission-r1/complete-r1/plan.json'
TOOL_PLAN_SHA = 'e890b99b615433d3557629bccd2a503c76e44b79d459bfa162d4ed9f7b0d9eb3'
EXCLUDED = frozenset(('CMAKE_EXECUTABLE', 'APPLE_TOOLCHAIN_SELECTOR'))
OLD_BASE = 'build/behavior/weighted-pool-combined-r1'
PRODUCT_PINS = dict(reference='57305ea18f2f11edff14826d8732bd5559115231673a19ebec0088302f44a09f',
                    candidate='8ea903429572485ddc3afb253c19d08f52a7bc3209e217342234d77ada97790b')
HEADER = 'source/lab/behavior/id_map_scene.hpp'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def profiles():
    return {role: {key: 'ON' if role == 'candidate' and key != 'STAR_USE_RUST_LINE_QUERY' else 'OFF'
                   for key in SELECTORS} for role in ('reference', 'candidate')}


def check_source_selectors():
    text = (ROOT / 'source/CMakeLists.txt').read_text()
    declared = re.findall(r'\b(?i:option)\s*\(\s*(STAR_USE_RUST_\w+)\b', text)
    rows = re.findall(r'\b(?i:option)\s*\(\s*(STAR_USE_RUST_\w+)\s+"[^"\n]*"\s+(ON|OFF)\s*\)', text)
    need(len(declared) == 29 and set(declared) == set(SELECTORS) and
         len(rows) == 29 and len(dict(rows)) == 29 and
         set(dict(rows)) == set(SELECTORS) and all(v == 'OFF' for _, v in rows),
         'actual source must declare exact 29 selectors, all default OFF')


def build_root(generation):
    need(type(generation) is int and generation > 0, 'positive integer generation required')
    return ROOT / ('build/behavior/id-map-combined-r' + str(generation))


def check_budget(root):
    archive = allocated(ROOT / 'build/migration-evidence-archive')
    live = allocated(ROOT / 'build') - archive
    current = allocated(root)
    need(0 <= archive <= CAPS['archiveBytes'], 'fixed 16 GiB archive cap')
    need(0 <= current <= CAPS['newRootBytes'] and 0 <= live <= CAPS['liveBytes'],
         'fixed live/new-root cap')
    need(live - current + CAPS['newRootBytes'] <= CAPS['liveBytes'],
         'new-root reservation exceeds fixed 4 GiB live cap')
    return dict(liveBytes=live, archiveBytes=archive, newRootBytes=current)


def check_retirement(path, pin):
    path = Path(path).absolute()
    protected = {ROOT / OLD_BASE / role / 'bin/starbound': digest
                 for role, digest in PRODUCT_PINS.items()}
    bindings, actual_pin = retired_product_bindings(ROOT, (path, pin), protected)
    need(set(bindings) == set(protected) and actual_pin == pin, 'exact retired original game pair')
    return dict(manifest=str(path), sha256=pin, physical=physical(path),
                products={str(p): row for p, row in bindings.items()},
                originState='UNAVAILABLE_ARCHIVED; no live inode or execution qualification')


def selected_paths(path, pin):
    """Only the external pin and selected paths survive the old-plan boundary."""
    path = Path(path).absolute()
    need(re.fullmatch('[0-9a-f]{64}', pin or '') is not None and sha(path) == pin,
         'externally pinned tool-selection plan required')
    old = json.loads(path.read_text())
    tools = old['tools']
    mandatory = {'CMAKE_EXECUTABLE', 'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER',
                 'CMAKE_AR', 'CMAKE_RANLIB', 'CMAKE_LINKER', 'CMAKE_MAKE_PROGRAM',
                 'STAR_CARGO_EXECUTABLE', 'STAR_RUSTC_EXECUTABLE', 'APPLE_TOOLCHAIN_SELECTOR'}
    need(type(tools) is dict and mandatory <= tools.keys(), 'complete selected tool paths required')
    for key, value in tools.items():
        need(re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', key) is not None and
             not key.startswith('STAR_USE_RUST_') and isinstance(value, str) and
             not any(c in value for c in '\n\r;'), 'tool path/argument schema')
        native(value)
        need(not Path(value).is_relative_to(ROOT / 'build') and
             not Path(physical(value)).is_relative_to(ROOT / 'build'), 'build product/archive cannot select tools')
    sdk = old['sdk']
    need(isinstance(sdk, str) and Path(sdk).is_absolute() and Path(sdk).is_dir(), 'selected SDK directory')
    need(not Path(sdk).is_relative_to(ROOT / 'build') and
         not Path(physical(sdk)).is_relative_to(ROOT / 'build'), 'build product/archive cannot select SDK')
    return dict(sorted(tools.items())), sdk


def source_roots(tools, sdk):
    roots = admission_roots(tools, sdk) + [str(ROOT / 'assets')]
    # Include selected tool packages/runtime trees, not archived tool copies.
    # System tools live in shared /usr/bin or /bin; their selected bytes are
    # additionally pinned individually instead of traversing the entire OS.
    for path in list(tools.values()) + list(map(str, auxiliary_tools())):
        package = Path(path).resolve(strict=True).parent.parent
        if str(package) not in ('/', '/usr'):
            roots.append(str(package))
    return list(dict.fromkeys(roots))


def check_member_scope(members):
    installed = ROOT / 'build/macos-arm-release/vcpkg_installed'
    for name, resolved in members.items():
        if Path(resolved).is_relative_to(ROOT / 'build'):
            need(Path(name).is_relative_to(installed) and Path(resolved).is_relative_to(installed),
                 'product/archive/source-copy cannot replace live source/tool input: ' + name)


def retained_objects():
    base = ROOT / OLD_BASE / 'reference/cmake'
    objects = sorted(str(p) for directory in ('core', 'extern')
                     for p in (base / directory).rglob('*.o'))
    need(len(objects) == 113 and len(set(objects)) == 113, 'retain original 113 reference Core/extern objects')
    for path in objects:
        no_symlink_parents(path)
        need(Path(path).is_file(), 'missing retained reference object')
    return objects


def commands(plan, role):
    need(role in ('reference', 'candidate'), 'exact backend role required')
    tools = plan['tools']
    root = Path(plan['buildRoot']) / role
    configure = [tools['CMAKE_EXECUTABLE'], '--preset', 'macos-arm-release', '-B', str(root / 'cmake')]
    configure += ['-D' + key + '=' + tools[key] for key in sorted(tools) if key not in EXCLUDED]
    configure += ['-D' + key + '=' + value for key, value in profiles()[role].items()]
    configure += ['-DCMAKE_OSX_SYSROOT=' + plan['sdk'], '-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON',
                  '-DCMAKE_VERBOSE_MAKEFILE=OFF', '-DBUILD_TESTING=OFF',
                  '-DSTAR_ENABLE_STEAM_INTEGRATION=OFF', '-DSTAR_ENABLE_DISCORD_INTEGRATION=OFF',
                  '-DSTAR_BUILD_LIGHTING_LAB=OFF', '-DSTAR_RUNTIME_OUTPUT_DIRECTORY=' + str(root / 'bin'),
                  '-DVCPKG_MANIFEST_INSTALL=OFF',
                  '-DVCPKG_INSTALLED_DIR=' + str(ROOT / 'build/macos-arm-release/vcpkg_installed')]
    cache_keys = [word[2:].partition('=')[0] for word in configure if word.startswith('-D')]
    need(len(cache_keys) == len(set(cache_keys)), 'conflicting future cache arguments')
    return dict(configure=configure,
                build=[tools['CMAKE_EXECUTABLE'], '--build', str(root / 'cmake'), '--target', 'starbound',
                       '--parallel', '6', '--', '-d', 'keepdepfile'])


def _pin(witness, paths):
    for path in map(Path, paths):
        witness['aliases'][str(path)] = physical(path)
        witness['files'][physical(path)] = sha(path)


def _require_pin(witness, path, label):
    name = str(path)
    need(witness['aliases'].get(name, physical(path)) == physical(path) and
         witness['files'].get(physical(path)) == sha(path), 'missing/changed admitted ' + label + ': ' + name)


def check_deadline(plan):
    need(plan['deadlines'] == DEADLINES, 'immutable admission deadlines')
    created = dt.datetime.fromisoformat(plan['createdUTC'])
    need(created.tzinfo is not None, 'timezone-aware creation required')
    age = (dt.datetime.now(dt.timezone.utc) - created).total_seconds()
    need(0 <= age < DEADLINES['maxAgeSeconds'], 'admission deadline reached')


def validate(plan):
    need(plan['stage'] == STAGE, 'wrong IdMap admission stage')
    need(plan['scope'] == SCOPE and plan['caps'] == CAPS, 'immutable admission scope/caps')
    check_deadline(plan)
    need(re.fullmatch('[0-9a-f]{40}', plan['sourceCheckpoint']) is not None and
         plan['checkpointRole'] == CHECKPOINT_ROLE, 'full BASE_ONLY source checkpoint')
    root = build_root(plan['generation'])
    need(plan['buildRoot'] == str(root), 'exact IdMap generation build root')
    no_symlink_parents(root)
    need(plan['profiles'] == profiles(), 'fixed 29-selector profiles')
    check_source_selectors()
    tools, sdk = selected_paths(plan['toolPlan'], plan['toolPlanSha256'])
    need(plan['toolPlanRole'] == 'PATH_SELECTION_ONLY; historical admission NOT reused', 'tool-plan role')
    need(plan['tools'] == tools and plan['sdk'] == sdk and plan['sdkPhysical'] == physical(sdk),
         'selected current tool/SDK paths or alias changed')
    need(plan['commands'] == {role: commands(plan, role) for role in profiles()}, 'future argv drift')
    need(plan['configureCwd'] == str(ROOT / 'source'), 'configure working directory')
    need(plan['retirement'] == check_retirement(plan['retirement']['manifest'], plan['retirement']['sha256']),
         'retirement selection changed')
    check_no_old_bins(root)
    check_budget(root)
    roots = source_roots(tools, sdk)
    need(plan['sourceRoots'] == roots, 'complete immutable source/tool root scope')
    members = tree_members(roots)
    need(members == plan['treeMembers'], 'source/tool tree membership changed')
    check_member_scope(members)
    witness = plan['witness']
    for path, resolved in plan['treeMembers'].items():
        if Path(path).is_file():
            need(resolved in witness['files'], 'unhashed source/tool input: ' + path)
    objects = retained_objects()
    need(plan['retainedReferenceObjects'] == objects, 'original reference object membership changed')
    for path in list(tools.values()) + list(map(str, auxiliary_tools())):
        native(path)
        need(witness['aliases'].get(str(path)) == physical(path), 'missing tool alias')
        _require_pin(witness, path, 'native tool')
    for path in objects + [plan['toolPlan']] + [r for r in roots if Path(r).is_file()]:
        _require_pin(witness, path, 'input')
    header = ROOT / HEADER
    need(plan['compiledHeader'] == dict(path=str(header), physical=physical(header), sha256=sha(header),
         role='DECLARED_FUTURE_COMPILE_DEPENDENCY; not yet compiled'), 'exact declared compiled header')
    _require_pin(witness, header, 'declared compiled header')
    for path in (ROOT / 'scripts/build-id-map-behavior-lab.py',
                 ROOT / 'source/lab/behavior/build_provenance.py', Path(__file__).resolve()):
        _require_pin(witness, path, 'actual builder/provenance/admission tool')
    unchanged(witness)
    check_deadline(plan)
    return root


def prepare(output, checkpoint, generation, retirement, retirement_sha,
            tool_plan=None, tool_plan_sha=TOOL_PLAN_SHA):
    created = dt.datetime.now(dt.timezone.utc).isoformat()
    output = Path(output).absolute()
    need(re.fullmatch('[0-9a-f]{40}', checkpoint or '') is not None, 'explicit full checkpoint required')
    root = build_root(generation)
    no_symlink_parents(output)
    no_symlink_parents(root)
    need(not os.path.lexists(output) and not os.path.lexists(root), 'fresh output/build root required')
    # Cheap fail-closed resource/product gates precede the expensive SDK witness
    # and EVERY output mutation. The currently live old pair must fail here.
    check_no_old_bins(root)
    retired = check_retirement(retirement, retirement_sha)
    budget = check_budget(root)
    check_source_selectors()
    tool_plan = Path(tool_plan if tool_plan is not None else ROOT / TOOL_PLAN).absolute()
    tools, sdk = selected_paths(tool_plan, tool_plan_sha)
    roots = source_roots(tools, sdk)
    for path in (output, root):
        need(not any(path.is_relative_to(Path(r)) or Path(r).is_relative_to(path) for r in roots),
             'generated output overlaps admitted source/tool tree')
    members = tree_members(roots)
    check_member_scope(members)
    witness = closure([Path(r) for r in roots if Path(r).is_dir()])
    objects = retained_objects()
    auxiliary = auxiliary_tools()
    for path in auxiliary:
        native(path)
    _pin(witness, list(tools.values()) + auxiliary + objects + [tool_plan] +
         [r for r in roots if Path(r).is_file()])
    header = ROOT / HEADER
    plan = dict(stage=STAGE, scope=SCOPE, caps=dict(CAPS), deadlines=dict(DEADLINES),
        createdUTC=created, sourceCheckpoint=checkpoint,
        checkpointRole=CHECKPOINT_ROLE, generation=generation, buildRoot=str(root),
        profiles=profiles(), tools=tools, sdk=sdk, sdkPhysical=physical(sdk),
        toolPlan=str(tool_plan), toolPlanSha256=tool_plan_sha,
        toolPlanRole='PATH_SELECTION_ONLY; historical admission NOT reused',
        retirement=retired, budgetBefore=budget, sourceRoots=roots, treeMembers=members,
        witness=witness, retainedReferenceObjects=objects, configureCwd=str(ROOT / 'source'),
        compiledHeader=dict(path=str(header), physical=physical(header), sha256=sha(header),
                            role='DECLARED_FUTURE_COMPILE_DEPENDENCY; not yet compiled'))
    plan['commands'] = {role: commands(plan, role) for role in profiles()}
    validate(plan)
    output.mkdir(parents=False)
    dump(output / 'plan.json', plan)
    return plan


def check_configured(plan, build):
    build = Path(build).absolute()
    root = Path(plan['buildRoot'])
    need(build in [root / role / 'cmake' for role in profiles()], 'exact admitted backend/cmake path')
    no_symlink_parents(build)
    role = build.parent.name
    cache, ninja = build / 'CMakeCache.txt', build / 'build.ninja'
    need(selection(cache) == plan['tools'], 'unadmitted configured executable selection')
    rows = re.findall(r'^(STAR_USE_RUST_\w+):[^=\n]+=(.*)$', cache.read_text(), re.M)
    need(len(rows) == 29 and len(dict(rows)) == 29 and dict(rows) == profiles()[role],
         'actual exact 29-selector cache vector')
    need(sdk_from_ninja(ninja) == plan['sdk'], 'configured SDK root differs')
    database = build / 'compile_commands.json'
    rows = json.loads(database.read_text())
    client = [row for row in rows if Path(row['file']).name == 'StarClientApplication.cpp']
    need(len(client) == 1, 'exactly one actual client compile command')
    row = client[0]
    words = row.get('arguments')
    if words is None:
        words = shlex.split(row['command'])
    need(isinstance(words, list) and all(isinstance(word, str) for word in words), 'compile argv schema')
    macros = []
    for index, word in enumerate(words):
        if word in ('-D', '-U'):
            need(index + 1 < len(words), 'missing macro argument')
            word += words[index + 1]
        if word.startswith(('-DSTAR_USE_RUST_', '-USTAR_USE_RUST_')):
            need(word.startswith('-D'), 'selector undefinition in actual client compile')
            macros.append(word[2:])
    expected = {key for key, value in profiles()[role].items() if value == 'ON'}
    need(len(macros) == len(expected) and set(macros) == expected, 'actual client macro vector')
    need(words[0] == plan['tools']['CMAKE_CXX_COMPILER'], 'actual client compiler selection')
    sdks = [words[i + 1] for i, word in enumerate(words[:-1]) if word == '-isysroot']
    need(sdks == [plan['sdk']], 'actual client SDK selection')
    need(words.count('-o') == 1 and words.index('-o') < len(words) - 1, 'one client object output required')
    directory = Path(row['directory'])
    need(directory.is_absolute(), 'absolute client compile working directory')
    obj = Path(words[words.index('-o') + 1])
    obj = obj if obj.is_absolute() else directory / obj
    need('..' not in obj.parts and obj.is_relative_to(build) and obj.suffix == '.o', 'client object output scope')
    no_symlink_parents(obj)
    source = Path(row['file'])
    source = source if source.is_absolute() else directory / source
    need(source == ROOT / 'source/client/StarClientApplication.cpp', 'actual client source path')
    need(words.count('-c') == 1 and words.index('-c') < len(words) - 1, 'one client compilation input required')
    actual_source = Path(words[words.index('-c') + 1])
    actual_source = actual_source if actual_source.is_absolute() else directory / actual_source
    need(actual_source == source, 'client compile argv/source metadata mismatch')
    return dict(selectedTools=plan['tools'], cacheSha256=sha(cache), ninjaSha256=sha(ninja),
        compileCommandsSha256=sha(database), backend=role, selectors=profiles()[role],
        clientObject=str(obj), clientDepfile=str(obj) + '.d', compiledHeader=plan['compiledHeader'],
        scope='configuration reconciled before bulk compilation; header dependency DECLARED, NOT yet compiled; NOT game qualification')


def configured(plan, plan_sha, build):
    need(re.fullmatch('[0-9a-f]{64}', plan_sha or '') is not None, 'external plan SHA256 required')
    validate(plan)
    build = Path(build).absolute()
    receipt = check_configured(plan, build)
    receipt['planSha256'] = plan_sha
    unchanged(plan['witness'])
    need(tree_members(plan['sourceRoots']) == plan['treeMembers'], 'source membership changed during configured check')
    check_deadline(plan)
    path = build.parent / 'complete-tool-admission.json'
    no_symlink_parents(path)
    if os.path.lexists(path):
        need(path.is_file() and json.loads(path.read_text()) == receipt, 'nonidentical complete tool receipt exists')
    else:
        dump(path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'before', 'configured'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--checkpoint')
    parser.add_argument('--generation', type=int)
    parser.add_argument('--retirement', type=Path)
    parser.add_argument('--retirement-sha')
    parser.add_argument('--tool-plan', type=Path, default=ROOT / TOOL_PLAN)
    parser.add_argument('--tool-plan-sha', default=TOOL_PLAN_SHA)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--sha')
    parser.add_argument('--build', type=Path)
    args = parser.parse_args()
    if args.phase == 'prepare':
        need(args.output is not None and args.retirement is not None, 'output and retirement required')
        prepare(args.output, args.checkpoint, args.generation, args.retirement, args.retirement_sha,
                args.tool_plan, args.tool_plan_sha)
        print(sha(args.output / 'plan.json'))
        return
    need(args.plan is not None and args.sha == sha(args.plan), 'externally pinned admission plan required')
    plan = json.loads(args.plan.read_text())
    if args.phase == 'configured':
        need(args.build is not None, 'configured directory required')
        configured(plan, args.sha, args.build)
    else:
        validate(plan)
    print('COMPLETE_ID_MAP_TOOL_SOURCE_ADMISSION_PASS')


if __name__ == '__main__':
    main()
