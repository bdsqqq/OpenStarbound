#!/usr/bin/env python3
"""Finite current-production StringView kernel qualification; no Cargo/project build.

All 113 objects are rebuilt per selector. Historical qualification authenticates
only immutable snapshots, never excuses drift in old current-source bindings.
The Rust protocol omits exactly one foreign-unwind invocation; Rust panic tests
are owned by the Rust module. No full application/platform attestation is made.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shlex
import sys
sys.dont_write_bytecode = True
import run as native
import contract
import callback_contract
import inventory
import host_run

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'build/string-view-rust/runner-worker-r1'
ARCHIVE = ROOT / 'build/string-view-rust/aggregate-r1/release/libstar_engine_ffi.a'
# Cargo's explicit-target CMake output is a separate artifact, not silently
# interchangeable with the initial aggregate. Each accepted image is rerun.
ARCHIVES = (ARCHIVE, ROOT / 'build/behavior/string-view-combined-r1/candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a')

def select_archive(path):
    selected = Path(path).resolve()
    need(selected in ARCHIVES, 'unknown aggregate artifact path')
    return selected
QUALIFIED = ROOT / 'build/string-view-lab/host-prototype-r1/parent-span-r4'
STATUS = 'FINITE_PRODUCTION_STRINGVIEW_RUST_PASS'
sha, dump, need = native.sha, native.dump, native.need
PINS = {
 'host_header.hpp': '12a3e198e9c0ee27beb36c80ee1fe0a01ca7915bc3218a1bc66da8585ea5c35a',
 'host_body.cpp': '15b2b0bc0f91b6a72e1a41abf58b2158bd51f095daa77366f7a84031184c2e15',
 'host_wrapper.cpp': 'fdc60c4b9242fb56d9434b526440f16108357e1778206605657db682fd2ed251',
 'host_api.h': 'c19909cba8d611e686a48f8779a5b366cc3f3dcb9d4a201e57d2d104ea812aeb',
 'host_test.cpp': '5c7e1587b261558d88f31b79a8ca0228cc20acf2a183412028a8ae6a2f8ad17b',
 'host_controller.cpp': '5cecfba6954996986ee8c75a8157f713e2d9cacf247d8f2f242bae58e40bddc5',
}
OMITTED = 'need(sb_string_view_run(4,&c,throwing)==3);'


def rename(text):
    return text.replace('StringViewHost', 'StringViewRust').replace('sb_string_view_', 'star_string_view_')


def authenticate():
    inventory.check()
    need(sha(QUALIFIED/'report.json') == 'c7a93dc3e6e7b04141b076faef7f65d340454fa2d438dca5f853bec2cc9d7231', 'qualified report pin')
    q = json.loads((QUALIFIED/'report.json').read_text())
    need(q['status'] == 'FINITE_NATIVE_STRINGVIEW_HOST_PASS', 'qualified status')
    old = {}
    for name, digest in PINS.items():
        p = QUALIFIED/'snapshots'/name
        need(sha(p) == digest == q['bindings'][str(p)], 'qualified snapshot '+name)
        old[name] = p.read_text()
        need((HERE/name).read_text() == old[name], 'current prototype drift '+name)
    # Exact branch bytes: preserve the entire original fallback and public header.
    cpp = (ROOT/'source/core/StarStringView.cpp').read_bytes()
    prefix, sep, suffix = b'#ifdef STAR_USE_RUST_STRING_VIEW\n', b'\n#else\n', b'\n#endif\n'
    need(cpp.startswith(prefix) and cpp.endswith(suffix) and cpp.count(sep)==1, 'outer selector')
    selected, fallback = cpp[len(prefix):-len(suffix)].split(sep)
    need(fallback == (HERE/'StarStringView.original.cpp').read_bytes(), 'exact fallback')
    need(sha(HERE/'StarStringView.original.cpp') == inventory.ORIGINAL_SHA, 'original cpp pin')
    need(sha(ROOT/'source/core/StarStringView.hpp') == inventory.HEADER_SHA, 'public header pin')
    wrapper = rename(old['host_wrapper.cpp']).replace('"host_header.hpp"', '"StarStringViewHost.hpp"')
    need(selected == wrapper.encode(), 'qualified wrapper reconstruction')
    host = old['host_header.hpp']+'\n'+old['host_body.cpp'].replace('#include "host_header.hpp"\n','')
    host = rename(host.replace('"host_api.h"','"StarRustStringView.h"'))
    host = host.replace('uint32_t host(', 'inline uint32_t host(').replace('void execute(', 'inline void execute(')
    need((ROOT/'source/core/StarStringViewHost.hpp').read_text() == host, 'qualified host reconstruction')
    api = old['host_api.h'].replace('SB_STRING_VIEW_HOST_API_H','STAR_RUST_STRING_VIEW_H').replace('SbStringView','StarStringView').replace('sb_string_view_', 'star_string_view_')
    api = api.replace('3 prototype-only\n * containment of an incorrectly throwing host.', '3 contained Rust\n * panic. A host must NEVER unwind through Rust.')
    need((ROOT/'source/core/StarRustStringView.h').read_text()==api, 'exact ABI reconstruction')
    return old


def generated(old):
    protocol = old['host_test.cpp']
    need(protocol.count(OMITTED)==1, 'one foreign throw omission')
    adapt = lambda s: rename(s).replace('"host_header.hpp"', '"StarStringViewHost.hpp"')
    controller = old['host_controller.cpp'].replace('"host_api.h"','"StarRustStringView.h"').replace('SbStringViewHost','StarStringViewHost').replace('sb_string_view_','star_string_view_')
    return {'protocol-native.cpp': adapt(protocol),
            'protocol-rust.cpp': adapt(protocol.replace(OMITTED,'')),
            'controller-native.cpp': controller}


def inputs(out, rs, libs):
    paths = [p for p in HERE.iterdir() if p.is_file()]
    paths += [QUALIFIED/'report.json', *[QUALIFIED/'snapshots'/n for n in PINS]]
    paths += [ROOT/n for n in ('source/core/StarStringView.cpp','source/core/StarStringView.hpp',
        'source/core/StarStringViewHost.hpp','source/core/StarRustStringView.h',
        'source/rust/ffi/src/string_view.rs','source/rust/ffi/src/lib.rs','source/CMakeLists.txt',
        'source/rust/Cargo.toml','source/rust/Cargo.lock','source/rust/ffi/Cargo.toml','cmake/Rust.cmake')]
    paths += [native.CM/n for n in ('build.ninja','compile_commands.json','CMakeCache.txt')]
    paths += [Path(r['source']) for r in rs]+[Path(r['compiler']).resolve() for r in rs]
    paths += [Path(p) for p in libs if Path(p).is_file()]
    paths += [ARCHIVE, Path(sys.executable).resolve(), Path('/usr/bin/nm').resolve()]
    paths += [out/n for n in ('recipes.json','libraries.json','input.tsv','expected.jsonl','callback-expected.jsonl','definition-map.json', *generated(authenticate()))]
    return {str(p.resolve()):sha(p) for p in paths}


def jobs(out, rs):
    r = rs[92]
    result = []
    for backend in ('native','rust'):
        extra = [] if backend=='native' else ['-DSTAR_USE_RUST_STRING_VIEW']
        for i, recipe in enumerate(rs):
            result.append((backend+'/'+str(i), recipe['compiler'], [*recipe['flags'],*extra], Path(recipe['source'])))
        for name, source, flags in [('driver',HERE/'lab.cpp',[]),('callback',HERE/'callback.cpp',[]),
                ('audit',out/'protocol-rust.cpp',['-DSV_CORPUS_AUDIT']),
                ('protocol',out/('protocol-'+backend+'.cpp'),[])]:
            result.append((backend+'/'+name,r['compiler'],[*r['flags'],*extra,*flags],source))
    result.append(('native/controller',r['compiler'],r['flags'],out/'controller-native.cpp'))
    return result


def plan(out, rs, libs):
    """Reconstruct exact commands, including order; no receipt-supplied argv trust."""
    r = rs[92]; alljobs = jobs(out,rs); result = []
    for phase in ('deps','compile'):
        for n,c,f,s in alljobs:
            args = [c,*f,'-M','-MF',out/(n+'.d'),s] if phase=='deps' else [c,*f,'-c',s,'-o',out/(n+'.o')]
            result.append((phase+'-'+n.replace('/','-'),args))
    for backend in ('native','rust'):
        extra = [] if backend=='native' else ['-DSTAR_USE_RUST_STRING_VIEW']
        result += [('symbols-'+backend,['/usr/bin/nm','-gUC',out/backend/'92.o']),
                   ('c11-'+backend,[r['compiler'],*extra,'-x','c','-std=c11','-pedantic-errors','-fsyntax-only',ROOT/'source/core/StarRustStringView.h'])]
        objects = [out/backend/(str(i)+'.o') for i in range(113)]
        for name in ('corpus','callback','protocol'):
            driver = {'corpus':'driver','callback':'callback','protocol':'protocol'}[name]
            linked = [out/backend/(driver+'.o')]
            if name=='corpus': linked += [out/backend/'audit.o']
            linked += objects
            # Native corpus links the sole Rust archive for counters only. Its
            # zero receipts must fail the positive gate despite identical values.
            if name=='protocol' and backend=='native': linked += [out/'native/controller.o']
            else: linked += [ARCHIVE]
            target = out/backend/name
            result.append(('link-'+backend+'-'+name,[r['compiler'],*r['flags'],*extra,*linked,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(target)+'.map','-o',target]))
    for backend in ('native','rust'):
        for name in ('corpus','callback','protocol'):
            for repeat in ('','-repeat'):
                result.append((backend+'-'+name+repeat,[out/backend/name]))
    return [(name,list(map(str,args))) for name,args in result]


def dependencies(out, rs):
    result = {}
    for n,_,_,_ in jobs(out,rs):
        words = shlex.split((out/(n+'.d')).read_text().replace('\\\n',' ').split(':',1)[1])
        for word in words:
            p = Path(word);p = p if p.is_absolute() else native.CM/p
            result[str(p.resolve())] = sha(p)
    return result


def symbols(path):
    names = {line.split(' T ',1)[1] for line in path.read_text().splitlines() if ' T ' in line}
    groups = {k:[] for k in inventory.COUNTS}
    for name in names:
        if name.startswith('Star::StringView::'): groups['member'].append(name)
        elif name.startswith(('Star::String::String(', 'Star::String::operator+=(')) and ('Star::StringView' in name or 'basic_string_view<char' in name):groups['string-bridge'].append(name)
        elif name.startswith('Star::operator') and 'Star::StringView' in name:groups['free'].append(name)
        elif 'formatter<Star::StringView' in name and '::format(' in name:groups['formatter'].append(name)
    need({k:len(v) for k,v in groups.items()} == inventory.COUNTS, '58 compiled definitions')
    return {k:sorted(v) for k,v in groups.items()}


def observations(out):
    need(len(contract.corpus()[1])==8332 and len(callback_contract.expected())==14,'fixed case domain')
    expected = contract.canon(contract.corpus()[1]); callbacks = callback_contract.canon(callback_contract.expected())
    need((out/'expected.jsonl').read_bytes()==expected,'oracle bytes')
    need((out/'callback-expected.jsonl').read_bytes()==callbacks,'callback oracle bytes')
    need((out/'input.tsv').read_text()==''.join('\t'.join(c)+'\n' for c in contract.corpus()[0]),'corpus inputs')
    for backend in ('native','rust'):
        for repeat in ('','-repeat'):
            stem = backend+'-corpus'+repeat
            need((out/(stem+'.stdout')).read_bytes()==expected,'8332 exact cases '+stem)
            host_run.counts(out/(stem+'.stderr'),backend=='rust')
            need((out/(backend+'-callback'+repeat+'.stdout')).read_bytes()==callbacks,'14 exact callbacks')
            need((out/(backend+'-protocol'+repeat+'.stdout')).read_bytes()==b'NATIVE_STRINGVIEW_PROTOCOL_PASS\n','native context protocol')
        need((out/(backend+'-corpus.stderr')).read_bytes()==(out/(backend+'-corpus-repeat.stderr')).read_bytes(),'counter repeat')
    try:host_run.counts(out/'native-corpus.stderr',True)
    except ValueError as error: rejection = str(error)
    else:raise ValueError('native bypass escaped')
    need(symbols(out/'symbols-native.stdout')==symbols(out/'symbols-rust.stdout'),'identical compiled boundary')
    return rejection


def verify(out):
    """Read-only; reconstruct sources, closure, commands and all semantic gates."""
    need(out.is_relative_to(BASE) and out!=BASE,'owned output')
    old = authenticate(); q=json.loads((out/'report.json').read_text())
    need(q['status']==STATUS and q['cases']==8332 and q['callbacks']==14 and q['modes']==58 and q['objects_per_backend']==113,'scope')
    need(q['archive']==str(ARCHIVE) and q['archive_sha256']==sha(ARCHIVE),'sole archive identity')
    for group in ('bindings','artifacts'):
        for p,h in q[group].items():need(sha(p)==h,'drift '+p)
    for name,text in generated(old).items():need((out/name).read_text()==text,'protocol reconstruction '+name)
    rs,libs=native.recipe()
    need(json.loads((out/'recipes.json').read_text())==rs and json.loads((out/'libraries.json').read_text())==libs,'current native recipes')
    need(q['bindings']==json.loads((out/'before.json').read_text())==json.loads((out/'after.json').read_text()),'before/after equality')
    required = {**inputs(out,rs,libs),**dependencies(out,rs)}
    need(all(q['bindings'].get(p)==h for p,h in required.items()),'complete closure binding')
    need(json.loads((out/'initial.json').read_text())==inputs(out,rs,libs),'initial freeze')
    need(json.loads((out/'definition-map.json').read_text())==contract.source_map() and len(contract.source_map())==58,'definition model')
    commands = q['commands'];need(commands==json.loads((out/'commands.json').read_text()),'commands')
    expected = plan(out,rs,libs)
    need([(c['name'],c['command']) for c in commands]==expected,'exact command plan')
    for c in commands:
        need(c==json.loads((out/(c['name']+'.command.json')).read_text()),'command receipt')
        need(type(c['returncode']) is int and c['returncode']==0,'normal exit')
        need(str(Path(c['command'][0]).resolve())==c['executable'] and sha(c['executable'])==c['before']==c['after'],'executable identity')
        for stream in ('stdout','stderr'):need(sha(out/(c['name']+'.'+stream))==c[stream],'stream identity')
    pre = json.loads((out/'preexecute.json').read_text())
    for p,h in pre.items():need(sha(p)==h,'preexecution artifact drift '+p)
    required_artifacts = [out/(n+'.o') for n,_,_,_ in jobs(out,rs)]
    required_artifacts += [out/b/n for b in ('native','rust') for n in ('corpus','callback','protocol')]
    need(all(str(p) in pre for p in required_artifacts),'preexecution compiled artifacts')
    need(q['bypass_rejection']==observations(out),'bypass rejection')
    return q


def run(out):
    need(out.is_relative_to(BASE) and out!=BASE and not out.exists(),'fresh owned path required')
    old=authenticate();need(ARCHIVE.is_file(),'parent aggregate must exist; no Cargo allowed')
    rs,libs=native.recipe()
    need(len(rs)==113 and Path(rs[92]['source']).name=='StarStringView.cpp','113 recipes / index92')
    need(not any('star_rust' in p or 'star_engine_ffi' in p or 'libstar_core' in p for p in libs),'native libraries only')
    out.mkdir(parents=True)
    for backend in ('native','rust'):(out/backend).mkdir()
    for name,text in generated(old).items():(out/name).write_text(text)
    dump(out/'recipes.json',rs);dump(out/'libraries.json',libs)
    cases,rows=contract.corpus()
    (out/'input.tsv').write_text(''.join('\t'.join(c)+'\n' for c in cases))
    (out/'expected.jsonl').write_bytes(contract.canon(rows))
    (out/'callback-expected.jsonl').write_bytes(callback_contract.canon(callback_contract.expected()))
    dump(out/'definition-map.json',contract.source_map())
    initial=inputs(out,rs,libs);dump(out/'initial.json',initial)
    expected=plan(out,rs,libs);commands=[];count=len(jobs(out,rs))
    def command(item):
        name,args=item
        data=(out/'input.tsv').read_bytes() if name in ('native-corpus','native-corpus-repeat','rust-corpus','rust-corpus-repeat') else None
        return native.cmd(args,name,out,data)
    with ThreadPoolExecutor(max_workers=6) as pool:commands.extend(pool.map(command,expected[:count]))
    bindings={**initial,**dependencies(out,rs)}
    need(all(sha(p)==h for p,h in initial.items()),'scan drift')
    # Snapshot the actual source closure before compilation/execution, including
    # oracle/generator bytes. SDK and library identities remain hash-only.
    for path,digest in list(bindings.items()):
        src=Path(path)
        if src.is_relative_to(ROOT/'source'):
            dest=out/'snapshots'/src.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(src.read_bytes())
            need(sha(dest)==digest,'snapshot drift');bindings[str(dest)]=digest
    dump(out/'before.json',bindings)
    with ThreadPoolExecutor(max_workers=6) as pool:commands.extend(pool.map(command,expected[count:2*count]))
    for item in expected[2*count:-12]:commands.append(command(item))
    dump(out/'preexecute.json',{str(p):sha(p) for p in out.rglob('*') if p.is_file()})
    need(all(sha(p)==h for p,h in bindings.items()),'before native execution drift')
    for item in expected[-12:]:commands.append(command(item))
    rejection=observations(out)
    after={p:sha(p) for p in bindings};dump(out/'after.json',after);need(bindings==after,'execution drift')
    dump(out/'commands.json',commands)
    q=dict(status=STATUS,cases=8332,callbacks=14,modes=58,objects_per_backend=113,
        archive=str(ARCHIVE),archive_sha256=sha(ARCHIVE),bindings=bindings,commands=commands,bypass_rejection=rejection,
        protocol_omission=OMITTED,mode48='private helper has a positive internal controller receipt; 58 compiled source definitions',
        limitations=['finite unsigned local macOS arm64 kernel evidence only; no game/full application gate',
          'SDK framework implementation binaries are not transitively byte-attested; exact local tool/SDK headers are bound',
          'CMake default-OFF/aggregate selection checks belong to parent; CMake bytes bound, no project build',
          'no arbitrary pointer/lifetime/OOM/performance/platform proof; known native context checks only',
          'Rust panic is tested by parent Rust-only tests; no foreign C++ unwind invoked through Rust',
          'before/after identities cannot detect transient edits reverted between snapshots'],
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file()})
    dump(out/'report.json',q);verify(out)
    print(STATUS,sha(out/'report.json'),out/'report.json',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=('run','verify'));parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--archive',type=Path,default=ARCHIVE)
    args=parser.parse_args();out=args.output.resolve();ARCHIVE=select_archive(args.archive)
    if args.phase=='run':run(out)
    else:print(verify(out)['status'])
