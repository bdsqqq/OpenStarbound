#!/usr/bin/env python3
"""Bounded compile/configure evidence; never builds Cargo, Core, or the game."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'build/ttl-production-r1'
SEED = ROOT / 'build/ttl-rust-parity-r1/guarded-cmake/CMakeCache.txt'
BASE_PLAN = ROOT / 'build/ttl-cache-native-r1/compile.plan.json'
ORIGINAL = ROOT / 'source/lab/ttl-cache/StarTtlCache.original.hpp'
OWNED = [ROOT / 'source/core/StarTtlCache.hpp', ROOT / 'source/core/StarTtlCacheHost.hpp', ROOT / 'source/CMakeLists.txt']
FROZEN = {ORIGINAL: '51942575d77806e99f783f18ba0edb0595a41e634605322d06a85b03a2514081',
 ROOT / 'source/core/StarRustTtlCache.h': '254cf12cb2ec798334cf0799b4344f58eb140e657dceb12d0788200cdc17332d',
 ROOT / 'source/rust/ffi/src/ttl_cache.rs': 'c17c51d6d902558e7b8a0fbed4d5b0282044dbe432775e8b4eea12784b00d6fd',
 ROOT / 'source/lab/ttl-boundary/cache.hpp': '5bb90f41a4e74f310afc580e3e9328a68217458b3967848858e694aed1a9c152',
 ROOT / 'source/lab/ttl-boundary/host.hpp': 'bbcb9049962e10d5488113f2267c6d92973af4e3d257f987e1045532206f76b1'}
DEADLINE = dt.datetime(2026, 10, 27, 18, 49, 0, tzinfo=dt.timezone.utc).timestamp()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def need(ok, message):
    if not ok:
        raise AssertionError(message)

def pins():
    return {str(p): sha(p) for p in OWNED + sorted(HERE.glob('*')) if p.is_file()}

def cache(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        m = re.match(r'([^/#][^:]*):[^=]+=(.*)', line)
        if m:
            result[m[1]] = m[2]
    return result

def tools():
    selected = {k: v for k, v in cache(SEED).items()
        if k.startswith(('CMAKE_', 'STAR_')) and Path(v).is_absolute()
        and Path(v).is_file() and os.access(v, os.X_OK)}
    selected['CMAKE_COMMAND'] = cache(SEED)['CMAKE_COMMAND']
    need(all(k in selected for k in ['CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_AR', 'CMAKE_RANLIB', 'CMAKE_MAKE_PROGRAM']), 'selected tools incomplete')
    return selected

def tool_pins(selected):
    return {k: dict(path=v, resolved=str(Path(v).resolve()), sha256=sha(v)) for k, v in selected.items()}

def command(name, argv, timeout=90, cwd=ROOT, expected=0):
    prefix = OUT / name
    need(not prefix.with_suffix('.receipt.json').exists(), 'refuse overwriting command ' + name)
    remaining = int(DEADLINE - time.time())
    need(remaining > 1, 'hard deadline')
    timeout = min(timeout, remaining)
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/Users/bdsqqq/.rustup/toolchains/stable-aarch64-apple-darwin/bin',
        'HOME': str(OUT / 'home'), 'TMPDIR': str(OUT / 'tmp'), 'LANG': 'C', 'LC_ALL': 'C',
        'VCPKG_ROOT': '/Users/bdsqqq/.cache/openstarbound-vcpkg', 'CARGO_NET_OFFLINE': 'true'}
    before = pins()
    dump(str(prefix) + '.plan.json', dict(argv=argv, cwd=str(cwd), env=env, timeout=timeout,
        expected=expected, sourceBefore=before, tool=dict(path=argv[0], resolved=str(Path(argv[0]).resolve()), sha256=sha(argv[0]))))
    Path(str(prefix) + '.stdin').write_bytes(b'')
    with open(str(prefix) + '.stdin', 'rb') as stdin, open(str(prefix) + '.stdout', 'wb') as stdout, open(str(prefix) + '.stderr', 'wb') as stderr:
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True)
        dump(str(prefix) + '.started.json', dict(pid=child.pid, pgid=os.getpgid(child.pid), started=started, parentPid=os.getpid()))
        timed_out = False
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)
            code = child.wait()
        try:
            os.killpg(child.pid, 0)
            group_gone = False
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            group_gone = True
    receipt = dict(pid=child.pid, pgid=child.pid, started=started, ended=dt.datetime.now(dt.timezone.utc).isoformat(),
        returncode=code, timedOut=timed_out, reaped=True, groupGone=group_gone, sourceAfter=pins(),
        stdio={kind: sha(str(prefix) + '.' + kind) for kind in ['stdin', 'stdout', 'stderr']},
        planSha256=sha(str(prefix) + '.plan.json'))
    dump(str(prefix) + '.receipt.json', receipt)
    need(not timed_out and group_gone and code == expected, name + ': command failed (retained receipts)')
    need(before == pins(), name + ': owned source changed during command')
    return Path(str(prefix) + '.stdout').read_text(errors='surrogateescape')

def prepare():
    need(not OUT.exists(), 'fresh output root required')
    OUT.mkdir()
    (OUT / 'home').mkdir()
    (OUT / 'tmp').mkdir()
    need(all(sha(p) == h for p, h in FROZEN.items()), 'frozen input pin')
    baseline = ORIGINAL.read_text()
    (OUT / 'original-observer.hpp').write_text(baseline.replace('private:\n', 'private:\n  friend struct TtlCacheLabAccess;\n'))
    selected = tools()
    dump(OUT / 'inputs.json', dict(owned=pins(), frozen={str(p): h for p, h in FROZEN.items()},
        historicalProfile=dict(path=str(BASE_PLAN), sha256=sha(BASE_PLAN)), seedCache=dict(path=str(SEED), sha256=sha(SEED)), tools=tool_pins(selected),
        limitation='only owned source and frozen inputs pinned; no global source freeze or fresh native runtime claim'))
    print('prepared', OUT)

def objects():
    plan = json.loads(BASE_PLAN.read_text())
    argv = plan['argv'][:plan['argv'].index('-c')]
    argv = [x for x in argv if not x.startswith('-I' + str(ROOT / 'source/lab/ttl-cache'))]
    argv += ['-I' + str(OUT)]
    source = str(HERE / 'probe.cpp')
    for name, defs in [('native', []), ('ttl', ['-DSTAR_USE_RUST_TTL_CACHE']),
            ('combined', ['-DSTAR_USE_RUST_TTL_CACHE', '-DSTAR_USE_RUST_LRU_CACHE'])]:
        # Dependency discovery is a fresh compiler action with its own receipt.
        dep = OUT / (name + '.d')
        command(name + '-dependencies', argv + defs + ['-M', '-MF', str(dep), source])
        text = dep.read_text().replace('\\\n', ' ')
        import shlex
        deps = [Path(p) for p in shlex.split(text.split(':', 1)[1])]
        before = {str(p): sha(p) for p in deps}
        dump(OUT / (name + '-consumed-before.json'), before)
        obj = OUT / (name + '.o')
        command(name + '-compile', argv + defs + ['-c', source, '-o', str(obj)], timeout=120)
        need(before == {str(p): sha(p) for p in deps}, name + ': consumed header drift')
        dump(OUT / (name + '-artifact.json'), dict(objectSha256=sha(obj), dependencies=before, flags=argv + defs))
        command(name + '-symbols', [tools()['CMAKE_NM'], '-u', str(obj)])
    print('object probes complete')

def configure():
    selected = tools()
    before = tool_pins(selected)
    common = [selected['CMAKE_COMMAND'], '--preset', 'macos-arm-release',
        '-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON', '-DCMAKE_VERBOSE_MAKEFILE=OFF', '-DBUILD_TESTING=OFF',
        '-DSTAR_ENABLE_STEAM_INTEGRATION=OFF', '-DSTAR_ENABLE_DISCORD_INTEGRATION=OFF',
        '-DSTAR_BUILD_LIGHTING_LAB=OFF', '-DVCPKG_MANIFEST_INSTALL=OFF',
        '-DVCPKG_INSTALLED_DIR=' + str(ROOT / 'build/macos-arm-release/vcpkg_installed'),
        '-DSTAR_RUNTIME_OUTPUT_DIRECTORY=' + str(OUT / 'unused-bin')]
    common += ['-D' + key + '=' + value for key, value in selected.items() if key != 'CMAKE_COMMAND']
    for name, defs in [('default', []), ('only-ttl', ['-DSTAR_USE_RUST_TTL_CACHE=ON'])]:
        cm = OUT / ('cmake-' + name)
        need(not cm.exists(), 'fresh configure output required')
        command(name + '-configure', common + ['-B', str(cm)] + defs, timeout=180, cwd=ROOT / 'source')
        actual = cache(cm / 'CMakeCache.txt')
        selectors = {k: v for k, v in actual.items() if k.startswith('STAR_USE_RUST_')}
        need(len(selectors) == 27, 'all 27 selectors must exist')
        need(all(v == ('ON' if name == 'only-ttl' and k == 'STAR_USE_RUST_TTL_CACHE' else 'OFF') for k, v in selectors.items()), 'default selector drift')
        ninja = (cm / 'build.ninja').read_text()
        need(('Building Rust engine FFI' in ninja) == (name == 'only-ttl'), 'aggregate presence')
        need(ninja.count('Building Rust engine FFI') == (1 if name == 'only-ttl' else 0), 'single aggregate rule')
        need(('-DSTAR_USE_RUST_TTL_CACHE' in ninja) == (name == 'only-ttl'), 'TTL compile definition')
        dump(OUT / (name + '-profile.json'), dict(selectors=selectors, cacheSha256=sha(cm / 'CMakeCache.txt'),
            ninjaSha256=sha(cm / 'build.ninja'), configureOnly=True, cargoExecuted=False))
    need(before == tool_pins(selected), 'selected tool drift')
    print('fresh configure-only profiles complete')

if __name__ == '__main__':
    {'prepare': prepare, 'objects': objects, 'configure': configure}[sys.argv[1]]()
