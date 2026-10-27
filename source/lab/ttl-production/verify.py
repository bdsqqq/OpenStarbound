#!/usr/bin/env python3
"""Read-only replay of finite production compile/configure gates and controls."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'build/ttl-production-r1'


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def load(path):
    return json.loads(Path(path).read_text())


def off_source(text):
    """Select only our explicit TTL conditional blocks, retaining exact bytes."""
    lines = text.splitlines(keepends=True)
    result = []
    selected = True
    stack = []
    blocks = 0
    for line in lines:
        if line == '#ifdef STAR_USE_RUST_TTL_CACHE\n':
            stack.append(selected)
            selected = False
            blocks += 1
        elif stack and line == '#else\n':
            selected = stack[-1]
        elif stack and line == '#endif\n':
            selected = stack.pop()
        elif selected:
            result.append(line)
    need(not stack and blocks == 21, 'exact 19 methods + include + type-frame conditional blocks')
    result = ''.join(result)
    need(result.count('  friend struct TtlCacheLabAccess;\n') == 1, 'single approved observer friend')
    return result.replace('  friend struct TtlCacheLabAccess;\n', '')


def source_gate(text, original):
    need(off_source(text) == original, 'OFF entire source equality')


def receipt_gate(plan, started, receipt):
    need(type(receipt['returncode']) is int and receipt['returncode'] == plan['expected'], 'typed return code')
    need(type(receipt['pid']) is int and receipt['pid'] > 0 and type(started['pid']) is int and started['pid'] == receipt['pid'], 'typed PID pair')
    need(type(receipt['pgid']) is int and receipt['pgid'] == started['pgid'] == receipt['pid'], 'typed process group pair')
    need(started['started'] == receipt['started'] and receipt['ended'] >= receipt['started'], 'start/end identity')
    need(receipt['reaped'] is True and receipt['groupGone'] is True and receipt['timedOut'] is False, 'normal completion')
    need(plan['timeout'] > 0 and plan['timeout'] <= 180, 'bounded command')
    need(plan['sourceBefore'] == receipt['sourceAfter'], 'source stability within command')


def profile_gate(selectors, ttl):
    need(len(selectors) == 27 and all(k.startswith('STAR_USE_RUST_') for k in selectors), '27-selector schema')
    need(all(v == ('ON' if ttl and k == 'STAR_USE_RUST_TTL_CACHE' else 'OFF') for k, v in selectors.items()), 'exact profile selector values')


def object_gate(flags, expected_base, ttl, lru):
    expected = expected_base + (['-DSTAR_USE_RUST_TTL_CACHE'] if ttl else []) + (['-DSTAR_USE_RUST_LRU_CACHE'] if lru else [])
    need(flags == expected, 'exact historical actual compiler flags + declared selector delta')


def methods(text, marker):
    result = {}
    pos = 0
    while True:
        start = text.find(marker, pos)
        if start < 0:
            break
        begin = text.index('{', start)
        name = re.search(r'::(\w+)\(', text[start:begin])[1]
        depth, end = 1, begin + 1
        while depth:
            if text[end] == '{':
                depth += 1
            if text[end] == '}':
                depth -= 1
            end += 1
        body = text[begin+1:end-1]
        if '#ifdef STAR_USE_RUST_TTL_CACHE' in body:
            body = body.split('#ifdef STAR_USE_RUST_TTL_CACHE\n', 1)[1].split('#else\n', 1)[0]
        result[name] = re.sub(r'\s+', '', body)
        pos = end
    return result


def verify():
    inputs = load(OUT / 'inputs.json')
    for collection in ['owned', 'frozen']:
        for path, value in inputs[collection].items():
            need(sha(path) == value, collection + ' source pin: ' + path)
    for item in inputs['tools'].values():
        need(str(Path(item['path']).resolve()) == item['resolved'] and sha(item['path']) == item['sha256'], 'selected executable pin')
    header = (ROOT / 'source/core/StarTtlCache.hpp').read_text()
    original = (ROOT / 'source/lab/ttl-cache/StarTtlCache.original.hpp').read_text()
    source_gate(header, original)
    need((OUT / 'original-observer.hpp').read_text() == original.replace('private:\n', 'private:\n  friend struct TtlCacheLabAccess;\n'), 'original observer derivation')
    actual_methods = methods(header, 'TtlCacheBase<LruCacheType>::')
    reference_methods = methods((ROOT / 'source/lab/ttl-boundary/cache.hpp').read_text(), 'BoundaryTtlCacheBase<L>::')
    reference_methods['TtlCacheBase'] = reference_methods.pop('BoundaryTtlCacheBase')
    need(len(actual_methods) == 19 and actual_methods == reference_methods, 'all 19 ON bodies identical to accepted native continuations')
    expected_host = (ROOT / 'source/lab/ttl-boundary/host.hpp').read_text()
    expected_host = expected_host.replace('TtlBoundaryHost', 'TtlCacheRust').replace('std::runtime_error', 'std::logic_error').replace('ttl boundary', 'Rust TtlCache ABI')
    expected_host = expected_host.replace('#include <cstddef>', '#include <cstddef>\n#include <utility>')
    for call in ['maxSize()', 'currentSize()', 'values()']:
        expected_host = expected_host.replace('c.cache.' + call, 'std::as_const(c.cache).' + call)
    expected_host = expected_host.replace('&& (r.tag!=SB_TTL_VOID || !r.value);}', '&& (r.tag!=SB_TTL_VOID || !r.value) && (r.tag<SB_TTL_REF || !r.value);}')
    expected_host = expected_host.replace('out->size!=24 || out->version!=1 || out->reserved)return SB_TTL_INVALID;',
        'out->size!=24 || out->version!=1 || out->reserved)return SB_TTL_INVALID;\n  // Rust initializes leaf destinations with this exact sentinel. Other incoming\n  // tags must be canonical before any native field or dependency is mutated.\n  if(!valid(*out) && !(out->tag==UINT32_MAX && out->value==UINT64_MAX))return SB_TTL_INVALID;')
    need((ROOT / 'source/core/StarTtlCacheHost.hpp').read_text() == expected_host, 'exact accepted host derivation with const dispatch and ABI guards only')

    base_plan = load(inputs['historicalProfile']['path'])
    need(sha(inputs['historicalProfile']['path']) == inputs['historicalProfile']['sha256'], 'historical flags source pin')
    base = base_plan['argv'][:base_plan['argv'].index('-c')]
    base = [x for x in base if not x.startswith('-I' + str(ROOT / 'source/lab/ttl-cache'))] + ['-I' + str(OUT)]
    for name, ttl, lru in [('native', False, False), ('ttl', True, False), ('combined', True, True)]:
        artifact = load(OUT / (name + '-artifact.json'))
        need(sha(OUT / (name + '.o')) == artifact['objectSha256'], 'object byte pin')
        object_gate(artifact['flags'], base, ttl, lru)
        for path, value in artifact['dependencies'].items():
            need(sha(path) == value, 'consumed input pin: ' + path)
        symbols = (OUT / (name + '-symbols.stdout')).read_text().splitlines()
        need(('_sb_ttl_run' in symbols) == ttl, 'nominal TTL root symbol ON only')
        need(('_sb_lru_run' in symbols) == lru, 'nominal LRU root symbol combined only')
        compile_plan = load(OUT / (name + '-compile.plan.json'))
        need(compile_plan['argv'] == artifact['flags'] + ['-c', str(HERE / 'probe.cpp'), '-o', str(OUT / (name + '.o'))], 'object command flags binding')
        need((OUT / (name + '-compile.stderr')).read_bytes() == b'', 'warning-free production probe')

    profiles = {}
    for name, ttl in [('default', False), ('only-ttl', True)]:
        profile = load(OUT / (name + '-profile.json'))
        profile_gate(profile['selectors'], ttl)
        cm = OUT / ('cmake-' + name)
        need(sha(cm / 'CMakeCache.txt') == profile['cacheSha256'] and sha(cm / 'build.ninja') == profile['ninjaSha256'], 'configured profile artifacts')
        actual_selectors = {}
        for line in (cm / 'CMakeCache.txt').read_text().splitlines():
            match = re.match(r'(STAR_USE_RUST_[^:]+):[^=]+=(.*)', line)
            if match:
                actual_selectors[match[1]] = match[2]
        need(actual_selectors == profile['selectors'], 'independent actual cache selector reconstruction')
        argv = load(OUT / (name + '-configure.plan.json'))['argv']
        need([arg for arg in argv if arg.startswith('-DSTAR_USE_RUST_')] == (['-DSTAR_USE_RUST_TTL_CACHE=ON'] if ttl else []), 'no hidden configure selector overrides')
        ninja = (cm / 'build.ninja').read_text()
        need(('-DSTAR_USE_RUST_TTL_CACHE' in ninja) == ttl, 'actual propagated TTL compile definition')
        need(ninja.count('Building Rust engine FFI') == int(ttl), 'exact single aggregate configure rule')
        need(profile['configureOnly'] is True and profile['cargoExecuted'] is False, 'configure scope')
        profiles[name] = profile['selectors']

    receipts = []
    for path in sorted(OUT.glob('*.receipt.json')):
        name = path.name.removesuffix('.receipt.json')
        plan = load(OUT / (name + '.plan.json'))
        started = load(OUT / (name + '.started.json'))
        receipt = load(path)
        receipt_gate(plan, started, receipt)
        need(receipt['planSha256'] == sha(OUT / (name + '.plan.json')), 'plan pin')
        need(plan['tool']['sha256'] == sha(plan['tool']['path']) and str(Path(plan['tool']['path']).resolve()) == plan['tool']['resolved'], 'command tool pin')
        for kind, expected in receipt['stdio'].items():
            need(sha(OUT / (name + '.' + kind)) == expected, 'command stdio pin')
        for p, h in plan['sourceBefore'].items():
            need(sha(p) == h, 'command owned source pin')
        receipts.append(name)
    need(len(receipts) == 11, 'nine object/dependency/symbol + two configure commands')
    archive_manifest = load(OUT / 'pre-friend-manifest.json')
    archive = OUT / 'pre-friend-objects.tar.gz'
    need(sha(archive) == archive_manifest['archiveSha256'], 'historical archive pin')
    import tarfile
    with tarfile.open(archive, 'r:gz') as tar:
        need(set(tar.getnames()) == set(archive_manifest['members']), 'historical exact archive membership')
        for item in tar:
            data = tar.extractfile(item).read()
            need(dict(sha256=digest(data), size=len(data)) == archive_manifest['members'][item.name], 'historical exact bytes after prune')
    release = load(OUT / 'lru-source-release.json')
    need(release['stable'] is True and sha(ROOT / 'source/core/StarLruCache.hpp') == release['sha256'], 'coordinated LRU release source pin')
    return dict(status='PASS_FINITE_COMPILE_CONFIGURE_ONLY', methods=19, selectors=27, commands=receipts,
        coordinatedLruRelease=release, historicalArchiveSha256=archive_manifest['archiveSha256'],
        verificationSources={str(p): sha(p) for p in [HERE / 'verify.py', HERE / 'refresh.py']},
        historicalDisposition=archive_manifest['disposition'],
        profiles=profiles, sourcePins=inputs['owned'],
        limitations=['no Rust/Cargo build', 'no linked production runtime', 'no fresh Core/game runtime', 'no platform/performance/universal claim'])


def controls():
    failures = []
    def reject(name, fn):
        try:
            fn()
        except AssertionError as error:
            failures.append(dict(name=name, rejectedAt=str(error)))
        else:
            raise AssertionError('falsifier accepted: ' + name)
    header = (ROOT / 'source/core/StarTtlCache.hpp').read_text()
    original = (ROOT / 'source/lab/ttl-cache/StarTtlCache.original.hpp').read_text()
    # Exact source, flags, receipt and schema barriers; no model/expected-output fit.
    reject('OFF-source-write-order', lambda: source_gate(header.replace('  m_timeToLive = timeToLive;\n  m_timeSmear = timeSmear;', '  m_timeSmear = timeSmear;\n  m_timeToLive = timeToLive;'), original))
    reject('OFF-alias-allocator', lambda: source_gate(header.replace('1024', '1025', 1), original))
    p = load(OUT / 'ttl-compile.plan.json')
    s = load(OUT / 'ttl-compile.started.json')
    r = load(OUT / 'ttl-compile.receipt.json')
    bad = copy.deepcopy(r); bad['pid'] = True
    reject('typed-boolean-PID', lambda: receipt_gate(p, s, bad))
    bad2 = copy.deepcopy(r); bad2['returncode'] = False
    reject('typed-boolean-exit', lambda: receipt_gate(p, s, bad2))
    profile = load(OUT / 'only-ttl-profile.json')['selectors']
    altered = dict(profile); altered['STAR_USE_RUST_LINE_QUERY'] = 'ON'
    reject('profile-extra-LINE-ON', lambda: profile_gate(altered, True))
    missing = dict(profile); missing.pop('STAR_USE_RUST_TTL_CACHE')
    reject('profile-missing-selector', lambda: profile_gate(missing, True))
    flags = load(OUT / 'native-artifact.json')['flags']
    reject('different-optimization-flags', lambda: object_gate([x.replace('-O3', '-O0') for x in flags], flags, False, False))
    need(len(failures) == 7, 'seven falsifiers')
    return failures


if __name__ == '__main__':
    report = verify()
    report['falsifiers'] = controls()
    verify()  # positive replay after all isolated in-memory negatives
    if len(sys.argv) == 3 and sys.argv[1] == '--report-sha':
        need(sha(OUT / 'report.json') == sys.argv[2], 'immutable report pin')
        need(load(OUT / 'report.json') == report, 'report exact replay')
    print(json.dumps(report, indent=2, sort_keys=True))
