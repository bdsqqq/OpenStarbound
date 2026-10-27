#!/usr/bin/env python3
"""Before-execution tool/source admission for the single fresh TTL game pair.

Reuses the accepted cache-executable selector, not a guessed compiler-only list.
This is build admission only: it cannot qualify runtime or renew old receipts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
from game_syntax import closure, unchanged
sys.path.insert(0, str(ROOT / 'source/lab/ttl-rust'))
from guarded_canonical import selection
assert Path(selection.__code__.co_filename).resolve() == ROOT / 'source/lab/ttl-rust/guarded_canonical.py'
for module in ('common', 'canonical', 'guarded_canonical'):
    assert Path(sys.modules[module].__file__).resolve() == ROOT / ('source/lab/ttl-rust/' + module + '.py'), 'ambiguous admission helper import'

EXCLUDED = {'CMAKE_EXECUTABLE', 'APPLE_TOOLCHAIN_SELECTOR'}

def need(ok, why):
    if not ok:
        raise ValueError(why)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')

def validate(plan):
    need(plan['tools'] == selection(plan['seedCache']), 'selected seed tool set changed')
    need(sha(plan['seedCache']) == plan['seedCacheSha256'], 'seed bytes changed')
    need(sha(plan['argumentFile']) == plan['argumentSha256'], 'fixed argument bytes changed')
    need(Path(plan['launcherFile']).read_text().splitlines() ==
         [plan['tools']['CMAKE_EXECUTABLE'], plan['tools']['CMAKE_MAKE_PROGRAM'], plan['sdk']], 'fixed build launchers/SDK changed')
    arguments = Path(plan['argumentFile']).read_text().splitlines()
    need(arguments == ['-D' + k + '=' + v for k, v in plan['tools'].items() if k not in EXCLUDED], 'every cache executable must be fixed in future argv')
    for name, path in plan['tools'].items():
        physical = str(Path(path).resolve(strict=True))
        need(plan['witness']['aliases'].get(path) == physical and
             plan['witness']['files'].get(physical) == sha(path), 'missing pre-execution tool: ' + name)
    unchanged(plan['witness'])

def prepare(output):
    import re
    need(re.fullmatch(r'[0-9a-f]{40}', os.environ.get('STAR_TTL_SOURCE_CHECKPOINT', '')) is not None, 'explicit full source checkpoint required')
    need(not output.exists(), 'fresh build admission directory required')
    output.mkdir()
    seed = ROOT / 'build/ttl-production-r1/cmake-default/CMakeCache.txt'
    tools = selection(seed)
    args = ['-D' + k + '=' + v for k, v in tools.items() if k not in EXCLUDED]
    need(not any('\n' in a or '\r' in a for a in args), 'unrepresentable tool path')
    argfile = output / 'tool-args.txt'
    argfile.write_text('\n'.join(args) + '\n')
    # CMake's cache may leave OSX_SYSROOT EMPTY while its actual compiler rules
    # select a concrete SDK. Never interpret an empty cache path as cwd.
    import shlex
    sdk_paths = set()
    for line in (seed.parent / 'build.ninja').read_text().splitlines():
        if line.startswith('  FLAGS = '):
            words = shlex.split(line.partition(' = ')[2])
            for i, word in enumerate(words):
                if word == '-isysroot':
                    sdk_paths.add(words[i + 1])
    need(len(sdk_paths) == 1, 'one actual configured compiler SDK required')
    sdk = Path(next(iter(sdk_paths)))
    need(sdk.is_absolute() and sdk.is_dir(), 'absolute actual SDK, NEVER empty/cwd')
    launchers = output / 'launcher-paths.txt'
    launchers.write_text(tools['CMAKE_EXECUTABLE'] + '\n' + tools['CMAKE_MAKE_PROGRAM'] + '\n' + str(sdk) + '\n')
    compiler_usr = Path(tools['CMAKE_CXX_COMPILER']).resolve().parent.parent
    rust_usr = Path(tools['STAR_RUSTC_EXECUTABLE']).parent.parent
    roots = [ROOT / d for d in ('source', 'scripts', 'cmake', 'toolchains', 'triplets', 'lib', 'nix')]
    roots += [sdk, compiler_usr / 'include', compiler_usr / 'lib/clang',
              rust_usr / 'lib', Path(tools['CMAKE_EXECUTABLE']).parents[1],
              ROOT / 'build/macos-arm-release/vcpkg_installed',
              Path('/Users/bdsqqq/.cache/openstarbound-vcpkg/scripts'),
              Path('/Users/bdsqqq/.cache/openstarbound-vcpkg/triplets'), Path(sys.prefix)]
    witness = closure(roots)
    auxiliary = [Path('/bin/bash'), Path('/usr/bin/python3'), Path(sys.executable),
                 Path('/usr/bin/uname'), Path('/usr/bin/dirname'), Path('/usr/bin/git')]
    for path in list(map(Path, tools.values())) + auxiliary + [seed, seed.parent / 'build.ninja', argfile, launchers]:
        witness['aliases'][str(path)] = str(path.resolve(strict=True))
        witness['files'][str(path.resolve(strict=True))] = sha(path)
    plan = dict(stage='PREEXECUTION_COMPLETE_CACHE_TOOLS', tools=tools,
        seedCache=str(seed), seedCacheSha256=sha(seed), argumentFile=str(argfile), argumentSha256=sha(argfile), launcherFile=str(launchers),
        witness=witness, sdk=str(sdk), sourceCheckpoint=os.environ['STAR_TTL_SOURCE_CHECKPOINT'],
        checkpointRole='BASE_ONLY; complete current working-tree bytes pinned before any native action',
        scope='fresh full game pair; original native flags; no runtime/game/adoption assertion')
    validate(plan)
    # Coherent missing-archiver witness is a deterministic prelaunch rejection.
    import copy
    bad = copy.deepcopy(plan)
    del bad['witness']['files'][str(Path(tools['CMAKE_AR']).resolve())]
    try:
        validate(bad)
    except ValueError as e:
        need('pre-execution tool' in str(e), 'wrong archiver falsifier barrier')
    else:
        raise AssertionError('missing archiver admission accepted')
    dump(output / 'controls.json', dict(missingArchiverRejectedBeforeAnyConfigure=True))
    dump(output / 'plan.json', plan)
    print(sha(output / 'plan.json'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('phase', choices=['prepare', 'before', 'configured'])
    p.add_argument('--output', type=Path)
    p.add_argument('--plan', type=Path)
    p.add_argument('--sha')
    p.add_argument('--build', type=Path)
    a = p.parse_args()
    if a.phase == 'prepare':
        need(a.output is not None, 'output required')
        prepare(a.output.resolve())
        return
    need(a.plan is not None and a.sha == sha(a.plan), 'externally pinned admission plan required')
    plan = json.loads(a.plan.read_text())
    validate(plan)
    if a.phase == 'configured':
        need(a.build is not None, 'configured directory required')
        need(selection(a.build / 'CMakeCache.txt') == plan['tools'], 'unadmitted configured executable selection')
        dump(a.build.parent / 'complete-tool-admission.json', dict(planSha256=a.sha,
            selectedTools=plan['tools'], cacheSha256=sha(a.build / 'CMakeCache.txt'),
            ninjaSha256=sha(a.build / 'build.ninja'), scope='tools reconciled before bulk compilation'))
    print('COMPLETE_TOOL_SOURCE_ADMISSION_PASS')

if __name__ == '__main__':
    main()
