#!/usr/bin/env python3
"""One bounded native acquisition; 113 current reference objects, no Cargo/build system.

All files selected before compile/link; old full-build plan selects immutable
SDK/tool bytes only, never renews its changed global/catalog closure.
"""
import datetime as dt, hashlib, json, os, re, shlex, signal, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'build/weighted-pool-native-r1/attempt2'
sys.path.insert(0,str(HERE));import model, verify
sys.path.insert(0,str(HERE.parent/'ttl-production'));from game_syntax import closure,unchanged,subset
sys.path.insert(0,str(HERE.parent/'path-embed-replay'));import sdk_witness
DEADLINE=dt.datetime(2026,10,27,22,31,30,tzinfo=dt.timezone.utc).timestamp()
PIN='55a6aa0ee206e4435d57be0cb2f612dc70f4e06ab9af16ee2ed3476280c132ab'
sha=verify.sha

def dump(p,v):
    with Path(p).open('x') as f:json.dump(v,f,sort_keys=True,indent=2);f.write('\n')
def need(b,msg):
    if not b:raise AssertionError(msg)
def cap():
    need(time.time()<DEADLINE,'hard deadline')
    need(sum(p.stat().st_size for p in OUT.parent.rglob('*') if p.is_file())<64*1024*1024,'64MiB cap')
