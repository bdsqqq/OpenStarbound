#!/usr/bin/env python3
"""Read-only finite production parity/configuration replay, not game adoption."""
import argparse,hashlib,json,re,shlex,sys
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'build/id-map-production-r2';B=H.parent/'id-map';BOUND=H.parent/'id-map-boundary'
sys.path[:0]=[str(H),str(B),str(BOUND),str(H.parent)]
import configuration,model,edge_model,providers,native_symbols,native_evidence_json as codec
need=providers.need;sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def expected():
 names=[]
 for backend in ['off','on']:
  for role in ['native','edges','trace']:names += [backend+'-'+role+s for s in ['-compile','-expand','-link','','-repeat']]
  names += [backend+'-'+role+'-negative'for role in ['lazy','hash-move','opaque-auto']]
  names += [backend+'-syntax-'+role for role in ['StarStatSet','StarStatusController']]
 return names+['cmake-off','cmake-on']
def membership(r):need(r['commands']==expected(),'exact 42 production command roles')
def audit(pin):
 need(sha(O/'report.json')==pin,'external production report pin');r=load(O/'report.json');membership(r);ad=load(O/'admission.json');need(sha(O/'admission.json')==r['admissionSha256'],'production admission pin')
 for p,h in r['products'].items():need(sha(p)==h,'product '+p)
 for p,h in ad['witness']['files'].items():need(sha(p)==h,'fresh source/tool/resource '+p)
 for p,target in ad['witness']['aliases'].items():need(str(Path(p).resolve(strict=True))==target,'original alias identity')
 for name in expected():
  p=load(O/(name+'.plan.json'));e=load(O/(name+'.receipt.json'));s=load(O/(name+'.started.json'));code=1 if name.endswith('-negative')else 0
  need(e['returncode']==code and e['reaped']is True and e['group_gone']is True and e['timed_out']is False,'actual role terminal '+name);need(e['pid']>0 and e['pid']==e['pgid']==s['pid']==s['pgid']and s['os_start'],'actual OS PID/group');need(e['started_ns']==s['started_ns']<=e['ended_ns']and e['ended_ns']/1e9<=ad['deadline'],'same original command deadline');need(p['admission_sha256']==r['admissionSha256'],'actual command epoch')
  need(e['plan_sha256']==sha(O/(name+'.plan.json'))and e['stdout_sha256']==sha(O/(name+'.stdout'))and e['stderr_sha256']==sha(O/(name+'.stderr')),'actual plan/output binding')
  for path,h in p['argv_files'].items():need(sha(path)==h,'actual immutable command input')
 recipe=load(O/'recipe.json');need(sha(O/'recipe.json')==ad['recipeSha256']and len(recipe['objects'])==len(set(recipe['objects']))==113,'exact reference object recipe');archive=Path(ad['archive']);need(sha(archive)==ad['archiveSha256'],'same canonical Rust archive');owners=providers.physical(archive);saved=codec.loads((O/'live-providers.typed').read_text());c=recipe['compiler'];data={}
 for backend in ['off','on']:
  flags=[*recipe['flags']]+(['-DSTAR_USE_RUST_ID_MAP']if backend=='on'else[])
  for role,source in [('native',B/'native.cpp'),('edges',B/'edges.cpp'),('trace',H/'trace.cpp')]:
   name=backend+'-'+role;need(load(O/(name+'-compile.plan.json'))['argv']==[c,*flags,'-MD','-MF',str(O/(name+'.d')),'-c',str(source),'-o',str(O/(name+'.o'))],'exact actual production compiler role');deps=[str(Path(p).resolve())for p in shlex.split((O/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)[1])];need(str(R/'source/core/StarIdMap.hpp')in deps and str(BOUND/'StarIdMap.hpp')not in deps and ((str(R/'source/core/StarIdMapHost.hpp')in deps)==(backend=='on')),'real header, no lab shadow, no host OFF')
   link=[c,*recipe['flags'],*recipe['objects'],str(O/(name+'.o')),*([str(archive)]if backend=='on'else[]),*recipe['libraries'],'-Wl,-dead_strip','-Wl,-map,'+str(O/(name+'.map')),'-Wl,-t,-trace_implicit_libraries','-o',str(O/name)];need(load(O/(name+'-link.plan.json'))['argv']==link and load(O/(name+'-expand.plan.json'))['argv']==[c,'-###',*link[1:]],'exact selected objects/archive profile')
   symbols=native_symbols.live_symbols((O/(name+'.map')).read_bytes())
   if backend=='on':need(providers.live(symbols,owners,archive,role=='trace')==saved[name],'actual live canonical provider declarations')
   else:need(not any(s.name in providers.EXPORTS for s in symbols),'OFF links and runs without Rust providers')
   for suffix in ['','-repeat']:need(load(O/(name+suffix+'.plan.json'))['argv']==[str(O/name)],'actual tested executable')
   data[name]=(O/(name+'.stdout')).read_text();need(data[name]==(O/(name+'-repeat.stdout')).read_text(),'repeat byte identity')
  for path,flags0 in ad['consumerFlags'].items():need(load(O/(backend+'-syntax-'+Path(path).stem+'.plan.json'))['argv']==[c,*flags0,*(['-DSTAR_USE_RUST_ID_MAP']if backend=='on'else[]),'-fsyntax-only',str(R/path)],'actual consumer OFF/ON typecheck')
 for role,reader in [('native',model.verify),('edges',edge_model.verify)]:reader(data['off-'+role]);reader(data['on-'+role]);need(data['off-'+role]==data['on-'+role],'literal stream parity')
 need([x for x in data['off-trace'].splitlines()if x.startswith('TRACE\t')]==r['typedTraces']==[x for x in data['on-trace'].splitlines()if x.startswith('TRACE\t')],'five exact typed traces');need('PASS\tproduction-ten-rust-roots\n'in data['on-trace'],'all ten actual production roots')
 same_config=configuration.check(O/'cmake-off',O/'cmake-on',r['configuration']['rustc']);need(same_config==r['configuration'],'actual selector/real Rust.cmake graph');need(load(O/'sdk-before.json')==load(O/'sdk-after.json'),'actual SDK before/after')
 return dict(status='FINITE_PRODUCTION_IDMAP_REPLAY_PASS',commands=42,images=6,consumerTypechecks=4,negativeCompilations=6,typedTraces=5,limits=r['limits'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--report-sha',required=True);a=p.parse_args()
 def guard(event,args):
  if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.exec'}:raise ValueError('read-only production verifier')
 sys.addaudithook(guard);print(json.dumps(audit(a.report_sha),indent=2,sort_keys=True))
if __name__=='__main__':main()
