#!/usr/bin/env python3
"""One bounded native acquisition; 113 current reference objects, no Cargo/build system.

All files selected before compile/link; old full-build plan selects immutable
SDK/tool bytes only, never renews its changed global/catalog closure.
"""
import datetime as dt, hashlib, json, os, re, shlex, signal, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'build/id-map-native-r1'
sys.path.insert(0,str(HERE));import model, verify
sys.path.insert(0,str(HERE.parent/'ttl-production'));from game_syntax import closure,unchanged,subset
sys.path.insert(0,str(HERE.parent/'path-embed-replay'));import sdk_witness
DEADLINE=dt.datetime(2026,10,28,14,43,0,tzinfo=dt.timezone.utc).timestamp()
PIN='e890b99b615433d3557629bccd2a503c76e44b79d459bfa162d4ed9f7b0d9eb3'
sha=verify.sha
ADMISSION_NAME='admission.json'

def dump(p,v):
    with Path(p).open('x') as f:json.dump(v,f,sort_keys=True,indent=2);f.write('\n')
def need(b,msg):
    if not b:raise AssertionError(msg)
def cap():
    need(time.time()<DEADLINE,'hard deadline')
    need(sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<128*1024*1024,'128MiB cap')
spec=__import__('importlib.util',fromlist=['util']).spec_from_file_location('fixed_cleanup_policy',ROOT/'scripts/cleanup-migration-artifacts.py');cleanup=__import__('importlib.util',fromlist=['util']).module_from_spec(spec);spec.loader.exec_module(cleanup)
def budget():
    archive=cleanup.allocated_bytes(ROOT/'build/migration-evidence-archive');live=cleanup.allocated_bytes(ROOT/'build')-archive
    need(archive<=16*1024**3 and live<=4*1024**3,'fixed4/16GiB caps');return dict(archiveBytes=archive,liveBytes=live)
COMMANDS=[]
def command(name,args,stdin=b'',expected=0,timeout=90,expected_timeout=False):
    cap();before=budget();unchanged(WITNESS);args=list(map(str,args));prefix=OUT/name
    env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(OUT/'home'),TMPDIR=str(OUT/'tmp'),LANG='C',LC_ALL='C')
    (OUT/(name+'.stdin')).write_bytes(stdin)
    plan=dict(argv=args,cwd=str(ROOT),env=env,stdin_sha256=hashlib.sha256(stdin).hexdigest(),timeout=timeout,expected_returncode=expected,expected_timeout=expected_timeout,admission_sha256=sha(OUT/ADMISSION_NAME),budget_before=before,argv_files={arg:sha(arg)for arg in args if Path(arg).is_absolute()and Path(arg).is_file()})
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
    unchanged(WITNESS);cap();return o

def recipe():
    cm=ROOT/'build/behavior/weighted-pool-combined-r1/reference/cmake'
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
    need(len(db)==472 and len(selectors)==28 and all(v=='OFF' for _,v in selectors),'current all28OFF recipe')
    need(len(objects)==len(set(objects))==113,'current113 object closure')
    need('-O3' in flags and '-ffast-math' in flags and not any('-DSTAR_USE_RUST' in x['command'] for x in db),'unchanged optimized native flags')
    return dict(cm=str(cm),compiler=args[0],flags=flags,objects=objects,libraries=libs,selectors=selectors)

