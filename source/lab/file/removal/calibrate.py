#!/usr/bin/env python3
"""INSTRUMENTED non-destructive recursive-removal calibration; no OS deletion proof."""
import argparse, copy, json, re, shlex, stat, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run, audit
PARENT = run.BASE/'parent-final-r2'
BASE = run.ROOT/'build/file-lab/removal-worker-r1'
PIN = 'f1670d04f4620e6c68e5f8348c0d8090bfc7ba5279f733e51bbe9ed0c1cbb681'
OLD = b'''void File::remove(String const& filename) {
  if (::remove(filename.utf8Ptr()) < 0)
    throw IOException::format("remove error: {}", strerror(errno));
}'''
NEW = b'''void File::remove(String const& filename) {
  extern void removalInstrumentedLeaf(String const&);
  removalInstrumentedLeaf(filename);
}'''
CASES = [('chain',0), ('empty',0), ('siblings',0), ('chain',1), ('chain',2), ('chain',4)]
DIRS = ['chain','chain/a','chain/a/b','empty','siblings','siblings/x','siblings/y']
FILES = {'chain/a/b/leaf':b'\x00retained\xff', 'siblings/x/one':b'one', 'siblings/y/two':b'two', 'siblings/plain':b'plain'}

def generated():
    run.originals()
    data=(HERE.parent/'StarFile_unix.original.cpp').read_bytes()
    run.need(data.count(OLD)==1,'exact unique original static remove body')
    result=data.replace(OLD,NEW)
    run.need(result.replace(NEW,OLD)==data,'outside-body identity')
    return result

def model(out):
    chain=[str(out/'trees'/p) for p in ['chain/a/b/leaf','chain/a/b','chain/a','chain']]
    sibling=[str(out/'trees'/p) for p in ['siblings/x/one','siblings/x','siblings/y/two','siblings/y','siblings/plain','siblings']]
    return dict(cases=CASES,chain=chain,siblings=sibling,empty=[str(out/'trees/empty')],dirs=DIRS,files={k:v.hex() for k,v in FILES.items()},scope='INSTRUMENTED ONLY')

def tree(out):
    root=out/'trees'; device=root.stat().st_dev; gotdirs=[]; gotfiles={}
    for p in [root,*root.rglob('*')]:
        s=p.lstat();run.need(s.st_dev==device and not p.is_symlink(),'alias/device')
        if stat.S_ISDIR(s.st_mode):
            if p!=root:gotdirs.append(str(p.relative_to(root)))
        else:
            run.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary exclusive files')
            gotfiles[str(p.relative_to(root))]=p.read_bytes()
    run.need(sorted(gotdirs)==sorted(DIRS) and gotfiles==FILES,'exact unchanged tree')
    return dict(dirs=sorted(gotdirs),files={p:run.sha(root/p) for p in sorted(gotfiles)})

def plan(out):
    rs,libs=run.recipe();idx=next(i for i,r in enumerate(rs) if Path(r['source']).name=='StarFile_unix.cpp');r=rs[idx]
    objects=[out/'platform.o' if i==idx else PARENT/(str(i)+'.o') for i in range(113)]
    p=[]
    for name,source in [('platform',out/'StarFile_unix.instrumented.cpp'),('driver',HERE/'driver.cpp')]:
        p += [('deps-'+name,[r['compiler'],*r['flags'],'-M','-MF',out/(name+'.d'),source])]
    for name,source in [('platform',out/'StarFile_unix.instrumented.cpp'),('driver',HERE/'driver.cpp')]:
        p += [('compile-'+name,[r['compiler'],*r['flags'],'-c',source,'-o',out/(name+'.o')])]
    p += [('link',[r['compiler'],*r['flags'],out/'driver.o',*objects,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/'native.map'),'-o',out/'native']),('symbols',['/usr/bin/nm','-gUC',out/'native'])]
    for repeat in range(2):
        for i,(case,n) in enumerate(CASES):p.append((f'run-{repeat}-{i}',[out/'native',out/'trees'/case,str(n)]))
    return [(n,list(map(str,a))) for n,a in p]

