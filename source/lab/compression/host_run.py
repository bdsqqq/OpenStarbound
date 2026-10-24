#!/usr/bin/env python3
"""Replay native compression boundary without Cargo, game, or production writes."""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def opaque_driver(source):
    body = source[source.index('uint32_t run('):]
    if re.search(r'\b(?:NativeContext|nativeHost)\b', body):
        raise ValueError('OPAQUE_CONTROLLER: status driver reads a native context/host identity')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path)
    p.add_argument('--check-opaque-only', action='store_true')
    a = p.parse_args()
    source = (HERE / 'host_contract.cpp').read_text()
    opaque_driver(source)
    # This source-purity checker must reject a known bad native-layout read.
    try: opaque_driver(source.replace('uint32_t failure = SC_COMPLETE;', 'NativeContext* forbidden = nullptr;\nuint32_t failure = SC_COMPLETE;'))
    except ValueError: pass
    else: raise RuntimeError('opaque-driver checker missed its isolated known failure')
    if a.check_opaque_only:
        print('PASS opaque driver and isolated native-layout-read rejection'); return
    if a.output is None: p.error('--output required')
    raw = a.output.absolute(); out = raw.resolve(); base = ROOT / 'build/compression-lab/host-prototype'
    if any(x.is_symlink() for x in (raw, *raw.parents)) or not out.is_relative_to(base) or out == base or out.exists(): p.error('new nonsymlink nested host-prototype output required')
    out.mkdir(parents=True)
    cm = ROOT / 'build/behavior/reference/cmake'
    entry = next(x for x in json.loads((cm / 'compile_commands.json').read_text()) if x['file'].endswith('/StarCompression.cpp'))
    recipe = shlex.split(entry['command']); flags = []; skip = False
    for x in recipe[1:]:
        if skip: skip = False; continue
        if x == '-o': skip = True
        elif x not in ('-c', entry['file']): flags.append(x)
    if any('STAR_USE_RUST' in x for x in flags): raise ValueError('not an all-native recipe')
    lines = (cm / 'build.ninja').read_text().splitlines()
    i = next(i for i, x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
    objects = [cm / x for x in shlex.split(lines[i].split(': ', 1)[1])[1:] if x.endswith('.o') and x.startswith(('core/', 'extern/')) and not x.endswith('/StarCompression.cpp.o')]
    if not objects or any(not x.is_file() for x in objects): raise ValueError('sealed native objects missing')
    libs = shlex.split(next(x.split(' = ', 1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')))
    libs = [str(cm / x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
    fixture = ROOT / 'build/compression-lab/cpp-primary-r1/cases.tsv'
    commands = []

    def run(command, name, expected=0):
        command = list(map(str, command)); commands.append(shlex.join(command))
        r = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=90)
        (out / (name + '.log')).write_bytes((commands[-1] + '\n').encode() + r.stdout + r.stderr)
        if r.returncode != expected: raise RuntimeError(name + ' failed; inspect exact log')
        return r

    original = subprocess.check_output(['git', 'show', '038b6fd9:source/core/StarCompression.cpp'], cwd=ROOT)
    if original != (HERE / 'StarCompression.original.cpp').read_bytes() or original != (ROOT / 'source/core/StarCompression.cpp').read_bytes(): raise ValueError('original/production source drift')
    reference = original.replace(b'namespace Star {', b'namespace CompressionReference {\nusing namespace Star;').replace(b'"StarCompression.hpp"', b'"StarCompression.reference.hpp"')
    if reference != (HERE / 'StarCompression.reference.cpp').read_bytes(): raise ValueError('reference adaptation drift')
    shim = out / 'shim.hpp'
    shim.write_text('#include "StarByteArray.hpp"\n#include <zlib-ng.h>\nvoid labAppend(Star::ByteArray&,char const*,size_t);\nint labDefEnd(zng_stream*);\nint labInfEnd(zng_stream*);\nvoid labBind(zng_stream*);\nint labDefInit(zng_stream*,int);\nint labInfInit(zng_stream*);\nint labGzipInit(zng_stream*,int);\nint labDefStep(zng_stream*,int);\nint labInfStep(zng_stream*,int);\n')
    instrument = reference
    substitutions = [(b'out.append((char const*)tempBuffer.get(), BUFSIZE);', b'labAppend(out,(char const*)tempBuffer.get(), BUFSIZE);', 3), (b'out.append((char const*)tempBuffer.get(), BUFSIZE - strm.avail_out);', b'labAppend(out,(char const*)tempBuffer.get(), BUFSIZE - strm.avail_out);', 3), (b'zng_deflateEnd(&strm)', b'labDefEnd(&strm)', 1), (b'zng_inflateEnd(&strm)', b'labInfEnd(&strm)', 4), (b'strm.next_out = tempBuffer.get();', b'labBind(&strm); strm.next_out = tempBuffer.get();', 6)]
    substitutions += [(b'zng_deflateInit(&strm, compression)', b'labDefInit(&strm, compression)', 1), (b'zng_inflateInit(&strm)', b'labInfInit(&strm)', 1), (b'zng_inflateInit2(&strm, 31)', b'labGzipInit(&strm, 31)', 1), (b'zng_deflate(&strm, Z_FINISH)', b'labDefStep(&strm, Z_FINISH)', 1), (b'zng_inflate(&strm, Z_FINISH)', b'labInfStep(&strm, Z_FINISH)', 2)]
    for old, new, count in substitutions:
        if instrument.count(old) != count: raise ValueError('instrumentation source gate drift')
        instrument = instrument.replace(old, new)
    src = out / 'instrumented.cpp'; src.write_bytes(instrument)
    typo_dir = out / 'corrected-legacy-typo'; typo_dir.mkdir()
    typo_cpp = typo_dir / 'host_contract.cpp'; typo_test = typo_dir / 'host_contract_test.cpp'
    candidate_bytes = (HERE / 'host_contract.cpp').read_bytes()
    typo_anchor = b'Internal error in uncompressData, deflate_res is {}'
    if candidate_bytes.count(typo_anchor) != 1: raise ValueError('legacy typo mutant anchor drift')
    typo_cpp.write_bytes(candidate_bytes.replace(typo_anchor, b'Internal error in compressData, deflate_res is {}'))
    typo_test.write_bytes((HERE / 'host_contract_test.cpp').read_bytes())
    tracked = [typo_cpp, typo_test, Path(__file__), *[HERE / x for x in ('host_contract.hpp', 'host_contract.cpp', 'host_contract_test.cpp', 'StarCompression.original.cpp', 'StarCompression.original.hpp', 'StarCompression.reference.cpp', 'StarCompression.reference.hpp')], fixture, shim, src, cm / 'compile_commands.json', cm / 'build.ninja', Path(recipe[0]).resolve(), *objects, *[Path(x) for x in libs if x.endswith('.a')]]
    for n, unit in enumerate((HERE / 'host_contract_test.cpp', HERE / 'StarCompression.reference.cpp', src)):
        dep = out / (str(n) + '.d')
        run([recipe[0], *flags, '-I'+str(HERE), '-include', shim, '-M', '-MF', dep, unit], 'dep'+str(n))
        tracked += [Path(x) if Path(x).is_absolute() else ROOT / x for x in shlex.split(dep.read_text().replace('\\\n', ' ').split(':', 1)[1])]
    tracked = list(dict.fromkeys(x.resolve() for x in tracked)); before = {str(x): sha(x) for x in tracked}
    (out / 'before.json').write_text(json.dumps(before, indent=2))
    archive = out / 'native-core.a'; run(['/usr/bin/ar', 'rcs', archive, *objects], 'archive')
    receipts = []
    for name, unit, extra in [('normal', HERE / 'StarCompression.reference.cpp', []), ('instrumented', src, ['-DINSTRUMENTED=1', '-include', str(shim)])]:
        binary = out / name
        run([recipe[0], *flags, '-I'+str(HERE), *extra, HERE / 'host_contract_test.cpp', unit, archive, *libs, '-Wl,-dead_strip', '-o', binary], name+'-compile')
        h = sha(binary); r = run([binary, fixture], name+'-run'); repeat = run([binary, fixture], name+'-repeat')
        if sha(binary) != h or repeat.stdout != r.stdout: raise RuntimeError('binary/repeat drift')
        receipts.append(dict(binary=str(binary), sha256=h, result=r.stdout.decode()))
    bad = run([out / 'instrumented', fixture, '--known-fault'], 'known-cleanup-fault', 1)
    if b'COMPARISON cleanup End trace' not in bad.stderr: raise RuntimeError('actual erroneous codec cleanup escaped')
    missing = run([out / 'instrumented', fixture, '--known-missing-step'], 'known-missing-step-trace', 1)
    if b'COMPARISON complete codec/append call order' not in missing.stderr: raise RuntimeError('missing step receipt escaped complete trace comparison')
    typo_binary = typo_dir / 'corrected-typo'
    run([recipe[0], *flags, '-I'+str(HERE), '-DINSTRUMENTED=1', '-include', shim, typo_test, src, archive, *libs, '-Wl,-dead_strip', '-o', typo_binary], 'corrected-typo-compile')
    typo = run([typo_binary, fixture], 'known-corrected-typo', 1)
    if b'COMPARISON deflate legacy error wording' not in typo.stderr: raise RuntimeError('corrected legacy deflate typo escaped injected-status anchor')
    for language, standard in [('c', 'c11'), ('c++', 'c++17')]:
        probe = out / ('header-' + standard + '.txt'); probe.write_text('#include "host_contract.hpp"\nint main(void){return SC_RAISE_LIMIT!=15;}\n')
        run([recipe[0], '-x', language, '-std='+standard, '-Wall', '-Wextra', '-Werror', '-pedantic', '-I'+str(HERE), probe, '-o', out / ('header-' + standard)], 'header-'+standard)
        run([out / ('header-' + standard)], 'header-run-'+standard)
    after = {str(x): sha(x) for x in tracked}; (out / 'after.json').write_text(json.dumps(after, indent=2))
    if before != after: raise RuntimeError('source/compiler/native object/dependency drift')
    report = dict(status='PASS', receipts=receipts, bindings=before, commands=commands, negative_controls=['opaque-native-layout-read', 'actual-end-on-append-fault', 'missing-step-receipt-with-real-codec-call', 'corrected-legacy-deflate-typo-under-injected-status'], native_archive_sha256=sha(archive), limits=['C++ boundary only; no Rust/game port', 'injected append faults are counterfactual, not actual OOM', 'persistent contexts do not prove temp free timing', 'reference legacy abandoned codec states are bounded and process-reclaimed'])
    (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n'); print(json.dumps({k:v for k,v in report.items() if k not in ('bindings', 'commands')}))


if __name__ == '__main__': main()
