#!/usr/bin/env python3
"""Finite production replay. Requires explicit frozen inputs; never builds Cargo/game.

Parent interface:
  --parent-source-freeze /absolute/map.json (absolute path -> sha256)
  --archive /absolute/libstar_rust_ffi.a --archive-sha256 <parent handshake>
  --values /absolute/fresh-native-p1 --output build/buffer-lab/rust-<fresh>

The freeze must include production C++/headers/Rust/CMake and all fixture inputs.
A stale native game seal fails through verify_receipts before any compilation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from run import anchors, gate
from verify_receipts import verify as verify_native

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPECTED = '08a3143c0f6ad6dd6dbf29a5457e197fcfa05ec85a4cf4f04cde60af0edb7b38'
REQUIRED = ['source/core/StarBuffer.cpp', 'source/core/StarBuffer.hpp',
            'source/core/StarRustBuffer.h', 'source/core/StarBufferHost.hpp',
            'source/core/StarIODevice.hpp', 'source/core/StarByteArray.hpp',
            'source/rust/ffi/src/buffer.rs', 'source/rust/ffi/src/lib.rs',
            'source/CMakeLists.txt']
CONTROLS = ('native-bypass', 'receipt-zero', 'wrong-pending', 'getter-bypass')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def freeze(path, archive, digest):
    need(path.is_absolute() and archive.is_absolute(), 'absolute handshake paths required')
    bindings = json.loads(path.read_text())
    need(isinstance(bindings, dict) and bool(bindings), 'freeze must be path -> sha256 map')
    for name, expected in bindings.items():
        need(Path(name).is_absolute() and re.fullmatch('[0-9a-f]{64}', expected), 'freeze schema')
        need(sha(name) == expected, 'parent source drift '+name)
    need(bindings.get(str(archive.resolve())) == digest, 'archive absent from parent freeze')
    for name in REQUIRED:
        need(str((ROOT/name).resolve()) in bindings, 'missing frozen input '+name)
    need(re.fullmatch('[0-9a-f]{64}', digest) and sha(archive) == digest, 'archive handshake')
    return bindings


def protocol_adapter():
    source = (HERE/'host_contract_test.cpp').read_text()
    old = '#include "host_contract.cpp"'
    need(source.count(old) == 1, 'protocol include contract')
    source = source.replace(old, '''#include "StarBufferHost.hpp"
using namespace Star;
using namespace Star::BufferRust;
using SbBufferHost = StarBufferHost;
static uint32_t sb_buffer_run(uint32_t mode,void* ctx,SbBufferHost host) {
  return star_buffer_run(mode,ctx,host);
}''', 1)
    foreign = '  assert(sb_buffer_run(SB_B_EMPTY,nullptr,foreignThrow)==3); // C++ only, no Rust unwind claim.\n'
    need(source.count(foreign) == 1, 'foreign-throw removal contract')
    source = source.replace(foreign, '', 1)
    return source


DRIVER = r'''
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include "StarRustBuffer.h"
#include "StarBuffer.hpp"
#include <iostream>
#include <cstdint>
static thread_local uint64_t routes[50][4]{};
extern "C" uint32_t buffer_observed_run(uint32_t mode,void* ctx,StarBufferHost host) {
  auto status=star_buffer_run(mode,ctx,host);
  #ifdef WRONG_PENDING
  if(status==1)status=2;
  #endif
  if(mode<50&&status<4)++routes[mode][status];
  return status;
}
#define main buffer_original_main
#include "lab.cpp"
#undef main
int main(){
  uint64_t before[50][3]{};
  for(unsigned m=0;m<50;++m)for(unsigned e=0;e<3;++e)before[m][e]=star_buffer_call_count(m,e);
  int result=buffer_original_main();
  Star::Buffer caller(Star::ByteArray(16,'Q'));caller.resize(4);
  auto callerPtr=caller.ptr();Star::Buffer const& callerConst=caller;
  bool stable=callerPtr==callerConst.ptr() && &caller.data()==&callerConst.data();
  auto callerMode=(unsigned)caller.mode();auto callerPosition=caller.pos();auto callerSize=caller.size();
  std::cerr<<"BUFFER_RECEIPTS {\"counts\":[";
  for(unsigned m=0;m<50;++m){if(m)std::cerr<<',';std::cerr<<'[';
    for(unsigned e=0;e<3;++e){if(e)std::cerr<<',';
#ifdef ZERO_RECEIPTS
      std::cerr<<0;
#else
      std::cerr<<(star_buffer_call_count(m,e)-before[m][e]);
#endif
    }std::cerr<<']';}
  std::cerr<<"],\"routes\":[";
  for(unsigned m=0;m<50;++m){if(m)std::cerr<<',';std::cerr<<'[';
    for(unsigned s=0;s<4;++s){if(s)std::cerr<<',';std::cerr<<routes[m][s];}std::cerr<<']';}
  std::cerr<<"],\"nativeCaller\":{\"mode\":"<<callerMode<<",\"position\":"<<callerPosition<<",\"size\":"<<callerSize<<",\"pointerStable\":"<<(stable?"true":"false")<<"}}\n";
  return result;
}
'''


def observation(stderr):
    lines = [line[len(b'BUFFER_RECEIPTS '):] for line in stderr.splitlines()
             if line.startswith(b'BUFFER_RECEIPTS ')]
    need(len(lines) == 1, 'one receipt observation required')
    return json.loads(lines[0])


def qualification(data, receipt):
    need(anchors(data) == 583 and hashlib.sha256(data).hexdigest() == EXPECTED, 'native ordered values')
    need(set(receipt) == {'counts', 'routes', 'nativeCaller'}, 'receipt schema')
    need(receipt['nativeCaller'] == dict(mode=3, position=0, size=4, pointerStable=True), 'actual native caller state')
    for key, width in (('counts', 3), ('routes', 4)):
        need(len(receipt[key]) == 50, 'mode scope')
        for row in receipt[key]:
            need(len(row) == width and all(type(n) is int and 0 <= n < 2**64 for n in row), 'counter schema')
    for mode, (counts, routes) in enumerate(zip(receipt['counts'], receipt['routes'])):
        attempt, success, pending = counts
        need(attempt > 0 and attempt == success+pending, 'positive balanced Rust mode')
        # ExternalBuffer write/writeAbsolute unconditionally throw in the frozen
        # source; a status-0 observation for either would contradict ERROR.
        if mode in (37, 39):
            need(success == 0 and pending > 0, 'unconditional native write exception')
        else:
            need(success > 0, 'successful Rust mode absent')
        need(routes == [success, pending, 0, 0], 'C++ returned-status routes')
    need(sum(row[2] for row in receipt['counts']) > 0, 'native pending not observed')
    attempts = [row[0] for row in receipt['counts']]
    # Source constructors delegate to Buffer() before their own Rust controller.
    need(attempts[0] >= sum(attempts[1:5]), 'constructor child graph')
    # resize/ptr/reserve each call mutable data() before native storage access.
    need(attempts[16] >= attempts[7]+attempts[19]+attempts[22], 'mutable data child graph')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-source-freeze', required=True, type=Path)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--values', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    tracked = freeze(args.parent_source_freeze, args.archive, args.archive_sha256)
    native_report = args.values.resolve()/'report.json'
    verify_native(native_report)
    native = json.loads(native_report.read_text())
    need(native['cases'] == 583 and native['definitions'] == 50 and native['ordered_sha256'] == EXPECTED, 'native scope')
    for ext in ('cpp', 'hpp'):
        gate(ext, (HERE/f'StarBuffer.original.{ext}').read_text(), (HERE/f'StarBuffer.reference.{ext}').read_text())
    for name, digest in native['bindings'].items():
        need(sha(name) == digest, 'native binding drift')
        need(name not in tracked or tracked[name] == digest, 'native/freeze conflict')
        tracked[name] = digest
    for path in [*sorted((ROOT/'source/rust').rglob('*.rs')), *sorted((ROOT/'source/rust').rglob('Cargo.*')),
                 args.parent_source_freeze, args.archive, native_report, Path(__file__), HERE/'verify_candidate.py',
                 HERE/'host_contract_test.cpp', HERE/'lab.cpp', Path(sys.executable).resolve(), Path(native['link']['archive'])]:
        tracked[str(path.resolve())] = sha(path)
    out = args.output.absolute(); base = ROOT/'build/buffer-lab'
    need(not out.exists() and out.is_relative_to(base) and out.name.startswith('rust-')
         and not any(p.is_symlink() for p in [out, *out.parents]), 'fresh owned rust-* output required')
    out.mkdir(parents=True)
    link = native['link']; flags = [*link['flags'], '-UNDEBUG', '-I'+str(HERE), '-I'+str(ROOT/'source/core')]
    need(not any('STAR_USE_RUST' in flag for flag in flags), 'native reference flags changed')
    receipts = []; generated = {}; binaries = {}

    def run(command, name):
        command = list(map(str, command)); executable = Path(command[0]).resolve(); before = sha(executable)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=75)
        for stream in ('stdout', 'stderr'):
            (out/(name+'.'+stream)).write_bytes(getattr(result, stream))
        receipts.append(dict(name=name, command=command, returncode=result.returncode,
                             executable_sha256_before=before, executable_sha256=sha(executable),
                             stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                             stderr_sha256=hashlib.sha256(result.stderr).hexdigest()))
        (out/'receipts.json').write_text(json.dumps(receipts, indent=2)+'\n')
        need(result.returncode == 0 and before == sha(executable), name+' failed; no negative credit')
        return result.stdout, result.stderr

    driver = out/'driver.cpp'; driver.write_text(DRIVER)
    adapter = out/'protocol.cpp'; adapter.write_text(protocol_adapter())
    core = ROOT/'source/core/StarBuffer.cpp'
    for index, source in enumerate((core, driver, adapter)):
        dep = out/f'{index}.d'
        run([link['compiler'], *flags, '-DSTAR_USE_RUST_BUFFER', '-M', '-MF', dep, source], f'deps-{index}')
        for name in shlex.split(dep.read_text().replace('\\\n', ' ').split(':', 1)[1]):
            path = Path(name); path = path if path.is_absolute() else ROOT/path
            key = str(path.resolve())
            if path.resolve().is_relative_to(out):
                generated[key] = sha(path)
            else:
                need(key not in tracked or tracked[key] == sha(path), 'dependency drift')
                tracked[key] = sha(path)
    (out/'before.json').write_text(json.dumps(tracked, indent=2)+'\n')
    run([link['compiler'], *flags, '-x', 'c', '-std=c11', '-pedantic-errors', '-fsyntax-only', ROOT/'source/core/StarRustBuffer.h'], 'c11')
    obj = out/'selected.o'
    run([link['compiler'], *flags, '-DSTAR_USE_RUST_BUFFER', '-Dstar_buffer_run=buffer_observed_run', '-c', core, '-o', obj], 'selected-object')
    symbols, _ = run(['/usr/bin/nm', '-C', '--defined-only', obj], 'selected-symbols')
    definitions = sorted(set(re.findall(r' T (Star::(?:ExternalBuffer|Buffer)::[^\n]+)', symbols.decode())))
    definitions = [name for name in definitions if '::~' not in name]
    need(len(definitions) == 50 and definitions == json.loads((args.values/'compiled-definitions.json').read_text()), 'all 50 compiled members')
    (out/'compiled-definitions.json').write_text(json.dumps(definitions, indent=2)+'\n')

    def compile(source, object_path, name, defines=()):
        binary = out/name
        run([link['compiler'], *flags, *defines, source, object_path, link['archive'], args.archive,
             *link['libraries'], '-Xlinker', '-map', '-Xlinker', out/(name+'.map'), '-o', binary], name+'-compile')
        binaries[str(binary)] = sha(binary)
        need(b'native-core.a(StarBuffer.cpp.o)' not in (out/(name+'.map')).read_bytes(), 'native Buffer archive bypass')
        return binary

    positive = compile(driver, obj, 'candidate')
    data, stderr = run([positive], 'candidate'); seen = observation(stderr); qualification(data, seen)
    repeated, repeated_err = run([positive], 'repeat')
    need(repeated == data and observation(repeated_err) == seen, 'repeat values/routes')
    # Keep the private inline execute() definition identical across protocol
    # translation units; observation renaming belongs only to corpus builds.
    protocol_obj = out/'protocol-selected.o'
    run([link['compiler'], *flags, '-DSTAR_USE_RUST_BUFFER', '-c', core, '-o', protocol_obj], 'protocol-selected-object')
    protocol = compile(adapter, protocol_obj, 'protocol')
    protocol_data, protocol_err = run([protocol], 'protocol')
    need(protocol_data == data and b'buffer native protocol assertions passed' in protocol_err, 'actual native context assertions')
    controls = {}
    native_obj = out/'native.o'
    run([link['compiler'], *flags, '-c', HERE/'StarBuffer.original.cpp', '-o', native_obj], 'native-control-object')
    for name, object_path, defines in [('native-bypass', native_obj, ()), ('receipt-zero', obj, ('-DZERO_RECEIPTS',)),
                                        ('wrong-pending', obj, ('-DWRONG_PENDING',))]:
        binary = compile(driver, object_path, name, defines)
        wrong, err = run([binary], name); need(wrong == data, 'control must preserve native values')
        observed = observation(err)
        try:
            qualification(wrong, observed)
        except ValueError as error:
            controls[name] = str(error)
        else:
            raise ValueError('normally exiting control escaped '+name)
    # Getter control is deliberately exact and fails closed if production changes.
    body = core.read_text(); old = 'StreamOffset Buffer::pos(){BCTX;execute(c,SB_B_POS);return c.result;}'
    need(body.count(old) == 1, 'getter control source contract requires parent review')
    changed = out/'getter.cpp'; changed.write_text(body.replace(old, 'StreamOffset Buffer::pos() { return m_pos; }', 1))
    getter_obj = out/'getter.o'
    run([link['compiler'], *flags, '-DSTAR_USE_RUST_BUFFER', '-Dstar_buffer_run=buffer_observed_run', '-c', changed, '-o', getter_obj], 'getter-object')
    wrong, err = run([compile(driver, getter_obj, 'getter-bypass')], 'getter-bypass')
    need(wrong == data, 'getter control native values')
    try:
        qualification(wrong, observation(err))
    except ValueError as error:
        controls['getter-bypass'] = str(error)
    else:
        raise ValueError('getter bypass escaped')
    verify_native(native_report)
    after = {name: sha(name) for name in tracked}; need(after == tracked, 'input drift')
    (out/'after.json').write_text(json.dumps(after, indent=2)+'\n')
    for path in out.iterdir():
        if path.suffix in ('.cpp', '.o', '.map', '.d') or path.name == 'compiled-definitions.json':
            generated[str(path)] = sha(path)
    report = dict(status='FINITE_ACTUAL_RUST_BUFFER_PASS', cases=583, definitions=50, ordered_sha256=EXPECTED,
                  native_report=str(native_report), parent_source_freeze=str(args.parent_source_freeze),
                  rust_archive=str(args.archive), rust_archive_sha256=args.archive_sha256,
                  bindings=tracked, generated=generated, binaries=binaries, receipts=receipts,
                  observation=seen, normal_controls=controls,
                  limits=['finite native ownership/protocol/corpus only; no game/full-engine/OOM/platform qualification'])
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'status': report['status'], 'cases':583, 'definitions':50}))


if __name__ == '__main__':
    main()
