#!/usr/bin/env python3
"""production selection/type checks only; no retained objects or Cargo invocation."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'build/lru-production-r1/final-r2'
CLANG = '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang'
CMAKE = '/nix/store/fsdy1l7x2ybpry7lrhw2m7r6w8jvp01i-cmake-4.4.4/bin/cmake'
NINJA = '/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja'
TOOLS = Path('/Users/bdsqqq/.rustup/toolchains/stable-aarch64-apple-darwin/bin')
PROFILE = ROOT / 'build/behavior/path-embed-combined-r1/reference/cmake/compile_commands.json'
INPUTS = [ROOT / p for p in [
    'source/core/StarLruCache.hpp', 'source/core/StarLruCacheHost.hpp',
    'source/core/StarRustLruCache.h', 'source/CMakeLists.txt',
    'source/lab/lru-boundary/host_api.h', 'source/lab/lru-boundary/unwind.cpp',
    'source/lab/lru-cache/native.cpp', 'source/lab/lru-cache/StarLruCache.original.hpp',
    'source/rust/ffi/src/lru_cache.rs', 'cmake/Rust.cmake',
]] + list(HERE.glob('*')) + [PROFILE]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def command(name, argv, cwd=ROOT, data=b'', expected=0, timeout=180):
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:' + str(TOOLS),
           'HOME': str(OUT / 'home'), 'TMPDIR': str(OUT / 'tmp'),
           'LANG': 'C', 'LC_ALL': 'C', 'VCPKG_ROOT': '/Users/bdsqqq/.cache/openstarbound-vcpkg',
           'CARGO_NET_OFFLINE': 'true'}
    plan = {'argv': list(map(str, argv)), 'cwd': str(cwd), 'env': env,
            'stdin_sha256': hashlib.sha256(data).hexdigest(), 'timeout_seconds': timeout,
            'expected_exit': expected, 'started_at': time.time()}
    write(OUT / (name + '.plan.json'), plan)
    (OUT / (name + '.stdin')).write_bytes(data)
    p = subprocess.Popen(plan['argv'], cwd=cwd, env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    write(OUT / (name + '.started.json'), {'pid': p.pid, 'pgid': os.getpgid(p.pid), **plan})
    timed_out = False
    try:
        stdout, stderr = p.communicate(data, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(p.pid, signal.SIGKILL)
        stdout, stderr = p.communicate()
    (OUT / (name + '.stdout')).write_bytes(stdout)
    (OUT / (name + '.stderr')).write_bytes(stderr)
    receipt = {'pid': p.pid, 'pgid': p.pid, 'returncode': p.returncode,
               'timed_out': timed_out, 'ended_at': time.time(),
               'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
               'stderr_sha256': hashlib.sha256(stderr).hexdigest()}
    write(OUT / (name + '.receipt.json'), receipt)
    assert not timed_out, (name, 'timeout')
    assert p.returncode == expected, (name, receipt)
    return stdout


def main():
    assert not OUT.exists(), 'fresh root only; preserve failures'
    OUT.mkdir()
    for name in ('home', 'tmp'):
        (OUT / name).mkdir()
    before = {str(p.relative_to(ROOT)): sha(p) for p in INPUTS if p.is_file()}
    write(OUT / 'inputs-before.json', before)
    for p in INPUTS:
        if p.is_file():
            dest = OUT / 'source-snapshot' / p.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p.read_bytes())
    # compare the entire OFF header token stream with the frozen native header.
    active, stack, selected = True, [], []
    for line in (ROOT / 'source/core/StarLruCache.hpp').read_text().splitlines():
        if line == '#ifdef STAR_USE_RUST_LRU_CACHE':
            stack.append(active)
            active = False
        elif line == '#else':
            active = stack[-1] and not active
        elif line == '#endif':
            active = stack.pop()
        elif active:
            selected.append(line)
    normalize = lambda s: re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', s))
    assert normalize('\n'.join(selected)) == normalize((ROOT / 'source/lab/lru-cache/StarLruCache.original.hpp').read_text())
    # this row supplies flags only: NO old objects, link products or closure credit.
    row = next(r for r in json.loads(PROFILE.read_text()) if r['file'].endswith('/StarFile.cpp'))
    args = shlex.split(row['command'])
    flags = []
    i = 1
    while i < len(args):
        if args[i] == '-o':
            i += 2
        elif args[i] in ('-c', row['file']):
            i += 1
        else:
            flags.append(args[i])
            i += 1
    assert '-O3' in flags and '-ffast-math' in flags
    assert not any('STAR_USE_RUST_' in f for f in flags)
    write(OUT / 'profile.json', {'source_row': row, 'flags': flags,
          'limits': 'syntax/type instantiation only; no optimized object/link/runtime/closure claim'})
    sdk = flags[flags.index('-isysroot') + 1]
    c11 = b'''#include "StarRustLruCache.h"
#include "host_api.h"
_Static_assert(sizeof(SbLruRequest)==16, "request");
_Static_assert(sizeof(SbLruReply)==16, "reply");
_Static_assert(SB_LRU_MODES==12 && SB_LRU_TRAVERSE==3 && SB_LRU_MAP_CLEAR==20, "enum");
'''
    cargs = [CLANG, '-std=c11', '-x', 'c', '-isysroot', sdk,
             '-I' + str(ROOT / 'source/core'), '-I' + str(ROOT / 'source/lab/lru-boundary'),
             '-fsyntax-only', '-']
    command('c11', cargs, data=c11)
    # same compiler rejects a known bad ABI assertion, not just an empty header.
    command('c11-negative', cargs, data=c11 + b'_Static_assert(sizeof(SbLruReply)==17,"known bad ABI");\n', expected=1)
    # retain the original fixture expressions, changing ONLY class selection.
    unwind = (ROOT / 'source/lab/lru-boundary/unwind.cpp').read_text()
    assert unwind.startswith('#include "cache.hpp"\n#include "StarLruCache.hpp"\n')
    unwind = unwind.replace('#include "cache.hpp"\n#include "StarLruCache.hpp"\n', '', 1)
    for name in ('LruCacheBase', 'LruCache', 'HashLruCache'):
        unwind = unwind.replace('Star::' + name + '<', 'LruProductionReference::' + name + '<')
    unwind = unwind.replace('LruBoundary::', 'Star::')
    prefix = '''#include "StarLruCache.hpp"
namespace LruProductionReference { using namespace Star; }
#define Star LruProductionReference
#include "StarLruCache.original.hpp"
#undef Star
static_assert(sizeof(Star::LruCache<int,int>) == sizeof(LruProductionReference::LruCache<int,int>), "ordered layout");
static_assert(sizeof(Star::HashLruCache<int,int>) == sizeof(LruProductionReference::HashLruCache<int,int>), "hash layout");
'''
    lifetime = OUT / 'lifetime.cpp'
    lifetime.write_text(prefix + unwind)
    command('lazy-historical-negative', [CLANG + '++',
            '-I' + str(ROOT / 'build/lru-production-r1/historical-r1-source/source/core'),
            *flags, '-DSTAR_USE_RUST_LRU_CACHE', '-fsyntax-only', HERE / 'lazy.cpp'], expected=1)
    assert b'deleted' in (OUT / 'lazy-historical-negative.stderr').read_bytes()
    for mode in ('off', 'on'):
        select = ['-DSTAR_USE_RUST_LRU_CACHE'] if mode == 'on' else []
        for label, src in [('native', HERE / 'native.cpp'), ('lifetime', lifetime), ('lazy', HERE / 'lazy.cpp')]:
            command(label + '-' + mode, [CLANG + '++', *flags, *select,
                    '-I' + str(HERE), '-I' + str(ROOT / 'source/lab/lru-cache'),
                    '-fsyntax-only', '-MD', '-MF', OUT / (label + '-' + mode + '.d'), src])
            if label != 'lazy':
                obj = OUT / (label + '-' + mode + '.o')
                command(label + '-object-' + mode, [CLANG + '++', *flags, *select,
                        '-I' + str(HERE), '-I' + str(ROOT / 'source/lab/lru-cache'),
                        '-c', src, '-o', obj])
                undefined = command(label + '-undefined-' + mode,
                        [str(Path(CLANG).parent / 'nm'), '-u', obj])
                assert (b'_sb_lru_run' in undefined) == (mode == 'on')
    # fresh FULL-PROJECT configure only; all existing Rust selectors default OFF.
    base = [CMAKE, '--preset', 'macos-arm-release',
            '-DCMAKE_C_COMPILER=' + CLANG, '-DCMAKE_CXX_COMPILER=' + CLANG + '++',
            '-DCMAKE_MAKE_PROGRAM=' + NINJA, '-DCMAKE_OSX_SYSROOT=' + sdk,
            '-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON', '-DCMAKE_VERBOSE_MAKEFILE=OFF',
            '-DBUILD_TESTING=OFF', '-DSTAR_ENABLE_STEAM_INTEGRATION=OFF',
            '-DSTAR_ENABLE_DISCORD_INTEGRATION=OFF', '-DSTAR_BUILD_LIGHTING_LAB=OFF',
            '-DVCPKG_MANIFEST_INSTALL=OFF',
            '-DVCPKG_INSTALLED_DIR=' + str(ROOT / 'build/macos-arm-release/vcpkg_installed'),
            '-DSTAR_CARGO_EXECUTABLE=' + str(TOOLS / 'cargo'),
            '-DSTAR_RUSTC_EXECUTABLE=' + str(TOOLS / 'rustc'),
            '-DSTAR_RUNTIME_OUTPUT_DIRECTORY=' + str(OUT / 'unused-bin')]
    for mode in ('default', 'on'):
        cm = OUT / mode
        select = ['-DSTAR_USE_RUST_LRU_CACHE=ON'] if mode == 'on' else []
        command('configure-' + mode, [*base, '-B', cm, *select], cwd=ROOT / 'source')
        cache = (cm / 'CMakeCache.txt').read_text()
        assert 'STAR_USE_RUST_LRU_CACHE:BOOL=' + ('ON' if mode == 'on' else 'OFF') in cache
        selectors = re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$', cache, re.M)
        assert all(v == ('ON' if mode == 'on' and k == 'STAR_USE_RUST_LRU_CACHE' else 'OFF') for k, v in selectors)
        db = json.loads((cm / 'compile_commands.json').read_text())
        assert len(db) > 200
        assert all(('-DSTAR_USE_RUST_LRU_CACHE' in r['command']) == (mode == 'on') for r in db)
        ninja = (cm / 'build.ninja').read_text()
        assert ('build star_rust_engine_ffi_build:' in ninja) == (mode == 'on')
        if mode == 'on':
            assert ninja.count('--package star-engine-ffi --target aarch64-apple-darwin --release --locked --offline') == 1
        write(OUT / ('routing-' + mode + '.json'), {'selectors': selectors, 'compile_rows': len(db),
              'global_definition_verified': True, 'single_aggregate': mode == 'on',
              'limits': 'configured/generated only; no Cargo, Core or game build'})
    # exercise the unchanged shared module guards, independently of toolchain
    # discovery in a cross/universal full-project configure (no Cargo runs).
    guard = OUT / 'guard-project'
    guard.mkdir()
    (guard / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.23)
project(lru_guard NONE)
set(STAR_ARCHITECTURE arm64)
if(VERIFY_CROSS)
  set(CMAKE_CROSSCOMPILING TRUE)
else()
  set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64")
endif()
include("''' + str(ROOT / 'cmake/Rust.cmake') + '''")
message(FATAL_ERROR "guard unexpectedly survived")
''')
    for label, select, text in [('cross', 'ON', b'native builds only'),
                                ('universal', 'OFF', b'universal/multi-architecture')]:
        command('guard-' + label, [CMAKE, '-S', guard, '-B', OUT / ('guard-' + label),
                '-DVERIFY_CROSS=' + select,
                '-DSTAR_CARGO_EXECUTABLE=' + str(TOOLS / 'cargo'),
                '-DSTAR_RUSTC_EXECUTABLE=' + str(TOOLS / 'rustc')], expected=1)
        assert text in (OUT / ('guard-' + label + '.stderr')).read_bytes()
    after = {str(p.relative_to(ROOT)): sha(p) for p in INPUTS if p.is_file()}
    assert before == after, 'owned/participating test inputs changed'
    write(OUT / 'inputs-after.json', after)
    write(OUT / 'report.json', {'status': 'PRODUCTION_SELECTION_SYNTAX_CONFIGURATION_PASS',
          'inputs': before, 'lifetime_fixture_sha256': sha(lifetime),
          'off_header_matches_original_ignoring_comments_whitespace': True,
          'commands': sorted(p.name for p in OUT.glob('*.receipt.json')),
          'limits': 'fresh fixture objects only; no link/runtime/game/complete production dependency closure; parent gates remain open'})
    print('PRODUCTION_SELECTION_SYNTAX_CONFIGURATION_PASS', sha(OUT / 'report.json'))


if __name__ == '__main__':
    main()
