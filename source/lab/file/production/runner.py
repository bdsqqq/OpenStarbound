#!/usr/bin/env python3
"""Current production File qualification. Never builds Rust or the project.

Historical receipts authenticate only exact snapshots. All native objects and
all current header closures are acquired afresh. See README.md for proof limits.
"""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import time
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))
import run as native
import contract
import supplement
import inventory
spec = importlib.util.spec_from_file_location('removal_model', LAB/'removal/calibrate.py')
removal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(removal)
ROOT = native.ROOT
BASE = ROOT/'build/file-rust/runner-worker-r1'
ARCHIVE = ROOT/'build/file-rust/aggregate-r1/release/libstar_engine_ffi.a'
ARCHIVES = (ARCHIVE,
    ROOT/'build/behavior/file-combined-r1/candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a',
    ROOT/'build/behavior/file-combined-r2/candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a')
QUALIFIED = ROOT/'build/file-lab/host-worker-r1/final-r4'
PIN = '3b12952507e944bf7520a7014b23409aede621c1a6a74082badeb41e920ded4e'
STATUS = 'FINITE_CURRENT_PRODUCTION_FILE_RUST_PASS'
OMITTED = 'need(file_host_run(15,&dummy,throws)==3);'
SNAPSHOTS = ('README.md','abi.h','acquire.py','controller.cpp','driver.cpp','generate.py','layout.cpp','native.hpp','protocol.cpp','removal_replay.py','strict.c','verify.py','wrappers.cpp')
sha, need, dump = native.sha, native.need, native.dump
LIMITS = [
 'Finite local macOS arm64 production-controller evidence; no game/full engine or other platform proof.',
 'Internal unsafe host: live typed state, valid bounded scalars and operation order, live aligned output disjoint from ALL reachable native state. Guards are not general pointer/alias/temporal proof.',
 'Modes 0/2/3/4/5/7/33 retain native prefixes/returns; TLS counts controller entry, not facade entry. Prefix failures need not count.',
 'Removal is INSTRUMENTED: sole static leaf substitution; no actual OS unlink, permissions, deletion failure or race proof.',
 'Rust panic testing belongs to parent Rust-only tests; no throwing C++ callback is invoked through Rust.',
 'SDK headers/tools/libraries are bound; framework implementation binaries are not transitively attested.',
 'Archive identity and actual linked members are attested; source-to-archive build provenance belongs to parent.',
 'Before/after hashes cannot detect edits reverted between observations; no general OOM/performance/destructor-timing proof.'
]

def load(p):
    return json.loads(Path(p).read_text())

def select_archive(p):
    p = Path(p).resolve()
    need(p in ARCHIVES, 'unknown aggregate artifact path')
    return p

def rename(s):
    for old, new in [('FilePrototype','FileRust'), ('"native.hpp"','"StarFileHost.hpp"'), ('"abi.h"','"StarRustFile.h"'), ('file_host_run','star_file_run'), ('file_host_count','star_file_call_count'), ('file_host_fn','StarFileHost')]:
        s = s.replace(old, new)
    return s

