#!/usr/bin/env python3
"""Production OptionParser bridge replay. Run only after core/archive freeze.

The supplied fresh native calibration supplies independent whole-stream evidence,
not a candidate-derived golden. This runner never invokes Cargo or Ninja.
"""
import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path
import run as native
from verify_receipts import verify as verify_native

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CORE = ROOT / 'source/core'
ARCHIVE = ROOT / 'build/option-parser-rust/target/release/libstar_engine_ffi.a'
ORDERED_SHA256 = '056b5d907385bcb6266b86623b249c1deaa862263fd2ff4bf8232864ff290e4b'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_counts(data, backend='rust'):
    rows = [list(map(int, line.split())) for line in data.decode('ascii').splitlines()]
    if len(rows) != 8 or any(len(r) != 4 or r[0] != i for i, r in enumerate(rows)):
        raise ValueError('counter schema')
    for mode, attempt, success, exception in rows:
        if any(n < 0 or n > (1 << 64) - 1 for n in (attempt, success, exception)):
            raise ValueError('counter range')
        if backend == 'cpp':
            if attempt or success or exception:
                raise ValueError('native bypass unexpectedly entered Rust')
        elif not (attempt > 0 and success > 0 and attempt == success + exception):
            raise ValueError('missing/unbalanced Rust calls: mode ' + str(mode))
    if backend == 'rust' and any(rows[i][3] == 0 for i in (3, 4, 7)):
        raise ValueError('required duplicate/real ostream native exception missing')
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--values', required=True, type=Path,
                        help='fresh run.py native report directory after source freeze')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    values = args.values.absolute()
    verify_native(values / 'report.json')
    report = json.loads((values / 'report.json').read_text())
    if report['ordered_sha256'] != ORDERED_SHA256:
        raise ValueError('native stream differs from pre-port immutable calibration')
    output = args.output.absolute()
    base = ROOT / 'build/option-parser-lab'
    if (output == base or not output.is_relative_to(base) or output.exists()
            or any(p.is_symlink() for p in [output, *output.parents])):
        parser.error('fresh owned nonsymlink output required')
    output.mkdir(parents=True)
    receipts, generated, binaries = [], {}, {}
    link = report['link']
    compiler = link['compiler']
    flags = [*link['flags'], '-I' + str(HERE), '-I' + str(CORE)]
    selected = ['-DSTAR_USE_RUST_OPTION_PARSER']

    def execute(command, name):
        command = list(map(str, command))
        exe = Path(command[0]).resolve()
        sealed = sha(exe)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=100)
        for stream in ('stdout', 'stderr'):
            (output / (name + '.' + stream)).write_bytes(getattr(result, stream))
        if sha(exe) != sealed:
            raise ValueError('executable changed')
        receipts.append(dict(name=name, command=command, executable_sha256=sealed,
                             returncode=result.returncode,
                             stdout_sha256=sha(output / (name + '.stdout')),
                             stderr_sha256=sha(output / (name + '.stderr'))))
        (output / 'receipts.json').write_text(json.dumps(receipts, indent=2))
        if result.returncode != 0:
            raise RuntimeError(name + ' failed; compile/crash is NOT a negative-control pass')
        return result.stdout

    def write(name, body):
        path = output / name
        path.write_text(body)
        generated[str(path)] = sha(path)
        return path

    # The frozen main relied on implicit main return. A renamed function MUST
    # return explicitly, otherwise the adapter would introduce undefined behavior.
    fixture = (HERE / 'lab.cpp').read_text()
    assert fixture.count('int main(){') == 1
    fixture = fixture.replace('"StarOptionParser.original.hpp"', '"StarOptionParser.hpp"')
    fixture = fixture.replace('int main(){', 'int fixture_main(){')
    end = fixture.rfind('}')
    assert not fixture[end + 1:].strip()
    fixture = fixture[:end] + 'return 0;\n' + fixture[end:]
    suffix = '''
int main(int argc,char** argv){
 if(argc!=2)return 2;
 int rc=fixture_main();
 std::ofstream counts(argv[1],std::ios::binary|std::ios::trunc);
 for(uint32_t mode=0;mode<8;++mode){counts<<mode;
  for(uint32_t event=0;event<3;++event)counts<<' '<<COUNTER;
  counts<<'\\n';}
 counts.close();return counts.fail()?3:rc;
}
'''
    head = '#include "StarRustOptionParser.h"\n#include <fstream>\n'
    adapter = write('values.cpp', head + fixture + suffix.replace('COUNTER', 'star_option_parser_call_count(mode,event)'))
    suppressed = write('suppressed.cpp', head + fixture + suffix.replace('COUNTER', 'uint64_t(0)'))
    # Keep production and phase-one enum definitions in separate translation units.
    shim = write('raw-shim.cpp', '#include "StarRustOptionParser.h"\n'
                 'extern "C" uint32_t star_option_parser_lab_controller(uint32_t mode,void* ctx,StarOptionParserLabHost host){return star_option_parser_run(mode,ctx,host);}\n')
    header = write('header.c', '#include "StarRustOptionParser.h"\n_Static_assert(sizeof(uint64_t)==8,"scalar");\n')

    tracked = [Path(p) for p in report['bindings']]
    tracked += [Path(__file__), HERE / 'run.py', HERE / 'verify_receipts.py',
                HERE / 'verify_candidate.py', HERE / 'test_candidate.py', HERE / 'host_contract.hpp',
                HERE / 'host_contract_test.cpp', values / 'report.json',
                values / 'original.stdout', Path(link['archive']), ARCHIVE,
                CORE / 'StarOptionParser.cpp', CORE / 'StarOptionParser.hpp',
                CORE / 'StarRustOptionParser.h', CORE / 'StarOptionParserHost.hpp',
                Path(sys.executable).resolve()]
    tracked += list((ROOT / 'source/rust').rglob('*.rs'))
    tracked += list((ROOT / 'source/rust').rglob('Cargo.toml'))
    tracked += [ROOT / 'source/rust/Cargo.lock']
    for i, file in enumerate([CORE / 'StarOptionParser.cpp', adapter, shim, HERE / 'host_contract_test.cpp']):
        dep = output / (str(i) + '.d')
        execute([compiler, *flags, *selected, '-DSTAR_OPTION_PARSER_LAB_TEST_HOOKS',
                 '-M', '-MF', dep, file], 'dependencies-' + str(i))
        tracked += [Path(p) if Path(p).is_absolute() else ROOT / p for p in
                    shlex.split(dep.read_text().replace('\\\n', ' ').split(':', 1)[1])]
    tracked = list(dict.fromkeys(p.resolve() for p in tracked))
    before = {str(p): sha(p) for p in tracked}
    (output / 'before.json').write_text(json.dumps(before, indent=2))

    def compile(name, cpp, fixture, rust=True, hooks=False, extra=()):
        binary = output / name
        execute([compiler, *flags, *(selected if rust else []),
                 *(['-DSTAR_OPTION_PARSER_LAB_TEST_HOOKS'] if hooks else []),
                 cpp, fixture, *extra, link['archive'], ARCHIVE, *link['libraries'],
                 '-Wl,-dead_strip', '-o', binary], name + '-compile')
        binaries[str(binary)] = sha(binary)
        return binary

    baseline = (values / 'original.stdout').read_bytes()
    assert native.anchors(baseline) == 295
    controls, counts_artifacts = [], {}

    def observe(name, cpp=CORE / 'StarOptionParser.cpp', fixture=adapter, rust=True):
        exe = compile(name, cpp, fixture, rust=rust)
        counts_path = output / (name + '.counts')
        data = execute([exe, counts_path], name)
        if data != baseline:
            raise ValueError('whole independent native stream mismatch: ' + name)
        native.anchors(data)
        counts_artifacts[str(counts_path)] = sha(counts_path)
        return counts_path.read_bytes()

    validate_counts(observe('rust-values'))
    bypass = observe('native-bypass', rust=False)
    validate_counts(bypass, 'cpp')
    suppressed_data = observe('suppressed-receipt', fixture=suppressed)
    for name, data in [('native-bypass', bypass), ('suppressed-receipt', suppressed_data)]:
        try:
            validate_counts(data)
        except ValueError:
            controls.append(name)
        else:
            raise ValueError('clean counter control escaped: ' + name)

    # Preserve the SAME exception_ptr and C++ rethrow. Only corrupt the scalar
    # route, so output equality cannot hide missing native-exception accounting.
    text = (CORE / 'StarOptionParserHost.hpp').read_text()
    old = 'catch(...){pending=std::current_exception();return 1;}'
    if text.count(old) != 1:
        raise ValueError('pending-route control requires explicit source reinspection; do not guess')
    mutant_header = write('pending-host.hpp', text.replace(old, 'catch(...){pending=std::current_exception();return 2;}'))
    cpp_text = (CORE / 'StarOptionParser.cpp').read_text()
    old_include = '"StarOptionParserHost.hpp"'
    assert cpp_text.count(old_include) == 1
    mutant_cpp = write('pending-route.cpp', cpp_text.replace(old_include, json.dumps(str(mutant_header))))
    wrong = observe('pending-route', cpp=mutant_cpp)
    try:
        validate_counts(wrong)
    except ValueError:
        controls.append('pending-route')
    else:
        raise ValueError('clean pending-route mutant escaped')

    # Corrupt selected wrapper dispatch ONLY in an isolated translation unit.
    # This still executes Rust and returns normally, so values (not receipts)
    # must reject it. Match the exact frozen wrapper before editing anything.
    old_dispatch = 'this,0,m_commandName,m_summary,m_additionalHelp,m_options,m_arguments'
    if cpp_text.count(old_dispatch) != 1:
        raise ValueError('selected dispatch control requires explicit source reinspection')
    dispatch_cpp = write('selected-dispatch.cpp', cpp_text.replace(old_dispatch,
                         'this,1,m_commandName,m_summary,m_additionalHelp,m_options,m_arguments'))
    dispatch_exe = compile('selected-dispatch', dispatch_cpp, adapter)
    dispatch_counts = output / 'selected-dispatch.counts'
    dispatch_data = execute([dispatch_exe, dispatch_counts], 'selected-dispatch')
    counts_artifacts[str(dispatch_counts)] = sha(dispatch_counts)
    if dispatch_data == baseline:
        raise ValueError('selected dispatch mutant escaped whole-stream comparison')
    controls.append('selected-dispatch')

    host = compile('rust-host', CORE / 'StarOptionParser.cpp', HERE / 'host_contract_test.cpp',
                   hooks=True, extra=[shim])
    execute([host], 'rust-host')
    execute([compiler, '-x', 'c', '-std=c11', '-pedantic', '-Wall', '-Wextra', '-Werror',
             '-I' + str(CORE), '-fsyntax-only', header], 'strict-c11')
    after = {str(p): sha(p) for p in tracked}
    (output / 'after.json').write_text(json.dumps(after, indent=2))
    if before != after or any(sha(p) != h for p, h in {**generated, **binaries, **counts_artifacts}.items()):
        raise ValueError('bound artifact drift')
    verify_native(values / 'report.json')
    result = dict(status='FINITE_PRODUCTION_RUST_OPTION_PARSER_PASS', cases=295,
                  ordered_sha256=hashlib.sha256(baseline).hexdigest(), controls=controls,
                  native_report=str(values / 'report.json'), bindings=before,
                  generated=generated, binaries=binaries, counts=counts_artifacts,
                  receipts=receipts, limits=['No actual game/screenshots, OOM, performance, other-platform or whole-engine UB claim',
                  'Frozen host tests exercise all 33 operations/24 templates; Rust panic tests belong to Rust unit suite'])
    (output / 'report.json').write_text(json.dumps(result, indent=2))
    from verify_candidate import verify
    print(json.dumps(verify(output / 'report.json'), sort_keys=True))


if __name__ == '__main__':
    main()