def main():
    global WITNESS
    need(not OUT.exists(),'fresh one-shot output only');OUT.mkdir();(OUT/'home').mkdir();(OUT/'tmp').mkdir()
    header=ROOT/'source/core/StarIdMap.hpp';need(sha(header)==sha(HERE/'StarIdMap.original.hpp')=='ff8b48f3931efedf8e5b19bc074b84a04f04329aedabbfd3eeb7b7b6ffeaad62','frozen original byte identity')
    raw=header.read_text();old='(IdType)BaseMap::size() > m_max - m_min';need(raw.count(old)==1,'single exact fullness mutant')
    (OUT/'StarIdMap.mutant.hpp').write_text(raw.replace(old,'(IdType)BaseMap::size() >= m_max - m_min'))
    (OUT/'expected.tsv').write_text(model.expected())
    r=recipe();dump(OUT/'recipe.json',r);cm=Path(r['cm']);c=r['compiler'];flags=[*r['flags'],'-I'+str(HERE),'-I'+str(OUT)]
    oldpath=ROOT/'build/weighted-pool-game-admission-r1/complete-r1/plan.json';need(sha(oldpath)==PIN,'historical tool-path selector pin')
    oldplan=json.loads(oldpath.read_text());sdk=r['flags'][r['flags'].index('-isysroot')+1];need(sdk==oldplan['sdk'],'actual SDK binding');usr=Path(c).resolve().parent.parent
    roots=[ROOT/'source/core',ROOT/'source/extern',HERE,OUT,Path(sdk),usr/'include',usr/'lib/clang']
    for i,x in enumerate(flags):
        if x in ('-isystem','-isysroot'):roots.append(Path(flags[i+1]))
        elif x.startswith('-I'):roots.append(Path(x[2:]))
    # OUT contains command products later: freeze its existing input files only,
    # never claim future generated output membership was preadmitted.
    witness=closure(roots);tools=[Path(c),usr/'bin/clang',Path(oldplan['tools']['CMAKE_LINKER']),usr/'lib/libLTO.dylib',usr/'lib/libtapi.dylib',Path('/bin/ps'),Path(sys.executable)]
    for p in tools:
        resolved=str(p.resolve(strict=True));witness['files'][resolved]=sha(p);witness['aliases'][str(p)]=resolved
    for p in [*map(Path,r['objects']),*[Path(x)for x in r['libraries']if Path(x).is_absolute()and Path(x).is_file()],cm/'build.ninja',cm/'CMakeCache.txt',cm/'compile_commands.json',oldpath,Path(__file__),Path(verify.__file__),Path(model.__file__),Path(sys.modules['game_syntax'].__file__),Path(sdk_witness.__file__),ROOT/'scripts/cleanup-migration-artifacts.py']:
        witness['files'][str(p.resolve())]=sha(p)
    WITNESS=witness;sdk_before=sdk_witness.capture(sdk,sdk);dump(OUT/'sdk-before.json',sdk_before)
    dump(OUT/'admission.json',dict(witness=witness,tools=[str(x)for x in tools],recipe_sha256=sha(OUT/'recipe.json'),sdk_manifest_sha256=sha(OUT/'sdk-before.json'),old_plan_role='historical tool/SDK paths ONLY, not expired global admission or current game-source proof',deadline=DEADLINE,scope='defined uint32 native IdMap/IdHashMap contract, no Rust/Cargo/game',budget=budget()))
    controls={};victim=str(header.resolve());bad=dict(files=dict(witness['files']));del bad['files'][victim]
    try:subset([header],bad)
    except AssertionError:controls['missing_input_rejected_before_compile']=True
    else:raise AssertionError('missing header accepted')
    command('compiler-version',[c,'--version'])
    link=[c,*flags,*r['objects'],str(OUT/'native.o'),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/'native.map'),'-Wl,-t,-trace_implicit_libraries','-o',str(OUT/'native')]
    command('link-expand',[c,'-###',*[str(x).replace(str(OUT/'native.o'),str(HERE/'native.cpp'))for x in link[1:]]])
    need(str(Path(oldplan['tools']['CMAKE_LINKER']))in(OUT/'link-expand.stderr').read_text(),'selected ld expansion')
    command('compile',[c,*flags,'-MD','-MF',OUT/'native.d','-c',HERE/'native.cpp','-o',OUT/'native.o'])
    subset(shlex.split((OUT/'native.d').read_text().replace('\\\n',' ').split(':',1)[1]),witness)
    command('link',link)
    command('native',[OUT/'native']);command('repeat',[OUT/'native'])
    command('lazy-negative',[c,*flags,'-DIDMAP_LAZY_NEGATIVE','-fsyntax-only',HERE/'native.cpp'],expected=1)
    command('hash-move-only-negative',[c,*flags,'-DIDMAP_HASH_MOVE_ONLY_NEGATIVE','-fsyntax-only',HERE/'native.cpp'],expected=1)
    command('mutant-compile',[c,*flags,'-DIDMAP_MUTANT_HEADER','-c',HERE/'native.cpp','-o',OUT/'mutant.o'])
    mutantlink=[str(x).replace(str(OUT/'native.o'),str(OUT/'mutant.o')).replace(str(OUT/'native.map'),str(OUT/'mutant.map'))for x in link];mutantlink[-1]=str(OUT/'mutant');command('mutant-link',mutantlink)
    command('mutant',[OUT/'mutant'],expected=1)
    outputs={n:(OUT/(n+'.stdout')).read_text()for n in ['native','repeat','mutant']};result=verify.semantics(outputs)
    need((OUT/'mutant.stderr').read_text()=='FAIL\t(IdMapException) No id space left in IdMapWrapper\n','exact mutant error')
    need('deleted'in(OUT/'lazy-negative.stderr').read_text(),'lazy constraint diagnostic')
    for label,data in [('wrong_literal',outputs['native'].replace('0,1','9,1',1)),('missing_property',outputs['native'].replace('PASS\tordered/auto-add-copy\n','')),('actual_fullness_mutant',outputs['mutant'])]:
        try:model.verify(data)
        except ValueError:controls[label]=True
        else:raise AssertionError('falsifier accepted '+label)
    unchanged(witness);sdk_after=sdk_witness.capture(sdk,sdk);need(sdk_before==sdk_after,'SDK drift');dump(OUT/'sdk-after.json',sdk_after)
    paths=re.findall(r'^\[\s*\d+\] (.*\.tbd)$',(OUT/'native.map').read_text(),re.M);need(paths,'linked SDK interfaces')
    dump(OUT/'sdk-consumed.json',sdk_witness.reconcile_consumed(sdk_before,paths,requested_root=sdk,expected_canonical_root=sdk))
    result.update(status='FINITE_NATIVE_IDMAP_NOT_RUST_OR_GAME',commands=COMMANDS,controls=controls,admissionSha256=sha(OUT/'admission.json'),admissionFile='admission.json',acceptedCommandCount=11,headerSha256=sha(header),definitions=10,fields=['m_min','m_max','m_nextId'],inheritedAPIs=16,limits=['finite uint32 defined ranges only; signed overflow/full-small-integer nonprogress unexecuted diagnostics','not Rust integration, game behavior or full39 migration','existing all28OFF113referenceobjects consumed as pinned inputs, not recompiled/current full-game proof'])
    result['products']={str(p):sha(p)for p in OUT.rglob('*')if p.is_file()and p.name not in ('report.json','acquisition.stdout','acquisition.stderr')}
    dump(OUT/'report.json',result);cap();print('REPORT',sha(OUT/'report.json'),flush=True)
if __name__=='__main__':main()