def authenticate():
    """No old verifier and no waiver for drift in historical current-source paths."""
    need(sha(QUALIFIED/'report.json') == PIN, 'historical report pin')
    q = load(QUALIFIED/'report.json')
    old = {}
    snapshots = {str(QUALIFIED/'snapshots'/n) for n in SNAPSHOTS}
    need({p for p in q['bindings'] if Path(p).parent == QUALIFIED/'snapshots'} == snapshots, '13 qualified snapshots')
    for name in SNAPSHOTS:
        p = QUALIFIED/'snapshots'/name
        need(sha(p) == q['bindings'][str(p)], 'historical snapshot '+name)
        need(p.read_bytes() == (LAB/'host'/name).read_bytes(), 'prototype source drift '+name)
        old[name] = p.read_text()
    need(sha(QUALIFIED/'snapshots/wrappers.cpp') == '00e312e46575079e8e997b870e74544e7558b84c7b6badd68c4bc53eff7ee8f3', 'wrapper pin')
    need(sha(QUALIFIED/'snapshots/native.hpp') == 'ed3eef2e194934449f9dccc444598db5afd09bd155e44ad567b3cfcdbcde89cf', 'host pin')
    for name, digest in native.ORIGINALS.items():
        frozen = LAB/name.replace('.', '.original.', 1)
        need(sha(frozen) == digest, 'original pin '+name)
        if name != 'StarFile.cpp':
            need(sha(ROOT/'source/core'/name) == digest, 'unchanged production '+name)
    expected = '#ifdef STAR_USE_RUST_FILE\n'+rename(old['wrappers.cpp'])+'\n#else\n'+(LAB/'StarFile.original.cpp').read_text()+'\n#endif\n'
    need((ROOT/'source/core/StarFile.cpp').read_text() == expected, 'exact production branches')
    host = rename(old['native.hpp']).replace('file native prototype protocol','Rust File ABI protocol failure')
    need((ROOT/'source/core/StarFileHost.hpp').read_text() == host, 'exact native host reconstruction')
    oldcomment = '/* Prototype only: 0 success, 1 captured native exception, 2 protocol error,\n * 3 foreign host throw contained by the native controller. Never cross Rust. */'
    newcomment = '''/*
 * Internal synchronous controller ABI, not general pointer validation.
 * The host owns live native state and supplies bounded scalars in the expected
 * operation order. Output storage must be live, aligned, and disjoint from all
 * reachable native state. Native buffers are never borrowed by Rust.
 * 0 success, 1 captured native exception, 2 protocol error, 3 contained Rust
 * panic. A C++ exception must NEVER unwind through Rust.
 * Counters describe controller entry; typed native setup may precede it.
 */'''
    need(old['abi.h'].count(oldcomment) == 1, 'exact ABI documentation delta')
    api = rename(old['abi.h']).replace('FILE_HOST_PROTOTYPE_H','STAR_RUST_FILE_H').replace(oldcomment,newcomment)
    need((ROOT/'source/core/StarRustFile.h').read_text() == api, 'exact production ABI')
    inventory.check()
    need('_conditional' in inventory.generate(), 'conditional production inventory required')
    need(len(contract.expected().splitlines()) == 139, 'literal 139 observations')
    # Authenticate the historical layout output independently of stale bindings.
    need(sha(QUALIFIED/'layout.stdout') == q['artifacts'][str(QUALIFIED/'layout.stdout')], 'historical layout')
    return old

def generated(old):
    protocol = old['protocol.cpp']
    need(protocol.count(OMITTED) == 1, 'exactly one foreign-unwind invocation')
    platform = (LAB/'StarFile_unix.original.cpp').read_bytes()
    need(platform.count(removal.OLD) == 1, 'unique instrumented leaf')
    instrumented = platform.replace(removal.OLD, removal.NEW)
    need(instrumented.replace(removal.NEW,removal.OLD) == platform, 'outside leaf bytes')
    driver = rename(old['driver.cpp']).replace('"../lab.cpp"', '"'+str(LAB/'lab.cpp')+'"')
    c11 = rename(old['strict.c']) + '''
static uint32_t host(void* ctx,uint32_t op,uint64_t a,uint64_t b,uint64_t c,uint64_t* out) {
  (void)ctx; (void)op; (void)a; (void)b; (void)c; *out=0; return 0;
}
int main(void) {
  int ctx=0;
  if(star_file_run(15,&ctx,host)!=0) return 1;
  if(star_file_call_count(15,0)!=1 || star_file_call_count(15,1)!=1 || star_file_call_count(15,2)!=0) return 2;
  return 0;
}
'''
    return {'driver.cpp':driver, 'protocol-native.cpp':rename(protocol),
      'protocol-rust.cpp':rename(protocol.replace(OMITTED,'')),
      'controller-native.cpp':rename(old['controller.cpp']),
      'layout.cpp':old['layout.cpp'], 'strict.c':c11,
      'StarFile_unix.instrumented.cpp':instrumented.decode()}

def recipes():
    rs, libs = native.recipe()
    need(len(rs) == 113, '113 configured translation units')
    need(len({r['source'] for r in rs}) == 113, 'unique translation units')
    for name in ('StarFile.cpp','StarFile_unix.cpp'):
        need(sum(Path(r['source']).name == name for r in rs) == 1, 'unique '+name)
    need(not any('star_engine_ffi' in s or 'star_rust' in s or 'libstar_core' in s for s in libs), 'native libraries only')
    return rs, libs

def index(rs, name):
    return next(i for i,r in enumerate(rs) if Path(r['source']).name == name)