def initial(out):
    paths={p.resolve() for p in HERE.iterdir() if p.is_file()}
    paths.update(map(Path,json.loads((PARENT/'report.json').read_text())['bindings']))
    paths.update([Path(sys.executable).resolve(),Path('/usr/bin/nm'),PARENT/'report.json',out/'expected.json',out/'StarFile_unix.instrumented.cpp'])
    paths.update(PARENT/(str(i)+'.o') for i in range(113))
    return {str(p):run.sha(p) for p in sorted(paths)}

def bindings(out):
    rs,libs=run.recipe()
    paths={p.resolve() for p in HERE.iterdir() if p.is_file()}
    paths.update([Path(sys.executable).resolve(),Path('/usr/bin/nm'),PARENT/'report.json',out/'expected.json',out/'StarFile_unix.instrumented.cpp'])
    parent=json.loads((PARENT/'report.json').read_text())
    paths.update(map(Path,parent['bindings']))
    paths.update(PARENT/(str(i)+'.o') for i in range(113))
    paths.update(Path(p) for p in libs if Path(p).is_file())
    for name in ('platform','driver'):
        paths.add(out/(name+'.d'))
        for word in shlex.split((out/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]):
            p=Path(word);paths.add((p if p.is_absolute() else run.CM/p).resolve())
    return {str(p):run.sha(p) for p in sorted(paths)}

def check_output(data,out,i):
    case,n=CASES[i];lines=data.decode().splitlines();run.need(lines[-1]==('same-exception' if n else 'return'),'termination/exception identity')
    events=[]
    for index,line in enumerate(lines[:-1],1):
        ordinal,path=line.split(':');run.need(ordinal==str(index),'call ordinal');events.append(bytes.fromhex(path).decode())
    m=model(out)
    if case=='siblings':
        run.need(len(events)==len(m[case]) and set(events)==set(m[case]),'sibling membership')
        for child in events:
            for ancestor in events:
                if child.startswith(ancestor+'/'):run.need(events.index(child)<events.index(ancestor),'descendant before ancestor')
    else:run.need(events==(m[case][:n] if n else m[case]),'literal chain/empty trace')

def validate(q,out,check_parent=True):
    if check_parent:audit.validate(json.loads((PARENT/'report.json').read_text()),PARENT)
    run.need(run.sha(PARENT/'report.json')==PIN,'parent pin')
    run.need(q['status']=='INSTRUMENTED_REMOVAL_REPEAT_PASS','scope')
    run.need(initial(out)==json.loads((out/'initial.json').read_text()),'pre-scan source/tool/object freeze')
    run.need((out/'StarFile_unix.instrumented.cpp').read_bytes()==generated(),'mechanical full platform copy')
    run.need(json.loads((out/'expected.json').read_text())==json.loads(json.dumps(model(out))),'frozen model')
    run.need(q['bindings']==bindings(out)==json.loads((out/'before.json').read_text())==json.loads((out/'after.json').read_text()),'complete dependency bindings')
    p=plan(out);run.need([(c['name'],c['command']) for c in q['commands']]==p,'exact argv plan')
    required={out/n for n in ['initial.json','StarFile_unix.instrumented.cpp','expected.json','platform.d','driver.d','platform.o','driver.o','native','native.map','before.json','after.json','preexecute.json','tree-before.json','tree-after.json']}
    required.update(out/(name+ext) for name,_ in p for ext in ('.stdout','.stderr','.command.json'))
    required.update(out/'trees'/name for name in FILES)
    run.need(set(q['artifacts'])==set(map(str,required)),'complete artifacts')
    for path,h in q['artifacts'].items():run.need(run.sha(path)==h,'artifact drift')
    for c in q['commands']:
        name=c['name'];run.need(c==json.loads((out/(name+'.command.json')).read_text()),'command mirror')
        run.need(type(c['returncode']) is int and c['returncode']==0,'exit')
        run.need(c['stdin']=={'kind':'pipe','size':0,'sha256':run.hashlib.sha256(b'').hexdigest()},'owned empty pipe')
        run.need(str(Path(c['command'][0]).resolve())==c['executable'] and run.sha(c['executable'])==c['before']==c['after'],'executable')
        for stream in ('stdout','stderr'):run.need(run.sha(out/(name+'.'+stream))==c[stream],'streams')
        if name.startswith('run-'):check_output((out/(name+'.stdout')).read_bytes(),out,int(name.rsplit('-',1)[1]))
    symbols=(out/'symbols.stdout').read_text().splitlines()
    hits=[s for s in symbols if 'Star::File::remove(Star::String const&)' in s]
    run.need(len(hits)==1 and ' T ' in hits[0],'one strong static remove symbol')
    rs,_=run.recipe();idx=next(i for i,r in enumerate(rs) if Path(r['source']).name=='StarFile_unix.cpp')
    table=(out/'native.map').read_bytes().split(b'# Object files:\n',1)[1].split(b'# Sections:',1)[0]
    entries=[line.split(b'] ',1)[1] for line in table.splitlines() if b'] ' in line]
    wanted=[out/'driver.o',*[out/'platform.o' if i==idx else PARENT/(str(i)+'.o') for i in range(113)]]
    actual=[e for e in entries if b'/file-lab/' in e]
    run.need(actual==[str(p).encode() for p in wanted],'actual ordered native object closure')
    run.need(str(PARENT/(str(idx)+'.o')).encode() not in entries,'original platform absent')
    pre=json.loads((out/'preexecute.json').read_text())
    expected_pre={out/n for n in ['initial.json','platform.o','driver.o','native','native.map','StarFile_unix.instrumented.cpp','expected.json','platform.d','driver.d','before.json','tree-before.json']}
    expected_pre.update(out/(n+e) for n,_ in p if not n.startswith('run-') for e in ('.stdout','.stderr','.command.json'))
    run.need(set(pre)==set(map(str,expected_pre)),'preexecution membership')
    for path,h in pre.items():run.need(run.sha(path)==h,'preexecution hash')
    run.need(tree(out)==json.loads((out/'tree-before.json').read_text())==json.loads((out/'tree-after.json').read_text()),'tree audit')
    for i in range(len(CASES)):run.need((out/f'run-0-{i}.stdout').read_bytes()==(out/f'run-1-{i}.stdout').read_bytes(),'exact repeat')
    return q

