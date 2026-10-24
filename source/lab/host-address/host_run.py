#!/usr/bin/env python3
import argparse,hashlib,json,pathlib,subprocess,sys,importlib.util
root=pathlib.Path(__file__).resolve().parents[3];lab=root/'source/lab/host-address'
ap=argparse.ArgumentParser();ap.add_argument('--values',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);args=ap.parse_args();p=args.output.absolute();base=root/'build/host-address-lab'
if p.exists() or p==base or not p.is_relative_to(base) or any(x.is_symlink() for x in [p,*p.parents]):ap.error('fresh owned nonsymlink output required')
from verify_receipts import verify
verify(args.values/'report.json')
p.mkdir(parents=True);r=json.loads((args.values/'report.json').read_text());link=r['link'];receipts=[];all_binaries={}
def sha(x):return hashlib.sha256(pathlib.Path(x).read_bytes()).hexdigest()
def run(cmd,name):
 cmd=list(map(str,cmd));before_exe=sha(pathlib.Path(cmd[0]).resolve());x=subprocess.run(cmd,cwd=root,capture_output=True,timeout=60);(p/(name+'.stdout')).write_bytes(x.stdout);(p/(name+'.stderr')).write_bytes(x.stderr);receipts.append(dict(name=name,command=cmd,returncode=x.returncode,executable_sha256=sha(pathlib.Path(cmd[0]).resolve()),stdout_sha256=hashlib.sha256(x.stdout).hexdigest(),stderr_sha256=hashlib.sha256(x.stderr).hexdigest()));(p/'receipts.json').write_text(json.dumps(receipts,indent=2));
 if sha(pathlib.Path(cmd[0]).resolve())!=before_exe:raise RuntimeError('executed tool drift')
 if x.returncode:raise RuntimeError(name+' '+str(x.returncode)+' '+x.stderr.decode()[-3000:])
 return x.stdout
tracked={**r['bindings'],str(pathlib.Path(link['archive'])):r['archive_sha256']}
# Parent extended these two owned fixtures after oracle-final-r1. Bind the
# current versions explicitly and build a FRESH original baseline below.
fixture_changes={}
for f in (lab/'lab.cpp',lab/'run.py'):
 old=tracked.pop(str(f));snapshot=p/('fixture-'+f.name);snapshot.write_bytes(f.read_bytes());now=sha(snapshot)
 if old!=now:fixture_changes[str(f)]={'oracle_sha256':old,'snapshot_sha256':now}
 tracked[str(snapshot)]=now
for f,h in tracked.items():
 if sha(f)!=h:raise RuntimeError('identity drift before '+f)
for f in (lab/'host_contract.cpp',lab/'host_contract.hpp',lab/'host_contract_test.cpp',pathlib.Path(__file__).resolve()):tracked[str(f)]=sha(f)
(p/'before.json').write_text(json.dumps(tracked,indent=2))
def compile(src,name,corpus=True):
 exe=p/name;run([link['compiler'],*link['flags'],'-I'+str(lab),*([p/'fixture-lab.cpp'] if corpus else []),src,link['archive'],*link['libraries'],'-Wl,-dead_strip','-o',exe],name+'-compile');all_binaries[str(exe)]=sha(exe);return exe
(p/'strict.c').write_text('#include "host_contract.hpp"\nint main(void){return HA_EP_HASH != 26 || HA_CATCH_NETWORK != 36 || HA_READ_INDEX != 37;}\n')
run([link['compiler'],'-x','c','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-I'+str(lab),'-fsyntax-only',p/'strict.c'],'strict-c11')
original=compile(lab/'StarHostAddress.original.cpp','original-fresh');baseline=run([original],'original-fresh');
exe=compile(lab/'host_contract.cpp','prototype-final');got=run([exe],'prototype-final');again=run([exe],'prototype-repeat');
if got!=baseline or again!=baseline:raise RuntimeError('whole ordered mismatch')
spec=importlib.util.spec_from_file_location('oracle',p/'fixture-run.py');o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o);count=o.anchors(got)
test=compile(lab/'host_contract_test.cpp','contract-test-final',False);run([test],'contract-test-final')
s=(lab/'host_contract.cpp').read_text();mutants={
 'hash-consume':s.replace('h=h*101+byte(slot,i)','h=h*103+byte(slot,i)'),
 'last-resolver':s.replace('call(HA_CHILD,HA_CHILD_SET_RAW,HA_BUFFER);break;}call(HA_RESOLVER_NEXT);','call(HA_CHILD,HA_CHILD_SET_RAW,HA_BUFFER);}call(HA_RESOLVER_NEXT);'),
 'early-port':s.replace('streamTemporary.emplace(endpoint->address());return 0;','streamTemporary.emplace(endpoint->address());supplied=endpoint->port();return 0;').replace('*stream<<endpoint->port();return 0;','*stream<<supplied;return 0;')}
controls=[];artifacts={}
for name,body in mutants.items():
 if body==s:raise RuntimeError('empty mutant '+name)
 f=p/(name+'.cpp');f.write_text(body);e=compile(f,name);out=run([e],name)
 if out==baseline:raise RuntimeError('escaped '+name)
 controls.append(name);artifacts[str(f)]=sha(f);artifacts[str(e)]=sha(e)
for f,h in tracked.items():
 if sha(f)!=h:raise RuntimeError('identity drift after '+f)
(p/'after.json').write_text(json.dumps({f:sha(f) for f in tracked},indent=2))
report=dict(fixture_changes=fixture_changes,status='FINITE_NATIVE_PROTOTYPE_AND_SELECTED_PROTOCOL_PASS',cases=count,controls=controls,ordered_sha256=hashlib.sha256(got).hexdigest(),bindings=tracked,artifacts=artifacts,binaries=all_binaries,receipts=receipts,limits=['No Rust, production integration, application or TCP qualification','Header adds formal READ_INDEX37; no byte-read sentinel. Selected resolver lifetime/typed extent/nonwrap tests pass, not exhaustive protocol coverage','Native callback per-mode operation allowlist plus output/terminal guards are not a full transition automaton','Catch-body allocation failure replacement not injected; only code-traced','No destructor/allocation timing qualification'])
(p/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ('status','cases','controls','ordered_sha256')}))
