"""Reconstruct membership, commands, closure, native rows and counter controls."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,shlex,copy
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent));import run,audit,contract,supplement
P=run.BASE/'parent-final-r2'
NAMES=['wrappers','controller','driver','supplement','protocol','layout']
RUNS=[('native','native'),('repeat','native'),('supplement','supplement'),('supplement-repeat','supplement'),('bypass','bypass')]
def plan(out):
 rs,libs=run.recipe();r=rs[57];p=[]
 for name in NAMES:
  source=H.parent/'supplement.cpp' if name=='supplement' else H/(name+'.cpp')
  p.append(('deps-'+name,[r['compiler'],*r['flags'],'-M','-MF',out/(name+'.d'),source]))
 for name in NAMES:
  source=H.parent/'supplement.cpp' if name=='supplement' else H/(name+'.cpp')
  p.append(('compile-'+name,[r['compiler'],*r['flags'],'-c',source,'-o',out/(name+'.o')]))
 p.append(('strict-c11',[r['compiler'],'-x','c','-std=c11','-pedantic-errors','-Wall','-Wextra','-c',H/'strict.c','-o',out/'strict.o']))
 for name,driver in [('native','driver'),('supplement','supplement'),('bypass','driver')]:
  objs=[out/'wrappers.o' if i==57 and name!='bypass' else P/(str(i)+'.o') for i in range(113)]
  p.append(('link-'+name,[r['compiler'],*r['flags'],out/(driver+'.o'),out/'controller.o',*objs,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(out/(name+'.map')),'-o',out/name]))
 for name in ['protocol','layout']:
  p.append(('link-'+name,[r['compiler'],*r['flags'],out/(name+'.o'),*([out/'controller.o'] if name=='protocol' else []),'-o',out/name]))
 p.append(('symbols',['/usr/bin/nm','-gUC',out/'wrappers.o']))
 p.extend((name,[out/exe,out/(name+'-cases')]) for name,exe in RUNS)
 p.extend((name,[out/name]) for name in ['protocol','layout'])
 return [(n,list(map(str,a))) for n,a in p]
def required_artifacts(out):
 result={out/n for n in ['before.json','after.json','commands.json','preexecute.json','strict.o','native','native.map','supplement','supplement.map','bypass','bypass.map','protocol','layout']}
 result.update(out/(n+e) for n in NAMES for e in ['.d','.o'])
 result.update(out/(n+e) for n,_ in plan(out) for e in ['.stdout','.stderr','.command.json'])
 result.update(out/'snapshots'/p.name for p in H.iterdir() if p.is_file())
 for name,_ in RUNS:
  final=supplement.model()[2] if name.startswith('supplement') else contract.final_files()
  result.update(out/(name+'-cases')/n for n in final)
 return set(map(str,result))
def bindings(out):
 rs,libs=run.recipe();r=rs[57]
 paths={p for p in H.iterdir() if p.is_file()}|{out/'snapshots'/p.name for p in H.iterdir() if p.is_file()}|{P/(str(i)+'.o') for i in range(113)}|{P/'report.json',Path(r['compiler']).resolve()}
 paths.update(Path(p).resolve() for p in libs if Path(p).is_file())
 for name in NAMES:
  for w in shlex.split((out/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1]):
   p=Path(w);paths.add((p if p.is_absolute() else run.CM/p).resolve())
 return {str(p):run.sha(p) for p in paths}
def validate(q,out):
 run.need(out.parent==run.ROOT/'build/file-lab/host-worker-r1','owned output')
 run.need(q['status']=='FINITE_NATIVE_PROTOTYPE_PARTIAL' and q['parent']==str(P),'scope')
 wanted=plan(out);run.need([(c['name'],c['command']) for c in q['commands']]==wanted,'complete command argv')
 run.need(set(q['artifacts'])==required_artifacts(out),'complete artifacts')
 # Membership checks precede expensive parent replay, so omitted dependencies
 # cannot be hidden by a self-consistent supplied dictionary.
 before=json.loads((out/'before.json').read_text());run.need(q['bindings']==before==json.loads((out/'after.json').read_text()),'binding mirrors')
 run.need(q['commands']==json.loads((out/'commands.json').read_text()),'command list mirror')
 run.need(run.sha(P/'report.json')=='f1670d04f4620e6c68e5f8348c0d8090bfc7ba5279f733e51bbe9ed0c1cbb681','exact parent')
 audit.validate(json.loads((P/'report.json').read_text()),P)
 run.need(q['bindings']==bindings(out),'reconstructed full closure')
 for p in H.iterdir():
  if p.is_file():run.need(p.read_bytes()==(out/'snapshots'/p.name).read_bytes(),'snapshot identity')
 for p,h in q['artifacts'].items():run.need(run.sha(p)==h,'artifact drift '+p)
 for c in q['commands']:
  n=c['name'];run.need(c==json.loads((out/(n+'.command.json')).read_text()),'command mirror')
  run.need(type(c['returncode']) is int and c['returncode']==0,'normal exit')
  exe=Path(c['command'][0]).resolve();run.need(str(exe)==c['executable'] and run.sha(exe)==c['before']==c['after'],'executable identity')
  stdin={'kind':'pipe','size':0,'sha256':run.hashlib.sha256(b'').hexdigest()} if n in [x[0] for x in RUNS]+['protocol','layout'] else {'kind':'inherit'}
  run.need(c['stdin']==stdin,'owned stdin')
  for st in ['stdout','stderr']:run.need(run.sha(out/(n+'.'+st))==c[st],'stream bytes')
 for name,_ in RUNS:
  expected,final=(supplement.model()[1:]) if name.startswith('supplement') else (contract.expected(),contract.final_files())
  run.need((out/(name+'.stdout')).read_bytes()==expected,'independent ordered corpus');run.audit(out/(name+'-cases'),final)
  if not name.startswith('supplement'):
   rows=[list(map(int,s.split())) for s in (out/(name+'.stderr')).read_text().splitlines()]
   run.need(len(rows)==34 and [r[0] for r in rows]==list(range(34)),'34 counter modes')
   run.need(all(a==s+e and (a==0 if name=='bypass' else a>0) for _,a,s,e in rows),'balanced positive or bypass counters')
 for name in ['native','supplement']:
  other='repeat' if name=='native' else 'supplement-repeat'
  run.need((out/(name+'.stdout')).read_bytes()==(out/(other+'.stdout')).read_bytes(),'exact repeat')
 run.need((out/'native.stderr').read_bytes()==(out/'repeat.stderr').read_bytes(),'exact counter repeat')
 run.need((out/'protocol.stdout').read_bytes()==b'native protocol finite controls pass\n','protocol output')
 symbols=sorted({s.split(' T ',1)[1] for s in (out/'symbols.stdout').read_text().splitlines() if ' T Star::File::' in s})
 run.need(len(symbols)==34 and symbols==q['symbols'],'compiled 34 symbols')
 for name in ['native','supplement','bypass']:
  table=(out/(name+'.map')).read_bytes().split(b'# Object files:\n',1)[1].split(b'# Sections:',1)[0]
  entries=[line.split(b'] ',1)[1].decode() for line in table.splitlines() if b'] ' in line]
  args=dict(wanted)['link-'+name];run.need([s for s in entries if '/file-lab/' in s]==[s for s in args if s.endswith('.o')],'actual link object closure')
 pre=json.loads((out/'preexecute.json').read_text())
 expected={p for p in required_artifacts(out) if Path(p).parent==out}-{str(out/n) for n in ['after.json','commands.json','preexecute.json']}
 for n in [x[0] for x in RUNS]+['protocol','layout']:
  expected-={str(out/(n+e)) for e in ['.stdout','.stderr','.command.json']}
 run.need(set(pre)==expected,'preexecute membership')
 for p,h in pre.items():run.need(run.sha(p)==h,'preexecute bytes')
 return q

def controls(q,out,dest):
 dest.mkdir();results=[]
 mutations=[('omit-object',lambda x:x['artifacts'].pop(str(out/'wrappers.o'))),('omit-source',lambda x:x['bindings'].pop(str(H/'native.hpp'))),('omit-command',lambda x:x['commands'].pop()),('wrong-argv',lambda x:x['commands'][0]['command'].append('-DWRONG')),('exit',lambda x:x['commands'][0].update(returncode=1)),('stdin',lambda x:x['commands'][-1].update(stdin={'kind':'inherit'})),('status',lambda x:x.update(status='PASS'))]
 for name,fn in mutations:
  bad=copy.deepcopy(q);fn(bad);run.dump(dest/(name+'.json'),bad)
  try:validate(bad,out)
  except ValueError as e:results.append({'case':name,'rejected':str(e)})
  else:raise ValueError('escaped corruption '+name)
 run.dump(dest/'results.json',results);return results
if __name__=='__main__':
 out=Path(sys.argv[1]).resolve();q=json.loads((out/'report.json').read_text());validate(q,out)
 if len(sys.argv)>2:controls(q,out,Path(sys.argv[2]).resolve())
 print('INDEPENDENT_FINITE_NATIVE_PROTOTYPE_REPLAY_PASS_WITH_GAPS')
