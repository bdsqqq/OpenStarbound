#!/usr/bin/env python3
"""Real Map/Maybe BiMap differential. Keep results, not disposable executables.

Uses one reusable Rust target, the existing process guardian, and an owned fresh
work directory. This is lab evidence, not game adoption or whole-game origin.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work-dir', type=Path, required=True)
    ap.add_argument('--production', action='store_true', help='compare production header OFF and ON')
    ap.add_argument('--resume-after-cargo-budget-failure', action='store_true')
    args = ap.parse_args()
    out = args.work_dir.resolve()
    resume = args.resume_after_cargo_budget_failure
    if not out.is_relative_to(ROOT / 'build') or (out.exists() and not resume):
        raise ValueError('fresh owned work directory under build required')
    if resume:
        receipt = json.loads((out / 'cargo.receipt.json').read_text())
        if not (receipt['failure'] == 'unchanged 1536 MiB reservation exceeds live cap'
                and receipt['returncode'] == 0 and receipt['commandReaped']):
            raise ValueError('only the documented post-Cargo budget failure may resume')
        previous = json.loads((out / 'inputs.json').read_text())['pins']
        if any(sha(Path(p)) != value for p, value in previous.items() if Path(p) != Path(__file__).resolve()):
            raise ValueError('native inputs changed; cannot resume')
        if (out / 'cargo-r2.receipt.json').exists():
            raise ValueError('budget repair already attempted')
    out.mkdir(parents=True, exist_ok=resume)
    products = out / 'products'
    products.mkdir(exist_ok=resume)
    # Charge the shared target INSIDE the already reserved active root. A cache
    # outside it was additionally charged against the full 1536 MiB reservation.
    cache = ROOT / 'build/behavior/static-vector-combined-r1/rust-migration-current'
    cache.mkdir(exist_ok=True)
    for name in ('tmp', 'home', 'cargo-home'):
        (out / name).mkdir(exist_ok=resume)
    spec = importlib.util.spec_from_file_location('_real_bimap_builder', ROOT / 'scripts/build-static-vector-behavior-lab.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    rustdir = Path.home() / '.rustup/toolchains/stable-aarch64-apple-darwin/bin'
    cargo, rustc = (rustdir / 'cargo').resolve(), (rustdir / 'rustc').resolve()
    clang = Path('/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang++').resolve()
    sdk = Path('/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk').resolve(strict=True)
    python = Path(sys.executable).resolve()
    env = dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=str(out / 'home'), TMPDIR=str(out / 'tmp'),
               CARGO_HOME=str(out / 'cargo-home'), CARGO_NET_OFFLINE='true', RUSTC=str(rustc),
               CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER=str(clang), SDKROOT=str(sdk), LANG='C', LC_ALL='C')
    literal = lambda p: str(p).replace('\\', '\\\\').replace('"', '\\"')
    profile = ('(version 1)(allow default)(deny file-mount file-unmount)(deny file-write*)'
               '(allow file-write* (subpath "' + literal(out) + '") (subpath "' + literal(cache) + '"))')
    inputs = [*HERE.glob('*.hpp'), *HERE.glob('*.cpp'), *HERE.glob('*.py'),
              *(ROOT / 'source/core' / n for n in ('StarBiMap.hpp', 'StarBiMapHost.hpp', 'StarRustBiMap.h',
                'StarMap.hpp', 'StarMaybe.hpp', 'StarException_unix.cpp', 'StarMemory.cpp')),
              *sorted((ROOT / 'source/rust').rglob('*.rs'))]
    pins = {str(p): sha(p) for p in inputs}
    write = lambda p, value: builder.ad.bounded.write_json(p, value, 512 * 1024)
    deadline = time.monotonic() + 12 * 60

    def stable():
        if time.monotonic() >= deadline:
            raise ValueError('real BiMap test time budget expired')
        if any(sha(Path(p)) != value for p, value in pins.items()):
            raise ValueError('test source changed during execution')
        builder.ad.check_budget()

    def run(argv, name, seconds=120):
        started = time.monotonic()
        def remaining():
            return max(0, min(deadline - time.monotonic(), seconds - (time.monotonic() - started)))
        def check(p):
            if p.parent != out or p.exists():
                raise ValueError('fresh command output required')
        return builder._supervise_command(['/usr/bin/sandbox-exec', '-p', profile, *map(str, argv)], out, env, out / name,
            limits=dict(stdoutBytes=2 * 1024**2, stderrBytes=2 * 1024**2, readChunkBytes=65536, overflowBytes=65536),
            validate=stable, remaining_seconds=remaining, python=python,
            witness={}, write_record=write, check_output=check,
            scope='REAL_MAP_MAYBE_NONTRIVIAL_BIMAP_LAB_NOT_GAME', stdin=subprocess.DEVNULL)

    write(out / ('inputs-r2.json' if resume else 'inputs.json'), dict(pins=pins, tools={str(p): sha(p) for p in (cargo, rustc, clang)}, sdk=str(sdk),
                                   cache=str(cache), cleanup='owned native products removed after success; one Rust target retained'))
    if not resume:
        run([python, '-B', HERE / 'generate_core.py', '--output-dir', out / 'generated', '--real-support'], 'generate')
    original = (HERE / 'StarBiMap.original.hpp').read_text()
    assert original.count('#include "StarString.hpp"') == 1
    native_text = original.replace('#include "StarString.hpp"', '#include "' + str(ROOT / 'source/core/StarString.hpp') + '"')
    if resume:
        assert (out / 'native.hpp').read_text() == native_text
    else:
        (out / 'native.hpp').write_text(native_text)
    # Exact native exception bodies; exclude logger/fatal entrypoints, not their
    # observable behavior under test. No substitute exception implementation.
    exception = (ROOT / 'source/core/StarException_unix.cpp').read_text()
    marker = 'void printStack(char const* message) {'
    assert exception.count(marker) == 1
    prefix = exception.split(marker)[0]
    assert prefix.count('#include "StarLogging.hpp"') == 1
    projected = prefix.replace('#include "StarLogging.hpp"', '#include "StarArray.hpp"\n#include "StarMaybe.hpp"\n#include "StarFormat.hpp"') + '\n}\n'
    if resume:
        assert (out / 'exception.cpp').read_text() == projected
        assert sha(ROOT / 'source/core/StarException_unix.cpp') == json.loads((out / 'projection.json').read_text())['sourceSha256']
    else:
        (out / 'exception.cpp').write_text(projected)
        write(out / 'projection.json', dict(sourceSha256=sha(ROOT / 'source/core/StarException_unix.cpp'),
                                           originalPrefixSha256=hashlib.sha256(prefix.encode()).hexdigest(),
                                           projectedSha256=sha(out / 'exception.cpp'), excluded='logger/fatal entrypoints'))
    base = [cargo, '--offline', '--locked', '--manifest-path', ROOT / 'source/rust/ffi/Cargo.toml',
            '--target', 'aarch64-apple-darwin', '--target-dir', cache, '--release', '--lib']
    run([base[0], 'build', *base[1:]], 'cargo-r2' if resume else 'cargo')
    run([base[0], 'test', *base[1:], '--', '--test-threads=1'], 'rust-tests')
    archive = cache / 'aarch64-apple-darwin/release/libstar_engine_ffi.a'
    cpp = [clang, '--driver-mode=g++', '-std=c++17', '-O0', '-g0', '-DNDEBUG', '-DFMT_HEADER_ONLY',
           '-isysroot', sdk, '-I', ROOT / 'source/core', '-I', ROOT / 'source/extern']
    for name, source in [('exception', out / 'exception.cpp'), ('memory', ROOT / 'source/core/StarMemory.cpp')]:
        run([*cpp, '-c', source, '-o', products / (name + '.o')], name + '-compile')
    support = [products / 'exception.o', products / 'memory.o']
    headers = [('native', out / 'native.hpp'), ('candidate', out / 'generated/StarBiMap.generated.hpp')]
    if args.production:
        headers = [(role, ROOT / 'source/core/StarBiMap.hpp') for role in ('native', 'candidate')]
    for role, header in headers:
        extra = [] if role == 'native' else ['-DBIMAP_CANDIDATE', archive]
        if args.production and role == 'candidate':
            extra.append('-DSTAR_USE_RUST_BIMAP')
        run([*cpp, '-DBIMAP_HEADER="' + str(header) + '"', HERE / 'real.cpp', *support, *extra,
             '-o', products / role], role + '-link')
        run([products / role], role)
    assert (out / 'native.stdout').read_bytes() == (out / 'candidate.stdout').read_bytes(), 'native/candidate trace mismatch'
    rows = [json.loads(line) for line in (out / 'native.stdout').read_text().splitlines()]
    assert len(rows) == 20
    counts = json.loads((out / 'candidate.stderr').read_text().removeprefix('BIMAP_RUST_COUNTS '))
    assert len(counts) == 23 and all(type(n) is int and n >= 0 for n in counts)
    assert all(counts[n] > 0 for n in (19, 20, 21, 22)) and counts[16] == 0
    # Safe mutant adds a copy, never reads a freed key or removes the catch.
    mutant = (out / 'generated/StarBiMap.generated.hpp').read_text()
    needle = '    Right right = *rightPtr;'
    assert mutant.count(needle) == 1
    (out / 'extra-copy.hpp').write_text(mutant.replace(needle, '    Right extraCopy = *rightPtr;\n    Right right = extraCopy;'))
    run([*cpp, '-DBIMAP_HEADER="' + str(out / 'extra-copy.hpp') + '"', '-DBIMAP_CANDIDATE', HERE / 'real.cpp',
         *support, archive, '-o', products / 'extra-copy'], 'mutant-link')
    run([products / 'extra-copy'], 'mutant')
    assert (out / 'mutant.stdout').read_bytes() != (out / 'native.stdout').read_bytes(), 'extra-copy mutant undetected'
    run([*cpp, HERE / 'frame_test.cpp', archive, '-o', products / 'frame-test'], 'frame-link')
    run([products / 'frame-test'], 'frame')
    stable()
    status = 'PRODUCTION_BIMAP_OFF_ON_20_TRACE_PARITY_PASS_NOT_GAME' if args.production else 'REAL_NATIVE_MAP_MAYBE_20_TRACE_PARITY_PASS_NOT_GAME'
    result = dict(status=status, cases=[r['case'] for r in rows],
                  nativeSha256=sha(out / 'native.stdout'), candidateSha256=sha(out / 'candidate.stdout'), counts=counts,
                  frame=json.loads((out / 'frame.stdout').read_text()), archiveSha256=sha(archive),
                  nativeProducts={p.name: sha(p) for p in products.iterdir()}, mutantDetected=True,
                  sourcePins=pins, budget=builder.ad.check_budget(), cache='one reusable target; not archived providers')
    write(out / 'result.json', result)
    # Fresh owned scratch only. Preserve all compact diagnostics/failure truth.
    shutil.rmtree(products)
    for name in ('tmp', 'home', 'cargo-home'):
        shutil.rmtree(out / name)
    print(json.dumps(dict(status=result['status'], cases=len(rows), mutantDetected=True)))


if __name__ == '__main__':
    main()
