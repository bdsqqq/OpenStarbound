#!/usr/bin/env python3
"""Fresh game-TU syntax checks; no linking, Cargo, game, or runtime qualification.

Historical Ninja contributes flags ONLY. All consumed source/header bytes and the
compiler are admitted before execution, then independently checked through -MD.
"""
import datetime as dt
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
OUT = ROOT / 'build/ttl-game-source-r1/syntax'
DEADLINE = dt.datetime(2026, 10, 27, 19, 25, tzinfo=dt.timezone.utc).timestamp()

def need(ok, why):
    if not ok:
        raise AssertionError(why)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def closure(roots):
    files, aliases, seen = {}, {}, set()
    for root in roots:
        aliases[str(root)] = str(root.resolve(strict=True))
        for base, dirs, names in os.walk(root.resolve(strict=True), followlinks=True):
            physical = str(Path(base).resolve())
            if physical in seen:
                dirs[:] = []
                continue
            seen.add(physical)
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
            for name in dirs + names:
                p = Path(base) / name
                if p.is_symlink():
                    aliases[str(p)] = str(p.resolve(strict=True))
            for name in names:
                p = Path(base) / name
                if p.is_file():
                    p = p.resolve(strict=True)
                    files.setdefault(str(p), sha(p))
    return dict(files=files, aliases=aliases)

def unchanged(witness):
    for p, resolved in witness['aliases'].items():
        need(str(Path(p).resolve(strict=True)) == resolved, 'alias drift: ' + p)
    for p, h in witness['files'].items():
        need(sha(p) == h, 'input drift: ' + p)

def subset(paths, witness):
    for p in paths:
        actual = str(Path(p).resolve(strict=True))
        need(actual in witness['files'] and sha(actual) == witness['files'][actual], 'unadmitted dependency: ' + str(p))

def main():
    need(not OUT.exists(), 'fresh one-shot syntax root required')
    OUT.mkdir()
    sources = ['game/StarTenantDatabase.cpp', 'client/StarClientApplication.cpp']
    selectors = set(re.findall(r'option\((STAR_USE_RUST_\w+)', (ROOT / 'source/CMakeLists.txt').read_text()))
    need(len(selectors) == 27, 'exact selector schema')
    plans, roots = [], [ROOT / 'source']
    compiler = None
    for profile in ['reference', 'candidate']:
        cm = ROOT / ('build/behavior/lru-cache-combined-r1/' + profile + '/cmake')
        cache = (cm / 'CMakeCache.txt').read_text()
        selected = re.search(r'^CMAKE_CXX_COMPILER:[^=]+=(.+)$', cache, re.M)[1]
        need(compiler in (None, selected), 'same physical compiler for both roles')
        compiler = selected
        ninja = cm / 'build.ninja'
        text = ninja.read_text()
        for source in sources:
            filename = Path(source).name
            block = re.search(r'^build [^ :]*' + re.escape(filename) + r'\.o:[^\n]+\n((?:  [^\n]*\n)+)', text, re.M)
            need(block is not None, 'exact historical TU flags')
            properties = dict(re.findall(r'^  (\w+) = (.*)$', block[1], re.M))
            args = shlex.split(properties['DEFINES'] + ' ' + properties['FLAGS'] + ' ' + properties['INCLUDES'])
            if profile == 'candidate':
                args += ['-DSTAR_USE_RUST_TTL_CACHE']
            enabled = {x[2:] for x in args if x.startswith('-DSTAR_USE_RUST_')}
            expected = selectors - {'STAR_USE_RUST_LINE_QUERY'} if profile == 'candidate' else set()
            need(enabled == expected, 'declared 27-OFF / 26-ON-except-LINE profile')
            for i, arg in enumerate(args):
                if arg in ('-isysroot', '-isystem'):
                    roots.append(Path(args[i+1]))
                elif arg.startswith('-I'):
                    roots.append(Path(arg[2:]))
            name = profile + '-' + Path(source).stem
            argv = [compiler, *args, '-fsyntax-only', '-MD', '-MF', str(OUT / (name + '.d')), '-MT', name, str(ROOT / 'source' / source)]
            plans.append(dict(name=name, argv=argv, flagsSource=str(ninja), flagsSourceSha256=sha(ninja), cacheSource=str(cm / 'CMakeCache.txt'), cacheSourceSha256=sha(cm / 'CMakeCache.txt')))
    toolusr = Path(compiler).resolve().parent.parent
    roots += [toolusr / 'include', toolusr / 'lib/clang']
    witness = closure(roots)
    witness['files'][str(Path(compiler).resolve())] = sha(compiler)
    witness['aliases'][compiler] = str(Path(compiler).resolve(strict=True))
    for plan in plans:
        for key in ('flagsSource', 'cacheSource'):
            witness['files'][str(Path(plan[key]).resolve())] = plan[key + 'Sha256']
    dump(OUT / 'admission.json', dict(witness=witness, compiler=compiler, compilerResolved=str(Path(compiler).resolve()), plans=plans,
        scope='fresh syntax-only game TUs; historical flags only, no old Core objects, no Cargo/link/runtime'))
    # Known failure must fail BEFORE any compiler executes.
    victim = str((ROOT / 'source/core/StarTtlCache.hpp').resolve())
    bad = dict(files=dict(witness['files']))
    del bad['files'][victim]
    try:
        subset([victim], bad)
    except AssertionError:
        pass
    else:
        raise AssertionError('missing-input falsifier accepted')
    dump(OUT / 'controls.json', dict(missingConsumedHeaderRejected=True, compilerExecutedYet=False))
    results = []
    for plan in plans:
        unchanged(witness)
        need(time.time() < DEADLINE - 2, 'hard deadline before compiler launch')
        prefix = OUT / plan['name']
        dump(str(prefix) + '.plan.json', plan)
        env = dict(os.environ, LC_ALL='C', LANG='C', TMPDIR=str(OUT), CARGO_NET_OFFLINE='true')
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        with open(str(prefix) + '.stdout', 'wb') as stdout, open(str(prefix) + '.stderr', 'wb') as stderr:
            child = subprocess.Popen(plan['argv'], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True)
            dump(str(prefix) + '.started.json', dict(pid=child.pid, pgid=os.getpgid(child.pid), started=started, compilerSha256=sha(compiler)))
            timed_out = False
            try:
                code = child.wait(timeout=min(180, DEADLINE-time.time()))
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(child.pid, signal.SIGKILL)
                code = child.wait()
        dump(str(prefix) + '.receipt.json', dict(pid=child.pid, returncode=code, timedOut=timed_out, started=started, ended=dt.datetime.now(dt.timezone.utc).isoformat(), stdoutSha256=sha(str(prefix)+'.stdout'), stderrSha256=sha(str(prefix)+'.stderr')))
        need(code == 0 and not timed_out, 'compiler failed; immutable diagnostics retained: ' + plan['name'])
        dep = Path(str(prefix) + '.d').read_text().replace('\\\n', ' ')
        consumed = shlex.split(dep.split(':', 1)[1])
        subset(consumed, witness)
        unchanged(witness)
        results.append(dict(name=plan['name'], pid=child.pid, dependencies=len(consumed), dependencySha256=sha(str(prefix)+'.d')))
    dump(OUT / 'report.json', dict(status='PASS_FRESH_SYNTAX_ONLY_NOT_LINKED', results=results, admissionSha256=sha(OUT/'admission.json'), compilerSha256=sha(compiler)))
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