def acquire(out):
    run.need(out.parent==BASE and not out.exists(),'exclusive output')
    run.need(run.sha(PARENT/'report.json')==PIN,'parent pin')
    audit.validate(json.loads((PARENT/'report.json').read_text()),PARENT)
    out.mkdir();(out/'StarFile_unix.instrumented.cpp').write_bytes(generated());run.dump(out/'expected.json',model(out))
    (out/'trees').mkdir()
    for d in DIRS:(out/'trees'/d).mkdir()
    for n,b in FILES.items():
        with (out/'trees'/n).open('xb') as f:f.write(b)
    run.dump(out/'tree-before.json',tree(out));commands=[]
    p=plan(out); frozen=initial(out);run.dump(out/'initial.json',frozen)
    for name,args in p[:2]:commands.append(run.cmd(args,name,out,b''))
    run.need(frozen==initial(out),'scan input drift')
    before=bindings(out);run.dump(out/'before.json',before)
    for name,args in p[2:]:
        if name=='run-0-0':
            run.dump(out/'preexecute.json',{str(f):run.sha(f) for f in out.iterdir() if f.is_file()})
        run.need(all(run.sha(k)==v for k,v in before.items()),'input drift before command')
        tree(out);commands.append(run.cmd(args,name,out,b''));tree(out)
        if name.startswith('run-'):check_output((out/(name+'.stdout')).read_bytes(),out,int(name.rsplit('-',1)[1]))
    after=bindings(out);run.need(before==after,'input drift');run.dump(out/'after.json',after);run.dump(out/'tree-after.json',tree(out))
    q=dict(status='INSTRUMENTED_REMOVAL_REPEAT_PASS',bindings=before,commands=commands,artifacts={str(f):run.sha(f) for f in out.rglob('*') if f.is_file()})
    run.dump(out/'report.json',q);validate(q,out)
    print(q['status'],run.sha(out/'report.json'),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['acquire','verify']);ap.add_argument('output',type=Path);a=ap.parse_args();out=a.output.resolve()
    if a.phase=='acquire':acquire(out)
    else:validate(json.loads((out/'report.json').read_text()),out);print('INSTRUMENTED_REMOVAL_REPEAT_PASS')