def jobs(out,rs):
    r = rs[index(rs,'StarFile.cpp')]
    result = []
    for backend in ('native','rust'):
        extra = [] if backend == 'native' else ['-DSTAR_USE_RUST_FILE']
        for i, recipe in enumerate(rs):
            result.append((backend+'/'+str(i),recipe['compiler'],[*recipe['flags'],*extra],Path(recipe['source'])))
        for name, source in [('driver',out/'driver.cpp'),('supplement',LAB/'supplement.cpp'),('protocol',out/('protocol-'+backend+'.cpp')),('layout',out/'layout.cpp'),('removal-driver',LAB/'removal/driver.cpp'),('platform',out/'StarFile_unix.instrumented.cpp')]:
            result.append((backend+'/'+name,r['compiler'],[*r['flags'],*extra],source))
        result.append((backend+'/strict',r['compiler'],['-I'+str(ROOT/'source/core'),'-x','c','-std=c11','-pedantic-errors','-Wall','-Wextra',*extra],out/'strict.c'))
    result.append(('native/controller',r['compiler'],r['flags'],out/'controller-native.cpp'))
    return result

def executions(out):
    p = []
    for backend in ('native','rust'):
        for name in ('corpus','supplement'):
            for rep in ('','-repeat'):
                stem = backend+'-'+name+rep
                p.append((stem,[out/backend/name,out/(stem+'-cases')]))
        for name in ('protocol','layout','c11'):
            p.append((backend+'-'+name,[out/backend/name]))
        for rep in range(2):
            for i,(case,n) in enumerate(removal.CASES):
                p.append((f'{backend}-removal-{rep}-{i}',[out/backend/'removal',out/backend/'trees'/case,str(n)]))
    return p

def plan(out,rs,libs,archive):
    r = rs[index(rs,'StarFile.cpp')]
    p = []
    for phase in ('deps','compile'):
        for name,c,flags,source in jobs(out,rs):
            args = [c,*flags,'-M','-MF',out/(name+'.d'),source] if phase == 'deps' else [c,*flags,'-c',source,'-o',out/(name+'.o')]
            p.append((phase+'-'+name.replace('/','-'),args))
    for backend in ('native','rust'):
        objs = [out/backend/(str(i)+'.o') for i in range(113)]
        controller = out/'native/controller.o' if backend == 'native' else archive
        for name,driver in [('corpus','driver'),('supplement','supplement'),('protocol','protocol'),('layout','layout'),('c11','strict'),('removal','removal-driver')]:
            linked = [out/backend/(driver+'.o')]
            if name in ('corpus','supplement','removal'):
                selected = list(objs)
                if name == 'removal':selected[index(rs,'StarFile_unix.cpp')] = out/backend/'platform.o'
                linked += selected
                # OFF links Rust only for counter getters; no native Rust selector.
                linked += [archive]
            elif name in ('protocol','c11'):linked += [controller]
            target = out/backend/name
            p.append(('link-'+backend+'-'+name,[r['compiler'],*r['flags'],*linked,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(target)+'.map','-o',target]))
        p.append(('symbols-'+backend,['/usr/bin/nm','-gUC',out/backend/(str(index(rs,'StarFile.cpp'))+'.o')]))
        p.append(('symbols-'+backend+'-removal',['/usr/bin/nm','-gUC',out/backend/'removal']))
    p += executions(out)
    return [(n,list(map(str,args))) for n,args in p]

def input_paths(out,rs,libs,archive,old):
    paths = {p.resolve() for p in HERE.iterdir() if p.is_file()}
    paths.update(p.resolve() for p in LAB.iterdir() if p.is_file())
    paths.update(p.resolve() for p in (LAB/'host').iterdir() if p.is_file())
    paths.update(p.resolve() for p in (LAB/'removal').iterdir() if p.is_file())
    paths.update([QUALIFIED/'report.json', QUALIFIED/'layout.stdout',*[QUALIFIED/'snapshots'/n for n in SNAPSHOTS]])
    paths.update(ROOT/n for n in ['source/core/StarFile.cpp','source/core/StarFileHost.hpp','source/core/StarRustFile.h','source/rust/ffi/src/file.rs','source/rust/ffi/src/lib.rs','source/CMakeLists.txt','source/rust/Cargo.toml','source/rust/Cargo.lock','source/rust/ffi/Cargo.toml','cmake/Rust.cmake'])
    paths.update(native.CM/n for n in ['compile_commands.json','build.ninja','CMakeCache.txt'])
    paths.update(Path(r['source']).resolve() for r in rs)
    paths.update(Path(r['compiler']).resolve() for r in rs)
    paths.update(Path(p).resolve() for p in libs if Path(p).is_file())
    paths.update([archive,Path(sys.executable).resolve(),Path('/usr/bin/nm').resolve()])
    paths.update(out/n for n in ['recipes.json','libraries.json','expected.tsv','supplement.expected',*generated(old)])
    paths.update(out/'inputs'/n for n in contract.fixtures())
    paths.update(out/'supplement-inputs'/n for n in supplement.model()[0])
    return paths

