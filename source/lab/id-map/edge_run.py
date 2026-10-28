#!/usr/bin/env python3
"""Fresh, bounded standalone native edge acquisition. No Cargo or game generation."""
import datetime as dt,importlib.util,json,shlex,signal,sys,time
from pathlib import Path
import run as native
import edge_model,edge_verify
from map_bytes import sdk_paths
ROOT=native.ROOT;HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/id-map-edges-r1';sha=edge_verify.sha;need=edge_verify.need;dump=native.dump
DEADLINE=dt.datetime(2026,10,28,15,18,tzinfo=dt.timezone.utc).timestamp()
def cap():
    need(time.time()<DEADLINE,'original edge unit deadline')
    need(native.cleanup.allocated_bytes(OUT)<64*1024**2,'64MiB edge cap')
def main():
    need(not OUT.exists(),'fresh edge root only');OUT.mkdir();(OUT/'home').mkdir();(OUT/'tmp').mkdir()
    native.OUT=OUT;native.DEADLINE=DEADLINE;native.ADMISSION_NAME='admission.json';native.COMMANDS=[];native.cap=cap
    header=ROOT/'source/core/StarIdMap.hpp';need(sha(header)=='ff8b48f3931efedf8e5b19bc074b84a04f04329aedabbfd3eeb7b7b6ffeaad62','production header unchanged')
    raw=header.read_text();old='ds.read(map.m_min);';need(raw.count(old)==1,'exact partial-read mutant')
    (OUT/'StarIdMap.edge-mutant.hpp').write_text(raw.replace(old,'map.m_min = ds.read<typename IdMapWrapper<BaseMap>::IdType>();'))
    (OUT/'expected.tsv').write_text(edge_model.expected());r=native.recipe();dump(OUT/'recipe.json',r)
    cm=Path(r['cm']);c=r['compiler'];flags=[*r['flags'],'-I'+str(HERE),'-I'+str(OUT)];need('-DSTAR_LITTLE_ENDIAN'in flags,'admitted native byte order')
    selector=ROOT/'build/weighted-pool-game-admission-r1/complete-r1/plan.json';need(sha(selector)==native.PIN,'historical tool path selector');oldplan=json.loads(selector.read_bytes());sdk=r['flags'][r['flags'].index('-isysroot')+1];need(sdk==oldplan['sdk'],'selected SDK');usr=Path(c).resolve().parent.parent
    roots=[ROOT/'source/core',ROOT/'source/extern',HERE,OUT,Path(sdk),usr/'include',usr/'lib/clang']
    for i,x in enumerate(flags):
        if x in ('-isystem','-isysroot'):roots.append(Path(flags[i+1]))
        elif x.startswith('-I'):roots.append(Path(x[2:]))
    w=native.closure(roots);tools=[Path(c),usr/'bin/clang',Path(oldplan['tools']['CMAKE_LINKER']),usr/'lib/libLTO.dylib',usr/'lib/libtapi.dylib',Path('/bin/ps'),Path(sys.executable)]
    for p in tools:
        resolved=str(p.resolve(strict=True));w['files'][resolved]=sha(p);w['aliases'][str(p)]=resolved
    for p in [*map(Path,r['objects']),*[Path(x)for x in r['libraries']if Path(x).is_absolute()and Path(x).is_file()],cm/'CMakeCache.txt',cm/'compile_commands.json',cm/'build.ninja',selector,Path(__file__),Path(native.__file__),Path(edge_model.__file__),Path(edge_verify.__file__),Path(sys.modules['game_syntax'].__file__),Path(native.sdk_witness.__file__),ROOT/'scripts/cleanup-migration-artifacts.py']:w['files'][str(p.resolve())]=sha(p)
    native.WITNESS=w;sdk_before=native.sdk_witness.capture(sdk,sdk);dump(OUT/'sdk-before.json',sdk_before)
    dump(OUT/'admission.json',dict(witness=w,recipeSha256=sha(OUT/'recipe.json'),sdkSha256=sha(OUT/'sdk-before.json'),tools=list(map(str,tools)),deadline=DEADLINE,budget=native.budget(),scope='fresh defined native little-endian edge contract; old plan selects tool paths ONLY, no expired source/build admission renewal'))
    controls={};bad=dict(files=dict(w['files']));del bad['files'][str(header.resolve())]
    try:native.subset([header],bad)
    except AssertionError:controls['missing_header_before_compile']=True
    else:raise ValueError('missing header accepted')
    native.command('compiler-version',[c,'--version'])
    link=[c,*flags,*r['objects'],str(OUT/'native.o'),*r['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(OUT/'native.map'),'-Wl,-t,-trace_implicit_libraries','-o',str(OUT/'native')]
    native.command('link-expand',[c,'-###',*[str(x).replace(str(OUT/'native.o'),str(HERE/'edges.cpp'))for x in link[1:]]])
    need(str(Path(oldplan['tools']['CMAKE_LINKER']))in(OUT/'link-expand.stderr').read_text(),'actual selected ld')
    native.command('compile',[c,*flags,'-MD','-MF',OUT/'native.d','-c',HERE/'edges.cpp','-o',OUT/'native.o'])
    native.subset(shlex.split((OUT/'native.d').read_text().replace('\\\n',' ').split(':',1)[1]),w)
    native.command('link',link);native.command('native',[OUT/'native']);native.command('repeat',[OUT/'native'])
    native.command('mutant-compile',[c,*flags,'-DIDMAP_EDGE_MUTANT_HEADER','-c',HERE/'edges.cpp','-o',OUT/'mutant.o'])
    ml=[str(x).replace(str(OUT/'native.o'),str(OUT/'mutant.o')).replace(str(OUT/'native.map'),str(OUT/'mutant.map'))for x in link];ml[-1]=str(OUT/'mutant');native.command('mutant-link',ml);native.command('mutant',[OUT/'mutant'],expected=1)
    outputs={n:(OUT/(n+'.stdout')).read_text()for n in ['native','repeat','mutant']};result=edge_verify.semantics(outputs)
    need('partial-metadata-little-endian'in(OUT/'mutant.stderr').read_text(),'known partial-scalar mutant rejection')
    for label,data in [('transactional_read_mutant',outputs['mutant']),('wrong_literal',outputs['native'].replace('cursor=10','cursor=11',1)),('lost_property',outputs['native'].replace('PASS\tordered/outer-copy-identity-and-conservation\n',''))]:
        try:edge_model.verify(data)
        except ValueError:controls[label]=True
        else:raise ValueError('falsifier accepted '+label)
    native.unchanged(w);sdk_after=native.sdk_witness.capture(sdk,sdk);need(sdk_after==sdk_before,'SDK before/after identity');dump(OUT/'sdk-after.json',sdk_after)
    dump(OUT/'sdk-consumed.json',native.sdk_witness.reconcile_consumed(sdk_before,sdk_paths((OUT/'native.map').read_bytes()),requested_root=sdk,expected_canonical_root=sdk))
    result.update(status='FINITE_NATIVE_IDMAP_EDGES_NOT_RUST_OR_GAME',commands=native.COMMANDS,controls=controls,admissionSha256=sha(OUT/'admission.json'),limits=['finite uint32/little-endian and printable uint8 key fixture; not all malformed streams or integer domains','current all28OFF113referenceobjects consumed, not recompiled/newgame-source proof','no Rust/Cargo/ABI/production selector/gameplay/full39 completion'])
    result['products']={str(p):sha(p)for p in OUT.rglob('*')if p.is_file()and p.name!='report.json'};dump(OUT/'report.json',result);cap();print('REPORT',sha(OUT/'report.json'))
if __name__=='__main__':main()
