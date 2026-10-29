#!/usr/bin/env python3
"""Byte/source/tool admission only; never configures, builds, restores or qualifies a game.

The checkpoint names a BASE_ONLY commit. The witness, not git cleanliness, binds
all current working-tree inputs (including uncommitted admission/recipe changes).
Retired live inode seals are deliberately not reused as current evidence.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'source/lab'))
from migration.archive_blobs import open_blob
sys.path.insert(0, str(ROOT / 'source/lab/ttl-production'))
from game_syntax import closure, unchanged
sys.path.insert(0, str(ROOT / 'source/lab/ttl-rust'))
from guarded_canonical import selection
for name, directory in [('game_syntax', 'ttl-production'), ('common', 'ttl-rust'),
                        ('canonical', 'ttl-rust'), ('guarded_canonical', 'ttl-rust')]:
    if Path(sys.modules[name].__file__).resolve() != ROOT / f'source/lab/{directory}/{name}.py':
        raise ImportError('ambiguous admission helper import: ' + name)

EXCLUDED = {'CMAKE_EXECUTABLE', 'APPLE_TOOLCHAIN_SELECTOR'}
GIB = 1024 ** 3
CAPS = dict(liveBytes=4 * GIB, archiveBytes=16 * GIB, newRootBytes=1536 * 1024 ** 2)
RETIREMENT = 'build/migration-evidence-archive/runs/20261028-weighted-prebuild-retire-ttl-bins-r1/manifest.json'
RETIREMENT_SHA = '32e1ab38649e407280cd9c44cc13c38460e166716601159c4ac74ea21c6ba7ab'
PRESERVED = 'build/weighted-pool-game-admission-r1/retire-selection.json'
PRESERVED_SHA = 'eeb88a6d7967916b58da8ec17bbfcd65fc3167407ec9724f1e36072a35ad35b4'
SEED = 'build/behavior/ttl-cache-combined-r2/reference/cmake/CMakeCache.txt'
SELECTORS = tuple('STAR_USE_RUST_' + x for x in (
    'LIGHTING BLOCKS_ALONG_LINE LINE_QUERY ENCODE SHA256 VLQ BYTES UNICODE SHELL '
    'JSON_PATH TEXT_SCAN COMPRESSION ZSTD DATA_STREAM BUFFER IO_DEVICE BYTE_ARRAY '
    'STRING_VIEW FILE PATH_EMBED LRU_CACHE TTL_CACHE WEIGHTED_POOL HOST_ADDRESS '
    'OPTION_PARSER JSON_PATCH ASSET_PATH RANDOM_MWC').split())
SCOPE = 'byte/source/tool admission only; no configure, compilation, runtime or game qualification'
DEADLINES = dict(maxAgeSeconds=35 * 60,
                 execution='parent owns bounded process supervision; no timeout waiver')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def physical(path):
    return str(Path(path).resolve(strict=True))


def lexists(path):
    return os.path.lexists(path)


def no_symlink_parents(path):
    for part in (Path(path), *Path(path).parents):
        need(not part.is_symlink(), 'symlink build/admission path: ' + str(part))


def native(path):
    need(Path(path).is_absolute() and Path(path).is_file() and os.access(path, os.X_OK), 'nonexecutable tool')
    with Path(path).open('rb') as stream:
        magic = stream.read(4)
    need(magic in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                   b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
                   b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca', b'\x7fELF'),
         'non-native tool/wrapper: ' + str(path))


def sdk_from_ninja(path):
    sdks = set()
    for line in Path(path).read_text().splitlines():
        if line.startswith('  FLAGS = '):
            words = shlex.split(line.partition(' = ')[2])
            for i, word in enumerate(words):
                if word == '-isysroot':
                    need(i + 1 < len(words), 'missing actual SDK argument')
                    sdks.add(words[i + 1])
    need(len(sdks) == 1, 'one actual -isysroot SDK required, not empty OSX cache')
    sdk = Path(next(iter(sdks)))
    need(sdk.is_absolute() and sdk.is_dir(), 'actual SDK must be an absolute directory')
    return str(sdk)


def profiles():
    return {role: {key: 'ON' if role == 'candidate' and key != 'STAR_USE_RUST_LINE_QUERY' else 'OFF'
                   for key in SELECTORS} for role in ('reference', 'candidate')}


def tree_members(roots):
    """Membership complements unchanged(): newly added inputs must also fail closed."""
    result = {}
    for root in map(Path, roots):
        need(root.exists(), 'missing source/tool root: ' + str(root))
        if root.is_file():
            result[str(root)] = physical(root)
            continue
        seen = set()
        for base, dirs, names in os.walk(root, followlinks=True):
            resolved = physical(base)
            if resolved in seen:
                dirs[:] = []
                continue
            seen.add(resolved)
            dirs[:] = sorted(d for d in dirs if d not in ('__pycache__', '.git'))
            for name in dirs + sorted(names):
                p = Path(base) / name
                result[str(p)] = physical(p)
    return result


def allocated(root):
    seen, total = set(), 0
    if not lexists(root):
        return 0
    for base, dirs, names in os.walk(root, followlinks=False):
        for p in [Path(base)] + [Path(base) / n for n in dirs + names]:
            s = p.lstat()
            identity = (s.st_dev, s.st_ino)
            if identity not in seen:
                seen.add(identity)
                total += s.st_blocks * 512
    return total


def check_budget(build_root):
    archive = allocated(ROOT / 'build/migration-evidence-archive')
    live = allocated(ROOT / 'build') - archive
    current = allocated(build_root)
    need(archive <= CAPS['archiveBytes'], 'fixed 16 GiB archive cap')
    need(live <= CAPS['liveBytes'] and current <= CAPS['newRootBytes'], 'fixed live/new-root cap')
    need(live - current + CAPS['newRootBytes'] <= CAPS['liveBytes'], 'new-root reservation exceeds fixed 4 GiB live cap')
    return dict(liveBytes=live, archiveBytes=archive, newRootBytes=current)


def expected_retired():
    return {f'build/behavior/ttl-cache-combined-r2/{role}/bin/{name}'
            for role in ('reference', 'candidate')
            for name in ('imgui.ini', 'starbound', 'starbound.behavior-build.json')}


def check_retirement():
    manifest = ROOT / RETIREMENT
    need(sha(manifest) == RETIREMENT_SHA, 'retirement manifest physical pin')
    data = json.loads(manifest.read_text())
    need(data['status'] == 'ARCHIVED_VERIFIED_PRUNED', 'retirement status')
    entries = data['entries']
    need(len(entries) == 6 and {e['path'] for e in entries} == expected_retired(), 'exact six retired bin members')
    need(set(data['roots']) == {f'build/behavior/ttl-cache-combined-r2/{r}/bin' for r in ('reference', 'candidate')}, 'retirement roots')
    verified = {}
    for entry in entries:
        need(not lexists(ROOT / entry['path']), 'retired live member reappeared')
        digest = entry['sha256']
        need(re.fullmatch('[0-9a-f]{64}', digest), 'invalid archive digest')
        if digest not in verified:
            h, size = hashlib.sha256(), 0
            with open_blob(ROOT / 'build/migration-evidence-archive', digest) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
                    size += len(block)
            need(h.hexdigest() == digest, 'retired archive reconstruction hash')
            verified[digest] = size
        need(verified[digest] == entry['size'], 'retired archive reconstruction size')
    preserved = ROOT / PRESERVED
    need(sha(preserved) == PRESERVED_SHA, 'externally pinned preservation selection')
    protection = json.loads(preserved.read_text())
    need(len(protection['protected']) == 1032, 'entire 1032-file complement required')
    for path, digest in protection['protected'].items():
        need(not Path(path).is_symlink() and sha(path) == digest, 'preserved complement bytes: ' + path)
    for path, target in protection['protectedSymlinks'].items():
        need(Path(path).is_symlink() and os.readlink(path) == target, 'preserved complement symlink')
    for role in ('reference', 'candidate'):
        objects = [p for p in protection['protected'] if f'/{role}/cmake/' in p
                   and p.endswith('.o') and any('/' + x + '/' in p for x in ('core', 'extern'))]
        need(len(objects) == 113, '113 preserved objects per backend')
    return dict(manifest=str(manifest), sha256=RETIREMENT_SHA, physical=physical(manifest),
                preservationSelection=str(preserved), preservationSha256=PRESERVED_SHA,
                preservationPhysical=physical(preserved))


def check_no_old_bins(build_root):
    need(not lexists(ROOT / 'build/.migration-cleanup.lock'), 'cleanup lock active')
    behavior = ROOT / 'build/behavior'
    bins = [behavior / role / 'bin' for role in ('reference', 'candidate')]
    if behavior.is_dir():
        for generation in behavior.iterdir():
            bins += [generation / role / 'bin' for role in ('reference', 'candidate')]
    # glob with a final literal can omit DANGLING symlinks on older Python.
    # Enumerate parents, then lstat via lexists; never infer absence from glob.
    for directory in bins:
        if not directory.is_relative_to(build_root):
            need(not directory.is_symlink() and not lexists(directory / 'starbound'),
                 'old game binary/symlink remains: ' + str(directory / 'starbound'))


def validate(plan):
    need(plan['stage'] == 'WEIGHTED_POOL_PREEXECUTION_COMPLETE_CACHE_TOOLS', 'wrong admission stage')
    need(plan['caps'] == CAPS and plan['scope'] == SCOPE, 'immutable budget/scope')
    need(plan['deadlines'] == DEADLINES, 'immutable admission deadlines')
    created = dt.datetime.fromisoformat(plan['createdUTC'])
    need(created.tzinfo is not None, 'admission creation must be timezone-aware')
    age = (dt.datetime.now(dt.timezone.utc) - created).total_seconds()
    need(0 <= age < DEADLINES['maxAgeSeconds'], 'admission deadline reached')
    need(re.fullmatch('[0-9a-f]{40}', plan['sourceCheckpoint']) is not None, 'full BASE_ONLY checkpoint')
    need(plan['checkpointRole'] == 'BASE_ONLY; current working-tree bytes authoritative', 'checkpoint role')
    generation = str(plan['generation'])
    need(re.fullmatch('[1-9][0-9]*', generation) is not None, 'positive build generation')
    build_root = ROOT / ('build/behavior/weighted-pool-combined-r' + generation)
    need(plan['buildRoot'] == str(build_root), 'exact generation build root')
    no_symlink_parents(build_root)
    need(plan['profiles'] == profiles(), 'fixed 28-selector profiles')
    actual_selectors = re.findall(r'option\((STAR_USE_RUST_\w+)', (ROOT / 'source/CMakeLists.txt').read_text())
    need(len(actual_selectors) == 28 and set(actual_selectors) == set(SELECTORS), 'source selector schema changed')
    seed = ROOT / SEED
    need(plan['seedCache'] == str(seed) and plan['seedPhysical'] == physical(seed)
         and plan['seedCacheSha256'] == sha(seed), 'seed physical/byte pin')
    need(plan['seedNinjaSha256'] == sha(seed.parent / 'build.ninja'), 'seed compiler flags pin')
    need(plan['tools'] == selection(seed), 'selected seed cache tools changed')
    need(plan['sdk'] == sdk_from_ninja(seed.parent / 'build.ninja'), 'actual SDK selection changed')
    need(plan['sdkPhysical'] == physical(plan['sdk']), 'SDK alias changed')
    for key, path in plan['tools'].items():
        native(path)
        need(plan['witness']['aliases'].get(path) == physical(path) and
             plan['witness']['files'].get(physical(path)) == sha(path), 'missing pre-execution tool: ' + key)
    arguments = ['-D' + k + '=' + v for k, v in plan['tools'].items() if k not in EXCLUDED]
    need(Path(plan['argumentFile']).read_text().splitlines() == arguments and
         sha(plan['argumentFile']) == plan['argumentSha256'], 'every cache executable fixed in future argv')
    need(Path(plan['launcherFile']).read_text().splitlines() == [plan['tools']['CMAKE_EXECUTABLE'],
         plan['tools']['CMAKE_MAKE_PROGRAM'], plan['sdk']] and
         sha(plan['launcherFile']) == plan['launcherSha256'], 'fixed launcher bytes/SDK')
    need(plan['retirement'] == check_retirement(), 'retirement physical selection changed')
    check_no_old_bins(build_root)
    check_budget(build_root)
    need(plan['sourceRoots'] == admission_roots(plan['tools'], plan['sdk']), 'complete immutable source/tool root scope')
    need(tree_members(plan['sourceRoots']) == plan['treeMembers'], 'source/tool tree membership changed')
    for path, resolved in plan['treeMembers'].items():
        if Path(path).is_file():
            need(resolved in plan['witness']['files'], 'unhashed source/tool input: ' + path)
    for path in auxiliary_tools():
        native(path)
        need(plan['witness']['aliases'].get(str(path)) == physical(path) and
             plan['witness']['files'].get(physical(path)) == sha(path), 'missing pre-execution support tool: ' + str(path))
    unchanged(plan['witness'])
    return build_root


def auxiliary_tools():
    return [Path('/bin/bash'), Path('/usr/bin/python3'), Path(sys.executable),
            Path('/usr/bin/uname'), Path('/usr/bin/dirname'), Path('/usr/bin/git')]


def admission_roots(tools, sdk):
    compiler_usr = Path(tools['CMAKE_CXX_COMPILER']).resolve().parent.parent
    rust_usr = Path(tools['STAR_RUSTC_EXECUTABLE']).resolve().parent.parent
    roots = [ROOT / d for d in ('source', 'scripts', 'cmake', 'toolchains', 'triplets', 'lib', 'nix')]
    roots += [ROOT / 'flake.nix', ROOT / 'flake.lock', Path(sdk), compiler_usr / 'include',
              compiler_usr / 'lib', rust_usr / 'lib', Path(tools['CMAKE_EXECUTABLE']).resolve().parents[1],
              ROOT / 'build/macos-arm-release/vcpkg_installed',
              Path('/Users/bdsqqq/.cache/openstarbound-vcpkg/scripts'),
              Path('/Users/bdsqqq/.cache/openstarbound-vcpkg/triplets'), Path(sys.prefix)]
    return list(dict.fromkeys(map(str, roots)))


def prepare(output):
    checkpoint = os.environ.get('STAR_WEIGHTED_POOL_SOURCE_CHECKPOINT', '')
    need(re.fullmatch('[0-9a-f]{40}', checkpoint) is not None, 'explicit full source checkpoint required')
    generation = os.environ.get('STAR_BEHAVIOR_WEIGHTED_POOL_GENERATION', '1')
    need(re.fullmatch('[1-9][0-9]*', generation) is not None, 'positive generation required')
    build_root = ROOT / ('build/behavior/weighted-pool-combined-r' + generation)
    no_symlink_parents(output)
    no_symlink_parents(build_root)
    need(not lexists(output) and not lexists(build_root), 'fresh admission output and build root required')
    check_no_old_bins(build_root)
    retirement = check_retirement()
    budget = check_budget(build_root)
    seed = ROOT / SEED
    tools = selection(seed)
    for path in tools.values():
        native(path)
    sdk = sdk_from_ninja(seed.parent / 'build.ninja')
    roots = list(map(Path, admission_roots(tools, sdk)))
    # Check every root, including the root-level files closure() does not walk.
    members = tree_members(roots)
    witness = closure([r for r in roots if r.is_dir()])
    auxiliary = auxiliary_tools()
    output.mkdir(parents=False)
    argfile, launchers = output / 'tool-args.txt', output / 'launcher-paths.txt'
    arguments = ['-D' + k + '=' + v for k, v in tools.items() if k not in EXCLUDED]
    need(not any('\n' in a or '\r' in a for a in arguments), 'unrepresentable tool argument')
    argfile.write_text('\n'.join(arguments) + '\n')
    launchers.write_text('\n'.join([tools['CMAKE_EXECUTABLE'], tools['CMAKE_MAKE_PROGRAM'], sdk]) + '\n')
    for path in list(map(Path, tools.values())) + auxiliary + [seed, seed.parent / 'build.ninja', argfile, launchers] + [r for r in roots if r.is_file()]:
        witness['aliases'][str(path)] = physical(path)
        witness['files'][physical(path)] = sha(path)
    for path in auxiliary:
        native(path)
    plan = dict(stage='WEIGHTED_POOL_PREEXECUTION_COMPLETE_CACHE_TOOLS', tools=tools,
        seedCache=str(seed), seedPhysical=physical(seed), seedCacheSha256=sha(seed),
        seedNinjaSha256=sha(seed.parent / 'build.ninja'), argumentFile=str(argfile), argumentSha256=sha(argfile),
        launcherFile=str(launchers), launcherSha256=sha(launchers), witness=witness,
        sdk=sdk, sdkPhysical=physical(sdk), sourceCheckpoint=checkpoint,
        checkpointRole='BASE_ONLY; current working-tree bytes authoritative', scope=SCOPE,
        generation=int(generation), buildRoot=str(build_root), profiles=profiles(),
        caps=CAPS, budgetBefore=budget, retirement=retirement, sourceRoots=list(map(str, roots)),
        treeMembers=members, createdUTC=dt.datetime.now(dt.timezone.utc).isoformat(),
        deadlines=DEADLINES)
    validate(plan)
    dump(output / 'plan.json', plan)
    print(sha(output / 'plan.json'))


def check_configured(plan, build):
    build_root = Path(plan['buildRoot'])
    need(build in [build_root / role / 'cmake' for role in ('reference', 'candidate')], 'exact admitted backend/cmake path required')
    no_symlink_parents(build)
    role = build.parent.name
    cache, ninja = build / 'CMakeCache.txt', build / 'build.ninja'
    need(selection(cache) == plan['tools'], 'unadmitted configured executable selection')
    rows = re.findall(r'^(STAR_USE_RUST_\w+):[^=\n]+=(.*)$', cache.read_text(), re.M)
    need(len(rows) == 28 and dict(rows) == plan['profiles'][role], 'actual exact 28-selector cache vector')
    need(sdk_from_ninja(ninja) == plan['sdk'], 'configured SDK root differs')
    commands = json.loads((build / 'compile_commands.json').read_text())
    client = [row for row in commands if Path(row['file']).name == 'StarClientApplication.cpp']
    need(len(client) == 1, 'exactly one actual client compile command')
    words = client[0].get('arguments')
    if words is None:
        words = shlex.split(client[0]['command'])
    macros = [word[2:] for word in words if word.startswith('-DSTAR_USE_RUST_')]
    expected = {k for k, v in plan['profiles'][role].items() if v == 'ON'}
    need(len(macros) == len(expected) and set(macros) == expected, 'actual client macro vector')
    need(words[0] == plan['tools']['CMAKE_CXX_COMPILER'], 'actual client compiler selection')
    sdks = [words[i + 1] for i, word in enumerate(words[:-1]) if word == '-isysroot']
    need(sdks == [plan['sdk']], 'actual client SDK selection')
    return dict(selectedTools=plan['tools'], cacheSha256=sha(cache), ninjaSha256=sha(ninja),
                compileCommandsSha256=sha(build / 'compile_commands.json'), backend=role,
                selectors=plan['profiles'][role], scope='configuration reconciled before bulk compilation; NOT game qualification')


def configured(plan, plan_sha, build):
    validate(plan)
    receipt = check_configured(plan, build)
    receipt['planSha256'] = plan_sha
    unchanged(plan['witness'])
    need(tree_members(plan['sourceRoots']) == plan['treeMembers'], 'source membership changed during configured check')
    path = build.parent / 'complete-tool-admission.json'
    if path.exists():
        need(not path.is_symlink() and json.loads(path.read_text()) == receipt, 'nonidentical complete tool receipt exists')
    else:
        dump(path, receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'before', 'configured'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--sha')
    parser.add_argument('--build', type=Path)
    args = parser.parse_args()
    if args.phase == 'prepare':
        need(args.output is not None, 'output required')
        prepare(args.output.absolute())
        return
    need(args.plan is not None and args.sha == sha(args.plan), 'externally pinned admission plan required')
    plan = json.loads(args.plan.read_text())
    need(Path(plan['argumentFile']) == args.plan.absolute().parent / 'tool-args.txt' and
         Path(plan['launcherFile']) == args.plan.absolute().parent / 'launcher-paths.txt',
         'launcher/argument files must be adjacent to pinned plan')
    if args.phase == 'configured':
        need(args.build is not None, 'configured directory required')
        configured(plan, args.sha, args.build.absolute())
    else:
        validate(plan)
    print('COMPLETE_WEIGHTED_POOL_TOOL_SOURCE_ADMISSION_PASS')


if __name__ == '__main__':
    main()
