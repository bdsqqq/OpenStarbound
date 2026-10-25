#!/usr/bin/env python3
"""Finite defined-storage native BTree probe; never rebuilds shared objects."""
import argparse, hashlib, json, os, shlex, shutil, subprocess
from pathlib import Path
import build_provenance as p
import btree_padding
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/behavior/ram-btree-domain-r1'
def digest(x):
    h=hashlib.sha256()
    with Path(x).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def ranges(a,b):
    result=[]; start=None
    for i in range(max(len(a),len(b))+1):
        different=i<max(len(a),len(b)) and a[i:i+1]!=b[i:i+1]
        if different and start is None:start=i
        if not different and start is not None:result.append([start,i]);start=None
    return result
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--cmake',type=Path,default=ROOT/'build/behavior/reference/cmake'); ap.add_argument('--output',type=Path,default=OUT); a=ap.parse_args(); cm=a.cmake.resolve()
    global_output=a.output.absolute()
    if global_output != OUT and not global_output.is_relative_to(OUT):raise RuntimeError('output outside owned root')
    return execute(cm,global_output)
def execute(cm,OUT):
    if any(x.is_symlink() for x in [OUT,*OUT.parents]):raise RuntimeError('symlink output ancestry')
    if OUT.exists():raise RuntimeError('refuse existing output')
    if shutil.disk_usage(OUT.parent).free<1024**3:raise RuntimeError('less than 1GiB free')
    OUT.mkdir()
    commands=[]
    def run(cmd,name):
        cmd=list(map(str,cmd)); executable=str(Path(cmd[0]).resolve()); identity=digest(executable)
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90)
        (OUT/(name+'.stdout')).write_text(r.stdout);(OUT/(name+'.stderr')).write_text(r.stderr)
        assert digest(executable)==identity, 'executed binary drift'
        commands.append({'name':name,'command':cmd,'executable':executable,'executable_sha256':identity,
                         'returncode':r.returncode,'stdout_sha256':digest(OUT/(name+'.stdout')),
                         'stderr_sha256':digest(OUT/(name+'.stderr'))})
        (OUT/'commands.json').write_text(json.dumps(commands,indent=2))
        if r.returncode:raise RuntimeError(name+' failed: '+r.stderr[-1000:])
        return r
    db=cm/'compile_commands.json'; ninja=cm/'build.ninja'; entries=json.loads(db.read_text())
    entry=next(e for e in entries if e['file'].endswith('/StarBTreeDatabase.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
    for f in recipe[1:]:
        if skip:skip=False;continue
        if f=='-o':skip=True
        elif f not in ['-c',entry['file']]:flags.append(f)
    if any(f.startswith('-DSTAR_USE_RUST_') for f in flags):raise RuntimeError('reference must be Native OFF')
    flags+=['-I'+str(ROOT/'source/base')]
    lines=ninja.read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
    objects=[cm/t for t in shlex.split(lines[i].split(': ',1)[1])[1:] if t.endswith('.o') and t.startswith(('core/','extern/'))]
    if not objects or any(not x.is_file() for x in objects):raise RuntimeError('missing native objects')
    libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')))
    libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
    compiler=Path(recipe[0]).absolute(); cpp=HERE/'ram_btree_probe.cpp'; archive=OUT/'native-core-extern.a'; exe=OUT/'probe'
    # The current game seal may predate the parent's authorized fixture edits.
    # A failed current-source closure is retained and blocks acceptance.
    proof=cm.parent/'bin/starbound'
    closure_before=None
    try:closure_before=p.verify(proof)
    except Exception as error:(OUT/'closure-before-error.txt').write_text(str(error))
    dep=run([str(compiler),*flags,'-M',str(cpp)],'dependencies').stdout
    headers=[Path(x) for x in shlex.split(dep.replace('\\\n',' '))[1:] if Path(x).is_file()]
    tracked=list(dict.fromkeys(x.resolve() for x in [Path(__file__),cpp,HERE/'btree_padding.py',ROOT/'source/base/StarBTreeLab.hpp',db,ninja,compiler,*objects,*(Path(x) for x in libs if Path(x).is_file()),*headers,*cm.rglob('*.h'),*cm.rglob('*.hpp')]))
    before={str(x):digest(x) for x in tracked};(OUT/'before.json').write_text(json.dumps(before,indent=2))
    run(['/usr/bin/ar','rcs',str(archive),*map(str,objects)],'archive')
    run([str(compiler),*flags,str(cpp),str(archive),*libs,'-Wl,-dead_strip','-o',str(exe)],'compile')
    artifacts={str(x):digest(x) for x in [exe,archive]}
    results=[]
    for name,extra in [('zero',[]),('zero-repeat',[]),('poison',['poison']),('poison-repeat',['poison'])]:results.append(json.loads(run([str(exe),*extra],name).stdout))
    assert results[0]==results[1] and results[2]==results[3]
    differences={}
    for kind in ['sha','vlq','bytes']:
        expected=['616c706861006f6e65','626574610074776f','626574610074776f'] if kind=='sha' else [bytes((i+s)&255 for i in range(n)).hex() for s,n in enumerate([127,128,700])]
        pages=[]
        for j,r in enumerate(results):
            assert r['guards']==7 and r[kind]['found']==expected
            b=bytes.fromhex(r[kind]['pagesHex']);pages.append(b)
            assert len(b)%512==0 and b[:8]==b'BTreeDB5' and int.from_bytes(b[8:12],'big')==512 and int.from_bytes(b[28:32],'big')==32
            assert b[67:512]==bytes([0 if j<2 else 165])*445
        for b in pages[:2]:btree_padding.validate_pages(b)
        # Use the actual game-receipt predicate on normally exiting poison runs.
        # Matching logical values alone must not establish page equivalence.
        for b in pages[2:]:
            try:btree_padding.validate_pages(b)
            except ValueError:pass
            else:raise AssertionError('normally exiting poison escaped padding predicate')
        differences[kind]=ranges(pages[0],pages[2])
    after={str(x):digest(x) for x in tracked};(OUT/'after.json').write_text(json.dumps(after,indent=2));assert before==after
    assert all(digest(Path(x))==h for x,h in artifacts.items())
    closure_after=None
    try:closure_after=p.verify(proof)
    except Exception as error:(OUT/'closure-after-error.txt').write_text(str(error))
    report={'status':'PASS' if closure_before and closure_after else 'DRAFT_CLOSURE_GAP','pid':os.getpid(),'native_closure_before':bool(closure_before),'native_closure_after':bool(closure_after),'cases':3,'runs':4,'sequences':12,'guard_assertions_per_run':7,'logical_crossfill_equal':True,'physical_repeat_equal':True,'normal_poison_zero_padding_rejected':True,'differing_ranges':differences,'artifacts':artifacts,'source_sha256':{str(x):digest(x) for x in [cpp,Path(__file__),ROOT/'source/base/StarBTreeLab.hpp']},'limits':['finite initialized storage only','no UB, OOM, sanitizer, platform, Rust or game qualification']}
    report.update(bindings=before, commands=commands, native_binary=str(proof),
                  native_binary_sha256=digest(proof),
                  predicate_sha256=digest(HERE/'btree_padding.py'))
    (OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('bindings','commands')}))
if __name__=='__main__':main()