def hashes(paths):
    return {str(p):sha(p) for p in sorted(paths)}

def dependencies(out,rs):
    paths, resolved = set(), {}
    for name,_,_,source in jobs(out,rs):
        words = shlex.split((out/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1])
        # Repeated SDK paths describe one immutable input, not another proof.
        # Keep this cache scan-local so each independent verification starts fresh.
        for word in words:
            if word not in resolved:
                p = Path(word)
                resolved[word] = (p if p.is_absolute() else native.CM/p).resolve()
        found = {resolved[word] for word in words}
        need(source.resolve() in found, 'dependency source membership '+name)
        paths.update(found)
    return paths

def snapshot_paths(paths,out):
    return {out/'snapshots'/p.relative_to(ROOT) for p in paths if p.is_relative_to(ROOT/'source')}

def base_artifacts(out,rs,libs,archive,old):
    paths = {out/n for n in ['recipes.json','libraries.json','expected.tsv','supplement.expected','initial.json','before.json',*generated(old)]}
    paths.update(out/'inputs'/n for n in contract.fixtures())
    paths.update(out/'supplement-inputs'/n for n in supplement.model()[0])
    paths.update(out/(n+e) for n,_,_,_ in jobs(out,rs) for e in ('.o','.d'))
    runtime = {n for n,_ in executions(out)}
    paths.update(out/(n+e) for n,_ in plan(out,rs,libs,archive) if n not in runtime for e in ('.stdout','.stderr','.command.json'))
    for b in ('native','rust'):
        paths.update(out/b/(n+e) for n in ('corpus','supplement','protocol','layout','c11','removal') for e in ('','.map'))
        paths.add(out/b/'tree-before.json')
        paths.update(out/b/'trees'/n for n in removal.FILES)
    return paths | snapshot_paths(input_paths(out,rs,libs,archive,old)|dependencies(out,rs),out)

def required_artifacts(out,rs,libs,archive,old):
    paths = base_artifacts(out,rs,libs,archive,old)
    paths.update(out/n for n in ('after.json','commands.json','preexecute.json'))
    for n,_ in executions(out):paths.update(out/(n+e) for e in ('.stdout','.stderr','.command.json'))
    for b in ('native','rust'):
        paths.add(out/b/'tree-after.json')
        for name in ('corpus','supplement'):
            final = contract.final_files() if name == 'corpus' else supplement.model()[2]
            for rep in ('','-repeat'):paths.update(out/(b+'-'+name+rep+'-cases')/n for n in final)
    return paths

def counts(data,positive):
    rows = [list(map(int,line.split())) for line in data.decode().splitlines()]
    need(len(rows)==34 and all(len(r)==4 for r in rows) and [r[0] for r in rows]==list(range(34)), '34 counter rows')
    need(all(a==s+e and (a>0 if positive else a==s==e==0) for _,a,s,e in rows), 'balanced positive counters / zero bypass')

