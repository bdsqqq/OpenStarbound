"""Consume the qualified instrumented reference without editing its artifacts."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,importlib.util
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent));import run,audit
spec=importlib.util.spec_from_file_location('removal',H.parent/'removal/calibrate.py');removal=importlib.util.module_from_spec(spec);spec.loader.exec_module(removal)
REFERENCE=run.ROOT/'build/file-lab/removal-worker-r1/acquire-r2'
PIN='e0484806e075469a90751be55c7044564198567a3405ada3db60a365fe1d893d'
def plan(out,prototype):
 rs,libs=run.recipe();idx=next(i for i,r in enumerate(rs) if Path(r['source']).name=='StarFile_unix.cpp');r=rs[57]
 objects=[prototype/'wrappers.o' if i==57 else REFERENCE/'platform.o' if i==idx else removal.PARENT/(str(i)+'.o') for i in range(113)]
 p=[('link',[r['compiler'],*r['flags'],REFERENCE/'driver.o',prototype/'controller.o',*objects,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/'native.map'),'-o',out/'native']),('symbols',['/usr/bin/nm','-gUC',out/'native'])]
 p += [(f'run-{rep}-{i}',[out/'native',out/'trees'/case,str(n)]) for rep in range(2) for i,(case,n) in enumerate(removal.CASES)]
 return [(n,list(map(str,args))) for n,args in p]
def bindings(prototype):
 q=json.loads((REFERENCE/'report.json').read_text());p=json.loads((prototype/'report.json').read_text())
 paths=set(q['bindings'])|set(q['artifacts'])|set(p['bindings'])|{str(REFERENCE/'report.json'),str(prototype/'report.json'),str(prototype/'wrappers.o'),str(prototype/'controller.o'),str(H/'removal_replay.py')}
 return {s:run.sha(s) for s in sorted(paths)}
def verify(q,out,prototype):
 run.need(run.sha(REFERENCE/'report.json')==PIN,'reference pin');removal.validate(json.loads((REFERENCE/'report.json').read_text()),REFERENCE)
 run.need(q['status']=='INSTRUMENTED_HOST_REMOVAL_REPEAT_PASS','scope')
 run.need(q['bindings']==bindings(prototype)==json.loads((out/'before.json').read_text())==json.loads((out/'after.json').read_text()),'complete lineage')
 p=plan(out,prototype);run.need([(c['name'],c['command']) for c in q['commands']]==p,'complete argv plan')
 required={out/n for n in ['native','native.map','before.json','after.json','tree-before.json','tree-after.json','preexecute.json']}
 required.update(out/(n+ext) for n,_ in p for ext in ['.stdout','.stderr','.command.json']);required.update(out/'trees'/n for n in removal.FILES)
 run.need(set(q['artifacts'])==set(map(str,required)),'required artifacts')
 for path,digest in q['artifacts'].items():run.need(run.sha(path)==digest,'artifact bytes')
 for c in q['commands']:
  n=c['name'];run.need(c==json.loads((out/(n+'.command.json')).read_text()) and type(c['returncode']) is int and c['returncode']==0,'command receipt')
  run.need(c['stdin']=={'kind':'pipe','size':0,'sha256':run.hashlib.sha256(b'').hexdigest()},'owned stdin')
  run.need(str(Path(c['command'][0]).resolve())==c['executable'] and run.sha(c['executable'])==c['before']==c['after'],'executable identity')
  for st in ('stdout','stderr'):run.need(run.sha(out/(n+'.'+st))==c[st],'streams')
  if n.startswith('run-'):removal.check_output((out/(n+'.stdout')).read_bytes(),out,int(n.rsplit('-',1)[1]))
 run.need(removal.tree(out)==json.loads((out/'tree-before.json').read_text())==json.loads((out/'tree-after.json').read_text()),'retained tree')
 for i in range(6):run.need((out/f'run-0-{i}.stdout').read_bytes()==(out/f'run-1-{i}.stdout').read_bytes(),'exact repeat')
 table=(out/'native.map').read_bytes().split(b'# Object files:\n',1)[1].split(b'# Sections:',1)[0];entries=[line.split(b'] ',1)[1].decode() for line in table.splitlines() if b'] ' in line]
 expected=[s for s in p[0][1] if s.endswith('.o')]
 run.need([s for s in entries if '/file-lab/' in s]==expected,'actual object closure')
 for needle in ['Star::File::remove(Star::String const&)','Star::File::removeDirectoryRecursive(Star::String const&)']:
  hits=[s for s in (out/'symbols.stdout').read_text().splitlines() if needle in s];run.need(len(hits)==1 and ' T ' in hits[0],'sole strong symbol')
 pre=json.loads((out/'preexecute.json').read_text());wanted={out/n for n in ['native','native.map','before.json','tree-before.json']};wanted.update(out/(n+e) for n,_ in p[:2] for e in ['.stdout','.stderr','.command.json'])
 run.need(set(pre)==set(map(str,wanted)),'preexecute membership')
 for s,d in pre.items():run.need(run.sha(s)==d,'preexecute bytes')
 return q

def acquire(out,prototype):
 run.need(out.parent==run.ROOT/'build/file-lab/host-worker-r1' and not out.exists(),'fresh owned output')
 run.need(run.sha(REFERENCE/'report.json')==PIN,'reference pin');removal.validate(json.loads((REFERENCE/'report.json').read_text()),REFERENCE)
 out.mkdir();(out/'trees').mkdir()
 for d in removal.DIRS:(out/'trees'/d).mkdir()
 for n,b in removal.FILES.items():(out/'trees'/n).write_bytes(b)
 run.dump(out/'tree-before.json',removal.tree(out));before=bindings(prototype);run.dump(out/'before.json',before);commands=[]
 for name,args in plan(out,prototype):
  if name=='run-0-0':run.dump(out/'preexecute.json',{str(p):run.sha(p) for p in out.iterdir() if p.is_file()})
  commands.append(run.cmd(args,name,out,b''));removal.tree(out)
  if name.startswith('run-'):removal.check_output((out/(name+'.stdout')).read_bytes(),out,int(name.rsplit('-',1)[1]))
 after=bindings(prototype);run.need(before==after,'lineage drift');run.dump(out/'after.json',after);run.dump(out/'tree-after.json',removal.tree(out))
 q=dict(status='INSTRUMENTED_HOST_REMOVAL_REPEAT_PASS',bindings=before,commands=commands,artifacts={str(p):run.sha(p) for p in out.rglob('*') if p.is_file()});run.dump(out/'report.json',q);verify(q,out,prototype);print(q['status'])
if __name__=='__main__':
 out,prototype=map(lambda s:Path(s).resolve(),sys.argv[1:3])
 if '--verify' in sys.argv:verify(json.loads((out/'report.json').read_text()),out,prototype)
 else:acquire(out,prototype)