COMMANDS=[]
def command(name,args,stdin=b'',expected=0,timeout=90,expected_timeout=False):
    cap();args=list(map(str,args));prefix=OUT/name
    env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(OUT/'home'),TMPDIR=str(OUT/'tmp'),LANG='C',LC_ALL='C')
    (OUT/(name+'.stdin')).write_bytes(stdin)
    plan=dict(argv=args,cwd=str(ROOT),env=env,stdin_sha256=hashlib.sha256(stdin).hexdigest(),timeout=timeout,expected_returncode=expected,expected_timeout=expected_timeout,admission_sha256=sha(OUT/'admission.json'))
    dump(str(prefix)+'.plan.json',plan)
    started=time.time_ns()
    p=subprocess.Popen(args,cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    # ps is selected and pinned in admission; its output is an observed OS start,
    # not a fabricated Python launch timestamp. Preserve both.
    osstart=subprocess.run(['/bin/ps','-p',str(p.pid),'-o','lstart=,pid=,pgid='],capture_output=True,timeout=5).stdout.decode().strip()
    dump(str(prefix)+'.started.json',dict(pid=p.pid,pgid=os.getpgid(p.pid),started_ns=started,os_start=osstart))
    timed=False
    try:o,e=p.communicate(stdin,timeout=min(timeout,DEADLINE-time.time()))
    except subprocess.TimeoutExpired:
        timed=True;os.killpg(p.pid,signal.SIGKILL);o,e=p.communicate(timeout=5)
    try:os.killpg(p.pid,0);gone=False
    except ProcessLookupError:gone=True
    (OUT/(name+'.stdout')).write_bytes(o);(OUT/(name+'.stderr')).write_bytes(e)
    receipt=dict(pid=p.pid,pgid=p.pid,started_ns=started,ended_ns=time.time_ns(),os_start=osstart,returncode=p.returncode,timed_out=timed,reaped=True,group_gone=gone,expected_returncode=expected,expected_timeout=expected_timeout,stdout_sha256=sha(OUT/(name+'.stdout')),stderr_sha256=sha(OUT/(name+'.stderr')),plan_sha256=sha(str(prefix)+'.plan.json'))
    dump(str(prefix)+'.receipt.json',receipt);COMMANDS.append(name)
    print(name,p.pid,p.returncode,'timeout',timed,flush=True)
    need(gone and p.returncode==expected and timed==expected_timeout,'command expectation: '+name)
    cap();return o

def recipe():
    cm=ROOT/'build/behavior/ttl-cache-combined-r2/reference/cmake'
    db=json.loads((cm/'compile_commands.json').read_text());lines=(cm/'build.ninja').read_text().splitlines()
    row=next(r for r in db if r['file']==str(ROOT/'source/core/StarJsonBuilder.cpp'))
    args=shlex.split(row['command']);flags=[];skip=False
    for x in args[1:]:
        if skip:skip=False;continue
        if x=='-o':skip=True
        elif x not in ('-c',row['file']):flags.append(x)
    pos=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
    objects=[str((cm/x).resolve()) for x in shlex.split(lines[pos].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/'))]
    libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[pos+1:pos+18] if x.startswith('  LINK_LIBRARIES = ')))
    libs=[str((cm/x).resolve()) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
    selectors=re.findall(r'^(STAR_USE_RUST[^:]*):BOOL=(.*)$',(cm/'CMakeCache.txt').read_text(),re.M)
    need(len(db)==472 and len(selectors)==27 and all(v=='OFF' for _,v in selectors),'current all27OFF recipe')
    need(len(objects)==len(set(objects))==113,'current113 object closure')
    need('-O3' in flags and '-ffast-math' in flags and not any('-DSTAR_USE_RUST' in x['command'] for x in db),'unchanged optimized native flags')
    return dict(cm=str(cm),compiler=args[0],flags=flags,objects=objects,libraries=libs,selectors=selectors)

def main():
    need(not OUT.exists(),'fresh one-shot output only');OUT.mkdir();(OUT/'home').mkdir();(OUT/'tmp').mkdir()
    header=(ROOT/'source/core/StarWeightedPool.hpp').read_text()
    (HERE/'StarWeightedPool.original.hpp').write_text(header.replace('WeightedPool','ReferenceWeightedPool'))
    proxy=header
    transforms=[('WeightedPool','ProxyWeightedPool'),('RandomSource','ProxyRandomSource'),('Random::','ProxyRandom::'),('staticRandomDouble','proxyStaticRandomDouble')]
    for a,b in transforms:proxy=proxy.replace(a,b)
    (HERE/'StarWeightedPool.proxy.hpp').write_text(proxy)
    (OUT/'StarWeightedPool.raw.hpp').write_text(header)
    (OUT/'StarWeightedPool.mutant.hpp').write_text(proxy.replace('target <= accumulatedWeight','target < accumulatedWeight'))
    (OUT/'mutant.cpp').write_text((HERE/'native.cpp').read_text().replace('"StarWeightedPool.proxy.hpp"','"StarWeightedPool.mutant.hpp"'))
    (OUT/'lazy-negative.cpp').write_text('#include "StarSet.hpp"\n#include "StarWeightedPool.hpp"\nstruct NoDefault {NoDefault()=delete;NoDefault(NoDefault const&)=default;};\nint main(){Star::WeightedPool<NoDefault> p;p.select(uint64_t(0));}\n')
    corpus,expected=model.corpus();(OUT/'corpus.tsv').write_text(corpus);(OUT/'expected.tsv').write_text(expected)
    r=recipe();dump(OUT/'recipe.json',r);cm=Path(r['cm']);c=r['compiler'];flags=[*r['flags'],'-I'+str(HERE),'-I'+str(OUT)]
    oldpath=ROOT/'build/ttl-game-build-r3/plan.json';need(sha(oldpath)==PIN,'immutable previous plan selector pin')
    old=json.loads(oldpath.read_text());sdk=r['flags'][r['flags'].index('-isysroot')+1];need(sdk==old['sdk'],'actual SDK binding')
    usr=Path(c).resolve().parent.parent
    roots=[ROOT/'source/core',ROOT/'source/extern',HERE,Path(sdk),usr/'include',usr/'lib/clang']
    for i,x in enumerate(flags):
        if x in ('-isystem','-isysroot'):roots.append(Path(flags[i+1]))
        elif x.startswith('-I'):roots.append(Path(x[2:]))
    witness=closure(roots)
    # Selected actual compiler/linker/runtime support only. No ar/ranlib invoked
    # or retroactively admitted: directly link the frozen object providers.
    tools=[Path(c),usr/'bin/clang',Path(old['tools']['CMAKE_LINKER']),usr/'lib/libLTO.dylib',usr/'lib/libtapi.dylib',Path('/bin/ps'),Path(sys.executable)]
    for p in tools:
        resolved=str(p.resolve(strict=True));witness['files'][resolved]=sha(p);witness['aliases'][str(p)]=resolved
    files=[*map(Path,r['objects']),*[Path(x) for x in r['libraries'] if Path(x).is_absolute() and Path(x).is_file()],cm/'build.ninja',cm/'CMakeCache.txt',cm/'compile_commands.json',oldpath,ROOT/'source/lab/migration/catalog.json',Path(__file__),Path(verify.__file__),Path(model.__file__),Path(sys.modules['game_syntax'].__file__),Path(sdk_witness.__file__),OUT/'mutant.cpp',OUT/'lazy-negative.cpp',OUT/'StarWeightedPool.mutant.hpp']
    for p in files:witness['files'][str(p.resolve())]=sha(p)
    sdk_before=sdk_witness.capture(sdk,sdk);dump(OUT/'sdk-before.json',sdk_before)
    dump(OUT/'admission.json',dict(witness=witness,tools=[str(x) for x in tools],recipe_sha256=sha(OUT/'recipe.json'),sdk_manifest_sha256=sha(OUT/'sdk-before.json'),old_plan_role='SELECT immutable tool/SDK paths ONLY; not renewal of old global admission',transforms=transforms,domain='finite dyadic literal model; nonfinite/overflow/subnormal diagnostic only under original -O3 -ffast-math',deadline=DEADLINE))
    unchanged(witness)
    controls={}
    bad=dict(files=dict(witness['files']));del bad['files'][str((ROOT/'source/core/StarWeightedPool.hpp').resolve())]
    try:subset([ROOT/'source/core/StarWeightedPool.hpp'],bad)
    except AssertionError:controls['missing_input_rejected_before_compile']=True
    else:raise AssertionError('missing header verifier accepted')
    command('compiler-version',[c,'--version'])
    # Driver expansion is itself preadmitted; inspect actual ld selection BEFORE
    # real compilation/link. All SDK tbd files were frozen before this command.
    link=[c,*flags,*r['objects'],str(OUT/'native.o'),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/'native.map'),'-Wl,-t,-trace_implicit_libraries','-o',str(OUT/'native')]
    command('link-expand',[c,'-###',*[str(x).replace(str(OUT/'native.o'),str(HERE/'native.cpp')) for x in link[1:]]])
    expanded=(OUT/'link-expand.stderr').read_text();need(str(Path(old['tools']['CMAKE_LINKER'])) in expanded,'selected actual ld must match preadmission')
    command('compile',[c,*flags,'-MD','-MF',OUT/'native.d','-c',HERE/'native.cpp','-o',OUT/'native.o'])
    deps=shlex.split((OUT/'native.d').read_text().replace('\\\n',' ').split(':',1)[1]);subset(deps,witness)
    command('link',link)
    command('corpus',[OUT/'native','corpus'],corpus.encode());command('corpus-repeat',[OUT/'native','corpus'],corpus.encode())
    command('properties',[OUT/'native','properties']);command('diagnostics',[OUT/'native','diagnostics'])
    command('nonprogress',[OUT/'native','hang'],expected=-signal.SIGKILL,timeout=.25,expected_timeout=True)
    command('lazy-negative',[c,*flags,'-fsyntax-only',OUT/'lazy-negative.cpp'],expected=1)
    need('deleted' in (OUT/'lazy-negative.stderr').read_text(),'lazy failure diagnostic')
    command('mutant-compile',[c,*flags,'-c',OUT/'mutant.cpp','-o',OUT/'mutant.o'])
    mutantlink=[str(x).replace(str(OUT/'native.o'),str(OUT/'mutant.o')).replace(str(OUT/'native.map'),str(OUT/'mutant.map')) for x in link]
    mutantlink[-1]=str(OUT/'mutant');command('mutant-link',mutantlink);command('mutant',[OUT/'mutant','corpus'],corpus.encode())
    outputs={name:(OUT/(name+'.stdout')).read_text() for name in ['corpus','corpus-repeat','properties']}
    result=verify.semantics(outputs)
    for name,altered in [('wrong_literal',dict(outputs,corpus=outputs['corpus'].replace('0\n','1\n',1))),('missing_property',dict(outputs,properties=outputs['properties'].replace('PASS\taccessors-alias\n',''))),('native_semantics_mutant',dict(outputs,corpus=(OUT/'mutant.stdout').read_text()))]:
        try:verify.semantics(altered)
        except AssertionError:controls[name+'_rejected']=True
        else:raise AssertionError('falsifier accepted: '+name)
    unchanged(witness);sdk_after=sdk_witness.capture(sdk,sdk);need(sdk_before==sdk_after,'SDK drift');dump(OUT/'sdk-after.json',sdk_after)
    paths=re.findall(r'^\[\s*\d+\] (.*\.tbd)$',(OUT/'native.map').read_text(),re.M)
    need(paths,'actual linked SDK interfaces');dump(OUT/'sdk-consumed.json',sdk_witness.reconcile_consumed(sdk_before,paths,requested_root=sdk,expected_canonical_root=sdk))
    dump(OUT/'controls.json',controls)
    result.update(status='finite native calibration ONLY',commands=COMMANDS,header_sha256=sha(ROOT/'source/core/StarWeightedPool.hpp'),binary_sha256=sha(OUT/'native'),generated_bytes_before_report=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),inventory_definitions=19,fields=['m_items','m_totalWeight'])
    result['products']={str(p):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name not in ('report.json','acquisition.stdout','acquisition.stderr')}
    dump(OUT/'report.json',result);cap();print('REPORT',sha(OUT/'report.json'),flush=True)
if __name__=='__main__':main()