def observations(out,rs):
    need((out/'expected.tsv').read_bytes()==contract.expected(), 'frozen 139 expected bytes')
    need((out/'supplement.expected').read_bytes()==supplement.model()[1], 'frozen supplement bytes')
    native.audit(out/'inputs',contract.fixtures())
    native.audit(out/'supplement-inputs',supplement.model()[0])
    symbolsets = []
    for b in ('native','rust'):
        for name in ('corpus','supplement'):
            expected,final = (contract.expected(),contract.final_files()) if name=='corpus' else supplement.model()[1:]
            for rep in ('','-repeat'):
                stem=b+'-'+name+rep
                need((out/(stem+'.stdout')).read_bytes()==expected,'ordered frozen output '+stem)
                native.audit(out/(stem+'-cases'),final)
                if name=='corpus':counts((out/(stem+'.stderr')).read_bytes(),b=='rust')
            need((out/(b+'-'+name+'.stderr')).read_bytes()==(out/(b+'-'+name+'-repeat.stderr')).read_bytes(),'exact stderr repeat')
        need((out/(b+'-protocol.stdout')).read_bytes()==b'native protocol finite controls pass\n','protocol controls')
        need((out/(b+'-layout.stdout')).read_bytes()==(QUALIFIED/'layout.stdout').read_bytes(),'qualified layout')
        need((out/(b+'-c11.stdout')).read_bytes()==b'', 'C11 runtime')
        symbols=sorted({line.split(' T ',1)[1] for line in (out/('symbols-'+b+'.stdout')).read_text().splitlines() if ' T Star::File::' in line})
        need(len(symbols)==34,'34 compiled File symbols');symbolsets.append(symbols)
        for needle in ['Star::File::remove(Star::String const&)','Star::File::removeDirectoryRecursive(Star::String const&)']:
            hits=[s for s in (out/('symbols-'+b+'-removal.stdout')).read_text().splitlines() if needle in s]
            need(len(hits)==1 and ' T ' in hits[0],'sole strong instrumented symbol')
        need(removal.tree(out/b)==load(out/b/'tree-before.json')==load(out/b/'tree-after.json'),'unchanged ordinary removal tree')
        for i in range(6):
            for rep in range(2):removal.check_output((out/f'{b}-removal-{rep}-{i}.stdout').read_bytes(),out/b,i)
            need((out/f'{b}-removal-0-{i}.stdout').read_bytes()==(out/f'{b}-removal-1-{i}.stdout').read_bytes(),'exact instrumented repeat')
    need(symbolsets[0]==symbolsets[1],'same compiled boundary')
    try:counts((out/'native-corpus.stderr').read_bytes(),True)
    except ValueError:pass
    else:raise ValueError('native bypass accepted as positive Rust evidence')

def object_entries(raw):
    # Apple maps may contain non-UTF-8 symbol spellings outside this section.
    # Decode only object paths; never normalize or replace bytes in a path.
    need(raw.count(b'# Object files:\n') == 1 and b'# Sections:' in raw,
         'link map object section')
    table=raw.split(b'# Object files:\n',1)[1].split(b'# Sections:',1)[0]
    return [s.split(b'] ',1)[1].decode('utf-8') for s in table.splitlines() if b'] ' in s]

def link_membership(out,plan_items,archive):
    for name,args in plan_items:
        if not name.startswith('link-'):continue
        target=Path(args[args.index('-o')+1])
        entries=object_entries(Path(str(target)+'.map').read_bytes())
        expected=[s for s in args if s.endswith('.o')]
        actual=[s for s in entries if s.startswith(str(out)+'/') and s.endswith('.o')]
        need(actual==expected,'actual ordered link objects '+name)
        need(not any('/file-lab/' in s or str(native.CM) in s for s in entries),'no historical objects')
        aggregates=[s for s in entries if 'libstar_engine_ffi.a' in s]
        if str(archive) in args:
            # Native supplement/removal do not reference counters; dead stripping
            # may omit the aggregate entirely. Rust and bypass corpus must use it.
            need(all(s.startswith(str(archive)+'(') for s in aggregates),'sole aggregate members')
            if '-rust-' in name or name=='link-native-corpus':need(aggregates,'actual aggregate member required')
        else:need(not aggregates,'unexpected Rust aggregate')

