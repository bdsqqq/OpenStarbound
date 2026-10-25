#!/usr/bin/env python3
"""Replay frozen native observations through the actual production Rust bridge.

Requires an explicit parent source/archive freeze. Never invokes Cargo or Ninja.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
LAB = pathlib.Path(__file__).resolve().parent
CORE = ROOT / 'source/core'
EXPECTED = 'e9a14b9a678ad9819b4f17043ef08ccc901270dd1510d9bfcd516083454aa9b1'


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--values', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--rust-archive', type=pathlib.Path, required=True)
    parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--source-sha256', required=True)
    args = parser.parse_args()
    from verify_receipts import verify
    verify(args.values / 'report.json')
    native = json.loads((args.values / 'report.json').read_text())
    link = native['link']
    output = args.output.absolute()
    base = ROOT / 'build/host-address-lab'
    require(output != base and output.is_relative_to(base) and not output.exists()
            and not any(p.is_symlink() for p in [output, *output.parents]), 'fresh owned output required')
    require(sha(CORE / 'StarHostAddress.cpp') == args.source_sha256, 'parent source freeze mismatch')
    require(sha(args.rust_archive) == args.archive_sha256, 'parent archive freeze mismatch')
    require(shutil.disk_usage(ROOT).free > 1024**3, 'below 1GiB stop guard')
    output.mkdir(parents=True)
    receipts, generated, binaries = [], {}, {}
    tracked = dict(native['bindings'])
    tracked[str(pathlib.Path(link['archive']).resolve())] = native['archive_sha256']
    for path in [pathlib.Path(__file__).resolve(), LAB / 'verify_candidate.py',
                 CORE / 'StarHostAddressHost.hpp', CORE / 'StarRustHostAddress.h',
                 LAB / 'host_contract_test.cpp', args.rust_archive.resolve(),
                 ROOT / 'source/CMakeLists.txt', *sorted((ROOT / 'source/rust').rglob('*.rs')),
                 *sorted((ROOT / 'source/rust').rglob('Cargo.toml')),
                 ROOT / 'source/rust/Cargo.lock']:
        if path.is_file():
            tracked[str(path)] = sha(path)

    def run(command, name):
        require(shutil.disk_usage(ROOT).free > 1024**3, 'below 1GiB stop guard')
        command = list(map(str, command))
        executable = pathlib.Path(command[0]).resolve()
        before = sha(executable)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=75)
        for stream in ('stdout', 'stderr'):
            (output / (name + '.' + stream)).write_bytes(getattr(result, stream))
        receipts.append(dict(name=name, command=command, returncode=result.returncode,
                             executable_sha256=before,
                             stdout_sha256=sha(output / (name + '.stdout')),
                             stderr_sha256=sha(output / (name + '.stderr'))))
        (output / 'receipts.json').write_text(json.dumps(receipts, indent=2))
        require(sha(executable) == before, 'executed binary drift')
        require(result.returncode == 0, name + ' execution failed: ' + result.stderr.decode(errors='replace')[-2500:])
        return result.stdout

    def write(name, body):
        path = output / name
        path.write_text(body)
        generated[str(path)] = sha(path)
        return path

    # The original implicit main return must become explicit after renaming.
    corpus = (LAB / 'lab.cpp').read_text()
    require(corpus.count('int main(){') == 1 and corpus.rstrip().endswith('}'), 'corpus main framing')
    corpus = corpus.replace('int main(){', 'int fixture_main(){', 1)
    corpus = corpus.rstrip()[:-1] + 'return 0;\n}\n'
    wrapper = '''
#include "StarRustHostAddress.h"
extern "C" uint64_t lab_route_count(unsigned,unsigned);
extern "C" uint64_t lab_native_count();
int main(){
 uint64_t before[27][3],routeBefore[27][4];for(unsigned m=0;m<27;++m){for(unsigned e=0;e<3;++e)before[m][e]=star_host_address_call_count(m,e);for(unsigned e=0;e<4;++e)routeBefore[m][e]=lab_route_count(m,e);}
 int result=fixture_main();
 for(unsigned m=0;m<27;++m){std::cerr<<"COUNTER "<<m;for(unsigned e=0;e<3;++e)std::cerr<<" "<<(star_host_address_call_count(m,e)-before[m][e]);std::cerr<<"\\n";}
 for(unsigned m=0;m<27;++m){std::cerr<<"ROUTE "<<m;for(unsigned e=0;e<4;++e)std::cerr<<" "<<(lab_route_count(m,e)-routeBefore[m][e]);std::cerr<<"\\n";}
 std::cerr<<"NATIVE "<<lab_native_count()<<"\\n";
 return result;
}
'''
    corpus_file = write('corpus.cpp', corpus + wrapper)
    protocol = (LAB / 'host_contract_test.cpp').read_text()
    require(protocol.count('#include "host_contract.cpp"') == 1, 'protocol inclusion')
    protocol = protocol.replace('#include "host_contract.cpp"', '''#include "StarHostAddressHost.hpp"
using Context = Star::HostAddressRust::Context;
extern "C" uint32_t star_host_address_lab_run(uint32_t m, void* p, StarHostAddressHost h) { return star_host_address_run(m,p,h); }''')
    foreign = ' assert(star_host_address_lab_run(HA_SIZE,nullptr,cppThrow)==HA_PANIC);'
    require(protocol.count(foreign) == 1, 'foreign unwind assertion framing')
    protocol_file = write('protocol.cpp', protocol.replace(foreign, ' // Foreign C++ unwind is forbidden across Rust; omitted.'))
    strict = write('strict.c', '#include "StarRustHostAddress.h"\nint main(void){return HA_EP_HASH!=26 || HA_READ_INDEX!=37;}\n')
    run([link['compiler'], '-x', 'c', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
         '-I' + str(CORE), '-fsyntax-only', strict], 'strict-c11')
    flags = [*link['flags'], '-I' + str(CORE), '-I' + str(LAB)]
    # Acquire all actual private-header dependencies before the first candidate build.
    for i, source in enumerate((CORE / 'StarHostAddress.cpp', protocol_file, corpus_file)):
        dep = output / (str(i) + '.d')
        run([link['compiler'], *flags, '-DSTAR_USE_RUST_HOST_ADDRESS', '-M', '-MF', dep, source], 'deps' + str(i))
        import shlex
        for name in shlex.split(dep.read_text().replace('\\\n', ' ').split(':', 1)[1]):
            path = pathlib.Path(name)
            if not path.is_absolute():
                path = ROOT / path
            tracked[str(path.resolve())] = sha(path)
    (output / 'before.json').write_text(json.dumps(tracked, indent=2))
    for path, expected in tracked.items():
        require(sha(path) == expected, 'input drift before: ' + path)

    def compile(name, sources, selected=True, extra=()):
        exe = output / name
        command = [link['compiler'], *flags, *(['-DSTAR_USE_RUST_HOST_ADDRESS'] if selected else []),
                   *extra, *sources, link['archive'], args.rust_archive, *link['libraries'],
                   '-framework', 'Security', '-framework', 'SystemConfiguration', '-liconv',
                   '-Wl,-dead_strip', '-o', exe]
        run(command, name + '-compile')
        binaries[str(exe)] = sha(exe)
        return exe

    original = compile('original', [LAB / 'lab.cpp', LAB / 'StarHostAddress.original.cpp'], False)
    baseline = run([original], 'original')
    require(hashlib.sha256(baseline).hexdigest() == EXPECTED, 'immutable ordered literal stream')
    spec = importlib.util.spec_from_file_location('native_oracle', LAB / 'run.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    require(oracle.anchors(baseline) == 430, 'literal record anchors')
    reference = compile('reference', [LAB / 'lab.cpp', LAB / 'StarHostAddress.reference.cpp'], False, ['-DLAB_REFERENCE'])
    require(run([reference], 'reference') == baseline, 'reference whole stream')
    shim_base = '''#include "StarRustHostAddress.h"
static uint64_t routes[27][4];
extern "C" uint64_t lab_native_count(){return 0;}
extern "C" uint64_t lab_route_count(unsigned m,unsigned e){return routes[m][e];}
extern "C" uint32_t lab_dispatch(uint32_t m,void* c,StarHostAddressHost h){uint32_t s=star_host_address_run(m,c,h);RETURN_STATUS if(m<27){++routes[m][0];++routes[m][s==0?1:s==1?2:3];}return s;}
'''
    def dispatch_object(name):
        obj = output / (name + '.o')
        run([link['compiler'], *flags, '-DSTAR_USE_RUST_HOST_ADDRESS', '-Dstar_host_address_run=lab_dispatch',
             '-c', CORE / 'StarHostAddress.cpp', '-o', obj], name + '-object')
        generated[str(obj)] = sha(obj)
        return obj
    selected_object = dispatch_object('selected')
    selected_shim = write('selected-shim.cpp', shim_base.replace('RETURN_STATUS', ''))
    selected = compile('candidate', [corpus_file, selected_object, selected_shim])
    for name in ('candidate', 'repeat'):
        require(run([selected], name) == baseline, 'candidate whole stream ' + name)
    protocol_exe = compile('protocol', [protocol_file, CORE / 'StarHostAddress.cpp'])
    run([protocol_exe], 'protocol')
    # Correct numbers from a native bypass must still fail backend qualification.
    bypass_shim = write('bypass-shim.cpp', '#include <stdint.h>\nextern "C" uint64_t lab_route_count(unsigned,unsigned){return 0;}\n')
    bypass_source = (CORE / 'StarHostAddress.cpp').read_text()
    needle = 'NetworkMode HostAddress::mode() const {'
    require(bypass_source.count(needle) >= 1, 'native observer anchor')
    bypass_source = 'static unsigned long long nativeObserver=0;\nextern "C" unsigned long long lab_native_count(){return nativeObserver;}\n' + bypass_source
    bypass_source = bypass_source.replace(needle, needle + '\n ++nativeObserver;')
    bypass_native = write('bypass-native.cpp', bypass_source)
    bypass = compile('native-bypass', [corpus_file, bypass_native, bypass_shim], False)
    require(run([bypass], 'native-bypass') == baseline, 'native bypass setup values')
    controls = ['native-bypass']
    # Both controls call the real Rust implementation. Only receipt routing or
    # the pending status of constructor 3 changes; values must still exit normally.
    for name, result in [('pending-route', 'if(m==3&&s==1)s=2;')]:
        shim = write(name + '.cpp', shim_base.replace('RETURN_STATUS', result))
        # Rename calls in the native production TU only, never the Rust export.
        exe = compile(name, [corpus_file, shim, selected_object])
        require(run([exe], name) == baseline, name + ' normal values')
        controls.append(name)
    suppressed = write('suppressed.cpp', (corpus + wrapper).replace('star_host_address_call_count(m,e)', '(uint64_t(0))'))
    exe = compile('suppressed-receipt', [suppressed, selected_object, selected_shim])
    require(run([exe], 'suppressed-receipt') == baseline, 'suppressed normal values')
    controls.append('suppressed-receipt')
    after = {path: sha(path) for path in tracked}
    (output / 'after.json').write_text(json.dumps(after, indent=2))
    require(after == tracked, 'input drift after')
    report = dict(status='FINITE_ACTUAL_RUST_HOST_ADDRESS_PASS', cases=430, ordered_sha256=EXPECTED,
                  bindings=tracked, generated=generated, binaries=binaries, receipts=receipts,
                  controls=controls, source_sha256=args.source_sha256,
                  rust_archive=str(args.rust_archive.resolve()), rust_archive_sha256=args.archive_sha256,
                  native_values=str((args.values / 'report.json').resolve()),
                  limits=['Finite 430 records and selected native context guards only; no game/TCP/platform/performance qualification',
                          'Scripted resolver results are counterfactual; only canonical 127.0.0.1 reaches libc',
                          'Foreign C++ throw assertion omitted; Rust contained panic requires separate Cargo test',
                          'No allocation fault/destructor timing qualification'])
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    from verify_candidate import verify as verify_candidate
    try:
        result = verify_candidate(output / 'report.json')
    except Exception as error:
        report['status'] = 'INCOMPLETE_REJECTED_BY_INDEPENDENT_VERIFIER'
        report['verification_error'] = str(error)
        (output / 'report.json').write_text(json.dumps(report, indent=2))
        raise
    print(json.dumps(result))


if __name__ == '__main__':
    main()
