import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,shlex,hashlib
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent))
import run,audit,contract,supplement
P=run.BASE/'parent-final-r2'
B=run.ROOT/'build/file-lab/host-worker-r1'
def acquire(out):
 run.need(not out.exists() and out.is_relative_to(B),'fresh owned output');out.mkdir()
 run.need(run.sha(P/'report.json')=='f1670d04f4620e6c68e5f8348c0d8090bfc7ba5279f733e51bbe9ed0c1cbb681','parent report pin')
 audit.validate(json.loads((P/'report.json').read_text()),P)
 rs,libs=run.recipe();r=rs[57];commands=[]
 sources={'wrappers':H/'wrappers.cpp','controller':H/'controller.cpp','driver':H/'driver.cpp','supplement':H.parent/'supplement.cpp','protocol':H/'protocol.cpp','layout':H/'layout.cpp'}
 before={str(p):run.sha(p) for p in H.iterdir() if p.is_file()}
 before.update({str(P/(str(i)+'.o')):run.sha(P/(str(i)+'.o')) for i in range(113)})
 before[str(P/'report.json')]=run.sha(P/'report.json')
 (out/'snapshots').mkdir()
 for p in sorted(H.iterdir()):
  if p.is_file():
   dest=out/'snapshots'/p.name;dest.write_bytes(p.read_bytes());before[str(dest)]=run.sha(dest)
 for name,source in sources.items():
  commands.append(run.cmd([r['compiler'],*r['flags'],'-M','-MF',out/(name+'.d'),source],'deps-'+name,out))
  for word in shlex.split((out/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]):
   p=Path(word);p=(p if p.is_absolute() else run.CM/p).resolve();before[str(p)]=run.sha(p)
 before.update({str(Path(p).resolve()):run.sha(p) for p in libs if Path(p).is_file()})
 before[str(Path(r['compiler']).resolve())]=run.sha(Path(r['compiler']).resolve())
 run.dump(out/'before.json',before)
 for name,source in sources.items():commands.append(run.cmd([r['compiler'],*r['flags'],'-c',source,'-o',out/(name+'.o')],'compile-'+name,out))
 commands.append(run.cmd([r['compiler'],'-x','c','-std=c11','-pedantic-errors','-Wall','-Wextra','-c',H/'strict.c','-o',out/'strict.o'],'strict-c11',out))
 objects=[out/'wrappers.o' if i==57 else P/(str(i)+'.o') for i in range(113)]
 for name,driver,objs in [('native','driver',objects),('supplement','supplement',objects),('bypass','driver',[P/(str(i)+'.o') for i in range(113)])]:
  commands.append(run.cmd([r['compiler'],*r['flags'],out/(driver+'.o'),out/'controller.o',*objs,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',out/name],'link-'+name,out))
 commands.append(run.cmd([r['compiler'],*r['flags'],out/'protocol.o',out/'controller.o','-o',out/'protocol'],'link-protocol',out))
 commands.append(run.cmd([r['compiler'],*r['flags'],out/'layout.o','-o',out/'layout'],'link-layout',out))
 commands.append(run.cmd(['/usr/bin/nm','-gUC',out/'wrappers.o'],'symbols',out))
 symbols=sorted({line.split(' T ',1)[1] for line in (out/'symbols.stdout').read_text().splitlines() if ' T Star::File::' in line});run.need(len(symbols)==34,'34 symbols')
 run.dump(out/'preexecute.json',{str(p):run.sha(p) for p in out.iterdir() if p.is_file()})
 for name,exe in [('native','native'),('repeat','native'),('supplement','supplement'),('supplement-repeat','supplement'),('bypass','bypass')]:
  f,expected,final=supplement.model() if name.startswith('supplement') else (contract.fixtures(),contract.expected(),contract.final_files())
  leaf=out/(name+'-cases');leaf.mkdir()
  if name.startswith('supplement'):(leaf/'backup.b1').mkdir()
  for k,v in f.items():(leaf/k).write_bytes(v)
  commands.append(run.cmd([out/exe,leaf],name,out,b''))
  run.need((out/(name+'.stdout')).read_bytes()==expected,'ordered oracle '+name);run.audit(leaf,final)
  if not name.startswith('supplement'):
   counts=[list(map(int,x.split())) for x in (out/(name+'.stderr')).read_text().splitlines()]
   run.need(len(counts)==34 and [x[0] for x in counts]==list(range(34)),'counter membership')
   run.need(all(a==s+e and (a>0 if name!='bypass' else a==0) for m,a,s,e in counts),'positive balanced counters/native bypass')
 commands.append(run.cmd([out/'protocol'],'protocol',out,b''))
 commands.append(run.cmd([out/'layout'],'layout',out,b''))
 after={p:run.sha(p) for p in before};run.dump(out/'after.json',after);run.need(before==after,'input drift')
 run.dump(out/'commands.json',commands)
 q=dict(status='FINITE_NATIVE_PROTOTYPE_PARTIAL',parent=str(P),bindings=before,commands=commands,symbols=symbols,limitations=['controller counters start after native initialization prefixes in modes 0,2,3,4,5,7,33','output span guard covers Context and lambda payload, not all reachable native objects','removal integration has separate receipt','full-expression source audit pending','no Rust, OS deletion, OOM, arbitrary pointers, platform-general, or application proof'],artifacts={str(p):run.sha(p) for p in out.rglob('*') if p.is_file()})
 run.dump(out/'report.json',q);print(q['status'])
if __name__=='__main__':acquire(Path(sys.argv[1]).resolve())