def validate(q,out,archive):
    need(out.is_relative_to(BASE) and out!=BASE,'owned output')
    old=authenticate();rs,libs=recipes();archive=select_archive(archive)
    need(q['status']==STATUS and q['cases']==139 and q['modes']==34 and q['objects_per_backend']==113 and q['removal_cases_per_backend']==12,'scope')
    need(q['limitations']==LIMITS and q['protocol_omission']==OMITTED,'proof boundary')
    need(q['archive']==str(archive) and q['archive_sha256']==sha(archive),'separately qualified archive')
    for name,data in generated(old).items():need((out/name).read_text()==data,'generated source '+name)
    need(load(out/'recipes.json')==rs and load(out/'libraries.json')==libs,'current recipes')
    initial=hashes(input_paths(out,rs,libs,archive,old))
    need(load(out/'initial.json')==initial,'complete initial snapshot')
    paths=input_paths(out,rs,libs,archive,old)|dependencies(out,rs)
    required=hashes(paths)
    for p in paths:
        if p.is_relative_to(ROOT/'source'):
            snap=out/'snapshots'/p.relative_to(ROOT)
            need(sha(snap)==required[str(p)],'source snapshot identity');required[str(snap)]=sha(snap)
    need(q['bindings']==required==load(out/'before.json')==load(out/'after.json'),'complete before/after closure')
    artifacts=required_artifacts(out,rs,libs,archive,old)
    need(set(q['artifacts'])==set(map(str,artifacts)),'required artifact membership')
    artifact_bytes = hashes(artifacts)
    need(q['artifacts']==artifact_bytes,'artifact bytes')
    pre=base_artifacts(out,rs,libs,archive,old)
    need(load(out/'preexecute.json')==hashes(pre),'complete preexecute membership/bytes')
    expected=plan(out,rs,libs,archive)
    need([(c['name'],c['command']) for c in q['commands']]==expected,'complete ordered argv')
    need(q['commands']==load(out/'commands.json'),'commands mirror')
    stdin={'kind':'pipe','size':0,'sha256':hashlib.sha256(b'').hexdigest()}
    # Every planned executable is already in the independently reconstructed
    # source/artifact closure. Use those current bytes instead of rehashing the
    # same compiler hundreds of times; acquisition still hashes each invocation.
    current_bytes = {**required, **artifact_bytes}
    for c in q['commands']:
        n=c['name'];need(c==load(out/(n+'.command.json')),'command mirror '+n)
        need(type(c['returncode']) is int and c['returncode']==0,'normal exit')
        need(c['stdin']==stdin,'owned empty stdin')
        exe=Path(c['command'][0]).resolve()
        need(str(exe) in current_bytes and c['executable']==str(exe) and c['before']==c['after']==current_bytes[str(exe)],'command executable')
        for stream in ('stdout','stderr'):need(c[stream]==sha(out/(n+'.'+stream)),'stream bytes')
    link_membership(out,expected,archive);observations(out,rs)
    return q

def controls(q,out,archive,dest):
    need(dest.is_relative_to(BASE) and not dest.exists(),'fresh owned controls')
    dest.mkdir(parents=True);results=[]
    mutations=[('omit-artifact',lambda x:x['artifacts'].pop(str(out/'rust/0.o'))),
      ('omit-source',lambda x:x['bindings'].pop(str(ROOT/'source/core/StarFileHost.hpp'))),
      ('before-after',lambda x:x['bindings'].update({str(ROOT/'source/core/StarFile.hpp'):'0'*64})),
      ('omit-command',lambda x:x['commands'].pop()),
      ('argv',lambda x:x['commands'][0]['command'].append('-DWRONG')),
      ('exit',lambda x:x['commands'][0].update(returncode=1)),
      ('stdin',lambda x:x['commands'][-1].update(stdin={'kind':'inherit'})),
      ('archive',lambda x:x.update(archive_sha256='0'*64)),
      ('scope',lambda x:x.update(cases=138)),
      ('foreign-unwind',lambda x:x.update(protocol_omission=''))]
    for name,fn in mutations:
        bad=copy.deepcopy(q);fn(bad);dump(dest/(name+'.json'),bad)
        try:validate(bad,out,archive)
        except (ValueError,KeyError) as e:results.append({'case':name,'rejected':str(e)})
        else:raise ValueError('escaped corruption '+name)
    dump(dest/'results.json',results)
    return results

