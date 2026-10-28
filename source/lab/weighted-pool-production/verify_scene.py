#!/usr/bin/env python3
"""Read-only no-Rust-link/native runtime and client syntax evidence; NOT game."""
import dataclasses,hashlib,json,shlex,sys
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;R=H.parents[2];S=R/'build/weighted-pool-scene-r1';O=S/'native';sys.path[:0]=[str(H.parent),str(H.parent/'path-embed-replay')]
import native_symbols,expanded_invocation,archive_identity,object_inventory,link_trace

def guard(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty','os.exec','pty.spawn'}:raise ValueError('read-only verification')
sys.addaudithook(guard)
PIN='d8b51ab18a196b32767e956aa02bc93d5a7251589ea0078c9066711bf7de672b'
def need(b,s):
 if not b:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def no_rust(symbols):need(not any(s.name in[b'_sb_wp_run',b'_sb_wp_count',b'_rust_eh_personality']for s in symbols),'native-only image must not link Rust exports')
def flags(argv,selectors,candidate):need({x[2:]for x in argv if x.startswith('-DSTAR_USE_RUST_')}==(set(selectors)-{'STAR_USE_RUST_LINE_QUERY'}if candidate else set()),'exact28OFF/27ONexceptLINE flags')
def main():
 need(sha(O/'report.json')==PIN,'external source-bound native report');report=load(O/'report.json');ad=load(O/'admission.json');w=ad['witness'];recipe=ad['recipe']
 for p,h in report['products'].items():need(sha(p)==h,'actual immutable product '+p)
 for p,h in w['files'].items():need(sha(p)==h,'actual compiled source/tool input '+p)
 for p,target in w['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'actual alias')
 names=['syntax-reference','syntax-candidate','compile','expand','link','native-runtime'];need(sorted(p.name[:-len('.receipt.json')]for p in O.glob('*.receipt.json'))==sorted(names),'exact six native commands');plans={}
 for name in names:
  p=load(O/(name+'.plan.json'));x=load(O/(name+'.receipt.json'));s=load(O/(name+'.started.json'));need(type(x['returncode'])is int and x['returncode']==0 and x['reaped']and x['groupGone']and not x['timedOut'],'strict actual native exit');need(x['pid']==x['pgid']==s['pid']==s['pgid']and s['osStart'],'actual PID/PGID/OS start');need(x['startedWallNs']==s['startedWallNs']<=x['endedWallNs'],'terminal clock');need(p['cwd']==str(R)and p['env']==ad['env']and p['admissionSha256']==sha(O/'admission.json')and x['planSha256']==sha(O/(name+'.plan.json')),'pre-execution exact plan')
  for ext in ['stdout','stderr']:need(x[ext+'Sha256']==sha(O/(name+'.'+ext)),'actual stdout/stderr')
  plans[name]=p['argv']
 import re
 selectors=re.findall(r'option\((STAR_USE_RUST_\w+)',(R/'source/CMakeLists.txt').read_text());need(len(selectors)==28,'current full selector schema')
 for role in ad['plans']:
  need(plans['syntax-'+role['name']]==role['argv'],'actual client syntax plan');need(sha(role['flagsSource'])==role['flagsSourceSha256'],'actual original game recipe');need('-fsyntax-only'in role['argv']and'-o'not in role['argv'],'TYPECHECK ONLY');flags(role['argv'],selectors,role['name']=='candidate');dep=O/(role['name']+'.d');deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);need(str(R/'source/client/StarClientApplication.cpp')in deps and str(R/'source/application/StarBehaviorLab.hpp')in deps,'actual CURRENT client fixture sources consumed')
  for p in deps:need(str(Path(p).resolve())in w['files'],'consumed input admitted before compiler')
 obj=O/'native-link.o';dep=O/'native-link.d';need(plans['compile']==[recipe['compiler'],*recipe['flags'],'-MD','-MF',str(dep),'-c',str(H/'native_link.cpp'),'-o',str(obj)],'actual defaultOFF production program');deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);need(str(R/'source/core/StarWeightedPool.hpp')in deps and str(R/'source/core/StarWeightedPoolHost.hpp')not in deps,'native OFF production header WITHOUT host dependency');flags(plans['compile'],selectors,False)
 commands=[shlex.split(x)for x in(O/'expand.stderr').read_text().splitlines()if x.lstrip().startswith('"')];need(len(commands)==1,'one expanded ld');sys.path.insert(0,str(H.parent));import native_evidence_json as codec
 bound=codec.loads((O/'expanded.typed').read_text('ascii'));expanded_invocation.verify(bound,commands[0]);inv=bound['inventory'];need(inv['tool']==ad['tools']['CMAKE_LINKER'],'actual selected linker');objects=[*recipe['objects'],str(obj)];need(len(recipe['objects'])==113 and[p for p in inv['file_inputs']if p.endswith('.o')]==objects,'exact113 native objects');need(not any('star_engine_ffi'in p or'/rust'in p for p in inv['file_inputs']),'NO aggregate archive in actual link');need(plans['expand']==[recipe['compiler'],'-###',*plans['link'][1:]],'actual link matches fixed expansion')
 blobs={p.encode():Path(p).read_bytes()for p in inv['file_inputs']if p.endswith('.a')};tables={p:b''.join(m['name']+b'\n'for m in archive_identity.arm64_archive_members(b))for p,b in blobs.items()};link_trace.parse((O/'link.stdout').read_bytes(),[p.encode()for p in objects],tables);object_inventory.reconcile((O/'native-link.map').read_bytes(),[p.encode()for p in objects],tables,blobs);symbols=native_symbols.live_symbols((O/'native-link.map').read_bytes());no_rust(symbols);need(plans['native-runtime']==[str(O/'native-link')]and(O/'native-runtime.stdout').read_text()=='PASS\tactual-production-default-off-without-rust-link\n','ACTUAL defaultOFF runtime result')
 controls=[]
 for name,fn in [('injected-rust-provider',lambda:no_rust([*symbols,dataclasses.replace(symbols[0],name=b'_sb_wp_run')])),('missing-new-selector',lambda:flags([x for x in ad['plans'][1]['argv']if x!='-DSTAR_USE_RUST_WEIGHTED_POOL'],selectors,True))]:
  try:fn()
  except ValueError:controls.append(name);continue
  raise ValueError('known failure accepted '+name)
 print(json.dumps(dict(status=report['status'],actualCommands=6,nativeDefaultOFF='BUILT_AND_RUNTIME_TESTED_WITHOUT_RUST_ARCHIVE_OR_HOST',clientProfiles='TYPECHECKED28OFF_AND27ON_EXCEPT_LINE',isolatedFalsifiers=controls,limits=['NO actual game execution/counters/framebuffer evidence','behavior logical tests are separate synthetic fixtures']),indent=2,sort_keys=True))
if __name__=='__main__':main()