def acquire(out,archive):
    need(out.is_relative_to(BASE) and out!=BASE and not out.exists(),'fresh owned output')
    old=authenticate();need(archive.is_file(),'parent archive missing; do not build or poll')
    rs,libs=recipes();out.mkdir(parents=True)
    deadline=time.monotonic()+15*60
    for b in ('native','rust'):
        (out/b).mkdir();(out/b/'trees').mkdir()
        for d in removal.DIRS:(out/b/'trees'/d).mkdir()
        for n,data in removal.FILES.items():(out/b/'trees'/n).write_bytes(data)
        dump(out/b/'tree-before.json',removal.tree(out/b))
    for n,data in generated(old).items():(out/n).write_text(data)
    dump(out/'recipes.json',rs);dump(out/'libraries.json',libs)
    (out/'expected.tsv').write_bytes(contract.expected());(out/'supplement.expected').write_bytes(supplement.model()[1])
    for name,fixtures in [('inputs',contract.fixtures()),('supplement-inputs',supplement.model()[0])]:
        (out/name).mkdir()
        for n,data in fixtures.items():(out/name/n).write_bytes(data)
    initial=hashes(input_paths(out,rs,libs,archive,old));dump(out/'initial.json',initial)
    p=plan(out,rs,libs,archive);count=len(jobs(out,rs));commands=[]
    def command(item):
        need(time.monotonic()<deadline,'15 minute acquisition budget exhausted')
        name,args=item
        return native.cmd(args,name,out,b'')
    with ThreadPoolExecutor(max_workers=6) as pool:commands.extend(pool.map(command,p[:count]))
    need(initial==hashes(input_paths(out,rs,libs,archive,old)),'scan source drift')
    paths=input_paths(out,rs,libs,archive,old)|dependencies(out,rs)
    before=hashes(paths)
    for path in paths:
        if path.is_relative_to(ROOT/'source'):
            dest=out/'snapshots'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
            need(sha(dest)==before[str(path)],'snapshot identity');before[str(dest)]=sha(dest)
    dump(out/'before.json',before)
    with ThreadPoolExecutor(max_workers=6) as pool:commands.extend(pool.map(command,p[count:2*count]))
    runtime=len(executions(out))
    for item in p[2*count:-runtime]:commands.append(command(item))
    dump(out/'preexecute.json',hashes(base_artifacts(out,rs,libs,archive,old)))
    need(before==hashes(map(Path,before)),'before execution drift')
    for item in p[-runtime:]:
        name,args=item
        if '-corpus' in name or '-supplement' in name:
            fixtures=supplement.model()[0] if '-supplement' in name else contract.fixtures()
            leaf=Path(args[1]);leaf.mkdir()
            if '-supplement' in name:(leaf/'backup.b1').mkdir()
            for n,data in fixtures.items():(leaf/n).write_bytes(data)
            native.audit(leaf,fixtures)
        for b in ('native','rust'):removal.tree(out/b)
        commands.append(command(item))
        for b in ('native','rust'):removal.tree(out/b)
    for b in ('native','rust'):dump(out/b/'tree-after.json',removal.tree(out/b))
    observations(out,rs);link_membership(out,p,archive)
    after=hashes(map(Path,before));need(before==after,'after execution drift')
    dump(out/'after.json',after);dump(out/'commands.json',commands)
    q=dict(status=STATUS,cases=139,modes=34,objects_per_backend=113,removal_cases_per_backend=12,
      archive=str(archive),archive_sha256=sha(archive),protocol_omission=OMITTED,limitations=LIMITS,
      bindings=before,commands=commands,artifacts=hashes(required_artifacts(out,rs,libs,archive,old)))
    validate(q,out,archive)
    dump(out/'report.json',q)
    print(STATUS,sha(out/'report.json'),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase',choices=('prepare','run','verify','controls'))
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--archive',type=Path,default=ARCHIVE)
    ap.add_argument('--controls-output',type=Path)
    a=ap.parse_args();out=a.output.resolve();archive=select_archive(a.archive)
    if a.phase=='prepare':
        need(out.is_relative_to(BASE) and out!=BASE and not out.exists(),'fresh owned preparation')
        old=authenticate();rs,libs=recipes();out.mkdir(parents=True)
        for n,data in generated(old).items():(out/n).write_text(data)
        dump(out/'plan.json',plan(out,rs,libs,archive))
        dump(out/'prepared.json',dict(status='PREPARED_NOT_EXECUTED',archive=str(archive),archive_exists=archive.is_file(),objects_per_backend=113,jobs=len(jobs(out,rs)),limitations=LIMITS))
        print('PREPARED_NOT_EXECUTED')
    elif a.phase=='run':acquire(out,archive)
    else:
        q=load(out/'report.json');validate(q,out,archive)
        if a.phase=='controls':
            need(a.controls_output is not None,'--controls-output required')
            controls(q,out,archive,a.controls_output.resolve())
        print(STATUS)
